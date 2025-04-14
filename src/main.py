from fastapi import FastAPI
from src.api.v1 import board, players, game

app = FastAPI()

app.include_router(game.router, prefix='/api/v1/game', tags=['game'])
