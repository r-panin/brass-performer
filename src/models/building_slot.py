from src.models.building import Building

class BuildingSlot():
    def __init__(self, industries:list):
        self.industries = industries
        self.claimed_by = None
        
    def build(self, building:Building, player):
        self.building = building
        self.claimed_by = player

    def __repr__(self):
        if not self.claimed_by:
            return f'Empty {self.industries}'
        else:
            return f'{self.building} owned by {self.claimed_by.color}'
