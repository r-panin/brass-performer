from enum import Enum, auto
from dataclasses import dataclass
from copy import deepcopy
from ...schema import ActionContext, BoardState

class GamePhase(Enum):
    MAIN = auto()
    TRANSACTION = auto()
    AWAITING_COMMIT = auto()
    END_OF_TURN = auto()
    SHORTFALL = auto()

@dataclass
class GameState:
    # Состояние на начало хода (для отката)
    _backup_state: BoardState
    # Состояние на момент последнего закоммиченного действия
    turn_state: BoardState
    # Текущее состояние в транзакции
    transaction_state: BoardState
    # Контекст действия
    action_context: ActionContext = ActionContext.MAIN
    # Количество поддействий в текущей транзакции
    subaction_count: int = 0
    # Текущая фаза игры
    phase: GamePhase = GamePhase.MAIN

class GameStateManager:
    SINGLE_ACTION_CONTEXTS = (ActionContext.BUILD, ActionContext.SCOUT, ActionContext.LOAN, ActionContext.PASS)
    DOUBLE_ACTION_CONTEXTS = (ActionContext.DEVELOP, ActionContext.NETWORK)
    def __init__(self, initial_state):
        self._state = GameState(
            _backup_state=deepcopy(initial_state),
            turn_state=deepcopy(initial_state),
            transaction_state=deepcopy(initial_state),
            phase=GamePhase.MAIN
        )
    
    @property
    def current_state(self) -> BoardState:
        return self._state.transaction_state
    
    @property
    def action_context(self) -> ActionContext:
        return self._state.action_context
    
    @property
    def phase(self) -> GamePhase:
        return self._state.phase

    @property
    def subaction_count(self) -> int:
        return self._state.transaction_state.subaction_count
    
    def start_transaction(self, context: ActionContext) -> None:
        """Начинает новую транзакцию"""
        if self._state.phase != GamePhase.MAIN:
            raise ValueError("Transaction can only start from MAIN phase")
        
        self._state.phase = GamePhase.TRANSACTION
        self._state.action_context = context
        self._state.transaction_state.subaction_count = 0
    
    def add_subaction(self) -> None:
        """Добавляет поддействие в текущую транзакцию"""
        if self._state.phase != GamePhase.TRANSACTION:
            raise ValueError("Can only add subactions in TRANSACTION phase")
        
        self._state.transaction_state.subaction_count += 1

        # Проверяем, нужно ли переходить в AWAITING_COMMIT
        max_actions = self._get_max_actions()
        if self._state.transaction_state.subaction_count >= max_actions:
            self._state.phase = GamePhase.AWAITING_COMMIT
            self._state.action_context = ActionContext.AWAITING_COMMIT
    
    def commit_transaction(self) -> None:
        """Фиксирует текущую транзакцию"""
        if self._state.phase not in (GamePhase.TRANSACTION, GamePhase.AWAITING_COMMIT):
            raise ValueError("Can only commit from TRANSACTION or AWAITING_COMMIT")
        
        # Обновляем состояние хода
        self._state.turn_state = deepcopy(self._state.transaction_state)
        
        # Сбрасываем транзакцию
        self._state.phase = GamePhase.MAIN
        self._state.action_context = ActionContext.MAIN
        self._state.transaction_state.subaction_count = 0
    
    def rollback_transaction(self) -> None:
        """Откатывает текущую транзакцию"""
        if self._state.phase not in (GamePhase.TRANSACTION, GamePhase.AWAITING_COMMIT):
            raise ValueError("Can only rollback from TRANSACTION or AWAITING_COMMIT")
        
        # Сбрасываем транзакцию
        self._state.phase = GamePhase.MAIN
        self._state.action_context = ActionContext.MAIN
        self._state.transaction_state = deepcopy(self._state.turn_state)
        self._state.transaction_state.subaction_count = 0

    def rollback_turn(self) -> None:
        self._state.phase = GamePhase.MAIN
        self._state.action_context = ActionContext.MAIN
        self._state.turn_state = deepcopy(self._state._backup_state)
        self._state.turn_state = deepcopy(self._state._backup_state)
        self._state.transaction_state.subaction_count = 0
    
    def end_turn(self) -> None:
        """Завершает ход"""
        self._state.phase = GamePhase.END_OF_TURN
        self._state.action_context = ActionContext.END_OF_TURN
        # Здесь может быть дополнительная логика завершения хода
    
    def start_new_turn(self, new_state: BoardState) -> None:
        """Начинает новый ход"""
        self._state._backup_state = deepcopy(new_state)
        self._state.turn_state = deepcopy(new_state)
        self._state.transaction_state = deepcopy(new_state)
        self._state.phase = GamePhase.MAIN
        self._state.action_context = ActionContext.MAIN
        self._state.transaction_state.subaction_count = 0

    def enter_shortfall(self):
        self.action_context = ActionContext.SHORTFALL
        self.phase = GamePhase.SHORTFALL

    def exit_shortfall(self):
        self.action_context = ActionContext.MAIN
        self.phase = GamePhase.MAIN
    
    def _get_max_actions(self) -> int:
        """Возвращает максимальное количество действий для текущего контекста"""
        if self._state.action_context in self.SINGLE_ACTION_CONTEXTS:
            return 1
        elif self._state.action_context in self.DOUBLE_ACTION_CONTEXTS:
            return 2
        return float('inf')
    
    def get_provisional_state(self) -> BoardState:
        """Возвращает состояние для клиента (скрывая приватные данные)"""
        state = self.current_state
        return state.hide_state()
    
    def has_subaction(self) -> bool:
        if self._state.transaction_state.subaction_count > 0:
            return True
        return False