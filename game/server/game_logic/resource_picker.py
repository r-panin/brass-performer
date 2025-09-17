from ...schema import Building, ResourceStrategy, ResourceAction, Player, BuildSelection, SellSelection, NetworkSelection, ResourceSource
from typing import List

class ResourcePicker():
    def __init__(self, state_manager):
        self.state_manager = state_manager
    
    def calcualte_resource_score(self, building:Building, strategy:ResourceStrategy, color) -> float:
        match type(strategy):
            case ResourceStrategy.MAXIMIZE_INCOME:
                return building.income / building.resource_count if building.owner == color else -(building.income / building.resource_count)
            case ResourceStrategy.MAXIMIZE_VP:
                vp_score = building.victory_points if building.owner == color else -building.victory_points
                city = self.state.get_building_slot(building.slot_id).city
                for link in self.state.links.values():
                    if city in link.cities:
                        if link.owner == color:
                            vp_score += building.link_victory_points
                        elif link.owner is not None:
                            vp_score -= building.link_victory_points
                return vp_score
        return 0 

    def _select_resources(self, action:ResourceAction, player:Player) -> List[ResourceSource]:
        amounts = self.get_resource_amounts(action, player)
        out = []
        if action.resources_used.strategy is ResourceStrategy.MERCHANT_FIRST:
            merchant_first = True
            strategy = action.resources_used.then
        else:
            strategy = action.resources_used.strategy

        if isinstance(action, (BuildSelection, SellSelection)):
            action_city = self.state.get_building_slot(action.slot_id).city
            link_id = None
        elif isinstance(action, NetworkSelection):
            action_city = None
            link_id = action.link_id

        if amounts.iron:
            iron_buildings = self.state.get_player_iron_sources()
            with_scores = [(building,
                            self.calculate_resource_score(building, strategy))
                            for building in iron_buildings]
            with_scores.sort(key=lambda x: x[1], reverse=True)
            taken_iron = 0


        if amounts.coal:
            coal_buildings = self.state.get_player_coal_sources(city_name=action_city, link_id=link_id)

        if amounts.beer:
            beer_buildings = self.state.get_player_beer_sources(city_name=action_city, link_id=link_id)
        # TODO