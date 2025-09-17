from ...schema import BoardState, LinkType
import random

class TurnManager:
    def __init__(self):
        self.concluded = False

    def prepare_next_turn(self, state:BoardState) -> BoardState:
        state.turn_order.pop()
        state.actions_left = 2
        if not state.turn_order:
            state = self._prepare_next_round(state)
        return state

    def _prepare_next_round(self, state:BoardState) -> BoardState:
        state.turn_order = sorted(state.players, key=lambda k: state.players[k].money_spent)

        if all(len(p.hand) == 0 for p in state.players.values()) and len(state.deck) == 0:
            if state.era == LinkType.CANAL:
                state = self._prepare_next_era(state)
            elif state.era == LinkType.RAIL:
                state = self._conclude_game(state)

        for player in state.players.values():
            player.bank += player.income
            
        
        if any(player.bank < 0 for player in self.state.players.values()):
            self.state_manager.enter_shortfall()

            if state.deck:
                while len(player.hand) < 8:
                    card = state.deck.pop()
                    player.hand[card.id] = card

        return state
    
    def _prepare_next_era(self, state:BoardState) -> BoardState:
        self.state.deck = self._build_initial_deck(len(self.state.players))
        random.shuffle(self.state.deck)

        for link in self.state.links.values():
            if link.owner is not None:
                for city_name in link.cities:
                    self.state.players[link.owner].victory_points += self.state.cities[city_name].get_link_vps()
                link.owner = None

        for building in self.state.iter_placed_buildings():
            if building.flipped:
                self.state.players[building.owner].victory_points += building.victory_points
            if building.level == 1:
                self.state.get_building_slot(building.slot_id).building_placed = None

        state.era = LinkType.RAIL

        return state

    def _conclude_game(self, state:BoardState) -> BoardState:
        self.concluded = True
        for link in state.links.values():
            if link.owner is not None:
                for city_name in link.cities:
                    state.players[link.owner].victory_points += state.cities[city_name].get_link_vps()

        for building in state.iter_placed_buildings():
            if building.flipped:
                state.players[building.owner].victory_points += building.victory_points
        
        return state 