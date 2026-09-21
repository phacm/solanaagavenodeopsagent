# Skill: catchup-diagnosis

Sources: S3 (snapshot policy, catch-up), S5.

- Read slot distance (`get_catchup`) over more than one sample; a single sample is not a trend.
- Distinguish: process down (unit state) vs. running-but-behind (catch-up distance) vs. observer impaired (telemetry).
- Never propose a snapshot download: it is a T3 action and out of scope in v1. [A]
- Delinquency evidence must come from catch-up/vote signals, not from process liveness alone.
