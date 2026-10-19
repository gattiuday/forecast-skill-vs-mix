"""One exception type, so the CLI can distinguish "answered no" from "could not answer".

Exit code 1 means the analysis ran and the answer was unfavourable. Exit code 2
means the analysis could not be run at all. Collapsing those two into a single
non zero code is the most common way a CI gate becomes uninterpretable, so the
distinction is carried by an exception type rather than by a string match.
"""


class AttributionError(Exception):
    """Raised when the input cannot support an attribution at all."""


class InsufficientOverlap(AttributionError):
    """Raised when too few SKUs appear in both periods to decompose anything."""


class UndefinedMetric(AttributionError, ValueError):
    """Raised when a metric is not defined on the data, as opposed to miscalled.

    Subclasses both deliberately. It is a ValueError because that is what a
    caller computing a mean over an empty series expects to catch, and it is an
    AttributionError because, at the CLI boundary, it means the tool declined to
    answer rather than that the user mistyped a flag.

    That boundary is why the type exists. Inferring "cannot answer" from the
    exception class alone was a guess, and it produced a CLI that mapped a
    genuine usage error and a genuine domain refusal to the same code in one
    direction and to the wrong one in the other. An audit found the contract
    and the code disagreeing; this makes the distinction structural, so the
    handler reads the author's intent rather than reconstructing it.
    """
