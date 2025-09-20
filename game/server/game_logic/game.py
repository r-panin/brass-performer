from ...schema import BoardState, PlayerColor, IndustryType, GameStatus, PlayerState, ActionProcessResult, RequestResult
from typing import List 
import random
from uuid import uuid4
import logging
import copy
from .game_state_manager import GameStateManager
from .action_space_generator import ActionSpaceGenerator
from .game_initializer import GameInitializer
from .action_processor import ActionProcessor
from .services.event_bus import EventBus
from .services.replay_service import ReplayService
from pathlib import Path



class Game:
    REPLAYS_PATH = Path(r"game\replays")
    @property
    def state(self) -> BoardState:
        return self.state_manager.current_state

    def __init__(self):
        self.id = str(uuid4())
        self.status = GameStatus.CREATED
        self.available_colors = copy.deepcopy(list(PlayerColor))
        random.shuffle(self.available_colors)
        logging.basicConfig(level=logging.INFO)

        self.event_bus = EventBus()
        self.initializer = GameInitializer()

    def start(self, player_count:int, player_colors:List[PlayerColor]):
        self.replay_service = ReplayService(self.event_bus)
        self.state_manager = GameStateManager(self.initializer.create_initial_state(player_count, player_colors), self.event_bus)
        logging.debug("STATE CREATED")
        self.action_space_generator = ActionSpaceGenerator(self.state_manager)
        self.action_processor = ActionProcessor(self.state_manager, self.event_bus)
        self.status = GameStatus.ONGOING
        logging.debug("START SUCCESS")
    
    def get_player_state(self, color:PlayerColor, state:BoardState=None) -> PlayerState:
        if state is None:
            state = self.state
        return PlayerState(
            state=state.hide_state(),
            your_color=color,
            your_hand={card.id: card for card in self.state.players[color].hand.values()}
        )

    def process_action(self, action, color) -> ActionProcessResult|RequestResult:
        if self.status is not GameStatus.ONGOING:
            raise ValueError(f'Cannot submit actions to a game in {self.status}')
        process_result = self.action_processor.process_incoming_message(action, color)
        if isinstance(process_result, ActionProcessResult):
            if process_result.end_of_game:
                self.status = GameStatus.COMPLETE
                self.replay_service.save_replay(self.REPLAYS_PATH / game.id)
        return process_result

if __name__ == '__main__':
    game = Game()
    game.start(4, ['white', 'red', 'yellow', 'purple'])
    player = game.state.players[game.state.turn_order[0]]
    for slot in game.state.iter_building_slots():
        if 'brewery' in slot.industry_type_options:
            slot.building_placed = next(building for building in player.available_buildings.values() if building.industry_type == IndustryType.BREWERY)
            slot.building_placed.slot_id = slot.id
        elif 'box' in slot.industry_type_options:
            slot.building_placed = next(building for building in player.available_buildings.values() if building.industry_type == IndustryType.BOX)
            slot.building_placed.slot_id = slot.id
        elif 'cotton' in slot.industry_type_options:
            slot.building_placed = next(building for building in player.available_buildings.values() if building.industry_type == IndustryType.COTTON)
            slot.building_placed.slot_id = slot.id
        elif 'pottery' in slot.industry_type_options:
            slot.building_placed = next(building for building in player.available_buildings.values() if building.industry_type == IndustryType.POTTERY)
            slot.building_placed.slot_id = slot.id
    for link in game.state.links.values():
            link.owner = player.color
    print(len(game.get_valid_sell_actions(player)))