# ADR-001: Decompose the WMAPE change rather than reporting a better portfolio metric

Status: accepted

## Context

The question that started this repository is one a planner is asked every quarter:
"forecast accuracy improved, was that us?" The usual answer is a portfolio WMAPE for
each period and the difference between them. That difference is real, and it cannot
answer the question.

WMAPE over a population is a volume weighted mean of per SKU absolute percentage
errors. Two things move between periods: the errors and the weights. A single number
computed from both carries both causes and has no structure that separates them. This
is not a precision problem that a better metric fixes. It is an aggregation identity,
and the information is destroyed at the point of aggregation.

The obvious alternatives were considered and rejected:

- **Report MAPE instead.** Unweighted MAPE removes the volume weights, so it does not
  move with mix. It also makes a forty dollar long tail SKU count the same as a four
  hundred thousand dollar one, which is why nobody plans with it. Swapping one
  aggregation problem for a worse one is not a fix.
- **Report accuracy per category.** This helps where the mix shift happens between
  categories and does nothing where it happens inside one. Since category definitions
  are a merchandising artefact, this makes the answer depend on an org chart.
- **Compare like for like on a fixed SKU list.** This is a real technique and it is
  what the restricted population in this tool is. On its own it silently drops the
  entrants and exits, which on this repository's fixture carry a measurable share of
  the change. Dropping them without saying so is the specific failure this tool is
  built to avoid.

## Decision

Decompose the change into a skill effect (errors moving at fixed weights), a mix
effect (weights moving at fixed errors), and an explicitly reported unattributable
remainder for the SKUs on which no decomposition is defined.

Report all three. Never report the skill effect alone.

## Consequences

The output is harder to put on a slide than one number, which is the point: the one
number was not answerable. A planner now has to say which part of an improvement they
are claiming, and the tool makes the unclaimed part visible rather than absent.

The decomposition needs a convention, and conventions disagree. ADR-002 handles that.

A SKU that launched, was discontinued, or went dormant for a whole period has no
counterfactual, so it is outside the decomposition by construction. ADR-005 records
what that costs and when the whole method stops being applicable.
