from abc import ABC, abstractmethod
from ...schema import BoardState, Action, ResourceAmounts, Player, BuildingAction, ValidationResult, ResourceSource, ResourceType, ResourceSourceType, IndustryType, PassAction, ScoutAction, NetworkAction, DevelopAction, ResourceAction, BuildAction, SellAction, LoanAction, ActionType
from typing import Dict, List
from collections import defaultdict


class ActionValidator(ABC):
    def __init__(self):
        super().__init__()

    @abstractmethod
    def validate(self, action: Action, game_state:BoardState, player: Player):
        pass

def validate_card_in_hand(func, disable=False):
    def wrapper(validator:BaseValidator, action:Action, game_state:BoardState, player:Player):
        if disable:
            return func(validator, action, game_state, player)
        if action.card_id not in player.hand:
            return ValidationResult(False, "Card not in player's hand")
        return func(validator, action, game_state, player)
    return wrapper

def validate_resources(func):
    def wrapper(validator:BaseValidator, action:ResourceAction, game_state:BoardState, player:Player):
        if not action.is_auto_resource_selection():

            preference_validation = validator._validate_iron_preference(game_state, action.resources_used)
            if not preference_validation.is_valid:
                return preference_validation
            
            coal_validation = validator._validate_coal_preference(game_state, action.resources_used,)
            if not coal_validation.is_valid:
                return coal_validation
            
            base_cost_validation = validator._validate_base_action_cost(action, game_state,player)
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
                return ValidationResult(False, "Not enough money in the bank")
        return func(validator, action, game_state, player)
    return wrapper

def validate_building_is_valid(func):
    def wrapper(validator:BaseValidator, action:BuildingAction, game_state:BoardState, player:Player):
        building = action.building_id
        if building not in player.available_buildings:
            return ValidationResult(False, f"Building ID {building} not in player's roster")

        building_validation = validator._validate_lowest_level_building(building, player)
        if not building_validation.is_valid:
            building_validation
        return func(validator, action, game_state, player)
    return wrapper

class BaseValidator(ActionValidator, ABC):
    def validate(self, action:PassAction, game_state:BoardState, player:Player) -> True:
        return ValidationResult(True)
    
    def _validate_lowest_level_building(self, building_id:str, player:Player) -> ValidationResult:
        building = player.available_buildings.get(building_id)
        if not building:
            return ValidationResult(False, f"Building {building_id} is not present in player's roster")
        for b in player.available_buildings.values():
            if b.industry_type == building.industry_type and b.level < building.level:
                return ValidationResult(False, f"Building {b.id} has priority")
        return ValidationResult(True)
    
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
                return ValidationResult(False, "Market resource requested when player resource is available")
        return ValidationResult(True)
            
    def _validate_coal_preference(self, game_state:BoardState, resources: List[ResourceSource], city_name:str=None, link_id:int = None) -> ValidationResult:
        if city_name:
            available_player_sources = game_state.get_player_coal_locations(city_name=city_name)
        elif link_id:
            available_player_sources = game_state.get_player_coal_locations(link_id=link_id)
        else:
            raise ValueError("Must provide either city name or link id")
        asking_amount = sum(resource.amount for resource in resources if resource.resource_type == ResourceType.COAL)
        resource_requests = [resource for resource in resources if resource.resource_type == ResourceType.COAL]
        requested_cities = [game_state.get_building_slot_location(resource.building_slot_id) for resource in resource_requests]
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
            requested_group_consumption = sum(resource.amount for resource in resource_requests if game_state.get_building_slot_location(resource.building_slot_id) in group_cities)
            if requested_group_consumption != expected_group_consumption:
                return ValidationResult(False, f"Cities {group_cities} have coal consumption preference")
            
            remaining_amount -= requested_group_consumption
            if expected_group_consumption < total_group_resource:
                found_incomplete_group = True
        
        market_consumption = sum(resource.amount for resource in resource_requests if resource.source_type == ResourceSourceType.MARKET)
        if found_incomplete_group:
            if market_consumption > 0:
                return ValidationResult(False, "Market access when player resources available")
        else:
            if market_consumption != remaining_amount:
                return ValidationResult(False, "whut?")
            
        return ValidationResult(True)    
    
    def _validate_base_action_cost(self) -> ValidationResult:
        raise ValueError("Must be defined for every resource action")
    
    
class PassValidator(BaseValidator):
    @validate_card_in_hand
    def validate(self, action:ScoutAction, game_state:BoardState, player:Player):
        return ValidationResult(True)
    
class ScoutValidator(BaseValidator):
    @validate_card_in_hand
    def validate(self, action:ScoutAction, game_state:BoardState, player:Player):
        for card in action.additional_card_cost:
            if not card in player.hand:
                return ValidationResult(False, "Smart guy, huh")
        if any(card.value == "wild" for card in player.hand):
            return ValidationResult(False, "Cannot scout with wild cards in hand")
        return ValidationResult(True)

class LoanValidator(BaseValidator):
    @validate_card_in_hand
    def validate(self, action:LoanAction, game_state:BoardState, player:Player):
        if player.income_points < 3:
            return ValidationResult(False, "Income cannot fall below -10")
        return ValidationResult(True)
            
class DevelopValidator(BaseValidator): 
    @validate_card_in_hand
    @validate_resources
    @validate_building_is_valid
    def validate(self, action:DevelopAction, game_state:BoardState, player:Player):
        return ValidationResult(True)
    
    def _validate_base_action_cost(self, action:DevelopAction, game_state, player):
        target_cost = ResourceAmounts(iron=1)
        if action.get_resource_amounts() != target_cost:
            return ValidationResult(False, "Base action cost doesn't match")


class DevelopDoubleValidator(DevelopValidator):
    @validate_card_in_hand(disable=True)
    @validate_building_is_valid
    @validate_resources
    def validate(self, action, game_state, player):
        return super().validate(action, game_state, player)()
    
    def _validate_base_action_cost(self, action, game_state, player):
        return super()._validate_base_action_cost(action, game_state, player)

class DevelopEndValidator(BaseValidator):
    def validate(self, action, game_state, player):
        if not (game_state.previous_actor == player.color and game_state.previous_action in (ActionType.DEVELOP, ActionType.DEVELOP_DOUBLE)):
            return ValidationResult(False, "Action must follow a develop action")
        return ValidationResult(True)

class NetworkValidator(BaseValidator):
    @validate_card_in_hand
    @validate_resources
    def validate(self, action:NetworkAction, game_state:BoardState, player:Player):
        link = game_state.links.get(action.link_id)
        if not link:
            return ValidationResult(False, f"Link {action.link_id} does not exist")
        network = game_state.get_player_network(player.color)
        if not network:
            if not set(link.cities) & network:
                return ValidationResult(False, "Link not in player's network")

    def _validate_base_action_cost(self, action:NetworkAction, game_state:BoardState, player):
        base_link_cost = game_state.get_link_cost()
        if base_link_cost != action.get_resource_amounts():
            return ValidationResult(False, "Base action cost doesn't match")
            

class NetworkDoubleValidator(NetworkValidator):
    @validate_card_in_hand(disable=True)
    def validate(self, action, game_state, player):
        return super().validate(action, game_state, player)
    
    def _validate_base_action_cost(self, action, game_state, player):
        base_link_cost = game_state.get_link_cost(double=True)
        if base_link_cost != action.get_resource_amounts():
            return ValidationResult(False, "Base action cost doens't match")

class NetworkEndValidator(BaseValidator):
    def validate(self, action, game_state, player):
        if not (game_state.previous_actor == player.color and game_state.previous_action is ActionType.NETWORK):
            return ValidationResult(False, "Action must follow a network action. God I hope someone doing double rail didn't get stuck")

class BuildValidator(BaseValidator):
    pass

class SellValidator(BaseValidator):
    pass

class SellStepValidator(BaseValidator):
    pass

class SellEndValidator(BaseValidator):
    pass
