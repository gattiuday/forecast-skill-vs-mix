"""Accuracy metrics, written out rather than imported, because the definitions are the subject.

WMAPE is quoted constantly in demand planning and defined inconsistently. The
form used throughout this package is the volume weighted one:

    WMAPE = sum_i |A_i - F_i| / sum_i A_i

which is algebraically a weighted mean of per SKU absolute percentage errors
with volume shares as the weights. That identity is the whole basis of the
decomposition in `decompose`, so it is asserted by a test rather than assumed.
"""

from __future__ import annotations

import numpy as np

from fsvm.errors import UndefinedMetric

__all__ = ["bias", "mape", "mase", "sku_ape", "volume_shares", "weighted_mean_identity", "wmape"]


def _as_float_array(values) -> np.ndarray:
    arr = np.asarray(values, dtype=float)
    if arr.ndim != 1:
        raise ValueError(f"expected a one dimensional sequence, got shape {arr.shape}")
    if not np.all(np.isfinite(arr)):
        raise ValueError("actuals and forecasts must be finite; found NaN or inf")
    return arr


def _check_pair(actual, forecast) -> tuple[np.ndarray, np.ndarray]:
    a = _as_float_array(actual)
    f = _as_float_array(forecast)
    if a.shape != f.shape:
        raise ValueError(f"actual and forecast lengths differ: {a.size} and {f.size}")
    if a.size == 0:
        raise ValueError("cannot compute an accuracy metric over an empty series")
    if np.any(a < 0):
        raise ValueError("negative actuals are not supported; net them out upstream")
    return a, f


def wmape(actual, forecast) -> float:
    """Volume weighted absolute percentage error over a whole population.

    Raises if total actual demand is zero, because the quantity is then
    undefined rather than zero. A period in which nothing was demanded has no
    forecast accuracy, and reporting 0.0 there would silently flatter every
    aggregate that contains it.
    """
    a, f = _check_pair(actual, forecast)
    denominator = a.sum()
    if denominator <= 0:
        raise UndefinedMetric("WMAPE is undefined when total actual demand is zero")
    return float(np.abs(a - f).sum() / denominator)


def mape(actual, forecast) -> float:
    """Unweighted mean absolute percentage error over SKUs with positive actuals.

    SKUs with zero actual are dropped rather than given an error of zero or
    infinity. The count of dropped SKUs is not returned here on purpose: use
    `sku_ape`, which reports them, whenever that count matters.
    """
    a, f = _check_pair(actual, forecast)
    positive = a > 0
    if not positive.any():
        raise UndefinedMetric("MAPE is undefined when every actual is zero")
    return float(np.mean(np.abs(a[positive] - f[positive]) / a[positive]))


def bias(actual, forecast) -> float:
    """Signed forecast bias as a share of actual volume.

    Positive means over forecasting. Bias is reported alongside WMAPE because
    two forecasts with the same WMAPE can have opposite inventory consequences,
    and WMAPE alone cannot tell them apart.
    """
    a, f = _check_pair(actual, forecast)
    denominator = a.sum()
    if denominator <= 0:
        raise UndefinedMetric("bias is undefined when total actual demand is zero")
    return float((f - a).sum() / denominator)


def sku_ape(actual, forecast) -> tuple[np.ndarray, np.ndarray]:
    """Per SKU absolute percentage error, and the mask of SKUs it is defined for.

    Returns the errors for SKUs with a positive actual, and a boolean mask over
    the original input saying which those were. The mask is returned rather than
    silently applied because the SKUs it excludes are exactly the ones the
    decomposition has to report as unattributable.
    """
    a, f = _check_pair(actual, forecast)
    defined = a > 0
    return np.abs(a[defined] - f[defined]) / a[defined], defined


def volume_shares(actual) -> np.ndarray:
    """Volume shares that sum to one, for use as decomposition weights."""
    a = _as_float_array(actual)
    total = a.sum()
    if total <= 0:
        raise UndefinedMetric("volume shares are undefined when total actual demand is zero")
    return a / total


def weighted_mean_identity(actual, forecast) -> float:
    """WMAPE recomputed as sum(share * per SKU APE), the form the decomposition uses.

    This exists only so a test can assert it equals `wmape` to floating point
    tolerance on populations with no zero actuals. If that identity ever breaks,
    every number the decomposition produces is meaningless, so it is pinned.
    """
    a, f = _check_pair(actual, forecast)
    if np.any(a <= 0):
        raise ValueError("the identity only holds where every actual is positive")
    return float(np.sum(volume_shares(a) * (np.abs(a - f) / a)))


def mase(actual, forecast, naive_forecast) -> float:
    """Mean absolute scaled error against a supplied naive forecast.

    Below one means the forecast beat the naive referee on this series. The
    referee is passed in rather than computed here so that the seasonal period
    is a decision made once, in `baseline`, and visible in the report.
    """
    a, f = _check_pair(actual, forecast)
    n = _as_float_array(naive_forecast)
    if n.shape != a.shape:
        raise ValueError(f"naive forecast length {n.size} does not match actual length {a.size}")
    naive_mae = float(np.mean(np.abs(a - n)))
    if naive_mae <= 0:
        raise UndefinedMetric(
            "MASE is undefined when the naive forecast is exact; "
            "this series is perfectly seasonal and carries no information about skill"
        )
    return float(np.mean(np.abs(a - f)) / naive_mae)
