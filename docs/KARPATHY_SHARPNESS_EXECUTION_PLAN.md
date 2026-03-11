# Karpathy Sharpness Execution Plan

## Objective

Preserve the sharpness, inevitability, and research honesty of Karpathy's `autoresearch` while keeping the stronger lab properties that Autoresearch Lab now has:

- one-workstation operability
- durable experiment state
- validation-gated trust
- unattended night loops
- reproducible artifacts

This plan assumes the project identity is:

**Autoresearch Lab = Karpathy's autoresearch, turned into a real local single-GPU research operating system.**

The goal is not to become broader.
The goal is to become sharper, truer, and more defensible.

## Governing Constraints

- Keep a single-GPU, local-first identity.
- Keep the upstream baseline path alive as a truth anchor.
- Prefer deletion, compression, and clearer naming over new surface area.
- Do not split files unless there is a demonstrated quality or reasoning failure.
- Do not add platform theater, dashboards, orchestration sprawl, or MLOps drift.
- Do not make stronger claims than the code, metrics, and artifacts can support.

## Success Definition

The repo should feel like:

- a sharper version of the current lab
- a truer descendant of Karpathy's original idea
- a better research tool without becoming a heavier product

By the end of this plan, the repo should have:

- one obvious golden operator path
- one fully honest canonical campaign
- one explicit baseline parity harness
- one trusted long-run proof path
- fewer ambiguous or duplicated narratives
- stronger evidence for every retained capability

## Phase 1: Identity And Golden Path

### Goal

Make the repo impossible to misunderstand.
Anyone opening the project should quickly understand what it is, how to run it, and what the primary path is.

### Tasks

- Tighten the top-level project statement in `README.md` so the first paragraph, quickstart, and capability list all tell the same story.
- State one canonical operator path and visibly demote secondary paths.
- Keep `arlab` as the public front door and treat module invocation as fallback only.
- Ensure `ARCHITECTURE.md`, `README.md`, `docs/runbook.md`, and `SHOWCASE.md` use compatible language for:
  - what the lab is
  - what counts as a trusted result
  - what the showcase is and is not
- Remove or archive any root-level or docs-level artifact that confuses the main identity more than it helps.

### Exit Criteria

- A new reader can answer "what is this?" in one sentence.
- A new operator can answer "what command path do I follow first?" in one sentence.
- No public-facing doc implies a broader identity than the code actually supports.

## Phase 2: Canonical Truth Path

### Goal

Choose one canonical campaign and make it the fully honest, fully defended path through the lab.

### Tasks

- Designate `base_2k` as either the true canonical campaign or replace it with a campaign that better deserves that role.
- Audit the canonical campaign definition against the actual builder and trainer behavior.
- Remove, rename, or narrow any campaign field that sounds more real than the implementation really is.
- Ensure tokenizer, dataset, split, and asset language matches what the code materially does.
- Add a short "canonical path contract" doc section that states:
  - what is real
  - what is heuristic
  - what is baseline-only
  - what is experimental

### Exit Criteria

- The canonical campaign is mechanically honest.
- There is no gap between campaign framing and what the builder actually materializes.
- The repo has one clear answer to "what is the real path to test this lab?"

## Phase 3: Upstream Baseline And Parity Harness

### Goal

Keep the original Karpathy path alive as a real reference, not a nostalgic leftover.

### Tasks

- Define the exact role of `prepare.py` and `train.py` in the repo:
  - sanity reference
  - baseline parity path
  - regression anchor
- Create a repeatable parity harness that compares:
  - upstream-style path
  - lab-native structured path
- Normalize comparison inputs as much as the repo allows:
  - same campaign
  - same budget
  - same metric naming
  - same eval semantics where feasible
- Document the current differences rather than implying parity where there is none.
- Use parity results to decide which scientific mechanisms must stay in the baseline path and which must migrate into the lab-native path.

### Exit Criteria

- The repo has a real answer to "better than upstream in what way?"
- Upstream preservation is functional, not ceremonial.
- Differences between baseline and lab-native paths are explicit and measurable.

## Phase 4: Compression And Deletion

### Goal

Recover more of Karpathy's sharpness by reducing unnecessary surface area and duplicated narrative.

### Tasks

- Audit commands, docs, and repo entrypoints for duplicated ways of saying the same thing.
- Identify capability areas that are real but not yet important enough to sit in the front door.
- Move historical material, speculative material, and low-signal artifacts out of the main path if they dilute comprehension.
- Collapse overlapping documentation where the distinction is not earning its keep.
- Maintain one language for trust:
  - raw search win
  - confirmed result
  - audited result
  - champion
- Maintain one language for proposal shape:
  - structured
  - code proposal
  - manual

### Exit Criteria

- The repo surface feels smaller without losing actual power.
- The front door shows the main path, not the full attic.
- A serious reader sees more inevitability and less scaffolding.

## Phase 5: Proof And Trust Path

### Goal

Prove the lab as a tool through one canonical long-run path that is easy to rerun and hard to fake.

### Tasks

- Define one official endurance run for the lab itself.
- Keep one official showcase run for public capability demonstration.
- Make sure both are:
  - reproducible
  - documented
  - signoff-covered
  - verifier-backed where applicable
- Ensure CI covers the trusted non-GPU path and protects the contracts that make the lab defensible.
- Make reports emphasize validated outcomes over raw leaderboard excitement.
- Keep the ability to say "this run did not prove the hypothesis" without weakening trust in the system.

### Exit Criteria

- The lab has one canonical proof path.
- The showcase has one canonical proof path.
- Both can fail honestly without making the repo look fake.

## Phase 6: Capability Retention And Capability Cuts

### Goal

Keep only the advanced capabilities that materially improve the lab.

### Tasks

- Evaluate each advanced capability against one hard question:
  - does this improve operator power, research throughput, trust, or reproducibility?
- Review:
  - memory
  - autotune
  - code proposals
  - showcase machinery
  - archive-aware scheduling
- For each capability, classify it as:
  - proven and core
  - useful but secondary
  - promising but not yet proven
  - should be cut or downgraded
- Rename anything that sounds stronger than the evidence warrants.
- Remove or demote capabilities that add maintenance burden without measurable leverage.

### Exit Criteria

- Every retained capability has a reason to exist.
- The repo sounds no smarter than it is.
- The lab is stronger because of its advanced features, not merely more decorated.

## Phase 7: Scientific Core Justification

### Goal

Ensure the lab-native scientific path has a strong reason to exist beyond being easier to orchestrate.

### Tasks

- Decide whether `research/dense_gpt/` is:
  - the primary future research engine
  - a structured-search engine
  - a temporary lab-native control surface
- Measure whether it is actually helping:
  - iteration speed
  - controllability
  - validation quality
  - real outcomes
- Port only the highest-value upstream ideas into the lab-native path after measurement, not by aesthetics.
- Refuse scientific churn that makes the lab look busy without making it stronger.

### Exit Criteria

- The lab-native scientific path has a justified role.
- It is not just "cleaner code around a weaker research core."
- The repo can explain why both the baseline path and lab-native path exist.

## Recommended Order

1. Phase 1
2. Phase 2
3. Phase 3
4. Phase 4
5. Phase 5
6. Phase 6
7. Phase 7

This order is deliberate:

- identity first
- truth path second
- baseline anchor third
- compression before more capability
- proof before expansion
- capability retention only after evidence

## What Not To Do

- Do not turn the repo into a platform.
- Do not add a dashboard to compensate for unclear reports.
- Do not split files just because they are large.
- Do not multiply campaigns before one campaign is indisputably honest.
- Do not promote a capability because it sounds advanced.
- Do not let the showcase define the whole lab.
- Do not quietly widen claims when results are mixed.

## Immediate Next Tasks

- Tighten the front-door statement and golden path across `README.md`, `ARCHITECTURE.md`, and `docs/runbook.md`.
- Decide whether `base_2k` is good enough to remain the canonical campaign.
- Write the baseline parity contract for `prepare.py` and `train.py` versus the lab-native path.
- Run a compression audit on docs and front-door artifacts.
- Define one official endurance run for the lab and one official proof run for the showcase.
