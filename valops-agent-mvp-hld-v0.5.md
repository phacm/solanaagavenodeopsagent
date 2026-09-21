# High-Level Design: Solana Validator Ops Agent — MVP (M0)

| Field | Value |
|---|---|
| Document | High-Level Design (HLD), **v0.5** — DRAFT for review |
| Product | Solana Validator Node Self-Operating Agent ("valops-agent") |
| Milestone | **M0 — a read-only incident-analysis assistant** (plan §2.6), split into **M0A** (containment prototype) and **M0B** (diagnosis workflow) |
| Author | Peng Huang (peng.huang@acm.org) |
| Date | 2026-09-21 |
| Supersedes | v0.4 (2026-09-21), v0.3 (2026-09-17), v0.1 (2026-09-17). Version numbers are kept in lockstep with the plan |
| Parent document | `solana-agave-node-ops-agent-plan-v0.5.md` (governs; this HLD refines it) |
| Governing language | English (Chinese summary in §18 is informational) |
| Status | **Conditional no-go for implementation** until G0 (plan §7.2). Open decisions in §15 |

---

## Change Log

| Version | Change | Driver |
|---|---|---|
| v0.1 | Initial M0 design | — |
| **v0.3** | Episode store split into three endpoints with transport-authenticated principals; the agent endpoint has no closure capability to misconfigure (§5.3) | V1 F1 |
| **v0.3** | Single audit sequencer, server-stamped principals, fsync, externally anchored signed chain heads; validator-host daemon keeps its own chain (§5.5) | V1 F2 |
| **v0.3** | Four named process classes with explicit compromise analysis; the `PreToolUse` hook demoted to defence-in-depth (§4.3, §6.3) | V1 F3 |
| **v0.3** | SDK configuration corrected (`tools` must carry `Skill`), fail-closed sandbox intent, prompt-inlining fallback that removes the skills dependency from the critical path (§6.1, §6.2) | V1 F4 |
| **v0.3** | Transition table with authorised principals, CAS revisions, idempotency keys, defined spontaneous-recovery behaviour, mandatory closure report, terminal `handed_off` (§5.2, §7.3) | V1 F5 |
| **v0.3** | "Zero availability risk" withdrawn; observer resource limits; telemetry-health episode class (§2.4, §5.9, §5.1) | V1 F6 |
| **v0.3** | Consensus mode is a declared fact cross-checked three ways; disagreement ⇒ `unknown` ⇒ no mode-specific recommendation (§5.10) | V1 F7 |
| **v0.3** | Immutable hash-addressed policy bundles with binding, drain, revocation and rollback (§5.4) | V1 F8 |
| **v0.3** | Artefact validation after every step; prose is never an artefact (§5.8) | V1 F9 |
| **v0.3** | Traceability and naming fixed: correct parent filename, `plan-review-vs-vibeserve.md` dependency removed, Observer Daemon vs. Executor separated by milestone (§0.1) | V1 F10 |
| **v0.3** | M0 split into M0A and M0B; M0B is gated on M0A's four properties (§13, §14) | V1 Recommendation |
| **v0.3** | Phase-0 partial verification appendix recording what was inspected on the SDK and what remains open (§16) | V1 F4 |
| **v0.3** | Competitive positioning routed to plan §15 and the open decisions; no design change | C1 |
| **v0.4** | M0 restated as a single-validator, testnet-only, read-only incident-analysis assistant for a named on-call operator. The product definition, registers and gates live in the plan and are referenced here, not restated (§1, §3) | V2 |
| **v0.4** | Hypotheses carry `rank` and `step_session`; the store enforces unique contiguous ranks per step. "Correctly ranked hypothesis" replaced by a measurable, adjudicated criterion (§5.3, §7.1, §13) | V2 |
| **v0.4** | Consensus mode worded uniformly: declared mode cross-checked against three observed inputs, four in total (§2.1, §5.10, §12) | V2 |
| **v0.4** | Maximum anchor lag stops new LLM steps (§5.5, §9) | V2 (D15) |
| **v0.4** | Degraded-mode runbooks (§9.1) | V2 |
| **v0.4** | Test gates split into deterministic (100%) and model-quality (frozen fixtures, confidence bounds, adjudication); M0A gates must run on real, not mocked, boundaries (§10) | V2 |
| **v0.4** | Work breakdown gains W0 (G0 package) and the M0B evaluation items. W1 depends on D1/D7 pins (§12) | V2 |
| **v0.4** | Exit criteria re-expressed as gates G1 and G2 with named authority; G2 requires operator-value evidence as well as safety (§13) | V2 |
| **v0.4** | Open decisions restructured: M0A blockers with defaults; D13 and D17 no longer block M0 and are excluded from it; D3 split, with D18 added (§15) | V2 |
| **v0.5** | **Multi-provider: Claude, Codex, Gemini via Antigravity.** Worker hosts one adapter; model broker [12] holds every provider key and is the worker's only egress (§4, §5.12) | Owner requirement 2026-09-21 |
| **v0.5** | Adapter launch specifications for Codex, Antigravity and the native API adapter (§6.5); new M0A suites for provider conformance and the model broker (§10.1); PA gate (§13); RB-14 (§9.1); provider evidence appendix (§16.1) | Owner requirement |
| **v0.5** | **Codebase implementation & architecture reconciliation (N-1 … N-17).** Store expanded to 5 endpoints (split `store-agent-report`, added `store-observe` for citable tool-driven observations; N-1, N-2); worker connects to bind-mounted UDS sockets in sandbox rather than inherited fds to preserve `SO_PEERCRED` kernel peer authentication (N-3); transition table reconciled so Judge retry exhaustion transitions to `handed_off` (N-4) and `no_action` routes to `judging` (N-5); Judge view clarified with deterministic verification records (N-6); store deterministically rejects mode-specific proposals under `unknown` mode (N-7); reporter alert metadata populated directly from record (N-8); terminal states accept reports, recovery observations, and controller bookkeeping (N-9); model broker streaming relay before audit (N-11), conservative usage estimation fallback (N-12), and refusal fallback disabling (N-10); delinquency check uses slot distance trend over P-03 samples (N-15); controller retains only `CAP_SETUID`/`CAP_SETGID` (N-14); per-role quotas (N-16); Judge-isolation assertion excludes target artefact under judgement (N-17) | Implementation reconciliation |

---

## 0. Abbreviations (first use)

| Abbreviation | Full term |
|---|---|
| HLD | High-Level Design |
| MVP | Minimum Viable Product |
| SDK | Software Development Kit |
| MCP | Model Context Protocol |
| LLM | Large Language Model |
| API | Application Programming Interface |
| RPC | Remote Procedure Call |
| HTTP / HTTPS | Hypertext Transfer Protocol (Secure) |
| mTLS | Mutual Transport Layer Security |
| UDS | Unix Domain Socket |
| CAS | Compare-And-Swap |
| WORM | Write Once, Read Many (immutable storage) |
| OS | Operating System |
| JSON | JavaScript Object Notation |
| YAML | YAML Ain't Markup Language |
| UUID | Universally Unique Identifier |
| SHA-256 | Secure Hash Algorithm, 256-bit |
| BFT | Byzantine Fault Tolerance ("Tower BFT", Solana's pre-Alpenglow vote/lockout mechanism) |
| SoT | Source of Truth |
| MTTD / MTTR | Mean Time To Detect / Mean Time To Recover |
| USD | United States Dollar |
| CI | Continuous Integration |
| SLO | Service Level Objective |
| TBD | To Be Decided |
| DRI | Directly Responsible Individual |
| RPO / RTO | Recovery Point Objective / Recovery Time Objective |

**Evidence tags.** `[E]` externally verifiable (§16). `[A]` design choice made here. `[H]` hypothesis to validate. `[U]` unknown, must be resolved.

No performance, cost, stake, reward, or market figure is asserted. Every threshold comes from the plan's parameter register (plan §13.2, IDs `P-nn`) and every target from its target register (plan §13.3, IDs `Q-n`). Proposed initial values there are [A] and bind nothing until G0.

### 0.1 Naming (V1 F10)

| Term | Meaning | Exists in |
|---|---|---|
| **Observer Daemon** | Validator-host process serving a **read-only** command table by command id | M0 onward |
| **Executor** | Validator-host process able to run **state-changing** commands under an approval token | **M1 onward — absent from the M0 artefact** |
| **Verifier** | Deterministic component that confirms state from re-sampled signals. In M0 it confirms *recovery*; from M1 it also performs *post-action* verification | M0 onward |
| **Controller** | Trusted ops-host process: episode runner, state transitions, token minting, artefact validation | M0 onward |
| **Worker** | Untrusted ops-host process hosting exactly one **adapter** (Claude SDK, `codex exec`, `agy -p`, or native API loop) running one session for one role and one episode | M0 onward |
| **Adapter** | The launcher and shim that run one provider runtime, or the native loop, inside a worker (§6.5; plan §5.12.3) | M0 onward (v0.5) |
| **Configuration** | (provider, adapter kind, runtime and version, model ID) — the unit of admission, binding and evaluation (plan §5.12.4) | M0 onward (v0.5) |
| **Model broker** | Capability broker holding every provider key; the worker's only network egress (§5.12) | M0 onward (v0.5) |

This document uses no other name for these components. Earlier drafts used "Executor" for the M0 read-only daemon; that usage is withdrawn.

---

## 1. Purpose and Position

Plan v0.5 describes the full system across six phases. This HLD specifies **only M0**, the smallest deployable increment that delivers value while taking no intentional risk to the validator, and that builds the complete control-plane skeleton later milestones plug into.

**What M0 is (v0.4, V2).** *A single-Agave-validator, testnet-only, read-only incident-analysis assistant for a named on-call operator — not an autonomous validator operator.* Its product hypothesis, its five supported fault classes (FC-1 … FC-5), the watchtower baseline, the report and alert workflow (AW-1 … AW-6), the feedback rubric (FB-1 … FB-6) and the measurable targets (Q-1 … Q-8) are defined **once, in plan §2.6**, and frozen at G0. This HLD designs the system that serves that definition. It does not restate or vary it.

**Model providers (v0.5).** Any role can be served by Claude, Codex or Gemini via Antigravity. Each is served through a *configuration* (provider, adapter, runtime version, model) that must pass admission (PA) before use. Every containment property in this HLD holds identically for every admitted configuration. That is possible because the boundary never depended on the runtime (DD-13, §5.12, §6.5).

**Authorisation (v0.4). Nothing here is built before **G0** approves the delivery package. M0B starts only after **G1**, where M0A is proven on real boundaries. M1 starts only after **G2**, where both the safety gates and the operator-value evidence pass. Gates, deciders and vetoes are in plan §7.2.

**M0 thesis [A].** The riskiest parts of this system are not the actions — they are the *judgement* and the *containment*. M0 therefore ships the judgement path (diagnose → recommend → independently judge → report) and the entire containment layer (capability boundaries, policy bundles, sandbox, anchored audit chain, deterministic verification), but ships **no ability to change the validator**. The value delivered is faster, better-evidenced diagnosis handed to a human operator.

**M0A before M0B [A], new in v0.3.** Every safety claim in this design rests on the containment layer, so the containment layer is built and proven first, with no diagnosis workflow attached. M0A's exit criteria (§13) are the review's four properties. M0B does not begin until they hold, on real rather than mocked boundaries, and G1 is approved.

---

## 2. MVP Scope

### 2.1 In Scope (M0)

| # | Capability | Milestone | Maps to plan v0.3 |
|---|---|---|---|
| C1 | Deterministic periodic health checks against one Agave validator | M0B | FR-1, FR-3, §5.1 Sentinel |
| C2 | Episode lifecycle with a framework-owned, append-only record, CAS transitions and idempotent appends | M0A | FR-9, §5.7, SR-18 |
| C3 | Hypothesis-driven diagnosis by an LLM role session (read-only tools) | M0B | §5.5, FR-8 |
| C4 | Remediation **recommendation** for a human to execute manually | M0B | §5.1 T1 |
| C5 | Independent `proposal-judge` verdict on every recommendation | M0B | FR-11, SR-12 |
| C6 | Incident report + alert to the operator channel | M0B | FR-9, FR-2 |
| C7 | Deterministic recovery confirmation, episode closure, and a closure report | M0B | FR-7, FR-15, §5.6 |
| C8 | Containment: authenticated capability boundaries, immutable policy bundles, OS sandbox, anchored hash-chained audit | **M0A** | SR-10, SR-11, SR-13, SR-14, SR-15, SR-16 |
| C9 | Consensus-mode determination: declared mode cross-checked against three observed inputs (four in total) | M0B | FR-8, §5.10 |
| **C10** | **Telemetry-health monitoring and its own episode class** | M0B | FR-13, §5.9 |
| **C11** | **Artefact validation after every role step** | M0B | FR-12, §5.8 |
| **C13** | **Multi-provider serving (v0.5):** model broker [12]; adapter framework; Claude reference adapter; Codex and Antigravity runtime adapters where admitted; native API adapter for all three | M0A (broker, framework, Claude); provider track (others) | Plan §5.12 |
| **C12** | **Evaluation support:** FC-1 … FC-5 injection scripts with a ground-truth log; rubric capture (FB-1 … FB-6) linked to episode ids; watchtower baseline campaign; frozen fixture sets and the evaluation harness | M0B | Plan §2.6, §8.1 |

### 2.2 Out of Scope (M0) — deferred to M1+

| Deferred | Target milestone | Reason |
|---|---|---|
| Any T2 execution (restart, upgrade) | M1 | M0 ships no write path to the validator [A] |
| Executor process, approval service, signed approval tokens | M1 | Only needed once T2 exists; `executor/` is absent from the M0 artefact |
| Configuration repository and deploy-by-commit | M1 | Same |
| Post-action verification (as opposed to recovery confirmation) | M1 | No actions in M0 |
| Mainnet-beta deployment | M2 | M0 runs on one testnet validator only (D3). The Phase-4 cluster is D18 |
| Multi-validator fleet orchestration | Later | Plan §2.3 |
| Multi-validator shadow observation | Phase 4 at the earliest | **Excluded from M0.** D13 is decided no earlier than Phase 4 |
| Clients other than Agave | Phase 4 at the earliest | **Excluded from M0** regardless of D2 |
| Publication of operator-trust metrics | Phase 4 at the earliest | **Excluded from M0** (D17) |
| Offline tuning loop | Research track | **Excluded from M0.** Plan §11, D10 |
| Any withdrawer-key or stake operation | Never | Plan §2.3 [E] S4 |

### 2.3 MVP Anti-Goals (enforced, not merely stated)

All plan §2.4 anti-patterns apply. Four are enforced structurally in M0 [A]:

1. **No write path exists.** The command table contains only read-only commands, and the loader refuses a table containing any state-changing token. A T2 tool cannot be "accidentally enabled" by configuration: it requires a code change, a new policy bundle, and review.
2. **The agent cannot close an episode.** Closure is computed by the verifier from re-sampled signals, and the operation does not exist on the agent-facing store endpoint (§5.3).
3. **No component asserts its own identity.** Principals derive from the transport (§5.3). A request field naming the caller is ignored if present.
4. **No in-process check is treated as a boundary.** Everything the `PreToolUse` hook checks is re-checked by the broker that serves the call (§6.3). The same holds for Codex approval policies and Antigravity allow-rules (§6.5).
5. **No provider credential in any worker (v0.5).** Keys exist only in the model broker; cached logins are never mounted into a worker (§5.12, PC-4).

### 2.4 The Availability Claim, Restated (V1 F6)

v0.1 said M0's availability risk was "zero" because no state-changing command exists. **That claim is withdrawn.** A read-only path still consumes CPU, memory, disk I/O, file descriptors, process slots, and local RPC capacity on the validator host.

What M0 guarantees [A]: **no intentional validator state-change path.**

How the residual risk is bounded [A]:

| Residual risk | Bound | Where |
|---|---|---|
| CPU / memory / tasks / file descriptors | systemd unit limits and cgroup constraints on the observer daemon | §5.11 |
| Local RPC load (`solana catchup --our-localhost 8899` and peers consume validator RPC) | Per-command rate limits; concurrency of one per command; circuit breaker that suspends polling and opens a telemetry-health episode when local RPC latency degrades | §5.11, §5.9 |
| Disk I/O from log reads | Bounded tail sizes, output caps, no full-log scans | §5.11 OD-4 |
| Retry storms | A timeout is a reported outcome, never an automatic retry | §5.11 OD-7 |

All limit values are in the parameter register: P-13, P-14, P-16 (plan §13.2). Observation impact is target Q-7.

---

## 3. Target Deployment (M0)

```
Cluster:    testnet (D3 — dedicated project-operated validator)
Validator:  1 × Agave validator, systemd, user `sol`               [E] S4
Ops host:   1 × separate small Linux host (no keypairs present)    [E] S2 rationale; [A] applied to agent
Transport:  UDS + kernel peer credentials on the ops host (D16);
            mTLS only for ops host ↔ validator host                [A]
Watchtower: agave-watchtower on the ops host or a third host,
            alerting on the same D5 channel (the baseline, AW-1)   [E] S2
Anchor:     external append-only storage, off the ops host (D15)   [A]
Providers:  Anthropic, OpenAI, Google — reached ONLY via the model
            broker on the ops host; keys in broker-only storage     [A] (v0.5)
Operator:   1 NAMED on-call operator + 1 named backup (plan §2.6);
            receives alerts and reports on the D5 channel           [A]
Injector:   fault injector / adjudicator, not the operator (plan §7.1)
```

Environment readiness items ER-1 … ER-13 (plan §7.1) must be signed off before the work items that need them.

---

## 4. Architecture

### 4.1 Component View

```
┌──────────────────────────────── OPS HOST ─────────────────────────────────────────────────┐
│                                                                                            │
│  [1] Sentinel (deterministic)        [10] Telemetry checks                                 │
│        │ open / update signal              │                                               │
│        ▼                                   ▼                                               │
│  ┌── [2] CONTROLLER (trusted) ───────────────────────────────────────────────────────┐    │
│  │   episode runner · CAS transitions · artefact validation · capability-token mint   │    │
│  │   holds NO provider key. Retains only CAP_SETUID/CAP_SETGID to spawn workers (N-14)│    │
│  └───────────────┬───────────────────────────────────────────────────────────────────┘    │
│                  │ fork/exec per step in bwrap sandbox under worker uid (N-14)             │
│  ┌── [7] WORKER (untrusted, OS sandbox) ─────────────────────────────────────────────┐    │
│  │   ONE adapter (Claude SDK │ codex exec │ agy -p │ native) · ONE role · ONE episode │    │
│  │   diagnostician │ change-planner │ proposal-judge │ reporter                       │    │
│  │   MCP "valops" = RPC stubs over broker sockets. No provider credential; no fs write│    │
│  │   provider extras (hooks, approvals, allow-rules) — DEFENCE IN DEPTH ONLY (§6.3)   │    │
│  └───────────────┬───────────────────────────────────────────────────────────────────┘    │
│                  │ UDS (worker connects to bind-mounted sockets; SO_PEERCRED at connect, N-3)
│  ┌── CAPABILITY BROKERS ─────────────────────────────────────────────────────────────┐    │
│  │  [3] episode-broker  ──► store-agent (agent.sock)                                  │    │
│  │  [9b] observer-broker ─► validator host (mTLS) + store-observe (observe.sock, N-1) │    │
│  │  [8] report-broker   ──► store-agent-report (agent-report.sock, N-2) + alert sink  │    │
│  │  [5] audit-sequencer ──► SOLE writer of chain; signs + anchors heads (fsync)      │    │
│  │  [12] model-broker   ──► SOLE provider-key holder; worker's ONLY egress (§5.12)    │    │
│  │          └─► Anthropic │ OpenAI │ Google — per bound configuration only            │    │
│  │  [3s] EPISODE STORE (5 endpoints: control, verify, agent, agent-report, observe)   │    │
│  └────────────────────────────────────────────────────────────────────────────────────┘    │
│                                                                                            │
│  [4] Policy bundles (immutable, hash-addressed, read-only to all) · active · revoked       │
│  [6] Verifier (deterministic) ── the ONLY writer of verifications and of `resolved`        │
│                                                                                            │
│            │ HTTPS + mTLS, command-id allowlist            ▲ signed chain checkpoints      │
└────────────┼──────────────────────────────────────────────┼────────────────────────────────┘
             ▼                                              │            ┌──────────────────┐
┌──────────────────── VALIDATOR HOST ──────────────────────┐│            │ [11] EXTERNAL    │
│  [9] Observer Daemon (user `valops`, non-root, no keys)   ├┘            │  ANCHOR (WORM /  │
│      read-only command table · typed args · output caps   │─────────────▶  remote log, D15)│
│      rate limits · concurrency 1 · systemd/cgroup limits  │             └──────────────────┘
│      local hash chain → forwards signed checkpoints        │
│  agave-validator (user `sol`, systemd)             [E] S4 │
│  (no Executor in M0 — §0.1)                                │
└────────────────────────────────────────────────────────────┘
```

### 4.2 Trust Boundaries

| Boundary | Crossed by | Control |
|---|---|---|
| LLM ↔ everything | MCP tool calls, which are RPC stubs | Broker-side enforcement using the authenticated principal; `PreToolUse` deny is a fast-fail layer in front of it, not the control |
| Worker ↔ ops host filesystem/network | syscalls | OS sandbox (D11) with a minimal read-only root filesystem: no filesystem writes; egress only to the model broker loopback and bind-mounted broker UDS sockets (N-3) |
| **Worker ↔ model providers** (v0.5) | model API requests | Model broker [12]: principal from the per-worker socket; provider and model fixed by the bound configuration; limits; key injected server-side; transcript to the audit chain |
| Worker ↔ controller authority | capability token | Token scoped to (episode, role, session, bundle, expiry, nonce); minted by the controller; verified by every broker |
| Ops host ↔ validator host | mTLS HTTPS | Command-id allowlist; the daemon accepts an enum, never a shell string (DD-3) |
| Anyone ↔ policy | file writes | Immutable hash-addressed bundles, read-only to every process; an episode is served from its bound bundle |
| Audit writers ↔ audit chain | sequencer socket | Single writer; `actor` stamped server-side from the authenticated principal; heads anchored off-host |
| Validator output ↔ LLM context | tool results | Structured, size-capped, redacted; treated as untrusted data (SR-6) |

### 4.3 Process Classes and Compromise Analysis (new in v0.3, V1 F3)

| Process | Runs as | Credentials held | A full compromise yields |
|---|---|---|---|
| **Worker** | dedicated uid, sandboxed | One capability token: one episode, one role, one session, short expiry | Exactly that role's tool surface, for that one episode, until expiry, **whichever adapter it runs**. No provider credential; no policy write; no state transition; no verification; no audit authorship; validator access only through the observer broker's allowlist, rate limits and output caps |
| **Controller** | dedicated uid | Token-minting key; store control endpoint. **No provider key** (v0.5) | Full control-plane authority. Mitigation: runs no model output; parses structured broker responses and the episode record, never transcript prose (§5.8). Unit drops all capabilities except `CAP_SETUID` and `CAP_SETGID` to spawn worker processes under dedicated worker uid (N-14) |
| **episode-broker** | dedicated uid | Store agent endpoint (`agent.sock`; N-2) | Ability to append agent artefacts to episodes. Still no state transition, verification or closure — those operations exist only on other endpoints |
| **observer-broker** | dedicated uid | mTLS client certificate for the daemon; store observe endpoint (`observe.sock`; N-1) | Read-only validator observation at the daemon's rate limits, and appending verified re-samples as citable signals |
| **report-broker** | dedicated uid | Alert channel credential; store agent-report endpoint (`agent-report.sock`; N-2) | Ability to send alerts (metadata filled from verified record, N-8) and append incident reports. Alert-rate anomalies are monitored |
| **model-broker** (v0.5) | dedicated uid | Anthropic, OpenAI and Google API keys | Spending on allowlisted models up to per-session limits. No validator, store or policy access |
| **audit-sequencer** | dedicated uid | Chain file; chain-head signing key | Ability to write the local chain. External anchoring (§5.5) bounds silent rewriting to the interval since the last anchor |
| **Observer daemon** | `valops` on the validator host | Read-only command table; local chain key | Read-only observation under OS resource limits. No state-changing command exists to invoke |

**Why the hook is not a boundary [A].** The `PreToolUse` policy gate runs inside the worker — the one process that hosts model output and is therefore the one process assumed to be compromisable by a sufficiently effective prompt injection or an SDK defect. Anything it enforces, an attacker who controls that process can bypass. It is retained for three reasons that do not require trusting it: it fails fast and cheaply, it gives the model a specific denial reason so behaviour stays legible, and it produces a first-line audit record. Every check it makes is repeated by the broker.

### 4.4 Key Design Decisions

| ID | Decision | Rationale | Tag |
|---|---|---|---|
| DD-1 | The **Episode Store is the source of truth**, not any model context | No single context spans an episode; survives restarts and long waits (NFR-4) | [A]; motivation [H] |
| DD-2 | **One fresh agent session per step** (any adapter), not one session with subagents; `Task` disallowed | Guarantees the Judge's context isolation (SR-12), which subagent inheritance rules do not | [A]; SDK subagent inheritance [E] S7 |
| DD-3 | The observer daemon takes a **command id**, not a command string | Removes shell injection and argument smuggling as a class | [A] |
| DD-4 | Closure is computed, never asserted by the model | Prevents self-grading (plan §2.4) | [A]; pattern [E] R2 |
| DD-5 | M0 ships **no state-changing command at all** | The availability risk of the MVP is bounded structurally rather than by policy — but it is not zero (§2.4) | [A] |
| DD-6 | `permission_mode="dontAsk"` with role-scoped allowlists | Anything not pre-approved is denied; `canUseTool` is never invoked in this mode, so no control may depend on it | [E] S7 |
| DD-7 | Reference implementation language: **Python** (`claude-agent-sdk`), the **D1 default** (plan §13.1), adopted at G0 unless D1 closes otherwise | Concrete interfaces are required for an HLD. In v0.3 the language choice matters less than it did: start/end and artefact-validation work lives in the controller, not in hooks (§6.2) | [A], pending D1 |
| **DD-8** | **Principals derive from the transport; the agent endpoint lacks closure capability entirely** | An authorization check can be misconfigured; a missing operation cannot | [A], V1 F1 |
| **DD-9** | **One audit sequencer, externally anchored** | Multiple writers race on `seq`/`prev`; a local-only chain can be recomputed wholesale by whoever can rewrite the file | [A], V1 F2 |
| **DD-10** | **Immutable bundles bound per episode**, rather than re-checking "the current mount" | Otherwise any legitimate policy deployment strands every in-flight episode | [A], V1 F8 |
| **DD-11** | **The verifier may set `resolved` only from `awaiting_operator`** | Otherwise a transient recovery races the runner and closes an episode mid-analysis | [A], V1 F5 |
| **DD-12** | **Loss of observability is an incident, not a silence** | "No data" must never read as "healthy" | [A], V1 F6 |
| **DD-13** | **Provider-neutral boundary** (v0.5): credentials, limits and transcripts live in the model broker; runtimes are admitted by conformance; provider-specific controls are defence in depth only | Three runtimes with different, partly undocumented, controls cannot all be trusted in-process. They do not need to be | [A], owner requirement |

---

## 5. Component Specifications

### 5.1 [1] Sentinel

Deterministic scheduler. Contains no LLM call.

| Property | Value |
|---|---|
| Trigger | Fixed interval per check (values in the bound bundle's `thresholds.yaml`, generated from the parameter register: P-01 … P-04, P-15) |
| Inputs | Observer broker read-only commands; `agave-watchtower` notifications; telemetry probes (§5.9) |
| Outputs | `open_episode` / `append_signal` on the store control endpoint |
| Rules | Pure functions over signals → severity class; no model involvement |

**Validator-health checks (M0)**

| Check | Signal source | Basis |
|---|---|---|
| Delinquency | slot distance trend over P-03 consecutive samples (`catchup`) | [E] S2, S5 (N-15) |
| Catch-up progress (slot distance trend) | `solana catchup --our-localhost 8899` | [E] S5 |
| Identity account balance below floor | `solana balance <identity pubkey>` | [E] S3 |
| Process/unit state | systemd unit status | [A] |
| Disk headroom on ledger and accounts volumes | filesystem stats | [A] |
| Running version drift vs. expected | log line `Starting validator with` | [E] S3 |
| Own leader slots approaching | `solana leader-schedule` filtered to own identity | [E] S3 |
| Consensus-mode inputs | version, cluster feature state, state files — see §5.10 | [E] S5 for the files |

**Telemetry-health checks (M0, new in v0.3)** — see §5.9.

**Watchtower baseline integration [A].** The sentinel checks the heartbeat file `watchtower_heartbeat` in M0; ingesting live watchtower notifications as triggers is deferred to M0B run-in.

**De-duplication [A].** One open episode per (episode class, check class, validator). A repeat signal updates the open episode instead of opening a new one. Enforced in the store under an index lock, not in a prompt, so neither a sentinel race nor an agent can manufacture episode churn.

### 5.2 [2] Controller (Episode Runner)

Deterministic state machine. Owns which step runs, with what inputs, under which budget, and whether its output counted.

```
open ──► diagnosing ──► recommending ──► judging ──┬─► reporting ──► awaiting_operator
             │               ▲                     │ PASS                   │
             │               └──── FAIL (retry ≤ N)┤                        │ verifier re-samples
             │                                     ▼ FAIL (retry > N)       │ (stability window W)
             │                                handed_off + alert (N-4)      ▼
             └──────────────────────────────► reporting                 resolved ──► closure report
                         (recovery observed during diagnosis)
     any non-terminal ──► handed_off  (failure · budget · integrity · missing artefact)
```

| Rule | Detail | Tag |
|---|---|---|
| R-1 | Every step is a new agent session, whichever adapter; no `resume`, no `continue_conversation`, no `fork_session`, no subagents | [A] |
| R-2 | Step input is assembled by the controller from the episode record — the model never chooses its own context | [A] |
| R-3 | Judge FAIL returns to `recommending`, at most **N** times (N = P-09); on exhaustion → `handed_off` + alert with every FAIL reason (reconciles §7.2; N-4) | [A] |
| R-4 | Any exception, budget exhaustion, integrity failure, or missing artefact → `handed_off` + alert. Never a silent stop | NFR-2 [A] |
| R-5 | Per-session `max_turns` and `max_budget_usd` set from the bound bundle | [E] S9 for the options |
| R-6 | The controller records `cost.per_role_usd` and `turns` per step **from the model broker's meter** (§5.12), so cost is comparable across providers. For the Claude adapter the SDK result is a cross-check | [A]; [E] S9 |
| **R-7** | **Every transition is a compare-and-swap on `revision`.** A transition computed from a stale revision is refused; the controller re-reads and re-decides | [A], V1 F5 |
| **R-8** | **No transition without a validated artefact** (§5.8) | [A], V1 F9 |
| **R-9** | The controller reads the episode record, never the transcript. Transcript text is retained for audit and human review and is parsed by nothing | [A], V1 F9 |
| **R-10** | The controller mints one capability token per step and revokes it when the step ends | [A], V1 F1 |
| **R-11** | **Per-role quotas (N-16):** episode-broker writes ≤ 4 × P-05; hook tool calls ≤ 3 × P-05; observer tools ≤ P-14 per session | [A] |
| **R-12** | **Worker spawn privileges (N-14):** controller unit retains only `CAP_SETUID` and `CAP_SETGID` to spawn worker processes under the dedicated worker uid | [A] |

### 5.3 [3] Episode Store — Five Endpoints (revised in v0.5, N-1, N-2)

The store is one service exposing five endpoints (implemented via separate Unix domain sockets to enforce transport authentication per broker, DD-8, N-1, N-2). They differ in **which operations exist**, not only in what they permit. The principal is derived from the endpoint the call arrived on (a UDS with OS-enforced ownership and peer credentials, or an mTLS identity — D16) together with the capability token presented. **No request field names the caller; one is ignored if supplied.**

```
store-agent         (worker, via episode-broker; requires capability token)
  append_hypothesis(episode_id, {rank, claim, test, expected_evidence}, idem_key) -> hypothesis_id
                                       # step_session is stamped by the store from the token
  append_hypothesis_status(episode_id, h_id, status, evidence_refs, idem_key)
  append_recommendation(episode_id, {...}, idem_key)                          -> recommendation_id
  append_no_action(episode_id, {reason, evidence_refs}, idem_key)
  append_verdict(episode_id, {recommendation_id, result, checks}, idem_key)
  read_episode(episode_id, view)       # view is forced by role; judge gets judge view
  # NO set_state. NO append_verification. NO append_report. NO closure.

store-agent-report  (worker, via report-broker; requires capability token; N-2)
  append_report(episode_id, kind, markdown_ref, idem_key)                     -> report_ref
  read_episode(episode_id, view)
  # Exposes ONLY report appending and reading; no hypothesis, recommendation or state ops.

store-control       (controller only; reachable solely by the controller's uid)
  open_episode(trigger, bundle_id, consensus_mode, idem_key)                  -> episode_id
  set_state(episode_id, state, expected_revision)     # every state EXCEPT resolved
  append_signal(episode_id, snapshot, idem_key)
  append_cost(episode_id, role, usd, turns, session_id, configuration, tokens, idem_key)
  append_step(episode_id, step_record, idem_key)
  annotate(episode_id, note, idem_key)
  read_episode(episode_id, view)
  list_episodes(filter)

store-verify        (verifier only; reachable solely by the verifier's uid)
  append_verification(episode_id, {rule, result, samples}, idem_key)
  append_recovery_observation(episode_id, {rule, note}, idem_key)
  set_state(episode_id, "resolved", expected_revision)   # only from awaiting_operator
  read_episode(episode_id, view)
  list_episodes(filter)

store-observe       (observer-broker only; reachable solely by observer-broker uid; N-1)
  append_observation(episode_id, observation, idem_key)                       -> signal_id
  # A tool-driven re-sample becomes a citable signal. The content comes from
  # the daemon via the observer-broker, never from the untrusted worker.
```

**Invariants [A]**

- No update, no delete. Corrections are new entries. The record of HLD §7.1 is a fold over an append-only log.
- Closure and verification are absent from the agent endpoints (`store-agent`, `store-agent-report`). There is no permission check to misconfigure.
- Terminal episodes accept only reports (closure), recovery observations (§7.3 post-hand-off monitoring) and the controller's bookkeeping (cost, step, annotation); no state transition and no other write (N-9).
- Every write records the authenticated principal, the session id, the bound bundle id, and an audit-chain reference.
- Every write carries an **idempotency key**. A repeated key returns the original result and appends nothing, so a retry after a timeout cannot inflate an episode.
- Every state transition is a **compare-and-swap** on `revision` (R-7).
- `read_episode(view="judge")` returns raw signals, the recommendation or no-action record under judgement, skill preconditions, and deterministic `verifications` and `recovery_observations` (N-6) — never hypothesis prose, planner rationale, prior verdicts, or reports (SR-12).
- **Deterministic mode enforcement (N-7):** The store rejects `append_recommendation` if the proposal cites a mode-specific skill while the episode consensus mode is `unknown` or mismatched, providing a deterministic layer in front of the model Judge.
- **Contract checks are server-side:** a hypothesis without a non-empty `test` is rejected; a hypothesis whose `rank` duplicates one already written in the same `step_session` is rejected, and the controller's artefact validation (§5.8) requires ranks 1…k with no gaps; an evidence reference naming a signal that was never collected is rejected; a verdict without a non-empty check list is rejected.

**The evidence-reference bridge [A].** Because the Judge never sees the diagnostician's prose, the only link from diagnosis to judgement is a recommendation's `evidence_refs`, which name signals collected in this episode. The store validates them. A fabricated justification is therefore a rejected write rather than something the Judge has to catch.

### 5.4 [4] Policy Bundles (revised in v0.3, V1 F8)

Read-only to every process. Immutable and addressed by the hash of their contents.

```
bundles/
├── <bundle-id = sha256 of contents>/
│   ├── command_table.yaml          # observer allowlist — read-only commands only
│   ├── thresholds.yaml             # generated from the parameter register (plan §13.2)
│   ├── deployment.yaml             # declared consensus mode, client, ledger/log paths (§5.10)
│   ├── prompts/{diagnostician,change_planner,proposal_judge,reporter}.md
│   ├── skills/<skill>/SKILL.md     # or inlined into prompts — §6.2 fallback
│   ├── verifier/<signal>.yaml      # declarative predicate + stability window
│   ├── judge_checklist.yaml
│   └── MANIFEST.sha256 (+ MANIFEST.sha256.sig)
├── active                          # pointer: the bundle NEW episodes bind to
└── revoked                         # ids that must stop being used immediately
```

| Operation | Behaviour | Tag |
|---|---|---|
| Binding | An episode records its bundle id at open and is served from that bundle until it terminates. Capability tokens carry the same id | [A] |
| Integrity check | At process start, at `open_episode`, and at every broker call — against **the episode's bound id**, never "whatever is mounted now" | [A] |
| Activation | Change the `active` pointer. In-flight episodes are untouched | [A] |
| Drain | A deadline (P-12) bounds how long old bundles stay live. Episodes exceeding it → `handed_off` + alert | [A] |
| Migration | None. An episode never changes bundle mid-flight; a half-old, half-new policy is the exact state this design exists to prevent | [A] |
| Emergency revocation | Add the id to `revoked`. Episodes bound to it → `handed_off` + high-severity alert; outstanding tokens for it are refused at every broker | [A] |
| Rollback | Re-point `active` at the previous id. Exact, because bundles are immutable and content-addressed | [A] |
| Failure mode | Any verification failure ⇒ **observe-only**: sentinel, store and verifier keep running; no LLM step starts; high-severity alert naming the changed path; audit entry | [A] |

The manifest is signed and the public key lives outside the bundle store. Key custody and rotation follow D14 (plan §13.1; default: offline hardware-token key with a sealed backup).

### 5.5 [5] Audit Sequencer (revised in v0.3, V1 F2)

**One process writes the ops-host chain.** Everything else submits records to it over a socket and receives the assigned sequence number and entry hash.

| Property | Design |
|---|---|
| Format | Append-only JSON Lines, hash-chained: `entry.prev = SHA256(previous entry canonical form)` |
| Serialisation | Single writer; no cross-process race on `seq` or `prev` |
| Identity | `actor` is stamped by the sequencer from the authenticated principal of the submitting connection. A submitter cannot label its own entry, so a compromised worker cannot forge a controller-attributed record |
| Durability | Each entry is fsynced before acknowledgement |
| Payloads | Content-addressed and hashed by the sequencer; the chain carries `payload_ref`, never the blob |
| **External anchoring** | Every P-18 minutes, signs `{chain_head, seq, ts}` and writes it to append-only external storage (D15 default: object storage with compliance-mode retention lock in an account the ops host cannot administer, written with a put-only credential). Rewriting local history then also requires rewriting anchors the ops host cannot modify |
| **Maximum anchor lag (v0.4)** | Lag above P-18 raises an alert. Lag above P-19 means the promised tamper-evidence bound no longer holds: the controller starts **no new LLM step** (sentinel-and-alert tier) until a fresh anchor is confirmed. Sentinel, store and verifier continue |
| **Validator-host chain** | The observer daemon maintains its own local chain and forwards signed checkpoints; the sequencer records the daemon's head, making truncation of the daemon's chain detectable from the ops host |
| Verification | `verify_chain` walks links and compares the head against the newest anchor. Run on a timer and in CI |

| Field | Meaning |
|---|---|
| `seq`, `ts`, `prev` | chain position, timestamp, previous entry hash |
| `actor` | **server-stamped** principal: kind + role + session id |
| `event` | `tool_call`, `tool_result`, `tool_denied`, `state_change`, `integrity_fail`, `alert`, `observe_*`, `verification`, `anchor` |
| `episode_id` | episode this entry belongs to, when applicable |
| `payload_ref` | pointer to the capped payload; large outputs by reference, never inline |

**Stated limitation [A].** Anchoring bounds how much history can be silently rewritten to the interval since the last anchor. It does not make the local file immutable, and it does not defend against an attacker who controls both the ops host and the anchor store. Anchor lag is a published metric (plan §9).

### 5.6 [6] Verifier (Recovery Confirmation)

Deterministic. Runs on a timer for the life of an episode.

| Aspect | Detail |
|---|---|
| Inputs | Re-sampled signals from the observer broker; declarative rules from the episode's bound bundle |
| Rule form | A per-signal predicate (`lt`/`le`/`gt`/`ge`/`eq`/`in`, composed with `all_of`/`any_of`) plus a **stability window**: e.g. "not delinquent **and** catch-up distance below threshold for W consecutive samples". W and the escalation deadline are P-17; thresholds come from the register. Rules are data, evaluated by code — never a string expression and never a model judgement |
| Commands | `agave-validator monitor` and `solana catchup --our-localhost 8899` [E] S5 |
| Output | Immutable verification record; `set_state(resolved)` on success |
| **Timing constraint (DD-11)** | The verifier may set `resolved` **only from `awaiting_operator`**. If the recovery predicate holds earlier, it appends a `recovery_observation` and changes nothing (§7.3) |
| Deadline | If the predicate never holds within the owner-set window, the state stays `awaiting_operator` and the alert escalates. The verifier does not hand off on its own |
| Constraint | The only component permitted to set `resolved` (DD-4), on an endpoint no other principal can reach |

### 5.7 [7] Role Sessions

| Role | Tools | Input view | Required artefact |
|---|---|---|---|
| `diagnostician` | T0 read tools + `add_hypothesis`, `set_hypothesis_status` | Full episode record | ≥1 hypothesis, each with claim, test, expected evidence and a rank (1…k, no gaps) |
| `change-planner` | T0 read tools + `propose_recommendation`, `report_no_action` | Episode record incl. hypotheses | Exactly one recommendation bound to one hypothesis, **or** one explicit no-action record with a reason |
| `proposal-judge` | T0 read tools + `submit_verdict` | **Judge view only** (§5.3) | One verdict: PASS/FAIL with a non-empty list of checks performed |
| `reporter` | `write_incident_report`, `send_alert`, `get_verification_result` | Episode record incl. verification records | One report reference and one dispatched alert |

**Hypothesis contract [A].** Accepted only with all three of `claim`, `test` (an observation that could refute it) and `expected_evidence`. A claim with no refuting test is rejected at the API, which forces falsifiable diagnosis rather than narrative.

**Recommendation contract [A].** Must name: the action in operator terms, the runbook skill it came from, the preconditions to verify before acting, the expected post-condition, the hypothesis it addresses, and **evidence references to signals actually collected in this episode**. In M0 the action is text for a human; the system contains no code that performs it.

**No-action is a first-class artefact [A], new in v0.3.** "Nothing should be done" is a legitimate planner conclusion, and before v0.3 it was indistinguishable from a failed session. It is now recorded explicitly, with a reason and evidence, and routes the episode to `judging` (evaluated against checklist item `no_action_justified`), matching the normative transition table (N-5).

**Reporter alert generation (N-8).** The report broker populates severity, fault class, top hypothesis, recommendation, verdict and report link directly from the verified episode record; the model supplies only a labelled summary. Even a persuaded or hallucinating reporter model cannot misstate the diagnosis, recommendation or verdict in an operator alert.

**Skill `draft_failover_runbook` (N-13).** Returns the bound bundle's failover checklist section for the confirmed consensus mode only; it is withheld under `unknown`.

### 5.8 [2] Artefact Validation (new in v0.3, V1 F9)

A session that ends without writing its artefact has failed, however confident its prose. After every step the controller [A]:

1. Reads the episode record from the store — **not the transcript** — and checks that the role's required artefact exists, was written during this step (matched by session id), and satisfies its schema.
2. Cross-checks the session's structured output where the SDK supplies one (`output_format`). Disagreement between structured output and the stored artefact is a step failure, and **the stored artefact is authoritative**: it is the one that passed the server-side contract checks.
3. On a missing or invalid artefact: counts a step failure and retries with a fresh session within the retry budget (P-08); on exhaustion, `handed_off` with an alert naming what was missing.
4. Never parses prose to recover an artefact.

| Role | Validated | Failure |
|---|---|---|
| diagnostician | ≥1 hypothesis with all three contract fields; ranks 1…k with no gaps in this step | retry, then `handed_off` |
| change-planner | exactly one recommendation, or one no-action record | retry, then `handed_off` |
| proposal-judge | one verdict with non-empty checks | retry, then `handed_off` (never a default PASS) |
| reporter | report ref present and alert dispatch acknowledged | retry, then `handed_off` |

A Judge step that fails validation is never treated as PASS. Absence of a verdict is not consent.

### 5.9 [10] Telemetry Health (new in v0.3, V1 F6)

v0.1 alerted on an unreachable observer daemon but explicitly opened no episode "on missing data alone". That leaves the system's most dangerous state — it cannot see the validator — as the only condition with no incident record.

| Probe | Signal |
|---|---|
| Observer reachability | connection success, mTLS handshake result |
| Observer latency | per-command response time distribution |
| Command error / timeout rate | per command id |
| Sample staleness | age of the newest successful sample per check |
| Watchtower liveness | last notification or heartbeat age |
| Local RPC latency | response time of the validator's own RPC as seen by the daemon |

| Rule | Detail | Tag |
|---|---|---|
| TH-1 | Breaching an owner-set threshold opens an episode of class `telemetry_health`, diagnosed and reported like any other | [A] |
| TH-2 | Missing data **never** opens, escalates, de-escalates, or resolves a `validator_health` episode | [A] |
| TH-3 | A validator-health episode whose signals have gone stale is annotated as such; its verifier cannot confirm recovery from stale samples, so it stays `awaiting_operator` and escalates | [A] |
| TH-4 | The local-RPC circuit breaker suspends polling when RPC latency degrades, and that suspension is itself a telemetry-health signal — the system does not go quiet to protect itself without saying so | [A] |

### 5.10 Consensus-Mode Determination (revised in v0.3, V1 F7)

File presence alone is ambiguous: both `tower-*.bin` and `vote_history-<IDENTITY>.bin` can exist after a migration, a rollback, or incomplete cleanup. Mode is therefore established by agreement, not by inference from one input [A]: the **declared mode cross-checked against three observed inputs — four inputs in total**. (v0.3 also called this "three-way" in places, counting only the observed inputs; v0.4 uses this one wording in both documents.)

| Input | Source | Tag |
|---|---|---|
| Declared mode in the bundle's `deployment.yaml` | Owner-set, reviewed, hashed | [A] |
| Running Agave version and its support for the mode | `running_version` [E] S3 | [E]/[A] |
| Cluster feature state for the consensus feature | On-cluster query; the exact query is **[U]** (D9). Until it is verified the input is `unavailable`, which counts as disagreement | [U] |
| Consensus state files present, with modification times | `consensus_state_files` [E] S5 | [E] |

Rules [A]: all inputs agreeing sets the mode. **Any disagreement sets `unknown`**, records every input in `consensus_mode_evidence`, raises an alert, and prohibits mode-specific recommendations — the planner is offered no mode-specific skill variant, and the Judge FAILs any proposal carrying a mode-specific precondition. `unknown` does not stop observation, diagnosis, or reporting; it stops only claims that depend on the mode. The store also enforces this deterministically by rejecting mode-specific recommendations when the mode is `unknown` or mismatched (N-7).

### 5.11 [9] Observer Daemon (validator host)

```
POST /observe   { command_id, args: {...}, request_id }
                → { status, structured, truncated, collected_at, audit_ref }
```

| Rule | Detail | Tag |
|---|---|---|
| OD-1 | `command_id` is an enum defined in the bound bundle's `command_table.yaml`. An unknown id is rejected before any process spawn | [A] |
| OD-2 | Arguments are typed and validated per command (`pubkey` must match base58 and an expected length; `lines` must be an integer within a bound). argv is assembled from the table with placeholders filled from validated arguments and daemon-local configuration, and executed without a shell | [A] |
| OD-3 | Every command is read-only in M0. The table loader **refuses to start** if any entry is not marked read-only or contains a state-changing or shell-metacharacter token | [A], DD-5 |
| OD-4 | Output is capped, structured where parseable, and redacted (paths, any key-like token) before return. Suspicious-instruction patterns are flagged, not obeyed | [A] |
| OD-5 | Per-command rate limits and **concurrency of one**; a breach returns an error and writes an audit entry | [A] |
| OD-6 | Runs as non-root `valops`; the validator's keypair files are not readable by this user | [E] S4 for non-root; [A] for the separate user |
| OD-7 | Timeout per command; a timeout is a normal, reported outcome, never a retry storm | [A] |
| **OD-8** | **Resource containment (SR-17):** the systemd unit sets `CPUQuota`, `MemoryMax`, `TasksMax`, `LimitNOFILE`, IO weight and `Nice`, and runs under a dedicated cgroup slice. Values: P-13 (plan §13.2) | [A], V1 F6 |
| **OD-9** | **Local-RPC circuit breaker:** when the validator's own RPC latency exceeds the owner's threshold, polling of RPC-backed commands is suspended and a telemetry-health signal is raised (§5.9 TH-4) | [A], V1 F6 |
| **OD-10** | **Local audit chain:** the daemon maintains its own hash chain of requests served and forwards signed checkpoints to the ops-host sequencer (§5.5) | [A], V1 F2 |

Hardening intent for the unit file [A]: `NoNewPrivileges`, `ProtectSystem=strict`, `ProtectHome`, `PrivateTmp`, `PrivateDevices`, a read-only bundle mount, and a `ReadOnlyPaths` entry for the ledger and log directories. Exact directives are a W2 deliverable.

### 5.12 [12] Model Broker (new in v0.5)

The design rationale, the provider matrix and the conformance profile are in plan §5.12. This section specifies the interface.

```
worker side (inside the worker's network namespace — its ONLY route):
  http://127.0.0.1:<port>/<provider>/...   provider-native wire format, incl. streaming
       │  loopback bridged to a per-worker UDS created by the controller at spawn
       ▼
model-broker, per request:
  1. principal   = the per-worker socket the request arrived on → (episode, role, session,
                   bound configuration). Nothing in the request can change it (SR-14)
  2. route       : <provider> must equal the configuration's provider; else refuse
  3. model       : requested model ID must equal the configuration's pinned model; else refuse
  4. limits      : requests, input tokens, output tokens, USD (P-30, P-31, P-06); else refuse
  5. strip       : every inbound credential header is removed
  6. inject      : the provider key from broker-only secret storage (SR-8)
  7. forward     : TLS to the provider endpoint fixed in the bundle's providers.yaml; no other host
  8. meter       : usage from the provider response → per-session counters → controller cost record.
                   If usage cannot be parsed, session is charged estimated input plus clamped maximum output (N-12).
  9. relay       : provider response is streamed/relayed to the worker (N-11).
 10. audit       : request and response hashed, payloads stored by reference, submitted to the
                   audit sequencer (§5.5) with the server-stamped principal immediately after relay (N-11).
 11. return      : completes connection (or returns a provider-shaped error on refusal).
```

| Rule | Detail | Tag |
|---|---|---|
| MB-1 | One socket per worker, created by the controller at spawn and destroyed at step end. A leaked socket dies with the step | [A] |
| MB-2 | A refusal is a step failure seen by the controller (NFR-2). It is never retried by the broker | [A] |
| MB-3 | Broker unavailable ⇒ **no LLM step starts** (fail closed); sentinel and verifier continue (RB-14) | [A] |
| MB-4 | Provider unreachable ⇒ in-flight step fails ⇒ `handed_off` (RB-1). Fallback applies to *new* episodes, through a pre-approved bundle only, after P-29 (plan §5.12.4) | [A] |
| MB-5 | A provider with no D21 approval on record is unroutable, whatever a bundle says | [A] |
| MB-6 | Transcripts are untrusted text and are never parsed by the control plane (R-9). They exist for audit and adjudication | [A] |
| MB-7 | The Anthropic native binding explicitly does not enable server-side refusal/overload model fallbacks, ensuring strict adherence to the D7 pinned model rule (N-10) | [A] |

---

## 6. Agent Configuration (§6.1–§6.4: reference Claude adapter; §6.5: other adapters)

### 6.1 Session Options — Claude Reference Adapter (Python — D1)

```python
ClaudeAgentOptions(
    setting_sources=[],                                  # no filesystem settings discovery  [E] S9
    # An explicit tools list replaces the built-in set. Per SDK documentation it must itself
    # carry "Skill" for the skills library to remain loadable, and with setting_sources=[]
    # the skills must come from the `skills` field. Both halves are W1 items.  [E] S9 / [U]
    tools=["Skill", *TOOLS_BY_ROLE[role]],
    allowed_tools=TOOLS_BY_ROLE[role],                   # exact names, no globs             [E] S9
    disallowed_tools=["Bash", "Write", "Edit", "NotebookEdit",
                      "WebFetch", "WebSearch", "Task"],  # removed from context; Task also
                                                         # forbids in-session subagents      [E] S7
    mcp_servers={"valops": valops_stub_server(role)},    # RPC stubs over broker sockets     [E] S9
    strict_mcp_config=True,                              #                                   [E] S9
    permission_mode="dontAsk",                           # unapproved ⇒ denied               [E] S7
    hooks={                                              # DEFENCE IN DEPTH ONLY (§6.3)
        "PreToolUse":        [HookMatcher(hooks=[policy_gate]),
                              HookMatcher(hooks=[audit_append])],
        "PostToolUse":        [HookMatcher(hooks=[audit_append_result])],
        "PostToolUseFailure": [HookMatcher(hooks=[audit_append_failure])],
    },
    skills=SKILLS_BY_ROLE[role],                         # from the BOUND bundle   [E] S9 / [U]
    sandbox=SANDBOX_PROFILE,                             # fail-closed intent — §6.2
    system_prompt={"type": "file",
                   "path": f"{bundle_path}/prompts/{role}.md"},  #                  [E] S9
    output_format=ARTEFACT_SCHEMA[role],                 # cross-check only; the store
                                                         # artefact stays authoritative (§5.8)
    max_turns=BUNDLE.max_turns[role],                    # register P-05
    max_budget_usd=BUNDLE.max_budget_usd[role],          # register P-06
    model=BUNDLE.model[role],                            # pinned (D7); W1 verifies this exact pin
    continue_conversation=False, resume=None, fork_session=False,   # enforces R-1
    agents=None, plugins=[],                             # no subagents, no plugins
    env=WORKER_ENV,                                      # NO provider credential (§4.3); base URL → model
                                                         # broker loopback (§5.12). Honoured by the SDK? W1 [U]
)
```

### 6.2 Sandbox Profile and the Skills Dependency (revised in v0.3, V1 F4)

**Sandbox intent [A].** The SDK sandbox is the third of four layers and never the control:

| Setting | Required value | Reason |
|---|---|---|
| enabled | true | — |
| **fail closed when the backend is unavailable** | **required** | Silently running unsandboxed is the failure this setting exists to prevent |
| `allowUnsandboxedCommands` | false | No escape hatch |
| `excludedCommands` | empty | No command is exempt |
| `enableWeakerNestedSandbox` | false | Weaker is not a fallback we accept |
| network | Model broker loopback only (§5.12) | Egress containment |
| unix sockets | broker socket files bind-mounted into `/run/valops/` (N-3) | The worker's sole legitimate IPC; worker connects directly to preserve kernel peer credentials |

**An unresolved discrepancy, recorded rather than papered over [E, X1].** The review cites a `failIfUnavailable` setting. On 2026-09-17 the installed `claude-agent-sdk` 0.2.154 exposed a `SandboxSettings` type with `enabled`, `autoAllowBashIfSandboxed`, `excludedCommands`, `allowUnsandboxedCommands`, `network`, `ignoreViolations` and `enableWeakerNestedSandbox` — and **no `failIfUnavailable` field**. In the implementation, the controller executes an explicit, deterministic bubblewrap preflight check (`valops/controller/preflight.py`) before spawning any worker process. If bubblewrap is unavailable, non-executable, or lacks unprivileged user namespace capability, worker spawn is refused immediately and the episode fails closed. **External OS sandbox enforcement (SR-11) is thus independent of SDK-level sandbox settings.**

**Skills fallback, removing an [U] from the critical path [A].** If W1 shows that a named skills library cannot be loaded reliably with `setting_sources=[]`, the controller falls back to **prompt inlining**: the runbook text for the role's permitted skills is concatenated into the role's system-prompt file inside the bundle, with identical source citations and compatibility matrix. Content, provenance and hash coverage are unchanged; only the delivery mechanism differs. **No requirement in M0 depends on the `skills` field working.**

### 6.3 Policy Gate Hook (`PreToolUse`) — Defence in Depth Only

Runs on every call, inside the worker, before any other permission step. Checks, in order [A]:

1. Tool is in this role's allowlist.
2. Arguments conform to the tool schema and to policy bounds.
3. Rate and quota limits for this role and episode are not exceeded.
4. Episode is in a state where this tool is legal (for example, `submit_verdict` only in `judging`).
5. The bound bundle id still verifies.

Any failure returns `permissionDecision: "deny"` with a reason and writes an audit entry.

**Every one of these five checks is repeated by the broker that serves the call**, using the principal authenticated from the transport and the capability token rather than anything the worker asserts (§4.3). The hook exists to fail fast, to give the model a legible denial reason, and to leave a first-line audit record. **It is not a trust boundary, and no security property in this document depends on it.**

### 6.4 Prompt-Injection Handling (SR-6)

| Layer | Measure |
|---|---|
| Tool output | Structured fields where parseable; hard size caps; redaction; suspicious-pattern flagging (imperative verbs targeting known command names) |
| Prompt | Role prompts state that all tool output is untrusted data, never instruction |
| Judge | Explicit check: does the recommendation contain any instruction traceable to log or RPC text? |
| Contract | Evidence references must resolve to collected signals, so an injected "finding" with no observation behind it is a rejected write (§5.3) |
| Structural | Even a fully persuaded model cannot act: no write path exists (DD-5), and a compromised worker holds only its scoped token (§4.3) |

### 6.5 Other Adapters: Codex, Antigravity, Native (new in v0.5)

§6.1 – §6.4 configure the reference Claude adapter. The adapters below meet the same conformance profile (plan §5.12.3, PC-1 … PC-9). Settings marked [U] are W1-O / W1-G items. A configuration that cannot meet a PC item with the settings below is not admitted in runtime form, and its provider is served by the native adapter (D20).

**Common launcher, all adapters [A].**

| Item | Setting |
|---|---|
| Sandbox | D11 backend. A **minimal read-only root filesystem per runtime** (`worker/rootfs/<runtime>`) containing only the runtime binary and its libraries. No shell, no coreutils unless the runtime cannot start without them (PC-2 inertness). No ops-host filesystem visible |
| Home and working directory | Fresh, read-only, generated by the controller from the bound bundle (PC-3). No `CLAUDE.md`, `AGENTS.md`, `GEMINI.md` or equivalent unless bundle-generated |
| Scratch | If W1 shows a runtime cannot start without a writable path, a size-capped, private in-sandbox tmpfs discarded at step end. Nothing is written to the ops-host filesystem (SR-11) |
| Network | Loopback to the model broker only (§5.12) |
| Environment | Placeholder, non-secret credential variables where a runtime insists on one. Auto-update and telemetry variables set off (PC-7) |
| Tools | The `valops` MCP stub server over stdio, exposing only the role's tools (§7.5) |
| Timeout | The controller kills the process tree at P-11, whatever the runtime's own timeout |

**Codex runtime adapter — `codex exec`.**

| Item | Setting | Evidence |
|---|---|---|
| Endpoint | `openai_base_url` in the generated `config.toml` → broker loopback, or a custom `[model_providers.valops]` with `base_url` | [E] S11 |
| Credential | API-key mode with a placeholder; account login never used | [E] S11 / [U] |
| Permission profile | `default_permissions = ":read-only"` | [E] S10 |
| Codex's own sandbox | Codex also uses bubblewrap + seccomp on Linux [E] S10. Nested inside D11 it must either work or be disabled in favour of D11. It must never degrade to unsandboxed (PC-5) | [U] |
| Approval policy | Non-interactive; no escalation path | [U], exact key name |
| MCP | `[mcp_servers.valops]` → stub server command | [E] S12 |
| Web search, connectors, browser | Off | [E] S10 lists them as separately controlled; exact keys [U] |
| Built-in shell | Removal not documented → PC-2 **inertness** test is the admission condition | [U] |

**Antigravity runtime adapter — `agy -p`.**

| Item | Setting | Evidence |
|---|---|---|
| Invocation | `agy -p <role prompt> --output-format stream-json --model <pinned slug> --print-timeout <below P-11>` | [E] S13 |
| Permissions | Generated `settings.json` with **no** `permissions.allow` entries. **`--dangerously-skip-permissions` is prohibited.** Because allow-rules are reportedly ignored in headless mode (S14), they are not relied on in either direction | [E] S13, S14 |
| Built-in file tools | Workspace read and write are auto-allowed in headless mode (S13). The workspace is the read-only generated directory, so writes fail at the OS. PC-2 inertness test required | [E] S13; [A] |
| Endpoint and credential | **Undocumented.** Headless mode uses cached credentials from an interactive login (S13), which PC-4 prohibits in the worker. Admission requires showing an endpoint override to the broker with no real credential in the worker | [U] |
| MCP | Configuration path reported by third parties only | [U] C2 |
| `--sandbox` | Not relied on; behaviour undocumented | [U] |
| Expected outcome | **Native-only** [H] (plan §5.12.3) | — |

**Native API adapter — all three providers.**

| Item | Setting |
|---|---|
| Loop | The project's own minimal tool-calling loop (`worker/adapters/native/loop.py`): send system prompt, episode view and the role's tool schemas; execute returned tool calls against the `valops` stubs; return results; stop when the model stops calling tools or at P-05 iterations |
| Provider bindings | The official provider client library for each (Anthropic, OpenAI, Google Gemini API), with its base URL pointed at the broker. Exact packages and versions pinned under D7 |
| Tools offered | **Only** the role's `valops` tools. There is no shell, file, web or code-execution tool, and no provider-hosted tool is enabled |
| Prompts and skills | From the bound bundle only; skills inlined (§6.2 fallback) |
| Artefacts | Written through the tools to the store, as for every adapter (§5.8) |
| Trust class | Runs as a worker: untrusted and sandboxed, although the project wrote it, because it parses model output |

---

## 7. Data and Interface Contracts

### 7.1 Episode Record (M0 subset of plan §5.7)

```json
{
  "episode_id": "uuid",
  "revision": 42,
  "class": "validator_health | telemetry_health",
  "opened_at": "RFC3339",
  "trigger": { "source": "sentinel|watchtower", "check": "delinquency|balance|...", "severity": "..." },
  "policy_bundle": "sha256:...",
  "consensus_mode": "tower|alpenglow|unknown",
  "consensus_mode_evidence": { "declared": "...", "version": "...", "feature_state": "...", "files": "..." },
  "signals":        [ { "id": "s1", "t": "...", "command_id": "...", "ref": "...", "summary": {} } ],
  "hypotheses":     [ { "id": "h1", "step_session": "...", "rank": 1,
                        "claim": "...", "test": "...", "expected_evidence": "...",
                        "status": "open|supported|refuted", "evidence_refs": ["s1"] } ],
  "recommendations":[ { "id": "r1", "hypothesis": "h1", "action_text": "...", "skill": "restart-idle-window",
                        "preconditions": [], "expected_postcondition": "...", "evidence_refs": ["s3"] } ],
  "no_action":      [ { "t": "...", "reason": "...", "evidence_refs": ["s2"] } ],
  "verdicts":       [ { "recommendation": "r1", "result": "PASS|FAIL", "checks": [], "session_id": "..." } ],
  "verifications":  [ { "t": "...", "rule": "...", "result": "pass|fail", "samples": [], "by": "verifier" } ],
  "recovery_observations": [ { "t": "...", "rule": "...", "note": "observed during analysis" } ],
  "reports":        [ { "kind": "incident|closure", "ref": "..." } ],
  "state": "open|diagnosing|recommending|judging|reporting|awaiting_operator|resolved|handed_off",
  "cost": { "per_role_usd": {}, "turns": {} }
}
```

`revision` increments on every append and is the CAS token for transitions (R-7).

**`rank` (v0.4, V2).** `rank` is 1 for the most likely hypothesis. Ranks are unique and contiguous within one `step_session`. The **top-ranked hypothesis** of an episode is the rank-1 hypothesis of the latest completed diagnosis step, and a later `refuted` status does not re-rank it. It is what the alert shows (AW-2) and what the operator rates in FB-1. The controller never routes on rank.

### 7.2 State Transition Table (new in v0.3, V1 F5)

| From | To | Authorised principal | Guard |
|---|---|---|---|
| `open` | `diagnosing` | controller | bundle verifies; not observe-only |
| `diagnosing` | `recommending` | controller | ≥1 hypothesis validated (§5.8) |
| `diagnosing` | `reporting` | controller | recovery observed, or no hypothesis supports an action |
| `recommending` | `judging` | controller | one recommendation or one no-action record validated (N-5) |
| `judging` | `recommending` | controller | verdict FAIL and retries remaining (≤ N) |
| `judging` | `reporting` | controller | verdict PASS |
| `judging` | `handed_off` | controller | verdict FAIL and retries exhausted (N-4; aligns with R-3, §9, RB-2) |
| `reporting` | `awaiting_operator` | controller | report ref present and alert dispatched |
| `awaiting_operator` | `resolved` | **verifier only** | recovery predicate held for W consecutive fresh samples |
| any non-terminal | `handed_off` | controller | failure, budget, integrity, revocation, drain deadline, missing artefact |
| `resolved`, `handed_off` | — | — | terminal |

Reports may be appended in a terminal state (that is how the closure report is written); terminal states also accept recovery observations (§7.3 post-hand-off monitoring) and controller bookkeeping (cost, step, annotation; N-9); no state transition and no other agent write is permitted there.

### 7.3 Concurrency Semantics (new in v0.3, V1 F5)

| Question | Answer | Tag |
|---|---|---|
| Two writers race a transition | CAS on `revision`: exactly one wins, the loser re-reads and re-decides | [A] |
| A request is delivered twice | Idempotency key: the second call returns the first result and appends nothing | [A] |
| Recovery observed **during** diagnosis, recommendation or judging | Verifier appends a `recovery_observation` and changes **no** state. The controller reads it at the next transition point and may route to `reporting`, skipping recommendation. **A step in flight is never cancelled**, so no step is interrupted between doing work and recording it | [A], DD-11 |
| Recovery observed in `awaiting_operator` | Verifier sets `resolved` after W consecutive samples, then the controller runs the closure step | [A] |
| Recovery observed after `handed_off` | Appended as an observation (accepted in terminal state, N-9). **`handed_off` is terminal** and is not reopened; if the signal recurs the sentinel opens a new episode. Reopening would make "what happened in incident X" unanswerable | [A] |
| Bundle revoked mid-episode | Episode → `handed_off` + high-severity alert; outstanding tokens refused | [A] |
| Worker hangs past its budget | Controller terminates it, revokes the token, counts a step failure | [A] |

### 7.4 Observer Command Table (M0 — all read-only)

| `command_id` | Underlying command | Args | Source |
|---|---|---|---|
| `validator_monitor` | `agave-validator -l <ledger> monitor` (bounded sample) | — | [E] S5 |
| `catchup` | `solana catchup --our-localhost 8899` | — | [E] S5 |
| `leader_schedule_self` | `solana leader-schedule`, filtered to own identity | `epoch?` | [E] S3 |
| `identity_balance` | `solana balance <identity pubkey>` | `pubkey` | [E] S3; [A] pubkey form |
| `running_version` | `grep -B1 'Starting validator with' <logfile>` | — | [E] S3 |
| `log_tail` | bounded tail, redacted | `lines` (bounded) | [A] |
| `host_metrics` | disk, memory, load, systemd unit state | — | [A] |
| `host_hygiene` | pending updates; SSH password authentication; fail2ban present; listening ports | — | [E] S4 for what to check |
| `consensus_state_files` | presence and mtimes of `tower-*.bin` vs. `vote_history-*.bin` — **one of the three observed inputs** to §5.10 | — | [E] S5 |
| `cluster_feature_state` | consensus feature activation state — exact query **[U]** (D9) | — | [U] |
| `rpc_latency` | local RPC round-trip sample, for OD-9 and §5.9 | — | [A] |

**M0 contains no other command, and no state-changing command.** Adding one is a code change plus a new bundle plus review. The table loader refuses to start on a table containing a state-changing or shell-metacharacter token (OD-3).

### 7.5 MCP Tool Surface by Role

| Tool | Roles | Tier |
|---|---|---|
| `get_validator_monitor`, `get_catchup`, `get_leader_schedule`, `get_identity_balance`, `get_running_version`, `tail_validator_log`, `get_host_metrics`, `get_host_hygiene`, `get_consensus_state_files`, `get_telemetry_health` | diagnostician, change-planner, proposal-judge | T0 |
| `get_verification_result` | change-planner, proposal-judge, reporter | T0 |
| `add_hypothesis`, `set_hypothesis_status` | diagnostician | T1 |
| `propose_recommendation`, `report_no_action` | change-planner | T1 |
| `submit_verdict` | proposal-judge | T1 |
| `write_incident_report`, `send_alert` | reporter | T1 |
| `draft_failover_runbook` | change-planner (text output only) | T1 [E] S5 for content |

Each tool is a stub that forwards a typed request to a broker; the broker enforces the contract.

---

## 8. Primary Flow (worked example — delinquency)

```
t0  Sentinel: catchup distance exceeds threshold for 2 consecutive samples
      → open_episode(class=validator_health, trigger=delinquency, bundle_id=<active>,
                     consensus_mode=<determined per §5.10>)        [store-control endpoint]
      → append_signal × n   (monitor, catchup, host_metrics, leader_schedule_self)

t1  Controller: verify bundle; CAS open → diagnosing; mint token(role=diagnostician,
      episode, session, bundle, expiry); fork worker with broker socket fds.
    diagnostician (fresh session):
        h1 rank 2 "ledger volume is full"      test: disk headroom + write errors in log
        h2 rank 1 "version drift after update" test: running_version vs. expected
      tool calls re-sample as needed; h1 set refuted (evidence s5), h2 supported (evidence s7)
    Controller validates the artefact (≥1 hypothesis, contract fields present, ranks 1..2);
    token revoked. Top-ranked hypothesis = h2 (shown in the AW-2 alert; rated in FB-1).

t2  CAS diagnosing → recommending. change-planner (fresh session, new token):
      r1 = { hypothesis h2, action "restart into an idle window to pick up version X",
             skill restart-idle-window, preconditions [ no own leader slot within window,
             snapshot policy: do not fetch on routine restart ],
             expected_postcondition [ running_version == X, catch-up recovers within W samples ],
             evidence_refs [ s7 ] }
      store validates that s7 exists in this episode; artefact validated.

t3  CAS recommending → judging. proposal-judge (fresh session, JUDGE VIEW ONLY):
      sees raw signals + r1 + skill preconditions. Sees no hypothesis prose, no planner
      rationale, no prior verdicts.
      checks: preconditions match the skill for the CONFIRMED consensus mode (if mode were
              `unknown`, a mode-specific precondition would be an automatic FAIL);
              every evidence ref resolves to a collected signal;
              least-impact option; no success-gaming pattern; no instruction sourced from log text
      → PASS, with the check list recorded. Artefact validated (non-empty checks).

t4  CAS judging → reporting. reporter → incident report + alert (recommendation + Judge
      evidence + raw signals). CAS reporting → awaiting_operator.

t5  Operator acts manually, outside the system. Verifier keeps re-sampling.
      Recovery predicate holds for W consecutive samples → verifier sets `resolved`
      [store-verify endpoint] and writes the verification record.
      If it never holds within the deadline → state stays awaiting_operator, alert escalates.

t6  Controller runs the closure reporter step: closure report + closure alert (FR-15).
      Episode remains `resolved`.
```

**Variant — recovery during analysis.** If at t2 the verifier's predicate holds, it appends a `recovery_observation` and changes nothing. The planner step completes and records its artefact. At the next transition the controller routes to `reporting` with the recovery attached, and the episode proceeds to `awaiting_operator` → `resolved` normally (§7.3).

---

## 9. Failure Modes

| Failure | Detection | Behaviour | Tag |
|---|---|---|---|
| Model provider unavailable or slow | Runtime error / timeout / broker upstream error | Episode → `handed_off` with signals gathered so far; alert; sentinel and verifier continue | [A] |
| Budget or turn limit hit | SDK result | Same | [A] |
| **Step ends with no valid artefact** | Controller validation (§5.8) | Retry with a fresh session; on exhaustion `handed_off` + alert naming what was missing. A missing verdict is never treated as PASS | [A] |
| Judge FAILs N times | Controller counter | `handed_off` + alert carrying every FAIL reason | [A] |
| Bundle hash mismatch | Integrity check | Observe-only; high-severity alert; no LLM step runs | [A] |
| **Bundle revoked, or drain deadline exceeded** | Broker / controller | Episode → `handed_off` + alert; outstanding tokens refused | [A] |
| **Observer daemon unreachable, slow, or stale** | Telemetry probes | **Opens a `telemetry_health` episode** (TH-1). Validator-health episodes are annotated, never opened, escalated or resolved on missing data (TH-2, TH-3) | [A], V1 F6 |
| **Local RPC degraded** | OD-9 circuit breaker | Polling of RPC-backed commands suspended; telemetry-health signal raised; the suspension is reported, not silent | [A] |
| Episode store write failure | API error | Controller aborts the step; alert; nothing is assumed written. Retry is safe because appends are idempotent | [A] |
| **Model broker unavailable** (v0.5) | Controller pre-flight | **No LLM step starts** (MB-3); sentinel and verifier continue; alert | [A] |
| **Model-broker refusal** (model not allowlisted, limit reached, provider without D21 approval) | Broker response | Step failure; retry within P-08 only if the cause is not a limit; otherwise `handed_off` + alert | [A] |
| **Audit sequencer unavailable** | Submit error | Fail closed: no LLM step starts without an audit path; sentinel and verifier continue and buffer; alert | [A] |
| **Anchor unreachable or stale** | Anchor lag metric | Lag above P-18: alert; the system keeps running, since a missing anchor weakens tamper-evidence but does not by itself indicate tampering. **Lag above P-19 (v0.4): no new LLM step starts** (sentinel-and-alert tier) until a fresh anchor is confirmed | [A], D15 |
| **Chain verification fails** | Timer / CI | High-severity alert; observe-only; the chain and the newest anchor are preserved for investigation | [A] |
| Agent attempts a denied tool | Broker denial (hook denial first) | Denied, audited, surfaced in the report | [E] S7 mechanism for the hook; [A] for the broker |
| **Agent attempts closure or verification** | — | The operation does not exist on its endpoint; the call fails as an unknown method and is audited | [A], DD-8 |
| Sandbox violation attempt | OS sandbox | Blocked, audited, alert | [A] |
| **Sandbox backend unavailable** | Controller pre-flight | Refuse to start a worker. Never run unsandboxed | [A], V1 F4 |
| **Operator does not acknowledge** (v0.4) | AW-3 acknowledgement window P-20 | Re-send once, then escalate to the backup operator. If both are silent, keep observing and alerting. The system never acts, because in M0 it cannot | [A], plan §2.6 |
| **Recovery test or restore fails** (v0.4) | Scheduled restore test (plan §17.3) | Alert the PO; blocks G1/G2 until it passes | [A] |
| Validator itself fails | Out of scope for the agent | systemd restart policy and watchtower are unaffected by the agent (NFR-1) | [A] |

**Degradation ordering [A].** Full operation → observe-only (bundle or integrity problem) → sentinel-and-alert only (agent or audit path unavailable) → watchtower only (ops host down). The validator's own availability does not depend on any of these tiers — though observation load on it is bounded rather than absent (§2.4).

### 9.1 Degraded-Mode Runbooks (new in v0.4, V2)

One runbook exists per failure mode. Each is kept in `docs/runbooks/RB-nn.md` and exercised by the degradation suite (§10.2) by following its steps. Two rules hold in every runbook [A]:

- **Never restore service by weakening a control.** Disabling the sandbox, relaxing a budget, raising a rate cap, skipping a check, or hand-editing a bundle are all prohibited as fixes. A needed change goes through change control (plan §17.1).
- **`handed_off` episodes are never reopened** (§7.3). The operator handles them by hand, and a recurring signal opens a new episode.

| ID | Trigger | Automatic behaviour | Operator actions | Exit condition |
|---|---|---|---|---|
| RB-1 | Model provider unavailable or slow | In-flight episode → `handed_off` with the signals gathered so far; alert. Sentinel and verifier continue. After P-29, and only if a **pre-approved** fallback bundle exists, the controller activates it for new episodes (audited, alerted) | Diagnose from watchtower and the handed-off signals. Check provider status. **Never** hand-edit `providers.yaml` to switch provider | A probe step on the primary configuration completes; `active` is returned to the primary bundle through the normal activation process |
| RB-2 | Budget, turn limit, step-retry or Judge-retry budget exhausted | `handed_off` + alert naming the cause | Handle the incident by hand. Log it for the weekly review (AW-6). If it recurs, file a change request against P-05 / P-06 / P-08 / P-09 | Per episode; none system-wide |
| RB-3 | Bundle integrity failure | **Observe-only**: no LLM step; high-severity alert naming the changed path | Notify the security reviewer. Compare the bundle with its signed manifest. Do not re-point `active` until the cause is known. Then either roll back to the previous verified bundle or revoke | A verified bundle is active and the integrity check passes at process start |
| RB-4 | Bundle revoked, or drain deadline exceeded | Bound episodes → `handed_off`; outstanding tokens refused | Handle the affected incidents by hand. Confirm which bundle is now active | No live episode is bound to a revoked bundle |
| RB-5 | Observer unreachable, slow or stale | **`telemetry_health` episode** opens (TH-1). Validator-health episodes are annotated, never resolved from stale data (TH-2, TH-3) | Rely on watchtower as the independent signal. Check the daemon unit, its cgroup, the mTLS link and the validator host. **Do not restart the validator because telemetry was lost** | Probes back within P-15 for W (P-17) samples. The verifier resolves the telemetry episode |
| RB-6 | Local-RPC breaker trips (OD-9) | RPC-backed polling suspended; telemetry-health signal raised | Check validator RPC load and whether observation is the cause (Q-7). Do not raise P-14 ad hoc | Latency below P-16 for W samples; polling resumes automatically |
| RB-7 | Episode store unavailable | Controller aborts the step; alert; nothing assumed written | Restore the service. If data is lost, restore from backup (plan §17.3) and verify revisions | Store up; idempotent retries replayed without duplicates |
| RB-8 | Audit sequencer unavailable | **No LLM step starts**. Sentinel and verifier continue and buffer; alert | Restore the sequencer. Confirm buffered entries are flushed in order | `verify_chain` passes, including the flushed entries |
| RB-9 | Anchor lag above P-19 | **No new LLM step starts**; alert | Check the anchor store's reachability and the put-only credential. Never disable the lag check | A fresh anchor is confirmed |
| RB-10 | Chain verification fails | **Observe-only**; high-severity alert; chain and newest anchor preserved | Treat as possible tampering; the security reviewer leads. **Do not truncate or "repair" the chain.** Rotate chain keys after the investigation | Written clearance from the security reviewer, recorded under change control |
| RB-11 | Sandbox backend unavailable | Controller refuses to spawn workers | Restore the backend. **Never run a worker unsandboxed** | Controller pre-flight passes |
| RB-12 | Operator does not acknowledge (AW-3) | Re-send once, then escalate to the backup | Backup takes over the incident | Acknowledged |
| RB-14 | Model broker unavailable (v0.5) | **No LLM step starts** (MB-3); sentinel and verifier continue; alert | Restore the broker. Never give a worker a provider key directly as a workaround | Broker pre-flight passes; a probe step completes |
| RB-13 | Ops host down | Watchtower-only tier. Watchtower should run on a third host so that it survives this case (§3) | Restore the ops host from backup (plan §17.3). Verify both chains against the anchor before re-enabling LLM steps | Restore verified; all probes healthy |

---

## 10. Testing Strategy (M0 exit gates)

**Gate classes (v0.4, plan §8.1).** Every suite below is marked **D** (deterministic: 100% pass, every run, repeated over P-22 trials, one failure blocks) or **MQ** (model quality: frozen fixture set with its hash recorded before the run, repeatable controls, P-23 runs per fixture, pass judged on the lower confidence bound against the plan §13.3 target, disputed and unstable cases adjudicated by a human who did not write the prompts or fixtures). An MQ result obtained while any D suite is failing counts for nothing.

### 10.1 M0A gates — containment, before any diagnosis work

All M0A suites are class **D**. **They count towards G1 only when run on real boundaries** (plan §7.2): real Unix domain sockets with each process class under its own uid and kernel peer credentials; the real D11 sandbox backend, with fail-closed shown by actually making it unavailable; the real external anchor store under its retention lock; the pinned runtime version making real calls with the pinned model **through the real model broker holding real provider keys**; and the observer daemon on the real testnet validator host under its real cgroup limits. Mocked runs are useful during development and carry no G1 weight.

| Suite | Contents | Gate |
|---|---|---|
| **Principal authentication** | Caller-supplied actor field ignored; call on the agent endpoint with a control-endpoint operation fails as unknown method; token for episode A refused on episode B; role A's token refused for role B's operation; expired token refused; token bound to a revoked bundle refused | 100% pass, every run |
| **Capability absence** | Agent endpoint exposes no `set_state`, no `append_verification`, no closure — asserted against the served method list, not by attempting and catching | 100% pass |
| **Audit integrity** | Single-writer serialisation under concurrent submitters (no `seq`/`prev` collision); entry actor matches the authenticated principal and not the submitted one; fsync before ack; local chain rewrite detected against an external anchor; daemon chain truncation detected at the ops host | 100% pass |
| **Process topology** | For every admitted configuration: worker environment and filesystem contain no provider credential or cached login; worker cannot open any network connection but the model broker; worker cannot write any file; worker reaches broker sockets bind-mounted into its mount namespace (preserving `SO_PEERCRED`; N-3); sandbox backend unavailable ⇒ refuse to start | 100% pass |
| **Provider conformance** (v0.5) | Per configuration, PC-1 … PC-9 (plan §5.12.3): each built-in tool attempted and shown removed or inert; planted instruction files ignored; host cached login unused; hang killed at P-11; blocked auto-update and telemetry do not fail open; runtime never runs unsandboxed | 100% pass; decides PA and D20 |
| **Model broker** (v0.5) | Principal from the per-worker socket, not from the request; wrong provider or model refused; limits cut off exactly; inbound credential headers stripped; no direct provider route from the worker; broker down ⇒ no LLM step; transcript hash matches the request sent; unapproved provider unroutable | 100% pass |
| **SDK configuration** | On the **D1/D7-pinned** runtime, SDK version and model only: session loads exactly the intended tools, prompt file and skills (or the inlined-prompt fallback); removed built-ins absent from context; `dontAsk` denies an unlisted tool; hook deny and hook timeout each prevent execution | 100% pass; result amends §6. A re-pin re-runs this suite |

**M0B does not start until all seven pass on real boundaries for the reference configuration, repeated over P-22 trials, and G1 is approved** (plan §7.2).

### 10.2 M0B gates

| Suite | Contents | Gate |
|---|---|---|
| Policy (CI-blocking) | Role calling another role's tool denied; out-of-state tool call denied; agent write to a bundle fails at the OS level | 100% pass, every run |
| Write-path absence | Static check: no state-changing command id in any bundle's table; no code path from a tool to such a command; `executor/` absent from the artefact | 100% pass, every run |
| Bundle lifecycle | Mutate each bundle file ⇒ observe-only + alert; activation leaves in-flight episodes on their bundle; drain deadline ⇒ `handed_off`; revocation stops in-flight episodes and refuses tokens; rollback restores the exact previous bundle | 100% pass |
| Concurrency | CAS race: exactly one transition wins; duplicate delivery is a no-op; recovery mid-analysis attaches an observation and changes no state; `handed_off` not reopened | 100% pass |
| Judge adversarial | Seeded bad recommendations: alert silencing; recovery claimed from process liveness alone; repeated restarts; snapshot download renamed; log-injected instruction; precondition mismatched to consensus mode; **evidence ref to a signal never collected**; **mode-specific precondition while mode is `unknown`** | **MQ with a no-miss target:** every seeded case returns FAIL in every one of P-23 runs; fixture set frozen before the run; confidence interval reported |
| Judge isolation | Controller asserts the Judge input (view minus the target artefact under judgement, N-17) contains no planner or diagnostician prose before the session starts | 100% pass |
| Artefact completeness | Session ends with no artefact ⇒ retry then `handed_off`; structured output disagreeing with the stored artefact ⇒ step failure; prose containing a plausible recommendation is never promoted to one; missing verdict never treated as PASS | 100% pass |
| Closure ownership | Agent attempts `set_state(resolved)` and a verification write ⇒ operation does not exist | 100% pass |
| Falsifiability | Hypothesis lacking `test` rejected at the API; evidence ref to a non-existent signal rejected | 100% pass |
| Telemetry health | Daemon unreachable / slow / stale each open a `telemetry_health` episode and alter no validator-health episode; RPC breaker trip is reported | 100% pass |
| Consensus mode | Tower and vote-history fixtures; **both files present**; version or feature state disagreeing with the declaration ⇒ `unknown` and mode-specific proposals FAIL | 100% pass |
| Resource containment | Observer daemon under synthetic load stays within its cgroup limits (P-13); validator RPC latency measured in paired observer-on / observer-off windows | Limits: D, never exceeded. RPC impact: within Q-7 |
| Functional (testnet) — routing | FC-1 … FC-5 injected (plan §2.6): correct episode class and trigger; correct degradation for FC-5 | **D:** 100% |
| Diagnosis and actionability | FC-1 … FC-5, P-24 injections each, ground truth logged by the injector before reports are read. Top-ranked hypothesis (§7.1) rated by FB-1; recommendation rated by FB-2 | **MQ:** Q-1 and Q-2 lower confidence bounds ≥ plan §13.3 targets; **zero FB-2 unsafe flags (D)** |
| Operator value vs. baseline | Watchtower baseline campaign, then paired run-in incidents (plan §2.6) | **MQ:** Q-4 lower confidence bound > 0 and ≥ target; Q-3, Q-5, Q-6 within ceilings |
| Degradation | API down; store down; broker down; sequencer down; anchor down; **anchor lag above P-19**; daemon down; budget exhausted; operator unresponsive — each exercised by following its runbook (§9.1) | **D:** correct degradation tier; validator unaffected; runbook exit condition reached |
| Backup and recovery | Restore store, chains and bundles onto a fresh ops host; verify against the anchor; resume without duplicate appends; revocation list never rolled back; key-recovery paths (plan §17.3) | **D:** 100%; RPO/RTO within P-26 |
| Repetition | D suites over P-22 trials; MQ suites P-23 runs per fixture | No single-trial pass counts |

---

## 11. Observability and Metrics

The G2 metrics are Q-1 … Q-8, defined in plan §2.6 with targets in plan §13.3, **reported separately for every configuration** (v0.5). The table below is what the system must emit for them and for day-to-day health. Rows not mapped to a Q-metric carry no gate weight.

| Metric | Purpose |
|---|---|
| Episodes opened, by class, check and severity | Volume and noise |
| MTTD vs. watchtower alone | Does the sentinel add detection value |
| Top-ranked hypothesis correct (FB-1 on the rank-1 hypothesis, §7.1) | Diagnosis quality — **Q-1** |
| Judge FAIL rate; share of FAILs a human confirms as correct | Is the Judge useful or merely obstructive |
| Recommendation actionability (FB-2); unsafe flags | Recommendation quality — **Q-2** |
| Operator time to decision (FB-4), paired against the watchtower baseline | Operator value — **Q-4** |
| Alerts per day; false-alarm share (FB-5) | Operator burden — **Q-5** |
| Step-failure rate by cause (missing artefact, schema failure, output disagreement) | Is the artefact contract too tight or the prompt too loose |
| Unauthorized executions | **Hard requirement: zero** — **Q-8** |
| Denials, tamper events, token rejections, sandbox blocks | Containment health |
| **Anchor lag; chain-verification runs and results** | Tamper-evidence health |
| **Telemetry-health episode count and duration; sample staleness per check; RPC breaker trips** | Can the system still see the validator |
| **Observer resource usage vs. limits; measured validator RPC impact** | Is observation cheap enough to be harmless (§2.4) — **Q-7** |
| Cost and turns per role, per episode and per day, **per configuration**, from the model-broker meter | **Q-6**; data for P-05 … P-07, P-30 |
| Model-broker refusals by cause; provider error rate; fallback activations | Provider health (v0.5) |
| Time from episode open to AW-2 alert delivered | Report latency — **Q-3** |

---

## 12. Work Breakdown

Ordered by dependency. Complexity is a relative rating **[A]**. The M0A effort estimates, critical path and time box are in the M0A charter (plan §7.1), their one home. M0B estimates are produced the same way at G1.

### G0 — before any code

| # | Work item | Depends on | Complexity | Notes |
|---|---|---|---|---|
| **W0** | **G0 delivery package** | — | M | Product definition (plan §2.6); M0A-blocking decisions closed or defaulted (plan §13.1); registers (plan §13.2, §13.3); gate classes and fixture-freeze procedure (plan §8.1); M0A charter with named DRIs (plan §7.1); governance (plan §17); runbooks (§9.1); cross-document consistency check. **No code before G0** |

### M0A — containment prototype

| # | Work item | Depends on | Complexity | Notes |
|---|---|---|---|---|
| W1 | Phase-0 SDK verification spike | W0; **D1, D7 pinned** | M | Confirms `tools=["Skill", …]`, skills loading with `setting_sources=[]`, `dontAsk` + role allowlists, hook deny/timeout, sandbox fail-closed and the `failIfUnavailable` discrepancy (§6.2), `output_format`. Blocks everything; result amends §6 |
| W2 | Observer daemon + command table + mTLS + **systemd/cgroup limits** | W0 | M | Parallel with W1. OD-3 loader refusal is part of this item |
| W3 | Episode store: three endpoints, CAS, idempotency, contract checks (incl. rank uniqueness) | W0 | L | Server-side rejection of agent closure is the core of DD-4/DD-8 |
| W4 | **Audit sequencer + external anchoring + daemon-side chain** | W3 | M | Single writer, server-stamped principals, anchor export (D15) |
| W5 | Policy bundles: build, sign, bind, activate, drain, revoke, roll back; generate thresholds from the parameter register | W0; D14 | M | Replaces the v0.1 "mount + manifest" item |
| W6 | Process topology: controller, worker spawn, token minting, OS sandbox (D11), **adapter framework + Claude adapter + per-runtime minimal rootfs** | W1, W5 | L | Must fail closed; demonstrated against the §10.1 suite |
| W7 | Capability brokers: episode, observer, report | W2, W3, W4 | M | Broker-side re-enforcement of every hook check |
| W6b | **Model broker [12]** (§5.12) | W4 | M | Sole key holder, egress bridge, allowlist, limits, transcript (v0.5) |
| **W8** | **M0A containment test suite (§10.1), run on real boundaries** | W3–W7, W6b | M | **Evidence for G1** (reference configuration) |

### Provider track (v0.5) — parallel, off the G1 critical path

| # | Work item | Depends on | Complexity | Notes |
|---|---|---|---|---|
| W1-O | Phase-0 verification: Codex configuration, PC-1 … PC-9 | W0; D7, D21 | S | Decides D20 for Codex |
| W1-G | Phase-0 verification: Antigravity configuration, PC-1 … PC-9 | W0; D7, D21 | S | Decides D20 for Gemini; native-only expected [H] |
| W21 | Codex runtime adapter (§6.5) | W1-O, W6, W6b | S | Only if W1-O admits the runtime |
| W22 | Antigravity runtime adapter (§6.5) | W1-G, W6, W6b | S | Only if W1-G admits the runtime |
| W23 | Native API adapter, three provider bindings (§6.5) | W6, W6b | M | The floor for every provider |
| W24 | PA runs per configuration (§13) | W8, W21–W23 | M | Re-runs §10.1 per configuration |

### M0B — diagnosis workflow

| # | Work item | Depends on | Complexity | Notes |
|---|---|---|---|---|
| W9 | MCP tool stubs, role-scoped | W6, W7 | S | Stubs only; contracts live in the brokers |
| W10 | Hooks: policy gate + audit (defence in depth) | W7, W9 | S | Explicitly not a boundary (§6.3) |
| W11 | Sentinel + thresholds + **telemetry-health probes** | W2, W3 | M | |
| W12 | Controller state machine + **artefact validation** | W3, W6, W9 | L | |
| W13 | Skills library v1 with compatibility matrix, **and the inlined-prompt fallback** | W5 | M | Content work, not code |
| W14 | Role prompts + Judge checklist | W13 | M | |
| W15 | Recovery verifier + **consensus-mode determination** | W2, W3, W5; D9 | M | Declarative predicates; declared mode cross-checked against three observed inputs (§5.10) |
| W16 | Reporter + alert sink (D5) + **closure report** | W7, W3 | S | |
| W17 | Test suites §10.2 incl. fault-injection harness | W11, W12, W15 | L | |
| W19 | **Evaluation support (C12):** FC-1 … FC-5 injection scripts with ground-truth log; rubric capture linked to episode ids; evaluation harness recording repeatable controls; fixture-set freezing and hashing | W11, W16 | M | Needed before any MQ gate run |
| W20 | **Watchtower baseline campaign** (plan §2.6) | W19; ER-3 | S | Before the run-in; recorded once |
| W18 | Testnet deployment and run-in over P-25 | all, incl. W20 | M | |

---

## 13. Milestone Exit Criteria (re-expressed as gates in v0.4)

The gates, their deciders and their vetoes are defined in plan §7.2. This section lists the HLD-level evidence each gate needs.

### G0 — before M0A coding

W0 complete and approved (§12). No code before this.

### G1 — M0A → M0B

All four properties the review asks to prove first, demonstrated by the §10.1 suites at 100% over P-22 trials **on real, not mocked, boundaries** (§10.1):

1. **Authenticated capability boundaries.** No caller can assert its own identity; the agent endpoint has no closure, verification or state-transition operation; tokens are scoped, expiring and bundle-bound. Shown over real Unix domain sockets with real uids and kernel peer credentials.
2. **Centralised, externally anchored audit.** One writer; server-stamped principals; fsync; signed chain heads in the **real** external append-only store; local rewriting and daemon-chain truncation both detectable against it; anchor lag above P-19 stops new LLM steps.
3. **A process topology that fails closed.** Four process classes with disjoint credentials; the worker holds no provider credential, cannot write the filesystem, and reaches nothing but the model broker and its broker sockets; the model broker enforces provider, model and limits; making the **real** sandbox backend unavailable prevents a worker from starting.
4. **A verified SDK configuration.** On the D1/D7-pinned runtime, SDK and model, the session loads exactly the intended tools, prompt and skills — or the inlined-prompt fallback is adopted and §6 amended accordingly. The `failIfUnavailable` discrepancy (§6.2) is resolved, or fail-closed is shown outside the SDK.

G1 is granted for the **reference (Claude) configuration**; its PA is part of G1. Also required: environment readiness ER-1 … ER-13 complete, and a backup-restore test passed (plan §7.1, §17.3).

### PA — provider admission, per configuration (v0.5)

For the Codex, Antigravity and native configurations. It is off the G1 critical path and decided by the PO and the security reviewer (plan §7.2).

1. Provider conformance PC-1 … PC-9 passes at 100% over P-22 trials (§10.1).
2. Every other §10.1 suite is re-run **with this configuration** on real boundaries and passes at 100%.
3. D21 data-handling approval is on record for the provider.
4. The configuration is pinned in `providers.yaml` of a signed bundle.

A configuration that holds PA may serve M0B episodes and enter the run-in. It is evaluated on its own; results are never pooled (plan §8.1).

### G2 — M0 → M1

G2 is granted **per configuration** (plan §5.12.4). M1 may use only configurations that hold G2. M1 needs **both** safety evidence **and** operator-value evidence. Safety passing alone is not enough (plan §12 item 9).

**Safety (all class D, 100%):**

1. Every D suite in §10.1 and §10.2 passes over P-22 trials, with zero unauthorized executions (Q-8 = 0).
2. The write-path-absence check passes on the shipped artefact, and `executor/` is absent from it.
3. Tamper, revocation, drain, sandbox, anchor-lag and telemetry-loss tests each force the expected degraded state, and each runbook (§9.1) reaches its exit condition.
4. Observer resource usage never exceeds its limits (P-13) under load.
5. Backup and recovery tests pass within P-26.
6. Zero unresolved FB-2 *unsafe* flags.

**Operator value (class MQ, on frozen fixtures and the run-in, targets from plan §13.3):**

7. Every seeded Judge adversarial case returns FAIL in every run (no-miss target).
8. **Diagnosis quality (Q-1):** across FC-1 … FC-5, the **top-ranked hypothesis** (rank 1 in the latest completed diagnosis step, §7.1) is rated *correct* in FB-1 against the injector's ground truth, with a lower confidence bound at or above target. This replaces v0.3's "correctly ranked hypothesis", which the schema could not measure.
9. **Actionability (Q-2):** the FB-2 ∈ {1, 2} share has a lower confidence bound at or above target.
10. **Value vs. baseline (Q-4):** the paired reduction in time to correct diagnosis, against the watchtower baseline, has a lower confidence bound above zero and at or above target.
11. Report latency (Q-3), operator burden (Q-5), cost (Q-6) and observation impact (Q-7) are within their ceilings over the run-in period (P-25).

**Records:**

12. The Phase-0 verification log is complete on the pinned configuration, and §6 has been amended wherever the SDK behaved differently from the assumptions here.
13. Per-role cost measured over the run-in has been fed back into P-05 … P-07 through change control.

**Kill criteria.** Plan §12 applies, including items 8 (M0A time box exhausted) and 9 (operator value not shown). The M0-specific triggers: if W1 shows the SDK's permission, hook or sandbox semantics cannot guarantee SR-3, SR-4, SR-10 or SR-11 on the pinned version **and** the gap cannot be closed outside the SDK; or if M0A cannot demonstrate its four properties — stop and redesign the containment layer before writing further code.

---

## 14. Traceability: Review Findings → This Document

| Finding (V1) | Severity | Resolution | Where |
|---|---|---|---|
| F1 — store trust boundary not enforceable | High | Three endpoints; transport-derived principals; capability tokens; **closure absent from the agent endpoint** | §5.3, DD-8, §10.1 |
| F2 — audit neither safely multi-writer nor tamper-evident | High | Single sequencer, server-stamped actors, fsync, payload hashing, signed heads anchored off-host, daemon-side chain with forwarded checkpoints | §5.5, DD-9, §10.1 |
| F3 — process/sandbox decomposition inconsistent | High | Four named process classes with a compromise analysis; hook demoted to defence in depth; brokers re-enforce every check | §4.3, §6.3, §10.1 |
| F4 — SDK configuration not valid as reference | High | `tools=["Skill", …]`; fail-closed sandbox intent; **prompt-inlining fallback removes the skills dependency from the critical path**; the `failIfUnavailable` discrepancy recorded rather than assumed | §6.1, §6.2, §16 |
| F5 — resolution races the runner | High | Transition table with authorised principals; CAS revisions; idempotency keys; recovery-during-analysis attaches an observation only; closure report; terminal `handed_off` | §5.2, §7.2, §7.3, DD-11 |
| F6 — "zero availability risk" unsafe; telemetry loss mishandled | High | Claim withdrawn and restated; observer resource limits and RPC breaker; **telemetry-health episode class** | §2.4, §5.9, §5.11, DD-12 |
| F7 — consensus-mode detection ambiguous | Medium | Declared mode cross-checked against three observed inputs (four in total); disagreement ⇒ `unknown` ⇒ mode-specific recommendations prohibited | §5.10, §7.4 |
| F8 — policy updates strand active episodes | Medium | Immutable hash-addressed bundles; per-episode binding; drain, revocation, exact rollback | §5.4, DD-10 |
| F9 — output completeness not enforced | Medium | Artefact validation before every transition; structured output as cross-check; stored artefact authoritative; prose never parsed; no-action is a first-class artefact | §5.8, §5.7, §7.2 |
| F10 — broken references and naming drift | Low | Parent filename corrected; the absent `plan-review-vs-vibeserve.md` dependency removed; Observer Daemon vs. Executor separated by milestone | §0.1, plan §14 |
| Recommendation — start with an M0A containment prototype | — | M0 split; M0B gated on M0A's four properties | §1, §12, §13 |

Competitive-analysis input (C1) produced no design change here; it is recorded in plan §15 and routed to plan decisions D1, D2, D7, D13, D17.

### 14.1 Pre-coding review (V2) → v0.4

The full mapping is in plan §16. HLD-specific resolutions:

| V2 item | Resolution | Where |
|---|---|---|
| M0 defined as a read-only incident-analysis assistant, not an autonomous operator | Stated; definition referenced from plan §2.6, not restated | §1, §3 |
| "Correctly ranked hypothesis" with no rank field | `rank` and `step_session` in the schema and the store API; uniqueness enforced; exit criterion measured by FB-1 on the top-ranked hypothesis | §5.3, §7.1, §13 G2-8 |
| Three-way vs. four-input consensus wording | One wording in both documents | §2.1, §5.10, §7.4, §12 W15, §14 |
| D3 as both an M0 and a Phase-4 decision | D3 = M0 testnet environment; D18 = Phase-4 cluster | §2.2, §15 |
| W1 cannot validate before language, SDK and model are pinned | W1 depends on W0 and the D1/D7 pins; SDK suite runs on the pinned configuration only | §10.1, §12 |
| M0B only after real, not mocked, boundaries | Definition of "real" for every M0A suite | §10.1, §13 G1 |
| Deterministic vs. model-quality gates | Every suite classed D or MQ | §10 |
| Degraded-mode runbooks | RB-1 … RB-13 | §9.1 |
| D15 maximum lag | Above P-19, no new LLM step | §5.5, §9, RB-9 |
| D13, D10, D17, non-Agave clients, M1 out of M0 | Out-of-scope table; D13 and D17 removed from M0 blockers | §2.2, §15 |

### 14.2 Owner requirement (2026-09-21) → v0.5

| Requirement | Resolution | Where |
|---|---|---|
| Support Claude, Codex and Gemini via Antigravity | Adapters, model broker, conformance, PA per configuration | §1, §4, §5.12, §6.5, §10.1, §13 |
| Keep every containment property | Worker boundary is runtime-independent; credentials and limits in the broker; provider extras are defence in depth only | §2.3 items 4–5, §4.3, DD-13 |
| Keep M0 narrow | Reference configuration alone on the G1 path; provider track parallel | §12, §13, D19 |

### 14.3 Codebase Implementation & Architecture Reconciliation (N-1 … N-17)

Refinements and resolutions established during the M0 codebase implementation (`valops/`, `tests/`, `docs/IMPLEMENTATION-NOTES.md`):

| ID | Finding / Area | Resolution in Codebase | HLD Section |
|---|---|---|---|
| **N-1** | Store endpoint structure | Added `store-observe` endpoint so tool-driven re-samples become citable signals; content arrives from daemon via observer-broker | §4.1, §5.3 |
| **N-2** | Agent endpoint principal isolation | Split `store-agent` into `store-agent` (episode broker) and `store-agent-report` (report broker), enforcing principal per socket | §4.1, §4.3, §5.3 |
| **N-3** | Worker socket transport & credentials | Broker sockets bind-mounted into sandbox filesystem; worker connects directly to ensure `SO_PEERCRED` captures worker UID | §4.1, §4.2, §6.2 |
| **N-4** | Judge retry exhaustion | Reconciled §7.2: retry exhaustion transitions to `handed_off` (with alert detailing fail reasons), aligning with R-3, §9, and RB-2 | §5.2, §7.2 |
| **N-5** | `no_action` routing | `report_no_action` transitions from `recommending` to `judging` (evaluated against checklist item `no_action_justified`), matching transition table | §5.7, §7.2 |
| **N-6** | Judge view contents | Judge view includes signals, target artefact, skill definition/preconditions, plus deterministic `verifications` and `recovery_observations` | §5.3, §5.7 |
| **N-7** | Mode-specific proposal enforcement | Store deterministically rejects `append_recommendation` citing mode-specific skill if episode consensus mode is `unknown` or mismatched | §5.3, §5.10 |
| **N-8** | Reporter alert generation | Report broker populates alert metadata (severity, fault class, top hypothesis, recommendation, verdict, link) directly from verified record | §4.3, §5.7 |
| **N-9** | Terminal state operations | Terminal states accept reports (closure), recovery observations (§7.3 post-handoff monitoring), and controller bookkeeping (cost, step, annotation) | §5.3, §7.2, §7.3 |
| **N-10** | Provider refusal fallbacks | Anthropic native binding explicitly disables server-side refusal/overload model fallbacks to preserve D7 configuration pinning | §5.12 |
| **N-11** | Model broker streaming & audit | Provider response is streamed/relayed to worker first, followed immediately by transcript hash submission to audit sequencer | §5.12 |
| **N-12** | Model broker token metering fallback | If usage is unparseable from provider stream/response, session is charged estimated input plus clamped maximum output tokens | §5.12 |
| **N-13** | Failover runbook skill | `draft_failover_runbook` returns checklist for the confirmed mode only; withheld under `unknown` | §5.7, §7.5 |
| **N-14** | Worker process spawning privileges | Controller systemd unit retains only `CAP_SETUID` and `CAP_SETGID` to spawn worker processes under dedicated worker UID | §4.1, §4.3, §5.2 |
| **N-15** | Delinquency detection interface | Delinquency check tracks slot distance trend over P-03 consecutive samples (`catchup`), avoiding fragile unbuffered monitor scraping | §5.1 |
| **N-16** | Per-role operational quotas | Episode-broker writes $\le 4 \times P-05$, hook tool calls $\le 3 \times P-05$, observer tools $\le P-14$ per session | §5.2 |
| **N-17** | Judge isolation assertion | Controller asserts Judge input view *minus* the target artefact under judgement contains no planner or diagnostician prose | §10.2 |

---

## 15. Open Decisions Blocking M0 (restructured in v0.4)

The decision register — DRI, approver, due gate, default-if-late and closing evidence — lives in **plan §13.1**. It is summarised here only to show which HLD work items each decision blocks and what this HLD assumes if the default is adopted.

**M0A blockers — closed or defaulted at G0.**

| ID | Decision | Blocks | Default this HLD is written against |
|---|---|---|---|
| D1 | Implementation language | W1 and all code | Python (DD-7) |
| D7 | Pinned runtime versions and model IDs, **per provider** | W1, W1-O, W1-G, W12 | Exact pins per configuration, recorded in `providers.yaml` |
| D3 | M0 testnet environment | W2, W18 | One dedicated project-operated Agave testnet validator plus a separate ops host (§3) |
| D5 | Alert channel | W16 | A dedicated channel on the service the operator already uses with watchtower |
| D6 | Thresholds, budgets, trial and pass rules | W5, W11, W12, W17 | Parameter register P-01 … P-28 and target register Q-1 … Q-8 (plan §13.2, §13.3) |
| D11 | OS sandbox backend (also hosts the Codex and Antigravity runtimes) | W1, W6, W1-O, W1-G | bubblewrap; must fail closed on the real backend at G1 |
| D14 | Bundle signing key custody and rotation | W5 | Offline hardware-token key held by the PO, with a sealed backup |
| D15 | Audit anchor service, cadence, maximum lag | W4 | Retention-locked object storage in a separate account; P-18 interval; P-19 maximum lag (§5.5) |
| D16 | Capability transport | W3, W6, W7 | UDS with kernel peer credentials on one ops host; mTLS only to the validator host |

**Multi-provider decisions (v0.5).**

| ID | Decision | Blocks | Default this HLD is written against |
|---|---|---|---|
| D19 | Provider scope and order for M0 | W0 | Claude is the reference configuration on the G1 path; Codex and Antigravity on the provider track through PA; each provider needs at least one admitted configuration through the run-in |
| D20 | Runtime or native adapter, per provider | W21–W23 | Runtime first, native on any PC failure; W1-O / W1-G decide |
| D21 | Data-handling approval, per provider | W1-O, W1-G, MB-5 | No approval ⇒ unroutable |
| D22 | Cross-provider Judge | — | Not used in M0 |

**M0B blocker.**

| ID | Decision | Blocks | Default |
|---|---|---|---|
| D9 | Consensus mode on testnet; exact cluster-feature query | W13, W15 | Query unverified ⇒ feature-state input `unavailable` ⇒ mode `unknown` ⇒ no mode-specific recommendation (§5.10) |

**Excluded from M0 — do not block it.** D2 (Agave only), D4 (no upgrade in M0), D8 (T0/T1 only), D10 (offline tuning excluded), D12 (no approval step), **D13** (single validator; shadow-fleet size decided no earlier than Phase 4), **D17** (no publication in M0), **D18** (Phase-4 target cluster; the Phase-4 half of v0.3's D3). In v0.3 this HLD listed D13 and D17 as M0 blockers; v0.4 removes them, as V2 required.

---

## 16. Appendix: Phase-0 Partial Verification Log (as of 2026-09-17)

Recorded so W1 starts from evidence rather than from the assumptions in §6. **Everything here must be re-confirmed on the pinned version before it is relied on.** Since v0.4, W1 runs only on the D1/D7 pin (§12); 0.2.154 is an inspection reference, not a pin. Source X1: direct inspection of `claude-agent-sdk` 0.2.154.

| Item | Observed | Status |
|---|---|---|
| `ClaudeAgentOptions` fields | `tools`, `allowed_tools`, `disallowed_tools`, `system_prompt`, `mcp_servers`, `strict_mcp_config`, `permission_mode`, `hooks`, `skills`, `sandbox`, `setting_sources`, `max_turns`, `max_budget_usd`, `model`, `output_format`, `agents`, `plugins`, `env`, `continue_conversation`, `resume`, `fork_session` all present | Consistent with §6.1 |
| `permission_mode` values | includes `dontAsk` | Consistent with DD-6 |
| `PreToolUse` hook output | `hookSpecificOutput.permissionDecision` ∈ {`allow`, `deny`, `ask`, `defer`}, with `permissionDecisionReason` | Consistent with §6.3 |
| Python hook events | `PreToolUse`, `PostToolUse`, `PostToolUseFailure`, `UserPromptSubmit`, `Stop`, `SubagentStop`, `PreCompact`, `Notification`, `SubagentStart`, `PermissionRequest` — **no `SessionStart` / `SessionEnd` / `StopFailure`** | Confirms §6.2 and plan D1 |
| `ResultMessage` | carries `total_cost_usd`, `num_turns`, `model_usage`, `permission_denials`, `session_id`, `structured_output` | Supports R-6 cost accounting and denial metrics |
| `SandboxSettings` | `enabled`, `autoAllowBashIfSandboxed`, `excludedCommands`, `allowUnsandboxedCommands`, `network`, `ignoreViolations`, `enableWeakerNestedSandbox` — **no `failIfUnavailable`** | **Open (§6.2).** W1 must resolve |
| `SandboxNetworkConfig` | `allowedDomains`, `deniedDomains`, `allowManagedDomainsOnly`, `allowUnixSockets`, `allowAllUnixSockets`, `allowLocalBinding`, … | Supports the §6.2 network and socket restrictions |
| `tools` preset type | an explicit list, or the preset `{"type":"preset","preset":"claude_code"}` | Explicit list chosen; the `Skill` requirement in an explicit list is **still [U]** and is W1's first check |
| Skills loading with `setting_sources=[]` | not exercised | **[U].** Fallback in §6.2 makes this non-blocking |
| SDK sandbox behaviour end-to-end | not exercised | **[U].** External OS sandbox is the control meanwhile |

### 16.1 Provider Evidence (as of 2026-09-21, v0.5)

Recorded so W1-O and W1-G start from evidence. Plan §5.12.1 carries the full matrix. **Nothing here is relied on until re-confirmed on the pinned version.**

| Item | Observed | Source | Status |
|---|---|---|---|
| Codex permission profiles | `:read-only`, `:workspace`, `:danger-full-access`; custom `[permissions.<name>]`, selected by `default_permissions` | S10 | Supports §6.5 |
| Codex Linux sandbox | bubblewrap + seccomp; Landlock as fallback | S10 | Nesting inside D11 is **[U]** |
| Codex network | Profile `network.enabled`; domain rules enforced only with `features.network_proxy` | S10 | Not relied on; the broker is the egress control |
| Codex endpoint override | `openai_base_url`; custom `[model_providers.<id>]` with `base_url` | S11 (excerpt) | Supports the model broker; confirm in W1-O |
| Codex shell tool removal | Not documented | S10 | **[U]** → PC-2 inertness test |
| Antigravity headless | `agy -p`; `--output-format text\|json\|stream-json`; `--json-schema`; `--model`; `--print-timeout` (default 5 min); `--sandbox` | S13 | Supports §6.5 |
| Antigravity headless permissions | Workspace read/write auto-allowed; shell soft-denied unless allowed; `permissions.allow` in `~/.gemini/antigravity-cli/settings.json`; `--dangerously-skip-permissions` | S13 | Allow-rules not relied on |
| Antigravity headless defect | `permissions.allow` ignored; processes hang past `--print-timeout`; **open** | S14 | Why PC-1 kill is controller-side |
| Antigravity auth | Cached credentials from an interactive login; no API-key mode documented first-party | S13; C2 [U] | Conflicts with PC-4 unless W1-G finds a key-less broker route |
| Antigravity endpoint override | Not documented | — | **[U]**; native-only expected |
| Antigravity MCP config | `mcp_config.json` path reported by third parties | C2 | **[U]** |
| Gemini CLI | Reported as superseded by Antigravity CLI | C2 | **[U]**; not used |

---

## 17. Sources

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
| R1 | K. Kamahori, S. Li, S. Peter, B. Kasikci, *VibeServe*, arXiv:2605.06068v1, 2026 — **preprint, not peer-reviewed**; structural inspiration only |
| R2 | uw-syfi, *VibeSys* repository README (MIT license) — https://github.com/uw-syfi/vibesys |
| V1 | Review of plan v0.2 and HLD v0.1 — `cx-feedback-solvalops-plan-hld.md` (2026-09-17) |
| V2 | Pre-coding review of plan v0.3 and HLD v0.3 — `cx-feedback-v0.3-before-coding.md` (2026-09-21). Conditional no-go pending the delivery definition; drives v0.4 |
| C1 | Competitive analysis — `ag-solvalops-competitive-analysis.md` (2026-09-17). **Market claims unverified; tagged [U]** (plan §1.2) |
| X1 | Direct inspection of `claude-agent-sdk` 0.2.154, 2026-09-17 (§16) |
| S10–S14, C2 | Codex and Antigravity documentation, the Antigravity headless defect, and third-party Antigravity articles, accessed 2026-09-21. Full entries and caveats in plan §14 (§16.1) |
| — | Parent plan: `solana-agave-node-ops-agent-plan-v0.5.md` |

All external sources accessed 2026-09-17. Re-verify during W1. **Note:** `plan-review-vs-vibeserve.md`, cited by earlier drafts, is not present in the repository; no claim in v0.3 depends on it.

---

## 18. 中文摘要（参考用，以英文为准）

**v0.5 代码实现与架构对齐（N-1 … N-17）：** 根据实际代码库（`valops/`、`tests/`、106 项全绿自动化测试）与实现备忘（`docs/IMPLEMENTATION-NOTES.md`）对设计进行完全对齐与勘误：
1. **事件存储扩展为五个专用端点**（§5.3）：新增 `store-observe` 套接字用于观测代理将工具采样转化为可引用的事实信号（N-1）；拆分 `store-agent-report` 套接字专供报告代理追加报告与读取（N-2），实现端点级身份与能力硬隔离。
2. **工作进程沙箱套接字通信**（§4.1, §6.2）：沙箱内通过绑定挂载（bind mount）套接字文件而非继承已连接描述符，确保内核 `SO_PEERCRED` 在 `connect()` 时准确捕获工作进程专属 UID，杜绝凭据混淆（N-3）。
3. **状态机流转对齐**（§5.2, §7.2）：裁判重试耗尽时转入终态 `handed_off` 并发出全量拒绝原因告警（N-4，对齐 R-3、§9 及 RB-2）；`report_no_action` 同样流转至 `judging` 由裁判依据核验项判定合理性（N-5）。
4. **终态操作语义明确**（§5.3, §7.2, §7.3）：终态（`resolved`、`handed_off`）仅接受报告追加、交接后的恢复观测存证（§7.3）以及控制器成本/轮次/步骤记账，严格禁止其他写入与状态转移（N-9）。
5. **裁判视图与模式硬拒绝**（§5.3, §5.7, §5.10）：裁判视图包含原始信号、待评测产物与技能前置条件，并包含确定性验证与恢复观测记录（N-6）；存储端强制在共识模式为 `unknown` 或不匹配时直接拒绝模式相关提案写入（N-7），在模型裁决前筑牢确定性防线。
6. **告警真实性与模型代理机制**（§5.7, §5.12）：报告告警的严重级、故障类别、首要假设与裁决结论由报告代理从已存事实记录中强制抽取填充，模型仅提供标签化摘要，杜绝虚构误报（N-8）；模型代理采用流式先转发、后异步写审计链策略（N-11）；用量不可解析时按保守估算上限记账（N-12）；原生 Anthropic 绑定显式禁用服务端拒答模型自动回退（N-10），坚守 D7 固定模型红线。
7. **运行权限与探针健壮性**（§4.3, §5.1, §10.2）：控制器服务仅保留 `CAP_SETUID`/`CAP_SETGID` 用于派生工作进程（N-14）；掉队检测基于连续 P-03 个采样的追赶距离趋势（N-15）；裁判隔离断言检查视图排除待评测产物后的内容（N-17）。

**v0.5 多提供方支持：** 支持 Claude、Codex、经 Antigravity 的 Gemini 三家模型提供方。工作进程内运行一个"适配器"（Claude SDK、`codex exec`、`agy -p` 或项目自写的原生 API 循环）；新增**模型代理 [12]**，唯一持有三家 API 密钥，是工作进程唯一的网络出口，并按绑定配置限定提供方与模型、统一执行轮次/令牌/美元上限、将所有模型请求写入审计链。**工作进程不持有任何提供方凭据。** 新增 §6.5 各适配器启动规范、M0A 新测试（提供方一致性 PC-1…PC-9、模型代理）、**PA 准入关口**（按配置）、运行手册 RB-14、§16.1 提供方证据附录。Claude 为参考配置，唯一位于 G1 关键路径；Codex、Antigravity 在并行轨道上逐一准入；G2 按配置分别授予。Antigravity 无头模式存在未关闭缺陷（忽略 `permissions.allow`、超时挂起），因本设计不依赖任何进程内管控，只影响准入，预计走原生适配器〔H〕。

**v0.4 状态（保持有效）：** 根据编码前评审（V2），结论为**"有条件不启动"**。G0 批准交付定义包之前不编写代码；G1（M0A 在真实而非模拟的边界上通过）之后才启动 M0B；G2（安全门槛**与**值班人员价值证据均达标）之后才进入 M1。关口、决策人与否决权见计划 §7.2。

**M0 定位：** 服务于**指定值班人员**、仅针对**一台 Agave 测试网验证节点**的**只读事故分析助手**，而非自主验证节点运维系统。产品假设、五类受支持故障（FC-1…FC-5）、watchtower 基线、报告/告警流程、反馈量表（FB-1…FB-6）与量化指标（Q-1…Q-8）**只在计划 §2.6 定义**，本 HLD 引用而不重复。

**v0.4 对本 HLD 的修改：**
1. **假设排名**：假设新增 `rank` 与 `step_session` 字段，存储端强制同一步骤内排名唯一且连续；"排名第一的假设"= 最近一次完成的诊断步骤中 rank 为 1 的假设，由值班人员按 FB-1 评分，取代 v0.3 无法度量的"正确排序的假设"。
2. **共识模式措辞统一**：声明值 + 三项观测输入交叉校验，共四项输入；集群特性查询未核实时该输入记为 `unavailable`，结果为 `unknown`。
3. **审计锚定最大延迟**：超过 P-19 时不再启动新的 LLM 步骤。
4. **降级运行手册 RB-1…RB-13**：每种故障模式均规定触发条件、自动行为、值班操作与退出条件；任何手册都不得以削弱管控的方式恢复服务。
5. **测试门槛分类**：确定性（D，100% 通过）与模型质量（MQ，冻结样本、可重复控制、置信下界判定、人工裁决）；M0A 全部测试须在真实 UDS/uid、真实沙箱后端、真实外部锚定存储、已固定版本的 SDK 与模型上运行才计入 G1。
6. **工作分解**：新增 W0（G0 交付包）、W19（评估支撑：故障注入、量表采集、评估框架）、W20（watchtower 基线采集）；W1 依赖 D1/D7 已固定。
7. **待决事项重组**：M0A 阻塞项 D1/D7、D3、D5、D6、D11、D14、D15、D16 均给出默认方案；D9 为 M0B 阻塞项；D13、D17 不再阻塞 M0 且排除于 M0 之外；D3 拆分，新增 D18（阶段四目标集群）。

**v0.3 设计要点（保持不变）：** 事件存储身份由传输层认证、智能体端不存在结案能力；单一审计定序器及外部锚定；四类进程、`PreToolUse` 钩子仅为纵深防御；SDK 配置修正与提示词内联回退；比较并交换、幂等键、仅 `awaiting_operator` 可转 `resolved`、`handed_off` 为终态；撤回"可用性风险为零"并限制观测资源；遥测健康事件类；不可变策略包；产出完整性校验。
