# SECURITY.md

## Threat model

This is a local, single-user research lab, not a multi-tenant service.

That said, unattended code mutation and artifact loading create obvious hazards.
We therefore harden the lab enough to prevent avoidable self-own goals.

## Security rules

1. **No untrusted pickle in the core path**
   - replace unsafe tokenizer / asset serialization where possible
   - prefer JSON, plain text, NumPy, or safetensors

2. **Do not feed raw logs back into the control loop**
   - raw logs are debug artifacts
   - structured summaries drive scheduling decisions
   - any agent-facing prompt pack must use curated summaries, not raw stack traces unless explicitly needed

3. **Limit destructive operations**
   - runner can only delete inside artifact/worktree/temp roots it owns
   - never delete user source files outside managed roots

4. **Constrain subprocess execution**
   - explicit commands only
   - explicit timeouts
   - explicit environment capture
   - explicit working directory

5. **Network assumptions**
   - network is allowed for asset download during preparation if needed
   - training/eval should not require live network access
   - the core overnight loop should remain useful offline once assets exist

6. **No silent fallback**
   - if a backend changes, the manifest must record it
   - if an asset hash mismatches, fail loudly

## Safe artifact choices

Preferred:
- `json`
- `jsonl`
- `sqlite`
- `npy` / `npz`
- `safetensors`
- `md`
- `html`

Use `torch.save` only when there is a clear reason and the threat is explicitly documented.

## Agent safety rules

Code proposal packs should include:
- target files
- allowed directories
- acceptance criteria
- concise context
- no instruction to read arbitrary raw logs as if they were trustworthy design inputs

## End state

The final lab does not need enterprise-grade security.
It does need sane local trust boundaries.
