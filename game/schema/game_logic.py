from dataclasses import dataclass, field
from typing import List, Optional, Dict, Set, ClassVar
from enum import StrEnum
from pydantic import BaseModel

@dataclass(slots=True)
class GameEntity:
    _excluded_from_hash: ClassVar[Set[str]] = {'type_hash', 'id'}
    type_hash: str = field(default=None, init=False)
    
    def __post_init__(self):
        self.type_hash = self._generate_hash()
    
    def _generate_hash(self) -> str:
        # Ручной обход значимых полей вместо model_dump
        fields_data = []
        
        for field_name, field_value in self:
            if field_name in self._excluded_from_hash:
                continue
                
            if isinstance(field_value, (list, dict, set)):
                # Для коллекций создаем хешируемое представление
                fields_data.append((field_name, self._hash_collection(field_value)))
            else:
                fields_data.append((field_name, field_value))
        
        # Сортируем по имени поля для детерминированности
        fields_data.sort(key=lambda x: x[0])
        
        return str(hash(tuple(fields_data)))

    def _hash_collection(self, obj):
        if isinstance(obj, dict):
            return tuple(sorted((k, self._hash_collection(v)) for k, v in obj.items()))
        elif isinstance(obj, list):
            return tuple(self._hash_collection(x) for x in obj)
        elif isinstance(obj, set):
            return tuple(sorted(self._hash_collection(x) for x in obj))
        else:
            return obj


# Enum оставляем как есть - они легковесные
class ActionContext(StrEnum):
    GLOVCESTER_DEVELOP = 'gloucester_develop'
    SHORTFALL = 'shortfall'
    MAIN = 'main'
    SELL = 'sell'
    NETWORK = 'network'
    DEVELOP = 'develop'

class IndustryType(StrEnum):
    BOX = "box"
    POTTERY = "pottery"
    COTTON = "cotton"
    # ... остальные типы

class PlayerColor(StrEnum):
    WHITE = "white"
    PURPLE = "purple"
    YELLOW = "yellow"
    RED = "red"

@dataclass
class ResourceAmounts:
    coal: int = 0
    iron: int = 0
    beer: int = 0
    money: int = 0
    
@dataclass
class MerchantSlot(GameEntity):
    id: int
    city: str
    merchant_type: str  
    beer_available: bool = True

@dataclass
class Building(GameEntity):
    id: int
    industry_type: IndustryType
    level: int
    owner: PlayerColor
    flipped: bool
    cost: ResourceAmounts
    resource_count: int = 0
    victory_points: int = 0
    sell_cost: Optional[int] = None
    is_developable: bool = False
    link_victory_points: int = 0
    era_exclusion: Optional[str] = None
    income: int = 0
    slot_id: Optional[int] = None
    
    def get_cost(self) -> ResourceAmounts:
        return self.cost
    
    def is_sellable(self) -> bool:
        return self.industry_type in (IndustryType.BOX, IndustryType.COTTON, IndustryType.POTTERY)

@dataclass
class BuildingSlot(GameEntity):
    id: int
    city: str
    industry_type_options: List[IndustryType]
    building_placed: Optional[Building] = None

@dataclass
class Link(GameEntity):
    id: int
    type: List[str]  # List[LinkType] как List[str]
    cities: List[str]
    owner: Optional[str] = None

@dataclass
class City(GameEntity):
    name: str
    slots: Dict[int, BuildingSlot]  
    is_merchant: bool
    merchant_slots: Optional[Dict[int, MerchantSlot]] = None
    merchant_min_players: Optional[int] = None

@dataclass
class Market:
    coal_count: int = 0
    iron_count: int = 0
    coal_cost: int = 0
    iron_cost: int = 0

@dataclass
class Card(GameEntity):
    id: int
    card_type: str  
    value: str
    
    @classmethod
    def mock(cls) -> 'Card':
        import random
        return Card(id=random.randint(100, 10**6), card_type='city', value='mock')

class PlayerExposed(BaseModel):
    hand_size: int
    available_buildings: Dict[int, Building]  
    color: PlayerColor
    bank: int
    income: int
    income_points: int
    victory_points: int
    money_spent: int = 0
    has_city_wild: bool = False
    has_industry_wild: bool = False

@dataclass
class Player:
    hand: Dict[int, Card]
    available_buildings: Dict[int, Building]
    color: PlayerColor
    bank: int
    income: int = -10
    income_points: int = -10
    victory_points: int = 0
    money_spent: int = 0
    has_city_wild: bool = False
    has_industry_wild: bool = False
    
    def hide_hand(self) -> PlayerExposed:
        return PlayerExposed(
            hand_size=len(self.hand),
            available_buildings=self.available_buildings,
            color=self.color,
            bank=self.bank,
            income=self.income,
            income_points=self.income_points,
            victory_points=self.victory_points,
            money_spent=self.money_spent,
            has_city_wild=self.has_city_wild,
            has_industry_wild=self.has_industry_wild
        )

@dataclass
class BoardState:
    cities: Dict[str, City]
    links: Dict[int, Link]
    players: Dict[PlayerColor, Player]
    market: Market
    deck: List[Card]
    era: str  # LinkType как str
    turn_order: List[PlayerColor]
    turn_index: int
    actions_left: int = 0
    discard: List[Card] = field(default_factory=list)
    wilds: List[Card] = field(default_factory=list)
    action_context: ActionContext = ActionContext.MAIN
    
    def hide_state(self) -> 'BoardStateExposed':
        players_exposed = {color: player.hide_hand() for color, player in self.players.items()}
        return BoardStateExposed(
            cities=self.cities,
            links=self.links,
            players=players_exposed,
            market=self.market,
            deck_size=len(self.deck),
            era=self.era,
            turn_order=self.turn_order,
            turn_index=self.turn_index,
            actions_left=self.actions_left,
            discard=self.discard,
            wilds=self.wilds,
            action_context=self.action_context
        )

# API модели оставляем на Pydantic для валидации
class BoardStateExposed(BaseModel):
    cities: Dict[str, City]  
    links: Dict[int, Link]
    players: Dict[PlayerColor, PlayerExposed]
    market: Market
    deck_size: int
    era: str
    turn_order: List[PlayerColor]
    turn_index: int
    actions_left: int = 0
    discard: List[Card]
    wilds: List[Card]
    action_context: ActionContext