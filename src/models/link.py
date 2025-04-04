class Link():
    def __init__(self, city_a, city_b, tri_link=False):
        self.city_a = city_a,
        self.city_b = city_b
    
    def claim(self, p_color:str):
        self.claimed_by = p_color
