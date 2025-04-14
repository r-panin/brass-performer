import json
from pathlib import Path
from src.models.building import Building
from src.models.board import Board
from src.models.city import City
from src.models.link import Link
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

    def discard(self):
        self.hand.pop()

    def build_roster(self):
        with self.BUILDING_TABLE.open() as text:
            table = json.loads(text.read())
            for building in table:
                for _ in range(building['count']):
                    self.building_roster.append(Building.from_json(building))
        for buidling in self.building_roster:
            buidling.owner = self

    def is_joker_in_hand(self):
        for card in self.hand:
            if 'any' in card.values():
                return True

    def build_action(self, building:Building, city:City):
        cost = building.cost['money']
        cost += self.acquire_iron(building.cost['iron'])
        cost += self.acquire_coal(building.cost['coal'], city)
        slot = self.select_building_slot(building.industry, city)
        self.pay_cost(cost)
        building.location = city
        slot.build(building, self)
        self.building_roster.remove(building)
        return cost
    
    def acquire_iron(self, amount):
        player_sources = self.board.get_iron_sources()
        player_iron_count = 0
        for source in player_sources:
            player_iron_count += source.resource_count
        if player_sources:
            self.select_source(player_sources, player_iron_count)
        if player_iron_count >= amount:
            return 0
        else:
           market_iron = amount - player_iron_count
           cost = self.board.market.execute_trade(market_iron, 'iron', True)
           return cost

    def acquire_coal(self, amount, city):
        source_groups = self.board.get_coal_sources(city)
        player_coal_count = 0
        if source_groups:
            for group in source_groups:
                player_sources = list()
                for source in group:
                    player_coal_count += source.resource_count
                    if source:
                        player_sources.append(source)
                self.select_source(player_sources, player_coal_count)
            if player_coal_count >= amount:
                return 0
        elif self.board.market_available(city):
           market_coal = amount - player_coal_count
           cost = self.board.market.execute_trade(market_coal, 'coal', True)
           return cost
        else:
            return None
        
    def acquire_beer(self, amount, city):
        sources = self.board.get_beer_sources(city)
        beer_count = 0
        for source in sources:
            beer_count += source.resource_count
        if beer_count < amount:
            return None
        self.select_source(sources, amount)
        return 0
        
    def select_source(self, sources:list, amount, method='own-first'):
        if method == 'own-first':
            own_sources = [source for source in sources if source.owner == self].sort(key=lambda a: a.resource_count)
            foreign_sources = [source for source in sources if source not in own_sources].sort(key=lambda a: a.resource_count)
            while amount:
                if not own_sources or foreign_sources:
                    return None
                if own_sources:
                    best_source = own_sources[0]
                elif foreign_sources:
                    best_source = foreign_sources[-1]
                best_source.use_resource()
                if best_source.resource_count < 1:
                    if best_source.owner == self:
                        own_sources.remove(best_source)
                    else:
                        foreign_sources.remove(best_source)
                amount -= 1
            return 0
                 

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
    
    def select_building_slot(self, industry:str, city:City, method='random'):
        permitted_slots = [slot for slot in city.slots if industry in slot.industries]
        for slot in permitted_slots:
            if len(slot.industries) == 1:
                return slot
        if method == 'random':
            return choice(permitted_slots)
    
    def sell_action(self, buildings:list):
        for building in buildings:
            if self.board.merchant_available(building):
                self.select_beer(building)
                building.flipped = True
                self.income_points += building.income
        return

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
        return

    def develop_action(self, building:Building, building2:Building=None):
        for building in building,building2:
            # get iron
            continue
        return

    def scout_action(self):
        self.hand.append(self.board.city_jokers.pop(), self.board.industry_jokers.pop())
        return

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

    def get_buildable_building(self, industry):
        out = None
        for building in self.building_roster:
            if (building.industry == industry) and (not out or building.level < out.level):
                out = building
        return out

if __name__ == '__main__':
    p = Player('purple', 1)
    print(p.building_roster)
    print(len(p.building_roster))