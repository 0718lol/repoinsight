"""入口。"""
from shop.cart import Cart
from shop.models import Item
from shop import utils


def main():
    cart = Cart()
    cart.add(Item("apple", 3.5), 2)
    cart.add(Item("banana", 1.2), 5)
    print(utils.money(cart.lines and pricing_total(cart)))

def pricing_total(cart):
    from shop.pricing import total
    return total(cart.lines)
