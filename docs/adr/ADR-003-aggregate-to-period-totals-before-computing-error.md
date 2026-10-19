# ADR-003: Aggregate weekly rows to period totals before computing error

Status: accepted

## Context

A weekly panel supports two different error calculations:

1. Compute a per SKU error each week, then average those over the period.
2. Sum actual and forecast to period totals per SKU, then compute one error.

These are different quantities and they do not rank forecasts the same way. The first
penalises a forecast that is right on the period and wrong on the timing inside it. The
second does not see timing error at all: a forecast that is early by two weeks and a
forecast that is exactly right both score zero.

## Decision

Aggregate to period totals, then compute the error. The decomposition is defined on
period totals.

## Rationale

The question this tool answers is about a quarterly or annual accuracy claim in a
planning review. That conversation is already about period totals, and a tool that
silently answers a different question than the one being asked is worse than no tool.

Aggregating also makes the weights well defined. A volume share has to be a share of
something, and "share of period demand" is a quantity a planner already has. Weekly
weights would have to be averaged, which reintroduces exactly the aggregation ambiguity
this repository exists to surface.

## What this gives up

The tool is blind to timing error within a period. A forecast that consistently lands
two weeks early scores as perfect here and would cause real stockouts and real expedite
costs. That is a genuine blind spot, not a rounding issue.

A planner using this tool for a period accuracy claim is on solid ground. A planner using
it to decide whether a forecast is fit for replenishment is not, because replenishment is
driven by timing. Those are different questions and this tool answers one of them.

## Trigger for revisiting

If this is ever used to support a replenishment or safety stock decision, add a
within period timing error alongside the period error and report both. The first metric
to watch would be the share of SKUs whose period total error is small while their peak
week is misplaced by more than the replenishment lead time.
