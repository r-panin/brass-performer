from game.server.game_logic.game import Game
from game.server.game_logic.action_space_generator import ActionSpaceGenerator
from game.schema import PlayerColor
import json

colors = list(PlayerColor)

game = Game()
game.start(4, colors)

active_player = game.state_service.get_active_player().color
partial_state = game.get_player_state(active_player)
action_generator = ActionSpaceGenerator()

starting_hash = json.dumps([action.model_dump() for action in action_generator.get_action_space(game.state_service, active_player)], sort_keys=True)

for _ in range(100):
    new_game = Game.from_partial_state(partial_state)
    new_hash = json.dumps([action.model_dump() for action in action_generator.get_action_space(new_game.state_service, active_player)], sort_keys=True)

    print(new_hash == starting_hash)