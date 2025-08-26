from fastapi import HTTPException, status, APIRouter, Depends
from ..dependancies import get_game_manager
from ...schema import GameResponse, GameResponseDetail, PlayerInfo, GameStatus, BoardStateExposed
from ..managers import GameManager
from typing import List
import logging

router = APIRouter()

# Инициализация менеджера игр

# HTTP endpoints
@router.post("/games", response_model=GameResponse, status_code=status.HTTP_201_CREATED)
async def create_game(game_manager:GameManager=Depends(get_game_manager)):
    """Создание новой игры"""
    try:
        game_id = game_manager.create_game()
        game = game_manager.get_game(game_id)
        
        return GameResponse(
            id=game_id,
            status=game.status,
            players=game_manager.list_game_player_colors(game_id)
        )
    except Exception as e:
        logging.error(f"Error creating game: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to create game"
        )

@router.get("/games", response_model=List[GameResponse])
async def list_games(game_manager=Depends(get_game_manager)):
    """Получение списка всех игр"""
    games = []
    for game in game_manager.list_games():
        games.append(GameResponse(
            id=game.id,
            status=game_manager.get_game_status(game.id),
            players=game_manager.list_game_player_colors(game.id)
        ))
    
    return games

@router.get("/games/{game_id}", response_model=GameResponseDetail)
async def get_game(game_id: str, game_manager:GameManager=Depends(get_game_manager)):
    """Получение информации о конкретной игре"""
    game = game_manager.get_game(game_id)
    if not game:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Game not found"
        )
    
    state = None if game.status == GameStatus.CREATED else game.state
    
    return GameResponseDetail(
        id=game.id,
        state=state,
        status=game.status,
        players=game_manager.list_game_player_colors(game.id)
    )

@router.delete("/games/{game_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_game(game_id: str, game_manager:GameManager=Depends(get_game_manager)):
    """Удаление игры"""
    game = game_manager.get_game(game_id)
    if not game:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Game not found"
        )
    game_manager.remove_game(game_id)
    return None

@router.post("/games/{game_id}/join", response_model=PlayerInfo, status_code=status.HTTP_200_OK)
async def join_game(game_id: str, game_manager:GameManager=Depends(get_game_manager)):
    player = game_manager.add_player(game_id)
    if not player:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Cannot join game"
        )
    return player
    

@router.post("/games/{game_id}/start", response_model=GameResponseDetail, status_code=status.HTTP_200_OK)
async def start_game(game_id:str, game_manager:GameManager=Depends(get_game_manager)):
    game = game_manager.start_game(game_id)
    if not game:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Unable to start game"
        )
    colors = [player.color for player in game.state.players]
    return GameResponseDetail(
        id=game_id,
        status=game.status,
        players=colors,
        state=game.state.hide_state()
    )
   