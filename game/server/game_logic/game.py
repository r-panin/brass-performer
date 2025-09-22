from ...schema import BoardState, PlayerColor, GameStatus, PlayerState, ActionProcessResult, RequestResult, PlayerState, Card, Request, RequestType
from typing import Dict, List 
import random
from uuid import uuid4
import logging
import copy
from .game_state_manager import GameStateManager
from .action_space_generator import ActionSpaceGenerator
from .game_initializer import GameInitializer
from .action_processor import ActionProcessor
from .services.event_bus import EventBus
from .services.replay_service import ReplayService
from pathlib import Path
from collections import defaultdict



class Game:
    REPLAYS_PATH = Path(r"game\replays")
    @property
    def state(self) -> BoardState:
        return self.state_manager.current_state

    @classmethod
    def from_partial_state(cls, partial_state:PlayerState):
        game = cls()
        game.start(len(partial_state.state.players), [player for player in partial_state.state.players])
        game._determine_cards(partial_state)
        return game
    
    def _determine_cards(self, partial_state:PlayerState) -> BoardState:
        full_deck = self.initializer._build_initial_deck(len(partial_state.state.players))
        known_card_ids = set(partial_state.state.discard) | set(partial_state.your_hand)
        available_deck = [card for card in full_deck if card.id not in known_card_ids]
        deal_to = [player for player in partial_state.state.players 
              if player != partial_state.your_color]
        player_hands:Dict[PlayerColor, Dict[int, Card]] = defaultdict(dict)
        for player in deal_to:
            cards_needed = 8 - len(player_hands.get(player, {}))
            for _ in range(min(cards_needed, len(available_deck))):
                card = available_deck.pop()
                player_hands[player][card.id] = card
        player_hands[partial_state.your_color] = partial_state.your_hand
        self.state_manager = GameStateManager(BoardState.determine(partial_state.state, player_hands, available_deck), self.event_bus)
            

    def __init__(self):
        self.id = str(uuid4())
        self.status = GameStatus.CREATED
        self.available_colors = copy.deepcopy(list(PlayerColor))
        random.shuffle(self.available_colors)
        logging.basicConfig(level=logging.INFO)

        self.event_bus = EventBus()
        self.initializer = GameInitializer()

    def start(self, player_count:int, player_colors:List[PlayerColor]):
        self.replay_service = ReplayService(self.event_bus)
        self.state_manager = GameStateManager(self.initializer.create_initial_state(player_count, player_colors), self.event_bus)
        self.action_space_generator = ActionSpaceGenerator(self.state_manager)
        self.action_processor = ActionProcessor(self.state_manager, self.event_bus)
        self.status = GameStatus.ONGOING
    
    def get_player_state(self, color:PlayerColor, state:BoardState=None) -> PlayerState:
        if state is None:
            state = self.state
        return PlayerState(
            state=state.hide_state(),
            your_color=color,
            your_hand={card.id: card for card in self.state.players[color].hand.values()},
        )

    def process_action(self, action, color) -> ActionProcessResult|RequestResult:
        if self.status is not GameStatus.ONGOING:
            raise ValueError(f'Cannot submit actions to a game in {self.status}')
        process_result = self.action_processor.process_incoming_message(action, color)
        if isinstance(process_result, ActionProcessResult):
            if process_result.end_of_game:
                self.status = GameStatus.COMPLETE
                self.replay_service.save_replay(self.REPLAYS_PATH / game.id)
        return process_result

if __name__ == '__main__':
    game = Game()
    game.start(4, ['white', 'red', 'yellow', 'purple'])
    game_from_state = Game.from_partial_state(game.process_action(Request(request=RequestType.REQUEST_STATE), 'white'))
    with open(r'G:\brass-performer\brass-performer\game\replays\main_game.json', 'w') as game_one_file:
        game_one_file.write(game.state.model_dump_json())
    with open(r'G:\brass-performer\brass-performer\game\replays\from_state.json', 'w') as game_two_file:
        game_two_file.write(game_from_state.state.model_dump_json())
