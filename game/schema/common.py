from enum import StrEnum
from pydantic import BaseModel
from typing import Optional, Literal

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

class ResourceType(StrEnum):
    COAL = "coal"
    IRON = "iron"
    BEER = "beer"
    MONEY = "money"

class ResourceSourceType(StrEnum):
    PLAYER = "player"
    MARKET = "market"
    MERCHANT = "merchant" # Beer

class ResourceSource(BaseModel):
    source_type: ResourceSourceType
    resource_type: ResourceType
    building_slot_id: Optional[int]
    merchant: Optional[str] # city name
    amount: int

class ResourceAmounts(BaseModel):
    iron: int = 0
    coal: int = 0
    beer: int = 0
    money: int = 0

class ResourceStrategy(StrEnum):
    OWN_FIRST = 'own_first'
    MERCHANT_FIRST = 'merchant_first'
    ENEMY_FIRST = 'enemy_first'

class AutoResourceSelection(BaseModel):
    mode: Literal["auto"]
    strategy: ResourceStrategy