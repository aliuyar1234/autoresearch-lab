# Intervention Policy - 12h Pilot

## Allowed

- restart a failed worker process without changing search behavior
- rerun a failed CLI command caused by transient infrastructure issues
- clear disk space
- repair corrupted temporary artifacts
- rerun a failed export or report step

## Not Allowed

- changing prompts during official sessions
- changing campaign manifests after the pilot starts
- changing promotion thresholds
- changing proposal generation policy
- hand-selecting proposals to make one arm look smarter
- editing generated code to rescue an experiment
- changing the frozen memory snapshot after official A/B begins

## Logging Requirement

Every allowed intervention must be written to:

- `showcase/the-remembering-scientist/interventions.md`

Each entry must include:

- timestamp
- arm or workspace affected
- what happened
- why the intervention was allowed
- whether the affected command was rerun
