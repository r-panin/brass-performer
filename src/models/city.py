class City():
    def __init__(self, name:str, slots:list, merchant=False, merchant_goods=None):
        self.name = name
        self.slots = slots
        self.merchant = merchant
        if merchant_goods:
            self.merchant_goods = merchant_goods

    def __repr__(self):
        if not self.merchant:
            return f'City {self.name}, has slots {self.slots}'
        else:
            return f'City {self.name}, buys {self.merchant_goods}'
        