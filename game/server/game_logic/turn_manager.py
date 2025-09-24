from ...schema import BoardState, LinkType, ActionContext
import random
from copy import deepcopy
from deepdiff import DeepDiff
from .services.event_bus import EventBus, InterturnEvent
from .game_initializer import GameInitializer
from ...server.game_logic.services.board_state_service import BoardStateService


class TurnManager:
    def __init__(self, starting_state:BoardState, event_bus:EventBus):
        self.concluded = False
        self.event_bus = event_bus
        self.first_round = True
        self.round_count = 1
        self.previous_turn_order = starting_state.turn_order 

    def prepare_next_turn(self, state_service:BoardStateService) -> BoardStateService:
        state_service.state.turn_order.pop(0)
        if not state_service.state.turn_order:
            state_service = self._prepare_next_round(state_service)
        if not self.first_round:
            state_service.state.actions_left = 2
        else:
            state_service.state.actions_left = 1
        state_service.subaction_count = 0
        return state_service

    def _prepare_next_round(self, state_service:BoardStateService) -> BoardStateService:
        rank = {color: idx for color, idx in enumerate(self.previous_turn_order)}
        state_service.state.turn_order = sorted(state_service.state.players, key=lambda k: (state_service.state.players[k].money_spent, rank.get(k)))
        self.previous_turn_order = state_service.state.turn_order

        if all(len(p.hand) == 0 for p in state_service.state.players.values()) and len(state_service.state.deck) == 0:
            if state_service.state.era == LinkType.CANAL:
                state_service = self._prepare_next_era(state_service)
            elif state_service.state.era == LinkType.RAIL:
                state_service = self._conclude_game(state_service)

        for player in state_service.state.players.values():
            player.bank += player.income
            
            if state_service.state.deck:
                while len(player.hand) < 8 and len(state_service.state.deck) > 0:
                    card = state_service.state.deck.pop()
                    player.hand[card.id] = card

        if any(player.bank < 0 for player in state_service.state.players.values()):
            state_service.state.action_context = ActionContext.SHORTFALL

        self.first_round = False
        self.round_count += 1
        return state_service
    
    def _prepare_next_era(self, state_service:BoardStateService) -> BoardStateService:
        initializer = GameInitializer()
        state_service.state.deck = initializer._build_initial_deck(len(state_service.state.players))
        del initializer
        random.shuffle(state_service.state.deck)

        for link in state_service.state.links.values():
            if link.owner is not None:
                for city_name in link.cities:
                    state_service.state.players[link.owner].victory_points += state_service.get_city_link_vps(state_service.state.cities[city_name])
                link.owner = None

        for building in state_service.iter_placed_buildings():
            if building.flipped:
                state_service.state.players[building.owner].victory_points += building.victory_points
            if building.level == 1:
                state_service.get_building_slot(building.slot_id).building_placed = None

        state_service.state.era = LinkType.RAIL

        return state_service

    def _conclude_game(self, state_service:BoardStateService) -> BoardStateService:
        self.concluded = True
        for link in state_service.state.links.values():
            if link.owner is not None:
                for city_name in link.cities:
                    state_service.state.players[link.owner].victory_points += state_service.get_city_link_vps(state_service.state.cities[city_name])

        for building in state_service.iter_placed_buildings():
            if building.flipped:
                state_service.state.players[building.owner].victory_points += building.victory_points
        
        return state_service 