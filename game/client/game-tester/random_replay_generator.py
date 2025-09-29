import httpx
import websockets
import json
import random
import asyncio
from typing import Dict, List, Optional

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
            self.player_colors[state['your_color']] = ws
            print(f"Player color: {state['your_color']}")
        
        active_player = state['state']['turn_order'][0]
        return active_player

    async def game_loop(self, first_active: str):
        print("Starting game loop...")
        active_player = first_active
        active_conn = self.player_colors[first_active]
        
        max_iterations = 10000
        iteration_count = 0

        while iteration_count < max_iterations:
            iteration_count += 1
            print(f"\n--- Turn {iteration_count}, active: {active_player} ---")
            
            # 1. Получаем доступные действия для текущего игрока
            actions_response = await self._request_actions(active_conn)
            if not actions_response:
                print("Failed to get actions, trying to recover...")
                success = await self._recover_from_error(active_conn)
                if not success:
                    break
                continue

            # 2. Если действий нет - передаем ход следующему игроку
            if not actions_response.get('result'):
                print("No actions available, passing turn")
                print(actions_response['result'])
                next_player = await self._pass_turn(active_conn)
                if next_player:
                    active_player = next_player
                    active_conn = self.player_colors[active_player]
                continue

            # 3. Выбираем и выполняем случайное действие
            action_result = await self._perform_random_action(
                active_conn, actions_response['result']
            )
            
            if not action_result:
                print("Action failed, trying to recover...")
                success = await self._recover_from_error(active_conn)
                if not success:
                    break
                continue

            # 4. Обрабатываем результат действия
            if action_result.get('end_of_game'):
                print("Game over")
                break

            # 5. Определяем следующего игрока
            next_player = await self._determine_next_player(
                active_conn, action_result, active_player
            )
            
            if not next_player:
                print("Failed to determine next player")
                break
                
            if next_player != active_player:
                active_player = next_player
                active_conn = self.player_colors[active_player]

        print("Game loop ended")

    async def _get_state(self, conn) -> Optional[Dict]:
        """Запрос текущего состояния игры"""
        try:
            await conn.send(json.dumps({"request": "state"}))
            response = await conn.recv()
            return json.loads(response)
        except Exception as e:
            print(f"Error getting state: {e}")
            return None

    async def _request_actions(self, conn) -> Optional[Dict]:
        """Запрос доступных действий с очисткой буфера сообщений"""
        try:
            # Очищаем буфер от возможных предыдущих сообщений
            await self._clear_message_buffer(conn)
            
            # Отправляем запрос действий
            await conn.send(json.dumps({"request": "actions"}))
            response = await conn.recv()
            actions_data = json.loads(response)
            
            # Проверяем структуру ответа
            if "result" in actions_data:
                return actions_data
            else:
                print(f"Invalid actions response: {actions_data}")
                return None
                
        except Exception as e:
            print(f"Error requesting actions: {e}")
            return None

    async def _clear_message_buffer(self, conn):
        """Очистка буфера сообщений с таймаутом"""
        try:
            while True:
                # Пытаемся прочитать сообщение без блокировки
                try:
                    message = await asyncio.wait_for(conn.recv(), timeout=0.1)
                    print(f"Cleared buffered message: {message[:100]}...")
                except asyncio.TimeoutError:
                    # Нет сообщений в буфере
                    break
                except Exception as e:
                    print(f"Error clearing buffer: {e}")
                    break
        except Exception as e:
            print(f"Error in buffer clearing: {e}")

    def _choose_action(self, actions_list: List) -> Optional[Dict]:
        """Выбор случайного действия с исключением commit: false при наличии альтернатив"""
        return random.choice(actions_list) if actions_list else None

    async def _perform_random_action(self, conn, actions_list: List) -> Optional[Dict]:
        """Выполнение случайного действия с валидацией ответа"""
        try:
            # Выбираем действие
            action = self._choose_action(actions_list)
            if not action:
                return None

            # Отправляем действие
            await conn.send(json.dumps(action))
            print(f"Perfoming action {action}")
            response = await conn.recv()
            result = json.loads(response)
            
            # Валидация ответа
            if not self._validate_action_response(result):
                print(f"Invalid action response: {result}")
                return None
                
            return result
            
        except Exception as e:
            print(f"Error performing action: {e}")
            return None

    def _validate_action_response(self, response: Dict) -> bool:
        """Проверка валидности ответа на действие"""
        required_fields = ['state', 'processed', 'awaiting']
        return all(field in response for field in required_fields)

    async def _pass_turn(self, conn) -> Optional[str]:
        """Явная передача хода следующему игроку"""
        try:
            # Запрашиваем текущее состояние
            await conn.send(json.dumps({"request": "state"}))
            response = await conn.recv()
            state_data = json.loads(response)
            
            # Извлекаем следующего игрока из состояния
            if 'state' in state_data and 'turn_order' in state_data['state']:
                print(f"Passing to {state_data['state']['turn_order'][0]}")
                print(f"Full turn order: {state_data['state']['turn_order']}")
                return state_data['state']['turn_order'][0]
            else:
                print(f"Invalid state response: {state_data}")
                return None
                
        except Exception as e:
            print(f"Error passing turn: {e}")
            return None

    async def _determine_next_player(self, conn, action_result: Dict, active_player: str) -> Optional[str]:
        """Определение следующего игрока на основе результата действия"""
        try:
            # Получаем состояние из ответа действия или запрашиваем отдельно
            if action_result.get('processed', False) and 'state' in action_result:
                state_data = action_result
            else:
                state_data = await self._get_state(conn)
                if not state_data:
                    return None

            # Извлекаем контекст и порядок ходов
            context = state_data['state']['action_context']
            turn_order = state_data['state']['turn_order']
            # Если контекст shortfall, ищем следующего игрока с действиями
            if context == 'shortfall':
                next_player = await self._get_next_player_shortfall(active_player, turn_order)
                return next_player if next_player else turn_order[0]
            else:    
                # Стандартная логика: первый игрок в turn_order
                return turn_order[0]
                
        except Exception as e:
            print(f"Error determining next player: {e}")
            return None

    async def _get_next_player_shortfall(self, current_player: str, turn_order: List[str]) -> Optional[str]:
        """Поиск следующего игрока с действиями в контексте shortfall"""
        current_index = turn_order.index(current_player)
        next_index = (current_index + 1) % len(turn_order)
        checked_players = 0

        # Перебираем всех игроков по кругу
        while checked_players < len(turn_order):
            player = turn_order[next_index]
            conn = self.player_colors[player]
            
            # Запрашиваем действия для игрока
            actions_response = await self._request_actions(conn)
            if actions_response and actions_response.get('result'):
                return player  # Нашли игрока с действиями
            
            # Переходим к следующему игроку
            next_index = (next_index + 1) % len(turn_order)
            checked_players += 1

        return None  # Ни у кого нет действий

    async def _recover_from_error(self, conn) -> bool:
        """Попытка восстановления после ошибки"""
        try:
            # Очищаем буфер и запрашиваем состояние
            await self._clear_message_buffer(conn)
            await conn.send(json.dumps({"request": "state"}))
            response = await conn.recv()
            state_data = json.loads(response)
            
            if 'state' in state_data:
                print("Recovered from error")
                return True
            else:
                print("Failed to recover from error")
                return False
                
        except Exception as e:
            print(f"Error in recovery: {e}")
            return False

    async def run(self):
        first_active = await self.setup()
        await self.game_loop(first_active)
        
        # Закрываем все соединения
        for conn in self.connections:
            await conn.close()

if __name__ == "__main__":
    import sys
    num_players = int(sys.argv[1]) if len(sys.argv) > 1 else 4
    client = TestClient(num_players)
    asyncio.run(client.run())