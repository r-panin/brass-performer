from abc import ABC, abstractmethod
from ...schema import BoardState, CardType, ResourceAmounts, Player, ValidationResult, ResourceSource, ResourceType, IndustryType, ResourceAction, ParameterAction, ScoutSelection, DevelopSelection, NetworkSelection, SellSelection, BuildSelection
from typing import List
from collections import defaultdict


class ActionValidator(ABC):
    def __init__(self):
        super().__init__()

    @abstractmethod
    def validate(self, action: ParameterAction, game_state:BoardState, player: Player):
        pass

def validate_card_in_hand(func):
    def wrapper(self:BaseValidator, action:ParameterAction, game_state:BoardState, player:Player):
        if game_state.subaction_count > 0:
            return func(self, action, game_state, player)
        if action.card_id not in player.hand:
            return ValidationResult(is_valid=False, message="Card not in player's hand")
        return func(self, action, game_state, player)
    return wrapper

def validate_resources(func):
    def wrapper(self:BaseValidator, action:ResourceAction, game_state:BoardState, player:Player):
        if not action.is_auto_resource_selection():

            source_validation = self._validate_resource_sources(action, game_state, player)
            if not source_validation.is_valid:
                return source_validation
            
            base_cost_validation = self._validate_base_action_cost(action, game_state,player)
            if not base_cost_validation.is_valid:
                return base_cost_validation

            preference_validation = self._validate_iron_preference(game_state, action.resources_used)
            if not preference_validation.is_valid:
                return preference_validation

            if isinstance(action, BuildSelection):
                city_name = game_state.get_building_slot(action.slot_id).city
                link_id = None
            elif isinstance(action, NetworkSelection):
                city_name = None
                link_id = action.link_id
            
                coal_validation = self._validate_coal_preference(game_state, action.resources_used, city_name=city_name, link_id=link_id)
                if not coal_validation.is_valid:
                    return coal_validation
            
            market_coal = [resource for resource in action.resources_used if resource.building_slot_id is None and resource.resource_type == ResourceType.COAL]
            market_coal_amount = len(market_coal)
            market_iron = [resource for resource in action.resources_used if resource.building_slot_id is None and resource.resource_type == ResourceType.IRON]
            market_iron_amount = len(market_iron)
            resource_expense = game_state.market.calculate_coal_cost(market_coal_amount) + game_state.market.calculate_iron_cost(market_iron_amount)
            base_expense = self._get_base_money_cost(action, game_state, player)
            total_expense = base_expense + resource_expense
            if total_expense > player.bank:
                return ValidationResult(is_valid=False, message="Not enough money in the bank")
        return func(self, action, game_state, player)
    return wrapper

class BaseValidator(ActionValidator, ABC):
    def validate(self, action:ParameterAction, game_state:BoardState, player:Player) -> True:
        return ValidationResult(is_valid=True)
    
    def _validate_iron_preference(self, game_state:BoardState, resources: List[ResourceSource]) -> ValidationResult:
        if any(resource.building_slot_id is None and resource.resource_type == ResourceType.IRON for resource in resources):
            available_player_amount = sum(source.resource_count for source in game_state.get_player_iron_sources() if source.industry_type == IndustryType.IRON)
            asking_amount = 0
            asking_market_amount = 0
            for resource in resources:
                if resource.resource_type == ResourceType.IRON:
                    asking_amount += 1
                    if resource.building_slot_id is None:
                        asking_market_amount += 1
            if asking_amount - asking_market_amount != available_player_amount:
                return ValidationResult(is_valid=False, message="Market resource requested when player resource is available")
        return ValidationResult(is_valid=True)
            
    def _validate_coal_preference(self, game_state:BoardState, resources: List[ResourceSource], city_name:str=None, link_id:int = None) -> ValidationResult:
        coal_in_resources = any(resource.resource_type == ResourceType.COAL for resource in resources)
        if not coal_in_resources:
            return ValidationResult(is_valid=True)
        if city_name:
            available_player_sources = game_state.get_player_coal_locations(city_name=city_name)
        elif link_id:
            available_player_sources = game_state.get_player_coal_locations(link_id=link_id)
        else:
            raise ValueError("Must provide either city name or link id")
        asking_amount = len(resource for resource in resources if resource.resource_type == ResourceType.COAL)
        resource_requests = [resource for resource in resources if resource.resource_type == ResourceType.COAL]
        requested_cities = [game_state.get_building_slot(resource.building_slot_id).city for resource in resource_requests]
        distance_groups = defaultdict(list)
        for city, distance in available_player_sources.items():
            distance_groups[distance].append(city)
        sorted_distances = sorted(distance_groups.keys())
        remaining_amount = asking_amount
        found_incomplete_group = False

        for distance in sorted_distances:
            if found_incomplete_group:
                for city in distance_groups[distance]:
                    if city in requested_cities:
                        return False
                continue

            group_cities = distance_groups[distance]
            total_group_resource = sum(game_state.get_resource_amount_in_city(city_name=city, resource_type=ResourceType.COAL) for city in group_cities)
            expected_group_consumption = min(remaining_amount, total_group_resource)
            requested_group_consumption = len(resource for resource in resource_requests if game_state.get_building_slot(resource.building_slot_id).city in group_cities)
            if requested_group_consumption != expected_group_consumption:
                return ValidationResult(is_valid=False, message=f"Cities {group_cities} have coal consumption preference")
            
            remaining_amount -= requested_group_consumption
            if expected_group_consumption < total_group_resource:
                found_incomplete_group = True
        
        market_consumption = len(resource for resource in resource_requests if resource.building_slot_id is None)
        if found_incomplete_group:
            if market_consumption > 0:
                return ValidationResult(is_valid=False, message="Market access when player resources available")
        else:
            if market_consumption != remaining_amount:
                return ValidationResult(is_valid=False, message="whut?")
            
        return ValidationResult(True)    
    
    def _validate_base_action_cost(self) -> ValidationResult:
        raise ValueError("Must be defined for every resource action")

    def _validate_resource_sources(self, action:ResourceAction, game_state:BoardState, player:Player) -> ValidationResult:
        slot_resources = defaultdict(list)
        for resource in action.resources_used:
            slot_resources[resource.building_slot_id].append(resource)
            '''General checks'''
            if resource.building_slot_id is not None:
                slot = game_state.get_building_slot(resource.building_slot_id)
                if slot.building_placed is None:
                    return ValidationResult(is_valid=False, message=f"Selected slot {slot.id} has no building")
                building = slot.building_placed
                if building.industry_type.value != resource.resource_type.value:
                    return ValidationResult(is_valid=False, message=f"Selected building slot {slot.id} has a building of a mismatched industry type")

            if resource.resource_type is ResourceType.COAL:
                coal_city = game_state.get_building_slot(resource.building_slot_id).city
                if isinstance(action, BuildSelection):
                    action:BuildSelection
                    build_city = game_state.get_building_slot(action.slot_id).city
                    connected = game_state.find_paths(start=build_city, end=coal_city)
                    if not connected:
                        return ValidationResult(is_valid=False, message=f"Cities {build_city} and {coal_city} are not connected")
                elif isinstance(action, NetworkSelection):
                    action:NetworkSelection
                    connected = game_state.find_paths(start_link_id=action.link_id, end=coal_city)
                    if not connected:
                        return ValidationResult(is_valid=False, message=f"Link {action.link_id} is not connected to city {coal_city}")

        for slot_id, resource_list in slot_resources.items():
            if slot_id is None:
                continue
            building = game_state.get_building_slot(slot_id).building_placed
            if len(resource_list) > building.resource_count:
                return ValidationResult(is_valid=False, message=f'Requested {len(resource_list)} from building in slot {slot_id}, available {building.resource_count}')
        
        return ValidationResult(is_valid=True)
    
    def _get_base_money_cost(self, action:ResourceAction, game_state:BoardState, player:Player) -> int:
        return 0


class PassValidator(BaseValidator):
    @validate_card_in_hand
    def validate(self, action:ParameterAction, game_state:BoardState, player:Player):
        return ValidationResult(is_valid=True)
    
class ScoutValidator(BaseValidator):
    @validate_card_in_hand
    def validate(self, action:ScoutSelection, game_state:BoardState, player:Player):
        for card in action.additional_card_cost:
            if not card in player.hand:
                return ValidationResult(is_valid=False, message="Smart guy, huh")
        if any(card.value == "wild" for card in player.hand):
            return ValidationResult(is_valid=False, message="Cannot scout with wild cards in hand")
        return ValidationResult(is_valid=True)

class LoanValidator(BaseValidator):
    @validate_card_in_hand
    def validate(self, action:ParameterAction, game_state:BoardState, player:Player):
        if player.income_points < 3:
            return ValidationResult(is_valid=False, message="Income cannot fall below -10")
        return ValidationResult(is_valid=True)
            
class DevelopValidator(BaseValidator): 
    @validate_card_in_hand
    @validate_resources
    def validate(self, action:DevelopSelection, game_state:BoardState, player:Player):
        return ValidationResult(is_valid=True)
    
    def _validate_base_action_cost(self, action:DevelopSelection, game_state:BoardState, player):
        target_cost = game_state.get_develop_cost()
        if action.get_resource_amounts() != target_cost:
            return ValidationResult(is_valid=False, message="Base action cost doesn't match")
        return ValidationResult(is_valid=True)

class NetworkValidator(BaseValidator):
    @validate_card_in_hand
    @validate_resources
    def validate(self, action:NetworkSelection, game_state:BoardState, player:Player):
        link = game_state.links.get(action.link_id)
        if not link:
            return ValidationResult(is_valid=False, message=f"Link {action.link_id} does not exist")
        
        if link.owner is not None:
            return ValidationResult(is_valid=False, message=f"Link {link.id} is already owned by {link.owner}")
        
        if game_state.era not in link.type:
            return ValidationResult(is_valid=False, message=f"Link {link.id} doesn't support transport type {game_state.era}")
        
        network = game_state.get_player_network(player.color)
        if not network:
            if not set(link.cities) & network:
                return ValidationResult(is_valid=False, message="Link not in player's network")

        for resource in action.resources_used:
            if resource.resource_type is ResourceType.BEER:
                if resource.building_slot_id is None:
                    return ValidationResult(is_valid=False, message="Beer for this action must be sourced from buildings")
                brewery = game_state.get_building_slot(resource.building_slot_id).building_placed
                if not brewery.owner == player.color:
                    beer_city = game_state.get_building_slot(resource.building_slot_id).city
                    connected = game_state.find_paths(start_link_id=link.id, end=beer_city)
                    if not connected:
                        return ValidationResult(is_valid=False, message=f"Link {link.id} is not connected to the city {beer_city}")
        return ValidationResult(is_valid=True)
                        

    def _validate_base_action_cost(self, action:NetworkSelection, game_state:BoardState, player):
        base_link_cost = game_state.get_link_cost()
        if base_link_cost != action.get_resource_amounts():
            return ValidationResult(is_valid=False, message="Base action cost doesn't match")
        return ValidationResult(is_valid=True)

    def _get_base_money_cost(self, action, game_state, player):
        return game_state.get_link_cost(game_state.subaction_count).money
            

class BuildValidator(BaseValidator):
    OVERBUILDABLE = (IndustryType.IRON, IndustryType.COAL)
    
    @validate_card_in_hand
    @validate_resources
    def validate(self, action:BuildSelection, game_state, player):
        card = player.hand[action.card_id]
        building = player.get_lowest_level_building(action.industry)
        slot = game_state.get_building_slot(action.slot_id)
        if card.card_type == CardType.INDUSTRY:
            if building.industry_type not in card.value:
                return ValidationResult(is_valid=False, message=f"Card valude {card.value} doesn't contain the industry {building.industry_type}")
            
        elif card.card_type == CardType.CITY:
            if slot.city != card.value:
                return ValidationResult(is_valid=False, message=f"Card value {card.value} doesn't match city {slot.city}")
            
        else:
            return ValidationResult(is_valid=False, message='wut?')
        
        if action.industry not in slot.industry_type_options:
            return ValidationResult(is_valid=False, message=f"Can't build {building.industry_type} in a slot that supports {slot.industry_type_options}")

        city = game_state.cities[slot.city]
        for s in city.slots.values():
            if (len(s.industry_type_options) < len(slot.industry_type_options)) and action.industry in s.industry_type_options:
                return ValidationResult(is_valid=False, message=f"Can't build in slot {slot.id} when {s.id} has priority for this industry")
        
        # Overbuilding validation
        if slot.building_placed is not None:
            existing_building = slot.building_placed
            
            # Level check
            if existing_building.level >= building.level:
                return ValidationResult(is_valid=False, message=f"Cannot overbuild level {existing_building.level} with level {building.level}")
            
            # Ownership check
            if existing_building.owner != player.color:
                # Industry type check
                if existing_building.industry_type not in self.OVERBUILDABLE:
                    return ValidationResult(is_valid=False, message=f"Cannot overbuild {existing_building.industry_type} of another player")
                
                # Resource availability check
                resource_type = ResourceType(existing_building.industry_type)
                resource_in_market = (
                    game_state.market.coal_count > 0 if resource_type == ResourceType.COAL
                    else game_state.market.iron_count > 0
                )
                
                if resource_in_market:
                    return ValidationResult(is_valid=False, message=f"Cannot overbuild {resource_type} while it's available in market")
                
                # Check cities for resource presence
                for city in game_state.cities.values():
                    if game_state.get_resource_amount_in_city(city.name, resource_type) > 0:
                        return ValidationResult(is_valid=False, message=f"Cannot overbuild {resource_type} while present in {city.name}")

        return ValidationResult(is_valid=True)  

    def _validate_base_action_cost(self, action:BuildSelection, game_state, player:Player):
        building = player.get_lowest_level_building(action.industry)
        moneyless_cost = building.get_cost()
        moneyless_cost.money = 0 # Money is calculated within game logic and shouldn't be checked here or pass within action
        if moneyless_cost != action.get_resource_amounts():
            return ValidationResult(is_valid=False, message="Building base cost doens't match resource selecion")
        return ValidationResult(is_valid=True)

    def _get_base_money_cost(self, action, game_state, player) -> int:
        building = player.get_lowest_level_building(action.industry)
        return building.get_cost().money

class SellValidator(BaseValidator):
    @validate_card_in_hand
    def validate(self, action:SellSelection, game_state:BoardState, player:Player):
        slot = game_state.get_building_slot(action.slot_id)
        if not slot.building_placed:
            return ValidationResult(is_valid=False, message=f"Slot {action.slot_id} does not contain a building")
        
        building = slot.building_placed

        if not building.is_sellable():
            return ValidationResult(is_valid=False, message="Building is not sellable")

        if slot.building_placed.owner != player.color:
            return ValidationResult(is_valid=False, message=f"Slot {action.slot_id} is occupied by a building owned by player {player.color} who is not the current actor")

        merchant_used = False        
        for resource in action.resources_used:
            if resource.merchant_slot_id is not None:
                if merchant_used:
                    return ValidationResult(is_valid=False, message="Cannot use two merchant beers in one sell step")
                merchant_used = True 
                merchant_slot = game_state.get_merchant_slot(resource.merchant_slot_id)
                if not merchant_slot.beer_available:
                    return ValidationResult(is_valid=False, message=f'No beer available at merchant slot {merchant_slot.id}')
                if not building.industry_type in merchant_slot.buys():
                    return ValidationResult(False, f"Merchant {merchant_slot.id} does not buy {IndustryType}")
                if not game_state.find_paths(start=slot.city, end=merchant_slot.city):
                    return ValidationResult(is_valid=False, message=f"No path to merchant {merchant_slot.city}")

            elif resource.building_slot_id is not None:
                brewery = game_state.get_building_slot(resource.building_slot_id)
                if brewery.building_placed.owner != player.color:
                    connected = game_state.find_paths(start=building.city, end=brewery.city)
                    if not connected:
                        return ValidationResult(is_valid=False, message=f'Brewery in {brewery.city} is not connected to building in {building.city}')
                
        if not game_state.can_sell(slot.city, slot.building_placed.industry_type):
            return ValidationResult(is_valid=False, message=f"No path from city {slot.city} to eligible merchants for industry {slot.building_placed.industry_type}")
        
        offered_amounts = action.get_resource_amounts()
        required_amounts = ResourceAmounts(beer=slot.building_placed.sell_cost)
        if offered_amounts != required_amounts:
            return ValidationResult(is_valid=False, message=f"Action requires {required_amounts}, offered are {offered_amounts}")
        return ValidationResult(is_valid=True)