from typing import Dict, List, Callable, Literal
from collections import defaultdict
from datetime import datetime
from pydantic import BaseModel, ConfigDict
from enum import StrEnum
from ....schema import PlayerColor, ActionContext, BoardState
from deepdiff import DeepDiff

class EventType(StrEnum):
    META_ACTION = 'meta_action'
    STATE_CHANGE = 'state_change'
    INTERTURN = 'interturn'
    COMMIT = 'commit'
    TURN_COMMIT = 'turn_commit'
    VALIDATION_FAIL = 'validation_fail'
    INITIAL_STATE = 'initial_state'


class Event(BaseModel):
    event_type: EventType
    timestamp: float = None
    model_config = ConfigDict(arbitrary_types_allowed=True)

    def __post_init__(self):
        if self.timestamp is None:
            self.timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")


class ValidationEvent(Event):
    reason: str
    actor: str
    event_type: Literal[EventType.VALIDATION_FAIL] = EventType.VALIDATION_FAIL


class StateChangeEvent(Event):
    diff: DeepDiff
    actor: PlayerColor
    event_type: Literal[EventType.STATE_CHANGE] = EventType.STATE_CHANGE


class InterturnEvent(Event):
    diff: DeepDiff
    event_type: Literal[EventType.INTERTURN] = EventType.INTERTURN


class MetaActionEvent(Event):
    old_context: ActionContext
    new_context: ActionContext
    event_type: Literal[EventType.META_ACTION] = EventType.META_ACTION


class CommitEvent(Event):
    diff: DeepDiff
    event_type: Literal[EventType.COMMIT] = EventType.COMMIT


class TurnCommitEvent(Event):
    diff: DeepDiff
    actor: PlayerColor
    event_type: Literal[EventType.TURN_COMMIT] = EventType.TURN_COMMIT


class InitialStateEvent(Event):
    state: BoardState
    event_type: Literal[EventType.INITIAL_STATE] = EventType.INITIAL_STATE
    
class EventBus:
    _subscribers: Dict[str, List[Callable[[Event], None]]]

    def __init__(self):
        self._subscribers = defaultdict(list)
        
    def subscribe(self, event_type:EventType, callback:Callable[[Event], None]):
        self._subscribers[event_type].append(callback)

    def publish(self, event:Event):
        if event.event_type in self._subscribers:
            for callback in self._subscribers[event.event_type]:
                callback(event)

