from collections import deque
from typing import Callable, Iterator, List, Optional, Dict, Set, Union
from ....schema import BoardState, City, Building, MerchantSlot, BuildingSlot,  IndustryType, Player, PlayerColor, ResourceType, LinkType, ResourceAmounts, MerchantType, ActionContext, Card, Link
import random
import math
import logging

class BoardStateService:
    
    COAL_MAX_COST:int = 8
    IRON_MAX_COST:int = 6
    COAL_MAX_COUNT:int = 14
    IRON_MAX_COUNT:int = 10
    
    def __init__(self, board_state: BoardState):
        self.state = board_state
        self.update_market_costs()
        # Временные поля для логики хода
        self.subaction_count: int = 0
        self.gloucester_develop: bool = False
        self._connectivity_cache = None
        self._graph_cache = None
        self._coal_cities_cache = None
        self._merchant_cities_cache = None
        self._networks_cache = None
        self._lowest_building_cache:Dict[PlayerColor, Dict[IndustryType, Building]] = {}
        self._iron_cache = None
        self.round_count = 1

    # --- Encapsulated BoardState accessors/mutators (public API) ---
    def get_board_state(self) -> BoardState:
        return self.state

    def wipe_hands(self) -> None:
        for _, player in self.get_players().items():
            player.hand = {}

    def clear_discard(self) -> None:
        self.state.discard = []

    def give_player_a_card(self, color:PlayerColor, card:Card) -> None:
        self.get_player(color).hand[card.id] = card

    def get_exposed_state(self):
        return self.state.hide_state()

    def get_players(self) -> Dict[PlayerColor, Player]:
        return self.state.players

    def get_player(self, color: PlayerColor) -> Player:
        return self.state.players[color]

    def get_player_hand_dict(self, color: PlayerColor) -> Dict[int, Card]:
        return self.state.players[color].hand

    def get_turn_order(self) -> List[PlayerColor]:
        return self.state.turn_order
    
    def set_turn_order(self, new_order: List[PlayerColor]) -> None:
        self.state.turn_order = new_order

    def advance_turn_order(self) -> PlayerColor:
        """Remove and return the active player from the front of turn order."""
        logging.debug(f"Turn order before advancing {self.state.turn_order}, removing {self.state.turn_order[0]}")
        self.state.turn_index += 1
        return self.state.turn_index

    def get_actions_left(self) -> int:
        return self.state.actions_left

    def set_actions_left(self, value: int) -> None:
        self.state.actions_left = value

    def get_action_context(self) -> ActionContext:
        return self.state.action_context

    def set_action_context(self, ctx: ActionContext) -> None:
        self.state.action_context = ctx

    def get_deck(self) -> List[Card]:
        return self.state.deck

    def get_deck_size(self) -> int:
        return len(self.state.deck)

    def append_discard(self, card: 'Card') -> None:
        self.state.discard.append(card)

    def get_wild_cards(self) -> List['Card']:
        return self.state.wilds

    def get_cities(self) -> Dict[str, City]:
        return self.state.cities

    def get_city(self, name: str) -> City:
        return self.state.cities[name]

    def get_links(self) -> Dict[int, Link]:
        return self.state.links

    def iter_links(self):
        return self.state.links.values()

    def get_link(self, link_id: int) -> Link:
        return self.state.links[link_id]

    def set_link_owner(self, link_id: int, owner: PlayerColor) -> None:
        self.state.links[link_id].owner = owner

    def get_market_coal_count(self) -> int:
        return self.state.market.coal_count

    def get_market_iron_count(self) -> int:
        return self.state.market.iron_count

    def get_era(self) -> LinkType:
        return self.state.era

    def invalidate_connectivity_cache(self):
        """Вызывается при любом изменении графа связей"""
        self._connectivity_cache = None
        self._graph_cache = None
        self._coal_cities_cache = None
        self._networks_cache = None

    def invalidate_networks_cache(self):
        self._networks_cache = None

    def invalidate_coal_cache(self):
        self._coal_cities_cache = None

    def _build_condition_caches(self):
        """Предварительно вычисляем города с углем и торговцами"""
        self._coal_cities_cache = set()
        self._merchant_cities_cache = set()
        
        for city_name, city in self.get_cities().items():
            # Кэш для угольных городов
            if any(slot.building_placed is not None and
                  slot.building_placed.industry_type == IndustryType.COAL and
                  slot.building_placed.resource_count > 0
                  for slot in city.slots.values()):
                self._coal_cities_cache.add(city_name)
            
            # Кэш для городов с торговцами
            if city.is_merchant:
                self._merchant_cities_cache.add(city_name)

    def _build_graph(self) -> Dict[str, Set[str]]:
        """Построение графа один раз для состояния"""
        if self._graph_cache is not None:
            return self._graph_cache

        graph = {}
        for link in self.iter_links():
            if link.owner is None:
                continue
            cities_in_link = [city for city in link.cities if city in self.get_cities()]
            
            for i, city1 in enumerate(cities_in_link):
                if city1 not in graph:
                    graph[city1] = set()
                for j, city2 in enumerate(cities_in_link):
                    if i != j:
                        graph[city1].add(city2)
        
        self._graph_cache = graph
        return graph
    
    def _get_connectivity_components(self) -> Dict[str, int]:
        """Вычисление компонент связности один раз для состояния"""
        if self._connectivity_cache is not None:
            return self._connectivity_cache
            
        graph = self._build_graph()
        visited = set()
        components = {}
        component_id = 0
        
        for city in graph:
            if city not in visited:
                # BFS для нахождения всей компоненты
                queue = deque([city])
                visited.add(city)
                current_component = set()
                
                while queue:
                    current_city = queue.popleft()
                    current_component.add(current_city)
                    components[current_city] = component_id
                    
                    for neighbor in graph.get(current_city, set()):
                        if neighbor not in visited:
                            visited.add(neighbor)
                            queue.append(neighbor)
                
                component_id += 1
        
        self._connectivity_cache = components
        return components
    
    def are_connected(self, city1: str, city2: str) -> bool:
        """Быстрая проверка связности через компоненты"""
        if city1 == city2:
            return True
            
        components = self._get_connectivity_components()
        return (city1 in components and 
                city2 in components and 
                components[city1] == components[city2])
    
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
            if start_link_id not in self.get_links():
                return {} if find_all else False
            link = self.get_link(start_link_id)
            start_cities = link.cities
            valid_start_cities = [city for city in start_cities if city in self.get_cities()]
            if not valid_start_cities:
                return {} if find_all else False
        else:
            if start not in self.get_cities():
                return {} if find_all else False
            valid_start_cities = [start]

        # Определяем условие поиска
        if end is not None:
            target_check = lambda city: city == end
        elif target_condition is not None:
            target_check = target_condition
        else:
            raise ValueError("Must have either target city or condition")

        # Быстрая проверка для стартовых городов
        if not find_all:
            for city in valid_start_cities:
                if target_check(city):
                    return True
        else:
            found_cities = {}
            for city in valid_start_cities:
                if target_check(city):
                    found_cities[city] = 0

        # Используем компоненты связности для быстрой проверки
        components = self._get_connectivity_components()
        graph = self._build_graph()
        
        # Для каждого стартового города находим его компоненту
        start_components = set()
        for city in valid_start_cities:
            if city in components:
                start_components.add(components[city])
        
        if not start_components:
            return found_cities if find_all else False

        # Быстрая проверка без BFS для случая find_all=False
        if not find_all:
            # Проверяем все города в нужных компонентах
            for city, comp_id in components.items():
                if comp_id in start_components and target_check(city):
                    return True
            return False

        # Для find_all=True делаем BFS только по нужным компонентам
        visited = set(valid_start_cities)
        queue = deque([(city, 0) for city in valid_start_cities])
        
        while queue:
            current_city, distance = queue.popleft()
            neighbors = graph.get(current_city, set())
            
            for neighbor in neighbors:
                if neighbor not in visited:
                    visited.add(neighbor)
                    new_distance = distance + 1
                    if target_check(neighbor):
                        found_cities[neighbor] = new_distance
                    queue.append((neighbor, new_distance))

        return found_cities
    
    def iter_placed_buildings(self) -> Iterator[Building]:
        for city in self.get_cities().values():
            for slot in city.slots.values():
                if slot.building_placed:
                    yield slot.building_placed

    def iter_merchant_slots(self) -> Iterator[MerchantSlot]:
        for city in self.get_cities().values():
            if city.merchant_slots:
                for slot in city.merchant_slots.values():
                    yield slot
    
    def iter_building_slots(self) -> Iterator[BuildingSlot]:
        for city in self.get_cities().values():
            if city.slots:
                for slot in city.slots.values():
                    yield slot
    
    def get_player_iron_sources(self) -> List[Building]:
        if self._iron_cache:
            return self._iron_cache
        out = []
        for building in self.iter_placed_buildings():
            if building.industry_type == IndustryType.IRON and building.resource_count > 0:
                out.append(building)
        self._iron_cache = out
        return out

    def invalidate_iron_cache(self):
        self._iron_cache = None

    def get_player_coal_locations(self, city_name: Optional[str] = None, link_id: Optional[int] = None) -> Dict[str, int]:
        '''Returns dict: city name, priority'''
        if self._coal_cities_cache is None:
            self._build_condition_caches()
        
        # Быстрая проверка: если нет угольных городов вообще
        if not self._coal_cities_cache:
            return {}
        
        return self.find_paths(
            start=city_name, 
            start_link_id=link_id, 
            target_condition=lambda city: city in self._coal_cities_cache,
            find_all=True
        ) 

    def get_player_coal_sources(self, city_name:Optional[str]=None, link_id:Optional[str]=None) -> List[tuple[Building, int]]:
        '''Returns list of tuples: Building, priority, sorted by priority asc'''        
        out = []
        coal_cities = self.get_player_coal_locations(city_name, link_id)
        for city, priority in coal_cities.items():
            for slot in self.get_city(city).slots.values():
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
                    if city_name:
                        connected = self.are_connected(city_name, city)
                    elif link_id:
                        link = self.get_link(link_id)
                        connected = any(self.are_connected(c, city) for c in link.cities)
                    else:
                        raise ValueError('Beer search requires either a city name or a link id')
                    if connected:
                        out.append(building)
        return out
    

    def market_access_exists(self, city_name: str) -> bool:
        if self._merchant_cities_cache is None:
            self._build_condition_caches()
        
        # Быстрая проверка: если нет городов с торговцами
        if not self._merchant_cities_cache:
            return False
        
        return self.find_paths(
            start=city_name, 
            target_condition=lambda city: city in self._merchant_cities_cache
        )

    def get_building_slot(self, building_slot_id) -> BuildingSlot:
        for city in self.get_cities().values():
            if building_slot_id in city.slots:
                return city.slots[building_slot_id]
    
    def get_merchant_slot(self, merchant_slot_id:int) -> MerchantSlot:
            for city in self.get_cities().values():
                if city.merchant_slots is not None:
                    if merchant_slot_id in city.merchant_slots:
                        return city.merchant_slots[merchant_slot_id]

    def get_resource_amount_in_city(self, city_name:str, resource_type:ResourceType) -> int:
        out = 0
        for building_slot in self.get_city(city_name).slots.values():
            if building_slot.building_placed:
                if building_slot.building_placed.industry_type == resource_type:
                    out += building_slot.building_placed.resource_count
        return out
    
    def get_player_network(self, player_color: PlayerColor) -> Set[str]:
        if self._networks_cache is None:
            self._networks_cache = {}
        if player_color in self._networks_cache:
            return self._networks_cache[player_color]
        
        network = self._build_player_network(player_color)
        self._networks_cache[player_color] = network
        return network
    
    def _build_player_network(self, player_color: PlayerColor) -> Set[str]:
        slot_cities = {
            city.name for city in self.get_cities().values()
            if any(slot.building_placed and slot.building_placed.owner == player_color
                for slot in city.slots.values())
        }
        
        link_cities = {
            city for link in self.iter_links()
            if link.owner == player_color
            for city in link.cities
        }

        if not slot_cities and not link_cities:
            return set(self.get_cities())
        
        return slot_cities | link_cities 

    def get_link_cost(self, subaction_count=0):
        if self.get_era() == LinkType.CANAL:
            return ResourceAmounts(money=3)
        elif self.get_era() == LinkType.RAIL:
            if subaction_count == 0:
                return ResourceAmounts(money=5, coal=1)
            else:
                return ResourceAmounts(money=10, coal=1, beer=1)
    
    def can_sell(self, city_name:str, industry:IndustryType) -> bool:
        eligible_merchants = [city for city in self.get_cities().values() if city.is_merchant and (any(slot.merchant_type in [MerchantType.ANY, MerchantType(industry)] for slot in city.merchant_slots.values()))]
        for merchant in eligible_merchants:
            if self.are_connected(city_name, merchant.name):
                return True

    def get_develop_cost(self, glousecter=False) -> ResourceAmounts:
        if glousecter:
            return ResourceAmounts()
        return ResourceAmounts(iron=1)

    def is_player_to_move(self, color:PlayerColor) -> bool:
        if not self.get_action_context() is ActionContext.SHORTFALL:
            return self.get_turn_order()[0] is color
        return self.get_player(color).bank < 0

    def has_subaction(self) -> bool:
        return self.subaction_count > 0
    
    def in_shortfall(self):
        if any(player.bank < 0 for player in self.get_players().values()):
            return True
        return False
    
    def is_terminal(self):
        return self.get_deck_size() == 0 and all(not player.hand for player in self.get_players().values()) and self.get_era() is LinkType.RAIL

    def get_turn_index(self) -> int:
        return self.state.turn_index
    
    def reset_turn_index(self) -> None:
        self.state.turn_index = 0

    def get_active_player(self) -> Player:
        if self.get_action_context() is not ActionContext.SHORTFALL:
            return self.get_player(self.get_turn_order()[self.get_turn_index()])
        else:
            players_in_shortfall = [player for player in self.get_players().values() if player.bank < 0]
            return players_in_shortfall[0]
    
    def update_market_costs(self):
        self.state.market.coal_cost = self.COAL_MAX_COST - math.ceil(self.get_market_coal_count() / 2)
        self.state.market.iron_cost = self.IRON_MAX_COST - math.ceil(self.get_market_iron_count() / 2)

    def sellable_amount(self, resource_type:ResourceType):
        if resource_type is ResourceType.IRON:
            return self.IRON_MAX_COUNT - self.get_market_iron_count()
        elif resource_type is ResourceType.COAL:
            return self.COAL_MAX_COST - self.get_market_coal_count()
    
    def _calculate_resource_cost(
        self, 
        resource_type: ResourceType, 
        amount: int
    ) -> int:
        if resource_type == ResourceType.COAL:
            current_count = self.get_market_coal_count()
            max_cost = self.COAL_MAX_COST
        elif resource_type == ResourceType.IRON:
            current_count = self.get_market_iron_count()
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
            self.state.market.coal_count = max(0, self.get_market_coal_count() - amount)
        elif resource_type == ResourceType.IRON:
            self.state.market.iron_count = max(0, self.get_market_iron_count() - amount)
            
        self.update_market_costs()
        return total_cost
    

    def _calculate_resource_sale_price(
        self, 
        resource_type: ResourceType, 
        amount: int
    ) -> int:
        if resource_type == ResourceType.COAL:
            current_count = self.get_market_coal_count()
            max_cost = self.COAL_MAX_COST
            max_count = self.COAL_MAX_COUNT
        elif resource_type == ResourceType.IRON:
            current_count = self.get_market_iron_count()
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
            self.state.market.coal_count += amount
        elif resource_type == ResourceType.IRON:
            self.state.market.iron_count += amount
            
        self.update_market_costs()
        return total_revenue

    def get_merchant_slot_purchase_options(self, merchant_slot:MerchantSlot) -> List[IndustryType]:
        out = set()
        if merchant_slot.merchant_type is MerchantType.ANY:
            out.add(IndustryType.BOX)
            out.add(IndustryType.COTTON)
            out.add(IndustryType.POTTERY)
        elif merchant_slot.merchant_type is MerchantType.POTTERY:
            out.add(IndustryType.POTTERY)
        elif merchant_slot.merchant_type is MerchantType.BOX:
            out.add(IndustryType.BOX)
        elif merchant_slot.merchant_type is MerchantType.COTTON:
            out.add(IndustryType.COTTON)
        return list(out)

    def get_city_link_vps(self, city:City):
        out = 0
        for slot in city.slots.values():
            if slot.building_placed is not None:
                building = slot.building_placed
                if building.flipped:
                    out += building.victory_points
        return out
    
    def recalculate_income(self, player:Player, keep_points=True):
        if keep_points:
            if player.income_points <= 10:
                player.income = player.income_points - 10
            elif player.income_points <= 30:
                player.income = (player.income_points - 10) // 2
            elif player.income_points <= 60:
                player.income = (10 + player.income_points - 30) // 3
            else:
                player.income = (20 + player.income_points - 60) // 4
        else:
            if player.income <= 0:
                player.income_points = player.income + 10
            elif player.income <= 10:
                player.income_points = 2 * player.income + 10
            elif player.income <= 20:
                player.income_points = 3 * player.income
            else:
                player.income_points = 3 * player.income + (player.income % 10)

    def get_lowest_level_building(self, color:PlayerColor, industry:IndustryType) -> Building:
            if not color in self._lowest_building_cache:
                self.update_lowest_buildings(color)
            return self._lowest_building_cache[color][industry]

    def update_lowest_buildings(self, color:PlayerColor):
        player = self.get_player(color)
        self._lowest_building_cache[color] = {}
        for industry in IndustryType:
            buildings = [b for b in player.available_buildings.values() if b.industry_type is industry]
            self._lowest_building_cache[color][industry] = min(buildings, key=lambda x: x.level, default=None)

    def check_wilds(self, color:PlayerColor) -> bool:
        player = self.get_player(color)
        if any(card.value == 'wild' for card in player.hand.values()):
            return True
        return False

    def get_current_round(self):
        return self.round_count
    
    def advance_round_count(self):
        self.round_count += 1