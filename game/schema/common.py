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
    building_slot_id: Optional[int]
    merchant_slot_id: Optional[int] 
    amount: int

    @model_validator(mode='after')
    @classmethod
    def validate_dependencies(cls, values):
        source_type = values.get('source_type')
        resource_type = values.get('resource_type')
        building_slot_id = values.get('building_slot_id')
        merchant_slot_id = values.get('merchant_slot_id')

        if resource_type == ResourceType.MONEY:
            if source_type != ResourceSourceType.PLAYER:
                raise ValueError('Money must come from player')
            if building_slot_id is not None:
                raise ValueError('Money cannot have building_slot_id')
            if merchant_slot_id is not None:
                raise ValueError('Money cannot have merchant')

        elif resource_type == ResourceType.IRON or resource_type == ResourceType.COAL:
            if source_type == ResourceSourceType.MERCHANT:
                raise ValueError(f'{resource_type} cannot be sourced from merchant')
            
        elif resource_type == ResourceType.BEER:
            if source_type == ResourceSourceType.MARKET:
                raise ValueError(f"Beer cannot come from market")
            
        if merchant_slot_id is not None and source_type != ResourceSourceType.MERCHANT:
            raise ValueError('Merchant field requires merchant source type')
        
        if merchant_slot_id is None and source_type is ResourceSourceType.MERCHANT:
            raise ValueError("Must specify merchant")
        
        if source_type == ResourceSourceType.PLAYER and building_slot_id is None and resource_type is not ResourceType.MONEY:
            raise ValueError(f'Must specify sourcing building')
        
        return values
        


        

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