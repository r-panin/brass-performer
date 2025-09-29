from .services.validation_service import ActionValidationService
from .services.event_bus import EventBus
from ...schema import BoardState, Action, PlayerColor, ActionProcessResult, Request, RequestType, RequestResult, PlayerState, ActionSpaceRequestResult
from .state_changer import StateChanger
from .action_space_generator import ActionSpaceGenerator
from .action_cat_provider import ActionsCatProvider
from .services.board_state_service import BoardStateService


class ActionProcessor():

    def __init__(self, state_service:BoardStateService, event_bus:EventBus=None):
        self.state_service = state_service
        self.validation_service = ActionValidationService(event_bus)
        self.state_changer = StateChanger(state_service, event_bus)
        self.action_space_generator = ActionSpaceGenerator()
        self.event_bus = event_bus
        self.ac_provider = ActionsCatProvider()

    def process_incoming_message(self, message, color:PlayerColor):
        if isinstance(message, Request):
            return self._process_request(message, color)
        elif isinstance(message, Action):
            return self._process_action(message, color)
        else:
            raise ValueError("Did not find a processor for incoming message")
    
    def _process_request(self, request:Request, color: PlayerColor) -> RequestResult:
        if request.request is RequestType.REQUEST_STATE:
           return PlayerState(
                state=self.state_service.get_exposed_state(),
                your_color=color,
                your_hand=self.state_service.get_player(color).hand,
                subaction_count=self.state_service.subaction_count,
                current_round=self.state_service.get_current_round()
            )
        elif request.request is RequestType.REQUEST_ACTIONS:
            actions = self.action_space_generator.get_action_space(self.state_service, color)
            return ActionSpaceRequestResult(
                success=True,
                result=actions
            )
        elif request.request is RequestType.GOD_MODE:
            return self.state_service.get_board_state()

    def _process_action(self, action: Action, color: PlayerColor) -> ActionProcessResult:
        # Проверяем, может ли игрок делать ход
        if not self.state_service.is_player_to_move(color):
            return ActionProcessResult(
                processed=False,
                message=f"Attempted move by {color}, current turn is {self.state_service.get_turn_order()[0]}",
                awaiting={},
                your_hand=self.state_service.get_player(color).hand,
                your_color=color,
                state=self.state_service.get_exposed_state(),
                current_round=self.state_service.get_current_round()
            )

        player = self.state_service.get_player(color)
        validation = self.validation_service.validate_action(action, self.state_service, player)
        if not validation.is_valid:
            return ActionProcessResult(
                processed=False,
                message=validation.message,
                awaiting=self.ac_provider.get_expected_params(self.state_service),
                your_hand=self.state_service.get_player(color).hand,
                your_color=color,
                state=self.state_service.get_exposed_state(),
                current_round=self.state_service.get_current_round()
            )
        
        # Обрабатываем действие в зависимости от типа
        self.state_service = self.state_changer.apply_action(action, self.state_service, player)

        return ActionProcessResult(
            processed=True,
            awaiting=self.ac_provider.get_expected_params(self.state_service),
            your_color=color,
            your_hand=self.state_service.get_player(color).hand,
            state=self.state_service.get_exposed_state(),
            current_round=self.state_service.get_current_round()
        )
