from abc import ABC, abstractmethod
from ...schema import BoardState, Action, Building, CardType, ResourceAmounts, Player, BuildingAction, ValidationResult, ResourceSource, ResourceType, ResourceSourceType, IndustryType, PassAction, ScoutAction, NetworkAction, DevelopAction, ResourceAction, BuildAction, SellAction, LoanAction, ActionType
from typing import Dict, List
from collections import defaultdict


class ActionValidator(ABC):
    def __init__(self):
        super().__init__()

    @abstractmethod
    def validate(self, action: Action, game_state:BoardState, player: Player):
        pass

def validate_card_in_hand(disable=False):
    def decorator(func):
        def wrapper(self:BaseValidator, action:Action, game_state:BoardState, player:Player):
            if disable:
                return func(self, action, game_state, player)
            if action.card_id not in player.hand:
                return ValidationResult(is_valid=False, message="Card not in player's hand")
            return func(self, action, game_state, player)
        return wrapper
    return decorator

def validate_move_order(func):
    def wrapper(self:BaseValidator, action:Action, game_state:BoardState, player:Player):
        if game_state.current_turn != player.color:
            return ValidationResult(is_valid=False, message=f"Attempted move by {player.color}, current turn is {game_state.current_turn}")
        return func(self, action, game_state, player)
    return wrapper

def validate_resources(func):
    def wrapper(self:BaseValidator, action:ResourceAction, game_state:BoardState, player:Player):
        if not action.is_auto_resource_selection():

            preference_validation = self._validate_iron_preference(game_state, action.resources_used)
            if not preference_validation.is_valid:
                return preference_validation
            
            coal_validation = self._validate_coal_preference(game_state, action.resources_used,)
            if not coal_validation.is_valid:
                return coal_validation
            
            base_cost_validation = self._validate_base_action_cost(action, game_state,player)
            if not base_cost_validation.is_valid:
                return base_cost_validation

            market_coal = [resource for resource in action.resources_used if resource.source_type == ResourceSourceType.MARKET and resource.resource_type == ResourceType.COAL]
            market_coal_amount = sum(resource.amount for resource in market_coal)
            market_iron = [resource for resource in action.resources_used if resource.source_type == ResourceSourceType.MARKET and resource.resource_type == ResourceType.IRON]
            market_iron_amount = sum(resource.amount for resource in market_iron)
            resource_expense = game_state.market.calculate_coal_cost(market_coal_amount) + game_state.market.calculate_iron_cost(market_iron_amount)
            base_expense = sum(resource.amount for resource in action.resources_used if resource.resource_type == ResourceType.MONEY)
            total_expense = base_expense + resource_expense
            if total_expense > player.bank:
                return ValidationResult(is_valid=False, message="Not enough money in the bank")
        return func(self, action, game_state, player)
    return wrapper

def validate_building_is_valid(func):
    def wrapper(self:BaseValidator, action:BuildingAction, game_state:BoardState, player:Player):
        building = action.building_id
        if building not in player.available_buildings:
            return ValidationResult(is_valid=False, message=f"Building ID {building} not in player's roster")

        building_validation = self._validate_lowest_level_building(building, player)
        if not building_validation.is_valid:
            building_validation
        return func(self, action, game_state, player)
    return wrapper

class BaseValidator(ActionValidator, ABC):
    def validate(self, action:PassAction, game_state:BoardState, player:Player) -> True:
        return ValidationResult(is_valid=True)
    
    def _validate_lowest_level_building(self, building_id:str, player:Player) -> ValidationResult:
        building = player.available_buildings.get(building_id)
        if not building:
            return ValidationResult(is_valid=False, message=f"Building {building_id} is not present in player's roster")
        for b in player.available_buildings.values():
            if b.industry_type == building.industry_type and b.level < building.level:
                return ValidationResult(is_valid=False, message=f"Building {b.id} has priority")
        return ValidationResult(is_valid=True)
    
    def _validate_iron_preference(self, game_state:BoardState, resources: List[ResourceSource]) -> ValidationResult:
        if any(resource.source_type == ResourceSourceType.MARKET and resource.resource_type == ResourceType.IRON for resource in resources):
            available_player_amount = sum(source.resource_count for source in game_state.get_player_iron_sources() if source.industry_type == IndustryType.IRON)
            asking_amount = 0
            asking_market_amount = 0
            for resource in resources:
                if resource.resource_type == ResourceType.IRON:
                    asking_amount += resource.amount
                    if resource.source_type == ResourceSourceType.MARKET:
                        asking_market_amount += resource.amount
            if asking_amount - asking_market_amount != available_player_amount:
                return ValidationResult(is_valid=False, message="Market resource requested when player resource is available")
        return ValidationResult(is_valid=True)
            
    def _validate_coal_preference(self, game_state:BoardState, resources: List[ResourceSource], city_name:str=None, link_id:int = None) -> ValidationResult:
        if city_name:
            available_player_sources = game_state.get_player_coal_locations(city_name=city_name)
        elif link_id:
            available_player_sources = game_state.get_player_coal_locations(link_id=link_id)
        else:
            raise ValueError("Must provide either city name or link id")
        asking_amount = sum(resource.amount for resource in resources if resource.resource_type == ResourceType.COAL)
        resource_requests = [resource for resource in resources if resource.resource_type == ResourceType.COAL]
        requested_cities = [game_state.get_building_slot(resource.building_slot_id, get_city_name=True) for resource in resource_requests]
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
            requested_group_consumption = sum(resource.amount for resource in resource_requests if game_state.get_building_slot(resource.building_slot_id, get_city_name=True) in group_cities)
            if requested_group_consumption != expected_group_consumption:
                return ValidationResult(is_valid=False, message=f"Cities {group_cities} have coal consumption preference")
            
            remaining_amount -= requested_group_consumption
            if expected_group_consumption < total_group_resource:
                found_incomplete_group = True
        
        market_consumption = sum(resource.amount for resource in resource_requests if resource.source_type == ResourceSourceType.MARKET)
        if found_incomplete_group:
            if market_consumption > 0:
                return ValidationResult(is_valid=False, message="Market access when player resources available")
        else:
            if market_consumption != remaining_amount:
                return ValidationResult(is_valid=False, message="whut?")
            
        return ValidationResult(True)    
    
    def _validate_base_action_cost(self) -> ValidationResult:
        raise ValueError("Must be defined for every resource action")
    
    
class PassValidator(BaseValidator):
    @validate_move_order
    @validate_card_in_hand()
    def validate(self, action:ScoutAction, game_state:BoardState, player:Player):
        return ValidationResult(is_valid=True)
    
class ScoutValidator(BaseValidator):
    @validate_move_order
    @validate_card_in_hand()
    def validate(self, action:ScoutAction, game_state:BoardState, player:Player):
        for card in action.additional_card_cost:
            if not card in player.hand:
                return ValidationResult(is_valid=False, message="Smart guy, huh")
        if any(card.value == "wild" for card in player.hand):
            return ValidationResult(is_valid=False, message="Cannot scout with wild cards in hand")
        return ValidationResult(is_valid=True)

class LoanValidator(BaseValidator):
    @validate_move_order
    @validate_card_in_hand()
    def validate(self, action:LoanAction, game_state:BoardState, player:Player):
        if player.income_points < 3:
            return ValidationResult(is_valid=False, message="Income cannot fall below -10")
        return ValidationResult(is_valid=True)
            
class DevelopValidator(BaseValidator): 
    @validate_move_order
    @validate_card_in_hand()
    @validate_building_is_valid
    @validate_resources
    def validate(self, action:DevelopAction, game_state:BoardState, player:Player):
        return ValidationResult(is_valid=True)
    
    def _validate_base_action_cost(self, action:DevelopAction, game_state, player):
        target_cost = ResourceAmounts(iron=1)
        if action.get_resource_amounts() != target_cost:
            return ValidationResult(is_valid=False, message="Base action cost doesn't match")


class DevelopDoubleValidator(DevelopValidator):
    @validate_move_order
    @validate_card_in_hand(disable=True)
    @validate_building_is_valid
    @validate_resources
    def validate(self, action, game_state, player):
        return super().validate(action, game_state, player)()
    
    def _validate_base_action_cost(self, action, game_state, player):
        return super()._validate_base_action_cost(action, game_state, player)

class DevelopEndValidator(BaseValidator):
    @validate_move_order
    def validate(self, action, game_state, player):
        if not (game_state.previous_actor == player.color and game_state.previous_action in (ActionType.DEVELOP, ActionType.DEVELOP_DOUBLE)):
            return ValidationResult(is_valid=False, message="Action must follow a develop action")
        return ValidationResult(is_valid=True)

class NetworkValidator(BaseValidator):
    @validate_move_order
    @validate_card_in_hand()
    @validate_resources
    def validate(self, action:NetworkAction, game_state:BoardState, player:Player):
        link = game_state.links.get(action.link_id)
        if not link:
            return ValidationResult(is_valid=False, message=f"Link {action.link_id} does not exist")
        
        if link.owner is not None:
            return ValidationResult(is_valid=False, message=f"Link {link.id} is already owned by {link.owner}")
        
        network = game_state.get_player_network(player.color)
        if not network:
            if not set(link.cities) & network:
                return ValidationResult(is_valid=False, message="Link not in player's network")

    def _validate_base_action_cost(self, action:NetworkAction, game_state:BoardState, player):
        base_link_cost = game_state.get_link_cost()
        if base_link_cost != action.get_resource_amounts():
            return ValidationResult(is_valid=False, message="Base action cost doesn't match")
            

class NetworkDoubleValidator(NetworkValidator):
    @validate_move_order
    @validate_card_in_hand(disable=True)
    def validate(self, action, game_state, player):
        return super().validate(action, game_state, player)
    
    def _validate_base_action_cost(self, action, game_state, player):
        base_link_cost = game_state.get_link_cost(double=True)
        if base_link_cost != action.get_resource_amounts():
            return ValidationResult(is_valid=False, message="Base action cost doens't match")

class NetworkEndValidator(BaseValidator):
    @validate_move_order
    def validate(self, action, game_state, player):
        if not (game_state.previous_actor == player.color and game_state.previous_action is ActionType.NETWORK):
            return ValidationResult(is_valid=False, message="Action must follow a network action. God I hope someone doing double rail didn't get stuck")
        return ValidationResult(is_valid=True)

class BuildValidator(BaseValidator):
    OVERBUILDABLE = (IndustryType.IRON, IndustryType.COAL)

    @validate_move_order
    @validate_card_in_hand()
    @validate_building_is_valid
    @validate_resources
    def validate(self, action:BuildAction, game_state, player):
        card = player.hand[action.card_id]
        building = player.available_buildings[action.building_id]
        slot = game_state.get_building_slot(action.slot_id)
        if card.card_type == CardType.INDUSTRY:
            if building.industry_type not in card.value:
                return ValidationResult(is_valid=False, message=f"Card valude {card.value} doesn't contain the industry {building.industry_type}")
            
        elif card.card_type == CardType.CITY:
            if slot.city != card.value:
                return ValidationResult(is_valid=False, message=f"Card value {card.value} doesn't match city {slot.city}")
            
        else:
            return ValidationResult(is_valid=False, message='wut?')
        
        if building.industry_type not in slot.industry_type_options:
            return ValidationResult(is_valid=False, message=f"Can't build {building.industry_type} in a slot that supports {slot.industry_type_options}")
        
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

    def _validate_base_action_cost(self, action:BuildAction, game_state, player:Player):
        building = player.available_buildings[action.building_id]
        if building.get_cost() != action.get_resource_amounts():
            return ValidationResult(is_valid=False, message="Building base cost doens't match resource selecion")
        return ValidationResult(is_valid=True)

class SellValidator(BaseValidator):
    @validate_move_order
    @validate_card_in_hand()
    def validate(self, action:SellAction, game_state:BoardState, player:Player):
        slot = game_state.get_building_slot(action.slot_id)
        if not slot.building_placed:
            return ValidationResult(is_valid=False, message=f"Slot {action.slot_id} does not contain a building")
        
        if slot.building_placed.owner != player.color:
            return ValidationResult(is_valid=False, message=f"Slot {action.slot_id} is occupied by a building owned by player {player.color} who is not the current actor")
        
        if ResourceSourceType.MERCHANT in action.resources_used:
            merchant_names = [resource.merchant for resource in action.resources_used if resource.merchant is not None]
            if merchant_names != set(merchant_names):
                return ValidationResult(is_valid=False, message="Cannot use two merchant beers in one sell action")
            
            for name in merchant_names:
                if not game_state.find_paths(start=slot.city, end=name):
                    return ValidationResult(is_valid=False, message=f"No path to merchant {name}")
                
        if not game_state.can_sell(slot.city, slot.building_placed.industry_type):
            return ValidationResult(is_valid=False, message=f"No path from city {slot.city} to eligible merchants for industry {slot.building_placed.industry_type}")
        
        offered_amounts = action.get_resource_amounts()
        required_amounts = ResourceAmounts(beer=slot.building_placed.sell_cost)
        if offered_amounts != required_amounts:
            return ValidationResult(is_valid=False, message=f"Action requires {required_amounts}, offered are {offered_amounts}")


class SellStepValidator(SellValidator):
    @validate_move_order
    @validate_card_in_hand(disable=True)
    def validate(self, action, game_state, player):
        return super().validate(action, game_state, player)

class SellEndValidator(BaseValidator):
    @validate_move_order
    def validate(self, action, game_state, player):
        allowed_from = (ActionType.SELL, ActionType.SELL_STEP)
        if not (game_state.previous_actor == player.color and game_state.previous_action in allowed_from):
            return ValidationResult(is_valid=False, message=f"Action must follow actions {allowed_from}, is following {game_state.previous_action}")
        return True
