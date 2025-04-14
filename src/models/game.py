from src.models.board import Board
from src.models.player import Player
from random import randint
from uuid import uuid4 as uuid

class GameState():
    ONGOING = 'ongoing'
    FINISHED = 'finished'

class Game():
    PLAYER_COLORS = ['purple', 'yellow', 'red', 'white']
    def __init__(self, n_players):
        self.uuid = uuid()
        self.turn = 1
        self.board = Board(n_players)
        self.players = [Player(self.PLAYER_COLORS.pop(randint(0,len(self.PLAYER_COLORS)-1)), self.board) for _ in range(n_players)]
        self.status = GameState.ONGOING
        #first move discard
        for player in self.players:
            player.discard()
            player.draw()
        self.to_move = self.players[0]
        self.moves_remaining = 1
