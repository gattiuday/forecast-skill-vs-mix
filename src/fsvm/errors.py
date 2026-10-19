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
