class Link():
    def __init__(self, city_a:str, city_b:str, tri_link=False):
        self.city_a = city_a
        self.city_b = city_b
        self.claimed_by = None
    
    def claim(self, player):
        self.claimed_by = player

    def __repr__(self):
        return f'Link between {self.city_a}, {self.city_b}'
