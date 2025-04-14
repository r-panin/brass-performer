from src.models.board import Board
from src.models.player import Player
from random import randint

class Game():
    PLAYER_COLORS = ['purple', 'yellow', 'red', 'white']
    def __init__(self, n_players):
        self.board = Board(n_players)
        self.players = [Player(self.PLAYER_COLORS.pop(randint(0,len(self.PLAYER_COLORS)-1)), self.board) for _ in range(n_players)]

    def turn(self):
        # play actions
        for player in self.players():
            actions = player.determine_possible_actions()
            for _ in range(2):
                '''
                play action
                '''
        # if deck hasn't been exhausted, draw until 8
        if len(self.board.deck) > 0:
            for player in self.players:
                while len(player.hand) < 8:
                    player.draw()
        
        # sort players by money spent
        self.players.sort(key=lambda x: x.money_spent)

        # get paid
        for player in self.players:
            player.gain_income()
        
