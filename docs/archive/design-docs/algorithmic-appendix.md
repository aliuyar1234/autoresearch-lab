# Algorithmic appendix

This document defines the intended algorithms for the novel parts of the lab.
Historical reference copies, when retained, live under `docs/archive/reference_impl/`. Live semantics belong in `lab/` and `research/`.

Do not replace them with hand-wavy alternatives without a concrete reason.

## 1. Experiment id generation

Requirements:
- unique within the local repo
- lexicographically sortable by time
- human-readable in reports
- safe for artifact directory names

Recommended format:

`exp_<YYYYMMDD>_<HHMMSS>_<4-digit local counter>`

Example:
`exp_20260309_214455_0007`

Algorithm:
1. get UTC or local-repo canonical timestamp
2. round to seconds
3. check the DB or artifact root for existing ids with the same second prefix
4. allocate the next 4-digit counter
5. reserve/write the manifest immediately

Reason:
- it is readable
- it avoids random UUID sprawl
- it still supports concurrent local restarts if the manifest is written first

## 2. Config fingerprinting

Goal:
- identical effective configs produce identical fingerprints
- semantically irrelevant ordering differences do not matter

Algorithm:
1. take the effective config object after campaign defaults and proposal overrides are merged
2. recursively normalize:
   - dict keys sorted
   - tuples converted to lists
   - sets converted to sorted lists
   - paths converted to normalized strings
   - floats rendered with stable JSON representation
3. serialize with canonical JSON
4. SHA-256 the bytes
5. store full hash and an 8-12 char short prefix for report readability

Current runtime home: `research/dense_gpt/fingerprint.py`.

## 3. Offline packing

The lab must move expensive packing work out of the hot train path.

### Input
Tokenized documents for a campaign split.

### Output
Packed fixed-length token blocks plus metadata manifests.

### Required properties
- BOS aligned
- deterministic for a given asset version
- low padding waste
- easy to verify
- mmap-friendly

### Recommended algorithm
Windowed best-fit decreasing:

1. tokenize all source documents into arrays
2. prepend BOS if the campaign requires it
3. split overlong documents into chunks of at most `sequence_length`
4. maintain a rolling buffer of unplaced chunks
5. sort candidate chunks in descending length within the current buffer
6. place each chunk into the bin with the least remaining space that still fits
7. when no bin fits, open a new bin
8. emit bins as fixed-length blocks
9. pad only the final leftover bins if necessary, and record exact padding counts in metadata

This achieves the spirit of upstream best-fit packing while avoiding per-run Python packing cost.

Current runtime home: `lab/campaigns/packing.py`.

## 4. Backend benchmark and cache

Goal:
- choose the best available attention backend for the current device profile and shape family
- avoid re-benchmarking every run
- blacklist failing backend-shape pairs

### Cache key
A backend cache key should include at least:
- device profile id
- compute capability
- torch version
- CUDA version
- backend candidate version identifiers
- sequence length family
- head dim
- dtype
- whether compile is enabled

### Algorithm
1. enumerate backend candidates
2. for each candidate:
   - run a tiny correctness check
   - warm up
   - benchmark a small relevant micro-shape family
   - record median latency
3. choose the fastest passing candidate
4. cache the result
5. if a candidate later fails during a real run, blacklist that backend+shape family and reselect

Current runtime home: `lab/backends/selector.py`.

## 5. Proposal generation

The scheduler should generate proposals by family, not by undirected mutation.

### Families
- baseline
- exploit
- ablation
- combine
- novel
- manual

### Generator rules

#### Baseline
Emit only when:
- campaign has no baseline record
- campaign version changed
- parity verification is required

#### Exploit
Mutate around current champions and strong near-misses with small local changes.

#### Ablation
Remove one change from a successful lineage to test causality.

#### Combine
Take two or more changes that improved orthogonal dimensions and merge them into one proposal.

#### Novel
Intentionally sample under-covered regions of the structured search space.

#### Manual
Human-authored or imported seed proposal.

### Anti-repeat rule
Do not generate a proposal if the effective config fingerprint already exists in:
- queued proposals
- completed experiments
- champions
- near-miss archive

Current runtime homes: `lab/scheduler/select.py`, `lab/scheduler/compose.py`, and `lab/scheduler/novelty.py`.

## 6. Scheduler selection policy

The scheduler should select both **what family to generate** and **what queued proposal to run next**.

### Inputs
- current queue
- recent experiment history
- archive state
- crash history
- lane mix targets
- remaining session budget
- campaign policy

### Lane policy
Recommended default overnight mix:
- mostly scout and main
- confirm only for candidates that clear thresholds
- code proposals only when structured search clearly plateaus or a specific architectural hypothesis is justified

### Family selection heuristic
Use a small rule set, not a weighted soup:

1. if no baseline exists, run baseline
2. if repeated crashes dominate the last N runs, suppress similar proposals and prefer reliability-safe families
3. if a strong near-miss exists with one uncertain change, queue ablation
4. if two orthogonal wins exist and have not yet been combined, queue combine
5. if novelty coverage is poor, queue novel
6. otherwise queue exploit

### Queue ranking heuristic
Within a lane, prefer:
1. explicit promotions
2. queued ablations that test recent wins
3. combines of orthogonal winners
4. exploits near current champion
5. novelty proposals

## 7. Promotion ladder

Promotion must be rule-based.

### Candidate decision order
1. valid terminal summary?
2. comparable campaign and lane?
3. metric improvement beyond lane threshold?
4. if within tie threshold, prefer simpler and cheaper run
5. if still tied, prefer better novelty coverage
6. otherwise discard or archive as near-miss

### Lane-specific intent

#### Scout -> Main
Advance only if the candidate beats the scout threshold and did not exceed safety limits.

#### Main -> Confirm
Advance only if the candidate beats the main threshold and is not a complexity regression without justification.

#### Confirm -> Champion
Promote only if confirm or audit survives according to campaign policy.

Current runtime home: `lab/scoring.py`.

## 8. Archive maintenance

The archive is not just “top N metrics”.

Keep several buckets:

1. **champions**
   - best confirmed campaign-local runs

2. **pareto**
   - strong quality vs VRAM vs throughput points

3. **simplicity winners**
   - runs whose improvement is small but whose design is materially cleaner

4. **near-misses**
   - runs that barely missed promotion but are strategically useful

5. **novel winners**
   - best representatives of under-covered regions

Current runtime home: `lab/scheduler/archive.py`.

## 9. Crash classification

Crash classification should be deterministic and excerpt-based.

Priority order:
1. preflight failures
2. import errors
3. compile errors
4. OOM train
5. OOM eval
6. timeout
7. NaN/Inf
8. assertion
9. missing data or corrupt assets
10. backend unavailable
11. interrupted
12. unknown

Algorithm:
- inspect structured runner context first
- inspect stderr excerpt second
- inspect stdout excerpt only if needed
- choose the narrowest reliable class
- store the excerpt and reason

Current runtime home: `lab/runner/failures.py`.

## 10. Morning report recommendations

The report recommendation engine should remain simple and inspectable.

Recommended rules:
- if one knob helps repeatedly across lineages, suggest local exploitation
- if a combined run regressed, suggest ablations of each constituent change
- if one crash class repeats, recommend reliability work before more search
- if confirm candidates are scarce, suggest wider scout novelty
- if many near-misses cluster around one region, suggest focused exploration there
- if improvements are consistently tiny and complex, suggest simplicity-preserving ablations

Current runtime home: `lab/reports/recommendations.py`.

## 11. Complexity cost

The complexity cost is a coarse tie-break input, not an optimizer.

Suggested interpretation:
- `0` baseline or trivial override
- `1` small config mutation
- `2` moderate structured change
- `3` complex structured composition
- `4` small code patch
- `5+` increasingly invasive code edits

Do not pretend this number is more precise than it is.

## 12. Campaign split semantics

Campaign split semantics must be explicit.

For the parity campaign:
- training excludes explicit held-out shards
- search, audit, and locked validation shards are fixed and versioned

For sampled corpora:
- deterministic partitioning with fixed seeds is required

Current runtime home: `lab/campaigns/split_rules.py`.
