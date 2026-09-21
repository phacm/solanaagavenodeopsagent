# Skill: telemetry-health (HLD §5.9, RB-5, RB-6)

- Loss of observability is itself the incident. Missing data NEVER implies the validator is healthy or unhealthy.
- Use watchtower as the independent signal.
- Check the observer daemon unit, its cgroup limits, the mTLS link and the validator host.
- Do NOT restart the validator because telemetry was lost. Do not propose raising rate caps (P-14) ad hoc.
