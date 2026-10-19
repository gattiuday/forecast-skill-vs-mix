# ADR-002: Report four decomposition conventions rather than choosing one

Status: accepted

## Context

Splitting a change into two factor effects requires deciding which period's values to
hold constant while the other varies. That choice is a convention, not a measurement,
and the standard ones disagree:

- **Laspeyres** holds mix at the base period for the skill term, so the mix term
  absorbs the cross product.
- **Paasche** mirrors it, holding mix at the comparison period.
- **Three term** keeps the cross product visible as its own interaction effect rather
  than assigning it.
- **Shapley** splits the cross product evenly, which is the Shapley value of the two
  factor cooperative game and is symmetric in the two periods.

On this repository's fixture the four put between 33% and 48% of the improvement on
skill: a spread of 0.43 points of WMAPE on a 2.86 point improvement. That spread is not
noise and it is not error. It is the size of the arbitrary step.

## Decision

Compute all four. Report the full table by default, with the spread stated explicitly.
Use Shapley for the headline number and the verdict, because it is the only one of the
four that is symmetric in the two periods and therefore does not depend on which period
the analyst happened to call the base.

## Alternatives considered

**Report Shapley alone.** Shorter output, and dishonest in a specific way: it presents a
convention dependent number as though it were measured. A reviewer who knows the field
would ask which convention, and the tool should answer before being asked.

**Let the user choose and report only their pick.** This is what `--convention` does for
the verdict, but the printed table always shows all four, so a user cannot quietly pick
the convention that flatters them without the alternative sitting next to it.

**Compute a confidence interval over conventions.** Rejected as a category error. The
four conventions are not samples from a distribution; they are four definitions. An
interval over them would imply a sampling process that does not exist.

## Consequences

The report is wider and a reader has to be told what the spread means. In exchange, the
tool never claims more precision than the method has. Where the spread approaches the
effect itself, the honest reading is that the split is not determined by the data, and
the table shows that without any extra machinery.

`convention_spread` is tested to be identical for the skill and mix effects, because
both are fixed to the same total; if those ever diverge, the decomposition is not exact
and `test_every_convention_sums_exactly_to_the_restricted_delta` is the first thing to
look at.
