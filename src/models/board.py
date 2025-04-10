import json
from random import shuffle, choice
from pathlib import Path
from models.city import City
from models.link import Link
from models.market import Market
from models.building_slot import BuildingSlot
from models.building import Building
from collections import deque

class Board():
    CARD_LIST = Path(__file__).parent.with_name('card_list.json')
    CITIES_LIST = Path(__file__).parent.with_name('cities_list.json')

    def __init__(self, n_players=4):
        self.n_players = n_players
        self.era = 'canal'
        self.market = Market()
        self.cities = list()
        self.build_deck()
        self.build_jokers()
        self.place_merchants()
        self.build_map()

    def __repr__(self):
        return f'''Board with {self.n_players} players\n
Total cards: {len(self.deck)}\n
Merchants: {self.merchants}\n
Current era: {self.era}\n
Random city: {choice(self.cities)}'''

    def build_deck(self):
        self.deck = list()
        with self.CARD_LIST.open() as text:
            cards = json.loads(text.read())
            np_filtered_cards = [card for card in cards if card["player_count"] <= self.n_players]
            for card in np_filtered_cards:
                if "city" in card.keys():
                    for _ in range(card['count']):
                        self.deck.append({"city": card['city']})
                elif "industry" in card.keys():
                    for _ in range(card['count']):
                        self.deck.append({'industry': card['industry']})
        shuffle(self.deck)

    def place_merchants(self):
        goods_list = ['any', 'cotton', 'box', 'blank', 'blank']
        merchant_list = ['Oxford', 'Gloucester', 'Shrewsbury']
        if self.n_players >= 3:
            goods_list.append('pottery')
            goods_list.append('blank')
            merchant_list.append('Warrington')
        if self.n_players == 4:
            goods_list.append('box')
            goods_list.append('cotton')
            merchant_list.append('Nottingham')
        shuffle(goods_list)
        shuffle(merchant_list)
        self.merchants = {merchant: [goods_list.pop(), goods_list.pop()] for merchant in merchant_list if merchant != 'Shrewsbury'}
        self.merchants['Shrewsbury'] = [goods_list.pop()]

    def build_jokers(self):
        self.city_jokers = [{"city": "any"} for _ in range(4)]
        self.industry_jokers = [{"industry": "any"} for _ in range(4)]

    def build_map(self):
        with self.CITIES_LIST.open() as text:
            cities = json.loads(text.read())
            for city in cities:
                name = city['name']
                links = [Link(city['name'], other_city['name']) for other_city in city['links'] if self.era in other_city['transport']]
                if city['name'] in self.merchants.keys():
                    merchant = True
                    slots = []
                else:
                    merchant = False
                    slots = [BuildingSlot(slot) for slot in city['slots']]
                self.cities.append(City(name, slots, links, merchant))
            
    def determine_player_network(self, player_color:str):
        network = list()
        for city in self.cities:
            if city not in network:
                claims = [link.claimed_by for link in city.links] + [slot.claimed_by for slot in city.slots]
                if player_color in claims:
                    network.append(city)
        return network
    
    def get_iron_sources(self):
        iron_buildings = list()
        for city in self.cities:
            iron_buildings += self.check_city_for_iron(city)
        return iron_buildings
    
    def check_city_for_iron(self, city:City):
        iron_buildings = list()
        for slot in city.slots:
            if hasattr(slot, 'building'):
                if slot.building.industry == 'iron' and slot.building.resource_count > 0:
                    iron_buildings.append(slot.building)
        return iron_buildings

    def check_city_for_coal(self, city:City):
        coal_buildings = set()
        for slot in city.slots:
            if hasattr(slot, 'building'):
                if slot.building.industry == 'coal' and slot.building.resource_count > 0:
                    coal_buildings.add(slot.building)
        return coal_buildings
    
    def get_coal_sources(self, city:City):
        visited = dict()
        result = list()
        queue = deque()

        queue.append((city, 0))
        visited[id(city)] = True

        while queue:
            current_city, distance = queue.popleft()
            current_coal_buidlings = self.check_city_for_coal(current_city)
            if current_coal_buidlings:
                result.append((current_city, distance))

            for link in current_city.links:
                neighbor = self.lookup_city(link.dest)
                if id(neighbor) not in visited:
                    visited[id(neighbor)] = True
                    queue.append((neighbor, distance + 1))
        
        return result

    def lookup_city(self, name):
        for city in self.cities:
            if city.name == name:
                return city
        return None
            

if __name__ == '__main__':
    b = Board()
    print(b)