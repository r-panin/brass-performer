import json
from random import shuffle, choice
from pathlib import Path
from models.city import City
from models.link import Link
from models.market import Market
from models.building_slot import BuildingSlot

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
                links = [Link(city, other_city) for other_city in city['links'] if self.era in other_city['transport']]
                if city['name'] in self.merchants.keys():
                    merchant = True
                    slots = []
                else:
                    merchant = False
                    slots = [BuildingSlot(slot) for slot in city['slots']]
                self.cities.append(City(name, slots, links, merchant))
            
    def determine_player_network(self, player_color:str):
        network = set()
        for city in self.cities:
            claims = [link.claimed_by for link in city.links] + [slot.claimed_by for slot in city.slots]
            if player_color in claims:
                network.add(city)
        return network
    
    def get_iron_sources(self):
        iron_buildings = set()
        for city in self.cities:
            iron_buildings.union(self.check_city_for_iron(city))
        return iron_buildings
    
    def check_city_for_iron(self, city:City):
        iron_buildings = set()
        for slot in city.slots:
            if hasattr(slot, 'building'):
                if slot.building.industry == 'iron' and slot.building.resource_count > 0:
                    iron_buildings.add(slot.building)
        return iron_buildings


    def get_coal_sources(self, location:City, _checked_cities=set(), _coal_buildings = list()):
        if _checked_cities == self.cities:
            return _coal_buildings
        primary_source = self.check_city_for_coal(location)
        _checked_cities.add(location)
        if len(primary_source) > 0:
            _coal_buildings.append(primary_source)
        for link in location.links:
            next_city = link.city_b
            self.get_coal_sources(self, next_city, _checked_cities)
            
            
    def check_city_for_coal(self, city:City):
        coal_buildings = set()
        for slot in city.slots:
            if hasattr(slot, 'building'):
                if slot.building.industry == 'coal' and slot.building.resource_count > 0:
                    coal_buildings.add(slot.building)
        return coal_buildings
            

if __name__ == '__main__':
    b = Board()
    print(b)