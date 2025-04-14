from pydantic import BaseModel
from uuid import uuid4 as uuid

class GameStart(BaseModel):
    players: int

class GameGet(BaseModel):
    uuid: str
    turn: int
    status: str
    to_move: str
    moves_remaining: int
