from ....schema import ResolveShortfallAction, ActionContext, ParameterAction, Player, ValidationResult, ActionType, BoardState
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
    
    def validate_action_context(self, action_context, action) -> ValidationResult:
            allowed_actions = self.state_manager.ACTION_CONTEXT_MAP.get(action_context)
            is_allowed = isinstance(action, allowed_actions) if allowed_actions else False
            if not is_allowed:
                return ValidationResult(is_valid=False,
                                        message=f'Action is not appropriate for context {action_context}')
            return ValidationResult(is_valid=True)

    def validate_shortfall_action(self, action:ResolveShortfallAction, player:Player) -> ValidationResult:
        if player.bank >= 0:
            return ValidationResult(is_valid=False, message=f'Player {player.color} is not in shortfall')
        if not action.slot_id:
            for building in self.state.iter_placed_buildings():
                if building.owner == player.color:
                    return ValidationResult(is_valid=False, message=f'Player {player.color} has building in slot {building.slot_id}, sell it first')
        return ValidationResult(is_valid=True)
