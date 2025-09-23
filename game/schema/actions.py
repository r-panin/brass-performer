from pydantic import BaseModel, Field, ConfigDict
from typing import Literal, List, Union, Optional
from collections import defaultdict
from .common import ActionType, ResourceSource, ResourceAmounts, ResourceType, IndustryType
from enum import StrEnum

'''
Meta classes
'''
class MetaAction(BaseModel):
    action: ActionType
    card_id: Optional[int] = None
    model_config = ConfigDict(extra='forbid')  

class ResourceAction(BaseModel):
    resources_used: Optional[List[ResourceSource]] = []

    def get_resource_amounts(self) -> ResourceAmounts:
        
        amounts = defaultdict(int)
        for resource in self.resources_used:
            amounts[resource.resource_type] += 1
        
        return ResourceAmounts(
            iron=amounts.get(ResourceType.IRON, 0),
            coal=amounts.get(ResourceType.COAL, 0),
            money=amounts.get("money", 0),
            beer=amounts.get(ResourceType.BEER, 0),
        )
    
class IndustryAction(BaseModel):
    industry: IndustryType

class SlotAction(BaseModel):
    slot_id: int

'''
Specific actions
'''

class BuildAction(MetaAction, ResourceAction, IndustryAction, SlotAction):
    action: Literal[ActionType.BUILD] = ActionType.BUILD
    card_id: int
    pass

class SellAction(MetaAction, ResourceAction, SlotAction):
    action: Literal[ActionType.SELL] = ActionType.SELL
    pass

class ScoutAction(MetaAction):
    action: Literal[ActionType.SCOUT] = ActionType.SCOUT
    card_id: List[int] = Field(min_length=3, max_length=3)

class DevelopAction(MetaAction, ResourceAction, IndustryAction):
    action: Literal[ActionType.DEVELOP] = ActionType.DEVELOP
    pass

class NetworkAction(MetaAction, ResourceAction):
    action: Literal[ActionType.NETWORK] = ActionType.NETWORK
    link_id: int

class LoanAction(MetaAction):
    action: Literal[ActionType.LOAN] = ActionType.LOAN
    card_id: int

class PassAction(MetaAction):
    action: Literal[ActionType.PASS] = ActionType.PASS
    card_id: int

class CommitAction(MetaAction):
    action: Literal[ActionType.COMMIT] = ActionType.COMMIT
    model_config = ConfigDict(extra='forbid')  

class ShortfallAction(MetaAction):
    action: Literal[ActionType.SHORTFALL] = ActionType.SHORTFALL
    slot_id: Optional[int] = None
    model_config = ConfigDict(extra='forbid')  

Action = Union[
    SellAction,
    BuildAction,
    ScoutAction,
    DevelopAction,
    NetworkAction,
    LoanAction,
    PassAction,
    CommitAction,
    ShortfallAction,
]

'''Requests'''

class RequestType(StrEnum):
    REQUEST_STATE = 'state'
    REQUEST_ACTIONS = 'actions'
    GOD_MODE = 'god_mode'

class Request(BaseModel):
    request: RequestType
