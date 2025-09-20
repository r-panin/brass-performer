import httpx
import websockets
import json
import random
import asyncio
from typing import List, Dict

class TestClient:
    def __init__(self, num_players: int = 2):
        self.base_url = "http://localhost:8000"
        self.ws_url = "ws://localhost:8000/ws"
        self.num_players = num_players
        self.game_id = None
        self.tokens: List[str] = []
        self.connections = []
        self.player_colors = {}  # Соответствие между соединением и цветом игрока

    async def setup(self):
        # Шаг 1: Создание игры
        async with httpx.AsyncClient() as client:
            response = await client.post(f"{self.base_url}/games")
            data = response.json()
            self.game_id = data['id']
            print(f"Game created with ID: {self.game_id}")

            # Шаг 2: Подключение игроков
            for _ in range(self.num_players):
                response = await client.post(f"{self.base_url}/games/{self.game_id}/join")
                data = response.json()
                self.tokens.append(data['token'])
                print(f"Player joined, token: {data['token']}")

            # Шаг 3: Запуск игры
            response = await client.post(f"{self.base_url}/games/{self.game_id}/start")
            if response.status_code == 200:
                print("Game started successfully")
            else:
                print(f"Error starting game: {response.status_code}")

        # Шаг 4: WebSocket подключения
        for token in self.tokens:
            ws = await websockets.connect(f"{self.ws_url}/{self.game_id}/player/{token}")
            self.connections.append(ws)
            print(f"WebSocket connected for token: {token}")
            state_msg = await ws.recv()
            state = json.loads(state_msg)
            self.player_colors[ws] = state['your_color']
            print(f"Player color: {state['your_color']}")

    async def game_loop(self):
        print("Starting game loop...")
        
        while True:
            # Получаем текущее состояние от любого игрока
            await self.connections[0].send(json.dumps({"request": "state"}))
            state_msg = await self.connections[0].recv()
            r = json.loads(state_msg)
            
            if 'error' in r.keys():
                print(r['error'])
            if 'result' in r.keys():
                if not 'state' in r['result'].keys():
                    continue
                else:
                    state = r['result']['state']
            else:
                state = r['state']
            
            if state.get('end_of_game', False):
                print("Game over!")
                break

            turn_order = state['turn_order']
            current_player_color = turn_order[0]
            
            # Находим соединение для текущего игрока
            current_player_conn = None
            for conn, color in self.player_colors.items():
                if color == current_player_color:
                    current_player_conn = conn
                    break
            
            if not current_player_conn:
                print(f"Could not find connection for player {current_player_color}")
                continue

            # Запрашиваем возможные действия от текущего игрока
            await current_player_conn.send(json.dumps({"request": "actions"}))
            actions_msg = await current_player_conn.recv()
            actions_data = json.loads(actions_msg)
            
            # Проверяем, не пришло ли состояние вместо действий
            if 'state' in actions_data:
                # Это состояние, а не действия - пропускаем ход
                print("Received state instead of actions, skipping turn")
                continue
            if 'error' in actions_data:
                print(actions_data['error'])
                
            print(f'KEYS IN ACTION DATA: {actions_data.keys()}')
            if actions_data.get('end_of_game', False):
                print("Game over!")
                break

            # Выбираем случайное действие
            result = actions_data['result']

            if 'state' in result.keys():
                continue
            
            # Проверяем, есть ли доступные действия
            if not any(result.values()):
                print("No available actions, skipping turn")
                continue
                
            # Выбираем случайную категорию с действиями
            available_categories = [cat for cat, actions in result.items() if actions]
            print(f'CATEGORIES: {available_categories}')
            if not available_categories:
                print("No available action categories, skipping turn")
                continue
                
            random_category = random.choice(available_categories)
            print(f'SELECTED CATEGORY: {random_category}')
            random_action = random.choice(result[random_category])
            print(f'SELECTED ACTION: {random_action}')
            
            # Отправляем действие и ожидаем ответ
            await current_player_conn.send(json.dumps(random_action))
            print(f"Player {current_player_color} sent action: {random_action}")
            
            # Ждем подтверждение действия или обновление состояния
            response_msg = await current_player_conn.recv()
            print(json.loads(response_msg).keys())
            
    async def run(self):
        await self.setup()
        await self.game_loop()
        
        # Закрываем все соединения
        for conn in self.connections:
            await conn.close()

if __name__ == "__main__":
    import sys
    num_players = int(sys.argv[1]) if len(sys.argv) > 1 else 2
    client = TestClient(num_players)
    asyncio.run(client.run())