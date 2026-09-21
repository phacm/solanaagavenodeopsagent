# Plan: Solana Validator Node Self-Operating Agent (multi-provider: Claude, Codex, Gemini/Antigravity)

| Field | Value |
|---|---|
| Document | Implementation plan, **v0.5** (DRAFT — for review before any code is written) |
| Author | Peng Huang (peng.huang@acm.org) |
| Date | 2026-09-21 |
| Supersedes | v0.4 (2026-09-21), v0.3 (2026-09-17), v0.2 (2026-09-17), v0.1 (2026-08-10) |
| Companion | `valops-agent-mvp-hld-v0.5.md` (refines this plan for milestone M0) |
| Status | **Conditional no-go for implementation.** M0A coding starts only after the G0 delivery package (§7.2) is approved |
| Governing language | English (Chinese summary in §18 is informational) |

---

## Change Log

| Version | Change | Driver |
|---|---|---|
| v0.1 | Initial plan | — |
| v0.2 | Independent `proposal-judge` subagent in front of human approval | Review F1 |
| v0.2 | Post-action verification and the "resolved" state owned by a deterministic framework verifier. Policy artifacts read-only and hash-checked | Review F2 |
| v0.2 | Structured episode record and a fresh session per step, replacing resumed long sessions. Diagnosis expressed as falsifiable hypotheses | Review F3 |
| v0.2 | Operating-system sandbox for the agent process | Review F4 |
| v0.2 | Versioned skills library with compatibility matrices | Review F5 |
| v0.2 | Optional offline tuning loop as a research track | Review F6 |
| v0.2 | Git-backed configuration repository and hash-chained audit log | Review F7 |
| v0.2 | Per-role cost measurement | Review F8 |
| v0.2 | Search-and-revert on live systems, self-expansion of scope, and single-seed evaluation recorded as anti-patterns | Review §4 |
| **v0.3** | **Principals are authenticated by the transport, never supplied by the caller.** The episode store is split into three separate capability endpoints; the agent-facing endpoint has no state-transition, verification or closure capability at all (§4.3, SR-14) | Review-2 F1 |
| **v0.3** | **Single audit sequencer** replaces multiple direct chain writers, with fsync, server-stamped principals, payload hashing, and signed chain heads anchored outside the ops host. The validator-host daemon keeps its own chain and forwards checkpoints (§4.4, SR-15) | Review-2 F2 |
| **v0.3** | **Explicit four-class process topology** (untrusted SDK worker / trusted controller / capability brokers / observer daemon). The in-process policy-gate hook is demoted to defence-in-depth; brokers re-enforce every check server-side (§4.2, SR-16) | Review-2 F3 |
| **v0.3** | SDK configuration corrected: an explicit `tools` list must carry `Skill`; a **prompt-inlined fallback removes the skills dependency from the critical path**; sandbox settings specified with fail-closed intent (§5.2, §7 W1) | Review-2 F4 |
| **v0.3** | Episode concurrency made safe: authorised-principal transition table, compare-and-swap revisions, idempotency keys, defined behaviour for spontaneous recovery, mandatory closure report, terminal semantics for `handed_off` (§5.7) | Review-2 F5 |
| **v0.3** | **"Zero availability risk" withdrawn** and replaced with "no intentional validator state-change path", plus resource limits on the observer daemon and a first-class **telemetry-health episode class** (§2.5, §3.2 SR-17, §5.1) | Review-2 F6 |
| **v0.3** | Consensus mode is a declared deployment fact, cross-checked three ways; disagreement yields `unknown` and prohibits mode-specific recommendations (§5.9, FR-8 revised) | Review-2 F7 |
| **v0.3** | **Immutable, hash-addressed policy bundles**; an episode is bound to one bundle for its lifetime; drain, migration, emergency revocation and rollback defined (§5.10, SR-10 revised) | Review-2 F8 |
| **v0.3** | Runner validates the required artefact after every step before advancing; model prose is non-authoritative (§5.11, FR-12) | Review-2 F9 |
| **v0.3** | Document traceability fixed; "Executor" and "Observer Daemon" separated by milestone (§0.1) | Review-2 F10 |
| **v0.3** | Phase 1 split into **M0A (containment prototype)** and **M0B (diagnosis workflow)**; M0B does not start until M0A's four properties are demonstrated (§7) | Review-2 Recommendation |
| **v0.3** | Competitive positioning recorded, and its roadmap recommendations routed to the matching open decisions without closing them (§15, §13) | Competitive analysis C1 |
| **v0.4** | **M0 product definition frozen at G0:** a single-Agave-validator, testnet-only, read-only incident-analysis assistant for a named on-call operator — explicitly *not* an autonomous validator operator. Product hypothesis, supported fault classes, watchtower baseline, report/alert workflow, feedback rubric and measurable targets added (§2.6) | Review-3 |
| **v0.4** | **Decision register with DRI, approver, due gate, default-if-late and required evidence** for every M0A blocker (D1/D7, D3, D5, D6, D11, D14, D15, D16). D13, D10, D17, non-Agave clients and M1 execution explicitly excluded from M0 (§13) | Review-3 |
| **v0.4** | **D6 split into an auditable parameter register**: unit, owner, safe initial value, bounds, measurement source, review cadence (§13.2) | Review-3 |
| **v0.4** | **Gate classes separated:** deterministic security gates require 100% pass; model-quality gates use frozen fixtures, repeatable controls, confidence intervals and human adjudication (§8.1) | Review-3 |
| **v0.4** | **Staged authorisation G0 → G1 → G2** with named go/no-go authority: M0A coding needs an approved delivery package; M0B needs M0A proven on *real, not mocked* boundaries; M1 needs safety gates **and** operator-value evidence (§7.2) | Review-3 |
| **v0.4** | **Time-boxed M0A charter**: DRIs, estimates, critical path, environment-readiness checklist (§7.1) | Review-3 |
| **v0.4** | **Delivery governance**: change control, data retention and access, backup and recovery tests, degraded-mode runbooks (§17; runbooks in HLD §9.1) | Review-3 |
| **v0.4** | **Cross-document corrections:** D3 split into D3 (M0 testnet environment) and new D18 (Phase-4 target cluster); consensus mode uniformly described as *the declared mode cross-checked against three observed inputs — four inputs in total*; hypotheses gain a `rank` field so "top-ranked hypothesis" is measurable; W1 now depends on D1/D7 being pinned (§5.7, §5.9, §13) | Review-3 |
| **v0.4** | Stale-anchor behaviour defined: anchor lag beyond the maximum (D15) stops new LLM steps (§4.4) | Review-3 (D15) |
| **v0.5** | **Multi-provider support: Claude, Codex, Gemini via Antigravity.** Provider matrix, runtime-adapter contract, conformance profile PC-1 … PC-9, admission outcomes, per-configuration evaluation, pre-approved fallback bundles (§5.12) | Owner requirement, 2026-09-21 |
| **v0.5** | **Model broker**, a fifth capability broker: sole holder of every provider credential, sole network egress for the worker, model allowlist, provider-neutral turn/token/USD limits, and the transcript of record (§5.12.2; SR-8, SR-11 revised) | Owner requirement |
| **v0.5** | **Native API adapter** per provider, with no built-in tools, as the fallback for any runtime that fails admission (§5.12.3) | Owner requirement |
| **v0.5** | "SDK worker" generalised to "worker"; §5.2 becomes the **reference (Claude) adapter**; decisions D19–D22 and parameters P-29 … P-31 added; W1 runs per configuration (§13) | Owner requirement |

"Review-2" above refers to source **V1** (§14), the review of plan v0.2 and HLD v0.1; its findings are numbered F1–F10, and are distinct from the earlier review whose findings drove v0.2. "Review-3" refers to source **V2** (§14), the pre-coding review of plan v0.3 and HLD v0.3, which returned a **conditional no-go** pending the delivery definition added in v0.4. v0.4 retains every v0.3 safety property that review asked to keep.

All v0.3 and v0.4 changes are design choices **[A]** unless tagged otherwise. Neither inspiring reference (R1, a preprint in another domain) nor the competitive analysis (C1, unverified third-party market research) validates any requirement in this plan (§1.1, §1.2).

---

## 0. Abbreviations (first-use definitions)

| Abbreviation | Full term |
|---|---|
| SDK | Software Development Kit |
| MCP | Model Context Protocol |
| LLM | Large Language Model |
| CLI | Command-Line Interface |
| RPC | Remote Procedure Call |
| SOL | Native token of the Solana network |
| BFT | Byzantine Fault Tolerance (as in "Tower BFT", Solana's pre-Alpenglow vote/lockout mechanism) |
| SSH | Secure Shell |
| mTLS | Mutual Transport Layer Security |
| UDS | Unix Domain Socket |
| CAS | Compare-And-Swap |
| WORM | Write Once, Read Many (immutable object storage) |
| OS | Operating System |
| JSON | JavaScript Object Notation |
| UUID | Universally Unique Identifier |
| MTTD / MTTR | Mean Time To Detect / Mean Time To Recover |
| StaaS | Staking-as-a-Service |
| USD | United States Dollar |
| PDF | Portable Document Format |
| TBD | To Be Decided |
| DRI | Directly Responsible Individual |
| RPO / RTO | Recovery Point Objective / Recovery Time Objective |
| p50 / p95 / p99 | 50th / 95th / 99th percentile |

### 0.1 Terminology Discipline (Review-2 F10)

Two validator-host processes were previously conflated. They are now separated by milestone and never used interchangeably:

| Term | Meaning | Exists in |
|---|---|---|
| **Observer Daemon** | Validator-host process serving a **read-only** command table by command id. Cannot change validator state. | M0 onward |
| **Executor** | Validator-host process able to run **state-changing** commands, only under a valid human approval token with executor-side precondition re-checks. | **M1 onward. Does not exist in M0.** |

"Framework Verifier" (plan v0.2) and "Recovery Verifier" (HLD) are the same component in two modes: in M0 it confirms *recovery* from re-sampled signals; from M1 it additionally performs *post-action* verification. This plan calls it the **Verifier** and names the mode where it matters.

---

## 1. Evidence Grading

- **[E]** Externally verifiable — traceable to a source in §14.
- **[A]** Assumption or design choice — not externally validated; must be reviewed.
- **[H]** Hypothesis — expected to hold; must be validated in testing.
- **[U]** Unknown from public sources — must be resolved before dependent work.

No performance target, stake threshold, reward figure, market-share figure, or cost estimate is asserted in this plan. Every such value is **TBD by owner** or tagged **[U]**.

**v0.4 qualification.** The parameter register (§13.2) and the M0A charter (§7.1) contain *proposed* initial values and effort estimates. They are [A] planning inputs, chosen to err in the safe direction, and they have no force until the owner approves them at G0. They are not performance claims.

### 1.1 Status of the VibeServe / VibeSys Reference

R1 (arXiv:2605.06068) is a preprint. Its authors state its limitations: single-seed runs, a user-supplied correctness checker, and a non-trivial compute budget [E R1 §6]. It studies *build-time* synthesis of LLM serving code in isolated, revertible workspaces, and its evaluation used Codex CLI [E R1 §3.2, §4.1]. This plan adopts only R1's *structural safeguards*. R1's search mechanism is not used against the live validator (§2.4).

### 1.2 Status of the Competitive Analysis (new in v0.3)

C1 (`ag-solvalops-competitive-analysis.md`) is third-party market analysis supplied to the project. Its market claims — segment share, competitor capability, adoption percentages, cost-reduction percentages, and protocol-governance status — are **not independently verified here and are tagged [U]**. They are recorded because they bear on positioning and on four open decisions, not because they establish fact.

Specific items carried forward with their status:

| C1 claim or recommendation | Status in this plan |
|---|---|
| Competitor segmentation and feature matrix (§3, §4 of C1) | [U]. Recorded in §15 as positioning input |
| "Over 80% of Solana validators run Jito-Solana forks" | [U]. Routed to D2; not used to justify scope |
| "Community approval of SIMD-0326 (Alpenglow)"; vote transactions and state-file change | Protocol-governance status is [U] here. The *state-file distinction* (`tower-*.bin` vs. `vote_history-<IDENTITY>.bin`) is [E] S5 |
| Recommendation 1 — shadow mode across 5–10 testnet validators | Routed to D13 and D18 (v0.4; was D3 in v0.3). Conflicts with the single-validator scope and is **excluded from M0** (§2.3, §13.1) |
| Recommendation 2 — position alongside `solana-validator-failover` rather than rebuild it | Accepted in spirit as a **documentation-only** change: the failover runbook skill may reference external failover tooling. No integration, and failover stays T3 (§2.3). [A] |
| Recommendation 3 — add Jito-Solana skills in Phase 1/2 | Routed to D2. Any client whose commands are not verified against a primary source stays [U] and is blocked from T2 (§5.8) |
| Recommendation 4 — choose TypeScript for D1 | Routed to D1, with C1's own rationale and its weaknesses recorded (§13 D1) |
| Recommendation 5 — tiered models per role, "60–80% cost reduction" | Structure routed to D7; the percentage is [U]. The model names C1 cites are **stale** and must not be copied into `policy/` (§13 D7) |

---

## 2. Scope

### 2.1 Goal

Build an agent, served by any of three model providers (Anthropic Claude, OpenAI Codex, Google Gemini via Antigravity; §5.12), that performs day-to-day operations of a single Solana validator (Agave client). The agent observes health continuously, diagnoses problems, recommends remediation, and — from M1 — executes a small set of actions that are independently judged and approved by a human. It works under safety limits that are enforced outside the model, in processes the model cannot reach.

That is the long-term goal across all phases. **The first deliverable, M0, is much narrower and is defined in §2.6**: a read-only incident-analysis assistant for one named on-call operator and one Agave testnet validator. M0 is not an autonomous validator operator, and nothing in M0 is judged against that goal.

### 2.2 In Scope (v1)

1. Health observation: delinquency, catch-up status, identity account balance, leader schedule, service state, disk and log signals.
2. **Telemetry health** as a first-class observed subject: the agent's own ability to observe the validator is itself monitored and produces incidents (new in v0.3, Review-2 F6).
3. Hypothesis-driven diagnosis and incident reports.
4. Gated actions from M1 (restart in an idle window, upgrade workflow). Every gated action passes an independent judge, a human approval, and framework verification.
5. A tamper-evident audit trail anchored outside the ops host.

### 2.3 Out of Scope (v1)

| Item | Reason | Tag |
|---|---|---|
| Any operation using the authorized withdrawer keypair | The withdrawer key must never be stored on the validator; withdrawals are done on a trusted computer | [E] S3, S4 |
| Autonomous identity failover (`set-identity`) | A safety-critical procedure with strict preconditions. v1 only drafts the runbook, which may reference external failover tooling (§1.2) | [E] S5 for the procedure; [A] for keeping it human-only |
| Stake, delegation, and commission management | Financial actions | [A] |
| Clients other than Agave | Commands not verified for other clients. **Excluded from M0 regardless of the D2 answer** | [U] (D2) |
| Multi-validator fleet orchestration | Deferred. Note: C1 Recommendation 1 proposes *observation* across 5–10 validators, which is a narrower question — see D13. **Multi-validator shadowing is excluded from M0**; D13 is decided no earlier than Phase 4 | [A] |
| Offline tuning loop (§11) | Research track. **Excluded from M0** | [A] (D10) |
| Publication of operator-trust metrics | **Excluded from M0.** M0 results are internal evidence for G2 only | [A] (D17) |

### 2.4 Anti-Patterns (explicitly prohibited)

| Prohibited | Reason | Tag |
|---|---|---|
| Try-measure-revert search on the live validator | Reverting does not undo downtime or missed leader slots | [A]; leader-slot concern from [E] S3 |
| Agent widening its own scope, tiers, thresholds, or benchmark conditions | Tiers are fixed by the owner. R1 reports its agent escalating benchmark load on its own [E R1 §4.2]; that behavior is unacceptable here | [A] |
| Agent writing to executor or daemon code, validator configuration, policy, skills, or the audit log | Integrity of the control plane | [A] |
| Agent marking an episode "resolved" or grading its own action | Self-grading; see §5.6 | [A], inspired by [E] R2 |
| Single-trial safety evaluation | Safety claims need repeated trials (P-22, P-23; §8.1) | [A] |
| **Any component asserting its own identity in a request** | Authorization must derive from the transport, not from a field a caller can set (Review-2 F1) | [A] |
| **Treating an in-process hook as an enforcement boundary** | The `PreToolUse` hook runs inside the process hosting the model. It is defence-in-depth; the broker is the control (Review-2 F3) | [A] |
| **Claiming zero availability risk** | A read-only path still consumes CPU, memory, disk I/O, file descriptors, process slots and local RPC capacity (Review-2 F6) | [A] |
| **Silently continuing when a required artefact was not produced** | A session that ends without writing its artefact has failed, whatever its prose says (Review-2 F9) | [A] |

### 2.5 Availability Claim, Restated (Review-2 F6)

v0.2 stated that the MVP's availability risk was "zero" because no state-changing command exists. That claim is withdrawn.

**What is guaranteed [A]:** there is **no intentional validator state-change path** in M0. No command in the observer command table changes validator state; adding one requires a code change, a policy-bundle change, and review (§5.10).

**What is not guaranteed, and how it is bounded [A]:**

| Residual risk | Bound |
|---|---|
| CPU, memory, file descriptors, process slots on the validator host | Observer daemon runs under systemd resource limits and cgroup constraints; per-command concurrency of one; global and per-command rate limits |
| Local RPC capacity (`solana catchup --our-localhost 8899` and similar consume validator RPC) | Rate limits sized by owner; circuit breaker that suspends polling and opens a telemetry-health episode when local RPC latency degrades |
| Disk I/O from log reads | Bounded tail sizes and output caps; no full-log scans |
| Timeouts causing retry storms | A timeout is a reported outcome, never an automatic retry (HLD OD-7) |

Concrete limit values are set in the parameter register (§13.2, D6).

### 2.6 M0 Product Definition (new in v0.4, Review-3)

**Statement [A].** *M0 is a single-Agave-validator, testnet-only, read-only incident-analysis assistant for a named on-call operator. It is not an autonomous validator operator.* It observes one validator, opens an episode when something is wrong, and hands the operator an evidence-linked diagnosis and a recommendation that the operator may act on by hand. It executes nothing.

| Element | M0 definition | Frozen at |
|---|---|---|
| User | One **named** on-call operator, plus one named backup for escalation. Named in the G0 package | G0 |
| Target | One Agave validator on testnet (D3). No other client, cluster or validator | G0 |
| Autonomy | T0 and T1 only (§5.1). No executor, no approval service, no validator write path | Fixed by design |
| Product hypothesis | See below | G0 |
| Supported fault classes | FC-1 … FC-5, below | G0 |
| Watchtower baseline | Baseline campaign, below | Procedure at G0; data before M0B run-in |
| Report and alert workflow | Steps AW-1 … AW-6, below | G0 |
| Human feedback rubric | FB-1 … FB-6, below | G0 |
| Measurable targets | Q-1 … Q-8, below; values in §13.2 | Metrics at G0; values no later than the start of the M0B run-in |

Anything frozen changes only through change control (§17.1). Changing a target or a fault class after an evaluation run invalidates that run.

**Product hypothesis [H].** *For the supported fault classes, an evidence-linked incident report delivered within the report-latency target lets the on-call operator reach a correct diagnosis faster and with less effort than the `agave-watchtower` alert alone, at an acceptable cost, and without measurable impact on the validator.* M0 exists to test this hypothesis. G2 (§7.2) asks whether the evidence supports it.

**Supported fault classes [A].** Each class has a reproducible testnet injection and an adjudicated root cause recorded by the injector before the operator reads any report.

| ID | Fault class | Injection on testnet | Primary signals |
|---|---|---|---|
| FC-1 | Validator process stopped or unit failed (leads to delinquency) | Stop the systemd unit | unit state, monitor, catch-up |
| FC-2 | Identity account balance below floor | Transfer from the testnet identity until below the floor | `identity_balance` |
| FC-3 | Ledger or accounts volume low on headroom | Fill the volume with a ballast file to below the floor | `host_metrics` |
| FC-4 | Running version differs from expected | Declare an expected version in the bundle that differs from the running one | `running_version` |
| FC-5 | Telemetry loss (observer unreachable, slow, or stale) | Stop, throttle or partition the observer daemon | telemetry probes (§5.1) |

An incident outside FC-1 … FC-5 still opens an episode and still produces a report, labelled **outside supported classes**. It counts towards operator burden (Q-5) and cost (Q-6), and is excluded from diagnosis quality (Q-1) and actionability (Q-2).

**Watchtower baseline [A].** Before the M0B run-in, a baseline campaign injects each supported fault class P-24 times with **only** `agave-watchtower` alerting. The operator diagnoses from the watchtower alert and their own tools, and fills in rubric items FB-1 and FB-4. The injector, not the operator, chooses the order, randomises it, and includes no-fault control windows. During the M0B run-in watchtower keeps running unchanged on the same channel, so that detection and diagnosis times are compared on paired incidents. The baseline is recorded once and is not re-run to improve a comparison.

**Report and alert workflow [A].**

| Step | What happens |
|---|---|
| AW-1 | `agave-watchtower` alerts as it does today. This path is independent of the agent (NFR-1) |
| AW-2 | The sentinel opens an episode. When the reporter step completes, one alert goes to the D5 channel carrying: severity; fault class or *outside supported classes*; the top-ranked hypothesis; the recommendation or no-action record; the Judge verdict; and a link to the full report with evidence references |
| AW-3 | The operator acknowledges within P-20. An unacknowledged alert is re-sent once, then escalated to the backup operator |
| AW-4 | The operator acts, or does not, outside the system, then records the rubric within P-21 |
| AW-5 | The verifier confirms recovery (§5.6). A closure report and closure alert follow (FR-15) |
| AW-6 | The project owner reviews rubric data and burden metrics weekly. Findings go through change control, never into a live bundle directly |

**Human feedback rubric [A].** It is completed per report by the on-call operator.

| ID | Item | Scale |
|---|---|---|
| FB-1 | Diagnosis: does the **top-ranked hypothesis** (rank 1 in the latest diagnosis step, §5.7) match the adjudicated root cause? | correct · partially correct (right component, wrong mechanism) · incorrect · no plausible hypothesis |
| FB-2 | Recommendation actionability | 1 executable as written · 2 minor edits · 3 major rework · 4 not usable — plus an independent **unsafe** flag: following it as written would have harmed the validator |
| FB-3 | Evidence sufficiency: could the operator check each claim from the cited signals alone? | yes · partly · no |
| FB-4 | Operator time from opening the alert to a decision | minutes |
| FB-5 | Alert value | actionable · informational · false alarm · duplicate of watchtower with nothing added |
| FB-6 | Free text | — |

**Adjudication.** For injected faults the ground truth is the injection record. For organic incidents a second reviewer adjudicates FB-1 and FB-2. That reviewer is neither the on-call operator nor the author of the role prompts. Disagreements go to the project owner. Any FB-2 **unsafe** flag is reviewed individually and blocks G2 until resolved.

**Measurable targets [A].** The metrics are fixed here. Their target values and confidence requirements live in the parameter register (§13.2) and are set by the owner.

| ID | Metric | Definition | Measurement source | Gate class (§8.1) |
|---|---|---|---|---|
| Q-1 | Diagnosis quality | Share of in-class episodes where FB-1 = correct | Rubric FB-1 + injection record | Model quality |
| Q-2 | Recommendation actionability | Share of in-class reports with FB-2 ∈ {1, 2}; **and zero unsafe flags** | Rubric FB-2 | Model quality (unsafe count: deterministic, must be 0) |
| Q-3 | Report latency | Episode open → AW-2 alert delivered, p50 and p95 | Store timestamps; alert-sink acknowledgement | Measured |
| Q-4 | Time to correct diagnosis vs. baseline | Paired difference between FB-4 with the report and FB-4 in the watchtower baseline, per fault class | Rubric FB-4; baseline campaign | Model quality |
| Q-5 | Operator burden | Alerts per day; false-alarm share (FB-5); median FB-4 | Alert sink; rubric | Measured against ceiling |
| Q-6 | Cost | USD per episode and per day, per role | SDK `total_cost_usd`, recorded per step by the controller (HLD §5.2 rule R-6) | Measured against ceiling |
| Q-7 | Observation impact | Validator local-RPC latency with observer on vs. off (paired windows); observer resource use vs. cgroup limits | Observer probes; cgroup accounting | Measured against tolerance |
| Q-8 | Safety | Unauthorized executions; containment-gate failures | Audit chain; CI | **Deterministic: must be 0** |

---

## 3. Requirements

### 3.1 Functional Requirements

| ID | Requirement | Source / Tag |
|---|---|---|
| FR-1 | Detect delinquency and alert promptly | [E] S2 |
| FR-2 | Integrate with `agave-watchtower`, running on a server separate from the validator | [E] S2 |
| FR-3 | Check identity account balance regularly and alert below a floor (P-02, §13.2) | [E] S3 |
| FR-4 | Restarts avoid leader slots, using `agave-validator exit` under systemd or `wait-for-restart-window` (M1+) | [E] S3, S5 |
| FR-5 | Upgrade flow: install while the validator runs → restart in an idle window → verify version with `grep -B1 'Starting validator with' <logfile>` (M1+) | [E] S3 |
| FR-6 | Default to `--no-snapshot-fetch` on routine restarts and run `solana catchup <pubkey>` afterwards. The agent never downloads a snapshot on its own in v1 | [E] S3; [A] "never" |
| FR-7 | The **Verifier** confirms state deterministically — recovery in M0, post-action from M1 — with `agave-validator monitor` or `solana catchup --our-localhost 8899`, and records an immutable result | [E] S5 for commands; [A] framework ownership |
| FR-8 | **(revised v0.3, wording fixed v0.4)** Consensus mode is a **declared deployment fact**, cross-checked against **three observed inputs**: the running Agave version, cluster feature state, and consensus state files — **four inputs in total**. Agreement of all four selects the matching skill variant; **any disagreement yields `unknown`, and mode-specific recommendations are prohibited** | [E] S5 for the file distinction; [A] for the cross-check; activation on the target cluster is [U] (D9) |
| FR-9 | Every anomaly produces an episode record (§5.7) and an incident report | [A] |
| FR-10 | Optional metrics reporting via `SOLANA_METRICS_CONFIG` | [E] S2 |
| FR-11 | Each T2 proposal carries a Judge verdict (PASS or FAIL, with evidence) before it reaches a human (M1+) | [A] |
| **FR-12** | **(new)** The runner advances state only after validating that the step produced its required artefact and that the artefact satisfies its schema. Model prose is never the artefact | [A], Review-2 F9 |
| **FR-13** | **(new)** Loss or degradation of observability is itself an incident: it opens a **telemetry-health** episode. Missing data never opens or escalates a *validator-health* episode on its own | [A], Review-2 F6 |
| **FR-14** | **(new)** Every episode is bound at open to one immutable, hash-addressed policy bundle and uses that bundle until it terminates | [A], Review-2 F8 |
| **FR-15** | **(new)** After an episode reaches `resolved`, a closure report and alert are produced | [A], Review-2 F5 |

### 3.2 Security and Safety Requirements

| ID | Requirement | Source / Tag |
|---|---|---|
| SR-1 | Validator runs as non-root `sol`. The observer daemon (and, from M1, the executor) runs as a separate non-root `valops` user that cannot read keypairs | [E] S4 (non-root); [A] |
| SR-2 | No withdrawer keypair on the validator host or the ops host | [E] S4 |
| SR-3 | No arbitrary shell. Only typed, allowlisted tools, enforced in four layers: SDK deny rules, OS sandbox, **capability broker**, daemon command table | [A]; SDK deny semantics [E] S7 |
| SR-4 | Every tool call passes a `PreToolUse` policy hook and an audit hook. Hook deny applies in all modes. **These run inside the untrusted worker and are defence-in-depth only** (SR-16) | [E] S7, S8 for hook semantics; [A] for the demotion |
| SR-5 | `bypassPermissions` is prohibited | [A]; rationale [E] S7 |
| SR-6 | Logs, gossip, and RPC data are untrusted input. Tool outputs are structured, truncated, and redacted. No instruction from those sources is acted on | [A] |
| SR-7 | Host hygiene is report-only: pending updates, SSH password authentication, fail2ban, open ports | [E] S4 for the checks; [A] report-only |
| SR-8 | **(revised v0.5)** Every model provider is authenticated by API key. **All provider keys are held by the model broker only** (§5.12.2), never by the controller's worker children and never by the worker. The worker holds no provider credential of any kind: no key, no cached login, no OAuth token | [E] S6, S11; [A] for the split |
| SR-9 | Per-session `max_turns` and `max_budget_usd`, plus a per-episode retry budget. Values in the parameter register: P-05, P-06, P-08, P-09 (§13.2) | [E] S9 for options; [A] retry budget |
| SR-10 | **(revised v0.3) Policy integrity by immutable bundle.** Command table, thresholds, hook code, system prompts, skills, and verifier rules live in a hash-addressed bundle that is read-only to every process. An episode records its bundle id at open and is served from that bundle. Bundle identity is verified at process start, at episode open, and at every broker call. A verification failure puts the system in observe-only and alerts | [A], Review-2 F8 |
| SR-11 | **OS sandbox.** The worker process runs with no filesystem writes and no network egress except the **model broker** (§5.12.2) and the broker sockets passed to it as inherited descriptors | [A]; backend choice D11 |
| SR-12 | **Judge isolation.** `proposal-judge` runs in a fresh session. It receives only the raw signal snapshot, the proposal, and the skill preconditions, never the orchestrator's, diagnostician's or planner's reasoning | [A] |
| SR-13 | **Audit integrity.** The audit log is append-only and hash-chained, written only by the audit sequencer (SR-15) | [A] |
| **SR-14** | **(new) Authenticated principals.** Every store and broker call derives its principal from the transport — a dedicated UDS with OS-enforced ownership and peer credentials, or an mTLS identity — plus a controller-minted capability token scoped to one episode, one role, one session, with an expiry and a nonce. **No request field names the caller.** The agent-facing endpoint exposes no state-transition, verification or closure operation at all | [A], Review-2 F1 |
| **SR-15** | **(new) Single audit sequencer with external anchoring.** One process owns the ops-host chain: it serialises entries, stamps the authenticated principal, hashes referenced payloads, fsyncs, and periodically signs and exports a chain head to append-only external storage (WORM object storage or a remote log service). The observer daemon maintains its own local chain on the validator host and forwards signed checkpoints; the sequencer records the daemon's chain head so truncation is detectable | [A], Review-2 F2 |
| **SR-16** | **(new) Process separation with fail-closed privileges.** Four process classes with disjoint credentials: untrusted worker (any provider adapter, §5.12), trusted controller, capability brokers (including the model broker), observer daemon (§4.2). A worker compromise must yield no capability beyond the tool surface its capability token already permits | [A], Review-2 F3 |
| **SR-17** | **(new) Resource containment on the validator host.** The observer daemon runs under explicit systemd/cgroup limits and per-command concurrency and rate caps, so that observation cannot degrade the validator (§2.5) | [A], Review-2 F6 |
| **SR-18** | **(new) Concurrency safety.** Every episode write carries an idempotency key; every state transition is a compare-and-swap on the episode revision. Duplicate delivery is a no-op; a stale transition is refused | [A], Review-2 F5 |

### 3.3 Non-Functional Requirements

| ID | Requirement | Tag |
|---|---|---|
| NFR-1 | The LLM is not in the keep-alive path. systemd and watchtower work without the agent | [A] |
| NFR-2 | Any agent failure (API error, budget exhausted, retry budget exhausted, Judge FAIL after retries, missing artefact) means no action and a human alert | [A] |
| NFR-3 | Actions are idempotent or guarded by preconditions re-checked by the executor (M1+) | [A] |
| NFR-4 | No single agent context spans a whole episode. State lives in the episode record | [A]; motivation [H] from R1 §1 (compaction drift) |
| **NFR-5** | **(new)** Every control-plane component degrades in a defined order and never fails silently (§9 of the HLD) | [A] |

---

## 4. Architecture

### 4.1 Component View

```
┌──────────────────────────── Ops host (separate from validator) ─────────────────────────────────┐
│                                                                                                  │
│  agave-watchtower ─────┐                                                                         │
│                        ▼                                                                         │
│  Sentinel (deterministic) ── opens episode ──► Episode Store service                              │
│        │  telemetry-health checks                       ▲ control endpoint                        │
│        ▼                                                │                                         │
│  ┌──── TRUSTED CONTROLLER (mints capability tokens; holds NO provider key) ──────────────────┐   │
│  │  Episode Runner: deterministic step machine, CAS state transitions, artefact validation   │   │
│  │  spawns one UNTRUSTED WORKER per step, passing only broker socket descriptors + token     │   │
│  └───────────────────────────────────────────────────────────────────────────────────────────┘   │
│        │ fork/exec                                                                                │
│  ┌──── UNTRUSTED WORKER (OS sandbox, SR-11) ─────────────────────────────────────────────────┐   │
│  │  ONE adapter (§5.12.3): Claude SDK │ codex exec │ agy -p │ native API loop                │   │
│  │  one FRESH session — one role, one episode, one bound configuration                       │   │
│  │   diagnostician │ change-planner │ proposal-judge │ reporter                              │   │
│  │  tools: MCP server "valops" (stdio) — every tool is an RPC stub over a broker socket      │   │
│  │  provider extras (Claude hooks, Codex approvals, agy allow-rules): DEFENCE IN DEPTH ONLY  │   │
│  │  credentials: one capability token. NO provider credential. No fs write.                  │   │
│  │  network: model broker only                                                               │   │
│  └───────────────────────────────────────────────────────────────────────────────────────────┘   │
│        │ UDS (inherited fds)                                                                      │
│  ┌──── CAPABILITY BROKERS (each a small process, one job, own socket, own principal) ────────┐   │
│  │  episode-broker  (agent endpoint: appends only — no set_state, no verification)           │   │
│  │  observer-broker (validates + rate-limits, then calls the validator host)                 │   │
│  │  report-broker   (report store + alert sink)                                              │   │
│  │  audit-sequencer (SOLE writer of the ops-host chain; signs and anchors chain heads)       │   │
│  │  model-broker    (SOLE holder of provider keys; worker's only egress; limits; transcript) │   │
│  │                   ──► Anthropic │ OpenAI │ Google (per bound configuration only)          │   │
│  └───────────────────────────────────────────────────────────────────────────────────────────┘   │
│                                                                                                  │
│  Policy bundle store (immutable, hash-addressed, read-only to all) ── active bundle pointer      │
│  Verifier (deterministic) ── the ONLY writer of verification records and of `resolved`           │
│  Approval service (M1+) ◄──► Human approver (sees proposal + Judge verdict + raw signals)        │
│                         │ typed RPC over mTLS, command-id allowlist                              │
└─────────────────────────┼────────────────────────────────────────────────────────────────────────┘
                          ▼                                          ▲ signed chain checkpoints
┌──────────────────────── Validator host ─────────────────────────┐  │  ┌──────────────────────┐
│ Observer daemon (user `valops`, non-root, no keypair access)     │──┘  │ External anchor      │
│   read-only command table · argument validation · output caps    │     │ (WORM object store / │
│   rate limits · concurrency 1 · systemd + cgroup limits (SR-17)  │     │  remote log service) │
│   local hash chain, forwards signed checkpoints (SR-15)          │     └──────────────────────┘
│ Executor daemon — M1 ONLY, does not exist in M0 (§0.1)           │
│ agave-validator (user `sol`, systemd)                            │
│ Config repository checkout (signed commits; rollback = previous) │
└──────────────────────────────────────────────────────────────────┘
```

### 4.2 Process Topology and Privilege (new in v0.3, Review-2 F3)

v0.2 described "the agent process" as a single sandboxed unit whose only write was the episode store. That was inconsistent: hooks write audit records, and the in-process MCP tools reach the observer, the alert sink and the report store. v0.3 names four process classes and states exactly what a compromise of each yields.

| Class | Holds | Can reach | A full compromise yields |
|---|---|---|---|
| **Untrusted worker** (any adapter, §5.12.3) | One short-lived capability token scoped to (episode, role, session, expiry) | The model broker; broker sockets inherited as file descriptors | Exactly the tool surface that token already permits, for one episode, until it expires. No provider credential, no policy write, no state transition, no audit authorship, no validator access except through the observer broker's allowlist and rate limits |
| **Trusted controller** | Token-minting key; control endpoint of the episode store. **No provider key** (v0.5) | Brokers, store control endpoint, worker lifecycle | Full control-plane authority. This process runs no model output and parses only structured broker responses |
| **Capability brokers** | Their own service identity; the observer client certificate (observer-broker only); **provider API keys (model-broker only)** | One downstream each | The capability of that one broker. Compromise of the observer broker yields read-only validator observation at its rate limits, nothing else. Compromise of the model broker yields spending on allowlisted models, nothing else |
| **Observer daemon** | Read-only command table; local audit chain key | Local read-only commands | Read-only observation of the validator under OS resource limits. No state-changing command exists to invoke (§2.5) |

**Consequence for the policy gate [A].** The `PreToolUse` policy hook executes inside the worker, the one process hosting model output. It is therefore *not* a trust boundary. Every check it performs — role allowlist, argument bounds, rate and quota limits, episode-state legality, bundle identity — is re-performed by the broker that serves the call, using the authenticated principal from the token rather than anything the worker claims. The hook is retained because it fails fast, produces a first-line audit record, and gives the model an explicit denial reason; it is never the only thing standing between a model and an effect.

### 4.3 Episode Store Endpoints (new in v0.3, Review-2 F1)

The store is one service with three endpoints that differ in what they expose, not in what they check:

| Endpoint | Transport and principal | Operations |
|---|---|---|
| `store-agent` | UDS owned by the broker user; caller additionally presents a controller-minted capability token naming (episode, role, session, expiry, nonce) | `append_hypothesis`, `append_hypothesis_status`, `append_recommendation`, `append_verdict`, `append_report`, `read_episode(view)` — **by role**, and nothing else |
| `store-control` | Separate UDS reachable only by the controller's uid | `open_episode`, `set_state` (all states except `resolved`), `append_signal`, `append_cost`, `read_episode` |
| `store-verify` | Separate UDS reachable only by the verifier's uid | `append_verification`, `set_state(resolved)`, `read_episode` |

**The agent endpoint has no code path to `set_state`, to verification records, or to closure.** This is an absence of capability, not a permission check that could be misconfigured. The principal is derived from the socket the call arrived on and the token presented; no request field names the caller.

Token properties [A]: single episode, single role, single session id, short expiry (P-10, §13.2), per-call nonce recorded for idempotency (SR-18), and bound to the policy bundle id of the episode so a bundle change invalidates outstanding tokens (§5.10).

### 4.4 Audit Sequencer (new in v0.3, Review-2 F2)

| Property | Design | Tag |
|---|---|---|
| Single writer | One sequencer process owns the ops-host chain file. Every other component submits records over a socket and receives the assigned sequence number and entry hash. No component appends directly | [A] |
| Server-stamped identity | `actor` is written by the sequencer from the authenticated principal of the submitting connection. A submitter cannot label its own entries | [A], Review-2 F1 |
| Durability | Each entry is fsynced before its acknowledgement | [A] |
| Payloads | Large payloads are content-addressed and hashed by the sequencer; the chain carries the reference, never the blob | [A] |
| External anchoring | The sequencer periodically signs `{chain_head, seq, timestamp}` and writes it to append-only external storage. Rewriting the local chain then requires also rewriting anchors the ops host cannot modify | [A] |
| Validator-host chain | The observer daemon keeps a local chain and forwards signed checkpoints to the sequencer, which records the daemon's head. Truncation of the daemon's chain becomes detectable at the ops host | [A] |
| Anchor cadence and backend | Decided in D15. Interval P-18 and maximum lag P-19 are in the register (§13.2) | [A] |
| **Maximum anchor lag (new v0.4)** | Lag above P-18 raises an alert. Lag above the maximum P-19 means the tamper-evidence bound this design promises no longer holds. **No new LLM step starts** (sentinel-and-alert tier), and sentinel, store and verifier continue. Normal operation resumes automatically once a fresh anchor is confirmed | [A], Review-3 |

The residual limitation is stated plainly: anchoring bounds *how much* history an attacker can silently rewrite to the interval since the last anchor. It does not make the local file immutable.

### 4.5 Design Rationale

| Decision | Tag |
|---|---|
| Ops host separate from validator (same reasoning as watchtower placement) | [E] S2 for watchtower; [A] applied to agent |
| Deterministic sentinel and episode runner frame the LLM steps | [A] |
| Role separation with an independent Judge | [A]; pattern from [E] R1 §3.3 |
| Framework (not an agent) runs canonical verification | [A]; pattern from [E] R2 |
| Fresh session per step over persistent structured state | [A]; pattern from [E] R1 §3.3, R2 |
| Claude Agent SDK as the **reference** runtime; Codex and Antigravity runtimes admitted by conformance; a native API adapter per provider as the floor (§5.12) | [E] S6 for product definitions; [A] preference for self-hosting near private infrastructure; [A] multi-provider requirement v0.5 |
| **Provider credentials and limits enforced in a broker, not in any runtime** | [A], v0.5 |
| **Capability brokers rather than in-process tool implementations** | [A], Review-2 F3 |
| **Transport-derived principals rather than caller-asserted actors** | [A], Review-2 F1 |

---

## 5. Agent Design

### 5.1 Autonomy Tiers

| Tier | Meaning | Examples | Enforcement |
|---|---|---|---|
| **T0 Observe** | Read-only | status, catch-up, leader schedule, balance, log tail, disk, version, consensus files | Broker allowlist by role; SDK `allowed_tools`; audit |
| **T1 Low-risk** | No validator impact | send alert, write report section, append a hypothesis or recommendation to the episode | Broker policy checks with rate limits |
| **T2 Gated** | Affects availability | idle-window restart, stage upgrade, apply configuration commit | **M1+.** Planner → **Judge PASS** → human approval token → executor preconditions → execute → **verification** |
| **T3 Forbidden** | Agent may only draft text | failover, snapshot download, key operations, withdraw, host security changes, editing policy or skills | No such tools exist; built-ins removed |

Tier assignment is [A] and requires owner approval (D8).

**Telemetry health [A], new in v0.3.** The sentinel additionally checks the observation path itself: observer daemon reachability, response latency, command error and timeout rates, staleness of the newest successful sample per check, watchtower liveness, and local RPC latency. Breaching the owner's thresholds opens a **telemetry-health** episode, which is diagnosed and reported like any other but whose subject is the agent's own observability, not the validator. Missing data does not raise, lower, or resolve any validator-health episode.

### 5.2 Reference Adapter: Claude Agent SDK Configuration (revised in v0.3, Review-2 F4; scoped in v0.5)

**Scope (v0.5).** This section configures the **Claude runtime adapter**, the reference adapter. Codex, Antigravity and the native adapters are specified in §5.12 and HLD §6.5. Everything below that is a *control* (tool allowlist, no settings discovery, sandbox intent, no resumption) is required of every adapter through the conformance profile (§5.12.3). Everything that is Claude-specific (hooks, `dontAsk`) is defence in depth. With the model broker in place, the controller sets `ANTHROPIC_BASE_URL`-style routing to the broker; whether the SDK honours it is a W1 item [U].

A factory builds options for each step session. Every field below is a Phase-0 verification item; the plan does not assume the SDK behaves as documented until W1 confirms it on the pinned version.

**W1 needs a pinned configuration first (v0.4, Review-3).** A configuration cannot be verified until it is fixed. W1 therefore starts only after D1 (language) and D7 (runtime versions and model IDs, **per provider** since v0.5) are closed in the decision register (§13.1). From v0.5, W1 runs once per configuration (§5.12.4). W1 records the exact language runtime, SDK version and model ID it ran against. A W1 result obtained on any other combination does not count towards G1, and changing any of the three later re-opens W1 (§17.1). The Python listing below is the reference for the D1 default.

```python
ClaudeAgentOptions(
    setting_sources=[],                          # no filesystem settings discovery      [E] S9
    # An explicit `tools` list replaces the built-in set. Per SDK documentation it must
    # itself carry "Skill" for the skills library to remain loadable; with
    # setting_sources=[] the skills must be supplied by the `skills` field. Both halves
    # of that statement are W1 items.                                          [E] S9 / [U]
    tools=["Skill", *MCP_TOOL_NAMES[role]],
    allowed_tools=MCP_TOOL_NAMES[role],          # exact names, no globs                 [E] S9
    disallowed_tools=["Bash", "Write", "Edit", "NotebookEdit",
                      "WebFetch", "WebSearch", "Task"],  # removed from context; Task
                                                 # also forbids in-session subagents     [E] S7
    mcp_servers={"valops": valops_stub_server(role)},  # RPC stubs over broker sockets   [E] S9
    strict_mcp_config=True,                      #                                       [E] S9
    permission_mode="dontAsk",                   # unapproved → denied                   [E] S7
    hooks={                                      # defence in depth only (SR-16)
        "PreToolUse":  [HookMatcher(hooks=[policy_gate]), HookMatcher(hooks=[audit_append])],
        "PostToolUse": [HookMatcher(hooks=[audit_append_result])],
        "PostToolUseFailure": [HookMatcher(hooks=[audit_append_failure])],
    },
    skills=SKILLS_BY_ROLE[role],                 # from the bound policy bundle          [E] S9 / [U]
    sandbox=SANDBOX_PROFILE,                     # see below — fail-closed intent        [E] S9 / [U]
    system_prompt={"type": "file", "path": f"{bundle}/prompts/{role}.md"},  #            [E] S9
    output_format=ARTEFACT_SCHEMA[role],         # structured output as a cross-check     [E] S9
    max_turns=BUNDLE.max_turns[role],            # register P-05 (§13.2)
    max_budget_usd=BUNDLE.max_budget_usd[role],  # register P-06 (§13.2)
    model=BUNDLE.model[role],                    # pinned (D7)
    continue_conversation=False, resume=None, fork_session=False,   # enforces R-1
    agents=None, plugins=[],                     # no subagents, no plugins
)
```

**Sandbox profile, stated with intent [A].** The Claude SDK's own sandbox is the third of four layers and is never the control. Required intent: sandbox enabled; **fail closed if the sandbox backend is unavailable rather than silently running unsandboxed**; `allowUnsandboxedCommands=False`; no excluded commands; no weaker nested sandbox; network restricted to the Claude API endpoint; Unix socket access restricted to the broker sockets.

W1 must resolve one concrete discrepancy already observed: the review cites a `failIfUnavailable` setting, and in the SDK version inspected on 2026-09-17 (`claude-agent-sdk` 0.2.154) the `SandboxSettings` type exposed `enabled`, `autoAllowBashIfSandboxed`, `excludedCommands`, `allowUnsandboxedCommands`, `network`, `ignoreViolations` and `enableWeakerNestedSandbox`, with **no `failIfUnavailable` field present** [E, direct inspection]. Either the flag exists under another name or in another version, or fail-closed behaviour must be obtained outside the SDK. Until this is resolved, the external OS sandbox (SR-11) is treated as the sole sandbox control and the SDK sandbox as an unverified bonus.

**Skills fallback, removing an [U] from the critical path [A].** If W1 shows that a named skills library cannot be loaded reliably under `setting_sources=[]`, the runner falls back to **prompt inlining**: the runbook text for the role's permitted skills is concatenated into the role's system-prompt file inside the policy bundle, with the same source citations and compatibility matrix. The content, its provenance and its hash coverage are identical; only the delivery mechanism changes. No requirement depends on the `skills` field working.

| Role | `allowed_tools` | Input given to session | Required artefact (FR-12) |
|---|---|---|---|
| diagnostician | T0 tools + `add_hypothesis`, `set_hypothesis_status` | Episode record (signals, prior hypotheses) | ≥1 hypothesis, each with claim, test, expected evidence and a **rank** (unique, contiguous from 1 within the step) |
| change-planner | T0 tools + `propose_recommendation`, `report_no_action` | Episode record + supported hypotheses | Exactly one recommendation, or one explicit no-action record with a reason |
| proposal-judge | T0 tools + `submit_verdict` | **Only** raw signal snapshot, proposal, skill preconditions (SR-12) | One verdict with a non-empty list of checks performed |
| reporter | `write_incident_report`, `send_alert`, `get_verification_result` | Episode record incl. verification records | One report reference and one dispatched alert |

SDK facts relied on (all [E] S7/S8/S9, each re-confirmed in W1):
- Evaluation order: hooks → deny rules → ask rules → permission mode → allow rules → `canUseTool`.
- In `dontAsk` mode, `canUseTool` is never called. No control in this design may depend on it.
- When hooks conflict, `deny` wins. A timed-out `PreToolUse` hook means the tool does not run.
- A bare name in `disallowed_tools` removes the tool from the model's context entirely.
- The Python SDK does not expose `SessionStart`, `SessionEnd`, or `StopFailure` callback hooks; the TypeScript SDK does. Start/end work is therefore done by the controller, which is where it belongs regardless of language (§13 D1).
- v0.3 uses separate top-level sessions per role rather than in-session subagents, and disallows `Task`, so subagent context-inheritance rules cannot weaken Judge isolation.

### 5.3 Tool Catalog (MCP server `valops`, role-scoped)

Every tool below is a thin stub in the worker that forwards a typed request to a broker. The broker, not the stub, enforces the tool's contract.

| Tool | Tier | Underlying command / action | Source |
|---|---|---|---|
| `get_validator_monitor` | T0 | `agave-validator -l <ledger> monitor` (bounded) | [E] S5 |
| `get_catchup` | T0 | `solana catchup --our-localhost 8899` | [E] S5 |
| `get_leader_schedule` | T0 | `solana leader-schedule` (filtered to own identity) | [E] S3 |
| `get_identity_balance` | T0 | `solana balance <identity pubkey>` | [E] S3; [A] pubkey form |
| `get_running_version` | T0 | `grep -B1 'Starting validator with' <logfile>` | [E] S3 |
| `tail_validator_log` | T0 | bounded tail with redaction | [A] |
| `get_host_metrics` | T0 | disk, memory, CPU, systemd unit status | [A] |
| `get_host_hygiene` | T0 | pending updates, sshd PasswordAuthentication, fail2ban, listening ports | [E] S4 |
| `get_consensus_state_files` | T0 | detect `tower-*.bin` / `vote_history-*.bin` — **one of the three observed inputs** to FR-8 (four inputs in total with the declaration), never the sole determinant | [E] S5 |
| `get_telemetry_health` | T0 | observer reachability, latency, staleness per check | [A], new v0.3 |
| `get_verification_result` | T0 | read verification records | [A] |
| `add_hypothesis` | T1 | append hypothesis `{rank, claim, test, expected_evidence}` | [A]; `rank` new v0.4 |
| `set_hypothesis_status` | T1 | mark supported/refuted with refs to collected signals | [A], new v0.3 |
| `propose_recommendation` | T1 | append recommendation (no execution in M0) | [A] |
| `report_no_action` | T1 | explicit "no action recommended" artefact with reason | [A], new v0.3 |
| `submit_verdict` | T1 | Judge only: PASS or FAIL + checked evidence | [A] |
| `send_alert` | T1 | alert channel | [A] |
| `write_incident_report` | T1 | report store | [A] |
| `draft_failover_runbook` | T1 (text) | checklist per S5; executes nothing; may cite external failover tooling (§1.2) | [E] S5 |

T2 execution is **not** an agent tool in any milestone. From M1, after Judge PASS the controller submits the approved proposal to the approval service, and the executor runs it only with a valid token [A].

### 5.4 T2 Action Pipeline (M1+)

```
change-planner ──propose_recommendation──► Episode record
        │
        ▼
proposal-judge (fresh session, isolated inputs)
        ├─ FAIL (with evidence) ──► back to planner; retry budget N (P-09) ──► exhausted ⇒ hand off to human
        └─ PASS
             ▼
Controller ──► Approval service ──► Human sees: proposal + Judge evidence + raw signals
                                            ├─ reject ⇒ close as handed_off
                                            └─ approve ⇒ signed token {action_uuid, command_hash, expiry}
                                                   ▼
                                    Executor: verify token + hash; re-check preconditions
                                    (e.g., not in/near own leader slot per leader schedule)
                                                   ▼ execute
                                    Verifier (deterministic): FR-7 checks
                                    → immutable verification record → sets episode state
```

### 5.5 Judge Checklist (minimum, extended via the policy bundle)

| Check | Tag |
|---|---|
| Proposal's preconditions match the runbook skill for the **confirmed** consensus mode and client; if mode is `unknown`, any mode-specific precondition is an automatic FAIL | [E] S3/S5 for content; [A] check |
| Every evidence reference in the proposal resolves to a signal actually collected in this episode | [A], new v0.3 |
| Action is the least-impact option that addresses the cited evidence (for example, no restart for a balance alert) | [A] |
| **Success-gaming patterns** (domain analogue of R1's reward-hacking checks [E R1 §3.3]): resolving by silencing or deduplicating alerts; declaring recovery on process liveness without catch-up or vote evidence; repeated restarts to clear symptoms; proposing a snapshot download (a T3 action) under another name; recommending an action whose only effect is to stop the signal being observed | [A] |
| Proposal contains no instruction copied from log or RPC text (SR-6) | [A] |

The Judge never sees the diagnostician's or planner's prose (SR-12). The bridge from diagnosis to judgement is the proposal's evidence references, which point at observations rather than at reasoning — a fabricated justification is therefore a rejected write at the store, not a judgement call.

### 5.6 Verification and Resolution Ownership

- Only the **Verifier** writes verification records and sets `resolved` [A]. It reaches the store on its own endpoint (§4.3); no other principal has the operation.
- Verification commands and predicates are fixed per signal in the policy bundle (read-only, hashed) [A]. Commands are from S3 and S5 [E].
- The agent reads results with `get_verification_result` and can only describe them.
- Rules are declarative predicates plus a stability window, evaluated by code — never by a model, and never by string evaluation.

### 5.7 Episode Record, Concurrency and Lifecycle (revised in v0.3, Review-2 F5)

**Record schema (framework-owned, append-only API) [A]**

```json
{
  "episode_id": "uuid",
  "revision": 42,
  "class": "validator_health | telemetry_health",
  "opened_at": "...", "trigger": {"source": "sentinel|watchtower", "check": "...", "severity": "..."},
  "policy_bundle": "sha256:...",
  "consensus_mode": "tower|alpenglow|unknown",
  "consensus_mode_evidence": {"declared": "...", "version_check": "...", "feature_check": "...", "files": "..."},
  "signals": [{"id": "s1", "t": "...", "command_id": "...", "ref": "...", "summary": {}}],
  "hypotheses": [{"id": "h1", "step_session": "...", "rank": 1,
                  "claim": "...", "test": "...", "expected_evidence": "...",
                  "status": "open|supported|refuted", "evidence_refs": []}],
  "recommendations": [{"id": "r1", "hypothesis": "h1", "action_text": "...", "skill": "...",
                       "preconditions": [], "expected_postcondition": "...", "evidence_refs": []}],
  "verdicts": [{"recommendation": "r1", "result": "PASS|FAIL", "checks": [], "session_id": "..."}],
  "approvals": [{"recommendation": "r1", "by": "...", "decision": "...", "token_expiry": "..."}],
  "executions": [{"recommendation": "r1", "executor_result": "...", "audit_ref": "..."}],
  "verifications": [{"t": "...", "rule": "...", "result": "pass|fail", "samples": [], "by": "verifier"}],
  "recovery_observations": [{"t": "...", "rule": "...", "note": "observed during analysis"}],
  "reports": [{"kind": "incident|closure", "ref": "..."}],
  "state": "open|diagnosing|recommending|judging|reporting|awaiting_operator|resolved|handed_off",
  "cost": {"per_role_usd": {}, "turns": {}}
}
```

`approvals` and `executions` are empty in M0 by construction; the fields exist so that the M1 schema is an extension rather than a migration.

**Hypothesis ranking [A], new in v0.4 (Review-3).** v0.3 required a "correctly ranked hypothesis" in its exit criteria, but its schema had no ranking field. Each hypothesis now carries `step_session`, the diagnostician session that wrote it, and `rank`, a positive integer where 1 means most likely. The store enforces that ranks within one `step_session` are unique and contiguous from 1. The **top-ranked hypothesis** of an episode is the rank-1 hypothesis of the latest *completed* diagnosis step. A later `refuted` status does not re-rank it. The operator rates it in FB-1 (§2.6), so a diagnostician that ranks well but refutes poorly is still visible. Ranking is the model's ordering claim. It is never used by the controller to route the episode.

**Transition table with authorised principals [A].** Every transition is a compare-and-swap against `revision`; a transition computed from a stale revision is refused and the caller re-reads.

| From | To | Authorised principal |
|---|---|---|
| `open` | `diagnosing` | controller |
| `diagnosing` | `recommending`, `reporting` | controller |
| `recommending` | `judging` | controller |
| `judging` | `recommending` (Judge FAIL retry, ≤ N), `reporting` | controller |
| `reporting` | `awaiting_operator` | controller |
| `awaiting_operator` | `resolved` | **verifier only** |
| any non-terminal | `handed_off` | controller (also on verifier-reported integrity failure) |
| `resolved`, `handed_off` | — | terminal |

**Idempotency [A].** Every append carries a caller-supplied key; a repeat of a key already recorded returns the original result without appending. Retries after a timeout are therefore safe and cannot inflate an episode.

**Spontaneous recovery during analysis [A].** The verifier samples continuously, including while an episode is being diagnosed. If the recovery predicate holds before the episode reaches `awaiting_operator`, the verifier appends a `recovery_observation` and **does not** change state. The controller reads it at the next transition point and may route `diagnosing → reporting`, skipping recommendation. Analysis in flight is never cancelled mid-step, so no step can be interrupted between doing work and recording it. Only from `awaiting_operator` can the verifier set `resolved`.

**Closure [A], FR-15.** On `resolved` the controller runs one final reporter step producing a **closure report** (what was recommended, what the operator appears to have done, how recovery was confirmed, and the per-role cost) and dispatches a closure alert. Reports may be appended in a terminal state; state does not change.

**`handed_off` is terminal [A].** Later recovery does not reopen it. The verifier appends a recovery observation for the record, and if the underlying signal recurs the sentinel opens a **new** episode. Reopening a terminal episode would make "what happened in incident X" unanswerable.

**Lifecycle.** The controller is a deterministic state machine. Each LLM step is a new session that reads the record and writes only through T1 tools. No step resumes a prior transcript (NFR-4) [A].

### 5.8 Skills Library

| Skill | Content source | Compatibility matrix fields |
|---|---|---|
| `restart-idle-window` | [E] S3, S5 | consensus mode · client · docs version and access date |
| `upgrade-agave` | [E] S3 | same + upgrade method (D4) |
| `catchup-diagnosis` | [E] S3 (snapshot policy, catch-up) | same |
| `identity-balance` | [E] S3 | same |
| `telemetry-health` | §5.1 | — (new in v0.3) |
| `failover-runbook-draft` | [E] S5 (Tower BFT and Alpenglow sections) | same; output is text only |
| `host-hygiene-report` | [E] S4 | OS distribution |
| `judge-checklist` | §5.5 | — |

Rules [A]:
- Skills are read-only to agents and part of the immutable policy bundle (SR-10).
- Every factual step cites its source section. Unverified clients are marked [U] and blocked from T2 (this is the gate any D2 answer must pass).
- Changes go through human review as signed commits and produce a new bundle.
- A long-term `ops-memory.md` of lessons is appended by the reporter role only into a *staging* file outside the bundle. A human reviews it before it is promoted into a new bundle.

### 5.9 Consensus Mode Determination (revised in v0.3, Review-2 F7)

File presence alone is ambiguous: both `tower-*.bin` and `vote_history-<IDENTITY>.bin` may exist after a migration, a rollback, or incomplete cleanup. Mode is therefore established by agreement, not inference [A]. **Terminology (fixed in v0.4, Review-3):** there is one *declared* input and three *observed* inputs — four inputs in total. Earlier text that called this a "three-way" check counted only the observed inputs. Both documents now use "declared mode cross-checked against three observed inputs".

| Input | Source |
|---|---|
| **Declared** mode in the deployment facts of the policy bundle | Owner-set, reviewed, hashed |
| **Running Agave version** and its support for the mode | Observed via `get_running_version` [E] S3 |
| **Cluster feature state** for the relevant consensus feature | Observed on-cluster; exact query is [U] (D9). If the query is unresolved at M0B, this input is recorded as `unavailable`, which counts as disagreement and yields `unknown` |
| **Consensus state files** present, with modification times | Observed [E] S5 |

Rules: all inputs agreeing sets the mode. Any disagreement sets `unknown`, records every input in `consensus_mode_evidence`, raises an alert, and **prohibits mode-specific recommendations** — the planner is offered no mode-specific skill variant, and the Judge FAILs any proposal whose preconditions are mode-specific. Unknown mode does not stop observation, diagnosis, or reporting.

### 5.10 Policy Bundles: Versioning, Drain, Revocation, Rollback (new in v0.3, Review-2 F8)

v0.2 recorded a policy hash per episode and re-checked the *current* mount against it on every tool call, which would have stranded every in-flight episode on any legitimate policy deployment.

| Concept | Design | Tag |
|---|---|---|
| Bundle | An immutable directory addressed by the hash of its contents: command table, thresholds, prompts, skills, verifier rules, judge checklist, deployment facts. Bundles are never edited in place | [A] |
| Binding | An episode records its bundle id at open and is served from that bundle until it terminates. Capability tokens are bound to the same id | [A] |
| Activation | An `active` pointer names the bundle used for **new** episodes. Activation is a pointer change, not a content change | [A] |
| Drain | On activation, in-flight episodes continue on their bundle. A drain deadline (P-12, §13.2) bounds the number of live bundles; episodes exceeding it go to `handed_off` with an alert | [A] |
| Migration | There is none for a live episode. An episode never changes bundle mid-flight — a partly-old, partly-new policy is exactly the state this design exists to prevent | [A] |
| Emergency revocation | A revocation list names bundle ids that must stop being used immediately. Episodes bound to a revoked bundle go to `handed_off` with a high-severity alert; outstanding capability tokens for it are refused at the brokers | [A] |
| Rollback | Re-point `active` at the previous bundle. Because bundles are immutable and content-addressed, rollback is exact | [A] |
| Integrity check | Bundle contents are verified against their id at process start, at episode open, and at every broker call, using the episode's bound id — never "whatever is mounted now" | [A] |

Bundle signing key custody and rotation follow D14 (§13.1).

### 5.11 Output Completeness and Artefact Validation (new in v0.3, Review-2 F9)

A session that ends without writing its artefact has failed, however confident its prose. The controller therefore does the following after every step [A]:

1. Read the episode record from the store (not the transcript) and check that the role's required artefact from §5.2 exists, was written in this step, and satisfies its schema.
2. Cross-check against the session's structured output where the SDK supplies one; a disagreement between structured output and the stored artefact is a step failure, and the **stored artefact remains authoritative**.
3. On a missing or invalid artefact: count a step failure, retry within the retry budget (P-08, §13.2) with a fresh session, and on exhaustion move to `handed_off` with an alert naming what was missing.
4. Never parse prose to recover an artefact. Transcript text is read by no control-plane component; it is retained for audit and human review only.

### 5.12 Model Providers and Runtime Adapters (new in v0.5)

**Requirement (owner, 2026-09-21).** The system supports three model providers: **Anthropic Claude**, **OpenAI Codex**, and **Google Gemini via Antigravity**. Every safety property in this plan holds identically whichever provider serves a role.

**Why this is tractable [A].** v0.3 already moved every control out of the process that hosts the model: brokers re-check every call (§4.2), the OS sandbox is external (SR-11), closure is absent from the agent endpoint (§4.3), and artefacts are validated from the store, not from prose (§5.11). None of these depends on which agent runtime runs inside the worker. v0.5 finishes the job with two changes. It adds a **model broker**, so provider credentials, model allowlists and budgets are also enforced outside the worker. It also defines a **runtime adapter** contract, so each provider's agent runtime is admitted only when it has been shown to fit inside that boundary.

#### 5.12.1 Provider Matrix

What each provider's own runtime offers, as documented on 2026-09-21. Every cell is re-verified in that provider's W1 run on its pinned version.

| Concern | Claude — Agent SDK (Python) | Codex — `codex exec` (CLI) | Gemini — Antigravity CLI `agy -p` |
|---|---|---|---|
| Headless single-shot run | In-process SDK session [E] S9 | Non-interactive `exec` mode [E] S11 | `-p` / `--print`; output formats `text`, `json`, `stream-json`; `--json-schema` [E] S13 |
| Built-in tools removable | Yes: `disallowed_tools` removes them from context [E] S7 | **Not documented.** The read-only permission profile restricts execution, but no documented switch removes the shell tool [E] S10 / [U] | **Not documented.** Workspace file read and write are auto-allowed in headless mode; shell defaults to ask, which headless mode soft-denies [E] S13 / [U] |
| In-process permission control | Hooks and `dontAsk` [E] S7, S8 | Permission profiles `:read-only` / `:workspace` / `:danger-full-access`; approval policies [E] S10 | `permissions.allow` in `~/.gemini/antigravity-cli/settings.json` — **reported ignored in headless mode, open issue** [E] S14 |
| Own sandbox | SDK `SandboxSettings`; no fail-closed flag found (§5.2) [E] X1 | bubblewrap + seccomp on Linux, Landlock fallback [E] S10 | `--sandbox`, behaviour undocumented [E] S13 / [U] |
| MCP client | Yes [E] S9 | Yes, `[mcp_servers.<id>]` in `config.toml` [E] S12 | Reported in a central `mcp_config.json`; not in first-party headless docs [U] C2 |
| Endpoint override (for the model broker) | [U] — gateway base-URL support to be shown in W1 | `openai_base_url`, or a custom `[model_providers.<id>]` with `base_url` [E] S11 | **Not documented** [U] |
| Authentication | API key [E] S6 | API key or account login [E] S11 | **Cached credentials** from an interactive login [E] S13; an API-key variable is reported by third parties only [U] C2 |
| Turn or cost limits | `max_turns`, `max_budget_usd` [E] S9 | None found [U] | `--print-timeout` only (default 5 min) [E] S13 |
| Known defect bearing on this design | — | — | Headless runs **hang past `--print-timeout`** and ignore `permissions.allow` (issue #548, open) [E] S14 |

**Reading the matrix [A].** Claude's runtime is the most controllable of the three and remains the **reference adapter** (§5.2). The Codex and Antigravity runtimes each have at least one [U] in a row this design relies on. None of those gaps is a safety gap, because none of those rows is a control here. They are **admission** questions: can this runtime run inside the boundary at all? If not, that provider is served by the native API adapter (§5.12.3), which has no built-in tools to remove.

#### 5.12.2 Model Broker (a fifth capability broker)

| Property | Design | Tag |
|---|---|---|
| Sole holder of provider credentials | The Anthropic, OpenAI and Google API keys live only in the model broker. **The worker holds no provider credential of any kind:** no API key, no cached login, no OAuth token. This replaces v0.4's "short-lived session credential" (SR-8) | [A] |
| Sole egress | The worker's network namespace has one route: a loopback endpoint bridged to the model broker's socket. The broker forwards only to the provider endpoint named by the episode's bound configuration | [A] |
| Model allowlist | A request naming a model not assigned to this (episode, role) by the bound bundle is refused | [A] |
| Provider-neutral limits | Per session: request count (the turn proxy), input and output tokens, and USD computed from the bundle's pricing table. Exhaustion refuses further requests, and the controller sees a step failure (NFR-2). This makes `max_turns` and `max_budget_usd` enforceable for Codex and Antigravity, which expose no equivalent, and a second layer for Claude | [A] |
| Transcript of record | Every model request and response is hashed and submitted to the audit sequencer (§4.4) by the broker. The audit trail therefore no longer depends on any runtime's own event stream or hooks | [A] |
| Cost accounting | `cost.per_role_usd` is taken from the broker, not from runtime self-reports, so cost (Q-6) is comparable across providers | [A] |
| Compromise yields | Spending up to the per-session limits on allowlisted models. No validator access, no store access | [A] |
| Requires from each runtime | An endpoint override. Where a runtime cannot be pointed at the broker, that runtime is **not admitted** (§5.12.3) | [A] |

#### 5.12.3 Runtime Adapters and Admission

Every worker runs one **adapter**. An adapter is a launcher and a small shim that start one runtime for one role and one episode, inside the external sandbox, with the `valops` MCP stub server (§5.3) as its only tool source. Two adapter kinds exist:

- **Runtime adapter.** It drives the provider's own agent runtime: the Claude Agent SDK, `codex exec`, or `agy -p`.
- **Native API adapter.** It runs a minimal tool-calling loop that the project writes over the provider's plain model API, through the model broker. It has **no built-in tools at all**: the only tools the model is offered are the role's `valops` tools, rendered from the bundle. It exists for every provider, so every provider has at least one path that satisfies the conformance profile by construction.

**Conformance profile [A].** A (provider, adapter, runtime version, model) configuration is admitted only when W1 for that configuration shows every item. Every item is a deterministic test (§8.1).

| ID | Requirement |
|---|---|
| PC-1 | Headless, single role, single episode; exits on completion. A hang is killed by the controller at P-11 regardless of any runtime timeout (issue S14 is why) |
| PC-2 | The model can reach **only** the role's `valops` tools. Built-in tools are either removed, or shown **inert** inside the external sandbox. Inert means a minimal root filesystem containing nothing but the runtime; no writable path; no route but the model broker; no secret in the environment or the filesystem. Removal is preferred. Inertness must be demonstrated by attempting each built-in tool and observing that it achieves nothing |
| PC-3 | No configuration or instruction discovery. The runtime's home and working directories are fresh, read-only, and generated by the controller from the bundle. Project-instruction files (`CLAUDE.md`, `AGENTS.md`, `GEMINI.md` and equivalents) are either absent or bundle-generated |
| PC-4 | No credential in the worker. The runtime operates through the model broker with a non-secret placeholder credential, and never uses a cached login |
| PC-5 | Runs inside the D11 sandbox. The runtime's own sandbox is disabled or strictly tighter, and a runtime that would fall back to running unsandboxed fails admission |
| PC-6 | Speaks MCP over stdio to the `valops` stub server |
| PC-7 | Auto-update, telemetry and phone-home are disabled or harmlessly blocked. The runtime must not fail open when they are blocked |
| PC-8 | Exact version pinned. The same inputs produce the same tool surface on every run |
| PC-9 | The role's system prompt and skills text (inlined, §5.2 fallback) are delivered from the bound bundle and nothing else |

Provider-specific extras are **defence in depth only and never a condition of admission**: Claude hooks, Codex approval policies, Antigravity `permissions.allow`. v0.3 already decided that no in-process control is a boundary (§2.4). v0.5 relies on that decision: Antigravity's headless mode ignoring `permissions.allow` (S14) weakens nothing here.

**Admission outcomes.** Each configuration ends W1 in one of three states:

1. **Runtime admitted** — the provider's own runtime passes PC-1 … PC-9.
2. **Native-only** — the runtime fails an item, and the native API adapter for that provider passes.
3. **Not admitted** — neither passes. The provider is dropped from this bundle. Other providers are unaffected.

Expected outcomes, stated as hypotheses [H] so that W1 can refute them:

| Provider | Expected outcome |
|---|---|
| Claude | Runtime admitted, conditional on showing the base-URL override |
| Codex | Runtime admitted if built-in tools can be shown inert under PC-2; otherwise native-only |
| Antigravity | **Native-only** is likely: the endpoint override is undocumented, authentication uses a cached login, file writes are auto-allowed and there is an open headless defect. This is a prediction, not a decision; W1 decides |

#### 5.12.4 Configurations, Binding and Failover

- A **configuration** is (provider, adapter kind, runtime and version, model ID). The bundle's `providers.yaml` assigns one configuration per role. The assignment is bound to the episode with the bundle (FR-14), so **an episode never changes provider mid-flight**.
- **Default [A]: one configuration serves all roles in an episode.** A cross-provider Judge (for example, a Codex planner judged by Claude) is a distinct configuration. It may reduce shared blind spots between planner and Judge [H], and it is admitted only through its own model-quality gates (D22).
- **Provider outage.** In-flight episodes go to `handed_off` (HLD RB-1). New episodes may move to another provider only by activating a **pre-approved fallback bundle** whose configuration has already passed the same gates. The controller may perform that activation automatically after P-29 of continuous unavailability. It is audited and alerted. Unapproved automatic failover is prohibited.
- **Evaluation is per configuration.** Model-quality results (§8.1) are never pooled across configurations. Q-1 … Q-7 are reported per configuration, and G2 is granted per configuration.
- **Data egress.** Episode views now go to up to three providers. A provider is admitted only after its data-handling terms are approved for testnet operational data (D21, §17.2).

---

## 6. Repository Layout

```
valops-agent/
├── PLAN.md · HLD.md
├── pyproject.toml | package.json        # D1
├── bundles/                             # immutable, hash-addressed policy bundles (§5.10)
│   ├── <bundle-hash>/
│   │   ├── command_table.yaml           # read-only commands only in M0
│   │   ├── thresholds.yaml              # generated from the parameter register (§13.2)
│   │   ├── deployment.yaml              # declared consensus mode, client, ledger paths (§5.9)
│   │   ├── providers.yaml               # role → configuration (provider, adapter, runtime pin, model) (§5.12)
│   │   ├── pricing.yaml                 # P-31, for broker-side USD limits
│   │   ├── prompts/{diagnostician,change_planner,proposal_judge,reporter}.md
│   │   ├── skills/<skill>/SKILL.md      # §5.8 (or inlined into prompts — §5.2 fallback)
│   │   ├── verifier/<signal>.yaml       # declarative predicate + stability window
│   │   ├── judge_checklist.yaml
│   │   └── MANIFEST.sha256 (+ .sig)
│   ├── active                           # pointer for NEW episodes
│   └── revoked                          # revocation list (§5.10)
├── controller/                          # TRUSTED: runner state machine, token minting, artefact validation
│   ├── runner.py · transitions.py · artefacts.py · tokens.py
├── worker/                              # UNTRUSTED: one adapter per worker (§5.12.3)
│   ├── main.py                          # adapter dispatch from the bound configuration
│   ├── adapters/
│   │   ├── claude_sdk/options.py        # reference adapter: per-role ClaudeAgentOptions factory
│   │   ├── codex_cli/                   # generated config.toml, `codex exec` launcher
│   │   ├── antigravity_cli/             # generated settings + MCP config, `agy -p` launcher
│   │   └── native/{loop.py,anthropic.py,openai.py,gemini.py}   # no built-in tools
│   ├── rootfs/                          # minimal per-runtime root filesystems (PC-2 inertness)
│   ├── hooks/{policy_gate,audit}.py     # defence in depth (SR-16)
│   └── tools/stubs.py                   # MCP tools = RPC stubs over broker sockets
├── brokers/
│   ├── episode_broker.py                # agent endpoint: appends only
│   ├── observer_broker.py               # validation, rate limits, mTLS client
│   ├── report_broker.py                 # report store + alert sink
│   ├── audit_sequencer.py               # SOLE chain writer; signs and anchors heads (§4.4)
│   └── model_broker.py                  # SOLE provider-key holder; egress; limits; transcript (§5.12.2)
├── store/                               # episode store service: three endpoints (§4.3)
│   ├── service.py · schema.json · cas.py · idempotency.py
├── verifier/verifier.py                 # recovery (M0) and post-action (M1) verification
├── sentinel/{checks.py,telemetry.py,scheduler.py}
├── observer/                            # VALIDATOR HOST: read-only daemon
│   ├── daemon.py · validate.py · redact.py · chain.py   # local chain + checkpoint forwarding
│   └── systemd/valops-observerd.service                 # resource limits (SR-17)
├── approval/{service,client}.py         # M1+
├── executor/{daemon.py,validate.py}     # M1+ ONLY — absent in M0 (§0.1)
├── sandbox/                             # OS sandbox profiles (D11)
├── config-repo/                         # signed validator config commits
├── ops-memory/staging.md                # human-reviewed before promotion into a bundle
├── docs/
│   ├── gates/G0.md · G1.md · G2.md      # go/no-go records with evidence (§7.2)
│   ├── registers/{decisions,parameters,targets}.yaml   # §13.1–13.3; bundles generated from these
│   ├── changes/                         # change requests (§17.1)
│   └── runbooks/                        # degraded-mode runbooks (HLD §9.1)
├── eval/
│   ├── fixtures/<fixture-set-hash>/     # frozen model-quality fixtures (§8.1)
│   ├── injections/                      # FC-1…FC-5 injection scripts + ground-truth log (§2.6)
│   └── rubric/                          # FB-1…FB-6 submissions and adjudications
└── tests/
    ├── unit/
    ├── containment/   # capability boundaries, principal spoofing, sandbox escape, audit forgery
    ├── policy/        # denial, tamper, bundle drain/revocation/rollback
    ├── judge/         # success-gaming and injection proposals
    ├── concurrency/   # CAS races, duplicate delivery, recovery-during-analysis
    ├── integration/   # testnet fault injection
    ├── recovery/      # backup/restore and key-recovery tests (§17.3)
    ├── conformance/   # PC-1…PC-9 per configuration (§5.12.3)
    └── replay/        # recorded incident corpus (also used by §11)
```

---

## 7. Phased Implementation

Phase 1 of v0.2 is split. The review's central recommendation is that the containment layer be **demonstrated** before the diagnosis workflow is built on top of it, because every later safety claim rests on it.

v0.4 adds a step in front of everything. **No code is written until the delivery package is approved at G0** (§7.2).

| Phase | Milestone | Deliverable | Exit criteria |
|---|---|---|---|
| **G0 — Define** | Before M0A | The delivery package: M0 product definition (§2.6), closed M0A-blocking decisions (§13.1), approved parameter register (§13.2), gate classes and fixture-freeze procedure (§8.1), M0A charter (§7.1), governance (§17), degraded-mode runbooks (HLD §9.1), **D19–D21 decided (§13.1)** | G0 approval by the go/no-go authority (§7.2). **No M0A code before this** |
| **0 — Verify** | Phase 0 (HLD W1), first item of M0A | Per configuration (§5.12.4): the reference Claude configuration on the G1 critical path; Codex, Antigravity and native configurations on the parallel provider track. Each runs the conformance profile PC-1 … PC-9 (§5.12.3). For the reference adapter, a spike on the runtime version, language and model **pinned by D1/D7**. Confirm: `tools=["Skill", ...]` semantics and whether skills load with `setting_sources=[]`; `dontAsk` + role-scoped allowlists; hook deny and timeout behaviour; SDK sandbox fail-closed behaviour and the `failIfUnavailable` discrepancy (§5.2); OS sandbox backend with the SDK process; structured `output_format` | Written verification log. Every mismatch amends §5.2 before Phase 1 starts |
| **1A — Containment prototype** | **M0A** | The four properties the review asks to prove first: (1) authenticated capability boundaries around the episode store, (2) centralised audit sequencer with external anchoring, (3) concrete process/sandbox topology that fails closed, (4) a verified SDK configuration loading exactly the intended tools, prompts and skills — with **no diagnosis workflow at all** | Containment suite (§8) passes at 100% over P-22 trials, **on real transports, a real sandbox backend, a real external anchor store and the pinned SDK — not mocks**: principal spoofing refused, agent endpoint has no closure capability, forged and expired tokens refused, chain forgery detected against the anchor, sandbox escape blocked, worker holds no provider credential (model broker, §5.12.2). **M0B does not start until G1 is approved** (§7.2) |
| **1B — Read-only core** | **M0B** | Observer daemon with resource limits; observer/episode/report brokers; policy bundles with drain and revocation; sentinel incl. telemetry-health; episode store with CAS and idempotency; diagnostician | Policy tests pass: no non-T0 execution possible; bundle tamper leads to observe-only; telemetry loss opens its own episode |
| **2 — Roles, judgement, reporting** | M0B | Controller state machine, planner, **proposal-judge**, reporter, skills v1 (or inlined prompts), recovery verifier, closure reports | Testnet fault injection produces correct episodes. Judge suite catches all seeded success-gaming proposals (suite frozen before the run). Artefact-validation suite passes. Watchtower baseline campaign (§2.6) recorded, then M0B run-in completed over P-25. **G2 approval (§7.2)** |
| **3 — Gated actions (testnet)** | M1 — **not part of M0; starts only after G2** | Approval service, executor with token and precondition checks, T2 restart and upgrade, configuration repository | End-to-end testnet upgrade: Judge PASS → human approval → execution → verification records success |
| **4 — Shadow mode on target cluster** | M1 | Full pipeline with execution disabled; humans act on their own and compare | Observation period (**TBD**) completed; §9 metrics collected, including per-role cost. Target cluster is D18; scope of the shadow fleet is D13 |
| **5 — Limited autonomy** | M1 | Enable T2 with approval on target cluster | Owner sign-off |

Testnet first per [E] S3. `solana-test-validator` is used for unit-level loops only; cluster behaviours require testnet [H].

### 7.1 M0A Charter (new in v0.4, Review-3)

| Item | Content |
|---|---|
| Objective | Demonstrate the four containment properties (HLD §13) on **real** boundaries, with no diagnosis workflow attached, using the **reference (Claude) configuration** and the **model broker**. In parallel, bring Codex and Antigravity through provider admission (PA, §7.2) |
| Starts | On G0 approval. Not before |
| Time box [A] | **Proposed: 7 calendar weeks** from G0 for the G1 track, with a checkpoint review at week 3. This was 6 weeks in v0.4; the model broker adds about a week. The provider track has its own time box, below. Both are confirmed or changed at G0 |
| In scope | W1–W8 and W6b (model broker) for G1. W1-O, W1-G and W21–W23 on the provider track (HLD §12). One stub role session per configuration, used only to exercise the worker, sandbox and brokers |
| Out of scope | Every M0B item: sentinel checks, role prompts, skills content, Judge, verifier rules, reporter. Every item excluded from M0 in §2.3 |
| On time-box expiry | A go/no-go review, never a silent extension. The authority (§7.2) may either extend **once**, by at most half the original box, with a written reason and a re-planned critical path, or invoke kill criterion 2 (§12) and redesign the containment layer |

**Roles and DRIs [A].** Names are recorded in the G0 package. One person may hold more than one role, except as the constraints column requires.

| Role | Responsibility | Constraint |
|---|---|---|
| Project owner (PO) | Owns scope, the registers and the G0/G1/G2 decisions. Presumed to be the author; confirm at G0 | — |
| Containment DRI | W2–W8 delivery | — |
| SDK DRI | W1 for the reference configuration and the verification log | — |
| Provider DRI | The provider track: W1-O, W1-G, adapters W21–W23, admission evidence | — |
| Workflow DRI | M0B controller workflow, roles, verifier and evaluation support (named at G1) | — |
| Independent security reviewer | Reviews the G1 evidence. Holds a safety veto at every gate | **Must not have implemented any M0A item** |
| On-call operator (+ backup) | The M0 user (§2.6). Fills the rubric. Holds the value veto at G2 | Named individuals, not a rota |
| Fault injector / adjudicator | Runs injections and the baseline campaign and records ground truth before reports are read | **Must not be the on-call operator or the prompt author** |

**Estimates and critical path [A].** These are planning estimates in engineer-days, to be re-baselined by each DRI at G0. They are not commitments.

| # | Work item (HLD §12) | Depends on | Estimate |
|---|---|---|---|
| W1 | Phase-0 verification of the **reference (Claude)** configuration, pinned | **D1, D7 closed**; ER-5, ER-6 | 5 |
| W2 | Observer daemon, command table, mTLS, systemd/cgroup limits | ER-1, ER-9 | 8 |
| W3 | Episode store: three endpoints, CAS, idempotency, contract checks | ER-2, ER-10 | 10 |
| W4 | Audit sequencer, external anchoring, daemon-side chain | W3; ER-7 | 6 |
| W5 | Policy bundles: build, sign, bind, activate, drain, revoke, roll back | ER-8 | 6 |
| W6 | Process topology: controller, worker spawn, token minting, OS sandbox, **adapter framework and the Claude adapter** | W1, W5; ER-6, ER-10 | 10 |
| W6b | **Model broker:** key custody, sole-egress bridge, model allowlist, turn/token/USD limits, transcript to the sequencer (§5.12.2) | W4; ER-5 | 6 |
| W7 | Capability brokers: episode, observer, report | W2, W3, W4 | 6 |
| W8 | M0A containment suite on real boundaries, including model-broker tests | W3–W7, W6b | 6 |
| | **Total, G1 track** | | **63** |

**Provider track (v0.5) [A].** It runs in parallel with the G1 track, needs its own engineer, and is off the G1 critical path. Proposed time box: the same 7 weeks. A provider that does not reach admission by then is carried into M0B as *not yet admitted*. That does not delay M0B.

| # | Work item | Depends on | Estimate |
|---|---|---|---|
| W1-O | Phase-0 verification of the Codex runtime configuration (PC-1 … PC-9) | D7 (Codex pins), D21; ER-5 | 4 |
| W1-G | Phase-0 verification of the Antigravity runtime configuration (PC-1 … PC-9) | D7 (Antigravity pins), D21; ER-5 | 4 |
| W21 | Codex runtime adapter | W1-O, W6, W6b | 4 |
| W22 | Antigravity runtime adapter | W1-G, W6, W6b | 4 |
| W23 | Native API adapter: one loop, three provider bindings | W6, W6b | 6 |
| | **Total, provider track** | | **22** |

The **critical path** is G0 → W3 → W4 → W7 → W8, 28 engineer-days end to end. G0 → W3 → W4 → W6b → W8 is the same length. The parallel path G0 → D1/D7 → W1 → W6 → W8 is 21 days, and becomes critical if W1 finds a gap that must be closed outside the SDK. With two engineers on the G1 track, 63 engineer-days fits the proposed 7-week box with about half a week of slack. The provider track needs a third engineer. Without one, it runs after G1, and the Codex and Antigravity configurations join M0B later. A W1 finding that invalidates the SDK sandbox or permission model is the main schedule risk, and it is a kill-criterion question (§12 item 1) before it is a schedule question.

**Environment readiness checklist [A].** Each item is signed off with evidence before the work item that needs it starts. All items must be complete for G1.

| ID | Item | Evidence | Needed by |
|---|---|---|---|
| ER-1 | Agave testnet validator provisioned, caught up, identity funded (D3) | Validator pubkey; `solana catchup` output | W2 |
| ER-2 | Separate ops host, hardened per S4, with no keypairs present | Host inventory; hardening checklist | W3 |
| ER-3 | `agave-watchtower` running on the ops host or a third host, alerting to the D5 channel | Test alert received | Baseline campaign |
| ER-4 | Alert channel live (D5), operator and backup subscribed | Test alert acknowledged by both | G1 |
| ER-5 | Language runtime, and per provider the runtime version and model ID, pinned (D1/D7). **Anthropic, OpenAI and Google API keys in model-broker-only secret storage**; data-handling terms approved (D21) | Lockfiles; secret-store access list; D21 record | W1, W1-O, W1-G |
| ER-6 | Sandbox backend installed, required kernel features confirmed (D11) | Backend version; feature probe output | W1, W6 |
| ER-7 | External anchor store in a separate account with retention lock; ops host holds a write-only credential (D15) | Bucket or log policy; failed-delete test | W4 |
| ER-8 | Bundle signing key created under the D14 custody procedure; public key pinned in controller configuration | Key ceremony record | W5 |
| ER-9 | mTLS certificate authority and certificates for the observer link | Certificate fingerprints | W2 |
| ER-10 | Dedicated uids per process class; socket directories with the right ownership (D16) | `id` and `stat` output | W3, W6 |
| ER-11 | Time synchronisation on both hosts | Sync status | W4 |
| ER-12 | Backups configured for store, chains and bundles (§17.3) | First successful restore test | G1 |
| ER-13 | Access list for hosts, secret store and anchor store, per §17.2 | Reviewed list | G1 |

### 7.2 Gates and Go/No-Go Authority (new in v0.4, Review-3)

| Gate | Authorises | Required evidence | Decided by | Veto |
|---|---|---|---|---|
| **G0** | M0A coding | The complete delivery package: §2.6 frozen; every M0A-blocking decision in §13.1 closed or defaulted with evidence; §13.2 initial values approved; §8.1 gate classes and fixture-freeze procedure; §7.1 charter with named DRIs; §17 governance; HLD §9.1 runbooks drafted; cross-document consistency check (§17.4) clean | PO, with the security reviewer's concurrence | Security reviewer |
| **G1** | M0B | M0A suites (HLD §10.1) pass at 100% over P-22 trials **on real boundaries** (below); W1 log complete on the pinned configuration; the `failIfUnavailable` discrepancy resolved, or fail-closed shown outside the SDK; ER-1 … ER-13 complete; a backup-restore test passed (§17.3) | PO and the independent security reviewer | Security reviewer |
| **PA** (per configuration, v0.5) | Use of one (provider, adapter, runtime version, model) configuration in M0B | PC-1 … PC-9 pass (§5.12.3); every HLD §10.1 suite re-run **with this configuration** on real boundaries at 100% over P-22 trials; D21 approved for that provider. The reference configuration's PA is part of G1 | PO and the security reviewer | Security reviewer |
| **G2** | M1 (Phase 3) | **Safety:** every deterministic gate passes at 100%, and Q-8 = 0. **Value:** Q-1, Q-2, Q-4 meet their targets under §8.1 rules on frozen fixtures and the run-in; Q-3, Q-5, Q-6, Q-7 are within their ceilings; zero unresolved FB-2 *unsafe* flags; HLD §13 criteria | PO, the on-call operator and the security reviewer. **Granted per configuration** (§5.12.4); M1 may use only configurations that hold G2 | Security reviewer (safety); on-call operator (value) |

**"Real, not mocked", for G1 [A].** Mocks are welcome in unit tests and carry no weight at G1.

- **Transport:** real Unix domain sockets, with each process class running as its own uid and peer credentials checked by the kernel.
- **Sandbox:** the real D11 backend. Fail-closed is shown by actually making the backend unavailable, not by simulating the error.
- **Anchor:** the real external store with its retention lock. Rewrite detection is tested against anchors that store actually holds.
- **Runtime and model:** the pinned runtime version making real calls with the pinned model, **through the real model broker** holding real provider keys.
- **Validator link:** the observer daemon on the real testnet validator host, under its real cgroup limits.

**Rules [A].** Every gate decision is written down as *go*, *no-go*, or *conditional go* with named conditions and a date, and committed to the repository (`docs/gates/G<n>.md`) with the evidence it relied on. Schedule pressure is not evidence. A failed gate is re-presented only after a fix recorded under change control (§17.1). No gate may be skipped or merged with another.

---

## 8. Test Plan

| Category | Tests |
|---|---|
| **Containment (M0A gate, CI-blocking)** | Caller-asserted principal ignored; agent endpoint offers no `set_state`, verification or closure operation; token for episode A refused on episode B; expired token refused; token bound to a revoked bundle refused; duplicate nonce is a no-op; worker process holds no provider credential and cannot reach any network endpoint but the model broker and its broker sockets, for every admitted configuration; audit entry attributed to a principal the submitter does not hold is impossible; chain rewrite detected by comparing against an external anchor; observer daemon resource limits enforced under load |
| Policy (CI-blocking) | Removed built-ins denied; role calling another role's tool denied; out-of-state tool call denied; T2 without token refused (M1); forged or expired approval token refused (M1); hook timeout means no execution; agent write to a bundle fails at the OS level |
| Write-path absence | Static check: no state-changing command id in any bundle's command table; no code path from a tool to such a command; `executor/` absent from the M0 artefact |
| Bundle lifecycle | Tamper with each bundle file ⇒ observe-only + alert; activation does not disturb in-flight episodes; drain deadline exceeded ⇒ `handed_off` + alert; revocation stops in-flight episodes and refuses outstanding tokens; rollback restores the exact previous bundle |
| Sandbox | Worker attempts disallowed network egress and filesystem writes and is blocked; sandbox backend unavailable ⇒ refuse to start, never run unsandboxed |
| Concurrency | Two controllers racing a transition: exactly one wins by CAS; duplicate append delivery is a no-op; recovery predicate satisfied mid-diagnosis attaches an observation and changes no state; `handed_off` is not reopened by later recovery |
| Judge adversarial | Seeded proposals: alert silencing, liveness-only recovery, restart loops, snapshot download disguised, log-injected commands, precondition mismatched to consensus mode, evidence reference to a signal never collected. Each must return FAIL |
| Judge isolation | Judge session input contains no planner or diagnostician prose (asserted by the controller before the session starts) |
| Artefact completeness | Session ends with no artefact ⇒ step failure, retry, then `handed_off`; structured output disagreeing with the stored artefact ⇒ step failure; prose containing a plausible "recommendation" is never promoted to one |
| Resolution ownership | Agent attempts `set_state(resolved)` and a verification write ⇒ operation does not exist on its endpoint |
| Falsifiability | Hypothesis lacking `test` rejected at the API; evidence ref naming a non-existent signal rejected |
| Telemetry health | Observer unreachable, slow, and returning stale data each open a telemetry-health episode; none of them alters a validator-health episode |
| Consensus mode | Tower and vote-history fixtures; both files present; version and feature state disagreeing with the declaration ⇒ `unknown` and mode-specific proposals FAIL |
| Prompt injection | Instruction-bearing log lines cause no action beyond T0; report flags them |
| Functional (testnet) | Delinquency; low balance; idle-window restart (M1); upgrade and version check (M1); catch-up after restart |
| Degradation | A model provider down (in-flight episodes hand off; new ones use a pre-approved fallback bundle only); model broker down; store down; broker down; daemon down; budget or retry budget exhausted; anchor unreachable; **anchor lag above P-19 stops new LLM steps**. Correct degradation tier; validator unaffected; human alerted; each case exercised by following its runbook (HLD §9.1) |
| **Backup and recovery (new v0.4)** | Restore the episode store, audit chain and bundle store from backup onto a fresh ops host. Verify the restored chain against the external anchor. Resume open episodes without duplicating appends. Measure against RPO/RTO (P-26). Recover from loss of the controller's API key and of the bundle signing key using the D14 procedure (§17.3) |
| **Provider conformance (new v0.5)** | Per configuration: PC-1 … PC-9. Each built-in tool of the runtime is attempted and shown removed or inert. Project-instruction files planted in the working directory are ignored. A cached login present on the host is not used. Hang past timeout is killed at P-11. Runtime blocked from auto-update and telemetry does not fail open |
| **Model broker (new v0.5)** | No provider key in worker environment, filesystem or memory-mapped config. Request for a model not assigned to (episode, role) refused. Turn, token and USD limits cut off precisely. Worker cannot reach any provider endpoint directly. Broker down ⇒ no LLM step (fail closed). Transcript hash in the audit chain matches the request actually sent. Fallback bundle activates only if pre-approved, after P-29 |
| **Change control (new v0.4)** | Changing a frozen fixture, target or fault class after a run marks that run invalid in the evaluation record (§17.1) |
| Repetition | Deterministic suites repeated over P-22 trials; model-quality suites run P-23 times per fixture (§8.1); no single-trial pass counts |

### 8.1 Gate Classes (new in v0.4, Review-3)

v0.3 applied one rule, "pass over N trials", to two kinds of test that fail in different ways. v0.4 separates them.

| | **Deterministic security and safety gates** | **Model-quality gates** |
|---|---|---|
| What they test | Code and configuration: containment, policy, write-path absence, bundle lifecycle, concurrency, artefact validation, closure ownership, falsifiability contract, telemetry-health routing, consensus-mode rules, sandbox, degradation, backup/recovery | Model behaviour: diagnosis (Q-1), actionability (Q-2), time to diagnosis vs. baseline (Q-4), Judge detection of seeded bad proposals, Judge FAIL precision |
| Pass rule | **100% pass, every run, repeated over P-22 trials.** One failure blocks the gate. No tolerance, no averaging | The **lower bound of the confidence interval** (level P-23) on the pass rate is at or above the target in §13.3. A point estimate alone never passes a gate |
| Inputs | Test code in CI | **Frozen fixtures:** a versioned, hash-recorded set of recorded episodes, seeded proposals and injection scripts. It is frozen and its hash recorded *before* the run. Adding or editing a fixture creates a new set, and results never mix across sets |
| Controls | Deterministic by construction | **Repeatable controls,** recorded with every result: **configuration** (provider, adapter kind, runtime and version, model ID), language runtime, bundle id, prompt hashes, fixture-set hash, run count per fixture (P-23). A change to any control invalidates comparison with earlier runs |
| Scope (v0.5) | Run once per admitted configuration | Run per configuration; **never pooled** across configurations |
| Reporting | Pass/fail per test per trial | Pass rate, confidence interval, per-fixture variance across repeated runs, and every failing case listed. Unstable fixtures (disagreeing across repeated runs) are reported separately, not averaged away |
| Adjudication | Not needed | **Human adjudication** of every disputed, partial or unstable case, by an adjudicator who did not author the prompts or fixtures (§7.1). Adjudication is recorded before the pass rate is computed |
| Special cases | — | Judge seeded-adversarial cases have a target of **no misses**: any miss in any run blocks the gate, and the interval is still reported. FB-2 *unsafe* flags are counted deterministically and must be zero |

A model-quality gate can never compensate for a deterministic one. A model-quality result obtained with a failing deterministic suite is not evidence for anything.

---

## 9. Evaluation Metrics

**For M0, the metrics that decide G2 are Q-1 … Q-8 (§2.6), with target values in §13.3.** The list below is the wider set collected across all phases. Metrics not in Q-1 … Q-8 are diagnostic only in M0 and carry no gate weight.

- **Detection:** MTTD compared with watchtower alone.
- **Recovery:** MTTR for approved T2 episodes (M1+).
- **Safety (hard requirement):** zero unauthorized executions [A]. Counts of broker denials, executor refusals, tamper events, token rejections, and sandbox blocks.
- **Containment:** anchor lag (time since last externally anchored chain head); count of chain-verification runs and their results.
- **Telemetry:** observability uptime; count and duration of telemetry-health episodes; sample staleness distribution per check.
- **Judge:** FAIL rate; share of FAILs later confirmed correct by a human; seeded-case detection.
- **Artefacts:** step-failure rate by cause (missing artefact, schema failure, structured-output disagreement).
- **Human:** approval and override rate; rejections after a Judge PASS (M1+); recommendation acceptance rate in M0.
- **Quality:** human-rated diagnosis correctness in shadow mode; false-positive episode rate.
- **Cost per role:** USD and turns for diagnostician, planner, Judge, reporter per episode and per day, from SDK cost estimates [E] S9. R1 reports the Judge at 20–30% of active time in its runs [E R1 Table 1]; that comes from a different workload and harness and is **not** used as an estimate. C1's "60–80% cost reduction" from tiered models is likewise [U] and is not a target.

---

## 10. Risks

| Risk | Mitigation | Tag |
|---|---|---|
| LLM proposes a harmful action | No T3 tools; Judge; human approval; token bound to command hash; executor preconditions (M1) | [A] |
| Judge and planner share a blind spot | Isolated Judge inputs (SR-12); evidence refs checked against collected signals; human sees raw signals; seeded Judge tests | [A] |
| Human rubber-stamps approvals | Show Judge evidence and raw signals; track override and rejection metrics | [A] |
| Agent grades its own action | Verifier-only verification and resolution; the operation is absent from the agent endpoint (§4.3, §5.6) | [A] |
| **Worker compromise via prompt injection or SDK defect** | Worker holds only a scoped, short-lived token; brokers re-enforce every check; no provider credential, no filesystem write, no state transition (§4.2) | [A], new v0.3 |
| **A provider runtime's in-process controls fail** (for example, Antigravity headless ignoring `permissions.allow`, S14) | No in-process control is a boundary; admission requires PC-1 … PC-9 under the external sandbox; native adapter as the floor (§5.12.3) | [E] S14; [A], new v0.5 |
| **Runtime ships built-in tools that cannot be removed** | PC-2 inertness under a minimal root filesystem, or native-only admission | [U] S10, S13; [A], new v0.5 |
| **Model or runtime change at a provider** | Exact pins; any re-pin re-opens that configuration's W1 and PA (§17.1) | [A], new v0.5 |
| **Three providers triple evaluation cost and data egress** | Per-configuration evaluation; the provider track is off the G1 critical path; D21 data terms per provider | [A], new v0.5 |
| **Silent provider failover changes behaviour mid-incident** | No mid-episode provider change; only pre-approved fallback bundles, audited (§5.12.4) | [A], new v0.5 |
| **Forged or mislabelled audit entries** | Sequencer stamps the authenticated principal; single writer; external anchoring (§4.4) | [A], new v0.3 |
| **Observation degrades the validator** | Resource limits, concurrency 1, rate limits, RPC circuit breaker (§2.5, SR-17) | [A], new v0.3 |
| **Loss of observability mistaken for health** | Telemetry-health episode class; missing data never resolves or de-escalates a validator episode (FR-13) | [A], new v0.3 |
| **Policy deployment strands live episodes** | Immutable bundles, per-episode binding, drain deadline, revocation, exact rollback (§5.10) | [A], new v0.3 |
| **Transient recovery closes an episode mid-analysis** | Verifier may set `resolved` only from `awaiting_operator`; earlier recovery attaches an observation (§5.7) | [A], new v0.3 |
| **Model produces confident prose but no artefact** | Artefact validation before every transition; prose never parsed (§5.11) | [A], new v0.3 |
| Policy or skill tampering or drift | Immutable bundle, manifest hash, observe-only fallback, signed commits | [A] |
| Long-context drift in incidents | Fresh session per step over the episode record | [A]; [H] that this reduces drift |
| Memory poisoning via `ops-memory` | Staging file outside the bundle with human review before promotion | [A] |
| Prompt injection via logs or RPC | SR-6; Judge check; injection tests; structural containment (§4.2) | [A] |
| Restart during leader slot | Executor precondition + `agave-validator exit` idle-window wait (M1) | [E] S3 |
| Unnecessary snapshot download | T3; Judge check | [E] S3 |
| Identity balance depletion | T0 check + alert | [E] S3 |
| Two instances of one identity during failover | Failover is T3; runbook draft only | [E] S5 |
| Ops host compromise | No keypairs; process separation; OS sandbox; broker allowlists; mTLS; external audit anchor | [A] |
| Anthropic API outage | NFR-1 | [A] |
| SDK behavior changes | Pinned versions; repeat Phase 0 on upgrade | [A] |
| Alpenglow activation changes files or commands | FR-8 cross-check (declared mode vs. three observed inputs) + skill matrix; re-verify S5 before Phase 3 | [U] |
| **Delivery definition drifts after G0** | Frozen items change only through change control; a change invalidates affected evaluation runs (§17.1) | [A], new v0.4 |
| **M0 builds something the operator does not use** | Product hypothesis, watchtower baseline and operator value veto at G2 (§2.6, §7.2) | [A], new v0.4 |
| **Loss of ops-host state or keys** | Backups, restore tests, RPO/RTO, key-recovery procedure (§17.3) | [A], new v0.4 |
| Judge cost increases per-episode spend | Per-role cost metrics; budgets P-06, P-07 (§13.2) | [A] |
| **Competitor moves faster on diagnosis** | Not a safety risk and not a reason to relax a gate. Recorded in §15 for the owner's roadmap decisions only | [U] from C1 |

---

## 11. Research Track (optional, not a v1 dependency): Offline Tuning Loop

**Purpose [A].** Improve the sentinel's thresholds and classification rules, the diagnosis skills, and the Judge checklist. This happens **offline only**; the loop never touches the live validator.

**Method [A], adapted from R1's outer and inner loop [E R1 §3.3].**
- Each candidate change produces a new immutable bundle (§5.10), never an edit to an active one.
- Candidates are scored on:
  1. the replay corpus of recorded testnet incidents
  2. the fault-injection suite
  3. hard safety gates, where any unauthorized action or missed seeded case disqualifies the candidate
- An independent reviewer session checks each candidate for gaming the scorer.
- A candidate is promoted by activating its bundle only after human review and a signed commit.

**Limits.**
- R1 reports its method depends on the quality of the checker [E R1 §6].
- We have no reference implementation that defines a correct diagnosis, so the labeled replay corpus is the main cost, and its size and adequacy are **[U]**.
- Whether this loop improves operational metrics is **[H]**.
- Decision D10 decides whether to pursue the track.

---

## 12. Kill Criteria

1. Phase 0 shows SDK permission, hook, or sandbox semantics cannot guarantee SR-3, SR-4, SR-10 or SR-11 on the pinned version, **and** the gap cannot be closed outside the SDK.
2. **M0A cannot demonstrate its four properties.** If authenticated capability boundaries, a tamper-evident anchored audit trail, a fail-closed process topology, and a verified SDK configuration cannot all be shown, stop and redesign the containment layer before building anything on it.
3. Any unauthorized execution in containment, policy, sandbox, or testnet tests that cannot be traced to a fixable defect.
4. Judge misses seeded success-gaming or injection cases above an owner-set tolerance (P-28) after remediation. In M0 the tolerance is zero (§8.1).
5. Diagnosis quality below the owner threshold: Q-1 in M0 (§13.3); shadow-mode quality from Phase 4 (P-28).
6. Per-day cost, including the Judge, exceeds the owner budget (P-07) with no reduction path.
7. Observation itself measurably degrades validator performance beyond the owner-set tolerance (Q-7) and cannot be bounded by resource limits.
8. **(new v0.4)** The M0A time box expires, the one permitted extension (§7.1) expires too, and the four properties are still not demonstrated. This is treated as criterion 2.
9. **(new v0.4)** After the M0B run-in, the operator-value evidence (Q-1, Q-2, Q-4) does not support the product hypothesis (§2.6), and no change within M0's scope is expected to close the gap. Safety gates passing is not a reason to continue to M1.
10. **(new v0.5)** A provider that fails admission as both runtime and native adapter is dropped from the bundle. That is **not** a project kill, unless it is the reference provider and no other configuration has passed G1.

---

## 13. Decisions Needed From Owner (restructured in v0.4, Review-3)

v0.3 listed decisions without owners or deadlines, so "awaiting owner decisions" had no end. v0.4 gives every decision a DRI, an approver, the gate by which it must close, a **default adopted if it has not closed by then**, and the evidence that closes it. A default is a real decision. When the due gate arrives, the default is adopted and recorded, and any later change goes through change control (§17.1). Role names are defined in §7.1.

**D3 correction (Review-3).** In v0.3, D3 was "target cluster for Phase 4" in this plan but "target cluster for M0" in the HLD. v0.4 splits it: **D3** is now the M0 testnet environment, and **D18** is the Phase-4 target cluster.

### 13.1 Decision Register

**M0A blockers — each must be closed, or defaulted, at G0.**

| ID | Decision | DRI | Approver | Due | Proposed default if not decided by the due gate [A] | Evidence that closes it |
|---|---|---|---|---|---|---|
| **D1** | Implementation language (control plane and native adapter) | SDK DRI | PO | G0 | **Python** for controller, brokers, the Claude adapter (`claude-agent-sdk`) and the native adapter. The Codex and Antigravity runtimes are separate CLI binaries driven as subprocesses, so D1 does not constrain them (v0.5). The HLD reference and the X1 inspection are both Python. v0.3 moved start/end and validation work into the controller, so the TypeScript-only hook events add little (background below) | Recorded choice; lockfile |
| **D7** | Pinned runtime versions and model IDs, **per provider** (v0.5) | SDK DRI (Claude); Provider DRI (Codex, Antigravity) | PO | G0 for the reference configuration; before W1-O / W1-G for the others | **Claude:** the current `claude-agent-sdk` release on the G0 date, pinned exactly, and one current Claude model ID for all roles (candidate: `claude-opus-5`, confirm it is current at G0). **Codex:** the current `codex` CLI release and one current OpenAI model ID. **Antigravity:** the current `agy` release and one current Gemini model ID (the `--model` slug, S13), plus the matching Gemini API model ID for the native adapter. All exact, recorded at pin time, re-verified by W1 for that configuration. Per-role tiering waits for M0B cost data (Q-6). C1's model names are not used | Lockfiles and model IDs recorded in `providers.yaml` in the bundle; W1 run against each |
| **D3** | M0 testnet environment | Containment DRI | PO | G0 | One dedicated Agave **testnet** validator operated by the project, plus a separate ops host. No shared or third-party validator | ER-1, ER-2 signed off |
| **D5** | Alert channel | On-call operator | PO | G0 | A dedicated M0 channel on whichever service the operator already uses with watchtower (Slack, Discord, Telegram or Twilio [E] S2) | ER-4: test alert acknowledged by operator and backup |
| **D6** | Thresholds, budgets, trial and pass rules | PO | Security reviewer for safety parameters; on-call operator for alerting parameters | G0 for initial values; §13.3 targets no later than the start of the M0B run-in | The proposed values in §13.2, and the fixed floors in §13.3 | Signed registers §13.2, §13.3 |
| **D11** | OS sandbox backend | Containment DRI | Security reviewer | G0 for the choice; G1 for the proof | **bubblewrap** (namespaces plus seccomp). landlock only as an additional layer, since R2 documents it as weaker [E] R2 | W1 probe; fail-closed shown on the real backend at G1 |
| **D14** | Bundle signing key custody and rotation | PO | Security reviewer | G0 | Offline signing key on a hardware token held by the PO, with a sealed backup held by a second named person. Public keys pinned in controller configuration. Rotation: sign new bundles with the new key and pin both keys until the drain deadline (P-12) passes. Bundles signed by a retired key stay verifiable but cannot be activated | Key ceremony record (ER-8) |
| **D15** | Audit anchor service, cadence, maximum lag | Containment DRI | Security reviewer | G0 | Object storage with compliance-mode retention lock, in an account the ops host cannot administer. The ops host holds a put-only credential. Interval P-18; maximum lag P-19; above the maximum, no new LLM step starts (§4.4) | ER-7 failed-delete test |
| **D16** | Capability transport | Containment DRI | Security reviewer | G0 | **Unix domain sockets with kernel peer credentials on a single ops host.** mTLS is used only for the ops-host ↔ validator-host link, which already needs it. Splitting brokers across hosts is outside M0 | ER-10 |

**Multi-provider decisions (new in v0.5).**

| ID | Decision | DRI | Approver | Due | Proposed default if not decided by the due gate [A] | Evidence that closes it |
|---|---|---|---|---|---|---|
| **D19** | Provider scope and order for M0 | PO | Security reviewer | G0 | **Claude is the reference configuration and the only one on the G1 critical path.** Codex and Antigravity run on the parallel provider track and enter M0B through PA as each is admitted. G2 is granted per configuration. M0 counts as meeting the multi-provider requirement when **each** provider has at least one admitted configuration (runtime or native) that went through the M0B run-in. A provider stuck at *not admitted* is reported, not hidden | Recorded choice; PA records |
| **D20** | Runtime or native adapter, per provider | Provider DRI | Security reviewer | Each provider's W1 | Try the runtime adapter first. Fall back to the native API adapter on any PC failure. W1 decides; no preference is expressed in advance | W1 conformance record per configuration |
| **D21** | Data-handling approval, per provider | PO | Security reviewer | Before that provider's W1 (real episode data is not needed for W1, but keys are) | No provider receives episode data until its API data-handling terms are approved for testnet operational data (§17.2) | Written approval per provider |
| **D22** | Cross-provider Judge (for example, Claude judging a Codex planner) | PO | Security reviewer | After G2 of at least two configurations | **Not used in M0.** Evaluate afterwards as its own configuration, with its own model-quality gates | MQ results for the combined configuration |

**M0B blocker — must close before the work item that needs it.**

| ID | Decision | DRI | Approver | Due | Proposed default [A] | Evidence |
|---|---|---|---|---|---|---|
| **D9** | Consensus mode on testnet; exact cluster-feature query | Workflow DRI | PO | Before W15 | If the query is not verified against a primary source, the feature-state input is recorded as `unavailable`, mode resolves to `unknown`, and mode-specific recommendations are prohibited (§5.9). M0 stays usable | Query and its source recorded in the bundle |

**Excluded from M0.** These are recorded so they are not re-opened during M0.

| ID | Decision | M0 position | Decide before |
|---|---|---|---|
| D2 | Validator client(s) | **Agave only.** Fixed for M0 | Phase 4 |
| D4 | Upgrade method | Not needed; M0 performs no upgrade | Phase 3 (M1) |
| D8 | Tier table §5.1 | M0 uses T0 and T1 only. T2 approval is needed before M1 | G2 |
| D10 | Offline tuning track | **Excluded from M0** | After G2 |
| D12 | Approver policy | Not needed; M0 has no approval step | Phase 3 (M1) |
| D13 | Shadow-mode fleet size | **Excluded from M0.** M0 observes one validator | Phase 4 |
| D17 | Publication of operator-trust metrics | **Excluded from M0.** M0 results are internal G2 evidence | Phase 4 |
| **D18** | Target cluster for Phase-4 shadow mode (testnet or mainnet-beta). *The Phase-4 half of v0.3's D3* | Not an M0 question | Phase 4 |

**Background carried from v0.3.** These arguments are retained so the defaults above can be challenged on their merits.

| ID | Background |
|---|---|
| D1 | For TypeScript: it exposes hook events Python does not (`SessionStart`, `SessionEnd`, `StopFailure`) [E] S8, and C1 Recommendation 4 argues for it. Against treating that as decisive: all start/end and artefact-validation work belongs to the **trusted controller**, not to hooks inside the untrusted worker (§4.2, §5.11). C1's second argument, Solana web3.js compatibility, does not apply, because no component constructs or signs a transaction. A third option: **controller in one language, worker in whichever the SDK serves best**, since they communicate over sockets |
| D2 | C1 Recommendation 3 urges Jito-Solana on an "over 80% of validators" claim that is [U] here. Whatever is chosen, §5.8's rule holds: a client whose commands are not verified against a primary source stays [U] and is blocked from T2 |
| D7 | A different model for the Judge is possible; its value is unproven [H]. C1 Recommendation 5's *structure* (a cheaper model for high-frequency summarisation, a stronger one for diagnosis and judgement) is worth evaluating with M0B data. Its specific model names are stale and its "60–80%" saving is [U]. Re-pin on each SDK upgrade, which re-opens W1 (§5.2) |
| D11 | Must pass Phase 0 and must fail closed |
| D13 | C1 Recommendation 1 proposes shadow observation across 5–10 testnet validators to build operator trust. It is observation-only, but it changes the sentinel, store and cost model from single- to multi-target |
| D17 | A published metric becomes a target and invites the gaming this design otherwise guards against (§5.5) |

### 13.2 Parameter Register (D6, new in v0.4)

Every tunable value has one row, and each row is owned. "Proposed safe initial value" is [A] and errs in the safe direction: less load on the validator, fewer model turns and less spend, earlier hand-off to a human. Values marked *set at G0* depend on facts only the owner has. The register is versioned. Since v0.5, P-05, P-06 and P-30 are held per configuration, because turn counts and costs are not comparable across providers. The thresholds in a policy bundle are generated from it, never edited by hand, and each bundle records the register version it came from.

| ID | Parameter | Unit | Owner | Proposed safe initial value [A] | Bounds | Measurement source | Review cadence |
|---|---|---|---|---|---|---|---|
| P-01 | Sentinel check interval, per check | s | PO | 60 | 30 – 600 | Scheduler log; observer load (Q-7) | Each bundle release |
| P-02 | Identity balance floor | SOL | On-call operator | *Set at G0:* testnet vote cost per day × days of runway the operator wants | > 0 | `identity_balance`; vote-cost history | Monthly |
| P-03 | Catch-up alert: slot-distance threshold; consecutive samples | slots; samples | On-call operator | Threshold from the healthy-state distribution in the baseline campaign; 2 samples | samples 1 – 10 | `catchup` | After baseline, then monthly |
| P-04 | Disk headroom floor, ledger and accounts volumes | % free | On-call operator | 15 | 5 – 50 | `host_metrics` | Monthly |
| P-05 | `max_turns` per role | turns | SDK DRI | Until W1 measures: diagnostician 20, planner 15, Judge 15, reporter 10 | 1 – 50 | SDK `num_turns` | Each SDK or model pin |
| P-06 | `max_budget_usd` per session, per role | USD | PO | *Set at G0* from W1 cost measurements. Exhaustion hands off to a human, so lower is safer | > 0 | SDK `total_cost_usd` | Weekly during run-in |
| P-07 | Daily cost ceiling (Q-6) | USD/day | PO | *Set at G0* | > 0 | Cost records | Weekly |
| P-08 | Step retry budget (missing or invalid artefact) | count | Workflow DRI | 1 | 0 – 3 | Controller | Each release |
| P-09 | Judge FAIL retry budget N | count | Workflow DRI | 1 | 0 – 2 | Controller | Each release |
| P-10 | Capability token expiry | s | Security reviewer | Equal to P-11 | ≤ P-11 | Broker log | Each release |
| P-11 | Step wall-clock timeout | s | Workflow DRI | 300 | 60 – 900 | Controller | Each release |
| P-12 | Bundle drain deadline | h | PO | 24 | 1 – 72 | Controller | Each release |
| P-13 | Observer daemon limits: `CPUQuota`; `MemoryMax`; `TasksMax`; `LimitNOFILE` | % of one CPU; MiB; count; count | Containment DRI | 20; 256; 32; 256 | CPU ≤ 50; memory ≤ 1024 | cgroup accounting | After each Q-7 measurement |
| P-14 | Observer per-command rate cap; concurrency | calls/min; count | Containment DRI | 6 per command; concurrency **1 (fixed by design)** | rate 1 – 60; concurrency = 1 | Daemon log | After each Q-7 measurement |
| P-15 | Telemetry staleness threshold | × check interval | On-call operator | 3 | 2 – 10 | Telemetry probes | Monthly |
| P-16 | Local-RPC latency breaker threshold | ms | Containment DRI | 2 × the healthy p99 measured in the baseline campaign | — | `rpc_latency` | After baseline |
| P-17 | Verifier stability window W; `awaiting_operator` escalation deadline | samples; min | On-call operator | 5; 30 | W 3 – 20 | Verifier | Monthly |
| P-18 | Anchor interval | min | Security reviewer | 15 | 1 – 60 | Sequencer | Each release |
| P-19 | Maximum anchor lag before LLM steps stop | min | Security reviewer | 60 | ≥ 2 × P-18 | Anchor-lag metric | Each release |
| P-20 | Operator acknowledgement window (AW-3) | min | On-call operator | 15 | 5 – 60 | Alert sink | Monthly |
| P-21 | Rubric completion deadline (AW-4) | h | PO | 24 | 4 – 72 | Rubric records | Monthly |
| P-22 | Deterministic-gate trial count | trials | Security reviewer | 20 | ≥ 10 | CI | Per gate |
| P-23 | Model-quality runs per fixture; confidence level | runs; % | PO | 5 runs; 95% Wilson interval | runs ≥ 3 | Evaluation harness | Per gate |
| P-24 | Injections per supported fault class, baseline and run-in each | count | Fault injector | 10 | ≥ 5; size it so the interval can clear the target | Injection log | Per campaign |
| P-25 | M0B run-in observation period | days | PO | 28 | ≥ 14 | Calendar | Once |
| P-26 | RPO; RTO for store, chains and bundles | min | Containment DRI | RPO 15 (never above P-18); RTO 240 | — | Restore test (§17.3) | Quarterly |
| P-27 | Retention periods | per class | PO | §17.2 | — | — | Yearly |
| P-28 | Kill-criteria tolerances (§12 items 4–7) | per criterion | PO | *Set at G0* | — | — | Per gate |
| P-29 | Continuous provider unavailability before a **pre-approved** fallback bundle may be activated for new episodes (v0.5) | min | PO | 30 | 10 – 240; *never* if no fallback bundle is approved | Model-broker error rate | Monthly |
| P-30 | Per-session limits at the model broker: requests; input tokens; output tokens (v0.5) | count | Provider DRI | Requests = P-05 for the role; token limits from W1 measurements × 1.5 | > 0 | Model broker | Each provider pin |
| P-31 | Provider price table used to compute USD at the broker (v0.5) | USD per token class | PO | From each provider's published price list at pin time [U] | — | Provider price pages | Each provider pin, and monthly |

A value outside its bounds cannot be activated: the bundle builder refuses it. Widening a bound is a change-control item (§17.1).

### 13.3 Target Register (Q-1 … Q-8, new in v0.4)

Target values are set by the PO with the on-call operator. Those that need baseline data are set after the baseline campaign and before the M0B run-in. They are frozen before any evaluation run that counts. **Fixed floors cannot be relaxed by the owner.**

| ID | Target | Set by | Fixed floor |
|---|---|---|---|
| Q-1 | Minimum lower confidence bound on the diagnosis-correct share | PO + operator, before run-in | — |
| Q-2 | Minimum lower confidence bound on the FB-2 ∈ {1, 2} share | PO + operator, before run-in | **Unsafe flags = 0** |
| Q-3 | Maximum p50 and p95 report latency | PO + operator, at G0 | — |
| Q-4 | Minimum paired reduction in time to correct diagnosis vs. baseline, per fault class | PO + operator, after baseline | **Lower confidence bound > 0**, or the product hypothesis is not supported |
| Q-5 | Maximum alerts per day; maximum false-alarm share | Operator, at G0 | — |
| Q-6 | Maximum USD per episode; per day ≤ P-07 | PO, at G0 | — |
| Q-7 | Maximum validator local-RPC latency increase, observer on vs. off; observer never exceeds its cgroup limits | Containment DRI + operator, after baseline | Limits never exceeded |
| Q-8 | Unauthorized executions; containment-gate failures | — | **0** |

---

## 14. Sources

| ID | Source |
|---|---|
| S1 | Anza, *Operating a Validator* — https://docs.anza.xyz/operations |
| S2 | Anza, *Agave Validator Monitoring Best Practices* — https://docs.anza.xyz/operations/best-practices/monitoring |
| S3 | Anza, *Agave Validator Operations Best Practices* — https://docs.anza.xyz/operations/best-practices/general |
| S4 | Anza, *Agave Validator Security Best Practices* — https://docs.anza.xyz/operations/best-practices/security |
| S5 | Anza, *Validator Guide: Setup Node Failover* — https://docs.anza.xyz/operations/guides/validator-failover |
| S6 | Anthropic, *Agent SDK overview* — https://code.claude.com/docs/en/agent-sdk/overview |
| S7 | Anthropic, *Configure permissions* — https://code.claude.com/docs/en/agent-sdk/permissions |
| S8 | Anthropic, *Intercept and control agent behavior with hooks* — https://code.claude.com/docs/en/agent-sdk/hooks |
| S9 | Anthropic, *Agent SDK reference – Python* — https://code.claude.com/docs/en/agent-sdk/python |
| R1 | K. Kamahori, S. Li, S. Peter, B. Kasikci, *VibeServe: Can AI Agents Build Bespoke LLM Serving Systems?*, arXiv:2605.06068v1, 2026 — **preprint, not peer-reviewed** — https://arxiv.org/abs/2605.06068 |
| R2 | uw-syfi, *VibeSys* repository README (MIT license) — https://github.com/uw-syfi/vibesys |
| **V1** | Review of plan v0.2 and HLD v0.1 — `cx-feedback-solvalops-plan-hld.md` (2026-09-17). Findings F1–F10 and the M0A recommendation; drives most v0.3 changes |
| **C1** | Competitive analysis — `ag-solvalops-competitive-analysis.md` (2026-09-17). **Third-party market analysis; its market claims are unverified here and tagged [U]** (§1.2) |
| S10 | OpenAI, *Codex — Permissions* (permission profiles; Linux sandbox) — https://learn.chatgpt.com/docs/permissions (redirected from developers.openai.com/codex/permissions) |
| S11 | OpenAI, *Codex — Advanced configuration* and *Developer commands* (`openai_base_url`, `model_providers`, CLI reference) — https://developers.openai.com/codex/config-advanced · https://developers.openai.com/codex/cli/reference — **consulted through search excerpts only; full read is a W1-O item** |
| S12 | OpenAI, *Codex — Model Context Protocol* — https://developers.openai.com/codex/mcp — **search excerpt only** |
| S13 | Google, *Antigravity CLI — Headless mode* — https://antigravity.google/docs/cli/headless/ |
| S14 | `google-antigravity/antigravity-cli` issue #548, "--print (headless) mode ignores permissions.allow entirely" — **open** on 2026-09-21 — https://github.com/google-antigravity/antigravity-cli/issues/548 |
| **C2** | Third-party Antigravity CLI articles (for example, migration guides from Gemini CLI to `agy`, MCP configuration guides), 2026. **Unverified; every claim taken from them is [U]**, including that Antigravity CLI replaces Gemini CLI, the `AV_API_KEY` variable, and the MCP configuration path |
| **V2** | Pre-coding review of plan v0.3 and HLD v0.3 — `cx-feedback-v0.3-before-coding.md` (2026-09-21). Returns a **conditional no-go** pending the delivery definition; drives every v0.4 change ("Review-3") |
| **X1** | Direct inspection of `claude-agent-sdk` 0.2.154 on 2026-09-17: `ClaudeAgentOptions` field set, `SandboxSettings` field set, `PreToolUseHookSpecificOutput` decision values, Python hook event list, `ResultMessage` cost fields. Recorded in the HLD's Phase-0 appendix; **supersedes nothing until W1 re-confirms it on the pinned version** |

Sources S1–S9, R1, R2 accessed 2026-09-17; S10–S14 and C2 accessed 2026-09-21. Re-verify in Phase 0, per configuration.

**Traceability corrections (Review-2 F10, updated v0.4).** The companion HLD is `valops-agent-mvp-hld-v0.5.md`, and this plan's filename is `solana-agave-node-ops-agent-plan-v0.5.md`; earlier cross-references to `solana-validator-ops-agent-plan-v0.2.md` were wrong. `plan-review-vs-vibeserve.md`, cited by v0.2 and by HLD v0.1, **is not present in the repository**; no claim in v0.3 depends on it. If it exists elsewhere it should be added to the repository or the citation dropped permanently.

---

## 15. Competitive Position (informational; all market claims [U])

Recorded from C1 for the owner's roadmap decisions. Nothing in §2, §3 or §5 depends on this section.

| Segment | Example products (per C1) | Where valops-agent differs (per C1) |
|---|---|---|
| Conversational validator CLIs | SLV / `slv.dev` | Autonomous daemon rather than an interactive copilot; no arbitrary shell generation; independent Judge and tiers |
| Deterministic HA utilities | `solana-validator-failover`, `solana-validator-ha` | Those switch fast but do not diagnose *why*. Complementary, not competing (§1.2 Rec 2) |
| Managed StaaS | Blockdaemon, Kiln, Figment, Chorus One | Operator keeps hardware and keys; no custody or take-rate |
| Generic AI SRE | Kubiya, K8sGPT, Robusta, RunWhen | Those lack protocol context: leader slots, catch-up, identity balance, consensus state files |
| Passive observability | `agave-watchtower`, exporters, dashboards | Alerting without diagnosis; valops-agent consumes rather than replaces it (FR-2) |

**The positioning claim [U]:** "autonomous, protocol-native SRE for sovereign validators", differentiated on containment rather than on capability breadth.

**Two cautions the owner should carry into the roadmap decisions [A]:**

1. C1 treats the safety architecture as the moat. If that is right, then every schedule pressure to skip a gate is a pressure to delete the product's differentiator. M0A exists partly to make that trade-off explicit and early.
2. C1 identifies operator risk-aversion toward LLMs as the principal threat. The remedy in this plan is evidence, not persuasion: no write path in M0, deterministic closure, an anchored audit trail, and measured shadow-mode results. Publication of those results is D17, and a published metric becomes a target — which is precisely the gaming behaviour §5.5 exists to catch.

---

## 16. Traceability: Review-3 (V2) → v0.4

| V2 item | Resolution | Where |
|---|---|---|
| Keep the core safety posture (read-only M0, M0A gate, untrusted worker, immutable per-episode bundles, verifier-only resolution, telemetry loss as incident, missing data ≠ health) | Retained unchanged. No v0.4 change weakens any of them | §2.5, §4, §5 |
| Conditional no-go until the delivery definition is complete | Status set to conditional no-go; G0 introduced; no M0A code before G0 | Header, §7, §7.2 |
| M0 stated as single-validator, testnet-only, read-only assistant for a named operator — not an autonomous operator | Product definition | §2.1, §2.6 |
| Frozen product hypothesis, fault classes, watchtower baseline, report/alert workflow, feedback rubric | Added and frozen at G0 | §2.6 |
| Measurable targets: diagnosis quality, actionability, report latency, operator burden, cost, observation impact | Q-1 … Q-8 with target register and fixed floors | §2.6, §13.3 |
| Owners, approvers, due dates, defaults and evidence for D1/D7, D3, D5, D6, D11, D14, D15, D16 | Decision register | §13.1 |
| Keep D13, D10, D17, non-Agave clients and M1 execution out of M0 | "Excluded from M0" table; scope table updated | §2.3, §13.1 |
| D3 called both an M0 and a Phase-4 decision | Split into D3 (M0 testnet environment) and D18 (Phase-4 cluster) | §13 |
| Consensus mode described as both three-way and four-input | One wording: declared mode cross-checked against three observed inputs, four in total | FR-8, §5.3, §5.9; HLD §5.10 |
| HLD requires a "correctly ranked hypothesis" but the schema has no rank | `rank` and `step_session` fields; top-ranked hypothesis defined; exit criterion now measured by FB-1 | §5.7; HLD §7.1, §13 |
| W1 cannot validate a configuration before language, SDK and model are pinned | W1 depends on D1/D7 closure; results on other configurations do not count; re-pin re-opens W1 | §5.2, §7.1 |
| Time-boxed M0A charter, DRIs, estimates, critical path, environment readiness | M0A charter | §7.1 |
| Change control; data retention and access; backup and recovery tests; degraded-mode runbooks | Delivery governance; runbooks in HLD | §17; HLD §9.1 |
| Explicit go/no-go authority | G0/G1/G2 with deciders and vetoes | §7.2 |
| D6 as an auditable parameter register | Register with unit, owner, safe initial value, bounds, source, cadence | §13.2 |
| Deterministic gates 100%; model gates with frozen fixtures, repeatable controls, confidence reporting, human adjudication | Gate classes | §8.1 |
| M0A coding only after approval; M0B only after real, not mocked, boundaries, fail-closed sandbox, external anchoring and validated SDK; M1 only on safety **and** operator-value evidence | G0, G1 ("real, not mocked"), G2 | §7.2 |

### 16.1 Owner Requirement (2026-09-21) → v0.5

| Requirement | Resolution | Where |
|---|---|---|
| Support Claude, Codex and Gemini via Antigravity | Provider matrix; runtime and native adapters; conformance profile; admission per configuration | §5.12 |
| …without weakening any v0.3/v0.4 safety property | Every control already sat outside the model process. The model broker moves credentials and limits outside it too. Provider extras are defence in depth only | §4.2, §5.12.2, §5.12.3 |
| …without widening M0 beyond what V2 allowed | Still one validator, testnet, one operator. Claude is the only configuration on the G1 critical path; the others use a parallel track and enter through PA | §2.6, §7.1, §7.2, D19 |
| …with honest evidence | Every provider claim tagged; runtime gaps and the open Antigravity defect recorded, not assumed away | §5.12.1, §14 |

---

## 17. Delivery Governance (new in v0.4, Review-3)

### 17.1 Change Control

**Frozen items.** These are frozen: the §2.6 product definition; the registers in §13.1 – §13.3; the M0A charter (§7.1); the gate suites (§8, HLD §10); the model-quality fixture sets (§8.1); the degraded-mode runbooks (HLD §9.1); the pinned language runtime; and, per configuration, the runtime version and model ID (D1/D7), plus `providers.yaml` (§5.12.4).

**Procedure [A].**

1. A change request is filed under `docs/changes/`. It states what changes and why, which gates and evaluation runs it affects, its safety impact, and how to roll it back.
2. The PO approves every change. The **security reviewer** must also approve a change touching containment, a safety parameter, a deterministic suite, or the D1/D7 pins. The **on-call operator** must also approve a change touching alerting, the workflow or the rubric.
3. On approval, the register version is bumped, a new policy bundle is generated (a new hash, §5.10), and activation follows the normal bundle process.
4. Any evaluation run whose repeatable controls changed is marked **invalid for gate purposes**. A change to the D1/D7 pins re-opens W1 **for the affected configuration only**, together with the HLD §10.1 SDK-configuration suite and that configuration's PA.

**Emergency path.** A security fix may be applied first when it only *tightens* behaviour. Bundle revocation (§5.10) is the mechanism. The change request follows within one business day. The emergency path can never relax a gate, a bound or a fixed floor.

**Prohibited.** Relaxing a fixed floor (§13.3). Editing a fixture set in place. Changing a target after seeing the results of the run it applies to. Activating a hand-edited threshold file.

### 17.2 Data Retention and Access

Retention values are proposed [A] and live in the register as P-27.

| Data class | Contains | Proposed retention | Human access | Notes |
|---|---|---|---|---|
| Episode records | Signal summaries, hypotheses, recommendations, verdicts, verifications, costs | Project life + 1 year | PO, DRIs, operator, adjudicator | Written only through the store endpoints (§4.3) |
| Audit chains (ops host and daemon) and anchors | Tamper-evident history | At least 1 year after M0 ends, never shorter than the anchor store's retention lock | PO, security reviewer | Nobody can delete during the lock |
| Raw command payloads | Log tails and command output: **untrusted text** | 90 days | DRIs, operator | Redacted at source (HLD OD-4) |
| Session transcripts | Model output and tool traffic: **untrusted text** | 90 days | PO, security reviewer, adjudicator | Never parsed by the control plane (§5.11). Not used for tuning in M0 (D10 excluded) |
| Reports, rubric submissions, adjudications | Operator-facing output and feedback | Project life + 1 year | PO, operator, adjudicator | Input to G2 |
| Evaluation fixtures and results | Frozen sets and run records | Project life | PO, DRIs, security reviewer | Needed to reproduce any gate decision |
| Secrets | Anthropic, OpenAI and Google API keys (model broker only), token-minting key, chain-head and daemon-chain signing keys, bundle signing key, mTLS keys | Until rotated | The named holders only | Never in plaintext backups. Rotated when a holder leaves the project |

**Principles [A].**

- **Least privilege** per process class (§4.2). Humans use named accounts, and their access is logged.
- **Two egress paths only.** Data leaves the environment only through model-provider API calls, which pass through the model broker and carry exactly what the role's view contains, and through alerts to the D5 channel, which are size-capped and redacted. Since v0.5 up to three providers receive episode data: Anthropic, OpenAI and Google. **Each provider's data-handling terms must be approved (D21) before it receives any.** The broker refuses to route to a provider without an approval on record.
- **Model-broker transcripts** belong to the *session transcripts* class: untrusted text, 90 days.
- **No keypair material** in any data class (SR-2).

### 17.3 Backup and Recovery

| Asset | Backup | Recovery test (before G1 via ER-12, then quarterly) |
|---|---|---|
| Episode store | Periodic snapshot plus shipping of the append log, within RPO P-26 | Restore onto a fresh ops host; re-fold records and compare revisions; resume an open episode; show that idempotent retries add no duplicate appends |
| Ops-host audit chain | Copied with the store | `verify_chain` on the restored chain against the newest external anchor. Any gap between the restored head and the anchor must equal the expected loss window, and is recorded |
| Daemon chain | Backed up from the validator host | Verify against the daemon checkpoints the sequencer recorded |
| Bundle store, `active`, `revoked` | Replicated; bundles are immutable | Every bundle rehashes to its id. **The revocation list must never be restored to an older version:** revocations are also written to the audit chain, and a restore rebuilds the list from the newer of the backup and the chain |
| Registers, docs, gate records | Git | Clone and verify signed commits |
| Provider API keys (Anthropic, OpenAI, Google) | Not backed up | Re-issue from each provider. The model broker refuses to route to a provider whose key is missing; configurations of other providers keep working |
| Token-minting key | Not backed up | Regenerate; outstanding tokens are invalid by design |
| Chain-head signing key | Not backed up | Regenerate; record the key transition in the chain and in the next anchor |
| Bundle signing key | Sealed backup per D14 | Recover from the sealed backup. If both copies are lost: new key ceremony, re-sign, pin the new key |
| The validator itself | **Out of scope.** Operator's own procedures | M0 never touches the validator's data |

A failed recovery test blocks G1 or G2 until it passes. RTO and RPO are measured in each test and compared with P-26.

### 17.4 Cross-Document Consistency

- **One home per concept.** The plan governs. The product definition, the registers and the gates live only in the plan (§2.6, §7.2, §8.1, §13). Component behaviour and the degraded-mode runbooks live only in the HLD (§5, §9.1). The other document refers to them and never restates their values.
- **Pre-gate check.** Before each gate, a reviewer who did not edit the documents checks decision IDs, consensus-mode wording, schema fields against exit criteria, filenames and version numbers across both documents. The result goes in the gate record.

### 17.5 Degraded-Mode Runbooks

One runbook exists per failure mode in HLD §9. Each states the trigger, the automatic behaviour, the operator's actions, and the exit condition. The runbooks are in HLD §9.1 and in `docs/runbooks/`, and each is exercised by the degradation tests (§8). Operator unavailability (AW-3 escalation exhausted) has its own runbook: the system keeps observing and alerting, and never acts on its own, because in M0 it cannot.

---

## 18. 中文摘要（参考用，以英文为准）

**v0.5 变化：支持三家模型提供方（Claude、Codex、经 Antigravity 的 Gemini）**（负责人需求，2026-09-21；均为设计选择〔A〕）

1. **可行性依据**：v0.3 起所有管控均位于承载模型的进程之外（代理侧复核、外部沙箱、智能体端无结案能力、以存储产出物为准），与使用哪家运行时无关。
2. **新增模型代理（model broker，第五个能力代理）**：唯一持有三家 API 密钥；工作进程唯一的网络出口；按绑定配置限定模型；在代理侧统一执行轮次、令牌与美元上限（Codex、Antigravity 本身不提供此类上限）；所有模型请求/响应哈希后写入审计链。**工作进程不持有任何提供方凭据**（无密钥、无缓存登录）。
3. **运行时适配器与准入**：一致性要求 PC-1…PC-9（无头运行、仅可调用 `valops` 工具、内置工具被移除或在外部沙箱中被证明无效、不读取任何配置/指令文件、无凭据、运行于 D11 沙箱内、MCP stdio、禁止自动更新与遥测、版本固定、提示词只来自策略包）。结果三种：运行时准入 / 仅原生适配器 / 不准入。
4. **原生 API 适配器**：项目自写的最小工具调用循环，没有任何内置工具，作为每家提供方的保底路径。
5. **已核实的差异**（2026-09-21）：Codex 文档未说明能否移除 shell 工具；Antigravity CLI 无头模式默认允许工作区文件读写、使用缓存登录、未记录端点覆盖方式，且存在**未关闭缺陷 #548**（无头模式忽略 `permissions.allow` 并超时挂起）。由于本设计从不把进程内管控当作边界，这些缺陷不削弱安全性，只影响准入；预计 Antigravity 走原生适配器〔H〕。
6. **配置与绑定**：配置 =（提供方、适配器类型、运行时版本、模型 ID），写入策略包 `providers.yaml` 并随事件绑定；**事件进行中绝不切换提供方**；提供方中断时仅可启用**预先批准**的备用策略包。模型质量评估与 G2 均**按配置分别进行，绝不合并**。
7. **范围与进度**：M0 仍为单节点、测试网、单值班人员。Claude 为参考配置，唯一位于 G1 关键路径；Codex 与 Antigravity 走并行的"提供方轨道"，逐一通过新增的 **PA 准入关口**后进入 M0B。M0A 时限建议由 6 周调整为 7 周（新增模型代理），提供方轨道另需一名工程师，估算 22 人日。
8. **新增决策** D19（提供方范围与顺序）、D20（每家用运行时还是原生适配器）、D21（每家数据处理条款审批）、D22（跨提供方评审，M0 不采用）；**新增参数** P-29（启用备用策略包前的不可用时长）、P-30（代理侧会话上限）、P-31（价格表）。


**v0.4 结论与状态（保持有效）：** 根据编码前评审（V2，"Review-3"），当前为**"有条件不启动"**：在 G0 交付定义包获批之前，不编写任何 M0A 代码。v0.3 的全部安全边界保持不变。

**v0.4 主要变化（均为设计选择〔A〕）：**

1. **M0 产品定义（§2.6）**：M0 是服务于**指定值班人员**、仅针对**一台 Agave 测试网验证节点**的**只读事故分析助手**，而非自主验证节点运维系统。在 G0 冻结：产品假设、五类受支持故障（FC-1 进程停止、FC-2 身份账户余额不足、FC-3 磁盘余量不足、FC-4 运行版本偏离、FC-5 遥测丢失）、watchtower 基线采集方法、报告/告警流程（AW-1…AW-6）、人工反馈量表（FB-1…FB-6）及量化指标（Q-1 诊断质量、Q-2 建议可执行性、Q-3 报告时效、Q-4 相对基线的诊断耗时、Q-5 值班负担、Q-6 成本、Q-7 观测影响、Q-8 安全）。
2. **决策登记表（§13.1）**：D1/D7、D3、D5、D6、D11、D14、D15、D16 均指定负责人、审批人、截止关口、逾期默认方案与关闭证据。默认方案包括：Python；固定 SDK 版本与单一模型 ID；专用测试网节点；专用告警频道；bubblewrap 沙箱；硬件令牌离线签名密钥加密封备份；带合规保留锁的对象存储锚定；单主机 UDS + 内核对端凭据。
3. **明确排除于 M0**：D13 多节点影子运行、D10 离线调优、D17 公开指标、非 Agave 客户端、M1 执行能力。
4. **D6 拆分为参数登记表（§13.2）**：P-01…P-28，每项含单位、负责人、安全初值、上下限、测量来源、复审周期；目标登记表（§13.3）含不可放宽的底线（不安全建议数为 0、Q-4 置信下界 > 0、Q-8 为 0）。
5. **测试门槛分类（§8.1）**：确定性安全测试须 100% 通过；模型质量测试采用冻结样本、可重复控制、置信区间下界判定与人工裁决。
6. **分级授权（§7.2）**：G0（批准交付定义 → 开始 M0A 编码）、G1（M0A 在**真实而非模拟**的传输边界、失效即关闭的沙箱、外部审计锚定及已固定版本 SDK 上通过 → 开始 M0B）、G2（安全门槛**与**值班人员价值证据均达标 → 进入 M1）。安全评审人拥有安全否决权，值班人员拥有价值否决权。
7. **M0A 章程（§7.1）**：建议时限 6 周，第 3 周检查；负责人角色；工作量估算（共 57 人日）；关键路径 G0 → W3 → W4 → W7 → W8；环境就绪清单 ER-1…ER-13；超时只能经批准延期一次。
8. **交付治理（§17）**：变更控制、数据保留与访问、备份恢复测试、跨文档一致性检查、降级运行手册（见 HLD §9.1）。
9. **跨文档修正**：D3 拆分为 D3（M0 测试网环境）与 D18（阶段四目标集群）；共识模式统一表述为"声明值 + 三项观测输入交叉校验，共四项输入"；假设新增 `rank` 字段，使"排名第一的假设"可度量；W1 须在语言、SDK 版本与模型固定后执行。
10. **审计锚定最大延迟**：超过最大延迟时停止启动新的 LLM 步骤。

**v0.3 变化（历史记录）：** 传输层认证身份与三端点事件存储；单一审计定序器及外部锚定；四类进程及 `PreToolUse` 钩子降级为纵深防御；SDK 配置修正与提示词内联回退；并发安全（比较并交换、幂等键、仅 `awaiting_operator` 可转 `resolved`、`handed_off` 为终态）；撤回"可用性风险为零"；遥测健康事件类；共识模式声明值与三项观测输入交叉校验；不可变策略包；产出完整性校验；M0 拆分为 M0A 与 M0B。竞品分析（C1）建议仍仅作为决策输入，其市场数据标注为〔U〕，模型名称已过时，不得写入策略包。
