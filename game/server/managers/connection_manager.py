from typing import Dict, List, Union, Callable, Awaitable, Tuple
from fastapi import WebSocket
from ...schema import PlayerColor

class ConnectionManager:
    def __init__(self):
        self.active_connections: Dict[str, List[Tuple[WebSocket, PlayerColor]]] = {}
    
    async def connect(self, websocket: WebSocket, game_id: str, color: PlayerColor):
        await websocket.accept()
        if game_id not in self.active_connections:
            self.active_connections[game_id] = []
        self.active_connections[game_id].append((websocket, color))  
    
    def disconnect(self, connection: WebSocket, game_id: str):
        if game_id in self.active_connections:
            self.active_connections[game_id] = [(ws, color) for (ws, color) in self.active_connections if ws != connection]
            if not self.active_connections[game_id]:
                del self.active_connections[game_id]

    async def broadcast(
        self,
        game_id: str,
        message: Union[dict, Callable[[WebSocket, str], dict]]
    ):
        if game_id not in self.active_connections:
            return

        for connection, color in self.active_connections[game_id]:
            if isinstance(message, dict):
                await connection.send_json(message)
            else:
                # Передаем и соединение, и цвет в функцию-генератор
                custom_message = message(connection, color)
                if hasattr(custom_message, '__await__'):
                    custom_message = await custom_message
                await connection.send_json(custom_message)