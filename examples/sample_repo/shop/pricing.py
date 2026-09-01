"""计价:依赖模型层。

问题演示:又导回了 cart.py,和 cart.py 形成环。
"""
from shop import cart
from shop.models import Item


def total(lines):
    return round(sum(item.price * qty for item, qty in lines), 2)


def make_cart():
    return cart.Cart()
