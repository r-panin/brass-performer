from .event_bus import EventType, EventBus, Event
from typing import List, Dict
from abc import ABC, abstractmethod
from pathlib import Path
import json

class ReplayService:
    def __init__(self, event_bus:EventBus):
        self._generators:Dict[str, ReplayGenerator] = {
            "raw": RawReplayGenerator(),
            "turnwise": TurnwiseReplayGenerator()
        }
        self._recorder = ReplayRecorder()
        for event_type in EventType:
            event_bus.subscribe(event_type, self._recorder.add_event)

    def save_replay(self, filename: Path, replay_type: str = 'raw'):
        events = self._recorder.get_events()
        generator = self._generators.get(replay_type)
        if not generator:
            raise ValueError(f"Unknown replay type {replay_type}")

        replay_data = generator.generate(events)

        with open(filename, 'w') as outfile:
            json.dump(replay_data, outfile, indent=2)

        return replay_data


class ReplayRecorder:
    def __init__(self):
        self.events:List[Event] = []

    def add_event(self, event:Event):
        self.events.append(event)

    def get_events(self) -> List[Event]:
        return self.events.copy()
    
class ReplayGenerator(ABC):
    @abstractmethod
    def generate(self, events) -> List[Event]:
        pass

class RawReplayGenerator(ReplayGenerator):
    def generate(self, events):
        return events
    
class TurnwiseReplayGenerator(ReplayGenerator):
    def generate(self, events:List[Event]):
        return [event for event in events if event.event_type in (EventType.INITIAL_STATE, EventType.TURN_COMMIT, EventType.INTERTURN)]