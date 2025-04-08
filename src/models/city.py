class City():
    def __init__(self, name:str, slots:list, links:list, merchant=False):
        self.name = name
        self.slots = slots
        self.merchant = merchant
        self.links = links

    def __repr__(self):
        return f'City {self.name}, has connections {self.links}, has slots {self.slots}'
        