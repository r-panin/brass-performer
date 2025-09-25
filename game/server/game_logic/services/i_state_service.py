from abc import ABC, abstractmethod
from typing import Optional, Callable, Iterator, List

class IBoardStateService(ABC):

    COAL_MAX_COST:int = 8
    IRON_MAX_COST:int = 6
    COAL_MAX_COUNT:int = 14
    IRON_MAX_COUNT:int = 10
    
    @abstractmethod
    def __init__(self, board_state):
        pass

    @abstractmethod
    def invalidate_connectivity_cache(self):
        """Вызывается при любом изменении графа связей"""
        pass

    @abstractmethod
    def invalidate_networks_cache(self):
        pass
    
    @abstractmethod
    def invalidate_coal_cache(self):
        pass

    @abstractmethod
    def are_connected(self, city1: str, city2: str) -> bool:
        pass
    
    @abstractmethod
    def find_paths(
        self,
        start: Optional[str] = None,
        target_condition: Optional[Callable[[str], bool]] = None,
        end: Optional[str] = None,
        find_all: bool = False,
        start_link_id: Optional[str] = None  
    ) -> Union[bool, Dict[str, int]]:
        pass
    
    @abstractmethod
    def iter_placed_buildings(self) -> Iterator[Building]:
        pass

    @abstractmethod
    def iter_merchant_slots(self) -> Iterator[MerchantSlot]:
        pass
    
    @abstractmethod
    def iter_building_slots(self) -> Iterator[BuildingSlot]:
        pass
    
    @abstractmethod
    def get_player_iron_sources(self) -> List[Building]:
        pass

    @abstractmethod
    def get_player_coal_locations(self, city_name: Optional[str] = None, link_id: Optional[int] = None) -> Dict[str, int]:
        '''Returns dict: city name, priority'''
        pass

    @abstractmethod
    def get_player_coal_sources(self, city_name:Optional[str]=None, link_id:Optional[str]=None) -> List[tuple[Building, int]]:
        '''Returns list of tuples: Building, priority, sorted by priority asc'''        
        pass
    
    @abstractmethod
    def get_player_beer_sources(self, color:PlayerColor, city_name:Optional[str]=None, link_id:Optional[int]=None) -> List[Building]:
        pass        
    

    @abstractmethod
    def market_access_exists(self, city_name: str) -> bool:
        pass

    @abstractmethod
    def get_building_slot(self, building_slot_id) -> BuildingSlot:
        pass
    
    @abstractmethod
    def get_merchant_slot(self, merchant_slot_id:int) -> MerchantSlot:
        pass

    @abstractmethod
    def get_resource_amount_in_city(self, city_name:str, resource_type:ResourceType) -> int:
        pass
    
    @abstractmethod
    def get_player_network(self, player_color: PlayerColor) -> Set[str]:
        pass

    @abstractmethod
    def get_link_cost(self, subaction_count=0):
        pass
    
    @abstractmethod
    def can_sell(self, city_name:str, industry:IndustryType) -> bool:
        pass

    @abstractmethod
    def get_develop_cost(self, glousecter=False) -> ResourceAmounts:
        pass

    @abstractmethod
    def is_player_to_move(self, color:PlayerColor) -> bool:
        pass

    @abstractmethod
    def has_subaction(self) -> bool:
        pass
    
    @abstractmethod
    def in_shortfall(self):
        pass
    
    @abstractmethod
    def is_terminal(self):
        pass

    @abstractmethod
    def get_active_player(self) -> Player:
        pass
    
    @abstractmethod
    def update_market_costs(self):
        pass

    @abstractmethod
    def sellable_amount(self, resource_type:ResourceType):
        pass
    
    @abstractmethod
    def calculate_coal_cost(self, amount: int) -> int:
        pass
    
    @abstractmethod
    def calculate_iron_cost(self, amount: int) -> int:
        pass
    
    @abstractmethod
    def purchase_resource(
        self, 
        resource_type: ResourceType, 
        amount: int
    ) -> int:
        pass

    @abstractmethod
    def _calculate_resource_sale_price(
        self, 
        resource_type: ResourceType, 
        amount: int
    ) -> int:
        pass

    @abstractmethod
    def sell_resource(
        self, 
        resource_type: ResourceType, 
        amount: int
    ) -> int:
        pass

    @abstractmethod
    def get_merchant_slot_purchase_options(self, merchant_slot:MerchantSlot) -> List[IndustryType]:
        pass

    @abstractmethod
    def get_city_link_vps(self, city:City):
        pass
    
    @abstractmethod
    def recalculate_income(self, player:Player, keep_points=True):
        pass

    @abstractmethod
    def get_lowest_level_building(self, color:PlayerColor, industry:IndustryType) -> Building:
        pass

    @abstractmethod
    def update_lowest_buildings(self, color:PlayerColor):
        pass
