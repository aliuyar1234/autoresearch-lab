# The Remembering Scientist

Status: planned, not yet executed

Purpose: this file is the durable source of truth for the flagship public showcase of Autoresearch Lab. It records the exact intended claim, fairness rules, runtime plan, artifacts, decision rules, and publication package so the next session can resume immediately without re-deriving the plan.

Created from: GPT Pro showcase design answer captured on 2026-03-10

Core claim:

> Same GPU. Same campaign. Same budget. The only difference was memory.

Working title:

> The Remembering Scientist

## Why This Showcase Exists

Autoresearch Lab should be showcased as a one-GPU research lab with memory, judgment, and a morning briefing, not as a generic experiment framework or benchmark matrix.

The flagship story should demonstrate that persistent research memory changes the trajectory of autonomous experimentation. The difference must show up in:

- the quality of the final champion
- the speed of finding meaningful keeps
- the amount of wasted search avoided
- the coherence of the resulting morning report and lineage

## Final Showcase Concept

Run the same one-GPU lab twice from the same baseline:

- `remembering` arm: has access to a frozen historical memory snapshot
- `amnesiac` arm: same runner, same proposal generator, same campaign, same time budget, but no access to historical memory

By morning, compare:

- who found the better confirmed champion
- who got there faster
- who repeated fewer known dead ends
- who left behind the more coherent research trail

Important framing:

- this is a controlled A/B case study
- this is not a giant benchmark matrix
- this is not a dashboard tour
- this is not a retrieval anecdote without outcome changes
- this should be publishable even if the result is mixed or inconclusive

## A/B Fairness Rules

### Frozen A/B Principle

Everything below must be identical between the two arms except access to historical memory:

- baseline commit
- campaign manifests
- runner version
- proposal generator version and prompt template
- scheduler policy
- promotion thresholds
- doctor, recovery, and cleanup behavior
- GPU workstation
- per-experiment budget
- official session duration
- confirm, audit, and replay protocol
- manual intervention policy

The only intentional difference:

- `remembering` can retrieve from a frozen historical memory snapshot
- `amnesiac` cannot retrieve any historical memory

### Shared Context For Both Arms

This is allowed for both arms:

- repo docs
- campaign definitions
- metric definitions
- machine and GPU profile
- runbook and recovery instructions
- proposal schema
- leaderboard and champion rules
- search space boundaries

### Historical Memory Allowed Only For Remembering

This is exclusive to the `remembering` arm:

- historical experiment summaries
- historical proposal and result pairs
- archived failure autopsies
- prior morning reports
- champion lineage and code diffs
- cross-campaign findings
- repeated-dead-end tags
- prior audit outcomes

### What The Amnesiac Arm Still Keeps

The `amnesiac` arm is not supposed to be crippled beyond the intended ablation. It must still have:

- same-session local archive
- same-session leaderboard
- current-night proposal tracking
- current-night champion updates
- same doctor and recovery behavior
- same static repo knowledge

The `amnesiac` arm must not have:

- frozen historical SQLite memory
- historical artifact retrieval
- cross-session carryover between official showcase sessions
- manually injected prior findings

## Memory Snapshot Rules

### Seed The Remembering Arm With A Frozen Snapshot

The memory seed must be created before the official comparison begins.

It should include real prior history such as:

- earlier experiments from adjacent campaigns
- earlier experiments from older commits of the same codebase
- failure families
- champion summaries
- code-proposal round trips
- audit notes
- "do not try this again" lessons
- "this combination worked before" lessons

It must not include:

- the top-winning patch from the exact same baseline on the exact same primary campaign
- any post hoc human summary written after seeing official A/B results
- hand-crafted memory cards that leak conclusions from the final comparison

Publish a small seed manifest with:

- snapshot timestamp
- included sources
- excluded sources
- snapshot hash
- brief explanation of why the seed is fair

## Official Session Isolation

During the official comparison:

- both official pairs start from the same baseline
- the `remembering` arm uses the same frozen seed snapshot in both pairs
- the `amnesiac` arm starts empty in both pairs
- neither arm is allowed to learn from earlier official comparison sessions

This avoids the comparison becoming harder to interpret.

## Confirm, Audit, And Replay

### Confirm Runs

Purpose: verify that primary-campaign winners are not just lucky nightly keeps.

Recommended policy:

- pool candidates after all official search sessions
- deduplicate by `family_id`
- take top 2 candidates per arm
- rerun them on the primary campaign
- use at least:
  - one clean confirm replay under official settings
  - one alternate-seed replay if supported, otherwise one slightly longer confirm budget on the same campaign

### Audit Runs

Purpose: test whether the winner survives outside the exact search lane.

Recommended policy:

- take the best confirmed candidate from each arm
- run it on one sibling audit campaign
- do not feed audit results back into the official search story
- use audit as robustness characterization, not as the only headline metric

### Replay Runs

Purpose: create clean, screenshot-ready publication artifacts.

Replay cleanly:

- baseline
- final `remembering` champion
- final `amnesiac` champion

These are the logs and summaries that should be cited and screenshotted publicly.

## Manual Intervention Policy

Allowed:

- restarting a failed worker process
- clearing disk space
- recovering from corrupted temporary files
- re-running a failed export step
- obvious infrastructure fixes that do not change search behavior

Not allowed:

- editing prompts mid-run
- changing proposal policies
- changing thresholds
- hand-picking proposals to try next
- manually rewriting generated code to help
- changing campaign manifests after the first official session starts

Every allowed intervention should be logged in `interventions.md`.

## Campaign Strategy

Use exactly 2 campaigns:

- 1 primary campaign for search and headline results
- 1 audit campaign for robustness

Primary campaign requirements:

- most stable metric lane already trusted
- good signal under short budget
- visually legible
- interpretable wins and failures
- cheap enough to run multiple official sessions on one workstation

Audit campaign requirements:

- clearly related to the primary
- not identical
- same enough that transfer is meaningful
- cheap enough to replay finalists

Do not use more than one audit campaign for the first flagship.

## Chronological Execution Plan

### Phase 0 - Freeze The Protocol

Create the following under `showcase/the-remembering-scientist/`:

- `PROTOCOL.md`
- `SUCCESS_RULES.md`
- `INTERVENTION_POLICY.md`
- `METRICS.md`

Freeze:

- baseline commit
- campaign manifests
- official session duration
- proposal generator version
- scheduler version
- promotion rules
- confirm rules
- audit rules

Exit criterion:

- a skeptic could read the protocol folder and understand exactly what will happen before the runs occur

### Phase 1 - Instrument Evidence Paths

Ensure every proposal captures:

- `proposal_id`
- `parent_ids`
- `family_id`
- `campaign_id`
- `expected_effect`
- `risk_level`
- `cited_memory_ids`
- `cited_failure_ids`
- `code_diff_ref`
- `result_ref`
- `promotion_status`

Ensure retrieval logs capture:

- query text
- retrieved memory IDs
- scores or ranks
- which items were actually attached to proposal context

Exit criterion:

- one run can be traced from retrieval -> proposal -> patch -> result -> promotion decision

### Phase 2 - Pick Campaigns And Establish Baseline

Do:

- choose 1 primary campaign
- choose 1 audit campaign
- replay the baseline at least 2 times on the primary
- replay the baseline at least 1 time on the audit

Estimate:

- normal variance or noise floor
- expected throughput per session
- whether the campaign actually moves during a single official session

Exit criterion:

- it is clear what counts as a meaningful delta
- the primary campaign is lively enough to justify the showcase

### Phase 3 - Build And Freeze The Memory Snapshot

Create:

- frozen SQLite snapshot
- frozen artifact bundle
- seed manifest
- exclusions manifest

Recommended seed contents:

- previous experiment summaries
- prior promoted keeps
- failure autopsies
- prior reports
- cross-campaign findings
- champion lineage metadata

Recommended exclusions:

- official comparison runs
- exact winner patch for the same baseline and primary campaign combination
- any hand-written hindsight after protocol freeze

Exit criterion:

- the memory snapshot is hashed, versioned, and frozen

### Phase 4 - Build The Amnesiac Harness

Prepare:

- empty SQLite template
- empty artifact memory template
- same-session local archive enabled
- post-session teardown script
- same static docs mounted as shared context

Exit criterion:

- the amnesiac arm has zero historical memory but otherwise behaves normally

### Phase 5 - Dry Run Both Arms

Run:

- one short dry run for `remembering`
- one short dry run for `amnesiac`

These are not official results. They exist to:

- catch logging gaps
- check throughput
- validate morning reports
- verify recovery behavior
- confirm retrieval panels can be collected later

Exit criterion:

- complete logs exist
- report format is usable
- no missing evidence path remains

### Phase 6 - Official Pair 1

Use the same:

- baseline commit
- frozen memory seed
- session duration
- policies

Choose one arm first by coin flip or predeclared order.

At the end of each session save:

- morning report
- session leaderboard snapshot
- archive snapshot
- proposal log
- retrieval log
- promotion log
- top candidate diffs
- failure summaries
- intervention log
- end-of-session champion summary

Exit criterion:

- one complete `remembering` session and one complete `amnesiac` session exist under the same protocol

### Phase 7 - Official Pair 2

Repeat pair 1 from the same baseline.

Rules:

- reverse the order of the arms relative to pair 1
- do not let either arm learn from pair 1
- use the same frozen memory seed again

Exit criterion:

- two paired comparisons exist instead of one lucky night

### Phase 8 - Candidate Pooling And Confirm

Process:

- pool top candidates from all official sessions
- deduplicate by `family_id`
- select top 2 per arm by:
  - primary improvement
  - simplicity
  - novelty
  - stability of logs

Then run confirms:

- one clean replay on primary
- one alternate-seed replay, or slightly more robust confirm variant if alternate seeds are not ready

Exit criterion:

- one best confirmed finalist per arm exists

### Phase 9 - Audit Finalists

Run:

- `remembering` finalist on audit campaign
- `amnesiac` finalist on audit campaign
- baseline on audit campaign if not already freshly replayed

Exit criterion:

- it is clear whether the winning idea is local-only or survives a sibling campaign

### Phase 10 - Clean Replay For Publication Assets

Replay cleanly:

- baseline
- `remembering` finalist
- `amnesiac` finalist

Save:

- final logs
- clean score summaries
- final diffs
- final report excerpts
- clean leaderboard snapshots

Exit criterion:

- every chart and screenshot can point to a clean run artifact

### Phase 11 - Build Visuals And Writeup

Assemble:

- hero chart
- morning report diptych
- retrieval-in-action panels
- lineage graph
- audit panel
- failure strip
- README showcase section
- `SHOWCASE.md`
- blog-style writeup
- short summary thread

Exit criterion:

- a reader can understand the result without reading the entire repo

## Runtime Budget

| Version | Scope | Rough GPU hours | Calendar nights | Human hours |
| --- | --- | ---: | ---: | ---: |
| Minimum viable | 1 official pair, top-1 confirm each, 1 audit, clean replay | 16-22 | 2-3 | 6-10 |
| Recommended | 2 official pairs, top-2 confirm each, 1 audit finalist each, clean replay set | 30-36 | 4-5 | 10-16 |
| Ambitious | 3 official pairs, stronger confirm lane, richer appendix, optional second audit for finalists only | 46-60 | 6-8 | 16-24 |

Opinionated recommendation:

- use the `Recommended` version
- use 6-hour official sessions unless later evidence suggests a different sweet spot

## Metrics Plan

### Headline Metrics

These belong in the hero section.

| Metric | Exact meaning | Public presentation |
| --- | --- | --- |
| Best confirmed primary improvement | Final confirmed finalist vs baseline on primary campaign, normalized so positive means better | Big number card plus hero chart |
| Time to first promoted keep | Wall-clock time and experiment index until first keep that survives confirm | Side-by-side scorecard |
| Repeated-dead-end rate | Share of proposals or runs that revisit already-known losing families from frozen seed or same-session history | Bar chart |
| Audit survival | Whether the final champion remains better than baseline on the audit campaign, and how much gain is retained | Compact audit table |

### Supporting Metrics

| Metric | Public use |
| --- | --- |
| Tentative keep rate | Secondary comparison table |
| Confirm pass rate | Secondary comparison table |
| Unique idea families explored | Small supporting chart |
| Proposal composition rate | Appendix or side chart |
| Useful retrieval rate | Retrieval panel annotation |
| Archive efficiency | Appendix |
| Champion lineage depth | Lineage figure annotation |

### Diagnostic Metrics

These build trust but should not dominate the hero section.

| Metric | Why it matters |
| --- | --- |
| Crash rate | Stability |
| Recovery or doctor interventions | Operational maturity |
| Average turnaround per run | Orchestration cost |
| Training vs overhead share | Whether memory or orchestration bloats the loop |
| Peak VRAM | Workstation realism |
| Throughput and tokens processed | Interpreting odd results |
| Empty or irrelevant retrieval rate | Whether memory is actually useful |
| Invalid proposal rate | Proposal quality |

Presentation rule:

- all hero numbers should be normalized so positive means better
- keep raw metric names in captions and appendix
- do not lead with internal jargon

## Artifact Checklist

Recommended folder layout:

```text
showcase/the-remembering-scientist/
  00_protocol/
  01_seed_snapshot/
  02_dry_runs/
  03_official_pairs/
  04_confirms/
  05_audit/
  06_clean_replays/
  07_figures/
  08_writeup/
```

### 00_protocol

Save:

- `PROTOCOL.md`
- `SUCCESS_RULES.md`
- `INTERVENTION_POLICY.md`
- `METRICS.md`
- baseline commit hash
- campaign manifest hashes
- scheduler and proposal generator version info

### 01_seed_snapshot

Save:

- frozen SQLite snapshot
- frozen artifact bundle manifest
- included-source list
- excluded-source list
- snapshot hash
- 3 to 5 sample memory cards for inspection

### 02_dry_runs

Save:

- short morning report per arm
- throughput summary
- proposal log sample
- retrieval log sample
- any missing-evidence bug list
- baseline variance note

### 03_official_pairs

For each arm and each pair, save:

- session manifest
- morning report
- leaderboard snapshot
- archive snapshot
- proposal log
- retrieval log
- promotion or decision log
- top candidate patch refs
- top failure patch refs
- crash summaries
- intervention log
- end-of-session champion summary

### 04_confirms

Save:

- confirm candidate list
- deduplication note by family
- clean confirm logs
- confirm table
- confirm winner note
- rejected finalist notes

### 05_audit

Save:

- audit logs
- audit comparison table
- audit summary paragraph
- any transfer surprises

### 06_clean_replays

Save:

- baseline clean replay
- remembering finalist clean replay
- amnesiac finalist clean replay
- clean screenshot-ready logs
- final diff patches

### 07_figures

Save:

- hero chart
- report comparison panel
- lineage graph
- retrieval panels
- audit panel
- failure strip
- captions file

### 08_writeup

Save:

- README section draft
- `SHOWCASE.md`
- long-form blog post draft
- short thread or post draft
- appendix or repro section

Mandatory qualitative artifacts:

- at least 1 crisp retrieval-to-result example
- at least 1 avoided-dead-end example
- at least 2 memorable failure examples
- the final champion diff
- the paired morning reports

## Visualization Plan

Use 6 strong visuals, not 20 weak ones.

### Figure 1 - Hero Chart

Content:

- cumulative best primary score vs experiment index or wall-clock
- `remembering` vs `amnesiac`

If two official pairs exist:

- use thin lines for each pair
- use a thicker aggregate or median line

### Figure 2 - Morning Report Diptych

Content:

- side-by-side morning reports
- left: `amnesiac`
- right: `remembering`
- same template and same fields

Recommended report fields:

- best run
- notable keeps
- notable failures
- retrieved lessons used
- repeated traps
- next-step hypotheses

### Figure 3 - Memory Retrieval In Action Panels

Select 2 to 3 mini-panels that show:

- retrieved note or notes
- generated proposal
- resulting patch
- resulting outcome

Selection rule:

- earliest promoted memory-citing proposal
- highest-improvement memory-citing proposal
- clearest avoided-failure case

### Figure 4 - Champion Lineage Graph

Display:

- DAG or tree from baseline to final champion
- node state: kept, discarded, crashed
- primary delta
- confirm status
- arm label

Highlight:

- final champion path
- major branch points
- dead-end branches

### Figure 5 - Audit Survival Panel

Compare on the audit campaign:

- baseline
- `remembering` finalist
- `amnesiac` finalist

### Figure 6 - The Cost Of Forgetting

Content:

- repeated-dead-end rate bar chart
- 2 to 3 failure cards

Each failure card should show:

- repeated trap
- why it failed before
- why the amnesiac arm retried it anyway
- how the remembering arm avoided or reframed it

## Public Writeup Blueprint

### Best Title

`The Remembering Scientist`

### Best Subtitle

`Same GPU. Same campaign. Same budget. The only difference was memory.`

### Suggested Opening Hook

I ran my one-GPU research lab twice from the exact same baseline. In one run it could consult its old notebook: prior failures, earlier champions, and cross-campaign lessons. In the other, it started the night with amnesia. By morning, the remembering lab had found stronger ideas faster, repeated fewer dead ends, and left behind a more coherent scientific trail.

### Section Outline

1. Hook
2. What Autoresearch Lab is
3. Why this showcase
4. The protocol
5. The experimental setup
6. Headline result
7. The morning after
8. Memory in action
9. Champion lineage
10. The cost of forgetting
11. Audit result
12. Caveats
13. Reproduce

### Closing Paragraph

The point of this project is not that memory makes one lucky run look smarter. The point is that research starts to compound when the lab can preserve what it learned, reuse it responsibly, and avoid paying for the same mistakes twice. On a single local GPU, that difference is the line between an experiment runner and a research lab.

Style rule:

- use first-person lab notebook voice
- do not use startup-marketing language like `platform`, `solution`, or `state of the art orchestration layer`

## Risk Management

| Risk | Why it hurts | Mitigation before the run |
| --- | --- | --- |
| Weak result | Score difference is small and boring | Choose a primary campaign with known overnight movement and estimate noise first |
| Noisy result | One lucky night can be dismissed | Run 2 official pairs and use confirm replays |
| Unfair comparison | Memory arm looks like it got extra hints | Freeze seed snapshot and publish included/excluded sources |
| Memory looks rigged | Critics think the answer was preloaded | Exclude exact winner patch for same baseline and campaign |
| Amnesiac looks crippled | Comparison feels theatrical | Keep same-session archive and same docs; remove only historical memory |
| No crisp retrieval examples | Story becomes abstract | Instrument cited retrieval IDs before official runs |
| Visually boring assets | Good result, weak presentation | Plan the 6 visuals in advance and capture clean replays |
| Too much complexity | Readers get lost | Use 1 primary campaign, 1 audit, 2 official pairs, and 6 visuals max |
| Too much human steering | Undercuts autonomy story | Freeze intervention policy and log every intervention |
| Audit backfires | Winner looks local-only | Frame audit honestly as robustness, not as the sole hero metric |
| Live demo temptation | Runtime failure ruins the launch | Publish a documented completed run, not a live overnight run |
| Showcase drifts into benchmark matrix | Story becomes generic | Keep the narrative on one claim: memory changes research compounding |

Additional non-obvious risk:

- the memory system may be real but narratively invisible

Mitigation:

- require every proposal to cite memory IDs
- log avoided failures
- save retrieval panels during the run
- make `memory in action` a mandatory artifact

## Decision Rules

### Successful Showcase

Call it successful if all of the following are true:

- protocol and seed snapshot are frozen and publishable
- the remembering arm wins on at least 2 of these 3 axes:
  - better confirmed primary result
  - faster time to first promoted keep
  - lower repeated-dead-end rate
- the remembering arm does not catastrophically fail the audit lane
- there is at least one undeniable retrieval -> proposal -> result example
- the morning report comparison is visibly more coherent for the remembering arm

### Inconclusive Showcase

Call it inconclusive if:

- final score differences are tiny relative to measured noise
- confirm results split randomly
- memory does not clearly reduce wasted search
- retrieval examples are weak or ambiguous
- audit contradicts the primary story without a good explanation

An inconclusive result may still be publishable, but it is not the flagship version.

### Pivot Rules

Pivot to a different showcase if any of the following appear during the dry run or pair 1:

- the primary campaign barely moves overnight
- the memory seed is too thin to generate real retrieval examples
- proposal lineage or retrieval logging is incomplete
- the main visible difference is only better report formatting
- the A/B cannot be explained cleanly in one sentence

Fallback showcase candidates:

- `One Sentence at Night, Better Model by Breakfast`
- `Hypothesis Court`

### Mandatory Artifacts Before Publishing

Do not publish the flagship version without:

- frozen protocol
- seed manifest
- paired morning reports
- hero chart
- confirm table
- audit table
- final champion diff
- one retrieval-in-action panel
- one avoided-dead-end example
- at least two failure cards
- clean replay logs for baseline and finalists

## Final Deliverables

Core publication package:

- README showcase section
- `SHOWCASE.md`
- long-form blog-style post
- figure set
- screenshot set
- appendix or repro section

Strongly recommended:

- protocol folder in repo
- seed manifest
- confirm and audit tables
- final patch refs or diff summaries
- short thread or post summary

Optional:

- short narrated video
- interactive lineage graph
- downloadable report bundle

## Recommended Version To Run

Use this exact scope unless later evidence forces a change:

- 1 primary campaign
- 1 audit campaign
- 2 official A/B pairs
- 6-hour sessions
- frozen seed snapshot
- no cross-pair learning during measurement
- top 2 candidates per arm to confirm
- top 1 confirmed finalist per arm to audit
- clean replay of baseline plus both finalists
- 6 core visuals
- README section, `SHOWCASE.md`, and long-form writeup

Recommended calendar:

- Day 1: protocol freeze, campaign choice, instrumentation check
- Day 2: baseline variance and dry runs
- Night 1: official pair 1, first arm
- Night 2: official pair 1, second arm
- Night 3: official pair 2, reversed order
- Night 4: official pair 2, reversed order
- Day or Night 5: confirm finalists
- Day or Night 6: audit and clean replays
- Day 7: visuals and writeup

Why this version:

- rigorous enough to be credible
- small enough for one workstation
- rich enough to create a memorable story

## Simplified Fallback Version

Use this only if the result is already very strong after pair 1 or time is tight.

Scope:

- 1 primary campaign
- 1 audit campaign
- 1 official A/B pair only
- top 1 confirm per arm
- 1 audit replay each
- 3 visuals only:
  - hero chart
  - morning report diptych
  - one retrieval panel

Tradeoff:

- faster and still publishable
- much easier for skeptics to dismiss as a lucky pair

## Next Session Starting Point

Tomorrow, do not re-brainstorm. Start here:

1. Read this file fully.
2. Decide whether the `Recommended Version To Run` still stands.
3. Freeze the protocol before running anything official.
4. Verify whether the current repo already logs all evidence required in `Phase 1 - Instrument Evidence Paths`.
5. Pick the primary and audit campaigns based on signal and runtime, not novelty.
6. Run baseline replays to estimate noise before committing to the showcase.
7. Build the frozen memory snapshot and the amnesiac harness.
8. Dry run both arms before any official pair.

Tomorrow's immediate deliverables should be:

- a concrete protocol folder
- a decision on primary and audit campaign
- a baseline variance note
- a list of any missing instrumentation gaps

If the campaign does not move, the retrieval signal is too weak, or the logging cannot support the story, do not force the showcase. Pivot early and honestly.
