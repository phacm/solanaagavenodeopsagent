# Skill: restart-idle-window (text for a human operator; the system executes nothing)

Sources: Anza *Agave Validator Operations Best Practices* (S3); *Setup Node Failover* (S5). Accessed 2026-09-17; re-verify in W13.

1. Check own upcoming leader slots (`get_leader_schedule` evidence). Do not restart inside or near one. [E] S3
2. Prefer a restart that waits for an idle window: `agave-validator exit` under systemd, or `agave-validator wait-for-restart-window` before restarting. [E] S3, S5
3. Routine restarts do NOT fetch a snapshot: keep `--no-snapshot-fetch`. [E] S3; [A] "never" in v1
4. After restart, confirm catch-up with `solana catchup --our-localhost 8899`. Recovery is confirmed by the verifier from catch-up evidence, never from process liveness alone. [E] S5
5. Do not repeat restarts to clear a symptom. If the first restart does not recover catch-up, hand off.
