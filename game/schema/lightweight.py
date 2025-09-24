from dataclasses import dataclass, field
from typing import List, Dict, Optional, Any

# Переиспользуем существующие Enum
from .common import ActionType, ResourceType, IndustryType

@dataclass(frozen=True)
class LightResourceSource:
    resource_type: ResourceType
    building_slot_id: Optional[int] = None
    merchant_slot_id: Optional[int] = None

@dataclass(frozen=True)
class LightResourceAmounts:
    iron: int = 0
    coal: int = 0
    beer: int = 0
    money: int = 0

@dataclass(frozen=True)
class LightBuilding:
    id: int
    industry_type: IndustryType
    level: int
    owner: str
    flipped: bool
    cost: Dict[str, int]
    resource_count: int = 0
    victory_points: int = 0
    sell_cost: Optional[int] = None
    is_developable: bool = True
    link_victory_points: int = 0
    era_exclusion: Optional[str] = None
    income: int = 0
    slot_id: Optional[int] = None
    
    def get_cost(self) -> LightResourceAmounts:
        return LightResourceAmounts(
            iron=self.cost.get(ResourceType.IRON, 0),
            coal=self.cost.get(ResourceType.COAL, 0),
            money=self.cost.get("money", 0)
        )
    
    def is_sellable(self) -> bool:
        return self.industry_type in (IndustryType.BOX, IndustryType.COTTON, IndustryType.POTTERY)

@dataclass(frozen=True)
class LightCard:
    id: int
    card_type: str
    value: str

@dataclass(frozen=True)
class LightPlayer:
    hand: Dict[int, LightCard]
    available_buildings: Dict[int, LightBuilding]
    color: str
    bank: int
    income: int = 0
    income_points: int = 0
    victory_points: int = 0
    money_spent: int = 0

@dataclass(frozen=True)
class LightMarket:
    coal_count: int = 0
    iron_count: int = 0
    coal_cost: int = 0
    iron_cost: int = 0

@dataclass(frozen=True)
class LightBoardState:
    cities: Dict[str, Any]  # Упрощаем для примера
    links: Dict[int, Any]   # Упрощаем для примера
    players: Dict[str, LightPlayer]
    market: LightMarket
    deck: List[LightCard]
    era: str
    turn_order: List[str]
    actions_left: int = 0
    discard: List[LightCard] = field(default_factory=list)
    wilds: List[LightCard] = field(default_factory=list)
    action_context: str = "main"

# Легковесные действия
@dataclass(frozen=True)
class LightAction:
    action: ActionType
    card_id: Optional[int] = None
    resources_used: Optional[List[LightResourceSource]] = None
    industry: Optional[IndustryType] = None
    slot_id: Optional[int] = None
    link_id: Optional[int] = None

class LightConverter:
    """Конвертер между Pydantic моделями и легковесными версиями"""
    
    @staticmethod
    def resource_source_to_light(source) -> LightResourceSource:
        return LightResourceSource(
            resource_type=source.resource_type,
            building_slot_id=source.building_slot_id,
            merchant_slot_id=source.merchant_slot_id
        )
    
    @staticmethod
    def building_to_light(building) -> LightBuilding:
        return LightBuilding(
            id=building.id,
            industry_type=building.industry_type,
            level=building.level,
            owner=building.owner,
            flipped=building.flipped,
            cost=dict(building.cost),
            resource_count=building.resource_count,
            victory_points=building.victory_points,
            sell_cost=building.sell_cost,
            is_developable=building.is_developable,
            link_victory_points=building.link_victory_points,
            era_exclusion=building.era_exclusion,
            income=building.income,
            slot_id=building.slot_id
        )
    
    @staticmethod
    def card_to_light(card) -> LightCard:
        return LightCard(
            id=card.id,
            card_type=card.card_type,
            value=card.value
        )
    
    @staticmethod
    def player_to_light(player) -> LightPlayer:
        return LightPlayer(
            hand={card_id: LightConverter.card_to_light(card) for card_id, card in player.hand.items()},
            available_buildings={b_id: LightConverter.building_to_light(b) for b_id, b in player.available_buildings.items()},
            color=player.color,
            bank=player.bank,
            income=player.income,
            income_points=player.income_points,
            victory_points=player.victory_points,
            money_spent=player.money_spent
        )
    
    @staticmethod
    def market_to_light(market) -> LightMarket:
        return LightMarket(
            coal_count=market.coal_count,
            iron_count=market.iron_count,
            coal_cost=market.coal_cost,
            iron_cost=market.iron_cost
        )
    
    @staticmethod
    def board_state_to_light(board_state) -> LightBoardState:
        return LightBoardState(
            cities=dict(board_state.cities),  # Упрощенная конвертация
            links=dict(board_state.links),    # Упрощенная конвертация
            players={color: LightConverter.player_to_light(player) for color, player in board_state.players.items()},
            market=LightConverter.market_to_light(board_state.market),
            deck=[LightConverter.card_to_light(card) for card in board_state.deck],
            era=board_state.era,
            turn_order=list(board_state.turn_order),
            actions_left=board_state.actions_left,
            discard=[LightConverter.card_to_light(card) for card in board_state.discard],
            wilds=[LightConverter.card_to_light(card) for card in board_state.wilds],
            action_context=board_state.action_context
        )
    
    @staticmethod
    def action_to_light(action) -> LightAction:
        resources_used = None
        if hasattr(action, 'resources_used') and action.resources_used:
            resources_used = [LightConverter.resource_source_to_light(ru) for ru in action.resources_used]
        
        return LightAction(
            action=action.action,
            card_id=getattr(action, 'card_id', None),
            resources_used=resources_used,
            industry=getattr(action, 'industry', None),
            slot_id=getattr(action, 'slot_id', None),
            link_id=getattr(action, 'link_id', None)
        )