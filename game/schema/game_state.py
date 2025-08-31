from enum import StrEnum
from pydantic import BaseModel, Field, model_validator
from typing import List, Optional, Dict, Any, Callable, Union, Generator
from uuid import uuid4
from collections import deque
import math

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
    coal_count: int = Field(le=14)
    iron_count: int = Field(le=10)
    coal_cost: int
    iron_cost: int
    
    COAL_MAX_COST = 8
    IRON_MAX_COST = 6
    COAL_MAX_COUNT = 14
    IRON_MAX_COUNT = 10
    
    def update_market_costs(self):
        self.coal_cost = self.COAL_MAX_COST - math.ceil(self.coal_count / 2)
        self.iron_cost = self.IRON_MAX_COST - math.ceil(self.iron_count / 2)
    
    def _calculate_resource_cost(
        self, 
        resource_type: ResourceType, 
        amount: int
    ) -> int:
        """Общий метод для расчета стоимости ресурса без изменения состояния"""
        # Определяем параметры в зависимости от типа ресурса
        if resource_type == ResourceType.COAL:
            current_count = self.coal_count
            max_cost = self.COAL_MAX_COST
        elif resource_type == ResourceType.IRON:
            current_count = self.iron_count
            max_cost = self.IRON_MAX_COST
        else:
            raise ValueError("Market can only sell iron and coal")
        
        total_cost = 0
        temp_count = current_count
        
        for _ in range(amount):
            # Если ресурса нет, используем максимальную цену и не уменьшаем количество
            if temp_count <= 0:
                current_cost = max_cost
            else:
                # Рассчитываем текущую стоимость за единицу
                current_cost = max_cost - math.ceil(temp_count / 2)
                temp_count -= 1
                
            total_cost += current_cost
            
        return total_cost
    
    def calculate_coal_cost(self, amount: int) -> int:
        """Рассчитать стоимость указанного количества угля"""
        return self._calculate_resource_cost(ResourceType.COAL, amount)
    
    def calculate_iron_cost(self, amount: int) -> int:
        """Рассчитать стоимость указанного количества железа"""
        return self._calculate_resource_cost(ResourceType.IRON, amount)
    
    def purchase_resource(
        self, 
        resource_type: ResourceType, 
        amount: int
    ) -> int:
        """Купить указанное количество ресурса и обновить состояние рынка"""
        total_cost = self._calculate_resource_cost(resource_type, amount)
        
        if resource_type == "coal":
            # Уменьшаем количество только если оно больше 0
            if self.coal_count > 0:
                self.coal_count = max(0, self.coal_count - amount)
        else:
            # Уменьшаем количество только если оно больше 0
            if self.iron_count > 0:
                self.iron_count = max(0, self.iron_count - amount)
            
        self.update_market_costs()
        return total_cost


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

    def iter_placed_buildings(self) -> Generator[Building]:
        for city in self.cities.values():
            for slot in city.slots.values():
                if slot.building_placed:
                    yield slot.building_placed

    def get_player_iron_sources(self) -> Generator[Building]:
        for building in self.iter_placed_buildings():
            if building.industry_type == IndustryType.IRON and building.resource_count > 0:
                yield building

    def get_player_coal_locations(self, city_name: str) -> Dict[str, int]:
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

    def get_building_slot_location(self, building_slot_id:str) -> str:
        for city_name, city in self.cities.items():
            if building_slot_id in city.slots:
                return city_name

    def get_resource_amount_in_city(self, city_name:str, resource_type:ResourceType) -> int:
        out = 0
        for building_slot in self.cities[city_name].slots.values():
            if building_slot.building_placed:
                if building_slot.building_placed.IndustryType == resource_type:
                    out += building_slot.building_placed.resource_count
        return out
    

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