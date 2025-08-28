from fastapi import APIRouter, WebSocket, Depends, WebSocketDisconnect
from ..dependancies import get_connection_manager, get_game_manager
from ..managers import ConnectionManager, GameManager
from ...schema import Action, PlayerColor
import json
from pydantic import ValidationError

router = APIRouter()

@router.websocket("/ws/{game_id}/player/{player_token}")
async def websocket_endpoint(websocket: WebSocket, game_id: str, player_token: str, connection_manager:ConnectionManager=Depends(get_connection_manager), game_manager:GameManager=Depends(get_game_manager)):
    if not game_manager.validate_token(game_id, player_token):
        await websocket.close(code=4001, reason="Game not started or invalid token")

    color = game_manager.get_player(player_token).color

    await connection_manager.connect(websocket, game_id)

    # Получаем игру
    game = game_manager.get_game(game_id)
    if not game:
        await websocket.send_json({"error": "Game not found"})
        connection_manager.disconnect()

    await websocket.send_json(game.get_player_state(color).model_dump()) # sending initial state
    
    try:
        while True:
            # Получаем сообщение от клиента
            data = await websocket.receive_json()
            
            # Парсим действие
            action_data = json.loads(data)
            
            # Применяем действие к игровому состоянию
            try:
                # Здесь будет метод для применения действия
                #game.apply_action(action)
                
                # Отправляем обновленное состояние всем игрокам
                await connection_manager.broadcast(game_id, message=create_board_state_message)
            except ValueError as e:
                await websocket.send_json({
                    "error": str(e)
                })
            except ValidationError as e:
                await websocket.send_json({
                    "error": "Validation error",
                    "details": e.errors()
                })
                
    except WebSocketDisconnect:
        connection_manager.disconnect(websocket, game_id)

def create_board_state_message(game, player_color:PlayerColor):
    def board_state_generator(websocket:WebSocket):
        return game.get_player_state(player_color)
    return board_state_generator