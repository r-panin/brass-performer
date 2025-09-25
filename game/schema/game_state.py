from enum import StrEnum
from pydantic import BaseModel, Field, model_validator
from typing import List, Optional, Dict, ClassVar, Set, Any
import json
import hashlib
from .common import IndustryType, ResourceType, ResourceAmounts
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
        return self.industry_type in (IndustryType.BOX, IndustryType.COTTON, IndustryType.POTTERY)


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


class Market(BaseModel):
    coal_count: int = Field(le=14)
    iron_count: int = Field(le=10)
    coal_cost: int
    iron_cost: int

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
