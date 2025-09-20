from ....schema import ActionContext, ParameterAction, Player, ValidationResult, ActionType, BoardState
from typing import Dict
from .validators import ActionValidator, PassValidator, ScoutValidator, LoanValidator, DevelopValidator, NetworkValidator, BuildValidator, SellValidator
from .event_bus import EventBus, ValidationEvent

class ActionValidationService():
    def __init__(self, event_bus:EventBus):
        self.validators: Dict[ActionType, ActionValidator] = {
            ActionType.PASS: PassValidator(),
            ActionType.SCOUT: ScoutValidator(),
            ActionType.LOAN: LoanValidator(),
            ActionType.DEVELOP: DevelopValidator(),
            ActionType.NETWORK: NetworkValidator(),
            ActionType.BUILD: BuildValidator(),
            ActionType.SELL: SellValidator(),
        }
        self.event_bus = event_bus

    def validate_action(self, action: ParameterAction, board_state:BoardState, player: Player, context:ActionContext) -> ValidationResult:
        validator = self.validators.get(ActionType(context))
        if not validator:
            return ValidationResult(is_valid=False, message=f"No validator for action type {action.action_type}") 
        
        result = validator.validate(action, board_state, player)
        if not result.is_valid:
            self.event_bus.publish(ValidationEvent(
                reason=result.message,
                actor=validator.__class__.__name__
            ))
        return result
    