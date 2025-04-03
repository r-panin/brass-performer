import json
from pathlib import Path
from building import Building


class Player():
    deck = list()

    def __init__(self, color, start_position):
        self.color = color
        self.move_order = start_position
        self.income = 0
        self.vp = 0

        self.hand = list()
        self.build_first_hand()

        self.building_roster = list()
        self.build_roster()

    def build_first_hand(self):
        for _ in range(8):
            self.draw()

    def draw(self):
        pass
        # self.hand.append(card)

    def build_roster(self):
        file = Path(__file__).parent.with_name('building_table.json')
        with file.open() as text:
            table = json.loads(text.read())
            for building in table:
                for _ in range(building['count']):
                    self.building_roster.append(Building.from_json(building))

if __name__ == '__main__':
    p = Player('purple', 1)
    print(p.building_roster)
    print(len(p.building_roster))