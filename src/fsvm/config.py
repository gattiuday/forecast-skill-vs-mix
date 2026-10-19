"""Thresholds and conventions in one place, so no magic number hides in a function.

Every value here is a judgement call rather than a fact, which is why they are
collected rather than inlined. A reviewer who disagrees with one of them can see
all of them at once and change the one they mean.
"""

from dataclasses import dataclass

#: Decomposition conventions this package implements. See ADR-002.
CONVENTIONS = ("laspeyres", "paasche", "three_term", "shapley")

#: The convention reported by default. Shapley is symmetric in the two periods,
#: so it does not silently privilege the base period the analyst happened to pick.
DEFAULT_CONVENTION = "shapley"


@dataclass(frozen=True)
class Thresholds:
    """Decision thresholds for the CLI verdict.

    min_overlap_skus
        Below this many SKUs present in both periods, no attribution is attempted.
    max_churn_share
        If more SKUs than this share of period one volume are unattributable
        (entrants, exits, or zero actual), the verdict is withheld rather than
        reported with a caveat nobody reads.
    bootstrap_samples
        Resamples used for the confidence interval on the skill effect.
    ci_level
        Two sided confidence level for that interval.
    """

    min_overlap_skus: int = 30
    max_churn_share: float = 0.35
    bootstrap_samples: int = 2000
    ci_level: float = 0.90


DEFAULTS = Thresholds()
