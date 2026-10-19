# Defense guide

What to say when someone pushes on this repository. Every number here is re-measured by
`make receipts` and checked against this document's wording, so if the code changes and
this file does not, the build fails.

## The one sentence version

A portfolio WMAPE is a volume weighted average over a SKU population, so when the
population changes between periods, a change in that average cannot be attributed
between forecasting skill and mix shift. This tool decomposes it, reports the four
standard conventions because they disagree, and refuses to report a split at all when
too much of the volume sits in SKUs that have no counterfactual.

## Why this project exists

I improved forecast accuracy at Cargill and reported it as a percentage. I could not
have told you, at the time, how much of that was the forecast getting better versus the
portfolio shifting toward items that were always easier to forecast. Nobody asked, and
that is the uncomfortable part. This is the tool that would have answered the question,
built on a fixture where I know the right answer so I can show it finds it.

## The six questions I expect

### 1. "Your decomposition needs a convention. Which one is correct?"

None of them. They are four definitions, not four estimates, and the difference between
them is which period's values you hold constant. On this fixture they put between 33%
and 48% of the improvement on skill, a spread of 0.43 points on a 2.86 point change.

I report Shapley as the headline because it is the only one of the four symmetric in the
two periods, so the answer does not depend on which period I happened to call the base.
But the table prints all four every time, because reporting one number would present a
convention dependent quantity as though it were measured. ADR-002.

If pushed further: a confidence interval over the conventions would be a category error.
They are not samples from a distribution.

### 2. "How do you know the decomposition is right if you cannot observe the truth?"

I cannot, on real data, which is why the fixture is constructed rather than sampled. Two
scenarios have the answer planted. In `pure_mix` every SKU's per SKU percentage error is
identical in both periods by construction, so the true skill effect is exactly zero. In
`pure_skill` each SKU's period volume is held constant, so the true mix effect is exactly
zero. All four conventions recover both planted zeros to 5 orders of magnitude below the
change being decomposed, and the residual is the fixture's three decimal rounding rather
than method error.

If someone checks that number against `exp01_recovery.json`, the worst ratio is 1.95 parts
per million. An earlier draft of this guide rounded that to "under one part in a million",
which is false, and the metric collector was rounding the exponent down, which rounds a
precision claim in the flattering direction. Both are fixed; the collector now rounds up.

Separately, every convention is tested to sum exactly to the restricted change. That one
matters most: an inexact decomposition lets a residual masquerade as skill.

### 3. "What is the weakest part of this repository?"

The number checker, and I know that because it failed an audit rather than because I
reasoned my way to it.

The first version claimed in the README that a stale figure fails the build. Someone
corrupted sixteen published figures one at a time and fourteen passed. Three causes. It
stripped fenced blocks before looking, so the convention table, which is the centrepiece
of the README, had no guard on any of its twelve cells. An anchor matching in one document
counted for every document, so the defense guide you are reading was almost entirely
unchecked. And the reverse direction, which looks for numbers that match no metric, only
printed a note instead of failing.

That last one was the real hole. A forward check can only confirm that a correct sentence
exists somewhere; it cannot notice that a wrong number was introduced. Corrupting a
published figure leaves the anchored sentence missing and introduces a number matching
nothing, and it is the second of those that catches a figure sitting in a table cell where
no phrase could reach it.

What it does now: the reverse check fails the build, every document is checked separately,
the convention table is generated from the measured values and verified by block equality,
the badges are checked against the metrics they advertise, and `tests/test_check_numbers.py`
corrupts every published figure in turn and asserts the build goes red. The checker has a
test because a checker nobody has watched fail is a checker nobody should believe.

I would rather be asked this than any other question here, because the answer is the
engineering story. The tool is a shift share decomposition, which is standard. The thing
that took work was making the numbers in the documents impossible to leave stale, and that
took getting it wrong first.

### 4. "What is this tool wrong about?"

Three things, and I would rather say them first.

Errors are computed on period totals, so the tool is blind to timing error inside a
period. A forecast that lands two weeks early scores as perfect here and would still
cause stockouts. It supports a period accuracy claim and should not be used to decide
whether a forecast is fit for replenishment. ADR-003.

The absolute numbers are properties of the generator. The beat rate of 46% is not a fact
about any real forecast. What transfers is the structure: that the unweighted and volume
weighted rates are 28 points apart is a property of skewed volume, which every portfolio
has.

And it cannot tell you whether the split agrees with what your planning team already
believes. That calibration needs a real panel and a period where the team has a firm
opinion. ADR-005 is the full boundary statement.

### 5. "Walk me through a bug you found."

The seasonal naive referee originally shifted by 52 rows rather than 52 weeks. Those are
the same thing only when every SKU has a row for every week, and a sales extract from an
ERP omits weeks with no sales, so a slow moving SKU's rows are not contiguous and a 52
row shift reaches back an arbitrary number of calendar weeks that varies per SKU.

Nothing raised. The output looked reasonable. I found it by asking what would happen if
the same panel arrived in the format an ERP actually produces, dropping the zero sales
rows, and running it again: the unweighted beat rate moved by 18.9 points.

The fix was two parts. Align the referee on week numbers so a missing predecessor is NaN
rather than whatever row happens to be there. Then densify: insert a zero demand row for
every week a SKU is missing inside its own observed span, flagged so those rows inform
the referee but are never scored. After that the same comparison moves the rate by 4.8
points, removing 14.1 points of that swing as artefact. The remaining gap is real
information loss, reported as undefined SKUs rather than folded into the rate.

I kept the broken implementation in `experiments/exp06_extract_format.py` so the size of
the bug stays re-measurable, and there is a regression test that fails if anything
reintroduces it. ADR-004.

### 6. "What would you build next, and what did you deliberately leave out?"

Left out: attributing the mix shift to specific SKUs or categories. The tool says how
much of a change was mix; the obvious next question is what drove it. I did not build
that because it changes the claim from "this much was mix" to "these items caused it",
and the second claim needs more than two periods to be stable. The trigger would be a
user with eight or more periods of history who wants to act on the mix finding.

Next, in order: within period timing error, because that is the gap ADR-003 names;
margin weighting instead of volume weighting, because a WMAPE gain concentrated in low
margin items is worth less; and a declarable assumption file for the densification rule,
for extracts where a missing week means missing data rather than zero.

## Numbers I should know cold

| Figure | Value |
| --- | --- |
| WMAPE improvement on the fixture | 2.86 points |
| Of which skill (Shapley) | 1.16 points |
| Of which mix (Shapley) | 1.38 points |
| Unattributable | 0.32 points |
| Skill share of the improvement | 41% |
| Range across conventions | 33% to 48% |
| Decomposable SKUs | 199 |
| Excluded SKUs | 41 |
| Beats seasonal naive, per SKU | 46% |
| Beats seasonal naive, by volume | 74% |
| SKUs needed to detect the effect 80% of the time | about 160 |
| Detection rate at 20 SKUs | 18% |
| Extract format swing, before the fix | 18.9 points |
| Extract format swing, after | 4.8 points |
| Tests | 258 tests |
| Line coverage | 100% line coverage |

## If someone says it is just a shift share analysis

They are right, and shift share is a well established technique from labour economics.
The contribution here is not the arithmetic. It is applying it to a forecast accuracy
claim where the practice is to report one number, reporting the convention spread
instead of hiding it, carrying the undecomposable population through to the output
rather than dropping it, and attaching a resolution floor so a small category cannot
support a claim it has no power to support.

I would rather be asked this than not. The answer is that knowing which standard
technique applies to a messy operational question, and knowing what it cannot do, is the
job.
