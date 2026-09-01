"""数据模型:被所有人依赖,自己不依赖任何人。"""


class Item:
    def __init__(self, name, price):
        self.name = name
        self.price = price
