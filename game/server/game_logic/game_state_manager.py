from enum import Enum, auto
from dataclasses import dataclass
from copy import deepcopy
from ...schema import ActionContext, BoardState, PlayerColor, MetaActions, CommitAction, BuildSelection, DevelopSelection, NetworkSelection, ParameterAction, ScoutSelection,SellSelection,EndOfTurnAction,ResolveShortfallAction
from typing import List, Dict, get_args
from .services.event_bus import EventBus, MetaActionEvent, CommitEvent, InitialStateEvent
from deepdiff import DeepDiff
import logging


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
    ACTION_CONTEXT_MAP = {
        ActionContext.MAIN: get_args(MetaActions),
        ActionContext.AWAITING_COMMIT: (CommitAction,),
        ActionContext.BUILD: (BuildSelection, CommitAction),
        ActionContext.DEVELOP: (DevelopSelection, CommitAction),
        ActionContext.NETWORK: (NetworkSelection, CommitAction),
        ActionContext.PASS: (ParameterAction, CommitAction),
        ActionContext.SCOUT: (ScoutSelection, CommitAction),
        ActionContext.SELL: (SellSelection, CommitAction),
        ActionContext.LOAN: (ParameterAction, CommitAction),
        ActionContext.END_OF_TURN: (EndOfTurnAction, CommitAction),
        ActionContext.SHORTFALL: (ResolveShortfallAction,),
        ActionContext.GLOUCESTER_DEVELOP: (DevelopSelection, CommitAction)
    }
    def __init__(self, initial_state:BoardState, event_bus:EventBus):
        self._state = GameState(
            _backup_state=deepcopy(initial_state),
            turn_state=deepcopy(initial_state),
            transaction_state=deepcopy(initial_state),
            phase=GamePhase.MAIN
        )
        self.event_bus = event_bus
        self.event_bus.publish(InitialStateEvent(
            state=initial_state
        ))
    
    @property
    def current_state(self) -> BoardState:
        return self._state.transaction_state

    @property
    def public_state(self) -> BoardState:
        return self._state.turn_state.hide_state()
    
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
        
        old_context = deepcopy(self.action_context)
        self._state.phase = GamePhase.TRANSACTION
        self._state.action_context = context
        self._state.transaction_state.subaction_count = 0
        self.event_bus.publish(MetaActionEvent(
            old_context=old_context, new_context=self.action_context
        ))
    
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
        
        self.event_bus.publish(CommitEvent(
            diff=DeepDiff(self._state.turn_state.model_dump(), self._state.transaction_state.model_dump())
        ))
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
        logging.debug(f"Rollback action, actions left {self.current_state.actions_left}")

    def rollback_turn(self) -> None:
        self._state.phase = GamePhase.MAIN
        self._state.action_context = ActionContext.MAIN
        self._state.turn_state = deepcopy(self._state._backup_state)
        self._state.transaction_state = deepcopy(self._state._backup_state)
        self._state.transaction_state.subaction_count = 0
        logging.debug(f"Rollback turn, actions left = {self.current_state.actions_left}")
    
    def end_turn(self) -> None:
        """Переводит в состояние подтверждения завершения хода"""
        self._state.phase = GamePhase.END_OF_TURN
        self._state.action_context = ActionContext.END_OF_TURN
    
    def start_new_turn(self, new_state: BoardState) -> None:
        """Начинает новый ход"""
        self._state._backup_state = deepcopy(new_state)
        self._state.turn_state = deepcopy(new_state)
        self._state.transaction_state = deepcopy(new_state)
        if self.action_context is not ActionContext.SHORTFALL:
            self._state.phase = GamePhase.MAIN
            self._state.action_context = ActionContext.MAIN
        self._state.transaction_state.subaction_count = 0
        

    def enter_shortfall(self):
        self._state.action_context = ActionContext.SHORTFALL
        self._state.phase = GamePhase.SHORTFALL

    def exit_shortfall(self):
        self._state.action_context = ActionContext.MAIN
        self._state.phase = GamePhase.MAIN
        self._state._backup_state = deepcopy(self._state.transaction_state)
        self._state.turn_state = deepcopy(self._state.transaction_state)

    def enter_gloucester_develop(self):
        self._state.action_context = ActionContext.GLOUCESTER_DEVELOP
        self._state.transaction_state.gloucester_develop = True
        if self.subaction_count < 1:
            self.subaction_count = 1

    def exit_gloucester_develop(self):
        self.action_context = ActionContext.SELL
        self._state.transaction_state.gloucester_develop = False
    
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
    
    def get_expected_params(self, color:PlayerColor) -> Dict[str, List[str]]:
        if not self.is_player_to_move(color):
            return {}
        classes = self.ACTION_CONTEXT_MAP[self.action_context]
        out = {}
        for cls in classes:
            fields = list(cls.model_fields.keys())
            if self.action_context not in (ActionContext.MAIN, ActionContext.AWAITING_COMMIT, ActionContext.END_OF_TURN):
                if self.has_subaction() and 'card_id' in fields:
                    fields.remove('card_id')
            out[cls.__name__] = fields
        return out
    
    def is_player_to_move(self, color:PlayerColor):
        if self.action_context is ActionContext.SHORTFALL:
            if self.current_state.players[color].bank < 0:
                return True
            return False
        
        if self.current_state.turn_order[0] != color:
            return False
        return True
    
    def get_turn_diff(self) -> DeepDiff:
        return DeepDiff(self._state._backup_state.model_dump(), self.current_state.model_dump())