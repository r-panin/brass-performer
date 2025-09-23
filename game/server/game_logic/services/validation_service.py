from ....schema import Action, Player, ValidationResult, ActionType, BoardState
from typing import Dict
from .validators import ActionValidator, PassValidator, ScoutValidator, LoanValidator, DevelopValidator, NetworkValidator, BuildValidator, SellValidator, CommitValidator, ShortfallValidator
from .event_bus import EventBus, ValidationEvent
from ..action_cat_provider import ActionsCatProvider


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
            ActionType.COMMIT: CommitValidator(),
            ActionType.SHORTFALL: ShortfallValidator()
        }
        self.event_bus = event_bus
        self.context_map = ActionsCatProvider.ACTION_CONTEXT_MAP

    def validate_action(self, action:Action, board_state:BoardState, player: Player) -> ValidationResult:
        context_validation = self._validate_action_context(board_state.action_context, action)
        if not context_validation.is_valid:
            return ValidationResult(is_valid=False, message=f"Context {board_state.action_context} does not permit action type {action.action}")
        validator = self.validators.get(action.action)
        if not validator:
            return ValidationResult(is_valid=False, message=f"No validator for action type {action.action_type}") 
        
        result = validator.validate(action, board_state, player)
        if not result.is_valid:
            self.event_bus.publish(ValidationEvent(
                reason=result.message,
                actor=validator.__class__.__name__
            ))
        return result
    
    def _validate_action_context(self, action_context, action) -> ValidationResult:
            allowed_actions = self.context_map[action_context]
            is_allowed = isinstance(action, allowed_actions)
            if not is_allowed:
                return ValidationResult(is_valid=False,
                                        message=f'Action is not appropriate for context {action_context}')
            return ValidationResult(is_valid=True)
