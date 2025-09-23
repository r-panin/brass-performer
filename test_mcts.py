from game.client.MCTS.mcts import MCTS
from game.server.game_logic.game import Game
from game.schema import PlayerColor
import logging
import sys

logging.basicConfig(
    level=logging.INFO,  # Уровень логирования
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",  # Формат сообщений
    handlers=[logging.StreamHandler(sys.stdout)]  # Вывод в stdout
)
logging.getLogger().setLevel(logging.INFO)

mcts = MCTS(simulations=100, depth=10000)

game = Game()
colors = list(PlayerColor)
game.start(4, colors) 

test_state = game.get_player_state(game.state.turn_order[0])

best_action = mcts.search(test_state)
print(f"Найдено лучшее действие: {best_action}")

