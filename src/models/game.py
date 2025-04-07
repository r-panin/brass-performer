from models.board import Board
from models.player import Player
from random import randint, choice

class Game():
    PLAYER_COLORS = ['purple', 'yellow', 'red', 'white']
    def __init__(self, n_players):
        self.board = Board(n_players)
        self.players = [Player(self.PLAYER_COLORS.pop(randint(0,len(self.PLAYER_COLORS)-1)), i, self.board) for i in range(n_players)]

    def turn(self):
        # if deck hasn't been exhausted, draw until 8
        if len(self.board.deck) > 0:
            for player in self.players:
                while len(player.hand) < 8:
                    player.draw()
        # play actions
        for player in self.players():
            actions = player.determine_possible_actions()
            for _ in range(2):
                action = choice(actions)
                if action.targetable:
                    target = player.determine_possible_targets(action)
                    player.play_action(target)
                else:
                    player.play_action()
