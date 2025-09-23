from fastapi import FastAPI
from .managers import ConnectionManager
from .managers import GameManager
from fastapi.middleware.cors import CORSMiddleware
from .endpoints.game_management import router as game_router
from .endpoints.websocket import router as websocket_router
import logging
import sys


logging.basicConfig(
    level=logging.DEBUG,  # Уровень логирования
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",  # Формат сообщений
    handlers=[logging.StreamHandler(sys.stdout)]  # Вывод в stdout
)
logging.getLogger().setLevel(logging.DEBUG)

connection_manager = ConnectionManager()
game_manager = GameManager()

app = FastAPI(title="Brass Server", version="1.0.0")

app.include_router(game_router)
app.include_router(websocket_router)

origins = [
    "http://localhost",
    "http://localhost:8000",
    "http://127.0.0.1",
    "http://127.0.0.1:8000",
    "http://localhost:8080",
    "http://127.0.0.1:8080"
]

# Настройка CORS для веб-интерфейса
app.add_middleware(
    CORSMiddleware,
    allow_origins=origins,  
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


