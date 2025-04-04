class Link():
    def __init__(self, city_a:str, city_b:str, tri_link=False):
        self.city_a = city_a
        self.city_b = city_b
    
    def claim(self, p_color:str):
        self.claimed_by = p_color

    def __repr__(self):
        return f'Link between {self.city_a}, {self.city_b}'
