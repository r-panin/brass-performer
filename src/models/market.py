class Market():
    def __init__(self):
        self.iron_cost = 2
        self.iron_count = 2
        self.coal_cost = 1
        self.coal_count = 1

        self.iron_max_cost = 6
        self.coal_max_cost = 8

    def buy_iron(self, amount):
        for _ in range(amount, 0, -1):
            cost += self.iron_cost
            if self.iron_cost < self.iron_max_cost:
                self.iron_count -= 1
            if self.iron_count == 0:
                self.iron_cost += 1
                self.iron_count = 2
        return cost

    def buy_coal(self, amount):
        for _ in range(amount, 0, -1):
            cost += self.coal_cost
            if self.coal_cost < self.coal_max_cost:
                self.coal_count -= 1
            if self.coal_count == 0:
                self.coal_cost += 1
                self.coal_count = 2
        return cost
    
    def sell_iron(self, amount):
        value = 0
        for _ in range(amount, 0, -1):
            if self.iron_cost == 1 and self.iron_count == 2:
                break
            if self.iron_count == 2:
                self.iron_cost -= 1
                self.iron_count = 0
            value += self.iron_cost
            self.iron_count += 1
        return value

    def sell_coal(self, amount):
        value = 0
        for _ in range(amount, 0, -1):
            if self.coal_cost == 1 and self.coal_count == 2:
                break
            if self.coal_count == 2:
                self.coal_cost -= 1
                self.coal_count = 0
            value += self.coal_cost
            self.coal_count += 1
        return value
