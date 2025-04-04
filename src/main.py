from models.board import Board
from models.player import Player
from random import randint

n_players = 4
player_colors = ['purple', 'yellow', 'red', 'white']

board = Board(n_players)
players = [Player(player_colors.pop(randint(0,len(player_colors)-1)), i, board.deck) for i in range(n_players)]

print(board)
print(players)
