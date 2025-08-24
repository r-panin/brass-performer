from .managers import ConnectionManager, GameManager

# Создаем экземпляры менеджеров
connection_manager = ConnectionManager()
game_manager = GameManager()

def get_connection_manager():
    return connection_manager

def get_game_manager():
    return game_manager