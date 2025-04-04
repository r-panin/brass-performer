class City():
    def __init__(self, name:str, links:list, slots:list, merchant=False):
        self.name = name
        self.links = links
        self.slots = slots
        self.merchant = merchant

    def __repr__(self):
        return f'City {self.name}, has connections {self.links}, has slots {self.slots}'
        