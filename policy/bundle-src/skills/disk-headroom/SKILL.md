# Skill: disk-headroom [A]

- Evidence: `get_host_metrics` volumes below P-04 free.
- Identify the volume (ledger vs. accounts) and the growth source from evidence.
- The operator frees space outside the ledger/accounts directories or extends the volume. Never propose deleting ledger or accounts data while the validator runs.
