from typing import Any, Dict
from fastapi import APIRouter, WebSocket, Depends, WebSocketDisconnect

from ..dependancies import get_connection_manager, get_game_manager
from ..managers import ConnectionManager, GameManager
from ...schema import PlayerColor, ActionType, Action, Request, GameStatus, ShortfallAction, BuildAction, CommitAction, DevelopAction, LoanAction, NetworkAction, PassAction, ScoutAction, SellAction, ActionProcessResult
from pydantic import ValidationError

router = APIRouter()

@router.websocket("/ws/{game_id}/player/{player_token}")
async def websocket_endpoint(websocket: WebSocket, game_id: str, player_token: str, connection_manager:ConnectionManager=Depends(get_connection_manager), game_manager:GameManager=Depends(get_game_manager)):
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
        while game.status == GameStatus.ONGOING:
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
                if isinstance(action_result, ActionProcessResult):
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

def get_end_game_message(game) -> Dict:
    return {"final scores": {player.color: player.victory_points for player in game.state_service.get_players().values()}}

def parse_action(data: Dict[str, Any]) -> Action:
    # Затем проверяем действия Action
    action_type = data.get("action")
    if action_type == ActionType.LOAN:
        return LoanAction(**data)
    elif action_type == ActionType.PASS:
        return PassAction(**data)
    elif action_type == ActionType.SELL:
        return SellAction(**data)
    elif action_type == ActionType.BUILD:
        return BuildAction(**data)
    elif action_type == ActionType.SCOUT:
        return ScoutAction(**data)
    elif action_type == ActionType.DEVELOP:
        return DevelopAction(**data)
    elif action_type == ActionType.NETWORK:
        return NetworkAction(**data)
    elif action_type == ActionType.SHORTFALL:
        return ShortfallAction(**data)
    elif action_type == ActionType.COMMIT:
        return CommitAction(**data)
    
    elif 'request' in data:
        return Request(**data)
    
    # Если ни один тип не подошел
    raise ValueError(f"Неизвестный тип действия: {data}")