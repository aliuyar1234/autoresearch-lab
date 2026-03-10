# Reference implementations

This directory contains concrete reference algorithms for the hardest parts of the lab.

These files exist for one reason:
to reduce implementation drift.

## How to use them

- treat them as the intended semantics
- copy or adapt them into `lab/` and `research/` as appropriate
- preserve the public behavior even if the final code is reorganized
- write tests against the behavior, not against incidental formatting

## What is here

- `config_fingerprint.py` — canonical JSON fingerprinting
- `crash_classifier.py` — deterministic crash classification
- `campaign_split_rules.py` — explicit split semantics for the initial campaigns
- `offline_packing.py` — offline best-fit-ish document packing
- `backend_selector.py` — backend benchmark, cache, and blacklist policy
- `promotion_policy.py` — rule-based promotion and champion decisions
- `archive_policy.py` — archive bucket maintenance
- `scheduler_policy.py` — proposal generation and next-run selection
- `report_recommendations.py` — simple inspectable next-step heuristics

## Important

These are intentionally standard-library-heavy and minimal.
They are meant to be understandable and portable.

If the final production code differs, it should differ because:
- the real code needs tighter integration
- tests prove parity of behavior
- the new version is clearly better and still legible
