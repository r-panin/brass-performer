from pydantic import BaseModel, Field
from enum import StrEnum
from typing import Literal, List, Union, Dict
from .game_state import ResourceSource, AutoResourceSelection, ResourceAmounts, ResourceType
from collections import defaultdict

class ActionType(StrEnum):
    BUILD = 'build'
    SELL = 'sell'
    SELL_STEP = 'sell_step'
    SELL_END = 'sell_end'
    LOAN = 'loan'
    SCOUT = 'scout'
    DEVELOP = 'develop'
    DEVELOP_DOUBLE = 'develop_double'
    DEVELOP_END = 'develop_end'
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

    def get_resource_amounts(self) -> ResourceAmounts:
        if self.resources_used is AutoResourceSelection:
            raise ValueError("Can't normalize resources before assigning them")
        
        amounts = defaultdict(int)
        for resource in self.resources_used:
            amounts[resource.resource_type] += resource.amount
        
        return ResourceAmounts(
            iron=amounts.get(ResourceType.IRON, 0),
            coal=amounts.get(ResourceType.COAL, 0),
            money=amounts.get(ResourceType.MONEY, 0),
            beer=amounts.get(ResourceType.BEER, 0),
        )
    
class BuildingAction(BaseModel):
    building_id: int

class BuildAction(BaseAction, ResourceAction, BuildingAction):
    action_type: Literal[ActionType.BUILD] = ActionType.BUILD
    slot_id: int # building slot ID
    
class SellAction(BaseAction, ResourceAction, BuildingAction):
    action_type: Literal[ActionType.SELL] = ActionType.SELL

class SellStep(ResourceAction, BuildingAction):
    action_type: Literal[ActionType.SELL_STEP] = ActionType.SELL_STEP

class SellEnd(BaseModel):
    action_type: Literal[ActionType.SELL_END] = ActionType.SELL_END

class LoanAction(BaseAction):
    action_type: Literal[ActionType.LOAN] = ActionType.LOAN

class ScoutAction(BaseAction):
    action_type: Literal[ActionType.SCOUT] = ActionType.SCOUT
    additional_card_cost: List[int] = Field(min_length=2, max_length=2) # card ids

class DevelopAction(BaseAction, ResourceAction, BuildingAction):
    action_type: Literal[ActionType.DEVELOP] = ActionType.DEVELOP

class DevelopDouble(ResourceAction, BuildingAction):
    action_type: Literal[ActionType.DEVELOP_DOUBLE] = ActionType.DEVELOP_DOUBLE

class DevelopEnd(BaseModel):
    action_type: Literal[ActionType.DEVELOP_END] = ActionType.DEVELOP_END

class NetworkAction(BaseAction, ResourceAction):
    action_type: Literal[ActionType.NETWORK] = ActionType.NETWORK
    link_id: int

class NetworkDouble(ResourceAction):
    action_type: Literal[ActionType.NETWORK_DOUBLE] = ActionType.NETWORK_DOUBLE
    link_id: int

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
    PassAction,
    SellStep,
    SellEnd,
    NetworkDouble,
    NetworkEnd,
    DevelopDouble,
    DevelopEnd
]
