import json
from pathlib import Path
from models.building import Building
from models.board import Board
from models.city import City
from models.link import Link
from random import choice


class Player():
    BUILDING_TABLE = Path(__file__).parent.with_name('building_table.json')
    def __init__(self, color:str, board:Board, control_type='random'):
        self.color = color
        self.income = 0
        self.income_points = 0
        self.vp = 0
        self.bank = 17
        
        self.control_type = control_type

        self.board = board

        self.hand = list()
        self.build_first_hand()

        self.building_roster = list()
        self.build_roster()

        self.network = set()
        self.money_spent = 0

    def __repr__(self):
        return f'Player color: {self.color}, hand: {self.hand}, bank: {self.bank}, income: {self.income}, vps: {self.vp}'

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
        for buidling in self.building_roster:
            buidling.owner = self

    def determine_possible_actions(self):
        possible_actions = []
        possible_actions.append(self.pass_action) # always true
        if len(self.hand) == 0:
            return possible_actions

        if len(self.hand) >= 3 and not self.is_joker_in_hand():
            possible_actions.append(self.scout_action)

        if self.income_points >= 3:
            possible_actions.append(self.loan_action)

        return possible_actions
    
    def is_joker_in_hand(self):
        for card in self.hand:
            if 'any' in card.values():
                return True

    def build_action(self, building:Building, city:City):
        cost = self.calculate_building_cost(building, city)
        self.select_iron(building.cost['iron'])
        #self.select_coal(building.cost['coal'])
        slot = self.select_building_slot(building.industry, city)
        self.pay_cost(cost)
        building.location = city
        slot.build(building, self)
        self.building_roster.remove(building)
        return cost
    
    def select_building_slot(self, industry:str, city:City, method='random'):
        permitted_slots = [slot for slot in city.slots if industry in slot.industries]
        for slot in permitted_slots:
            if len(slot.industries) == 1:
                return slot
        if method == 'random':
            return choice(permitted_slots)
    
    def select_iron(self, amount, method='random'):
        iron_sources = self.find_player_iron()
        if method == 'random':
            for _ in range(amount):
                choice(iron_sources).use_resource()
    
    def calculate_building_cost(self, building:Building, city:City):
        cost = building.cost['money']
        if building.cost['coal'] > 0:
            cost += self.get_coal_cost(building.cost['coal'], city)
        if building.cost['iron'] > 0:
            cost += self.get_iron_cost(building.cost['iron'])
        return cost
    
    def get_iron_cost(self, amount):
        player_iron = self.find_player_iron()
        total_iron = 0
        for source in player_iron:
            total_iron += source.resource_count
        if amount < total_iron:
            cost = 0
        else:
            market_iron = amount - total_iron
            cost = self.board.market.buy_iron(market_iron)
        return cost
    
    def find_player_iron(self):
        player_sources = self.board.get_iron_sources()
        player_iron = 0
        for source in player_sources:
            player_iron += source.resource_count
        return player_iron
    
    def find_building_slots(self, industry:str, city:City):
        possible_slots = []
        for slot in city.slots:
            print(slot)
            if industry in slot.industries and len(slot.industries) == 1:
                possible_slots = list()
                possible_slots.append(slot)
                break
            elif industry in slot.industries:
                possible_slots.append(slot)
        return possible_slots

    def sell_action(self, buildings:list):
        for building in buildings:
            if self.board.merchant_available(building):
                self.fetch_beer(building)
                building.flipped = True
                self.income_points += building.income
        return 0

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
        return 0

    def develop_action(self, building:Building, building2:Building=None):
        for building in building,building2:
            player_iron = self.find_player_iron()
            if not player_iron:
                cost = self.get_iron_cost(1)
                self.pay_cost(cost)
            else:
                self.select_iron(player_iron, 1)
            self.building_roster.remove(building)
        return

    def scout_action(self):
        self.hand.append(self.board.city_jokers.pop(), self.board.industry_jokers.pop())
        return 0

    def network_action(self, link:Link):
        if self.board.era == 'canal':
            self.pay_cost(3)
            link.claim(self.color)
        elif self.board.era == 'rail':
            #fuck this
            pass

    def pass_action(self):
        return 

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

    def gain_income(self):
        self.calculate_income()
        self.bank += self.income

    def pay_cost(self, cost):
        self.bank -= cost

    def select_building(self, industry):
        out = None
        for building in self.building_roster:
            if (building.industry == industry) and (not out or building.level < out.level):
                out = building
        return out

if __name__ == '__main__':
    p = Player('purple', 1)
    print(p.building_roster)
    print(len(p.building_roster))