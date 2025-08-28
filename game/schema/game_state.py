from enum import StrEnum
from pydantic import BaseModel, Field, model_validator
from typing import List, Optional, Dict, Any
from uuid import uuid4

class GameStatus(StrEnum):
    CREATED = 'created'
    ONGOING = 'ongoing'
    COMPLETE = 'complete'

class IndustryType(StrEnum):
    COAL = "coal"
    IRON = "iron"
    BREWERY = "brewery"
    COTTON = "cotton"
    BOX = "box"
    POTTERY = "pottery"

class PlayerColor(StrEnum):
    WHITE = "white"
    PURPLE = "purple"
    YELLOW = "yellow"
    RED = "red"

class MerchantType(StrEnum):
    ANY = "any"
    BOX = "box"
    POTTERY = "pottery"
    COTTON = "cotton"
    EMPTY = "empty"

class MerchantSlot(BaseModel):
    id: str = Field(default_factory=lambda: (str(uuid4())))
    city: str
    merchant_type: MerchantType
    beer_available: bool = True 

class Building(BaseModel):
    id: str = Field(default_factory=lambda: (str(uuid4())))
    industry_type: IndustryType
    level: int
    city: str
    owner: PlayerColor
    flipped: bool
    cost: Dict[str, int]
    resource_count: Optional[int] = None
    victory_points: int
    cost: Dict[str, int]
    sell_cost: Optional[int]
    is_developable: bool
    link_victory_points: int

class BuildingSlot(BaseModel):
    id: str = Field(default_factory=lambda: (str(uuid4())))
    city: str
    industry_type_options: List[IndustryType]
    building_placed: Optional[Building] = None

class LinkType(StrEnum):
    CANAL = "canal"
    RAIL = "rail"

class Link(BaseModel):
    id: str = Field(default_factory=lambda: (str(uuid4())))
    type: LinkType
    cities: List[str]
    owner: Optional[str] = None

class City(BaseModel):
    name: str
    slots: List[BuildingSlot] = []
    links: List[Link]
    is_merchant: bool
    merchant_slots: Optional[List[MerchantSlot]] = None
    merchant_min_players: Optional[int] = None

class Market(BaseModel):
    coal_count: int
    iron_count: int
    coal_cost: int
    iron_cost: int

class CardType(StrEnum):
    INDUSTRY = "industry"
    CITY = "city"

class Card(BaseModel):
    id: str = Field(default_factory=lambda: (str(uuid4())))
    card_type: CardType
    value: str
    def __repr__(self) -> str:
        return f'Card value: {self.value}'

    @model_validator(mode="before")
    @classmethod
    def set_type_and_value(cls, data:Any) -> Any:
        if isinstance(data, dict):
            if "city" in data:
                data["card_type"] = CardType.CITY
                data["value"] = data["city"]
            elif "industry" in data:
                data["card_type"] = CardType.INDUSTRY
                data["value"] = data["industry"]
            else:
                raise ValueError('Card must have either "city" or "industry" field')
            return data

class PlayerExposed(BaseModel):
    hand_size: int
    available_buildings: list[Building]
    color: PlayerColor
    bank: int
    income: int
    income_points: int
    victory_points: int

class Player(BaseModel):
    hand: list[Card]
    available_buildings: list[Building]
    color: PlayerColor
    bank: int
    income: int
    income_points: int
    victory_points: int

    def hide_hand(self) -> PlayerExposed:
        data = self.model_dump()
        data["hand_size"] = len(self.hand)
        del data["hand"]
        return PlayerExposed(**data)


class BoardStateExposed(BaseModel):
    cities: List[City]
    players: List[PlayerExposed]
    market: Market
    deck_size: int
    era: LinkType

class BoardState(BaseModel):
    cities: List[City]
    players: List[Player]
    market: Market
    deck: List[Card]
    era: LinkType

    def hide_state(self) -> BoardStateExposed:
        data = self.model_dump()
        data["players"] = [player.hide_hand() for player in self.players]
        data["deck_size"] = len(self.deck)
        del data["deck"]
        return BoardStateExposed(**data)

class ResourceType(StrEnum):
    COAL = "coal"
    IRON = "iron"
    BEER = "beer"

class ResourceSourceType(StrEnum):
    PLAYER = "player"
    MARKET = "market"
    MERCHANT = "merchant" # Beer

class ResourceSource(BaseModel):
    source_type: ResourceSourceType
    building_slot_id: Optional[str]

class ResourceSelection(BaseModel):
    resources_used: List[ResourceSource]
    additional_cost: int

class PlayerState(BaseModel):
    common_state: BoardStateExposed
    your_hand: List[Card]
    your_color: PlayerColor