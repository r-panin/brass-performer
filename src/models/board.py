import json
from random import shuffle, choice
from pathlib import Path
from models.city import City
from models.link import Link
from models.market import Market

class Board():
    CARD_LIST = Path(__file__).parent.with_name('card_list.json')
    CITIES_LIST = Path(__file__).parent.with_name('cities_list.json')

    def __init__(self, n_players=4):
        self.n_players = n_players
        self.build_deck()
        self.build_jokers()
        self.place_merchants()
        self.era = 'canal'
        self.build_map()
        self.market = Market()

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
        self.cities = list()
        with self.CITIES_LIST.open() as text:
            cities = json.loads(text.read())
            for city in cities:
                name = city['name']
                print(type(name))
                links = [Link(name, other_city['name']) for other_city in city['links'] if self.era in other_city['transport']]
                if city['name'] in self.merchants.keys():
                    merchant = True
                    slots = []
                else:
                    merchant = False
                    slots = city['slots']
                self.cities.append(City(name, links, slots, merchant))


if __name__ == '__main__':
    b = Board()
    print(b)