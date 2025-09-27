from game.server.game_logic.game import Game
import deepdiff
from copy import deepcopy
from game.client.MCTS.mcts import MCTS
from game.schema import PlayerColor

def main():
    mcts = MCTS(simulations=1000, depth=10000)

    game = Game()
    colors = list(PlayerColor)
    game.start(4, colors)
    initial_state = deepcopy(game.state_service)
    mcts.search(game.get_player_state(game.state_service.get_active_player().color))
    print(deepdiff.DeepDiff(initial_state, game.state_service))


main()