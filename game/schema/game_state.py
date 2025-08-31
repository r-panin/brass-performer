from enum import StrEnum
from pydantic import BaseModel, Field, model_validator
from typing import List, Optional, Dict, Any, Callable, Union, Set
from uuid import uuid4
from collections import deque

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

class LinkType(StrEnum):
    CANAL = "canal"
    RAIL = "rail"
    
class ResourceType(StrEnum):
    COAL = "coal"
    IRON = "iron"
    BEER = "beer"
    MONEY = "money"

class Building(BaseModel):
    id: str = Field(default_factory=lambda: (str(uuid4())))
    industry_type: IndustryType
    level: int
    city: str
    owner: PlayerColor
    flipped: bool
    cost: Dict[ResourceType, int]
    resource_count: int
    victory_points: int
    cost: Dict[str, int]
    sell_cost: Optional[int]
    is_developable: bool
    link_victory_points: int
    era_exclusion: Optional[LinkType]

class BuildingSlot(BaseModel):
    id: str = Field(default_factory=lambda: (str(uuid4())))
    city: str
    industry_type_options: List[IndustryType]
    building_placed: Optional[Building] = None

class Link(BaseModel):
    id: str = Field(default_factory=lambda: (str(uuid4())))
    type: LinkType
    cities: List[str]
    owner: Optional[str] = None

class City(BaseModel):
    name: str
    slots: Dict[str, BuildingSlot] = []
    links: Dict[str, Link]
    is_merchant: bool
    merchant_slots: Optional[Dict[str, MerchantSlot]] = None
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
    available_buildings: Dict[str, Building]
    color: PlayerColor
    bank: int
    income: int
    income_points: int
    victory_points: int

class Player(BaseModel):
    hand: Dict[str, Card]
    available_buildings: Dict[str, Building]
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
    cities: Dict[str, City]
    players: Dict[PlayerColor, PlayerExposed]
    market: Market
    deck_size: int
    era: LinkType
    current_turn: PlayerColor
    actions_left: int = Field(ge=0, le=2)

class BoardState(BaseModel):
    cities: Dict[str, City]
    players: Dict[PlayerColor, Player]
    market: Market
    deck: List[Card]
    era: LinkType
    current_turn: PlayerColor
    actions_left: int = Field(ge=0, le=2)
    discard: List[Card]

    def hide_state(self) -> BoardStateExposed:
        data = self.model_dump()
        data["players"] = {color: player.hide_hand() for color, player in self.players.items()}
        data["deck_size"] = len(self.deck)
        del data["deck"]
        return BoardStateExposed(**data)

    def iter_placed_buildings(self):
        for city in self.cities.values():
            for slot in city.slots.values():
                if slot.building_placed:
                    yield slot.building_placed

    def get_player_iron_sources(self):
        for building in self.iter_placed_buildings():
            if building.industry_type == IndustryType.IRON and building.resource_count > 0:
                yield building

    def get_player_coal_sources(self, city_name: str):
        return self.find_paths(self, city_name, target_condition=lambda city: any(
            slot.building_placed is not None and
            slot.building_placed.industry_type == IndustryType.COAL and
            slot.building_placed.resource_count > 0
            for slot in self.cities[city].slots.values
        ),
        find_all=True)

    def market_access_exists(self, city_name: str):
        return self.find_paths(self, city_name, target_condition=lambda city: self.cities[city].is_merchant)

    def find_paths(self, start:str, target_condition: Optional[Callable[[str], bool]] = None, end:Optional[str]=None, find_all:bool = False) -> Union[bool, Dict[str, int]]:
        if start not in self.cities:
            if find_all:
                return {}
            return False
        
        if end is not None:
            target_check = lambda city: city == end
        elif target_condition is not None:
            target_check = target_condition
        else:
            raise ValueError("Must have either target city or condition")
        
        if not find_all and target_check(start):
            return True
        
        visited = set()
        queue = deque([(start, 0)])
        visited.add(start)
        found_cities = {}
        if find_all and target_check(start):
            found_cities[start] = 0

        while queue:
            current_city_name, distance = queue.popleft()
            
            for link in self.cities[current_city_name].links.values():
                if link.owner is None:
                    continue
                for connected_city in link.cities:
                    if connected_city not in visited:
                        visited.add(connected_city)
                        new_distance = distance + 1

                        if target_check(connected_city):
                            if not find_all:
                                return True
                            found_cities[connected_city] = new_distance
                        queue.append((connected_city, new_distance))
        
        if find_all:
            return found_cities
        return False
    

class ResourceSourceType(StrEnum):
    PLAYER = "player"
    MARKET = "market"
    MERCHANT = "merchant" # Beer

class ResourceSource(BaseModel):
    source_type: ResourceSourceType
    resource_type: ResourceType
    building_slot_id: Optional[str]
    merchant: Optional[City] # beer only
    amount: int

class PlayerState(BaseModel):
    common_state: BoardStateExposed
    your_hand: Dict[str, Card]
    your_color: PlayerColor

class ValidationResult(BaseModel):
    is_valid: bool
    message: Optional[str]

class ExecutionResult(BaseModel):
    executed: bool
    message: Optional[str]