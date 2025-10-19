import json
from pathlib import Path
from typing import Dict, List
from ....schema import Building, ResourceType, ResourceAmounts, IndustryType
from collections import defaultdict


class BuildingProvider:
    BUILDING_ROSTER_PATH = Path(__file__).resolve().parent.parent.parent / 'res' / 'building_table.json'
    _instance = None
    _initialized = False

    def __new__(cls, *args, **kwargs):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
        return cls._instance

    def __init__(self):
        if not self._initialized:
            self.building_roster = self._build_building_roster()
            self.initialized = True
    
    def _build_building_roster(self) -> Dict[IndustryType, list[Building]]:
        buildings_by_industry = defaultdict(list)
        with open(self.BUILDING_ROSTER_PATH) as openfile:
            building_json:List[dict] = json.load(openfile)
        for building in building_json:
            cost_json = building['cost']
            cost = ResourceAmounts(
                iron=int(cost_json.get('iron', cost_json.get(ResourceType.IRON, 0))),
                coal=int(cost_json.get('coal', cost_json.get(ResourceType.COAL, 0))),
                beer=int(cost_json.get('beer', cost_json.get(ResourceType.BEER, 0))),
                money=int(cost_json.get('money', 0))
            )
            b = Building(
                id=building['id'],
                industry_type=building['industry'],
                level=building['level'],
                owner=None,
                flipped=False,
                cost=cost,
                resource_count=building.get('resource_count', 0),
                victory_points=building['vp'],
                sell_cost=building.get('sell_cost'),
                is_developable=building.get('developable', True),
                link_victory_points=building['conn_vp'],
                era_exclusion=building.get('era_exclusion'),
                income=building['income']
            )
            buildings_by_industry[b.industry_type].append(b)
        for ind in buildings_by_industry.values():
            ind.sort(key=lambda b: b.level)
        return buildings_by_industry

    def get_building(self, industry, index):
        if index <= self.get_max_index(industry):
            return self.building_roster[industry][index]
        return None

    def get_max_index(self, industry):
        return len(self.building_roster[industry]) - 1