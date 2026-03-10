# Metrics - 12h Pilot

## Headline Metrics

These are the pilot's top-line metrics.

1. Best confirmed primary improvement
2. Time to first promoted keep
3. Repeated-dead-end rate

## Supporting Metrics

1. Tentative keep rate
2. Confirm pass rate
3. Unique idea families explored
4. Proposal composition or lineage depth

## Diagnostic Metrics

1. Crash rate
2. Recovery or doctor interventions
3. Average turnaround per run
4. Peak VRAM
5. Throughput

## Important Pilot Note

For the bounded 12h pilot, "memory in action" is not yet a first-class schema feature. This means the pilot must treat memory evidence conservatively and explicitly document how it was inferred from:

- prior experiment state available to the scheduler
- parent proposal or experiment relationships
- differences in proposal trajectory between the two arms

If stronger retrieval evidence is required later, schema and logging work should happen before the full flagship.
