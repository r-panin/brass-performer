from typing import Dict, List, Callable, Literal
from collections import defaultdict
from datetime import datetime
from dataclasses import dataclass
from enum import StrEnum
from ....schema import PlayerColor, ActionContext
from deepdiff import DeepDiff

class EventType(StrEnum):
    META_ACTION = 'meta_action'
    STATE_CHANGE = 'state_change'
    INTERTURN = 'interturn'
    COMMIT = 'commit'
    TURN_COMMIT = 'turn_commit'
    VALIDATION_FAIL = 'validation_fail'

@dataclass
class Event:
    event_type: EventType
    timestamp: float = None

    def __post_init__(self):
        if self.timestamp is None:
            self.timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

@dataclass
class ValidationEvent(Event):
    event_type = Literal[EventType.VALIDATION_FAIL] = EventType.VALIDATION_FAIL
    reason: str
    actor: str

@dataclass
class StateChangeEvent(Event):
    event_type = Literal[EventType.STATE_CHANGE] = EventType.STATE_CHANGE
    diff: DeepDiff
    actor: PlayerColor

@dataclass
class InterturnEvent(Event):
    event_type = Literal[EventType.INTERTURN] = EventType.INTERTURN
    diff: DeepDiff

@dataclass
class MetaActionEvent(Event):
    event_type = Literal[EventType.META_ACTION] = EventType.META_ACTION
    old_context: ActionContext
    new_context: ActionContext

@dataclass
class CommitEvent(Event):
    event_type = Literal[EventType.COMMIT] = EventType.COMMIT
    diff: DeepDiff

@dataclass
class TurnCommitEvent(Event):
    event_type = Literal[EventType.TURN_COMMIT] = EventType.TURN_COMMIT
    diff: DeepDiff
    actor: PlayerColor
    
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

