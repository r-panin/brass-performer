from fastapi import APIRouter, Request
from src.models.game import Game
from src.schemas.game import GameStart

router = APIRouter()

@router.post('/start')
def start_game(request:GameStart):
    return Game(request.players)

