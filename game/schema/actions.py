from pydantic import BaseModel, Field
from enum import StrEnum
from typing import Literal, List, Union
from .game_state import Card, ResourceSelection

class ActionType(StrEnum):
    BUILD = 'build'
    SELL = 'sell'
    LOAN = 'loan'
    SCOUT = 'scout'
    DEVELOP = 'develop'
    NETWORK = 'network'
    PASS = 'pass'

class BaseAction(BaseModel):
    action_type: ActionType
    card_id: str 

class BuildAction(BaseAction):
    action_type: Literal[ActionType.BUILD] = ActionType.BUILD
    slot_id: str # building slot ID
    building_id: str # building ID
    resources_used: ResourceSelection 

class SellAction(BaseAction):
    action_type: Literal[ActionType.SELL] = ActionType.SELL
    building_ids: List[str]
    beer_used: ResourceSelection

class LoanAction(BaseAction):
    action_type: Literal[ActionType.LOAN] = ActionType.LOAN

class ScoutAction(BaseAction):
    action_type: Literal[ActionType.SCOUT] = ActionType.SCOUT
    additional_card_cost: List[Card] = Field(min_length=2, max_length=2)

class DevelopAction(BaseAction):
    action_type: Literal[ActionType.SCOUT] = ActionType.SCOUT
    buildings: List[str] = Field(min_length=1, max_length=2) # building ids

class NetworkAction(BaseAction):
    action_type: Literal[ActionType.NETWORK] = ActionType.NETWORK
    link_id: str

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
