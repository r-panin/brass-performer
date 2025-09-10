from ...schema import ActionContext, ParameterAction, Player, ValidationResult, ActionType, BoardState, BuildSelection, DevelopSelection, NetworkSelection, ScoutSelection, SellSelection
from typing import Dict
from .validators import ActionValidator, PassValidator, ScoutValidator, LoanValidator, DevelopValidator, NetworkValidator, BuildValidator, SellValidator

class ActionValidationService():
    def __init__(self):
        self.validators: Dict[ActionType, ActionValidator] = {
            ActionType.PASS: PassValidator(),
            ActionType.SCOUT: ScoutValidator(),
            ActionType.LOAN: LoanValidator(),
            ActionType.DEVELOP: DevelopValidator(),
            ActionType.NETWORK: NetworkValidator(),
            ActionType.BUILD: BuildValidator(),
            ActionType.SELL: SellValidator(),
        }

    def validate_action(self, action: ParameterAction, board_state:BoardState, player: Player) -> ValidationResult:
        validator = self.validators.get(action.action_type)
        if not validator:
            return ValidationResult(is_valid=False, message=f"No validator for action type {action.action_type}") 

        
        return validator.validate(action, board_state, player)
    