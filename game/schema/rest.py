from pydantic import BaseModel
from typing import List, Optional
from .game_state import GameStatus, BoardStateExposed, PlayerColor

class GameResponse(BaseModel):
    id: str
    status: GameStatus
    players: List[PlayerColor]

class GameResponseDetail(GameResponse):
    id: str
    status: GameStatus
    players: List[PlayerColor]
    state: Optional[BoardStateExposed]

class PlayerInfo(BaseModel):
    token: str
    color: PlayerColor
