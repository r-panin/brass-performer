class Link():
    def __init__(self, city_a:str, city_b:str, city_c=None):
        self.city_a = city_a
        self.city_b = city_b
        if city_c:
            self.city_c = city_c
        self.claimed_by = None
    
    def claim(self, player):
        self.claimed_by = player

    def __repr__(self):
        if not hasattr(self, 'city_c'):
            return f'Link between {self.city_a}, {self.city_b}'
        else:
            return f'Trilink between {self.city_a}, {self.city_b} and {self.city_c}'
