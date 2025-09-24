from game.client.MCTS.mcts import MCTS
from game.server.game_logic.game import Game
from game.schema import PlayerColor
from pathlib import Path
import cProfile
import pstats


def main():
    mcts = MCTS(simulations=1000, depth=10000)

    game = Game()
    colors = list(PlayerColor)
    game.start(4, colors) 

    test_state = game.get_player_state(game.state_service.get_active_player().color)

    best_action = mcts.search(test_state)
    print(f"Найдено лучшее действие: {best_action}")

cProfile.run('main()', 'mcts_profile')
p = pstats.Stats('mcts_profile')
p.sort_stats('cumulative').print_stats(20)

