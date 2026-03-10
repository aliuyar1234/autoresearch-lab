# Migration from upstream

## Upstream baseline summary

Upstream `autoresearch` currently revolves around:
- `prepare.py`
- `train.py`
- `program.md`
- `pyproject.toml`

It fixes:
- context length
- time budget
- tokenizer setup
- evaluation metric
- data source
- and asks the agent to mutate `train.py` while recording results in a TSV.

## Migration principle

Do not treat upstream as wrong.
Treat it as the minimal seed.

The upgraded lab should preserve:
- single GPU focus
- compactness
- fixed-budget comparability
- dense-model experimentation
- hackability

and add:
- proper orchestration
- structured persistence
- real proposal lanes
- campaign abstraction
- richer evaluation
- reporting and cleanup

## File mapping

### `prepare.py` evolves into:
- campaign asset builders
- safe tokenizer serialization
- token shard cache
- packed block builders
- campaign-local eval contracts

### `train.py` evolves into:
- `research/dense_gpt/train.py`
- `research/dense_gpt/model.py`
- `research/dense_gpt/optim.py`
- `research/dense_gpt/search_space.py`

### `program.md` evolves into:
- `AGENTS.md`
- repo-local design docs
- execution plans
- proposal packs for code-level research

### `results.tsv` evolves into:
- SQLite ledger
- artifact directory
- daily reports
- leaderboards

## Compatibility requirement

The first lab campaign, `base_2k`, must preserve upstream intent closely enough to answer:
- does the new lab reproduce the old baseline?
- does the new runner change outcomes?
- can we compare new improvements against the old starting point?

## Migration strategy

1. add docs and architecture
2. add lab scaffolding without breaking baseline
3. add runner and ledger
4. wrap or port current training path into the new lab
5. add campaigns and data pipeline
6. add scheduler and archive
7. refactor research surface once contracts are in place
