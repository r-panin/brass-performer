from ...schema import LinkType, ActionContext
import random
from .services.event_bus import EventBus
from .game_initializer import GameInitializer
from ...server.game_logic.services.board_state_service import BoardStateService


class TurnManager:
    ERA_CHANGE = {
        4: 8,
        3: 9,
        2: 10
    }
    GAME_END = {
        4: 16,
        3: 18,
        2: 20
    }
    def __init__(self, starting_service:BoardStateService, event_bus:EventBus):
        self.concluded = False
        self.event_bus = event_bus
        self.era_change_on = self.ERA_CHANGE[len(starting_service.get_players())]
        self.end_game_on = self.GAME_END[len(starting_service.get_players())]

    def prepare_next_turn(self, state_service:BoardStateService) -> BoardStateService:
        state_service.advance_turn_order()
        if state_service.get_turn_index() >= len(state_service.get_turn_order()):
            state_service = self._prepare_next_round(state_service)
        first_round = state_service.get_current_round() == 1
        if not first_round:
            state_service.set_actions_left(2)
        else:
            state_service.set_actions_left(1)
        state_service.subaction_count = 0
        return state_service

    def _prepare_next_round(self, state_service:BoardStateService) -> BoardStateService:
        
        rank = {player_color: idx for idx, player_color in enumerate(state_service.get_turn_order())}
        state_service.set_turn_order(sorted(state_service.get_players(), key=lambda k: (state_service.get_players()[k].money_spent, rank.get(k))))
        state_service.reset_turn_index()

        if self.era_change_on == state_service.round_count:
            state_service = self._prepare_next_era(state_service)
        elif self.end_game_on == state_service.round_count:
            state_service = self._conclude_game(state_service)
        
        first_round = state_service.get_current_round() == 1

        for player in state_service.get_players().values():
            player.bank += player.income
            
            if state_service.get_deck(): 
                card = state_service.get_deck().pop()
                player.hand[card.id] = card
                if not first_round:
                    card = state_service.get_deck().pop()
                    player.hand[card.id] = card
            
            player.money_spent = 0

        if any(player.bank < 0 for player in state_service.get_players().values()):
            state_service.set_action_context(ActionContext.SHORTFALL)

        state_service.advance_round_count()

        return state_service
    
    def _prepare_next_era(self, state_service:BoardStateService) -> BoardStateService:
        initializer = GameInitializer()
        state_service.get_board_state().deck = initializer._build_initial_deck(len(state_service.get_players()))
        del initializer
        random.shuffle(state_service.get_deck())

        for link in state_service.iter_links():
            if link.owner is not None:
                for city_name in link.cities:
                    state_service.get_player(link.owner).victory_points += state_service.get_city_link_vps(state_service.get_city(city_name))
                link.owner = None

        for building in state_service.iter_placed_buildings():
            if building.flipped:
                state_service.get_player(building.owner).victory_points += building.victory_points
            if building.level == 1:
                state_service.get_building_slot(building.slot_id).building_placed = None

        state_service.clear_discard()

        state_service.get_board_state().era = LinkType.RAIL

        for player in state_service.get_players().values():
            player.hand = {card.id: card for card in [state_service.get_deck().pop() for _ in range(6)]}

        return state_service

    def _conclude_game(self, state_service:BoardStateService) -> BoardStateService:
        self.concluded = True
        for link in state_service.iter_links():
            if link.owner is not None:
                for city_name in link.cities:
                    state_service.get_player(link.owner).victory_points += state_service.get_city_link_vps(state_service.get_city(city_name))

        for building in state_service.iter_placed_buildings():
            if building.flipped:
                state_service.get_player(building.owner).victory_points += building.victory_points
        
        return state_service 