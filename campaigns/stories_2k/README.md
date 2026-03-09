# stories_2k

Fast secondary campaign using TinyStories-style data.

Purpose:
- faster iteration
- more readable qualitative probes
- campaign-local leaderboard separate from climbmix

Split rule:
- deterministic stable-hash partitioning
- train excludes partitions `997`, `998`, and `999`
