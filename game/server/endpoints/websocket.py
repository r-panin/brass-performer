from fastapi import APIRouter, WebSocket, Depends, WebSocketDisconnect
from ..dependancies import get_connection_manager, get_game_manager, get_action_parser
from ..managers import ConnectionManager, GameManager
from ...schema import PlayerColor
from pydantic import ValidationError

router = APIRouter()

@router.websocket("/ws/{game_id}/player/{player_token}")
async def websocket_endpoint(websocket: WebSocket, game_id: str, player_token: str, connection_manager:ConnectionManager=Depends(get_connection_manager), game_manager:GameManager=Depends(get_game_manager), parse_action:callable=Depends(get_action_parser)):
    if not game_manager.validate_token(game_id, player_token):
        await websocket.close(code=4001, reason="Game not started or invalid token")

    color = game_manager.get_player(player_token).color


    await connection_manager.connect(websocket, game_id, color)

    # Получаем игру
    game = game_manager.get_game(game_id)
    if not game:
        await websocket.send_json({"error": "Game not found"})
        connection_manager.disconnect()

    await websocket.send_json(game.get_player_state(color).model_dump()) # sending initial state
    
    message_generator = create_board_state_message(game)
    
    try:
        while True:
            try:
                # Получаем сообщение от клиента
                action_data = await websocket.receive_json()

                # Парсим-парсим-парсим и сводит музыка с ума
                action = parse_action(action_data)
                
                # Применяем действие к игровому состоянию
                # Здесь будет метод для применения действия
                action_result = game.process_action(action, color)
                await websocket.send_json(action_result.model_dump())
                
                # Отправляем обновленное состояние всем игрокам
                if action_result.end_of_turn:
                    await connection_manager.broadcast(game_id, message=message_generator)
            except ValueError as e:
                await websocket.send_json({
                    "error": str(e)
                })
                continue
            except ValidationError as e:
                await websocket.send_json({
                    "error": "Validation error",
                    "details": e.errors()
                })
                continue
                
    except WebSocketDisconnect:
        connection_manager.disconnect(websocket, game_id)

def create_board_state_message(game):
    def board_state_generator(websocket:WebSocket, player_color:PlayerColor):
        return game.get_player_state(player_color).model_dump()
    return board_state_generator