from models.board import Board
from models.player import Player
from random import randint, choice

PLAYER_COLORS = ['purple', 'yellow', 'red', 'white']

n_players = 4

board = Board(n_players)
players = [Player(PLAYER_COLORS.pop(randint(0,len(PLAYER_COLORS)-1)), board) for _ in range(n_players)]

print(board)

builder = choice(players)
building = builder.select_building('coal')
city = board.lookup_city('Dudley')
builder.build_action(building, city)
#builder.build_action(builder.select_building('iron'), board.lookup_city('Dudley'))

print(board.get_coal_sources(board.lookup_city('Belper')))

