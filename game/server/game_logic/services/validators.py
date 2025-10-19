from abc import ABC, abstractmethod
from ....schema import CardType, ActionContext, PassAction, LoanAction, ResourceAmounts, MetaAction, Player, ValidationResult, ResourceSource, LinkType, ResourceType, IndustryType, ResourceAction, ScoutAction, DevelopAction, NetworkAction, SellAction, BuildAction
from typing import List
from collections import defaultdict
from .board_state_service import BoardStateService
from copy import copy


class ActionValidator(ABC):
    def __init__(self):
        super().__init__()

    @abstractmethod
    def validate(self, action, game_state:BoardStateService, player: Player) -> ValidationResult:
        pass

def validate_card_in_hand(func):
    def wrapper(self:BaseValidator, action:MetaAction, game_state:BoardStateService, player:Player):
        if game_state.subaction_count > 0:
            return func(self, action, game_state, player)
        if isinstance(action.card_id, int):
            if action.card_id not in player.hand:
                return ValidationResult(is_valid=False, message="Card not in player's hand")
        elif isinstance(action.card_id, list):
            for card in action.card_id:
                if card not in player.hand:
                    return ValidationResult(is_valid=False, message="Card not in player's hand")
        return func(self, action, game_state, player)
    return wrapper

def validate_resources(func):
    def wrapper(self:BaseValidator, action:ResourceAction, game_state:BoardStateService, player:Player):

        source_validation = self._validate_resource_sources(action, game_state, player)
        if not source_validation.is_valid:
            return source_validation
        
        base_cost_validation = self._validate_base_action_cost(action, game_state,player)
        if not base_cost_validation.is_valid:
            return base_cost_validation

        preference_validation = self._validate_iron_preference(game_state, action.resources_used)
        if not preference_validation.is_valid:
            return preference_validation

        if isinstance(action, BuildAction):
            city_name = game_state.get_building_slot(action.slot_id).city
            link_id = None
        elif isinstance(action, NetworkAction):
            city_name = None
            link_id = action.link_id
        
            coal_validation = self._validate_coal_preference(game_state, action.resources_used, city_name=city_name, link_id=link_id)
            if not coal_validation.is_valid:
                return coal_validation
        
        market_coal = [resource for resource in action.resources_used if resource.building_slot_id is None and resource.resource_type == ResourceType.COAL]
        market_coal_amount = len(market_coal)
        market_iron = [resource for resource in action.resources_used if resource.building_slot_id is None and resource.resource_type == ResourceType.IRON]
        market_iron_amount = len(market_iron)
        resource_expense = game_state.calculate_coal_cost(market_coal_amount) + game_state.calculate_iron_cost(market_iron_amount)
        base_expense = self._get_base_money_cost(action, game_state, player)
        total_expense = base_expense + resource_expense
        if total_expense > player.bank:
            return ValidationResult(is_valid=False, message="Not enough money in the bank")
        return func(self, action, game_state, player)
    return wrapper

class BaseValidator(ActionValidator, ABC):
    def validate(self, action, game_state:BoardStateService, player:Player) -> True:
        return ValidationResult(is_valid=True)
    
    def _validate_iron_preference(self, game_state:BoardStateService, resources: List[ResourceSource]) -> ValidationResult:
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
            
    def _validate_coal_preference(self, game_state:BoardStateService, resources: List[ResourceSource], city_name:str=None, link_id:int = None) -> ValidationResult:
        coal_in_resources = any(resource.resource_type == ResourceType.COAL for resource in resources)
        if not coal_in_resources:
            return ValidationResult(is_valid=True)
        if city_name:
            available_player_sources = game_state.get_player_coal_locations(city_name=city_name)
        elif link_id:
            available_player_sources = game_state.get_player_coal_locations(link_id=link_id)
        else:
            raise ValueError("Must provide either city name or link id")
        resource_requests = [resource for resource in resources if resource.resource_type == ResourceType.COAL]
        asking_amount = len(resource_requests)
        requested_cities = [game_state.get_building_slot(resource.building_slot_id).city for resource in resource_requests if resource.building_slot_id is not None]
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
            requested_group_consumption = len([resource for resource in resource_requests if game_state.get_building_slot(resource.building_slot_id).city in group_cities])
            if requested_group_consumption != expected_group_consumption:
                return ValidationResult(is_valid=False, message=f"Cities {group_cities} have coal consumption preference")
            
            remaining_amount -= requested_group_consumption
            if expected_group_consumption < total_group_resource:
                found_incomplete_group = True
        
        market_consumption = len([resource for resource in resource_requests if resource.building_slot_id is None])
        if found_incomplete_group:
            if market_consumption > 0:
                return ValidationResult(is_valid=False, message="Market access when player resources available")
        else:
            if market_consumption != remaining_amount:
                return ValidationResult(is_valid=False, message="whut?")
            
        return ValidationResult(is_valid=True)    
    
    def _validate_base_action_cost(self) -> ValidationResult:
        raise ValueError("Must be defined for every resource action")

    def _validate_resource_sources(self, action:ResourceAction, game_state:BoardStateService, player:Player) -> ValidationResult:
        slot_resources = defaultdict(list)
        for resource in action.resources_used:
            slot_resources[resource.building_slot_id].append(resource)
            '''General checks'''
            if resource.building_slot_id is not None:
                slot = game_state.get_building_slot(resource.building_slot_id)
                if slot.building_placed is None:
                    return ValidationResult(is_valid=False, message=f"Selected slot {slot.id} has no building")
                building = slot.building_placed
                if building.industry_type != IndustryType.BREWERY:
                    invalid_res_type = building.industry_type != resource.resource_type
                else:
                    invalid_res_type = resource.resource_type != ResourceType.BEER
                if invalid_res_type:
                    return ValidationResult(is_valid=False, message=f"Selected building slot {slot.id} has a building of a mismatched industry type")

            if resource.resource_type == ResourceType.COAL:
                if resource.building_slot_id is not None:
                    coal_city = game_state.get_building_slot(resource.building_slot_id).city
                    if isinstance(action, BuildAction):
                        action:BuildAction
                        build_city = game_state.get_building_slot(action.slot_id).city
                        connected = game_state.are_connected(build_city, coal_city)
                        if not connected:
                            return ValidationResult(is_valid=False, message=f"Cities {build_city} and {coal_city} are not connected")
                    elif isinstance(action, NetworkAction):
                        action:NetworkAction
                        link = game_state.get_link(action.link_id)
                        connected = any(game_state.are_connected(city, coal_city) for city in link.cities)
                        if not connected:
                            return ValidationResult(is_valid=False, message=f"Link {action.link_id} is not connected to city {coal_city}")
                else:
                    if isinstance(action, BuildAction):
                        action:BuildAction
                        build_city = game_state.get_building_slot(action.slot_id).city
                        connected = game_state.market_access_exists(build_city)
                        if not connected:
                            return ValidationResult(is_valid=False, message=f"Cities {build_city} is not connected to market")
                    elif isinstance(action, NetworkAction):
                        action:NetworkAction
                        link = game_state.get_link(action.link_id)
                        connected = any(game_state.market_access_exists(city) for city in link.cities)
                        if not connected:
                            return ValidationResult(is_valid=False, message=f"Link {action.link_id} is not connected to city {coal_city}")


        for slot_id, resource_list in slot_resources.items():
            if slot_id is None:
                continue
            building = game_state.get_building_slot(slot_id).building_placed
            if len(resource_list) > building.resource_count:
                return ValidationResult(is_valid=False, message=f'Requested {len(resource_list)} from building in slot {slot_id}, available {building.resource_count}')
        
        return ValidationResult(is_valid=True)
    
    def _get_base_money_cost(self, action:ResourceAction, game_state:BoardStateService, player:Player) -> int:
        return 0


class PassValidator(BaseValidator):
    @validate_card_in_hand
    def validate(self, action:PassAction, game_state:BoardStateService, player:Player):
        return ValidationResult(is_valid=True)
    
class ScoutValidator(BaseValidator):
    @validate_card_in_hand
    def validate(self, action:ScoutAction, game_state:BoardStateService, player:Player):
        for card in action.card_id:
            if player.hand[card].value == "wild":
                return ValidationResult(is_valid=False, message="Cannot scout with wild cards in hand")
        return ValidationResult(is_valid=True)

class LoanValidator(BaseValidator):
    @validate_card_in_hand
    def validate(self, action:LoanAction, game_state:BoardStateService, player:Player):
        if player.income_points < 3:
            return ValidationResult(is_valid=False, message="Income cannot fall below -10")
        return ValidationResult(is_valid=True)
            
class DevelopValidator(BaseValidator): 
    @validate_card_in_hand
    @validate_resources
    def validate(self, action:DevelopAction, game_state:BoardStateService, player:Player):
        building = game_state.get_current_building(player, action.industry)
        if building is None:
            return ValidationResult(is_valid=False, message=f"Ran out of buildings")
        if not building.is_developable:
            return ValidationResult(is_valid=False, message=f"Next building in industry {action.industry} is not developable")
        return ValidationResult(is_valid=True)
    
    def _validate_base_action_cost(self, action:DevelopAction, game_state:BoardStateService, player):
        if game_state.get_action_context() == ActionContext.GLOUCESTER_DEVELOP:
            target_cost = game_state.get_develop_cost(glousecter=True)
        else:
            target_cost = game_state.get_develop_cost(glousecter=False)
        if action.get_resource_amounts() != target_cost:
            return ValidationResult(is_valid=False, message="Base action cost doesn't match")
        return ValidationResult(is_valid=True)

class NetworkValidator(BaseValidator):
    @validate_card_in_hand
    @validate_resources
    def validate(self, action:NetworkAction, game_state:BoardStateService, player:Player):
        link = game_state.get_links().get(action.link_id)
        if not link:
            return ValidationResult(is_valid=False, message=f"Link {action.link_id} does not exist")
        
        if link.owner is not None:
            return ValidationResult(is_valid=False, message=f"Link {link.id} is already owned by {link.owner}")
        
        if game_state.get_era() not in link.type:
            return ValidationResult(is_valid=False, message=f"Link {link.id} doesn't support transport type {game_state.get_era()}")
        
        network = game_state.get_player_network(player.color)
        if not network:
            if not set(link.cities) & network:
                return ValidationResult(is_valid=False, message="Link not in player's network")

        for resource in action.resources_used:
            if resource.resource_type == ResourceType.BEER:
                if resource.building_slot_id is None:
                    return ValidationResult(is_valid=False, message="Beer for this action must be sourced from buildings")
                brewery = game_state.get_building_slot(resource.building_slot_id).building_placed
                if not brewery.owner == player.color:
                    beer_city = game_state.get_building_slot(resource.building_slot_id).city
                    connected = any(game_state.are_connected(city, beer_city) for city in link.cities)
                    if not connected:
                        return ValidationResult(is_valid=False, message=f"Link {link.id} is not connected to the city {beer_city}")
        return ValidationResult(is_valid=True)
                        

    def _validate_base_action_cost(self, action:NetworkAction, game_state:BoardStateService, player):
        base_link_cost = game_state.get_link_cost()
        base_link_cost.money = 0 # money is deducted automatically within game logic and shouldn't be validated here
        if base_link_cost != action.get_resource_amounts():
            return ValidationResult(is_valid=False, message="Base action cost doesn't match")
        return ValidationResult(is_valid=True)

    def _get_base_money_cost(self, action, game_state, player):
        return game_state.get_link_cost(game_state.subaction_count).money
            

class BuildValidator(BaseValidator):
    OVERBUILDABLE = (IndustryType.IRON, IndustryType.COAL)
    
    @validate_card_in_hand
    @validate_resources
    def validate(self, action:BuildAction, game_state:BoardStateService, player):
        card = player.hand[action.card_id]
        building = game_state.get_current_building(player, action.industry)
        if building is None:
            return ValidationResult(is_valid=False, message=f"Ran out of buildings")
        if building.era_exclusion is not None and building.era_exclusion != game_state.get_era():
            return ValidationResult(is_valid=False, message=f"Building with era exclusion {building.era_exclusion} cannot be built during {game_state.get_era()} era")
        slot = game_state.get_building_slot(action.slot_id)
        if card.card_type == CardType.INDUSTRY:
            if building.industry_type not in card.value and card.value != 'wild':
                return ValidationResult(is_valid=False, message=f"Card valude {card.value} doesn't contain the industry {building.industry_type}")
            
        elif card.card_type == CardType.CITY:
            if slot.city != card.value and card.value != 'wild':
                return ValidationResult(is_valid=False, message=f"Card value {card.value} doesn't match city {slot.city}")
            if card.value == 'wild' and 'brewery' in slot.city:
                return ValidationResult(is_valid=False, message="Can't use a city joker to build in farm breweries")
            
        else:
            return ValidationResult(is_valid=False, message='wut?')
        
        if action.industry not in slot.industry_type_options:
            return ValidationResult(is_valid=False, message=f"Can't build {building.industry_type} in a slot that supports {slot.industry_type_options}")

        city = game_state.get_city(slot.city)
        for s in city.slots.values():
            if (len(s.industry_type_options) < len(slot.industry_type_options)) and action.industry in s.industry_type_options:
                return ValidationResult(is_valid=False, message=f"Can't build in slot {slot.id} when {s.id} has priority for this industry")
            if s.building_placed is not None:
                if s.id == action.slot_id:
                    return ValidationResult(is_valid=False, message=f"Slot {slot.id} already occupied")
                if s.building_placed.owner == player.color and game_state.get_era() == LinkType.CANAL:
                    return ValidationResult(is_valid=False, message=f"Can't build two buildings in one city during canal era")
        
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

    def _validate_base_action_cost(self, action:BuildAction, game_state:BoardStateService, player:Player):
        building = game_state.get_current_building(player, action.industry)
        moneyless_cost = copy(building.get_cost())
        moneyless_cost.money = 0 # Money is calculated within game logic and shouldn't be checked here or pass within action
        if moneyless_cost != action.get_resource_amounts():
            return ValidationResult(is_valid=False, message="Building base cost doens't match resource selecion")
        return ValidationResult(is_valid=True)

    def _get_base_money_cost(self, action, game_state, player) -> int:
        building = game_state.get_current_building(player, action.industry)
        return building.get_cost().money

class SellValidator(BaseValidator):
    @validate_card_in_hand
    def validate(self, action:SellAction, game_state:BoardStateService, player:Player):
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
                if not building.industry_type in game_state.get_merchant_slot_purchase_options(merchant_slot):
                    return ValidationResult(False, f"Merchant {merchant_slot.id} does not buy {IndustryType}")
                if not game_state.are_connected(slot.city, merchant_slot.city):
                    return ValidationResult(is_valid=False, message=f"No path to merchant {merchant_slot.city}")

            elif resource.building_slot_id is not None:
                brewery = game_state.get_building_slot(resource.building_slot_id)
                if brewery.building_placed.owner != player.color:
                    connected = game_state.are_connected(slot.city, brewery.city)
                    if not connected:
                        return ValidationResult(is_valid=False, message=f'Brewery in {brewery.city} is not connected to building in {slot.city}')
                
        if not game_state.can_sell(slot.city, slot.building_placed.industry_type):
            return ValidationResult(is_valid=False, message=f"No path from city {slot.city} to eligible merchants for industry {slot.building_placed.industry_type}")
        
        offered_amounts = action.get_resource_amounts()
        required_amounts = ResourceAmounts(beer=slot.building_placed.sell_cost)
        if offered_amounts != required_amounts:
            return ValidationResult(is_valid=False, message=f"Action requires {required_amounts}, offered are {offered_amounts}")
        return ValidationResult(is_valid=True)

class CommitValidator(BaseValidator):
    def validate(self, action, game_state, player):
        return ValidationResult(is_valid=True)
    
class ShortfallValidator(BaseValidator):
    def validate(self, action, game_state, player):
        if player.bank >= 0:
            return ValidationResult(is_valid=False, message=f'Player {player.color} is not in shortfall')
        if not action.slot_id:
            for building in game_state.iter_placed_buildings():
                if building.owner == player.color:
                    return ValidationResult(is_valid=False, message=f'Player {player.color} has building in slot {building.slot_id}, sell it first')
        return ValidationResult(is_valid=True)