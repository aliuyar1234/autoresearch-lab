# Upstream baseline summary

This document summarizes the upstream repo behavior that the lab must preserve in spirit for `base_2k`.

## Core baseline shape

Upstream minimal loop:
- `prepare.py` defines the fixed data/eval environment
- `train.py` is the mutable research file
- `program.md` tells the agent to edit `train.py`, run experiments, and keep/discard based on `val_bpb`
- `results.tsv` tracks outcomes in a lightweight way

## Important constants and behaviors

From upstream `prepare.py`:
- `MAX_SEQ_LEN = 2048`
- `TIME_BUDGET = 300`
- `EVAL_TOKENS = 40 * 524288`
- `VOCAB_SIZE = 8192`
- dataset source based on `karpathy/climbmix-400b-shuffle`
- fixed validation shard logic

From upstream `train.py`:
- CUDA-first execution
- BF16 autocast
- single-GPU assumption
- attention backend chosen from device capability
- dense model with local/global window patterning and other compact experimental ideas

From upstream `program.md`:
- mutate only `train.py`
- run for five minutes
- compare `val_bpb`
- keep if improved, otherwise reset
- iterate forever

## What to preserve

The upgraded lab should preserve:
- single-GPU focus
- fixed-budget comparability
- dense-model-first research
- compactness and hackability
- one-user workstation ergonomics

## What to upgrade

The upgraded lab should add:
- campaign abstraction
- runner + artifacts + ledger
- scheduler + archive
- promotion ladders
- offline data pipeline
- reports and reliability
- structured search plus code proposal lane
