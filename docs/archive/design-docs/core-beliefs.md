# Core beliefs

## 1. Agent legibility first

If a future agent cannot discover a rule or constraint from the repo, the rule effectively does not exist.
Therefore:
- product principles live in markdown
- contracts live in schemas
- runtime truth lives in code and SQLite
- no critical knowledge may remain only in chat or human memory

## 2. Structure beats clever prompting

A better runner, better artifacts, and better contracts are worth more than fancier prompt wording.

## 3. Dense models only

This lab is for making dense single-GPU research better, not for turning one workstation into a miniature frontier cluster.

## 4. One workstation is enough scope

The machine can be powerful, but the lab must remain one-box-native.

## 5. Structured search is a first-class citizen

Many useful improvements are:
- optimizer group changes
- schedule changes
- depth/width/window choices
- sequence curricula
- KV head ratios
- initialization changes
- backend choices
- evaluation policy changes

These should not all require open-ended code editing.

## 6. Code-level research still matters

When structured search reaches a ceiling, the lab must cleanly hand off bigger ideas to a coding agent through proposal packs and worktrees.

## 7. Reports are the product surface

The morning report is the default human interface.
If the report is weak, the lab feels weak.

## 8. Cleanup is part of the product

Artifact sprawl and stale docs are not side problems.
They are entropy.
The lab must continuously garbage-collect itself.

## 9. Comparability is campaign-local

A 2k climbmix BPB run and a 4k TinyStories run are different research environments.
Treat them as such.

## 10. Compactness is a feature

A smaller, well-shaped lab will outperform a larger generic framework when driven by agents.
