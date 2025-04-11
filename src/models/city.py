class City():
    def __init__(self, name:str, slots:list, merchant=False):
        self.name = name
        self.slots = slots
        self.merchant = merchant

    def __repr__(self):
        return f'City {self.name}, has slots {self.slots}'
        