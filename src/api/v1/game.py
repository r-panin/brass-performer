from fastapi import APIRouter, Request
from src.models.game import Game
from src.schemas.game import GameStart, GameGet

router = APIRouter()

@router.post('/start')
def start_game(request:GameStart):
    game = Game(request.players)
    return GameGet(game)

