from typing import Dict, List, Union, Callable, Awaitable
from fastapi import WebSocket

class ConnectionManager:
    def __init__(self):
        self.active_connections: Dict[str, List[WebSocket]] = {}
    
    async def connect(self, websocket: WebSocket, game_id: str):
        await websocket.accept()
        if game_id not in self.active_connections:
            self.active_connections[game_id] = []
        self.active_connections[game_id].append(websocket)  
    
    def disconnect(self, connection: WebSocket, game_id: str):
        if game_id in self.active_connections:
            self.active_connections[game_id].remove(connection)
            if not self.active_connections[game_id]:
                del self.active_connections[game_id]

    async def broadcast(
        self,
        game_id: str,
        message: Union[dict, Callable[[WebSocket], Union[dict, Awaitable[dict]]]]
    ):
        if game_id not in self.active_connections:
            return

        for connection in self.active_connections[game_id]:
            if isinstance(message, dict):
                await connection.send_json(message)
            else:
                custom_message = message(connection)
                if hasattr(custom_message, '__await__'):
                    custom_message = await custom_message
                await connection.send_json(custom_message)