"""工具函数。format_receipt 是一个没人用的死函数。"""


def money(v):
    return f"¥{v:.2f}"


def format_receipt(lines, total_value):
    rows = "\n".join(f"{item.name} x{qty} = {money(item.price * qty)}" for item, qty in lines)
    return f"{rows}\n合计:{money(total_value)}"
