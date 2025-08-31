from abc import ABC, abstractmethod
from ...schema import BoardState, Action, Player, ValidationResult, ResourceSource, ResourceType
from typing import Dict, List


class ActionValidator(ABC):
    def __init__(self):
        super().__init__()

    @abstractmethod
    def validate(self, action: Action, game_state:BoardState, player: Player):
        pass

class BaseValidator(ActionValidator, ABC):
    def _validate_card_in_hand(self, action:Action, player:Player) -> ValidationResult:
        if action.card_id not in player.hand:
            return ValidationResult(False, "Card not in player's hand")
        return ValidationResult(True)
    
    def _validate_lowest_level_building(self, building_id:str, player:Player) -> ValidationResult:
        building = player.available_buildings.get(building_id)
        if not building:
            return ValidationResult(False, f"Building {building_id} is not present in player's roster")
        for b in player.available_buildings.values():
            if b.industry_type == building.industry_type and b.level < building.level:
                return ValidationResult(False, f"Building {b.id} has priority")
        return ValidationResult(True)
    
    def _validate_iron_preference(self, game_state:BoardState, resources: List[ResourceSource]):
        player_sources = game_state.get_player_iron_sources()