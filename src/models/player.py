import json
from pathlib import Path
from models.building import Building
from models.board import Board
from models.city import City


class Player():
    BUILDING_TABLE = Path(__file__).parent.with_name('building_table.json')
    def __init__(self, color:str, start_position:int, board:Board):
        self.color = color
        self.move_order = start_position
        self.income = 0
        self.income_points = 0
        self.vp = 0
        self.bank = 17

        self.board = board

        self.hand = list()
        self.build_first_hand()

        self.building_roster = list()
        self.build_roster()

        self.network = set()

    def __repr__(self):
        return f'Player color: {self.color}, current turn order: {self.move_order}, hand: {self.hand}'

    def build_first_hand(self):
        for _ in range(8):
            self.draw()

    def draw(self):
        self.hand.append(self.board.deck.pop())

    def build_roster(self):
        with self.BUILDING_TABLE.open() as text:
            table = json.loads(text.read())
            for building in table:
                for _ in range(building['count']):
                    self.building_roster.append(Building.from_json(building))

    def determine_possible_actions(self):
        possible_actions = []
        if len(self.hand) == 0:
            return possible_actions
        
        possible_actions.append(self.pass_action) # always true

        if len(self.hand) >= 3 and not self.is_joker_in_hand():
            possible_actions.append(self.scout_action)

        if self.income_points >= 3:
            possible_actions.append(self.loan_action)

        return possible_actions
    
    def determine_player_network(self):
        pass

    def is_joker_in_hand(self):
        for card in self.hand:
            if 'any' in card.values():
                return True

    def play_action(self, action, card:dict):
        action(card)

    def build_action(self, building:Building, city:City):
        possible_slots = []
        for slot in city.slots:
            if building.industry in slot.industires and len(slot) == 1:
                selected_slot = slot
                break
            elif building.industry in slot.industries:
                possible_slots.append(slot)
        if not selected_slot and len(possible_slots) > 0:
            selected_slot = self.select_building_slot
        selected_slot.claim(building, self.color)

    def sell_action(self, buildings:list):
        for building in buildings:
            if self.board.merchant_available(building):
                self.fetch_beer(building)
                building.flipped = True

    def loan_action(self):
        self.bank += 30

        self.income -= 3

        if self.income <= 0:
            self.income_points = self.income
        elif self.income <= 10:
            self.income_points = self.income * 2
        elif self.income <= 20:
            self.income_points = 20 + self.income * 3
        elif self.income <= 30:
            self.income_points = 50 + self.income * 4

    def develop_action(self, building:Building, building2:Building=None):
        self.fetch_iron()
        self.building_roster.remove(building)
        if building2:
            self.fetch_iron()
            self.building_roster.remove(building2)

    def scout_action(self):
        self.hand.append(self.board.city_jokers.pop(), self.board.industry_jokers.pop())

    def network_action(self, city_a:City, city_b:City):
        for link in city_a.links:
            if link.city_b == city_b.name:
                link.claimed_by = self.color
                break
        for link in city_b.links:
            if link.city_b == city_a.name:
                link.claimed_by = self.color

    def pass_action(self):
        pass

    def calculate_income(self):
        if self.income_points <= 0:
            self.income = self.income_points
        elif self.income_points <= 20:
            self.income = -(self.income_points // -2)
        elif self.income_points <= 50:
            self.income = 10 + -((self.income_points - 20) // -3)
        elif self.income_points <= 90:
            self.income = 20 + -((self.income_points - 50) // -4)
        else:
            self.income = 30

    def fetch_iron(self):
        pass

    def fetch_coal(self, location:str):
        pass

    def fetch_beer(self, location:str):
        pass

if __name__ == '__main__':
    p = Player('purple', 1)
    print(p.building_roster)
    print(len(p.building_roster))