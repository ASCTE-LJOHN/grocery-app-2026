# models.py
class Product:
    def __init__(self, id=None, name=None, price=None, category=None):
        self.id = id
        self.name = name
        self.price = price
        self.category = category

    def to_dict(self):
        return {
            'id': self.id,
            'name': self.name,
            'price': self.price,
            'category': self.category
        }