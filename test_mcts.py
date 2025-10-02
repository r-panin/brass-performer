from game.client.MCTS.mcts import MCTS
from game.server.game_logic.game import Game
from game.schema import PlayerColor
import cProfile
import pstats
import logging
from pathlib import Path

logging.basicConfig(
    level=logging.DEBUG,  # Уровень логирования
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",  # Формат сообщений
    handlers=[logging.FileHandler(Path(__file__).resolve().parent / 'game/mcts.log')]  # Вывод в stdout
)
logging.getLogger().setLevel(logging.DEBUG)

def main():
    mcts = MCTS(simulations=10000, depth=10000)

    game = Game()
    colors = list(PlayerColor)
    game.start(4, colors) 
    print("********************")
    print("Game started")
    print("Merchant slots: ")
    for slot in game.state_service.iter_merchant_slots():
        print(f"City {slot.city}, buys {slot.merchant_type}")

    while not game.concluded():
        active_player = game.state_service.get_active_player().color
        print(f"Current active player: {active_player}")

        test_state = game.get_player_state(active_player)        

        best_action = mcts.search(test_state)
        print(f"Игрок {active_player} выбирает действие: {best_action}")
        result = game.process_action(best_action, active_player)
        print(result.processed, result.message)
    print("Final scores")
    for player in game.state_service.state.players.values():
        print(f"Player {player.color} finished with a score {player.victory_points} and income {player.income}")

cProfile.run('main()', 'mcts_profile')
p = pstats.Stats('mcts_profile')
p.sort_stats('cumulative').print_stats(20)
#main()
