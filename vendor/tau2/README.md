# Pinned official data snapshot

Repository: https://github.com/sierra-research/tau2-bench

Commit: `4ce7c0397c1eb65c9bbe59aeacfe1ca44a1cd699`

The three upstream files are stored byte-for-byte, with original relative paths:
`data/tau2/domains/airline/tasks.json`, `split_tasks.json`, and `LICENSE`.
URLs and SHA256 digests are in `configs/tau2.lock.json`; the data module checks
independent pinned anchors before using them. Do not edit the snapshot in place.

This is official task metadata, not collected training trajectories. It contains
held-out task specifications solely to verify IDs and partitions. Training must
select Train24 and must not expose Test20 task content to a model.

This directory is not a Git repository or a runnable tau2 installation. Phase 1
must prepare the complete environment data at the same commit. The optional VCS
dependency in `pyproject.toml` pins upstream source separately.

Upstream MIT license and Sierra copyright are preserved in `LICENSE`.
