from abc import ABC, abstractmethod
from ...schema import BoardState, Action, Player, ValidationResult, ResourceSource, ResourceType, ResourceSourceType, IndustryType, PassAction, ScoutAction, NetworkAction, DevelopAction, BuildAction, SellAction, LoanAction
from typing import Dict, List
from collections import defaultdict


class ActionValidator(ABC):
    def __init__(self):
        super().__init__()

    @abstractmethod
    def validate(self, action: Action, game_state:BoardState, player: Player):
        pass

def validate_card_in_hand(func):
    def wrapper(validator:BaseValidator, action:Action, game_state:BoardState, player:Player):
        if action.card_id not in player.hand:
            return ValidationResult(False, "Card not in player's hand")
        return func(validator, action, game_state, player)
    return wrapper

class BaseValidator(ActionValidator, ABC):
    @validate_card_in_hand
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
            
    def _validate_coal_preference(self, game_state:BoardState, resources: List[ResourceSource], location:str) -> ValidationResult:
        available_player_sources = game_state.get_player_coal_sources(location)
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
    
    
class PassValidator(BaseValidator):
    pass

class ScoutValidator(BaseValidator):
    @validate_card_in_hand
    def validate(self, action:ScoutAction, game_state:BoardState, player:Player):
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
    def validate(self, action:DevelopAction, game_state:BoardState, player:Player):
        if action.buildings > 2:
            return ValidationResult(False, "Cannot develop over 2 buildings in one action")
        for building in action.buildings:
            if building not in player.available_buildings:
                return ValidationResult(False, f"Building ID {building} not in player's roster")
            building_validation = self._validate_lowest_level_building(building, player)
            if not building_validation.is_valid:
                building_validation
        for resource in action.resources_used:
            if resource.resource_type != ResourceType.IRON:
                return ValidationResult(False, "Must only use iron to develop")
        preference_validation = self._validate_iron_preference(game_state, action.resources_used)
        if not preference_validation.is_valid:
            return preference_validation
        if sum(resource.amount for resource in action.resources_used) != len(action.buildings):
            return ValidationResult(False, "Must use amount of iron equal to the number of buildings developed")
        market_resources = [resource for resource in action.resources_used if resource.source_type == ResourceSourceType.MARKET]
        market_amount = sum(resource.amount for resource in market_resources)
        if game_state.market.calculate_iron_cost() > player.bank:
            return ValidationResult(False, "Not enough money in the bank")
        return True