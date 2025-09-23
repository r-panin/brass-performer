from game.client.MCTS.mcts import MCTS
from game.server.game_logic.game import Game
from game.schema import PlayerColor
import logging
from pathlib import Path
import cProfile
import pstats

logging.basicConfig(
    level=logging.INFO,  # Уровень логирования
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",  # Формат сообщений
    handlers=[logging.FileHandler(Path(r'G:\brass-performer\fuck.log'), mode='w')]  
)
logging.getLogger().setLevel(logging.INFO)

def main():
    mcts = MCTS(simulations=100, depth=10000)

    game = Game()
    colors = list(PlayerColor)
    game.start(4, colors) 

    test_state = game.get_player_state(game.state.turn_order[0])

    best_action = mcts.search(test_state)
    print(f"Найдено лучшее действие: {best_action}")

cProfile.run('main()', 'mcts_profile')
p = pstats.Stats('mcts_profile')
p.sort_stats('cumulative').print_stats(20)

