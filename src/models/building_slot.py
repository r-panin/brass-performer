from models.building import Building

class BuildingSlot():
    def __init__(self, industries:list):
        self.industries = industries
        
    def claim(self, building:Building, player_color:str):
        self.building = building
        self.claimed_by = player_color

    def __repr__(self):
        if not hasattr(self, 'claimed_by'):
            return f'Empty {self.industries}'
        else:
            return f'{self.building} owned by {self.claimed_by}'
