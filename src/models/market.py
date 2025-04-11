class Market():
    def __init__(self):
        self.iron_stock = 8
        self.coal_stock = 13

        self.iron_max_stock = 6
        self.coal_max_stock = 8

    def calculate_cost(self, amount:int, resource_type:str, purchase:bool):
        if resource_type == 'iron':
            target_stock = self.iron_stock + (-amount if purchase else amount)
            cost = self._get_cost(self.iron_stock, target_stock, 'iron')
        elif resource_type == 'coal':
            target_stock = self.coal_stock + (-amount if purchase else amount)
            cost = self._get_cost(self.coal_stock, target_stock, 'coal')
        return cost
    
    def execute_trade(self, amount:int, resource_type:str, purchase:bool):
        cost = self.calculate_cost(amount, resource_type, purchase)
        if resource_type == 'iron':
            self.iron_stock += (-amount if purchase else amount)
            if self.iron_stock < 0:
                self.iron_stock = 0
            elif self.iron_stock > self.iron_max_stock:
                self.iron_stock = self.iron_max_stock
        elif resource_type == 'coal':
            if self.coal_stock < 0:
                self.coal_stock = 0
            elif self.coal_stock > self.coal_max_stock:
                self.coal_stock = self.coal_max_stock
            self.coal_stock += (-amount if purchase else amount)
        return cost

