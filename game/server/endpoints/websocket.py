from fastapi import APIRouter, WebSocket, Depends, WebSocketDisconnect
from ..dependancies import get_connection_manager, get_game_manager
from ...schema import Action

router = APIRouter()

@router.websocket("/ws/{game_id}")
async def websocket_endpoint(websocket: WebSocket, game_id: str, connection_manager=Depends(get_connection_manager), game_manager=Depends(get_game_manager)):
    # Подключаемся к игре
    await connection_manager.connect(websocket, game_id)
    
    try:
        while True:
            # Получаем сообщение от клиента
            data = await websocket.receive_json()
            
            # Парсим действие
            action = Action.parse_obj(data)
            
            # Получаем игру
            game = game_manager.get_game(game_id)
            if not game:
                await websocket.send_json({"error": "Game not found"})
                continue
            
            # Применяем действие к игровому состоянию
            try:
                # Здесь будет метод для применения действия
                game.apply_action(action)
                
                # Отправляем обновленное состояние всем игрокам
                await connection_manager.broadcast(
                    game_id, 
                    {"type": "game_update", "state": game.state.dict()}
                )
            except Exception as e:
                await websocket.send_json({"error": str(e)})
                
    except WebSocketDisconnect:
        connection_manager.disconnect(websocket, game_id)