from pydantic import BaseModel, Field
from typing import Literal, List, Union
from collections import defaultdict
from .common import ActionType, ResourceSource, AutoResourceSelection, ResourceAmounts, ResourceType, IndustryType

'''
Meta classes
'''
class MetaAction(BaseModel):
    action_type: ActionType

class ParameterAction(BaseModel):
    card_id: int

class IterativeAction(ParameterAction):
    card_id: int | None = Field(default=None, exclude=True)
    counter: int = 1

class ResourceAction(BaseModel):
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
    
class IndustryAction(BaseModel):
    industry = IndustryType

class SlotAction(BaseModel):
    slot_id: int

'''
Action init classes
'''
class BuildStart(MetaAction):
    action_type: Literal[ActionType.BUILD] = ActionType.BUILD

class SellStart(MetaAction):
    action_type: Literal[ActionType.SELL] = ActionType.SELL
    
class LoanStart(MetaAction):
    action_type: Literal[ActionType.LOAN] = ActionType.LOAN

class ScoutStart(MetaAction):
    action_type: Literal[ActionType.SCOUT] = ActionType.SCOUT

class DevelopStart(MetaAction):
    action_type: Literal[ActionType.DEVELOP] = ActionType.DEVELOP

class NetworkStart(MetaAction):
    action_type: Literal[ActionType.NETWORK] = ActionType.NETWORK

class PassStart(MetaAction):
    action_type: Literal[ActionType.PASS] = ActionType.PASS

'''
Specific action selections
'''
class BuildSelection(ParameterAction, ResourceAction, IndustryAction, SlotAction):
    pass

class SellSelection(ParameterAction, ResourceAction, SlotAction):
    pass

class SellIteration(IterativeAction, ResourceAction, SlotAction):
    pass

class ScoutSelection(ParameterAction):
    additional_card_cost: List[int] = Field(min_length=2, max_length=2) # card ids

class DevelopSelection(ParameterAction, ResourceAction, IndustryAction):
    pass

class DevelopIteration(IterativeAction, ResourceAction, IndustryAction):
    pass

class NetworkSelection(ParameterAction, ResourceAction):
    link_id: int

class NetworkIteration(IterativeAction, ResourceAction):
    link_id: int

class LoanSelection(ParameterAction):
    pass

class PassSelection(ParameterAction):
    pass

'''
This ends the pain
'''

class CommitAction(BaseModel):
    commit: bool

MetaActions = Union[
    LoanStart,
    PassStart,
    SellStart,
    BuildStart,
    ScoutStart,
    DevelopStart,
    NetworkStart
]

ParameterActions = Union[
    LoanSelection,
    PassSelection,
    SellSelection,
    SellIteration,
    BuildSelection,
    ScoutSelection,
    DevelopSelection,
    DevelopIteration,
    NetworkSelection,
    NetworkIteration
]
