"""Attribution of a change in portfolio forecast accuracy between skill and mix.

A portfolio WMAPE is a volume weighted average of per SKU errors. When the SKU
population or its volume weights change between two periods, the change in that
average carries two causes that the average itself cannot separate. This package
separates them where separation is defined, and refuses to where it is not.
"""

from fsvm.metrics import bias, mape, mase, sku_ape, volume_shares, wmape

__all__ = ["bias", "mape", "mase", "sku_ape", "volume_shares", "wmape"]
__version__ = "0.3.0"
