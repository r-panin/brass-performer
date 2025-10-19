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
    mcts = MCTS(simulations=5000, depth=10000)

    game = Game()
    colors = list(PlayerColor)
    game.start(4, colors) 
    with open(Path(__file__).resolve().parent / 'mcts_game_results.log', 'w', encoding='utf-8') as outpath:
        outpath.write("********************\n")
        outpath.write("Game started\n")
        outpath.write("Merchant slots: \n")
        for slot in game.state_service.iter_merchant_slots():
            outpath.write(f"City {slot.city}, buys {slot.merchant_type}\n")

        while not game.concluded():
        # for _ in range(1): # placeholder single run
            print(f"Current round: {game.state_service.round_count}")
            active_player = game.state_service.get_active_player().color
            outpath.write(f"Current active player: {active_player}\n")

            test_state = game.get_player_state(active_player)        

            best_action = mcts.search(test_state)
            outpath.write(f"Player {active_player} selects action: {best_action}\n")
            result = game.process_action(best_action, active_player)
            outpath.write(f"Action result: {result.processed}, message: {result.message}\n")
        outpath.write("Final scores\n")
        for player in game.state_service.state.players.values():
            outpath.write(f"Player {player.color} finished with a score {player.victory_points} and income {player.income}\n")

cProfile.run('main()', 'mcts_profile')
p = pstats.Stats('mcts_profile')
p.sort_stats('cumulative').outpath.write_stats(20)
#main()
