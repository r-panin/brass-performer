from .services.validation_service import ActionValidationService
from .services.event_bus import EventBus, TurnCommitEvent
from ...schema import Action, PlayerColor, ActionProcessResult, Request, RequestType, RequestResult, StateRequestResult, PlayerState, ActionSpaceRequestResult, MetaAction, ParameterAction, CommitAction, ActionContext, ResourceAction, AutoResourceSelection, EndOfTurnAction, ResolveShortfallAction, Player, ValidationResult
from .game_state_manager import GamePhase, GameStateManager
from .turn_manager import TurnManager
from .state_changer import StateChanger
from .action_space_generator import ActionSpaceGenerator


class ActionProcessor():

    def __init__(self, state_manager:GameStateManager, event_bus:EventBus):
        self.state_manager = state_manager
        self.validation_service = ActionValidationService(event_bus)
        self.turn_manager = TurnManager(event_bus)
        self.state_changer = StateChanger(state_manager, event_bus)
        self.action_space_generator = ActionSpaceGenerator(state_manager)
        self.event_bus = event_bus

    @property
    def state(self):
        return self.state_manager.current_state
    
    def validate_action_context(self, action_context, action) -> ValidationResult:
            allowed_actions = self.state_manager.ACTION_CONTEXT_MAP.get(action_context)
            is_allowed = isinstance(action, allowed_actions) if allowed_actions else False
            if not is_allowed:
                return ValidationResult(is_valid=False, message=f'Action is not appropriate for context {action_context}')
            return ValidationResult(is_valid=True)

    def process_incoming_message(self, message, color:PlayerColor):
        if isinstance(message, Request):
            return self._process_request(message, color)
        elif isinstance(message, Action):
            return self._process_action(message, color)
        else:
            raise ValueError("Did not find a processor for incoming message")
    
    def _process_request(self, request:Request, color: PlayerColor) -> RequestResult:
        if request.request is RequestType.REQUEST_STATE:
            return StateRequestResult(
                success=True,
                result=PlayerState(
                    common_state=self.state_manager.public_state,
                    your_color=color,
                    your_hand=self.state_manager.current_state.players[color].hand
                )
            )
        elif request.request is RequestType.REQUEST_ACTIONS:
            actions = self.action_space_generator.get_action_space(color)
            return ActionSpaceRequestResult(
                success=True,
                result=actions
            )

    def _process_action(self, action: Action, color: PlayerColor) -> ActionProcessResult:
        # Проверяем, может ли игрок делать ход
        if not self.state_manager.is_player_to_move(color):
            return ActionProcessResult(
                processed=False,
                message=f"Attempted move by {color}, current turn is {self.state.turn_order[0]}",
                awaiting={},
                current_context=self.state_manager.action_context,
                hand=self.state.players[color].hand,
                provisional_state=self.state_manager.get_provisional_state()
            )

        context_validateion = self.validate_action_context(self.state_manager.action_context, action)
        if not context_validateion.is_valid:
            return ActionProcessResult(
                processed=False,
                message=f"Attempted action {type(action)}, which current context {self.state_manager.action_context} forbids",
                awaiting=self.state_manager.get_expected_params(color),
                current_context=self.state_manager.action_context,
                hand=self.state.players[color].hand,
                provisional_state=self.state_manager.get_provisional_state()
            )
        
        # Обрабатываем действие в зависимости от типа
        if isinstance(action, MetaAction):
            return self._process_meta_action(action, color)
        elif isinstance(action, ParameterAction):
            return self._process_parameter_action(action, color)
        elif isinstance(action, CommitAction):
            return self._process_commit_action(action, color)
        elif isinstance(action, EndOfTurnAction):
            return self._process_end_of_turn_action(action, color)
        elif isinstance(action, ResolveShortfallAction):
            return self._process_resolve_shortfall_action(action, color)
        else:
            return ActionProcessResult(
                processed=False, 
                message="Unknown action type", 
                awaiting={'W': ('T', 'F')}, 
                current_context=self.state_manager.action_context,
                hand=self.state.players[color].hand,
                    provisional_state=self.state_manager.get_provisional_state()
            )

    def _process_meta_action(self, action: MetaAction, color: PlayerColor) -> ActionProcessResult:
        if self.state_manager.phase != GamePhase.MAIN:
            return ActionProcessResult(
                processed=False,
                message="Cannot submit a meta action outside of main context",
                awaiting=self.state_manager.get_expected_params(color),
                current_context=self.state_manager.action_context,
                hand=self.state.players[color].hand,
                    provisional_state=self.state_manager.get_provisional_state()
            )
        
        try:
            self.state_manager.start_transaction(ActionContext(action.action))
            return ActionProcessResult(
                processed=True,
                message=f"Entered {self.state_manager.action_context}",
                awaiting=self.state_manager.get_expected_params(color),
                current_context=self.state_manager.action_context,
                provisional_state=self.state_manager.get_provisional_state(),
                hand=self.state.players[color].hand
            )
        except ValueError as e:
            return ActionProcessResult(
                processed=False,
                message=str(e),
                awaiting=self.state_manager.get_expected_params(color),
                current_context=self.state_manager.action_context,
                hand=self.state.players[color].hand,
                    provisional_state=self.state_manager.get_provisional_state()
            )

    def _process_parameter_action(self, action: ParameterAction, color: PlayerColor) -> ActionProcessResult:
        if self.state_manager.phase != GamePhase.TRANSACTION:
            return ActionProcessResult(
                processed=False,
                message="No active transaction. Start with meta action",
                awaiting=self.state_manager.get_expected_params(color),
                current_context=self.state_manager.action_context,
                hand=self.state.players[color].hand,
                    provisional_state=self.state_manager.get_provisional_state()
            )
        
        player = self.state.players[color]
        
        # Автоматический выбор ресурсов, если нужно
        if isinstance(action, ResourceAction) and action.resources_used is AutoResourceSelection:
            action.resources_used = self._select_resources(action, player)
        
        # Валидация действия
        validation_result = self.validation_service.validate_action(
            action, 
            self.state, 
            player,
            self.state_manager.action_context
        )
        
        if not validation_result.is_valid:
            return ActionProcessResult(
                processed=False,
                message=validation_result.message,
                awaiting=self.state_manager.get_expected_params(color),
                current_context=self.state_manager.action_context,
                hand=player.hand
            )
        
        # Применяем действие
        self.state_changer.apply_action(action, player)
        
        # Обновляем состояние
        try:
            self.state_manager.add_subaction()
            return ActionProcessResult(
                processed=True,
                provisional_state=self.state_manager.get_provisional_state(),
                awaiting=self.state_manager.get_expected_params(color),
                current_context=self.state_manager.action_context,
                hand=player.hand
            )
        except ValueError as e:
            return ActionProcessResult(
                processed=False,
                message=str(e),
                awaiting=self.state_manager.get_expected_params(color),
                current_context=self.state_manager.action_context,
                hand=player.hand
            )

    def _process_commit_action(self, action: CommitAction, color: PlayerColor) -> ActionProcessResult:
        if self.state_manager.phase not in (GamePhase.TRANSACTION, GamePhase.AWAITING_COMMIT):
            return ActionProcessResult(
                processed=False,
                message="No active transaction to commit",
                awaiting=self.state_manager.get_expected_params(color),
                current_context=self.state_manager.action_context,
                hand=self.state.players[color].hand,
                provisional_state=self.state_manager.get_provisional_state()
            )
        
        if action.commit:
            if self.state_manager.subaction_count == 0:
                return ActionProcessResult(
                    processed=False,
                    message="No changes to state, nothing to commit",
                    awaiting=self.state_manager.get_expected_params(color),
                    current_context=self.state_manager.action_context,
                    hand=self.state.players[color].hand,
                    provisional_state=self.state_manager.get_provisional_state()
                )
            
            try:
                self.state_manager.commit_transaction()
                
                # Обновляем количество оставшихся действий
                self.state.actions_left -= 1
                
                if self.state.actions_left > 0:
                    # Продолжаем ход
                    return ActionProcessResult(
                        processed=True,
                        message="Changes committed",
                        provisional_state=self.state_manager.get_provisional_state(),
                        awaiting=self.state_manager.get_expected_params(color),
                        current_context=self.state_manager.action_context,
                        hand=self.state.players[color].hand
                    )
                else:
                    # Завершаем ход
                    self.state_manager.end_turn()
                    return ActionProcessResult(
                        processed=True,
                        message="Changes committed, confirm end of turn",
                        provisional_state=self.state_manager.get_provisional_state(),
                        awaiting=self.state_manager.get_expected_params(color),
                        current_context=self.state_manager.action_context,
                        hand=self.state.players[color].hand,
                    )
            except ValueError as e:
                return ActionProcessResult(
                    processed=False,
                    message=str(e),
                    awaiting=self.state_manager.get_expected_params(color),
                    current_context=self.state_manager.action_context,
                    hand=self.state.players[color].hand,
                    provisional_state=self.state_manager.get_provisional_state()
                )
        else:
            # Откатываем транзакцию
            try:
                self.state_manager.rollback_transaction()
                return ActionProcessResult(
                    processed=True,
                    message='Transaction rolled back',
                    provisional_state=self.state_manager.get_provisional_state(),
                    awaiting=self.state_manager.get_expected_params(color),
                    current_context=self.state_manager.action_context,
                    hand=self.state.players[color].hand,
                )
            except ValueError as e:
                return ActionProcessResult(
                    processed=False,
                    message=str(e),
                    awaiting=self.state_manager.get_expected_params(color),
                    current_context=self.state_manager.action_context,
                    hand=self.state.players[color].hand,
                    provisional_state=self.state_manager.get_provisional_state()
                )

    def _process_end_of_turn_action(self, action: EndOfTurnAction, color: PlayerColor) -> ActionProcessResult:
        if action.end_turn:
            # Завершаем ход и переходим к следующему игроку
            self.event_bus.publish(TurnCommitEvent(
                diff=self.state_manager.get_turn_diff(),
                actor=color
            ))


            next_state = self.turn_manager.prepare_next_turn(self.state)
            if self.turn_manager.concluded:
                return ActionProcessResult(processed=True, end_of_turn=True, awaiting={}, hand=self.state.players[color].hand,
                        provisional_state=self.state_manager.get_provisional_state(), end_of_game=True)
            self.state_manager.start_new_turn(next_state)
            return ActionProcessResult(processed=True, end_of_turn=True, awaiting={}, hand=self.state.players[color].hand,
                    provisional_state=self.state_manager.get_provisional_state())
        else:
            # Откатываемся к началу хода
            self.state_manager.rollback_turn()
            return ActionProcessResult(
                processed=True, 
                message='Reverted to turn start', 
                provisional_state=self.state_manager.get_provisional_state(), 
                awaiting={}, 
                current_context=self.state_manager.action_context,
                hand=self.state.players[color].hand
            )
        
    def _process_resolve_shortfall_action(self, action:ResolveShortfallAction, color: PlayerColor) -> ActionProcessResult:
        if self.state_manager.phase is not GamePhase.SHORTFALL:
            return ActionProcessResult(
                processed=False,
                awaiting=self.state_manager.get_expected_params(color),
                provisional_state=self.state_manager.get_provisional_state(),
                current_context=self.state_manager.action_context,
                hand=self.state.players[color].hand,
                message="Action is only allowed within shortfall context"
            )
        
        player = self.state.players[color]
        validation = self._validate_shortfall_action(self, action, player)
        if not validation.is_valid:
            return ActionProcessResult(
                processed=False,
                provisional_state=self.state_manager.get_provisional_state(),
                current_context=self.state_manager.action_context,
                hand=self.state.players[color].hand,
                message=validation.message,
                awaiting=self.state_manager.get_expected_params(color)
            )

        self.state_changer.resolve_shortfall(action, player)
        if not self._in_shortfall():
            self.state_manager.exit_shortfall()
     
    def _validate_shortfall_action(self, action:ResolveShortfallAction, player:Player) -> ValidationResult:
        if player.bank >= 0:
            return ValidationResult(is_valid=False, message=f'Player {player.color} is not in shortfall')
        if not action.slot_id:
            for building in self.state.iter_placed_buildings():
                if building.owner == player.color:
                    return ValidationResult(is_valid=False, message=f'Player {player.color} has building in slot {building.slot_id}, sell it first')
        return ValidationResult(is_valid=True)

    def _in_shortfall(self):
        if any(player.bank < 0 for player in self.state.players.values()):
            return True
        return False

    