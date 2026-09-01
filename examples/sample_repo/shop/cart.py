"""购物车:依赖模型层。

问题演示:这里与 pricing.py 互相导入,构成循环依赖。
"""
from shop import pricing


class Cart:
    def __init__(self):
        self.lines = []

    def add(self, item, qty):
        self.lines.append((item, qty))
        return pricing.total(self.lines)
