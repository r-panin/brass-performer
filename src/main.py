from models.board import Board
from models.player import Player
from random import randint, choice

PLAYER_COLORS = ['purple', 'yellow', 'red', 'white']

n_players = 4

board = Board(n_players)
players = [Player(PLAYER_COLORS.pop(randint(0,len(PLAYER_COLORS)-1)), board) for _ in range(n_players)]

print(board)
print(players)

#print(board.get_coal_sources(choice(board.cities)))

