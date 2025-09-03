from ...schema import Action, Player, ValidationResult, ActionType, BoardState
from typing import Dict
from .validators import ActionValidator, PassValidator, ScoutValidator, LoanValidator, DevelopValidator, NetworkValidator, BuildValidator, SellValidator, NetworkDoubleValidator, SellStepValidator, SellEndValidator, NetworkEndValidator

class ActionValidationService():
    def __init__(self):
        self.validators: Dict[ActionType, ActionValidator] = {
            ActionType.PASS: PassValidator(),
            ActionType.SCOUT: ScoutValidator(),
            ActionType.LOAN: LoanValidator(),
            ActionType.DEVELOP: DevelopValidator(),
            ActionType.DEVELOP_DOUBLE: DevelopDoubleValidator(),
            ActionType.DEVELOP_END: DevelopEndValidator(),
            ActionType.NETWORK: NetworkValidator(),
            ActionType.NETWORK_DOUBLE: NetworkDoubleValidator(),
            ActionType.NETWORK_END: NetworkEndValidator(),
            ActionType.BUILD: BuildValidator(),
            ActionType.SELL: SellValidator(),
            ActionType.SELL_STEP: SellStepValidator(),
            ActionType.SELL_END: SellEndValidator()
        }

    def validate_action(self, action: Action, board_state:BoardState, player: Player) -> ValidationResult:
        validator = self.validators.get(action.action_type)
        if not validator:
            return ValidationResult(is_valid=False, message=f"No validator for action type {action.action_type}") 
        
        return validator.validate(action, board_state, player)