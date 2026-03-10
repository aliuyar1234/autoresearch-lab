# Reporting spec

The report is the product surface.
A good morning report should tell the user what mattered without opening twenty files.

## Canonical report types

Required for v1:

1. **Daily / morning report**
2. **Campaign leaderboard**
3. **Champion card**
4. **Crash summary**

The daily report is the highest priority.

## Daily report sections

A daily report must contain these sections in this order:

1. **Header**
   - date/time range
   - campaign
   - machine/device profile
   - total runs attempted
   - total successful runs
   - total promoted runs
   - total failed runs

2. **Top outcomes**
   - best new candidate(s)
   - best confirmed candidate(s)
   - whether a new champion emerged
   - direct metric deltas vs previous champion

3. **What changed**
   - grouped by proposal family
   - summarize which knobs moved
   - note which combinations worked or failed

4. **Failure summary**
   - crash classes and counts
   - representative examples
   - recommended fixes if obvious

5. **Archive updates**
   - newly promoted runs
   - newly archived near-misses
   - superseded champions

6. **Recommendations**
   - next structured search regions
   - suggested ablations
   - suggested code-level proposals if warranted

7. **Appendix**
   - run table
   - artifact/report paths
   - generation metadata

## Leaderboard contract

Leaderboards must be campaign-local.
A leaderboard row should show:
- rank
- experiment id
- proposal id
- proposal family
- proposal kind
- lane
- primary metric
- delta vs champion
- backend
- peak VRAM
- complexity cost
- status

## Champion card contract

A champion card is a short durable summary for one important run.

Required fields:
- campaign
- experiment id
- proposal id
- proposal family
- proposal kind
- date
- primary metric
- delta vs previous champion
- config fingerprint
- key changes
- why it was better
- artifact path

## Crash summary contract

Crash summaries must group by crash class and include:
- count
- first/last occurrence
- typical excerpt
- likely cause
- whether scheduler should suppress similar proposals

## Rendering requirements

Markdown is canonical.
HTML may be added if it is generated from the same underlying structured report JSON.

Required structured companion:
- `report.json`

## Report generation source of truth

Reports must be generated from:
- SQLite ledger
- artifact summaries
- campaign metadata

They must not depend on ephemeral terminal output or human memory.

## Style guidance

Reports should be:
- concise but information-dense
- opinionated
- written like a competent research assistant
- explicit about uncertainty

Avoid:
- giant wall-of-logs
- vanity charts without decisions
- hand-wavy “everything improved” language
