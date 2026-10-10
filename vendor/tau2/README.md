# Pinned official data snapshot

Repository: https://github.com/sierra-research/tau2-bench

Commit: `5bfa7e37b36656b37dc6d022156be6563c1007f3`

The three upstream files are stored byte-for-byte, with original relative paths:
`data/tau2/domains/airline/tasks.json`, `split_tasks.json`, and `LICENSE`.
URLs and SHA256 digests are in `configs/tau2.lock.json`; the data module checks
independent pinned anchors before using them. Do not edit the snapshot in place.

Running the environment additionally needs `data/tau2/domains/airline/db.json`
and `policy.md`. Both are hash-pinned in the `runtime_files` section of the same
lock file but deliberately not committed — `db.json` alone is about 7 MB. They
are materialized into the ignored `data/` tree and verified by
`airline_data.runtime_lock` before any evaluation run.

This is official task metadata, not collected training trajectories. It contains
held-out task specifications solely to verify IDs and partitions. Training must
select Train24 and must not expose Test20 task content to a model.

This directory is not a Git repository or a runnable tau2 installation. Evaluation
requires the complete upstream checkout at the same commit; the optional VCS
dependency in `pyproject.toml` pins upstream source separately.

Upstream MIT license and Sierra copyright are preserved in `LICENSE`.
