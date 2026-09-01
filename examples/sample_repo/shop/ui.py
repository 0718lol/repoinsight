"""界面层。

问题演示:界面层本不该直接碰存储层,这里违反了分层规则。
"""
from shop import pricing, storage, utils


def show_cart():
    items = storage.load_items()
    lines = [(utils.money(p), 1) for _, p in items]
    return pricing.total([(type("X", (), {"price": p, "name": n})(), 1) for n, p in items]) if lines else 0
