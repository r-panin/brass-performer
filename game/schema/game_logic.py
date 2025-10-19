from dataclasses import dataclass, field
from typing import Any, List, Optional, Dict, Set, ClassVar
from enum import StrEnum
from pydantic import BaseModel

@dataclass(slots=True)
class GameEntity:
    _excluded_from_hash: ClassVar[Set[str]] = {'type_hash', 'id'}

    @property
    def type_hash(self):
        pass
    
class ActionContext(StrEnum):
    GLOUCESTER_DEVELOP = 'gloucester_develop'
    SHORTFALL = 'shortfall'
    MAIN = 'main'
    SELL = 'sell'
    NETWORK = 'network'
    DEVELOP = 'develop'

class IndustryType(StrEnum):
    BOX = "box"
    POTTERY = "pottery"
    COTTON = "cotton"
    IRON = "iron"
    COAL = "coal"
    BREWERY = "brewery"

class PlayerColor(StrEnum):
    WHITE = "white"
    PURPLE = "purple"
    YELLOW = "yellow"
    RED = "red"

class LinkType(StrEnum):
    CANAL = "canal"
    RAIL = "rail"

class CardType(StrEnum):
    CITY = "city"
    INDUSTRY = "industry"

class GameStatus(StrEnum):
    CREATED = 'created'
    ONGOING = 'ongoing'
    COMPLETE = 'complete'

class MerchantType(StrEnum):
    ANY = 'any'
    EMPTY = 'empty'
    BOX = 'box'
    POTTERY = 'pottery'
    COTTON = 'cotton'

@dataclass(frozen=True)
class ResourceAmounts:
    coal: int = 0
    iron: int = 0
    beer: int = 0
    money: int = 0
    
@dataclass
class MerchantSlot(GameEntity):
    id: int
    city: str
    merchant_type: MerchantType
    beer_available: bool = True

@dataclass
class Building(GameEntity):
    id: int
    industry_type: IndustryType
    level: int
    owner: PlayerColor
    flipped: bool
    cost: ResourceAmounts
    resource_count: int
    victory_points: int
    sell_cost: Optional[int]
    is_developable: bool
    link_victory_points: int
    era_exclusion: Optional[LinkType]
    income: int
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
    type: List[LinkType] 
    cities: List[str]
    owner: str

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
    card_type: CardType
    value: str
    
    @classmethod
    def mock(cls) -> 'Card':
        import random
        return Card(id=random.randint(100, 10**6), card_type=CardType.CITY, value='mock')

class PlayerExposed(BaseModel):
    hand_size: int
    available_buildings: Dict[IndustryType, int]  
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
    available_buildings: Dict[IndustryType, int]
    color: PlayerColor
    bank: int
    income: int
    income_points: int
    victory_points: int
    money_spent: int = 0 
    has_city_wild: bool = False
    has_industry_wild: bool = False
    
    def hide_hand(self) -> PlayerExposed:
        return PlayerExposed(
            hand_size=len(self.hand),
            available_buildings=self.available_buildings.copy(),
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
    era: LinkType
    turn_order: List[PlayerColor]
    turn_index: int
    actions_left: int
    discard: List[Card] = field(default_factory=list)
    wilds: List[Card] = field(default_factory=list)
    action_context: ActionContext = ActionContext.MAIN
    subaction_count: int = 0
    round_count: int = 1
    
    def hide_state(self) -> 'BoardStateExposed':
        players_exposed = {color: player.hide_hand() for color, player in self.players.items()}
        return BoardStateExposed(
            cities=self.cities.copy(),
            links=self.links.copy(),
            players=players_exposed,
            market=self.market,
            deck_size=len(self.deck),
            era=self.era,
            turn_order=self.turn_order.copy(),
            turn_index=self.turn_index,
            actions_left=self.actions_left,
            discard=self.discard.copy(),
            wilds=self.wilds.copy(),
            action_context=self.action_context,
            subaction_count=self.subaction_count,
            round_count=self.round_count
        )
    
    @classmethod
    def determine(
        cls,
        exposed_state: 'BoardStateExposed',
        player_hands: Dict[PlayerColor, Dict[int, Card]],
        deck: List[Card]
    ) -> "BoardState":
        players = {}
        for color, exposed_player in exposed_state.players.items():
            players[color] = Player(
                hand=player_hands[color],
                available_buildings=exposed_player.available_buildings.copy(),
                color=color,
                bank=exposed_player.bank,
                income=exposed_player.income,
                income_points=exposed_player.income_points,
                victory_points=exposed_player.victory_points,
                money_spent=exposed_player.money_spent,
                has_city_wild=exposed_player.has_city_wild,
                has_industry_wild=exposed_player.has_industry_wild
            )

        
        return cls(
            cities=exposed_state.cities.copy(),
            links=exposed_state.links.copy(),
            players=players,
            market=exposed_state.market,
            deck=deck,
            era=exposed_state.era,
            turn_order=exposed_state.turn_order.copy(),
            turn_index=exposed_state.turn_index,
            actions_left=exposed_state.actions_left,
            discard=exposed_state.discard.copy(),
            wilds=exposed_state.wilds.copy(),
            action_context=exposed_state.action_context,
            subaction_count=exposed_state.subaction_count,
            round_count=exposed_state.round_count
        )

    @classmethod
    def cardless(cls, exposed_state: "BoardStateExposed") -> "BoardState":
        players = {}
        for color, exposed_player in exposed_state.players.items():
            players[color] = Player(
                hand={},
                available_buildings=exposed_player.available_buildings.copy(),
                color=color,
                bank=exposed_player.bank,
                income=exposed_player.income,
                income_points=exposed_player.income_points,
                victory_points=exposed_player.victory_points,
                money_spent=exposed_player.money_spent,
                has_city_wild=exposed_player.has_city_wild,
                has_industry_wild=exposed_player.has_industry_wild
            )

        return cls(
            cities=exposed_state.cities.copy(),
            links=exposed_state.links.copy(),
            players=players.copy(),
            market=exposed_state.market,
            deck=[],
            era=exposed_state.era,
            turn_order=exposed_state.turn_order.copy(),
            turn_index=exposed_state.turn_index,
            actions_left=exposed_state.actions_left,
            discard=exposed_state.discard.copy(),
            wilds=exposed_state.wilds.copy(),
            action_context=exposed_state.action_context,
            subaction_count=exposed_state.subaction_count,
            round_count=exposed_state.round_count
        )
    
class BoardStateExposed(BaseModel):
    cities: Dict[str, City]  
    links: Dict[int, Link]
    players: Dict[PlayerColor, PlayerExposed]
    market: Market
    deck_size: int
    era: LinkType
    turn_order: List[PlayerColor]
    turn_index: int
    actions_left: int = 0
    discard: List[Card]
    wilds: List[Card]
    action_context: ActionContext
    subaction_count: int
    round_count: int

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

class RequestResult(OutputToPlayer):
    success: bool
    result: List[Any]

class StateRequestResult(RequestResult):
    result: PlayerState

class ActionSpaceRequestResult(RequestResult):
    result:List = []