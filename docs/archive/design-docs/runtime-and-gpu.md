# Runtime and GPU design

## Target machine

Primary inspiration machine:
- NVIDIA RTX PRO 6000 Blackwell workstation class
- 96 GB VRAM
- single GPU
- CUDA 12.8-class software stack

## Runtime goal

Exploit the workstation without letting hardware-specific choices leak everywhere.

## Device profiles

Introduce explicit device profiles.

Required v1 profile:
- `rtx_pro_6000_96gb`

A device profile records:
- device name
- compute capability
- VRAM
- preferred dtype
- backend benchmark results
- safe batch ceilings
- compile/cache notes

## Attention backend layer

Do not hardcode one attention path forever.

Implement a backend selector that can benchmark and choose among available options, for example:
- existing kernels-based FA path
- PyTorch SDPA
- FlexAttention / FLASH backend when available
- any future CUDA/FA4-compatible path that is installed

The selector must:
- benchmark on relevant shapes
- validate correctness on a small tensor case
- record chosen backend in the run manifest
- fallback cleanly if a backend fails

## Compile/cache policy

Compilation is expensive.
Cache what matters:
- backend selection
- shape families
- compile-friendly config variants
- blacklisted backend/config combinations

## VRAM policy

Use VRAM abundance to:
- increase device batch where helpful
- reduce accumulation overhead
- support longer-context campaigns
- support confirm lanes

Do not use it as an excuse to create a bloated default model with poor step throughput.

## Performance reporting

For every run record:
- compile seconds
- train seconds
- eval seconds
- tokens/sec
- steady-state MFU
- peak VRAM
- backend used
- device profile used

## Required v1 runtime behaviors

- preflight checks CUDA/device capability
- backend microbench can be rerun
- backend selection is cached
- failures blacklist bad backend+shape combos
- run manifests always record backend and device profile
