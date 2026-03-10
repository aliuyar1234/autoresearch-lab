# Device profiles

Device profiles let the lab stay CUDA-first without scattering hardware assumptions across the codebase.

## Why device profiles exist

The lab is intentionally narrow, but it still needs one place to encode:

- device identity
- VRAM
- compute capability
- preferred dtype
- backend benchmark cache keys
- safe batch ceilings
- compile notes

Without an explicit device profile abstraction, these decisions leak into random modules.

## Required v1 profiles

### `rtx_pro_6000_96gb`
Represents the target workstation class.

Recommended baseline fields:
- `profile_id`: `rtx_pro_6000_96gb`
- `vendor`: `nvidia`
- `family`: `blackwell`
- `vram_gb`: `96`
- `preferred_dtype`: `bfloat16`
- `supports_compile`: `true`
- `supports_high_confirm_budget`: `true`

### `generic_single_gpu_nvidia`
Fallback profile when the device is NVIDIA but does not match a committed explicit profile.

## Recommended profile fields

- `profile_id`
- `device_name`
- `vendor`
- `family`
- `compute_capability`
- `vram_gb`
- `preferred_dtype`
- `supports_compile`
- `supports_flash_attention`
- `supports_flex_attention`
- `safe_device_batch_ceiling`
- `notes`

## Runtime behaviors tied to device profiles

The profile should influence:
- backend candidate list
- default dtype
- backend cache key
- batch autotuning ceilings
- report rendering
- warning messages

It should **not** silently rewrite campaign semantics.

## Backend benchmark shape families

Benchmark at least these shape families:

1. `base_2k_train`
2. `base_2k_eval`
3. `long_4k_train`
4. `long_4k_eval`

Each shape family should include:
- sequence length
- batch size
- head count
- head dim
- dtype
- causal flag

## Persistence

The chosen device profile id must be recorded in:
- `manifest.json`
- `summary.json`
- experiment ledger row
- reports
