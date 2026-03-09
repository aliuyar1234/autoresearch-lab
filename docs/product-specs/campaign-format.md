# Campaign format

Campaigns are the unit of comparability.
A campaign fully defines the environment in which proposals compete.

## Storage layout

Each campaign lives under:
`campaigns/<campaign_id>/`

Required committed files:
- `campaign.json`
- `README.md`

Optional committed files:
- `notes.md`
- `probes/`
- `allowlist.txt`
- `denylist.txt`

## Manifest file

`campaign.json` is the machine-readable source of truth and must validate against `schemas/campaign.schema.json`.

## Required top-level fields

- `campaign_id`
- `version`
- `title`
- `description`
- `active`
- `comparability_group`
- `primary_metric`
- `budgets`
- `dataset`
- `tokenizer`
- `sequence_length`
- `vocab_size`
- `splits`
- `assets`
- `search_space`
- `promotion`
- `retention`
- `runtime`
- `baseline`

## Semantic meaning of key fields

### `comparability_group`
A string indicating which results can share a leaderboard.
Usually identical to the campaign id unless versions intentionally remain comparable.

### `primary_metric`
Object describing the optimization target.

Required subfields:
- `name`
- `direction` (`min` or `max`)
- `report_precision`
- `tie_threshold`

### `budgets`
Must contain:
- `scout_seconds`
- `main_seconds`
- `confirm_seconds`

May contain:
- `replication_seeds`
- `max_steps_override`
- `confirm_mode`

### `dataset`
Must describe:
- source
- raw format
- builder
- trust model
- raw cache root

Recommended:
- train sampling semantics
- excluded shards or partitions
- notes about public/private assumptions

### `tokenizer`
Must describe:
- kind
- vocab size
- artifact filenames

### `splits`
Must explicitly define:
- `train`
- `search_val`
- `audit_val`
- optionally `locked_val`

Each split must indicate:
- source selection method
- shard ids or deterministic partition rules
- token budget for eval when applicable

The split semantics must be explicit enough that a human can tell what is held out.

### `assets`
Must describe expected generated assets:
- tokenizer files
- pretokenized shards
- packed blocks
- hashes/manifest
- asset root path

### `search_space`
Reference to structured search policy for the campaign.
Usually points at `research/dense_gpt/search_space.py` plus campaign-specific constraints.

### `promotion`
Defines lane thresholds and rules.

### `retention`
Defines what artifacts to keep by run class:
- discarded
- promoted
- champion
- crash

### `runtime`
Defines machine/runtime constraints:
- allowed device profiles
- dtype
- backend preferences
- max expected VRAM
- compile cache policy

### `baseline`
Defines the canonical baseline target for parity and regression checks.

Required subfields:
- `name`
- `source`
- `target_metric`
- `notes`

## Required v1 campaigns

### `base_2k`
Purpose:
- preserve upstream baseline spirit
- 2048 sequence length
- 8192 vocab
- BPB metric
- fixed budget parity

Canonical held-out shards:
- search: `shard_06542.parquet`
- audit: `shard_06541.parquet`
- locked: `shard_06540.parquet`

### `stories_2k`
Purpose:
- fast secondary campaign
- different data style
- qualitative probe-friendly

Split rule:
- deterministic partitioning by stable document key hash

### `long_4k`
Purpose:
- stress long-context/runtime/data-path decisions
- not directly leaderboard-comparable to `base_2k`

## Versioning rule

A campaign version should change whenever comparability meaningfully changes:
- different tokenizer
- different split definition
- different sequence length
- different primary metric semantics
- substantially different packer assumptions

## Example authoring flow

1. copy a template from `templates/`
2. create `campaigns/<id>/campaign.json`
3. create a short `README.md`
4. run `python -m lab.cli campaign verify --campaign <id>`
5. commit both manifest and README
