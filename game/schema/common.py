from enum import StrEnum
from pydantic import BaseModel, model_validator
from typing import Optional

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

class ResourceSource(BaseModel):
    resource_type: ResourceType
    building_slot_id: Optional[int] = None
    merchant_slot_id: Optional[int] = None

    @model_validator(mode='after')
    def validate_dependencies(self):

        if self.resource_type == ResourceType.BEER:
            if self.building_slot_id is None and self.merchant_slot_id is None:
                raise ValueError("Beer must be sourced from a building or from a merchant")

        if self.building_slot_id is not None and self.merchant_slot_id is not None:
            raise ValueError("May only provide either a building slot or a merchant slot, not both")

        if not self.building_slot_id is None and self.merchant_slot_id is None and self.resource_type is None:
            raise ValueError("Object may not be empty")
            
        return self

class ResourceAmounts(BaseModel):
    iron: int = 0
    coal: int = 0
    beer: int = 0
    money: int = 0

class IndustryType(StrEnum):
    COAL = "coal"
    IRON = "iron"
    BREWERY = "brewery"
    COTTON = "cotton"
    BOX = "box"
    POTTERY = "pottery"