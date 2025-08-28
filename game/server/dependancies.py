from .managers import ConnectionManager, GameManager
from ..schema import Action
from pydantic import TypeAdapter

# Создаем экземпляры менеджеров
connection_manager = ConnectionManager()
game_manager = GameManager()
action_parser = TypeAdapter(Action)

def get_connection_manager():
    return connection_manager

def get_game_manager():
    return game_manager

def get_action_parser():
    return action_parser.validate_python