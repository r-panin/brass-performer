from fastapi import FastAPI
from .managers import ConnectionManager
from .managers import GameManager
from fastapi.middleware.cors import CORSMiddleware
from .endpoints.game_management import router as game_router
from .endpoints.websocket import router as websocket_router

connection_manager = ConnectionManager()
game_manager = GameManager()

app = FastAPI(title="Brass Server", version="1.0.0")

app.include_router(game_router)
app.include_router(websocket_router)

# Настройка CORS для веб-интерфейса
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # В продакшене замените на конкретные домены
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


