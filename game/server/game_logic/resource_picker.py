from ...schema import Building, ResourceStrategy, ResourceAction, Player, ResourceAmounts, BuildSelection, SellSelection, NetworkSelection, DevelopSelection

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
