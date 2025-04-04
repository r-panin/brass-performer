import json
from pathlib import Path
from models.building import Building
from models.board import Board


class Player():
    BUILDING_TABLE = Path(__file__).parent.with_name('building_table.json')
    def __init__(self, color, start_position, board:Board):
        self.color = color
        self.move_order = start_position
        self.income = 0
        self.vp = 0
        self.bank = 17

        self.board = board

        self.hand = list()
        self.build_first_hand()

        self.building_roster = list()
        self.build_roster()

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

if __name__ == '__main__':
    p = Player('purple', 1)
    print(p.building_roster)
    print(len(p.building_roster))