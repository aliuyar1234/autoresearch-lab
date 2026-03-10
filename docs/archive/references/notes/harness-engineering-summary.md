# Harness engineering summary for this repo

This document internalizes the relevant lessons from the OpenAI “Harness engineering” article so Codex does not need to browse it.

## Key lessons adapted here

1. **Repository knowledge is the system of record**
   - this pack therefore commits specs, plans, schemas, SQL, templates, fixtures, and guardrails

2. **Agent legibility is the goal**
   - the repo is shaped to be readable to an implementation agent
   - that is why there are separate design docs, product specs, execution plans, and reference implementations

3. **Architecture and taste must be enforced mechanically**
   - schemas, SQL, fixtures, and explicit file layout are not optional
   - they are how the repo resists drift

4. **Throughput changes the merge philosophy**
   - the lab is designed for lots of small local experiments, not giant manually curated branches

5. **Entropy and garbage collection matter**
   - cleanup, retention policy, report generation, and a resolved-ambiguities log are product features, not afterthoughts

## Local interpretation for Autoresearch Lab

The original `autoresearch` repo gave us the right minimal core:
- one machine
- one main trainer
- one metric
- one fixed budget

The harness-engineering lesson is that to make a coding agent reliable, we must add:
- repo-local memory
- explicit contracts
- clear architecture
- deterministic execution scaffolding
- garbage collection and anti-entropy mechanisms

That is exactly what this pack is trying to provide.
