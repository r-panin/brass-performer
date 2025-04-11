import json
from random import shuffle, choice
from pathlib import Path
from models.city import City
from models.link import Link
from models.market import Market
from models.building_slot import BuildingSlot
from models.building import Building
from collections import deque, defaultdict

class Board():
    CARD_LIST = Path(__file__).parent.with_name('card_list.json')
    CITIES_LIST = Path(__file__).parent.with_name('cities_list.json')

    def __init__(self, n_players=4):
        self.n_players = n_players
        self.era = 'canal'
        self.market = Market()
        self.cities = list()
        self.links = list()
        self.build_deck()
        self.build_jokers()
        self.place_merchants()
        self.build_map()

    def __repr__(self):
        return f'''Board with {self.n_players} players\n
Total cards: {len(self.deck)}\n
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
        merchants = {merchant: [goods_list.pop(), goods_list.pop()] for merchant in merchant_list if merchant != 'Shrewsbury'}
        merchants['Shrewsbury'] = [goods_list.pop()]
        return merchants

    def build_jokers(self):
        self.city_jokers = [{"city": "any"} for _ in range(4)]
        self.industry_jokers = [{"industry": "any"} for _ in range(4)]

    def build_map(self):
        self.add_tri_link()
        merchants = self.place_merchants()
        with self.CITIES_LIST.open() as text:
            cities = json.loads(text.read())
            for city in cities:
                name = city['name']
                links = [Link(city['name'], other_city['name']) for other_city in city['links'] if self.era in other_city['transport']
                         and not self.has_link(city['name'], other_city['name'])]
                self.links += links
                
                if name in merchants.keys():
                    merchant = True
                    slots = []
                    self.cities.append(City(name, slots, merchant, merchants[name]))
                else:
                    merchant = False
                    slots = [BuildingSlot(slot) for slot in city['slots']]
                    self.cities.append(City(name, slots, merchant))
    
    def has_link(self, city1, city2):
        """Проверяет, есть ли связь между city1 и city2 (включая тройные связи)."""
        for link in self.links:
            if (link.city_a == city1 and link.city_b == city2) or \
            (link.city_a == city2 and link.city_b == city1):
                return True
            
            if hasattr(link, 'city_c'):
                if link.city_c in (city1, city2) and \
                (link.city_a == city1 or link.city_b == city1 or 
                    link.city_a == city2 or link.city_b == city2):
                    return True
        return False

    def add_tri_link(self):
        self.links.append(Link('Kidderminster', 'Worcester', 'farm_brewery_south'))

    def get_connected_cities(self, city:City):
        connected = []
        for link in self.links:
            if link.claimed_by:
                if link.city_a == city.name:
                    connected.append(link.city_b)
                elif link.city_b == city.name:
                    connected.append(link.city_a)
        return connected
            
    def determine_player_network(self, player_color:str):
        network = [self.lookup_city(city) for link in self.links if link.claimed_by == player_color for city in (link.city_a, link.city_b)]
        for city in self.cities:
            if city not in network:
                claims = [slot.claimed_by for slot in city.slots]
                if player_color in claims:
                    network.append(city)
        return network
    
    def get_iron_sources(self):
        iron_buildings = list()
        for city in self.cities:
            iron_buildings += self.check_city_for_resource(city, 'iron')
        return iron_buildings
    
    def check_city_for_resource(self, city:City, resource_type):
        resource_buildings = list()
        for slot in city.slots:
            if hasattr(slot, 'building'):
                if slot.building.industry == resource_type and slot.building.resource_count > 0:
                    resource_buildings.append(slot.building)
        return resource_buildings

    def get_coal_sources(self, city:City):
        visited = dict()
        result = list()
        queue = deque()

        queue.append((city, 0))
        visited[id(city)] = True

        while queue:
            current_city, distance = queue.popleft()
            current_coal_buidlings = self.check_city_for_resource(current_city, 'coal')
            if current_coal_buidlings:
                result.append((current_city, distance))

            for conn_name in self.get_connected_cities(current_city):
                neighbor = self.lookup_city(conn_name)
                if id(neighbor) not in visited:
                    visited[id(neighbor)] = True
                    queue.append((neighbor, distance + 1))
        grouped = defaultdict(list)
        for source, distance in result:
            grouped[distance].append(source)
        output = [grouped[distance] for distance in sorted(grouped)]
        return output
    
    def get_beer_sources(self, player, city:City, merchant:City, industry:str):
        own_sources = list()
        foreign_sources = [merchant for merchant in self.merchants if industry in merchant.merchant_goods]
        for city in self.cities:
            local_sources = self.check_city_for_resource(city, 'beer')
            for source in local_sources:
                if source.owner == player:
                    own_sources.append(source)
                else:
                    foreign_sources.append(source)
        valid_foreign_sources = [source for source in foreign_sources if self.are_cities_connected(city, source)]
        sources = own_sources + valid_foreign_sources 
        return sources

    def lookup_city(self, name):
        for city in self.cities:
            if city.name == name:
                return city
        return None
    
    def are_cities_connected(self, start_city:City, target_city:City):
        visited = dict()
        queue = deque([start_city])
        visited[id(start_city)] = True

        while queue:
            current_city = queue.popleft()
            neighbors = self.get_connected_cities(current_city)
            for neighbor in neighbors:
                if neighbor == target_city:
                    return True
                if neighbor not in visited:
                    visited[id(neighbor)] = True
                    queue.append(neighbor)
        return False
            

if __name__ == '__main__':
    b = Board()
    print(b)