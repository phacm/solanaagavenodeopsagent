# Skill: upgrade-agave (text only; M0 performs no upgrade, D4)

Source: Anza S3. Re-verify in W13.

1. Install the target version while the validator keeps running. [E] S3
2. Restart into an idle window (see restart-idle-window). [E] S3
3. Verify the running version from the log: `grep -B1 'Starting validator with' <logfile>`. [E] S3
4. Confirm catch-up afterwards with `solana catchup`. [E] S3, S5
