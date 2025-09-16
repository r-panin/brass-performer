from pydantic import BaseModel, Field, ConfigDict
from typing import Literal, List, Union, Optional
from collections import defaultdict
from .common import ActionType, ResourceSource, AutoResourceSelection, ResourceAmounts, ResourceType, IndustryType

'''
Meta classes
'''
class MetaAction(BaseModel):
    action: ActionType
    model_config = ConfigDict(extra='forbid')  

class ParameterAction(BaseModel):
    card_id: Optional[int] = None
    model_config = ConfigDict(extra='forbid')  

class ResourceAction(BaseModel):
    resources_used: Optional[Union[List[ResourceSource], AutoResourceSelection]] = []

    def is_auto_resource_selection(self):
        return isinstance(self.resources_used, AutoResourceSelection)

    def get_resource_amounts(self) -> ResourceAmounts:
        if self.resources_used is AutoResourceSelection:
            raise ValueError("Can't normalize resources before assigning them")
        
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
Action init classes
'''
class BuildStart(MetaAction):
    action: Literal[ActionType.BUILD] = ActionType.BUILD

class SellStart(MetaAction):
    action: Literal[ActionType.SELL] = ActionType.SELL
    
class LoanStart(MetaAction):
    action: Literal[ActionType.LOAN] = ActionType.LOAN

class ScoutStart(MetaAction):
    action: Literal[ActionType.SCOUT] = ActionType.SCOUT

class DevelopStart(MetaAction):
    action: Literal[ActionType.DEVELOP] = ActionType.DEVELOP

class NetworkStart(MetaAction):
    action: Literal[ActionType.NETWORK] = ActionType.NETWORK

class PassStart(MetaAction):
    action: Literal[ActionType.PASS] = ActionType.PASS

'''
Specific action selections
'''
class BuildSelection(ParameterAction, ResourceAction, IndustryAction, SlotAction):
    pass

class SellSelection(ParameterAction, ResourceAction, SlotAction):
    pass

class ScoutSelection(ParameterAction):
    additional_card_cost: List[int] = Field(min_length=2, max_length=2) # card ids

class DevelopSelection(ParameterAction, ResourceAction, IndustryAction):
    pass

class NetworkSelection(ParameterAction, ResourceAction):
    link_id: int

'''
This ends the pain
'''

class CommitAction(BaseModel):
    commit: bool
    model_config = ConfigDict(extra='forbid')  

class EndOfTurnAction(BaseModel):
    end_turn: bool
    model_config = ConfigDict(extra='forbid')  

class ResolveShortfallAction(BaseModel):
    resolve: bool
    slot_id: int

MetaActions = Union[
    LoanStart,
    PassStart,
    SellStart,
    BuildStart,
    ScoutStart,
    DevelopStart,
    NetworkStart,
]

Action = Union[
    LoanStart,
    PassStart,
    SellStart,
    BuildStart,
    ScoutStart,
    DevelopStart,
    NetworkStart,
    SellSelection,
    BuildSelection,
    ScoutSelection,
    DevelopSelection,
    NetworkSelection,
    CommitAction
]
