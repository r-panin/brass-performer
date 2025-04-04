import json
from random import shuffle
from pathlib import Path

class Board():
    CARD_LIST = Path(__file__).parent.with_name('card_list.json')
    CITIES_LIST = Path(__file__).parent.with_name('cities_list.json')

    def __init__(self, n_players=4):
        self.n_players = n_players
        self.build_deck()
        self.build_jokers()
        self.place_merchants()
        self.era = 'canal'

    def __repr__(self):
        return f'''Board with {self.n_players} players\n
Total cards: {len(self.deck)}\n
Jokers: {self.joker_deck}\n
Merchants: {self.merchants}\n
Current era: {self.era}'''

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
        self.joker_deck = [{"city": "any"} for _ in range(4)] + [{"industry": "any"} for _ in range(4)]

    def build_map(self):
        pass


if __name__ == '__main__':
    b = Board()
    print(b)