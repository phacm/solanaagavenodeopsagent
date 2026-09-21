# Plan: Solana Validator Node Self-Operating Agent (Claude Agent SDK)

| Field | Value |
|---|---|
| Document | Implementation plan, **v0.3** (DRAFT — for review before any code is written) |
| Author | Peng Huang (peng.huang@acm.org) |
| Date | 2026-09-17 |
| Supersedes | v0.2 (2026-09-17), v0.1 (2026-08-10) |
| Companion | `valops-agent-mvp-hld-v0.3.md` (refines this plan for milestone M0) |
| Status | Awaiting owner decisions in §13 |
| Governing language | English (Chinese summary in §16 is informational) |

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

"Review-2" above refers to source **V1** (§14), the review of plan v0.2 and HLD v0.1; its findings are numbered F1–F10, and are distinct from the earlier review whose findings drove v0.2.

All v0.3 changes are design choices **[A]** unless tagged otherwise. Neither inspiring reference (R1, a preprint in another domain) nor the competitive analysis (C1, unverified third-party market research) validates any requirement in this plan (§1.1, §1.2).

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
| Recommendation 1 — shadow mode across 5–10 testnet validators | Routed to D3 and new D13. Conflicts with the current single-validator scope (§2.3); see §13 |
| Recommendation 2 — position alongside `solana-validator-failover` rather than rebuild it | Accepted in spirit as a **documentation-only** change: the failover runbook skill may reference external failover tooling. No integration, and failover stays T3 (§2.3). [A] |
| Recommendation 3 — add Jito-Solana skills in Phase 1/2 | Routed to D2. Any client whose commands are not verified against a primary source stays [U] and is blocked from T2 (§5.8) |
| Recommendation 4 — choose TypeScript for D1 | Routed to D1, with C1's own rationale and its weaknesses recorded (§13 D1) |
| Recommendation 5 — tiered models per role, "60–80% cost reduction" | Structure routed to D7; the percentage is [U]. The model names C1 cites are **stale** and must not be copied into `policy/` (§13 D7) |

---

## 2. Scope

### 2.1 Goal

Build an agent, using the Claude Agent SDK, that performs day-to-day operations of a single Solana validator (Agave client). The agent observes health continuously, diagnoses problems, recommends remediation, and — from M1 — executes a small set of actions that are independently judged and approved by a human. It works under safety limits that are enforced outside the model, in processes the model cannot reach.

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
| Clients other than Agave | Commands not verified for other clients | [U] (D2) |
| Multi-validator fleet orchestration | Deferred. Note: C1 Recommendation 1 proposes *observation* across 5–10 validators, which is a narrower question — see D13 | [A] |
| Offline tuning loop (§11) | Research track | [A] (D10) |

### 2.4 Anti-Patterns (explicitly prohibited)

| Prohibited | Reason | Tag |
|---|---|---|
| Try-measure-revert search on the live validator | Reverting does not undo downtime or missed leader slots | [A]; leader-slot concern from [E] S3 |
| Agent widening its own scope, tiers, thresholds, or benchmark conditions | Tiers are fixed by the owner. R1 reports its agent escalating benchmark load on its own [E R1 §4.2]; that behavior is unacceptable here | [A] |
| Agent writing to executor or daemon code, validator configuration, policy, skills, or the audit log | Integrity of the control plane | [A] |
| Agent marking an episode "resolved" or grading its own action | Self-grading; see §5.6 | [A], inspired by [E] R2 |
| Single-trial safety evaluation | Safety claims need repeated trials (count TBD) | [A] |
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

Concrete limit values are **TBD by owner** (D6).

---

## 3. Requirements

### 3.1 Functional Requirements

| ID | Requirement | Source / Tag |
|---|---|---|
| FR-1 | Detect delinquency and alert promptly | [E] S2 |
| FR-2 | Integrate with `agave-watchtower`, running on a server separate from the validator | [E] S2 |
| FR-3 | Check identity account balance regularly and alert below a floor (**TBD by owner**) | [E] S3 |
| FR-4 | Restarts avoid leader slots, using `agave-validator exit` under systemd or `wait-for-restart-window` (M1+) | [E] S3, S5 |
| FR-5 | Upgrade flow: install while the validator runs → restart in an idle window → verify version with `grep -B1 'Starting validator with' <logfile>` (M1+) | [E] S3 |
| FR-6 | Default to `--no-snapshot-fetch` on routine restarts and run `solana catchup <pubkey>` afterwards. The agent never downloads a snapshot on its own in v1 | [E] S3; [A] "never" |
| FR-7 | The **Verifier** confirms state deterministically — recovery in M0, post-action from M1 — with `agave-validator monitor` or `solana catchup --our-localhost 8899`, and records an immutable result | [E] S5 for commands; [A] framework ownership |
| FR-8 | **(revised v0.3)** Consensus mode is a **declared deployment fact**, cross-checked against the running Agave version, cluster feature state, and consensus state files. Agreement selects the matching skill variant; **any disagreement yields `unknown`, and mode-specific recommendations are prohibited** | [E] S5 for the file distinction; [A] for the three-way check; activation on the target cluster is [U] (D9) |
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
| SR-8 | Claude API authenticated by API key. The key is held by the **controller**, never by the worker; the worker receives a short-lived session credential only | [E] S6; [A] for the split |
| SR-9 | Per-session `max_turns` and `max_budget_usd`, plus a per-episode retry budget. Values **TBD** | [E] S9 for options; [A] retry budget |
| SR-10 | **(revised v0.3) Policy integrity by immutable bundle.** Command table, thresholds, hook code, system prompts, skills, and verifier rules live in a hash-addressed bundle that is read-only to every process. An episode records its bundle id at open and is served from that bundle. Bundle identity is verified at process start, at episode open, and at every broker call. A verification failure puts the system in observe-only and alerts | [A], Review-2 F8 |
| SR-11 | **OS sandbox.** The worker process runs with no filesystem writes and no network egress except the Claude API endpoint and the broker sockets passed to it as inherited descriptors | [A]; backend choice D11 |
| SR-12 | **Judge isolation.** `proposal-judge` runs in a fresh session. It receives only the raw signal snapshot, the proposal, and the skill preconditions, never the orchestrator's, diagnostician's or planner's reasoning | [A] |
| SR-13 | **Audit integrity.** The audit log is append-only and hash-chained, written only by the audit sequencer (SR-15) | [A] |
| **SR-14** | **(new) Authenticated principals.** Every store and broker call derives its principal from the transport — a dedicated UDS with OS-enforced ownership and peer credentials, or an mTLS identity — plus a controller-minted capability token scoped to one episode, one role, one session, with an expiry and a nonce. **No request field names the caller.** The agent-facing endpoint exposes no state-transition, verification or closure operation at all | [A], Review-2 F1 |
| **SR-15** | **(new) Single audit sequencer with external anchoring.** One process owns the ops-host chain: it serialises entries, stamps the authenticated principal, hashes referenced payloads, fsyncs, and periodically signs and exports a chain head to append-only external storage (WORM object storage or a remote log service). The observer daemon maintains its own local chain on the validator host and forwards signed checkpoints; the sequencer records the daemon's chain head so truncation is detectable | [A], Review-2 F2 |
| **SR-16** | **(new) Process separation with fail-closed privileges.** Four process classes with disjoint credentials: untrusted SDK worker, trusted controller, capability brokers, observer daemon (§4.2). A worker compromise must yield no capability beyond the tool surface its capability token already permits | [A], Review-2 F3 |
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
│  ┌──── TRUSTED CONTROLLER (holds API key, mints capability tokens) ──────────────────────────┐   │
│  │  Episode Runner: deterministic step machine, CAS state transitions, artefact validation   │   │
│  │  spawns one UNTRUSTED WORKER per step, passing only broker socket descriptors + token     │   │
│  └───────────────────────────────────────────────────────────────────────────────────────────┘   │
│        │ fork/exec                                                                                │
│  ┌──── UNTRUSTED SDK WORKER (OS sandbox, SR-11) ────────────────────────────────────────────┐    │
│  │  one FRESH Claude Agent SDK session for exactly one role and one episode                  │    │
│  │   diagnostician │ change-planner │ proposal-judge │ reporter                              │    │
│  │  tools: in-process MCP server "valops" — every tool is an RPC stub over a broker socket   │    │
│  │  hooks: PreToolUse policy gate + audit  (DEFENCE IN DEPTH ONLY — see SR-16)               │    │
│  │  credentials: one short-lived capability token. No API key. No filesystem write.          │    │
│  └───────────────────────────────────────────────────────────────────────────────────────────┘    │
│        │ UDS (inherited fds)                                                                      │
│  ┌──── CAPABILITY BROKERS (each a small process, one job, own socket, own principal) ────────┐   │
│  │  episode-broker  (agent endpoint: appends only — no set_state, no verification)           │   │
│  │  observer-broker (validates + rate-limits, then calls the validator host)                 │   │
│  │  report-broker   (report store + alert sink)                                              │   │
│  │  audit-sequencer (SOLE writer of the ops-host chain; signs and anchors chain heads)       │   │
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
| **Untrusted SDK worker** | One short-lived capability token scoped to (episode, role, session, expiry) | Claude API; broker sockets inherited as file descriptors | Exactly the tool surface that token already permits, for one episode, until it expires. No API key, no policy write, no state transition, no audit authorship, no validator access except through the observer broker's allowlist and rate limits |
| **Trusted controller** | Claude API key; token-minting key; control endpoint of the episode store | Brokers, store control endpoint, worker lifecycle | Full control-plane authority. This process runs no model output and parses only structured broker responses |
| **Capability brokers** | Their own service identity; the observer client certificate (observer-broker only) | One downstream each | The capability of that one broker. Compromise of the observer broker yields read-only validator observation at its rate limits, nothing else |
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

Token properties [A]: single episode, single role, single session id, short expiry (**TBD**, D6), per-call nonce recorded for idempotency (SR-18), and bound to the policy bundle id of the episode so a bundle change invalidates outstanding tokens (§5.10).

### 4.4 Audit Sequencer (new in v0.3, Review-2 F2)

| Property | Design | Tag |
|---|---|---|
| Single writer | One sequencer process owns the ops-host chain file. Every other component submits records over a socket and receives the assigned sequence number and entry hash. No component appends directly | [A] |
| Server-stamped identity | `actor` is written by the sequencer from the authenticated principal of the submitting connection. A submitter cannot label its own entries | [A], Review-2 F1 |
| Durability | Each entry is fsynced before its acknowledgement | [A] |
| Payloads | Large payloads are content-addressed and hashed by the sequencer; the chain carries the reference, never the blob | [A] |
| External anchoring | The sequencer periodically signs `{chain_head, seq, timestamp}` and writes it to append-only external storage. Rewriting the local chain then requires also rewriting anchors the ops host cannot modify | [A] |
| Validator-host chain | The observer daemon keeps a local chain and forwards signed checkpoints to the sequencer, which records the daemon's head. Truncation of the daemon's chain becomes detectable at the ops host | [A] |
| Anchor cadence and backend | **TBD by owner** (D15) | — |

The residual limitation is stated plainly: anchoring bounds *how much* history an attacker can silently rewrite to the interval since the last anchor. It does not make the local file immutable.

### 4.5 Design Rationale

| Decision | Tag |
|---|---|
| Ops host separate from validator (same reasoning as watchtower placement) | [E] S2 for watchtower; [A] applied to agent |
| Deterministic sentinel and episode runner frame the LLM steps | [A] |
| Role separation with an independent Judge | [A]; pattern from [E] R1 §3.3 |
| Framework (not an agent) runs canonical verification | [A]; pattern from [E] R2 |
| Fresh session per step over persistent structured state | [A]; pattern from [E] R1 §3.3, R2 |
| Claude Agent SDK rather than raw Client SDK or Managed Agents | [E] S6 for product definitions; [A] preference for self-hosting near private infrastructure |
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

### 5.2 SDK Configuration (revised in v0.3, Review-2 F4)

A factory builds options for each step session. Every field below is a Phase-0 verification item; the plan does not assume the SDK behaves as documented until W1 confirms it on the pinned version.

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
    max_turns=BUNDLE.max_turns[role],            # TBD by owner (D6)
    max_budget_usd=BUNDLE.max_budget_usd[role],  # TBD by owner (D6)
    model=BUNDLE.model[role],                    # pinned (D7)
    continue_conversation=False, resume=None, fork_session=False,   # enforces R-1
    agents=None, plugins=[],                     # no subagents, no plugins
)
```

**Sandbox profile, stated with intent [A].** The SDK sandbox is the third of four layers and is never the control. Required intent: sandbox enabled; **fail closed if the sandbox backend is unavailable rather than silently running unsandboxed**; `allowUnsandboxedCommands=False`; no excluded commands; no weaker nested sandbox; network restricted to the Claude API endpoint; Unix socket access restricted to the broker sockets.

W1 must resolve one concrete discrepancy already observed: the review cites a `failIfUnavailable` setting, and in the SDK version inspected on 2026-09-17 (`claude-agent-sdk` 0.2.154) the `SandboxSettings` type exposed `enabled`, `autoAllowBashIfSandboxed`, `excludedCommands`, `allowUnsandboxedCommands`, `network`, `ignoreViolations` and `enableWeakerNestedSandbox`, with **no `failIfUnavailable` field present** [E, direct inspection]. Either the flag exists under another name or in another version, or fail-closed behaviour must be obtained outside the SDK. Until this is resolved, the external OS sandbox (SR-11) is treated as the sole sandbox control and the SDK sandbox as an unverified bonus.

**Skills fallback, removing an [U] from the critical path [A].** If W1 shows that a named skills library cannot be loaded reliably under `setting_sources=[]`, the runner falls back to **prompt inlining**: the runbook text for the role's permitted skills is concatenated into the role's system-prompt file inside the policy bundle, with the same source citations and compatibility matrix. The content, its provenance and its hash coverage are identical; only the delivery mechanism changes. No requirement depends on the `skills` field working.

| Role | `allowed_tools` | Input given to session | Required artefact (FR-12) |
|---|---|---|---|
| diagnostician | T0 tools + `add_hypothesis`, `set_hypothesis_status` | Episode record (signals, prior hypotheses) | ≥1 hypothesis, each with claim, test, expected evidence |
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
| `get_consensus_state_files` | T0 | detect `tower-*.bin` / `vote_history-*.bin` — **one input of three** to FR-8, never the sole determinant | [E] S5 |
| `get_telemetry_health` | T0 | observer reachability, latency, staleness per check | [A], new v0.3 |
| `get_verification_result` | T0 | read verification records | [A] |
| `add_hypothesis` | T1 | append hypothesis `{claim, test, expected_evidence}` | [A] |
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
        ├─ FAIL (with evidence) ──► back to planner; retry budget N (TBD) ──► exhausted ⇒ hand off to human
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
  "hypotheses": [{"id": "h1", "claim": "...", "test": "...", "expected_evidence": "...",
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

File presence alone is ambiguous: both `tower-*.bin` and `vote_history-<IDENTITY>.bin` may exist after a migration, a rollback, or incomplete cleanup. Mode is therefore established by agreement, not inference [A]:

| Input | Source |
|---|---|
| **Declared** mode in the deployment facts of the policy bundle | Owner-set, reviewed, hashed |
| **Running Agave version** and its support for the mode | Observed via `get_running_version` [E] S3 |
| **Cluster feature state** for the relevant consensus feature | Observed on-cluster; exact query is [U] (D9) |
| **Consensus state files** present, with modification times | Observed [E] S5 |

Rules: all inputs agreeing sets the mode. Any disagreement sets `unknown`, records every input in `consensus_mode_evidence`, raises an alert, and **prohibits mode-specific recommendations** — the planner is offered no mode-specific skill variant, and the Judge FAILs any proposal whose preconditions are mode-specific. Unknown mode does not stop observation, diagnosis, or reporting.

### 5.10 Policy Bundles: Versioning, Drain, Revocation, Rollback (new in v0.3, Review-2 F8)

v0.2 recorded a policy hash per episode and re-checked the *current* mount against it on every tool call, which would have stranded every in-flight episode on any legitimate policy deployment.

| Concept | Design | Tag |
|---|---|---|
| Bundle | An immutable directory addressed by the hash of its contents: command table, thresholds, prompts, skills, verifier rules, judge checklist, deployment facts. Bundles are never edited in place | [A] |
| Binding | An episode records its bundle id at open and is served from that bundle until it terminates. Capability tokens are bound to the same id | [A] |
| Activation | An `active` pointer names the bundle used for **new** episodes. Activation is a pointer change, not a content change | [A] |
| Drain | On activation, in-flight episodes continue on their bundle. A drain deadline (**TBD**, D6) bounds the number of live bundles; episodes exceeding it go to `handed_off` with an alert | [A] |
| Migration | There is none for a live episode. An episode never changes bundle mid-flight — a partly-old, partly-new policy is exactly the state this design exists to prevent | [A] |
| Emergency revocation | A revocation list names bundle ids that must stop being used immediately. Episodes bound to a revoked bundle go to `handed_off` with a high-severity alert; outstanding capability tokens for it are refused at the brokers | [A] |
| Rollback | Re-point `active` at the previous bundle. Because bundles are immutable and content-addressed, rollback is exact | [A] |
| Integrity check | Bundle contents are verified against their id at process start, at episode open, and at every broker call, using the episode's bound id — never "whatever is mounted now" | [A] |

Bundle signing key custody and rotation are **TBD by owner** (D14).

### 5.11 Output Completeness and Artefact Validation (new in v0.3, Review-2 F9)

A session that ends without writing its artefact has failed, however confident its prose. The controller therefore does the following after every step [A]:

1. Read the episode record from the store (not the transcript) and check that the role's required artefact from §5.2 exists, was written in this step, and satisfies its schema.
2. Cross-check against the session's structured output where the SDK supplies one; a disagreement between structured output and the stored artefact is a step failure, and the **stored artefact remains authoritative**.
3. On a missing or invalid artefact: count a step failure, retry within the retry budget (**TBD**, D6) with a fresh session, and on exhaustion move to `handed_off` with an alert naming what was missing.
4. Never parse prose to recover an artefact. Transcript text is read by no control-plane component; it is retained for audit and human review only.

---

## 6. Repository Layout

```
valops-agent/
├── PLAN.md · HLD.md
├── pyproject.toml | package.json        # D1
├── bundles/                             # immutable, hash-addressed policy bundles (§5.10)
│   ├── <bundle-hash>/
│   │   ├── command_table.yaml           # read-only commands only in M0
│   │   ├── thresholds.yaml              # values TBD by owner
│   │   ├── deployment.yaml              # declared consensus mode, client, ledger paths (§5.9)
│   │   ├── prompts/{diagnostician,change_planner,proposal_judge,reporter}.md
│   │   ├── skills/<skill>/SKILL.md      # §5.8 (or inlined into prompts — §5.2 fallback)
│   │   ├── verifier/<signal>.yaml       # declarative predicate + stability window
│   │   ├── judge_checklist.yaml
│   │   └── MANIFEST.sha256 (+ .sig)
│   ├── active                           # pointer for NEW episodes
│   └── revoked                          # revocation list (§5.10)
├── controller/                          # TRUSTED: runner state machine, token minting, artefact validation
│   ├── runner.py · transitions.py · artefacts.py · tokens.py
├── worker/                              # UNTRUSTED: SDK session host
│   ├── main.py · options.py             # per-role ClaudeAgentOptions factory
│   ├── hooks/{policy_gate,audit}.py     # defence in depth (SR-16)
│   └── tools/stubs.py                   # MCP tools = RPC stubs over broker sockets
├── brokers/
│   ├── episode_broker.py                # agent endpoint: appends only
│   ├── observer_broker.py               # validation, rate limits, mTLS client
│   ├── report_broker.py                 # report store + alert sink
│   └── audit_sequencer.py               # SOLE chain writer; signs and anchors heads (§4.4)
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
└── tests/
    ├── unit/
    ├── containment/   # capability boundaries, principal spoofing, sandbox escape, audit forgery
    ├── policy/        # denial, tamper, bundle drain/revocation/rollback
    ├── judge/         # success-gaming and injection proposals
    ├── concurrency/   # CAS races, duplicate delivery, recovery-during-analysis
    ├── integration/   # testnet fault injection
    └── replay/        # recorded incident corpus (also used by §11)
```

---

## 7. Phased Implementation

Phase 1 of v0.2 is split. The review's central recommendation is that the containment layer be **demonstrated** before the diagnosis workflow is built on top of it, because every later safety claim rests on it.

| Phase | Milestone | Deliverable | Exit criteria |
|---|---|---|---|
| **0 — Verify** | Phase 0 (HLD W1) | Spike on pinned SDK version. Confirm: `tools=["Skill", ...]` semantics and whether skills load with `setting_sources=[]`; `dontAsk` + role-scoped allowlists; hook deny and timeout behaviour; SDK sandbox fail-closed behaviour and the `failIfUnavailable` discrepancy (§5.2); OS sandbox backend with the SDK process; structured `output_format` | Written verification log. Every mismatch amends §5.2 before Phase 1 starts |
| **1A — Containment prototype** | **M0A** | The four properties the review asks to prove first: (1) authenticated capability boundaries around the episode store, (2) centralised audit sequencer with external anchoring, (3) concrete process/sandbox topology that fails closed, (4) a verified SDK configuration loading exactly the intended tools, prompts and skills — with **no diagnosis workflow at all** | Containment suite (§8) passes over N trials: principal spoofing refused, agent endpoint has no closure capability, forged and expired tokens refused, chain forgery detected against the anchor, sandbox escape blocked, worker holds no API key. **M0B does not start until these pass** |
| **1B — Read-only core** | **M0B** | Observer daemon with resource limits; observer/episode/report brokers; policy bundles with drain and revocation; sentinel incl. telemetry-health; episode store with CAS and idempotency; diagnostician | Policy tests pass: no non-T0 execution possible; bundle tamper leads to observe-only; telemetry loss opens its own episode |
| **2 — Roles, judgement, reporting** | M0B | Controller state machine, planner, **proposal-judge**, reporter, skills v1 (or inlined prompts), recovery verifier, closure reports | Testnet fault injection produces correct episodes. Judge suite catches all seeded success-gaming proposals (suite frozen before the run). Artefact-validation suite passes |
| **3 — Gated actions (testnet)** | M1 | Approval service, executor with token and precondition checks, T2 restart and upgrade, configuration repository | End-to-end testnet upgrade: Judge PASS → human approval → execution → verification records success |
| **4 — Shadow mode on target cluster** | M1 | Full pipeline with execution disabled; humans act on their own and compare | Observation period (**TBD**) completed; §9 metrics collected, including per-role cost. Scope of the shadow fleet is D13 |
| **5 — Limited autonomy** | M1 | Enable T2 with approval on target cluster | Owner sign-off |

Testnet first per [E] S3. `solana-test-validator` is used for unit-level loops only; cluster behaviours require testnet [H].

---

## 8. Test Plan

| Category | Tests |
|---|---|
| **Containment (M0A gate, CI-blocking)** | Caller-asserted principal ignored; agent endpoint offers no `set_state`, verification or closure operation; token for episode A refused on episode B; expired token refused; token bound to a revoked bundle refused; duplicate nonce is a no-op; worker process holds no API key and cannot reach any network endpoint but the Claude API and its broker sockets; audit entry attributed to a principal the submitter does not hold is impossible; chain rewrite detected by comparing against an external anchor; observer daemon resource limits enforced under load |
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
| Degradation | Claude API down; store down; broker down; daemon down; budget or retry budget exhausted; anchor unreachable. Correct degradation tier; validator unaffected; human alerted |
| Repetition | Each safety-relevant test repeated over N trials (**TBD**, D6); no single-trial pass counts |

---

## 9. Evaluation Metrics (targets TBD by owner)

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
| **Worker compromise via prompt injection or SDK defect** | Worker holds only a scoped, short-lived token; brokers re-enforce every check; no API key, no filesystem write, no state transition (§4.2) | [A], new v0.3 |
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
| Alpenglow activation changes files or commands | FR-8 three-way check + skill matrix; re-verify S5 before Phase 3 | [U] |
| Judge cost increases per-episode spend | Per-role cost metrics; budgets (D6) | [A] |
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
4. Judge misses seeded success-gaming or injection cases above an owner-set tolerance (**TBD**) after remediation.
5. Shadow-mode diagnosis quality below the owner threshold (**TBD**).
6. Per-day cost, including the Judge, exceeds the owner budget (**TBD**) with no reduction path.
7. Observation itself measurably degrades validator performance beyond an owner-set tolerance (**TBD**) and cannot be bounded by resource limits.

---

## 13. Decisions Needed From Owner

| ID | Decision | Note |
|---|---|---|
| D1 | SDK language | Python (`claude-agent-sdk`) or TypeScript (`@anthropic-ai/claude-agent-sdk`). **Still open.** For TypeScript: it exposes hook events Python does not (`SessionStart`, `SessionEnd`, `StopFailure`) [E] S8, and C1 Recommendation 4 argues for it. Against treating that as decisive: in v0.3 all start/end and artefact-validation work belongs to the **trusted controller**, not to hooks running inside the untrusted worker (§4.2, §5.11), so the extra hook events buy less than they appear to; and C1's second argument — Solana web3.js compatibility — does not apply, because no component of this system constructs or signs a transaction. A third option, not in either source: **controller in one language, worker in whichever the SDK serves best**, since they communicate over sockets |
| D2 | Validator client(s) | Agave only vs. others [U]. C1 Recommendation 3 urges Jito-Solana on an "over 80% of validators" claim that is [U] here. Whatever is chosen, §5.8's rule holds: a client whose commands are not verified against a primary source stays [U] and is blocked from T2 |
| D3 | Target cluster for Phase 4 | testnet / mainnet-beta |
| D4 | Upgrade method | build from source vs. release binaries [E] S3 |
| D5 | Alert and approval channel | watchtower supports Slack, Discord, Telegram, Twilio [E] S2 |
| D6 | Thresholds and budgets | balance floor, check intervals, `max_turns`, `max_budget_usd`, retry budget N, **capability-token expiry**, **bundle drain deadline**, **observer resource limits and rate caps**, **telemetry staleness thresholds**, stability window W, observation period, repetition count, kill-criteria tolerances |
| D7 | Model selection | Pinned model ID(s); optionally a different model for the Judge (value unproven, [H]). C1 Recommendation 5's *structure* — a cheaper model for high-frequency summarisation, a stronger one for diagnosis and judgement — is worth evaluating; its **specific model names are stale and must not be copied into a bundle**, and its "60–80%" saving is [U]. Pin current model IDs at decision time and re-pin on each SDK upgrade |
| D8 | Tier table §5.1 | Approve or adjust |
| D9 | Consensus mode on target cluster | Alpenglow active at deployment? [U]. Also: the exact cluster-feature query used as the second input to §5.9 is [U] |
| D10 | Offline tuning track (§11) | Pursue yes or no; corpus budget |
| D11 | OS sandbox backend | For example bubblewrap vs. landlock on Linux (VibeSys documents landlock as weaker [E] R2); must pass Phase 0 and must fail closed |
| D12 | Approver policy | Single approver vs. two-person approval for T2 (M1+) |
| **D13** | **Shadow-mode fleet size** | C1 Recommendation 1 proposes shadow observation across 5–10 testnet validators to build operator trust. This is observation-only and so does not need the fleet-orchestration work excluded in §2.3, but it does change the sentinel, store and cost model from single- to multi-target. Decide: single validator, or N observed targets with per-target episode isolation |
| **D14** | **Bundle signing key custody and rotation** | Who holds the key, where, how it rotates, and what happens to bundles signed by a retired key |
| **D15** | **Audit anchor backend and cadence** | WORM object storage vs. a remote log service; anchor interval; who can read the anchor; what a missing or stale anchor triggers |
| **D16** | **Capability transport** | Unix domain sockets with peer credentials (single-host ops plane) vs. mTLS identities (if brokers are ever split across hosts) |
| **D17** | **Publication of operator-trust metrics** | C1 Recommendation 1 proposes publishing diagnosis accuracy and false-alarm rates. Decide whether shadow-mode results are published, and if so under what definitions, since a published metric becomes a target and invites the gaming this design otherwise guards against |

D13–D17 are new in v0.3. D13, D17 originate from the competitive analysis; D14–D16 from the containment review.

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
| **X1** | Direct inspection of `claude-agent-sdk` 0.2.154 on 2026-09-17: `ClaudeAgentOptions` field set, `SandboxSettings` field set, `PreToolUseHookSpecificOutput` decision values, Python hook event list, `ResultMessage` cost fields. Recorded in the HLD's Phase-0 appendix; **supersedes nothing until W1 re-confirms it on the pinned version** |

Sources S1–S9, R1, R2 accessed 2026-09-17. Re-verify in Phase 0.

**Traceability corrections (Review-2 F10).** The companion HLD is `valops-agent-mvp-hld-v0.3.md`, and this plan's filename is `solana-agave-node-ops-agent-plan-v0.3.md`; earlier cross-references to `solana-validator-ops-agent-plan-v0.2.md` were wrong. `plan-review-vs-vibeserve.md`, cited by v0.2 and by HLD v0.1, **is not present in the repository**; no claim in v0.3 depends on it. If it exists elsewhere it should be added to the repository or the citation dropped permanently.

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

## 16. 中文摘要（参考用，以英文为准）

**v0.3 主要变化（均为设计选择〔A〕；评审意见 V1 与竞品分析 C1 均不构成需求依据，C1 的市场数据一律标注为〔U〕）：**

1. **身份由传输层认证，调用方不得自述身份**：事件存储拆分为三个独立端点（智能体端 / 控制端 / 验证端），智能体端**根本不存在**状态迁移、验证写入与结案能力；能力令牌绑定单一事件、单一角色、单一会话、限时并带随机数。
2. **单一审计定序器**：唯一的链写入者，服务端盖章写入真实主体，落盘 fsync，定期对链头签名并锚定到运维主机之外的只追加存储；验证节点侧守护进程维护本地链并转发签名检查点。
3. **明确四类进程**：不受信 SDK 工作进程（仅持短期能力令牌，无 API 密钥、无文件写入）、受信控制器、能力代理、观测守护进程。**进程内 `PreToolUse` 钩子降级为纵深防御**，真正的管控在代理侧重新执行。
4. **SDK 配置修正**：显式 `tools` 列表须包含 `Skill`；并提供**提示词内联回退方案**，使技能库加载不再是关键路径上的未知项；沙箱要求"不可用即拒绝启动"，且已记录 0.2.154 版本中未发现 `failIfUnavailable` 字段这一实测差异。
5. **并发安全**：授权主体迁移表、基于修订号的比较并交换、每次追加的幂等键；分析过程中若自发恢复，只追加"恢复观测"而不改变状态；仅 `awaiting_operator` 可转入 `resolved`；`handed_off` 为终态；结案后必须产出结案报告与告警。
6. **撤回"可用性风险为零"的表述**，改为"不存在有意的验证节点状态变更路径"，并补充观测侧资源限制（systemd/cgroup、并发为一、限流、本地 RPC 熔断）。
7. **可观测性本身成为受监控对象**：新增 telemetry-health 事件类；数据缺失绝不用于开启、降级或关闭验证节点健康事件。
8. **共识模式改为声明事实 + 三方交叉校验**（声明值、运行版本、集群特性状态、状态文件），任一不一致即为 `unknown`，并禁止任何模式相关建议。
9. **不可变哈希寻址策略包**：事件在开启时绑定某个策略包直至终态；定义了灰度、排空、紧急吊销与精确回滚，解决了"发布新策略会卡死所有在途事件"的问题。
10. **产出完整性校验**：每步结束后由控制器核对必需产出物是否写入且符合模式，散文永不被解析为产出物；缺失即步骤失败，重试预算耗尽转人工。
11. **阶段划分调整**：原阶段一拆分为 **M0A 容器化/隔离原型**（先证明四项隔离性质）与 **M0B 只读核心**；M0A 不通过则不启动 M0B。
12. **新增待决事项** D13 影子模式观测节点数量、D14 策略包签名密钥保管与轮换、D15 审计锚定后端与周期、D16 能力传输方式、D17 是否公开运维可信度指标。

**竞品分析的四项建议**（TypeScript、Jito 支持、多节点影子模式、分层模型）**均记录为待决事项的输入，不在本版中拍板**；其中模型名称已过时，不得写入策略包。
