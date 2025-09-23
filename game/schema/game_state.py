from enum import StrEnum
from pydantic import BaseModel, Field, model_validator
from typing import List, Optional, Dict, Callable, Union, Iterator, ClassVar, Set, Any
from collections import deque
import math
import json
import hashlib
from .common import IndustryType, ResourceType, ResourceAmounts
import logging
import random
from functools import lru_cache


class GameEntity(BaseModel):
    _excluded_from_hash: ClassVar[Set[str]] = {'type_hash', 'id'}
    type_hash: str = Field(default=None, description='Auto-generated property hash, used for equivalence layer')

    def __init__(self, **data):
        super().__init__(**data)
        self.type_hash = self._generate_hash()

    def _generate_hash(self) -> str:
        exclude_fields = self._excluded_from_hash
        model_dict = self.model_dump(exclude=exclude_fields)

        serialized = json.dumps(model_dict, sort_keys=True, default=str)
        return hashlib.md5(serialized.encode()).hexdigest()

class ActionContext(StrEnum):
    GLOUCESTER_DEVELOP = 'gloucester_develop'
    SHORTFALL = 'shortfall'
    MAIN = 'main'
    SELL = 'sell'
    NETWORK = 'network'
    DEVELOP = 'develop'

class GameStatus(StrEnum):
    CREATED = 'created'
    ONGOING = 'ongoing'
    COMPLETE = 'complete'

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

class MerchantSlot(GameEntity):
    id: int
    city: str
    merchant_type: MerchantType
    beer_available: bool = True 
    
    def buys(self) -> List[IndustryType]:
        out = set()
        if self.merchant_type is MerchantType.ANY:
            out.add(IndustryType.BOX)
            out.add(IndustryType.COTTON)
            out.add(IndustryType.POTTERY)
        elif self.merchant_type is MerchantType.POTTERY:
            out.add(IndustryType.POTTERY)
        elif self.merchant_type is MerchantType.BOX:
            out.add(IndustryType.BOX)
        elif self.merchant_type is MerchantType.COTTON:
            out.add(IndustryType.COTTON)
        return list(out)

class LinkType(StrEnum):
    CANAL = "canal"
    RAIL = "rail"
    
class Building(GameEntity):
    id: int
    industry_type: IndustryType
    level: int
    owner: PlayerColor
    flipped: bool
    cost: Dict[ResourceType, int]
    resource_count: int = Field(ge=0)
    victory_points: int
    cost: Dict[str, int]
    sell_cost: Optional[int]
    is_developable: bool
    link_victory_points: int
    era_exclusion: Optional[LinkType]
    income: int
    slot_id: Optional[int] = None

    def get_cost(self) -> ResourceAmounts:
        return ResourceAmounts(
            iron=self.cost[ResourceType.IRON],
            coal=self.cost[ResourceType.COAL],
            money=self.cost.get("money", 0)
        )

    def is_sellable(self) -> bool:
        if self.industry_type in (IndustryType.BOX, IndustryType.COTTON, IndustryType.POTTERY):
            return True
        return False


class BuildingSlot(GameEntity):
    id: int
    city: str
    industry_type_options: List[IndustryType]
    building_placed: Optional[Building] = None

class Link(GameEntity):
    id:int
    type: List[LinkType]
    cities: List[str]
    owner: Optional[str] = None

class City(GameEntity):
    name: str
    slots: Dict[int, BuildingSlot] = []
    is_merchant: bool
    merchant_slots: Optional[Dict[int, MerchantSlot]] = None
    merchant_min_players: Optional[int] = None

    def get_link_vps(self):
        out = 0
        for slot in self.slots.values():
            if slot.building_placed is not None:
                building = slot.building_placed
                if building.flipped:
                    out += building.victory_points
        return out


class Market(BaseModel):
    coal_count: int = Field(le=14)
    iron_count: int = Field(le=10)
    coal_cost: int
    iron_cost: int
    
    COAL_MAX_COST:ClassVar[int] = 8
    IRON_MAX_COST:ClassVar[int] = 6
    COAL_MAX_COUNT:ClassVar[int] = 14
    IRON_MAX_COUNT:ClassVar[int] = 10
    
    def update_market_costs(self):
        self.coal_cost = self.COAL_MAX_COST - math.ceil(self.coal_count / 2)
        self.iron_cost = self.IRON_MAX_COST - math.ceil(self.iron_count / 2)

    def sellable_amount(self, resource_type:ResourceType):
        if resource_type is ResourceType.IRON:
            return self.IRON_MAX_COUNT - self.iron_count
        elif resource_type is ResourceType.COAL:
            return self.COAL_MAX_COST - self.coal_count
    
    def _calculate_resource_cost(
        self, 
        resource_type: ResourceType, 
        amount: int
    ) -> int:
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
            if temp_count <= 0:
                current_cost = max_cost
            else:
                current_cost = max_cost - math.ceil(temp_count / 2)
                temp_count -= 1
                
            total_cost += current_cost
            
        return total_cost
    
    def calculate_coal_cost(self, amount: int) -> int:
        return self._calculate_resource_cost(ResourceType.COAL, amount)
    
    def calculate_iron_cost(self, amount: int) -> int:
        return self._calculate_resource_cost(ResourceType.IRON, amount)
    
    def purchase_resource(
        self, 
        resource_type: ResourceType, 
        amount: int
    ) -> int:
        total_cost = self._calculate_resource_cost(resource_type, amount)
        
        if resource_type == ResourceType.COAL:
            self.coal_count = max(0, self.coal_count - amount)
        elif resource_type == ResourceType.IRON:
            self.iron_count = max(0, self.iron_count - amount)
            
        self.update_market_costs()
        return total_cost
    

    def _calculate_resource_sale_price(
        self, 
        resource_type: ResourceType, 
        amount: int
    ) -> int:
        if resource_type == ResourceType.COAL:
            current_count = self.coal_count
            max_cost = self.COAL_MAX_COST
            max_count = self.COAL_MAX_COUNT
        elif resource_type == ResourceType.IRON:
            current_count = self.iron_count
            max_cost = self.IRON_MAX_COST
            max_count = self.IRON_MAX_COUNT
        else:
            raise ValueError("Market can only buy iron and coal")
        
        total_revenue = 0
        temp_count = current_count
        
        for _ in range(amount):
            if current_count >= max_count:
                break
            # Цена уменьшается по мере увеличения количества на рынке
            current_price = max_cost - math.ceil((temp_count + 1) / 2)
            current_price = max(0, current_price)  # Не может быть отрицательной
            total_revenue += current_price
            temp_count += 1  # Увеличиваем количество после продажи
            
        return total_revenue

    def sell_resource(
        self, 
        resource_type: ResourceType, 
        amount: int
    ) -> int:
        total_revenue = self._calculate_resource_sale_price(resource_type, amount)
        
        if resource_type == ResourceType.COAL:
            self.coal_count += amount
        elif resource_type == ResourceType.IRON:
            self.iron_count += amount
            
        self.update_market_costs()
        return total_revenue


class CardType(StrEnum):
    INDUSTRY = "industry"
    CITY = "city"

class Card(GameEntity):
    id: int
    card_type: CardType
    value: str
    def __repr__(self) -> str:
        return f'Card value: {self.value}'

class PlayerExposed(BaseModel):
    hand_size: int
    available_buildings: Dict[int, Building]
    color: PlayerColor
    bank: int
    income: int
    income_points: int
    victory_points: int
    money_spent: int = 0

class Player(BaseModel):
    hand: Dict[int, Card]
    available_buildings: Dict[int, Building]
    color: PlayerColor
    bank: int 
    income: int = Field(ge=-10)
    income_points: int = Field(ge=-10)
    victory_points: int
    money_spent: int = 0

    def hide_hand(self) -> PlayerExposed:
        data = self.model_dump()
        data["hand_size"] = len(self.hand)
        del data["hand"]
        return PlayerExposed(**data)

    def recalculate_income(self, keep_points=True):
        if keep_points:
            if self.income_points <= 10:
                self.income = self.income_points - 10
            elif self.income_points <= 30:
                self.income = (self.income_points - 10) // 2
            elif self.income_points <= 60:
                self.income = (10 + self.income_points - 30) // 3
            else:
                self.income = (20 + self.income_points - 60) // 4
        else:
            if self.income <= 0:
                self.income_points = self.income + 10
            elif self.income <= 10:
                self.income_points = 2 * self.income + 10
            elif self.income <= 20:
                self.income_points = 3 * self.income
            else:
                self.income_points = 3 * self.income + (self.income % 10)

    def get_lowest_level_building(self, industry:IndustryType):
            return min(
                            (b for b in self.available_buildings.values() if b.industry_type is industry),
                            key=lambda x: x.level,
                            default=None
                            )


class BoardStateExposed(BaseModel):
    cities: Dict[str, City]
    links: Dict[int, Link]
    players: Dict[PlayerColor, PlayerExposed]
    market: Market
    deck_size: int
    era: LinkType
    turn_order: List[PlayerColor]
    actions_left: int = Field(ge=0, le=2)
    discard: List[Card]
    wilds: List[Card]
    subaction_count: int = Field(default=0, exclude=True)
    gloucester_develop: bool = Field(default=False, exclude=True)
    action_context: ActionContext


class BoardState(BaseModel):
    cities: Dict[str, City]
    links: Dict[int, Link]
    players: Dict[PlayerColor, Player]
    market: Market
    deck: List[Card]
    era: LinkType
    turn_order: List[PlayerColor]
    actions_left: int = Field(ge=0, le=2)
    discard: List[Card]
    wilds: List[Card]
    subaction_count: int = Field(default=0, exclude=True)
    gloucester_develop: bool = Field(default=False, exclude=True)
    action_context: ActionContext

    @classmethod
    def determine(
        cls,
        exposed_state: BoardStateExposed,
        player_hands: Dict[PlayerColor, Dict[int, Card]],
        deck: List[Card]
    ) -> "BoardState":
        # Восстанавливаем игроков с их картами
        players = {}
        for color, exposed_player in exposed_state.players.items():
            # Создаем полного игрока, подставляя карты из player_hands
            player_data = exposed_player.model_dump()
            player_data.update({
                "hand": player_hands[color],
                "available_buildings": exposed_player.available_buildings,
                "color": color,
                "bank": exposed_player.bank,
                "income": exposed_player.income,
                "income_points": exposed_player.income_points,
                "victory_points": exposed_player.victory_points,
                "money_spent": exposed_player.money_spent
            })
            players[color] = Player(**player_data)

        # Создаем данные для BoardState
        state_data = exposed_state.model_dump()
        state_data.update({
            "players": players,
            "deck": deck
        })
        
        # Удаляем поле deck_size, которое есть только в exposed
        del state_data["deck_size"]
        
        return cls(**state_data)
    
    def hide_state(self) -> BoardStateExposed:
        data = self.model_dump()
        data["players"] = {color: player.hide_hand() for color, player in self.players.items()}
        data["deck_size"] = len(self.deck)
        del data["deck"]
        return BoardStateExposed(**data)

    def iter_placed_buildings(self) -> Iterator[Building]:
        for city in self.cities.values():
            for slot in city.slots.values():
                if slot.building_placed:
                    yield slot.building_placed

    def iter_merchant_slots(self) -> Iterator[MerchantSlot]:
        for city in self.cities.values():
            if city.merchant_slots:
                for slot in city.merchant_slots.values():
                    yield slot
    
    def iter_building_slots(self) -> Iterator[BuildingSlot]:
        for city in self.cities.values():
            if city.slots:
                for slot in city.slots.values():
                    yield slot
    
    def get_player_iron_sources(self) -> List[Building]:
        out = []
        for building in self.iter_placed_buildings():
            if building.industry_type == IndustryType.IRON and building.resource_count > 0:
                out.append(building)
        return out

    def get_player_coal_locations(self, city_name:Optional[str]=None, link_id:Optional[int]=None) -> Dict[str, int] : 
        '''Returns dict: city name, priority'''
        return self.find_paths(start=city_name, start_link_id=link_id, target_condition=lambda city: any(
            slot.building_placed is not None and
            slot.building_placed.industry_type == IndustryType.COAL and
            slot.building_placed.resource_count > 0
            for slot in self.cities[city].slots.values()
        ),
        find_all=True)

    def get_player_coal_sources(self, city_name:Optional[str]=None, link_id:Optional[str]=None) -> List[tuple[Building, int]]:
        '''Returns list of tuples: Building, priority, sorted by priority asc'''        
        out = []
        coal_cities = self.get_player_coal_locations(city_name, link_id)
        for city, priority in coal_cities.items():
            for slot in self.cities[city].slots.values():
                if slot.building_placed is not None:
                    building = slot.building_placed
                    if building.industry_type == IndustryType.COAL and building.resource_count > 0:
                        out.append((building, priority))

        out.sort(key=lambda x: x[1])
        return out
    
    def get_player_beer_sources(self, color:PlayerColor, city_name:Optional[str]=None, link_id:Optional[int]=None) -> List[Building]:
        out = []
        for building in self.iter_placed_buildings():
            if building.industry_type == IndustryType.BREWERY:
                if building.owner == color:
                    out.append(building)
                else:
                    city = self.get_building_slot(building.slot_id).city
                    connected = self.find_paths(start=city_name, end=city, start_link_id=link_id)
                    if connected:
                        out.append(building)
        return out
    
    def market_access_exists(self, city_name: str):
        return self.find_paths(start=city_name, target_condition=lambda city: self.cities[city].is_merchant)

    def find_paths(
        self,
        start: Optional[str] = None,
        target_condition: Optional[Callable[[str], bool]] = None,
        end: Optional[str] = None,
        find_all: bool = False,
        start_link_id: Optional[str] = None  
    ) -> Union[bool, Dict[str, int]]:
        # Проверяем, что указан ровно один вариант старта
        if (start is None) == (start_link_id is None):
            raise ValueError("Specify exactly one: start city or start_link_id")

        # Обработка старта через связь
        if start_link_id is not None:
            if start_link_id not in self.links:
                return {} if find_all else False
            link = self.links[start_link_id]
            start_cities = link.cities
            # Фильтруем города, отсутствующие в self.cities
            valid_start_cities = [city for city in start_cities if city in self.cities]
            if not valid_start_cities:
                return {} if find_all else False
        else:
            # Проверка существования стартового города
            if start not in self.cities:
                return {} if find_all else False
            valid_start_cities = [start]

        # Определяем условие поиска
        if end is not None:
            target_check = lambda city: city == end
        elif target_condition is not None:
            target_check = target_condition
        else:
            raise ValueError("Must have either target city or condition")

        # Проверяем условие для стартовых городов
        if not find_all:
            for city in valid_start_cities:
                if target_check(city):
                    return True
        else:
            found_cities = {}
            for city in valid_start_cities:
                if target_check(city):
                    found_cities[city] = 0

        # Построение графа связей
        graph = {}
        for link in self.links.values():
            if link.owner is None:
                continue
            cities_in_link = link.cities
            for i in range(len(cities_in_link)):
                city1 = cities_in_link[i]
                if city1 not in graph:
                    graph[city1] = set()
                for j in range(len(cities_in_link)):
                    if i != j:
                        city2 = cities_in_link[j]
                        graph[city1].add(city2)

        # Инициализация BFS
        visited = set(valid_start_cities)
        queue = deque([(city, 0) for city in valid_start_cities])
        found_cities = found_cities if find_all else {}

        # Основной цикл BFS
        while queue:
            current_city, distance = queue.popleft()
            neighbors = graph.get(current_city, set())
            for neighbor in neighbors:
                if neighbor not in visited:
                    visited.add(neighbor)
                    new_distance = distance + 1
                    if target_check(neighbor):
                        if not find_all:
                            return True
                        found_cities[neighbor] = new_distance
                    queue.append((neighbor, new_distance))

        return found_cities if find_all else False

    def get_building_slot(self, building_slot_id) -> BuildingSlot:
        for city in self.cities.values():
            if building_slot_id in city.slots:
                return city.slots[building_slot_id]
        logging.debug(f"Couldn't find building slot {building_slot_id}")
    
    def get_merchant_slot(self, merchant_slot_id:int) -> MerchantSlot:
            for city in self.cities.values():
                if city.merchant_slots is not None:
                    if merchant_slot_id in city.merchant_slots:
                        return city.merchant_slots[merchant_slot_id]
            logging.debug(f"Couldn't find merchant slot {merchant_slot_id}")

    def get_resource_amount_in_city(self, city_name:str, resource_type:ResourceType) -> int:
        out = 0
        for building_slot in self.cities[city_name].slots.values():
            if building_slot.building_placed:
                if building_slot.building_placed.industry_type == resource_type:
                    out += building_slot.building_placed.resource_count
        return out
    
    def get_player_network(self, player_color: PlayerColor) -> Set[str]:
        slot_cities = {
            city.name for city in self.cities.values()
            if any(slot.building_placed and slot.building_placed.owner == player_color
                for slot in city.slots.values())
        }
        
        link_cities = {
            city for link in self.links.values()
            if link.owner == player_color
            for city in link.cities
        }

        if not slot_cities and not link_cities:
            return set(self.cities)
        
        return slot_cities | link_cities 

    def get_link_cost(self, subaction_count=0):
        if self.era == LinkType.CANAL:
            return ResourceAmounts(money=3)
        elif self.era == LinkType.RAIL:
            if subaction_count == 0:
                return ResourceAmounts(money=5, coal=1)
            else:
                return ResourceAmounts(money=10, coal=1, beer=1)
    
    def can_sell(self, city_name:str, industry:IndustryType) -> bool:
        eligible_merchants = [city for city in self.cities.values() if city.is_merchant and (any(slot.merchant_type in [MerchantType.ANY, MerchantType(industry)] for slot in city.merchant_slots.values()))]
        for merchant in eligible_merchants:
            if self.find_paths(start=city_name, end=merchant.name):
                return True

    def get_develop_cost(self, glousecter=False) -> ResourceAmounts:
        if glousecter:
            return ResourceAmounts()
        return ResourceAmounts(iron=1)

    def is_player_to_move(self, color:PlayerColor) -> bool:
        if not self.action_context is ActionContext.SHORTFALL:
            return self.turn_order[0] is color
        return self.players[color].bank < 0

    def has_subaction(self) -> bool:
        return self.subaction_count > 0
    
    def in_shortfall(self):
        if any(player.bank < 0 for player in self.players.values()):
            return True
        return False
    
    def is_terminal(self):
        return len(self.deck) == 0 and all(not player.hand for player in self.players.values())

    def get_active_player(self) -> Player:
        if self.action_context is not ActionContext.SHORTFALL:
            return self.players[self.turn_order[0]]
        else:
            players_in_shortfall = [player for player in self.players.values() if player.bank < 0]
            return random.choice(players_in_shortfall)

class OutputToPlayer(BaseModel):
    message: Optional[str] = None

class PlayerState(OutputToPlayer):
    state: BoardStateExposed
    your_hand: Dict[int, Card]
    your_color: PlayerColor

class ValidationResult(OutputToPlayer):
    is_valid: bool

class ActionProcessResult(PlayerState):
    processed: bool
    awaiting: Dict[str, List[str]]
    end_of_turn: bool = False
    end_of_game: bool = False

class TurnState(StrEnum):
    MAIN = 'main'
    IN_TRANSACTION = 'in_transaction'
    AWAITING_COMMIT = 'awaiting_commit'
    END_OF_TURN = 'end_of_turn'

class RequestResult(OutputToPlayer):
    success: bool
    result: List[Any]

class StateRequestResult(RequestResult):
    result: PlayerState

class ActionSpaceRequestResult(RequestResult):
    result:List = []
