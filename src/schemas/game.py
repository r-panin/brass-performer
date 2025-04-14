from pydantic import BaseModel

class GameStart(BaseModel):
    players: int
    