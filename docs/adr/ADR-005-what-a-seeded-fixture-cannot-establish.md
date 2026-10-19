# ADR-005: What a seeded fixture can and cannot establish

Status: accepted

## Context

Every number in this repository is measured against a seeded generator rather than
against a real demand history. That is a deliberate trade and it has a boundary. This
ADR states which claims survive the fixture and which one genuinely needs real data,
because a reviewer is entitled to know before they decide what the numbers are worth.

Validating an attribution tool on real data is circular in a specific way: the quantity
you want to check, the true split between skill and mix, is unobservable. There is no
real dataset with a labelled answer. So the fixture is not a convenience here, it is the
only way to grade the method at all.

## Claims the fixture fully establishes

These would be identical against real data, because they are properties of the
arithmetic rather than of the demand:

- **The decomposition is exact.** All four conventions sum to the restricted delta to
  floating point tolerance, on any input. Pinned for every convention.
- **The decomposition recovers a planted answer.** On a panel constructed so the true
  skill effect is exactly zero, every convention returns zero to 5 orders of magnitude
  below the change being decomposed. The residual is CSV rounding, not method error. The
  exponent is rounded up rather than down, because rounding a precision claim in the
  flattering direction is the one rounding a precision claim may not do.
- **The conventions disagree, and by how much on a given panel.** A property of the
  definitions.
- **The exit code contract.** Behavioural, not statistical.
- **The extract format sensitivity.** The 18.9 point swing under a positional referee is
  a property of the alignment logic meeting a sparse extract. Any real sparse extract
  would show the same class of error, though its size would differ.

## Claims the fixture establishes only conditionally

- **The sample size needed to detect a skill effect.** `exp05` reports that about 160
  SKUs are needed before the bootstrap interval excludes zero at least 80% of the time,
  and that at 20 SKUs it succeeds 18% of the time. That curve depends on the effect size
  present, which is a property of this generator. The shape of the finding generalises:
  a small category cannot support a skill claim. The specific number does not transfer
  to a different portfolio.
- **The beat rate against the seasonal referee.** The fixture's forecast is constructed,
  so the absolute level of 46% is a fact about the generator. The finding that the
  unweighted and volume weighted rates differ by 28 points is a property of a skewed
  volume distribution, which every real portfolio has.
- **The share of an improvement that is mix.** 41% skill on this panel, by construction.
  A real portfolio would give a different number, and the tool's value is that it would
  give one at all.

## The claim that needs real data

**That the skill and mix split, computed on a real portfolio, matches what the planning
team's own judgement would say.** A tool like this earns trust by agreeing with experts
where they are confident and disagreeing where they are not. That calibration cannot be
done here, and this repository does not claim it.

The honest statement to a hiring manager: this proves the method is sound and the
implementation is correct. It does not prove the method is useful on your data. The
first thing to do with a real panel is run `attribute` on a period where the planning
team already has a firm opinion, and see whether the tool agrees.

## Why the default path stays offline

A reviewer should reproduce every number with one command and no credentials. That is
worth more here than realism, because an unreproducible number from a real dataset is
worth less than a reproducible one from a constructed dataset whose construction is
documented. `make verify` runs with no network.
