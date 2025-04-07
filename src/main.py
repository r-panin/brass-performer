from models.board import Board
from models.player import Player
from random import randint

PLAYER_COLORS = ['purple', 'yellow', 'red', 'white']

n_players = 4

board = Board(n_players)
print(board)
players = [Player(PLAYER_COLORS.pop(randint(0,len(PLAYER_COLORS)-1)), i, board) for i in range(n_players)]

print(board)
print(players)

