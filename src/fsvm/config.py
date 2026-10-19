"""Thresholds and conventions in one place, rather than inline at the point of use.

Every value here is a judgement call rather than a fact, which is why they are
collected: a reviewer who disagrees with one can see all of them at once and
change the one they mean.

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
    bootstrap_seed
        Fixed so a published interval is reproducible. An audit found this
        hardcoded inside the resampler, where nobody arguing with the interval
        would have found it.
    season_weeks
        Lag of the naive referee. 52 for weekly retail demand.
    min_scored_weeks
        A SKU needs this many scorable weeks after the split to be graded at
        all. This one is not cosmetic: it decides which SKUs reach the beat
        rate and therefore moves that headline figure directly, which is why it
        sits here rather than in `baseline`.
    """

    min_overlap_skus: int = 30
    max_churn_share: float = 0.35
    bootstrap_samples: int = 2000
    ci_level: float = 0.90
    bootstrap_seed: int = 20260419
    season_weeks: int = 52
    min_scored_weeks: int = 4


DEFAULTS = Thresholds()
