from typing import Dict, List
from ..game_logic.game import Game
from ...schema import PlayerInfo, GameStatus
from uuid import uuid4

class GameManager:
    MAX_PLAYERS = 4
    MIN_PLAYERS = 2
    def __init__(self):
        self.games: Dict[str, Game] = {}
        self.players: Dict[str, PlayerInfo] = {}
        self.game_players: Dict[str, List[str]] = {} # {game_id: [PlayerInfo1, PlayerInfo2]}
    
    def create_game(self) -> str:
        game = Game()
        self.games[game.id] = game
        self.game_players[game.id] = []
        return game.id
    
    def get_game(self, game_id: str) -> Game:
        return self.games.get(game_id)
    
    def list_games(self) -> List[Game]:
        return self.games.values()
    
    def remove_game(self, game_id: str):
        if game_id in self.games:
            del self.games[game_id]

    def get_game_status(self, game_id: str):
        return self.games.get(game_id).status

    def start_game(self, game_id: str):
        if len(self.game_players[game_id]) < self.MIN_PLAYERS:
            return None
        game = self.games.get(game_id)
        player_count = len(self.game_players[game_id])
        colors = self.list_game_player_colors(game_id)
        game.start(player_count, colors)
        return game
    
    def add_player(self, game_id:str):
        if game_id not in self.games:
            return None
        if len(self.game_players[game_id]) >= self.MAX_PLAYERS:
            return None
        game = self.games[game_id]
        token = str(uuid4())
        color = game.available_colors.pop()
        player = PlayerInfo(token=token, color=color)
        self.players[player.token] = player
        self.game_players[game_id].append(token)
        return player

    def get_available_colors(self, game_id:str):
        game = self.games.get(game_id)
        return game.available_colors
    
    def list_game_players(self, game_id: str):
        player_tokens = self.game_players.get(game_id)
        return [self.players[token] for token in player_tokens]
    
    def list_game_player_colors(self, game_id:str):
        players = self.list_game_players(game_id)
        return [player.color for player in players]

    def get_player(self, player_token):
        return self.players[player_token]
    
    def validate_token(self, game_id, player_token):
        game = self.get_game(game_id)
        if not game or game.status != GameStatus.ONGOING:
            return False
        if not player_token in self.game_players[game_id]:
            return False
        return True

if __name__ == '__main__':
    manager = GameManager()
    print(manager.get_game(manager.create_game(4)))