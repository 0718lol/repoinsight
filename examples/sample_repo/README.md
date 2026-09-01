"""示例项目:一个迷你的「商店」程序,故意埋了一些典型问题供演示。

已知问题(用 repoinsight lint 能全部抓出来):
  1. shop/cart.py 和 shop/pricing.py 互相导入(循环依赖)
  2. shop/utils.py 的 format_receipt 没有任何人调用(死代码)
  3. shop/ui.py 违反分层:界面层直接调用了存储层 storage.load_items
"""
