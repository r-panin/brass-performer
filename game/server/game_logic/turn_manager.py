from ...schema import BoardState, LinkType, ActionContext
import random
from copy import deepcopy
from deepdiff import DeepDiff
from .services.event_bus import EventBus, InterturnEvent
import logging
from .game_initializer import GameInitializer

class TurnManager:
    def __init__(self, starting_state:BoardState, event_bus:EventBus):
        self.concluded = False
        self.event_bus = event_bus
        self.first_round = True
        self.round_count = 1
        self.previous_turn_order = starting_state.turn_order 

    def prepare_next_turn(self, state:BoardState) -> BoardState:
        if self.event_bus:
            initial_state = deepcopy(state)
        state.turn_order.pop(0)
        if not state.turn_order:
            state = self._prepare_next_round(state)
        if not self.first_round:
            state.actions_left = 2
        else:
            state.actions_left = 1
        if self.event_bus:
            diff = DeepDiff(initial_state.model_dump(), state.model_dump())
            self.event_bus.publish(InterturnEvent(
                diff=diff
            ))
        state.subaction_count = 0
        logging.debug(f"Remaining card count: {[len(player.hand) for player in state.players.values()]}")
        logging.debug(f"Current action count = {state.actions_left}")
        return state

    def _prepare_next_round(self, state:BoardState) -> BoardState:
        rank = {color: idx for color, idx in enumerate(self.previous_turn_order)}
        state.turn_order = sorted(state.players, key=lambda k: (state.players[k].money_spent, rank.get(k)))
        self.previous_turn_order = state.turn_order

        if all(len(p.hand) == 0 for p in state.players.values()) and len(state.deck) == 0:
            if state.era == LinkType.CANAL:
                state = self._prepare_next_era(state)
            elif state.era == LinkType.RAIL:
                state = self._conclude_game(state)

        for player in state.players.values():
            player.bank += player.income
            
            if state.deck:
                while len(player.hand) < 8 and len(state.deck) > 0:
                    card = state.deck.pop()
                    player.hand[card.id] = card

        if any(player.bank < 0 for player in state.players.values()):
            logging.info("Entering shortfall")
            state.action_context = ActionContext.SHORTFALL

        self.first_round = False
        self.round_count += 1
        logging.info(f"Round {self.round_count}, deck size: {len(state.deck)}")
        return state
    
    def _prepare_next_era(self, state:BoardState) -> BoardState:
        initializer = GameInitializer()
        state.deck = initializer._build_initial_deck(len(state.players))
        del initializer
        random.shuffle(state.deck)

        for link in state.links.values():
            if link.owner is not None:
                for city_name in link.cities:
                    state.players[link.owner].victory_points += state.cities[city_name].get_link_vps()
                link.owner = None

        for building in state.iter_placed_buildings():
            if building.flipped:
                state.players[building.owner].victory_points += building.victory_points
            if building.level == 1:
                state.get_building_slot(building.slot_id).building_placed = None

        state.era = LinkType.RAIL

        return state

    def _conclude_game(self, state:BoardState) -> BoardState:
        logging.critical("ATTEMPTING TO CONCLUDE GAME")
        self.concluded = True
        for link in state.links.values():
            if link.owner is not None:
                for city_name in link.cities:
                    state.players[link.owner].victory_points += state.cities[city_name].get_link_vps()

        for building in state.iter_placed_buildings():
            if building.flipped:
                state.players[building.owner].victory_points += building.victory_points
        
        return state 