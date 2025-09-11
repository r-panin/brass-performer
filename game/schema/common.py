from enum import StrEnum
from pydantic import BaseModel, model_validator
from typing import Optional, Literal

class ActionType(StrEnum):
    BUILD = 'build'
    SELL = 'sell'
    LOAN = 'loan'
    SCOUT = 'scout'
    DEVELOP = 'develop'
    NETWORK = 'network'
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
    building_slot_id: Optional[int] = None
    merchant_slot_id: Optional[int] = None
    amount: int

    @model_validator(mode='after')
    def validate_dependencies(self):

        if self.resource_type == ResourceType.MONEY:
            if self.source_type != ResourceSourceType.PLAYER:
                raise ValueError('Money must come from player')
            if self.building_slot_id is not None:
                raise ValueError('Money cannot have building_slot_id')
            if self.merchant_slot_id is not None:
                raise ValueError('Money cannot have merchant')

        elif self.resource_type == ResourceType.IRON or self.resource_type == ResourceType.COAL:
            if self.source_type == ResourceSourceType.MERCHANT:
                raise ValueError(f'{self.resource_type} cannot be sourced from merchant')
            
        elif self.resource_type == ResourceType.BEER:
            if self.source_type == ResourceSourceType.MARKET:
                raise ValueError(f"Beer cannot come from market")
            
        if self.merchant_slot_id is not None and self.source_type != ResourceSourceType.MERCHANT:
            raise ValueError('Merchant field requires merchant source type')
        
        if self.merchant_slot_id is None and self.source_type is ResourceSourceType.MERCHANT:
            raise ValueError("Must specify merchant")
        
        if self.source_type == ResourceSourceType.PLAYER and self.building_slot_id is None and self.resource_type is not ResourceType.MONEY:
            raise ValueError(f'Must specify sourcing building')
        
        return self
        


        

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

class IndustryType(StrEnum):
    COAL = "coal"
    IRON = "iron"
    BREWERY = "brewery"
    COTTON = "cotton"
    BOX = "box"
    POTTERY = "pottery"