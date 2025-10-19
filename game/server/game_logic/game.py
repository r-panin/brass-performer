from ...schema import (
    BoardState,
    PlayerColor,
    GameStatus,
    PlayerState,
    ActionProcessResult,
    RequestResult,
    Card,
    Request,
    RequestType,
    LinkType,
    CardType,
    Action,
    BoardStateExposed
)
from typing import Dict, List
import random
from uuid import uuid4
import copy
from .game_initializer import GameInitializer
from .action_processor import ActionProcessor
from .state_changer import StateChanger
from .services.event_bus import EventBus
from .services.replay_service import ReplayService
from .services.board_state_service import BoardStateService
from pathlib import Path
from collections import defaultdict
import logging



class Game:
    REPLAYS_PATH = Path(r"game\replays")

    @classmethod
    def from_partial_state(cls, partial_state:PlayerState, history:List[Action]=[]):
        game = cls()
        game.event_bus = EventBus()
        
        if history:
            state = BoardState.cardless(partial_state.state)
            known_hand = partial_state.your_hand.copy()
            deck_size = partial_state.state.deck_size
            state.deck = [Card.mock() for _ in range(deck_size)]
            transient_state_service = BoardStateService(state)
            initializer = GameInitializer() 
            card_dict = initializer._build_card_dict()
            state_changer = StateChanger(transient_state_service)

            expected_hand_sizes = {p.color: p.hand_size for p in partial_state.state.players.values()}
            for action in history:
                active_player = transient_state_service.get_active_player()
                if hasattr(action, 'card_id'):
                    if isinstance(action.card_id, int):
                        transient_state_service.give_player_a_card(active_player.color, card_dict[action.card_id])
                        if action.card_id in known_hand:
                            known_hand.pop(action.card_id)
                        expected_hand_sizes[active_player.color] -= 1
                    elif isinstance(action.card_id, list):
                        for card_id in action.card_id:
                            transient_state_service.give_player_a_card(active_player.color, card_dict[card_id])
                            if card_id in known_hand:
                                known_hand.pop(card_id)
                        expected_hand_sizes[active_player.color] -= len(action.card_id)

                state_changer.apply_action(action, transient_state_service, active_player)
                
                for player in transient_state_service.get_players().values():
                    expected_hand_sizes[player.color] += len(player.hand)
                    
                transient_state_service.wipe_hands()

            hidden_state = transient_state_service.state.hide_state()
            hidden_state.deck_size = transient_state_service.get_deck_size()
            for player in hidden_state.players.values():
                transient_player = transient_state_service.get_player(player.color)
                player.hand_size = expected_hand_sizes[player.color]
                player.has_city_wild = transient_player.has_city_wild
                player.has_industry_wild = transient_player.has_industry_wild
            game.state_service = BoardStateService(game._determine_cards(hidden_state, known_hand, partial_state.your_color))

        else:
            game.state_service = BoardStateService(game._determine_cards(partial_state.state, partial_state.your_hand, partial_state.your_color))
        
        game.action_processor = ActionProcessor(game.state_service, game.event_bus)
        game.status = GameStatus.ONGOING
        game.replay_service = None

        return game
    
    def _determine_cards(self, partial_state:BoardStateExposed, known_hand:Dict[int, Card], known_color:PlayerColor) -> BoardState:
        # Use a local initializer to avoid relying on instance attribute during reconstruction
        initializer = getattr(self, 'initializer', None) or GameInitializer()
        full_deck = initializer._build_initial_deck(len(partial_state.players))
        known_card_ids = set([card.id for card in partial_state.discard]) | set(known_hand)
        available_deck = [card for card in full_deck if card.id not in known_card_ids]

        deal_to = [player for player in partial_state.players]
        player_hands:Dict[PlayerColor, Dict[int, Card]] = defaultdict(dict)

        city_wild = next(card for card in partial_state.wilds if card.card_type == CardType.CITY)
        industry_wild = next(card for card in partial_state.wilds if card.card_type == CardType.INDUSTRY)

        if partial_state.players[known_color].has_city_wild:
            known_hand[city_wild.id] = city_wild
        if partial_state.players[known_color].has_industry_wild:
            known_hand[industry_wild.id] = industry_wild

        player_hands[known_color] = known_hand

        for player in deal_to:
            exposed_player = partial_state.players[player]
            if exposed_player.has_city_wild:
                player_hands[player][city_wild.id] = city_wild
            if exposed_player.has_industry_wild:
                player_hands[player][industry_wild.id] = industry_wild
            target_hand_size = exposed_player.hand_size
            while len(player_hands[player]) < target_hand_size and len(available_deck) > 0:
                card = available_deck.pop()
                player_hands[player][card.id] = card

        # Do not apply any additional burns here; deck_size already reflects that in the exposed state
        target_deck_size = partial_state.deck_size
        excess = len(available_deck) - target_deck_size
        for _ in range(max(0, excess)):
            if not available_deck:
                break
            available_deck.pop()

        out = BoardState.determine(partial_state, player_hands, available_deck)

        if len(out.deck) != partial_state.deck_size:
            logging.error(f"DETERMINIZED DECK SIZE DOESN'T MATCH PROVIDED DECK SIZE")
            logging.error(f"Cards in deck: {out.deck}")
            logging.error(f"Cards in discard: {out.discard}")
            for player in out.players.values():
                logging.error(f"Cards in {player.color}: {list(player.hand)}")
            logging.error(f"Known hand provided: {known_hand}")
            raise ValueError

        return out
            

    def __init__(self):
        self.id = str(uuid4())
        self.status = GameStatus.CREATED
        self.available_colors = copy.deepcopy(list(PlayerColor))
        random.shuffle(self.available_colors)

        self.event_bus = EventBus()
        self.initializer = GameInitializer()

    def start(self, player_count:int, player_colors:List[PlayerColor]):
        self.replay_service = ReplayService(self.event_bus)
        self.state_service = BoardStateService(self.initializer.create_initial_state(player_count, player_colors))
        self.action_processor = ActionProcessor(self.state_service, event_bus=self.event_bus)
        self.status = GameStatus.ONGOING
    
    def get_player_state(self, color:PlayerColor, state:BoardState=None) -> PlayerState:
        if state is None:
            state = self.state_service.get_board_state()
        return PlayerState(
            state=state.hide_state(),
            your_color=color,
            your_hand={card.id: card for card in self.state_service.get_player(color).hand.values()}
        )

    def process_action(self, action, color) -> ActionProcessResult|RequestResult:
        if self.status is not GameStatus.ONGOING:
            raise ValueError(f'Cannot submit actions to a game in {self.status}')
        process_result = self.action_processor.process_incoming_message(action, color)
        if self.concluded():
            self.status = GameStatus.COMPLETE
            self.replay_service.save_replay(self.REPLAYS_PATH / self.id)
            process_result.end_of_game = True
        return process_result

    def concluded(self):
        return self.state_service.get_deck_size() == 0 and all(not player.hand for player in self.state_service.get_players().values()) and self.state_service.get_era() is LinkType.RAIL

if __name__ == '__main__':
    game = Game()
    game.start(4, ['white', 'red', 'yellow', 'purple'])
    game_from_state = Game.from_partial_state(game.process_action(Request(request=RequestType.REQUEST_STATE), 'white'))
    with open(r'G:\brass-performer\brass-performer\game\replays\main_game.json', 'w') as game_one_file:
        game_one_file.write(game.state.model_dump_json())
    with open(r'G:\brass-performer\brass-performer\game\replays\from_state.json', 'w') as game_two_file:
        game_two_file.write(game_from_state.state.model_dump_json())
