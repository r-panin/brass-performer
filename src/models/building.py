class Building():
    SELLABLE_TYPES = ('box', 'cotton', 'pottery')

    def __init__(self, b_type:str, level:int):
        self.b_type = b_type
        self.level = level

        self.flipped = False

        self.sellable = self.get_sellable()

    def __repr__(self):
        return f'Building type: {self.b_type}, level: {str(self.level)}'

    @classmethod
    def from_json(cls, b_json: dict):
        building = cls(b_json['b_type'], b_json['level'])
        building.income = b_json['income']
        building.vp = b_json['vp']
        building.conn_vp = b_json['conn_vp']
        building.cost = b_json['cost']
        
        if 'sell_cost' in b_json.keys():
            building.sell_cost = b_json['sell_cost']

        if 'era_exclusion' in b_json.keys():
            building.era_exclusion = b_json['era_exclusion']

        if 'developable' in b_json.keys():
            building.developable = b_json['developable']
        else:
            building.developable = True
        
        if 'resource_count' in b_json.keys():
            building.resource_count = b_json['resource_count']

        return building


    def get_sellable(self):
        if self.b_type in self.SELLABLE_TYPES:
            return True
        return False
    
    def check_flip(self):
        if not self.sellable and self.resources == 0:
            self.flipped = True
        