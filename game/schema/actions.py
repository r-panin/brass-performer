from pydantic import BaseModel, Field
from enum import StrEnum
from typing import Literal, List, Union, Dict
from .game_state import Card, ResourceSource, AutoResourceSelection

class ActionType(StrEnum):
    BUILD = 'build'
    SELL = 'sell'
    SELL_STEP = 'sell_step'
    SELL_END = 'sell_end'
    LOAN = 'loan'
    SCOUT = 'scout'
    DEVELOP = 'develop'
    NETWORK = 'network'
    NETWORK_DOUBLE = 'network_double'
    NETWORK_END = 'network_end'
    PASS = 'pass'

class BaseAction(BaseModel):
    action_type: ActionType
    card_id: str 

class ResourceAction(BaseModel):
    action_type: ActionType
    resources_used: Union[List[ResourceSource], AutoResourceSelection]

    def is_auto_resource_selection(self):
        return isinstance(self.resources_used, AutoResourceSelection)

class BuildAction(BaseAction, ResourceAction):
    action_type: Literal[ActionType.BUILD] = ActionType.BUILD
    slot_id: str # building slot ID
    building_id: str # building ID

class SellAction(BaseAction, ResourceAction):
    action_type: Literal[ActionType.SELL] = ActionType.SELL
    building_id: str 

class SellStep(ResourceAction):
    action_type: Literal[ActionType.SELL_STEP] = ActionType.SELL_STEP
    building_id: str 

class SellEnd(BaseModel):
    action_type: Literal[ActionType.SELL_END] = ActionType.SELL_END

class LoanAction(BaseAction):
    action_type: Literal[ActionType.LOAN] = ActionType.LOAN

class ScoutAction(BaseAction):
    action_type: Literal[ActionType.SCOUT] = ActionType.SCOUT
    additional_card_cost: List[Card] = Field(min_length=2, max_length=2)

class DevelopAction(BaseAction, ResourceAction):
    action_type: Literal[ActionType.DEVELOP] = ActionType.DEVELOP
    buildings: List[str] = Field(min_length=1, max_length=2) # building ids

class NetworkAction(BaseAction, ResourceAction):
    action_type: Literal[ActionType.NETWORK] = ActionType.NETWORK
    link_id: str

class NetworkDouble(ResourceAction):
    action_type: Literal[ActionType.NETWORK_DOUBLE] = ActionType.NETWORK_DOUBLE
    link_id: str

class NetworkEnd(BaseModel):
    action_type: Literal[ActionType.NETWORK_END] = ActionType.NETWORK_END
    
class PassAction(BaseAction):
    action_type: Literal[ActionType.PASS] = ActionType.PASS

Action = Union[
    BuildAction, 
    SellAction, 
    LoanAction, 
    ScoutAction, 
    DevelopAction, 
    NetworkAction, 
    PassAction
]
