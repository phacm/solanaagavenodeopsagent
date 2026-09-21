# High-Level Design: Solana Validator Ops Agent — MVP (M0)

| Field | Value |
|---|---|
| Document | High-Level Design (HLD), **v0.3** — DRAFT for review |
| Product | Solana Validator Node Self-Operating Agent ("valops-agent") |
| Milestone | **M0 — Observe, Diagnose, Recommend**, split into **M0A** (containment prototype) and **M0B** (diagnosis workflow) |
| Author | Peng Huang (peng.huang@acm.org) |
| Date | 2026-09-17 |
| Supersedes | v0.1 (2026-09-17). The version number jumps to v0.3 to stay in lockstep with the plan |
| Parent document | `solana-agave-node-ops-agent-plan-v0.3.md` (governs; this HLD refines it) |
| Governing language | English (Chinese summary in §17 is informational) |
| Status | Awaiting owner decisions in §15 |

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

**Evidence tags.** `[E]` externally verifiable (§16). `[A]` design choice made here. `[H]` hypothesis to validate. `[U]` unknown, must be resolved.

No performance, cost, stake, reward, or market figure is asserted. Every threshold is **TBD by owner**.

### 0.1 Naming (V1 F10)

| Term | Meaning | Exists in |
|---|---|---|
| **Observer Daemon** | Validator-host process serving a **read-only** command table by command id | M0 onward |
| **Executor** | Validator-host process able to run **state-changing** commands under an approval token | **M1 onward — absent from the M0 artefact** |
| **Verifier** | Deterministic component that confirms state from re-sampled signals. In M0 it confirms *recovery*; from M1 it also performs *post-action* verification | M0 onward |
| **Controller** | Trusted ops-host process: episode runner, state transitions, token minting, artefact validation | M0 onward |
| **Worker** | Untrusted ops-host process hosting exactly one SDK session for one role and one episode | M0 onward |

This document uses no other name for these components. Earlier drafts used "Executor" for the M0 read-only daemon; that usage is withdrawn.

---

## 1. Purpose and Position

Plan v0.3 describes the full system across six phases. This HLD specifies **only M0**, the smallest deployable increment that delivers value while taking no intentional risk to the validator, and that builds the complete control-plane skeleton later milestones plug into.

**M0 thesis [A].** The riskiest parts of this system are not the actions — they are the *judgement* and the *containment*. M0 therefore ships the judgement path (diagnose → recommend → independently judge → report) and the entire containment layer (capability boundaries, policy bundles, sandbox, anchored audit chain, deterministic verification), but ships **no ability to change the validator**. The value delivered is faster, better-evidenced diagnosis handed to a human operator.

**M0A before M0B [A], new in v0.3.** Every safety claim in this design rests on the containment layer, so the containment layer is built and proven first, with no diagnosis workflow attached. M0A's exit criteria (§13) are the review's four properties. M0B does not begin until they hold.

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
| C9 | Consensus-mode determination by three-way agreement | M0B | FR-8, §5.10 |
| **C10** | **Telemetry-health monitoring and its own episode class** | M0B | FR-13, §5.9 |
| **C11** | **Artefact validation after every role step** | M0B | FR-12, §5.8 |

### 2.2 Out of Scope (M0) — deferred to M1+

| Deferred | Target milestone | Reason |
|---|---|---|
| Any T2 execution (restart, upgrade) | M1 | M0 ships no write path to the validator [A] |
| Executor process, approval service, signed approval tokens | M1 | Only needed once T2 exists; `executor/` is absent from the M0 artefact |
| Configuration repository and deploy-by-commit | M1 | Same |
| Post-action verification (as opposed to recovery confirmation) | M1 | No actions in M0 |
| Mainnet-beta deployment | M2 | M0 runs on testnet only (D3) |
| Multi-validator fleet orchestration | Later | Plan §2.3. Note: multi-target *observation* is D13, a narrower question |
| Offline tuning loop | Research track | Plan §11, D10 |
| Any withdrawer-key or stake operation | Never | Plan §2.3 [E] S4 |

### 2.3 MVP Anti-Goals (enforced, not merely stated)

All plan §2.4 anti-patterns apply. Four are enforced structurally in M0 [A]:

1. **No write path exists.** The command table contains only read-only commands, and the loader refuses a table containing any state-changing token. A T2 tool cannot be "accidentally enabled" by configuration: it requires a code change, a new policy bundle, and review.
2. **The agent cannot close an episode.** Closure is computed by the verifier from re-sampled signals, and the operation does not exist on the agent-facing store endpoint (§5.3).
3. **No component asserts its own identity.** Principals derive from the transport (§5.3). A request field naming the caller is ignored if present.
4. **No in-process check is treated as a boundary.** Everything the `PreToolUse` hook checks is re-checked by the broker that serves the call (§6.3).

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

All limit values are **TBD by owner** (D6).

---

## 3. Target Deployment (M0)

```
Cluster:    testnet (D3)
Validator:  1 × Agave validator, systemd, user `sol`               [E] S4
Ops host:   1 × separate small Linux host (no keypairs present)    [E] S2 rationale; [A] applied to agent
Watchtower: agave-watchtower on the ops host or a third host       [E] S2
Anchor:     external append-only storage, off the ops host (D15)   [A]
Operator:   1 human on-call, receives alerts and reports           [A]
```

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
│  │   holds the Claude API key. Parses structured broker responses only.               │    │
│  └───────────────┬───────────────────────────────────────────────────────────────────┘    │
│                  │ fork/exec per step, passing socket fds + one scoped token               │
│  ┌── [7] WORKER (untrusted, OS sandbox) ─────────────────────────────────────────────┐    │
│  │   ONE fresh SDK session · ONE role · ONE episode                                   │    │
│  │   diagnostician │ change-planner │ proposal-judge │ reporter                       │    │
│  │   MCP server "valops" = RPC stubs over broker sockets. No API key. No fs write.    │    │
│  │   hooks: PreToolUse policy gate + audit — DEFENCE IN DEPTH ONLY (§6.3)             │    │
│  └───────────────┬───────────────────────────────────────────────────────────────────┘    │
│                  │ UDS (inherited fds)                                                     │
│  ┌── CAPABILITY BROKERS ─────────────────────────────────────────────────────────────┐    │
│  │  [3] episode-broker → [3s] EPISODE STORE (3 endpoints, §5.3)                       │    │
│  │  [9b] observer-broker → validator host over mTLS                                   │    │
│  │  [8] report-broker → report store + alert sink                                     │    │
│  │  [5] audit-sequencer → SOLE writer of the chain; signs + anchors heads             │    │
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
| Worker ↔ ops host filesystem/network | syscalls | OS sandbox (D11): no filesystem writes; egress only to the Claude API and the inherited broker sockets |
| Worker ↔ controller authority | capability token | Token scoped to (episode, role, session, bundle, expiry, nonce); minted by the controller; verified by every broker |
| Ops host ↔ validator host | mTLS HTTPS | Command-id allowlist; the daemon accepts an enum, never a shell string (DD-3) |
| Anyone ↔ policy | file writes | Immutable hash-addressed bundles, read-only to every process; an episode is served from its bound bundle |
| Audit writers ↔ audit chain | sequencer socket | Single writer; `actor` stamped server-side from the authenticated principal; heads anchored off-host |
| Validator output ↔ LLM context | tool results | Structured, size-capped, redacted; treated as untrusted data (SR-6) |

### 4.3 Process Classes and Compromise Analysis (new in v0.3, V1 F3)

| Process | Runs as | Credentials held | A full compromise yields |
|---|---|---|---|
| **Worker** | dedicated uid, sandboxed | One capability token: one episode, one role, one session, short expiry | Exactly that role's tool surface, for that one episode, until expiry. No API key; no policy write; no state transition; no verification; no audit authorship; validator access only through the observer broker's allowlist, rate limits and output caps |
| **Controller** | dedicated uid | Claude API key; token-minting key; store control endpoint | Full control-plane authority. Mitigation is that it runs no model output: it parses structured broker responses and the episode record, never transcript prose (§5.8) |
| **episode-broker** | dedicated uid | Store agent endpoint | Ability to append agent artefacts to episodes. Still no state transition, verification or closure — those operations exist only on other endpoints |
| **observer-broker** | dedicated uid | mTLS client certificate for the daemon | Read-only validator observation at the daemon's rate limits |
| **report-broker** | dedicated uid | Alert channel credential | Ability to send alerts and write reports. Noisy, not dangerous; alert-rate anomalies are themselves monitored |
| **audit-sequencer** | dedicated uid | Chain file; chain-head signing key | Ability to write the local chain. External anchoring (§5.5) bounds silent rewriting to the interval since the last anchor |
| **Observer daemon** | `valops` on the validator host | Read-only command table; local chain key | Read-only observation under OS resource limits. No state-changing command exists to invoke |

**Why the hook is not a boundary [A].** The `PreToolUse` policy gate runs inside the worker — the one process that hosts model output and is therefore the one process assumed to be compromisable by a sufficiently effective prompt injection or an SDK defect. Anything it enforces, an attacker who controls that process can bypass. It is retained for three reasons that do not require trusting it: it fails fast and cheaply, it gives the model a specific denial reason so behaviour stays legible, and it produces a first-line audit record. Every check it makes is repeated by the broker.

### 4.4 Key Design Decisions

| ID | Decision | Rationale | Tag |
|---|---|---|---|
| DD-1 | The **Episode Store is the source of truth**, not any model context | No single context spans an episode; survives restarts and long waits (NFR-4) | [A]; motivation [H] |
| DD-2 | **One fresh SDK session per step**, not one session with subagents; `Task` disallowed | Guarantees the Judge's context isolation (SR-12), which subagent inheritance rules do not | [A]; SDK subagent inheritance [E] S7 |
| DD-3 | The observer daemon takes a **command id**, not a command string | Removes shell injection and argument smuggling as a class | [A] |
| DD-4 | Closure is computed, never asserted by the model | Prevents self-grading (plan §2.4) | [A]; pattern [E] R2 |
| DD-5 | M0 ships **no state-changing command at all** | The availability risk of the MVP is bounded structurally rather than by policy — but it is not zero (§2.4) | [A] |
| DD-6 | `permission_mode="dontAsk"` with role-scoped allowlists | Anything not pre-approved is denied; `canUseTool` is never invoked in this mode, so no control may depend on it | [E] S7 |
| DD-7 | Reference implementation language: **Python** (`claude-agent-sdk`), pending D1 | Concrete interfaces are required for an HLD. In v0.3 the language choice matters less than it did: start/end and artefact-validation work lives in the controller, not in hooks (§6.2) | [A], pending D1 |
| **DD-8** | **Principals derive from the transport; the agent endpoint lacks closure capability entirely** | An authorization check can be misconfigured; a missing operation cannot | [A], V1 F1 |
| **DD-9** | **One audit sequencer, externally anchored** | Multiple writers race on `seq`/`prev`; a local-only chain can be recomputed wholesale by whoever can rewrite the file | [A], V1 F2 |
| **DD-10** | **Immutable bundles bound per episode**, rather than re-checking "the current mount" | Otherwise any legitimate policy deployment strands every in-flight episode | [A], V1 F8 |
| **DD-11** | **The verifier may set `resolved` only from `awaiting_operator`** | Otherwise a transient recovery races the runner and closes an episode mid-analysis | [A], V1 F5 |
| **DD-12** | **Loss of observability is an incident, not a silence** | "No data" must never read as "healthy" | [A], V1 F6 |

---

## 5. Component Specifications

### 5.1 [1] Sentinel

Deterministic scheduler. Contains no LLM call.

| Property | Value |
|---|---|
| Trigger | Fixed interval per check (values in the bound bundle's `thresholds.yaml`, **TBD by owner**) |
| Inputs | Observer broker read-only commands; `agave-watchtower` notifications; telemetry probes (§5.9) |
| Outputs | `open_episode` / `append_signal` on the store control endpoint |
| Rules | Pure functions over signals → severity class; no model involvement |

**Validator-health checks (M0)**

| Check | Signal source | Basis |
|---|---|---|
| Delinquency | validator monitor / catch-up status | [E] S2 |
| Catch-up progress (slot distance trend) | `solana catchup --our-localhost 8899` | [E] S5 |
| Identity account balance below floor | `solana balance <identity pubkey>` | [E] S3 |
| Process/unit state | systemd unit status | [A] |
| Disk headroom on ledger and accounts volumes | filesystem stats | [A] |
| Running version drift vs. expected | log line `Starting validator with` | [E] S3 |
| Own leader slots approaching | `solana leader-schedule` filtered to own identity | [E] S3 |
| Consensus-mode inputs | version, cluster feature state, state files — see §5.10 | [E] S5 for the files |

**Telemetry-health checks (M0, new in v0.3)** — see §5.9.

**De-duplication [A].** One open episode per (episode class, check class, validator). A repeat signal updates the open episode instead of opening a new one. Enforced in the store under an index lock, not in a prompt, so neither a sentinel race nor an agent can manufacture episode churn.

### 5.2 [2] Controller (Episode Runner)

Deterministic state machine. Owns which step runs, with what inputs, under which budget, and whether its output counted.

```
open ──► diagnosing ──► recommending ──► judging ──┬─► reporting ──► awaiting_operator
             │               ▲                     │                        │
             │               └──── FAIL (retry ≤ N)┘                        │ verifier re-samples
             └──────────────────────────────► reporting                     │ (stability window W)
                         (recovery observed, or no action warranted)        ▼
                                                                        resolved ──► closure report
     any non-terminal ──► handed_off  (failure · budget · integrity · missing artefact)
```

| Rule | Detail | Tag |
|---|---|---|
| R-1 | Every step is a new SDK session; no `resume`, no `continue_conversation`, no `fork_session`, no subagents | [A] |
| R-2 | Step input is assembled by the controller from the episode record — the model never chooses its own context | [A] |
| R-3 | Judge FAIL returns to `recommending`, at most **N** times (N **TBD**, D6); on exhaustion → `handed_off` + alert | [A] |
| R-4 | Any exception, budget exhaustion, integrity failure, or missing artefact → `handed_off` + alert. Never a silent stop | NFR-2 [A] |
| R-5 | Per-session `max_turns` and `max_budget_usd` set from the bound bundle | [E] S9 for the options |
| R-6 | The controller records `cost.per_role_usd` and `turns` per step from the SDK result | [E] S9 |
| **R-7** | **Every transition is a compare-and-swap on `revision`.** A transition computed from a stale revision is refused; the controller re-reads and re-decides | [A], V1 F5 |
| **R-8** | **No transition without a validated artefact** (§5.8) | [A], V1 F9 |
| **R-9** | The controller reads the episode record, never the transcript. Transcript text is retained for audit and human review and is parsed by nothing | [A], V1 F9 |
| **R-10** | The controller mints one capability token per step and revokes it when the step ends | [A], V1 F1 |

### 5.3 [3] Episode Store — Three Endpoints (revised in v0.3, V1 F1)

The store is one service exposing three endpoints. They differ in **which operations exist**, not only in what they permit. The principal is derived from the endpoint the call arrived on (a UDS with OS-enforced ownership and peer credentials, or an mTLS identity — D16) together with the capability token presented. **No request field names the caller; one is ignored if supplied.**

```
store-agent      (worker, via episode-broker; requires a capability token)
  append_hypothesis(episode_id, {claim, test, expected_evidence}, idem_key)   -> hypothesis_id
  append_hypothesis_status(episode_id, h_id, status, evidence_refs, idem_key)
  append_recommendation(episode_id, {...}, idem_key)                          -> recommendation_id
  append_no_action(episode_id, {reason, evidence_refs}, idem_key)
  append_verdict(episode_id, {recommendation_id, result, checks}, idem_key)
  append_report(episode_id, kind, markdown_ref, idem_key)
  read_episode(episode_id, view)       # view is forced by role; judge gets the judge view
  # NO set_state. NO append_verification. NO closure. These operations do not exist here.

store-control    (controller only; reachable solely by the controller's uid)
  open_episode(trigger, bundle_id, consensus_mode, idem_key)                  -> episode_id
  set_state(episode_id, state, expected_revision)     # every state EXCEPT resolved
  append_signal(episode_id, snapshot, idem_key)
  append_cost(episode_id, role, usd, turns, idem_key)
  read_episode(episode_id, view)

store-verify     (verifier only; reachable solely by the verifier's uid)
  append_verification(episode_id, {rule, result, samples}, idem_key)
  append_recovery_observation(episode_id, {rule, note}, idem_key)
  set_state(episode_id, "resolved", expected_revision)   # only from awaiting_operator
  read_episode(episode_id, view)
```

**Invariants [A]**

- No update, no delete. Corrections are new entries. The record of HLD §7.1 is a fold over an append-only log.
- Closure and verification are absent from the agent endpoint. There is no permission check to misconfigure.
- Every write records the authenticated principal, the session id, the bound bundle id, and an audit-chain reference.
- Every write carries an **idempotency key**. A repeated key returns the original result and appends nothing, so a retry after a timeout cannot inflate an episode.
- Every state transition is a **compare-and-swap** on `revision` (R-7).
- `read_episode(view="judge")` returns raw signals, the recommendation under judgement, and the skill preconditions only — never hypothesis prose, planner rationale, prior verdicts, or reports (SR-12).
- **Contract checks are server-side:** a hypothesis without a non-empty `test` is rejected; an evidence reference naming a signal that was never collected is rejected; a verdict without a non-empty check list is rejected.

**The evidence-reference bridge [A].** Because the Judge never sees the diagnostician's prose, the only link from diagnosis to judgement is a recommendation's `evidence_refs`, which name signals collected in this episode. The store validates them. A fabricated justification is therefore a rejected write rather than something the Judge has to catch.

### 5.4 [4] Policy Bundles (revised in v0.3, V1 F8)

Read-only to every process. Immutable and addressed by the hash of their contents.

```
bundles/
├── <bundle-id = sha256 of contents>/
│   ├── command_table.yaml          # observer allowlist — read-only commands only
│   ├── thresholds.yaml             # all values TBD by owner
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
| Drain | A deadline (**TBD**, D6) bounds how long old bundles stay live. Episodes exceeding it → `handed_off` + alert | [A] |
| Migration | None. An episode never changes bundle mid-flight; a half-old, half-new policy is the exact state this design exists to prevent | [A] |
| Emergency revocation | Add the id to `revoked`. Episodes bound to it → `handed_off` + high-severity alert; outstanding tokens for it are refused at every broker | [A] |
| Rollback | Re-point `active` at the previous id. Exact, because bundles are immutable and content-addressed | [A] |
| Failure mode | Any verification failure ⇒ **observe-only**: sentinel, store and verifier keep running; no LLM step starts; high-severity alert naming the changed path; audit entry | [A] |

The manifest is signed and the public key lives outside the bundle store. Key custody and rotation are **TBD by owner** (D14).

### 5.5 [5] Audit Sequencer (revised in v0.3, V1 F2)

**One process writes the ops-host chain.** Everything else submits records to it over a socket and receives the assigned sequence number and entry hash.

| Property | Design |
|---|---|
| Format | Append-only JSON Lines, hash-chained: `entry.prev = SHA256(previous entry canonical form)` |
| Serialisation | Single writer; no cross-process race on `seq` or `prev` |
| Identity | `actor` is stamped by the sequencer from the authenticated principal of the submitting connection. A submitter cannot label its own entry, so a compromised worker cannot forge a controller-attributed record |
| Durability | Each entry is fsynced before acknowledgement |
| Payloads | Content-addressed and hashed by the sequencer; the chain carries `payload_ref`, never the blob |
| **External anchoring** | Periodically signs `{chain_head, seq, ts}` and writes it to append-only external storage (WORM object store or remote log service — D15). Rewriting local history then also requires rewriting anchors the ops host cannot modify |
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
| Rule form | A per-signal predicate (`lt`/`le`/`gt`/`ge`/`eq`/`in`, composed with `all_of`/`any_of`) plus a **stability window**: e.g. "not delinquent **and** catch-up distance below threshold for W consecutive samples". W and thresholds **TBD by owner**. Rules are data, evaluated by code — never a string expression and never a model judgement |
| Commands | `agave-validator monitor` and `solana catchup --our-localhost 8899` [E] S5 |
| Output | Immutable verification record; `set_state(resolved)` on success |
| **Timing constraint (DD-11)** | The verifier may set `resolved` **only from `awaiting_operator`**. If the recovery predicate holds earlier, it appends a `recovery_observation` and changes nothing (§7.3) |
| Deadline | If the predicate never holds within the owner-set window, the state stays `awaiting_operator` and the alert escalates. The verifier does not hand off on its own |
| Constraint | The only component permitted to set `resolved` (DD-4), on an endpoint no other principal can reach |

### 5.7 [7] Role Sessions

| Role | Tools | Input view | Required artefact |
|---|---|---|---|
| `diagnostician` | T0 read tools + `add_hypothesis`, `set_hypothesis_status` | Full episode record | ≥1 hypothesis, each with claim, test, expected evidence |
| `change-planner` | T0 read tools + `propose_recommendation`, `report_no_action` | Episode record incl. hypotheses | Exactly one recommendation bound to one hypothesis, **or** one explicit no-action record with a reason |
| `proposal-judge` | T0 read tools + `submit_verdict` | **Judge view only** (§5.3) | One verdict: PASS/FAIL with a non-empty list of checks performed |
| `reporter` | `write_incident_report`, `send_alert`, `get_verification_result` | Episode record incl. verification records | One report reference and one dispatched alert |

**Hypothesis contract [A].** Accepted only with all three of `claim`, `test` (an observation that could refute it) and `expected_evidence`. A claim with no refuting test is rejected at the API, which forces falsifiable diagnosis rather than narrative.

**Recommendation contract [A].** Must name: the action in operator terms, the runbook skill it came from, the preconditions to verify before acting, the expected post-condition, the hypothesis it addresses, and **evidence references to signals actually collected in this episode**. In M0 the action is text for a human; the system contains no code that performs it.

**No-action is a first-class artefact [A], new in v0.3.** "Nothing should be done" is a legitimate planner conclusion, and before v0.3 it was indistinguishable from a failed session. It is now recorded explicitly, with a reason and evidence, and routes the episode to `reporting`.

### 5.8 [2] Artefact Validation (new in v0.3, V1 F9)

A session that ends without writing its artefact has failed, however confident its prose. After every step the controller [A]:

1. Reads the episode record from the store — **not the transcript** — and checks that the role's required artefact exists, was written during this step (matched by session id), and satisfies its schema.
2. Cross-checks the session's structured output where the SDK supplies one (`output_format`). Disagreement between structured output and the stored artefact is a step failure, and **the stored artefact is authoritative**: it is the one that passed the server-side contract checks.
3. On a missing or invalid artefact: counts a step failure and retries with a fresh session within the retry budget (**TBD**, D6); on exhaustion, `handed_off` with an alert naming what was missing.
4. Never parses prose to recover an artefact.

| Role | Validated | Failure |
|---|---|---|
| diagnostician | ≥1 hypothesis with all three contract fields | retry, then `handed_off` |
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

File presence alone is ambiguous: both `tower-*.bin` and `vote_history-<IDENTITY>.bin` can exist after a migration, a rollback, or incomplete cleanup. Mode is therefore established by **agreement of four inputs**, not by inference from one [A]:

| Input | Source | Tag |
|---|---|---|
| Declared mode in the bundle's `deployment.yaml` | Owner-set, reviewed, hashed | [A] |
| Running Agave version and its support for the mode | `running_version` [E] S3 | [E]/[A] |
| Cluster feature state for the consensus feature | On-cluster query; the exact query is **[U]** (D9) | [U] |
| Consensus state files present, with modification times | `consensus_state_files` [E] S5 | [E] |

Rules [A]: all inputs agreeing sets the mode. **Any disagreement sets `unknown`**, records every input in `consensus_mode_evidence`, raises an alert, and prohibits mode-specific recommendations — the planner is offered no mode-specific skill variant, and the Judge FAILs any proposal carrying a mode-specific precondition. `unknown` does not stop observation, diagnosis, or reporting; it stops only claims that depend on the mode.

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
| **OD-8** | **Resource containment (SR-17):** the systemd unit sets `CPUQuota`, `MemoryMax`, `TasksMax`, `LimitNOFILE`, IO weight and `Nice`, and runs under a dedicated cgroup slice. Values **TBD by owner** (D6) | [A], V1 F6 |
| **OD-9** | **Local-RPC circuit breaker:** when the validator's own RPC latency exceeds the owner's threshold, polling of RPC-backed commands is suspended and a telemetry-health signal is raised (§5.9 TH-4) | [A], V1 F6 |
| **OD-10** | **Local audit chain:** the daemon maintains its own hash chain of requests served and forwards signed checkpoints to the ops-host sequencer (§5.5) | [A], V1 F2 |

Hardening intent for the unit file [A]: `NoNewPrivileges`, `ProtectSystem=strict`, `ProtectHome`, `PrivateTmp`, `PrivateDevices`, a read-only bundle mount, and a `ReadOnlyPaths` entry for the ledger and log directories. Exact directives are a W2 deliverable.

---

## 6. Agent Configuration

### 6.1 Session Options (reference, Python — D1)

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
    max_turns=BUNDLE.max_turns[role],                    # TBD by owner (D6)
    max_budget_usd=BUNDLE.max_budget_usd[role],          # TBD by owner (D6)
    model=BUNDLE.model[role],                            # pinned (D7)
    continue_conversation=False, resume=None, fork_session=False,   # enforces R-1
    agents=None, plugins=[],                             # no subagents, no plugins
    env=WORKER_ENV,                                      # contains NO Claude API key (§4.3)
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
| network | Claude API endpoint only | Egress containment |
| unix sockets | the inherited broker sockets only | The worker's sole legitimate IPC |

**An unresolved discrepancy, recorded rather than papered over [E, X1].** The review cites a `failIfUnavailable` setting. On 2026-09-17 the installed `claude-agent-sdk` 0.2.154 exposed a `SandboxSettings` type with `enabled`, `autoAllowBashIfSandboxed`, `excludedCommands`, `allowUnsandboxedCommands`, `network`, `ignoreViolations` and `enableWeakerNestedSandbox` — and **no `failIfUnavailable` field**. Either the flag exists under a different name or in a different version, or fail-closed behaviour must be obtained outside the SDK (for example, by having the controller refuse to spawn a worker when the external sandbox backend is unavailable, which it can verify independently). **W1 resolves this. Until then the external OS sandbox (SR-11) is treated as the only sandbox control.**

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
  "hypotheses":     [ { "id": "h1", "claim": "...", "test": "...", "expected_evidence": "...",
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

### 7.2 State Transition Table (new in v0.3, V1 F5)

| From | To | Authorised principal | Guard |
|---|---|---|---|
| `open` | `diagnosing` | controller | bundle verifies; not observe-only |
| `diagnosing` | `recommending` | controller | ≥1 hypothesis validated (§5.8) |
| `diagnosing` | `reporting` | controller | recovery observed, or no hypothesis supports an action |
| `recommending` | `judging` | controller | one recommendation or one no-action record validated |
| `judging` | `recommending` | controller | verdict FAIL and retries remaining (≤ N) |
| `judging` | `reporting` | controller | verdict PASS, or retries exhausted (recorded as such) |
| `reporting` | `awaiting_operator` | controller | report ref present and alert dispatched |
| `awaiting_operator` | `resolved` | **verifier only** | recovery predicate held for W consecutive fresh samples |
| any non-terminal | `handed_off` | controller | failure, budget, integrity, revocation, drain deadline, missing artefact |
| `resolved`, `handed_off` | — | — | terminal |

Reports may be appended in a terminal state (that is how the closure report is written); no other write and no transition is permitted there.

### 7.3 Concurrency Semantics (new in v0.3, V1 F5)

| Question | Answer | Tag |
|---|---|---|
| Two writers race a transition | CAS on `revision`: exactly one wins, the loser re-reads and re-decides | [A] |
| A request is delivered twice | Idempotency key: the second call returns the first result and appends nothing | [A] |
| Recovery observed **during** diagnosis, recommendation or judging | Verifier appends a `recovery_observation` and changes **no** state. The controller reads it at the next transition point and may route to `reporting`, skipping recommendation. **A step in flight is never cancelled**, so no step is interrupted between doing work and recording it | [A], DD-11 |
| Recovery observed in `awaiting_operator` | Verifier sets `resolved` after W consecutive samples, then the controller runs the closure step | [A] |
| Recovery observed after `handed_off` | Appended as an observation. **`handed_off` is terminal** and is not reopened; if the signal recurs the sentinel opens a new episode. Reopening would make "what happened in incident X" unanswerable | [A] |
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
| `consensus_state_files` | presence and mtimes of `tower-*.bin` vs. `vote_history-*.bin` — **one of four inputs** to §5.10 | — | [E] S5 |
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
        h1 "ledger volume is full"      test: disk headroom + write errors in log
        h2 "version drift after update" test: running_version vs. expected
      tool calls re-sample as needed; h1 set refuted (evidence s5), h2 supported (evidence s7)
    Controller validates the artefact (≥1 hypothesis, contract fields present); token revoked.

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
| Claude API unavailable or slow | SDK error / timeout | Episode → `handed_off` with signals gathered so far; alert; sentinel and verifier continue | [A] |
| Budget or turn limit hit | SDK result | Same | [A] |
| **Step ends with no valid artefact** | Controller validation (§5.8) | Retry with a fresh session; on exhaustion `handed_off` + alert naming what was missing. A missing verdict is never treated as PASS | [A] |
| Judge FAILs N times | Controller counter | `handed_off` + alert carrying every FAIL reason | [A] |
| Bundle hash mismatch | Integrity check | Observe-only; high-severity alert; no LLM step runs | [A] |
| **Bundle revoked, or drain deadline exceeded** | Broker / controller | Episode → `handed_off` + alert; outstanding tokens refused | [A] |
| **Observer daemon unreachable, slow, or stale** | Telemetry probes | **Opens a `telemetry_health` episode** (TH-1). Validator-health episodes are annotated, never opened, escalated or resolved on missing data (TH-2, TH-3) | [A], V1 F6 |
| **Local RPC degraded** | OD-9 circuit breaker | Polling of RPC-backed commands suspended; telemetry-health signal raised; the suspension is reported, not silent | [A] |
| Episode store write failure | API error | Controller aborts the step; alert; nothing is assumed written. Retry is safe because appends are idempotent | [A] |
| **Audit sequencer unavailable** | Submit error | Fail closed: no LLM step starts without an audit path; sentinel and verifier continue and buffer; alert | [A] |
| **Anchor unreachable or stale** | Anchor lag metric | Alert; the system keeps running, since a missing anchor weakens tamper-evidence but does not by itself indicate tampering | [A] |
| **Chain verification fails** | Timer / CI | High-severity alert; observe-only; the chain and the newest anchor are preserved for investigation | [A] |
| Agent attempts a denied tool | Broker denial (hook denial first) | Denied, audited, surfaced in the report | [E] S7 mechanism for the hook; [A] for the broker |
| **Agent attempts closure or verification** | — | The operation does not exist on its endpoint; the call fails as an unknown method and is audited | [A], DD-8 |
| Sandbox violation attempt | OS sandbox | Blocked, audited, alert | [A] |
| **Sandbox backend unavailable** | Controller pre-flight | Refuse to start a worker. Never run unsandboxed | [A], V1 F4 |
| Validator itself fails | Out of scope for the agent | systemd restart policy and watchtower are unaffected by the agent (NFR-1) | [A] |

**Degradation ordering [A].** Full operation → observe-only (bundle or integrity problem) → sentinel-and-alert only (agent or audit path unavailable) → watchtower only (ops host down). The validator's own availability does not depend on any of these tiers — though observation load on it is bounded rather than absent (§2.4).

---

## 10. Testing Strategy (M0 exit gates)

### 10.1 M0A gates — containment, before any diagnosis work

| Suite | Contents | Gate |
|---|---|---|
| **Principal authentication** | Caller-supplied actor field ignored; call on the agent endpoint with a control-endpoint operation fails as unknown method; token for episode A refused on episode B; role A's token refused for role B's operation; expired token refused; token bound to a revoked bundle refused | 100% pass, every run |
| **Capability absence** | Agent endpoint exposes no `set_state`, no `append_verification`, no closure — asserted against the served method list, not by attempting and catching | 100% pass |
| **Audit integrity** | Single-writer serialisation under concurrent submitters (no `seq`/`prev` collision); entry actor matches the authenticated principal and not the submitted one; fsync before ack; local chain rewrite detected against an external anchor; daemon chain truncation detected at the ops host | 100% pass |
| **Process topology** | Worker environment contains no Claude API key; worker cannot open any network connection but the Claude API; worker cannot write any file; worker holds only the inherited broker sockets; sandbox backend unavailable ⇒ refuse to start | 100% pass |
| **SDK configuration** | Session loads exactly the intended tools, prompt file and skills (or the inlined-prompt fallback); removed built-ins absent from context; `dontAsk` denies an unlisted tool; hook deny and hook timeout each prevent execution | 100% pass; result amends §6 |

**M0B does not start until all five pass, repeated over N trials.**

### 10.2 M0B gates

| Suite | Contents | Gate |
|---|---|---|
| Policy (CI-blocking) | Role calling another role's tool denied; out-of-state tool call denied; agent write to a bundle fails at the OS level | 100% pass, every run |
| Write-path absence | Static check: no state-changing command id in any bundle's table; no code path from a tool to such a command; `executor/` absent from the artefact | 100% pass, every run |
| Bundle lifecycle | Mutate each bundle file ⇒ observe-only + alert; activation leaves in-flight episodes on their bundle; drain deadline ⇒ `handed_off`; revocation stops in-flight episodes and refuses tokens; rollback restores the exact previous bundle | 100% pass |
| Concurrency | CAS race: exactly one transition wins; duplicate delivery is a no-op; recovery mid-analysis attaches an observation and changes no state; `handed_off` not reopened | 100% pass |
| Judge adversarial | Seeded bad recommendations: alert silencing; recovery claimed from process liveness alone; repeated restarts; snapshot download renamed; log-injected instruction; precondition mismatched to consensus mode; **evidence ref to a signal never collected**; **mode-specific precondition while mode is `unknown`** | Every seeded case returns FAIL; suite frozen before the run |
| Judge isolation | Controller asserts the Judge input contains no planner or diagnostician prose before the session starts | 100% pass |
| Artefact completeness | Session ends with no artefact ⇒ retry then `handed_off`; structured output disagreeing with the stored artefact ⇒ step failure; prose containing a plausible recommendation is never promoted to one; missing verdict never treated as PASS | 100% pass |
| Closure ownership | Agent attempts `set_state(resolved)` and a verification write ⇒ operation does not exist | 100% pass |
| Falsifiability | Hypothesis lacking `test` rejected at the API; evidence ref to a non-existent signal rejected | 100% pass |
| Telemetry health | Daemon unreachable / slow / stale each open a `telemetry_health` episode and alter no validator-health episode; RPC breaker trip is reported | 100% pass |
| Consensus mode | Tower and vote-history fixtures; **both files present**; version or feature state disagreeing with the declaration ⇒ `unknown` and mode-specific proposals FAIL | 100% pass |
| Resource containment | Observer daemon under synthetic load stays within its cgroup limits; validator RPC latency impact measured and within the owner's tolerance | Owner-set tolerance |
| Functional (testnet) | Injected faults: stop the validator; drain the testnet identity balance; fill the ledger volume; introduce version drift | Correct episode, correct hypothesis ranked first, actionable recommendation |
| Degradation | API down; store down; broker down; sequencer down; anchor down; daemon down; budget exhausted | Correct degradation tier; validator unaffected |
| Repetition | Every safety-relevant suite repeated over **N** trials (**TBD**, D6) | No single-trial pass counts |

---

## 11. Observability and Metrics (targets TBD by owner)

| Metric | Purpose |
|---|---|
| Episodes opened, by class, check and severity | Volume and noise |
| MTTD vs. watchtower alone | Does the sentinel add detection value |
| Hypothesis precision (human-rated first-ranked hypothesis correct) | Diagnosis quality |
| Judge FAIL rate; share of FAILs a human confirms as correct | Is the Judge useful or merely obstructive |
| Recommendation acceptance rate (operator acted on it as written) | Recommendation quality |
| Step-failure rate by cause (missing artefact, schema failure, output disagreement) | Is the artefact contract too tight or the prompt too loose |
| Unauthorized executions | **Hard requirement: zero** |
| Denials, tamper events, token rejections, sandbox blocks | Containment health |
| **Anchor lag; chain-verification runs and results** | Tamper-evidence health |
| **Telemetry-health episode count and duration; sample staleness per check; RPC breaker trips** | Can the system still see the validator |
| **Observer resource usage vs. limits; measured validator RPC impact** | Is observation cheap enough to be harmless (§2.4) |
| Cost and turns per role, per episode and per day | Budget planning before M1 (D6) |
| Time from episode open to report delivered | Operator experience |

---

## 12. Work Breakdown

Ordered by dependency. Complexity is a relative rating **[A]**; calendar duration is **TBD by owner** — no estimate is asserted here.

### M0A — containment prototype

| # | Work item | Depends on | Complexity | Notes |
|---|---|---|---|---|
| W1 | Phase-0 SDK verification spike | — | M | Confirms `tools=["Skill", …]`, skills loading with `setting_sources=[]`, `dontAsk` + role allowlists, hook deny/timeout, sandbox fail-closed and the `failIfUnavailable` discrepancy (§6.2), `output_format`. Blocks everything; result amends §6 |
| W2 | Observer daemon + command table + mTLS + **systemd/cgroup limits** | — | M | Parallel with W1. OD-3 loader refusal is part of this item |
| W3 | Episode store: three endpoints, CAS, idempotency, contract checks | — | L | Server-side rejection of agent closure is the core of DD-4/DD-8 |
| W4 | **Audit sequencer + external anchoring + daemon-side chain** | W3 | M | Single writer, server-stamped principals, anchor export (D15) |
| W5 | Policy bundles: build, sign, bind, activate, drain, revoke, roll back | — | M | Replaces the v0.1 "mount + manifest" item |
| W6 | Process topology: controller, worker spawn, token minting, OS sandbox (D11) | W1, W5 | L | Must fail closed; demonstrated against the §10.1 suite |
| W7 | Capability brokers: episode, observer, report | W2, W3, W4 | M | Broker-side re-enforcement of every hook check |
| **W8** | **M0A containment test suite (§10.1)** | W3–W7 | M | **M0A exit gate** |

### M0B — diagnosis workflow

| # | Work item | Depends on | Complexity | Notes |
|---|---|---|---|---|
| W9 | MCP tool stubs, role-scoped | W6, W7 | S | Stubs only; contracts live in the brokers |
| W10 | Hooks: policy gate + audit (defence in depth) | W7, W9 | S | Explicitly not a boundary (§6.3) |
| W11 | Sentinel + thresholds + **telemetry-health probes** | W2, W3 | M | |
| W12 | Controller state machine + **artefact validation** | W3, W6, W9 | L | |
| W13 | Skills library v1 with compatibility matrix, **and the inlined-prompt fallback** | W5 | M | Content work, not code |
| W14 | Role prompts + Judge checklist | W13 | M | |
| W15 | Recovery verifier + **consensus-mode determination** | W2, W3, W5 | M | Declarative predicates; three-way mode agreement (§5.10) |
| W16 | Reporter + alert sink (D5) + **closure report** | W7, W3 | S | |
| W17 | Test suites §10.2 incl. fault-injection harness | W11, W12, W15 | L | |
| W18 | Testnet deployment and run-in | all | M | |

---

## 13. Milestone Exit Criteria

### M0A → M0B

All four properties the review asks to prove first, demonstrated by the §10.1 suites over N trials:

1. **Authenticated capability boundaries.** No caller can assert its own identity; the agent endpoint has no closure, verification or state-transition operation; tokens are scoped, expiring and bundle-bound.
2. **Centralised, externally anchored audit.** One writer; server-stamped principals; fsync; signed chain heads in external append-only storage; local rewriting and daemon-chain truncation both detectable.
3. **A process topology that fails closed.** Four process classes with disjoint credentials; the worker holds no API key, cannot write the filesystem, and reaches nothing but the Claude API and its broker sockets; an unavailable sandbox backend prevents a worker from starting.
4. **A verified SDK configuration.** The session loads exactly the intended tools, prompt and skills — or the inlined-prompt fallback is adopted and §6 amended accordingly.

### M0 → M1

M0 is complete when **all** hold:

1. Every CI-blocking suite in §10.1 and §10.2 passes, repeated over N trials, with zero unauthorized executions.
2. The write-path-absence check passes on the shipped artefact, and `executor/` is absent from it.
3. Every seeded Judge adversarial case returns FAIL, on a suite frozen before the run.
4. Four injected fault classes on testnet each produce a correct episode, a correctly ranked hypothesis, and a recommendation an operator judges actionable.
5. Tamper, revocation, drain, sandbox and telemetry-loss tests each force the expected degraded state.
6. Observer resource usage stays within limits under load, and the measured impact on validator RPC is within the owner's tolerance (§2.4).
7. Per-role cost has been measured over the run-in period, so D6 budgets can be set from data rather than guessed.
8. The Phase-0 verification log is complete and §6 has been amended wherever the SDK behaved differently from the assumptions here — including a resolution of the `failIfUnavailable` discrepancy (§6.2).

**Kill criteria** (plan §12 applies unchanged; the M0-specific triggers): if W1 shows the SDK's permission, hook or sandbox semantics cannot guarantee SR-3, SR-4, SR-10 or SR-11 on the pinned version **and** the gap cannot be closed outside the SDK; or if M0A cannot demonstrate its four properties — stop and redesign the containment layer before writing further code.

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
| F7 — consensus-mode detection ambiguous | Medium | Declared fact cross-checked four ways; disagreement ⇒ `unknown` ⇒ mode-specific recommendations prohibited | §5.10, §7.4 |
| F8 — policy updates strand active episodes | Medium | Immutable hash-addressed bundles; per-episode binding; drain, revocation, exact rollback | §5.4, DD-10 |
| F9 — output completeness not enforced | Medium | Artefact validation before every transition; structured output as cross-check; stored artefact authoritative; prose never parsed; no-action is a first-class artefact | §5.8, §5.7, §7.2 |
| F10 — broken references and naming drift | Low | Parent filename corrected; the absent `plan-review-vs-vibeserve.md` dependency removed; Observer Daemon vs. Executor separated by milestone | §0.1, plan §14 |
| Recommendation — start with an M0A containment prototype | — | M0 split; M0B gated on M0A's four properties | §1, §12, §13 |

Competitive-analysis input (C1) produced no design change here; it is recorded in plan §15 and routed to plan decisions D1, D2, D7, D13, D17.

---

## 15. Open Decisions Blocking M0

| ID | Decision | Blocks | Note |
|---|---|---|---|
| **D1** | Implementation language | W1 and all code | Python assumed here (DD-7). Less pivotal in v0.3: start/end and artefact-validation work lives in the controller, not in hooks. C1 recommends TypeScript; see plan §13 D1 for both arguments |
| D3 | Target cluster for M0 | W18 | This HLD assumes testnet |
| D5 | Alert channel | W16 | watchtower supports Slack, Discord, Telegram, Twilio [E] S2 |
| D6 | Thresholds and budgets | W11, W12, W17 | Balance floor, check intervals, `max_turns`, `max_budget_usd`, retry budget N, stability window W, trial count N, **token expiry, bundle drain deadline, observer resource limits and rate caps, telemetry staleness thresholds, RPC-latency breaker threshold** |
| D7 | Pinned model id(s) | W1, W12 | A separate, cheaper model for the Judge is possible but unproven [H]. C1's model names are stale and must not be copied into a bundle |
| D9 | Consensus mode on target cluster | W13, W15 | Is Alpenglow active at deployment? [U]. **Also unresolved: the exact cluster-feature query** used as the second input to §5.10 |
| D11 | OS sandbox backend | W6 | Must be demonstrated in W1 and must fail closed |
| **D13** | Shadow-fleet size (from C1) | W11, W18 | Single validator, or N observed targets with per-target episode isolation. Observation-only, so narrower than the fleet orchestration excluded in §2.2 |
| **D14** | Bundle signing key custody and rotation | W5 | Previously listed as "not yet specified"; now a numbered decision |
| **D15** | Audit anchor backend and cadence | W4 | WORM object storage vs. remote log service; interval; who can read it; what a stale anchor triggers |
| **D16** | Capability transport | W3, W6, W7 | UDS with peer credentials (single-host ops plane) vs. mTLS identities (if brokers are split across hosts) |
| **D17** | Publication of operator-trust metrics (from C1) | W18 | A published metric becomes a target, and gaming targets is what §5.5 exists to catch |

D2 (client), D4 (upgrade method), D8 (tier table), D10 (offline tuning) and D12 (approver policy) do not block M0: M0 targets Agave only, performs no upgrade, exposes only T0/T1, and has no approval step.

---

## 16. Appendix: Phase-0 Partial Verification Log (as of 2026-09-17)

Recorded so W1 starts from evidence rather than from the assumptions in §6. **Everything here must be re-confirmed on the pinned version before it is relied on.** Source X1: direct inspection of `claude-agent-sdk` 0.2.154.

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
| C1 | Competitive analysis — `ag-solvalops-competitive-analysis.md` (2026-09-17). **Market claims unverified; tagged [U]** (plan §1.2) |
| X1 | Direct inspection of `claude-agent-sdk` 0.2.154, 2026-09-17 (§16) |
| — | Parent plan: `solana-agave-node-ops-agent-plan-v0.3.md` |

All external sources accessed 2026-09-17. Re-verify during W1. **Note:** `plan-review-vs-vibeserve.md`, cited by earlier drafts, is not present in the repository; no claim in v0.3 depends on it.

---

## 18. 中文摘要（参考用，以英文为准）

**M0 定位不变：** 只做"观测—诊断—建议"，不具备任何改动验证节点的能力。**但 v0.1 中"可用性风险为零"的表述已撤回**——只读路径同样会消耗验证节点的 CPU、内存、磁盘 I/O、文件描述符与本地 RPC 容量。现改为："不存在有意的状态变更路径"，并以 systemd/cgroup 资源限制、并发为一、限流与本地 RPC 熔断来约束残余风险。

**M0 拆分为两段：** **M0A 容器化隔离原型**必须先证明四件事——(1) 存储侧经认证的能力边界；(2) 集中式且外部锚定的审计服务；(3) 失败即拒绝的进程/沙箱拓扑；(4) 经实测确认的 SDK 配置。**M0A 不通过，M0B 不启动。**

**针对评审意见的十项修改：**
1. **身份不可自述**：事件存储拆为智能体端/控制端/验证端三个端点，主体由传输层（Unix 套接字对端凭据或 mTLS）与控制器签发的能力令牌推导；智能体端**根本没有**状态迁移、验证写入与结案方法——不是权限判断，而是能力缺失。
2. **单一审计定序器**：唯一写入者，服务端盖章真实主体，落盘 fsync，定期对链头签名并锚定到主机之外的只追加存储；验证节点侧守护进程维护本地链并转发签名检查点，使截断可被发现。已如实说明其局限：锚定只能把可被静默篡改的历史限制在上次锚定之后的区间。
3. **四类进程与失陷影响分析**：不受信工作进程仅持短期能力令牌，无 API 密钥、不可写文件；**进程内 `PreToolUse` 钩子降级为纵深防御**，其五项检查全部由代理侧以认证主体重新执行。
4. **SDK 配置修正**：显式 `tools` 需包含 `Skill`；并提供**提示词内联回退**，使技能库加载不再位于关键路径；沙箱要求"后端不可用即拒绝启动"；已记录 0.2.154 版本中**未发现 `failIfUnavailable` 字段**这一实测差异，留待 W1 解决。
5. **并发语义**：授权主体迁移表、修订号比较并交换、幂等键；分析过程中若观测到自发恢复，仅追加"恢复观测"而**不改变状态**，且**绝不中断进行中的步骤**；仅 `awaiting_operator` 可转入 `resolved`；`handed_off` 为终态，不因后续恢复而重开；结案后必须产出结案报告与告警。
6. **可观测性本身成为受监控对象**：新增 `telemetry_health` 事件类；**数据缺失绝不用于开启、升级、降级或关闭验证节点健康事件**。
7. **共识模式**：改为"声明事实 + 四方交叉校验"（声明值、运行版本、集群特性状态、状态文件及其修改时间），任一不一致即为 `unknown`，并禁止一切模式相关建议。
8. **不可变哈希寻址策略包**：事件开启时绑定并沿用至终态，定义了激活、排空、紧急吊销与精确回滚，解决"发布新策略卡死在途事件"的问题。
9. **产出完整性校验**：每步结束后由控制器核对必需产出物；结构化输出仅作交叉校验，**以存储中的产出物为准**；散文永不被解析；**缺失评审结论绝不按 PASS 处理**。"无需处置"成为一等产出物。
10. **文档可追溯性修正**：父文档文件名更正；已删除对不存在的 `plan-review-vs-vibeserve.md` 的依赖；"观测守护进程"（M0）与"执行器"（M1 起）严格区分，M0 交付物中不含 `executor/`。

**竞品分析（C1）未导致任何设计变更**，其市场数据一律标注为〔U〕，四项路线建议分别路由至 D1、D2、D7、D13、D17，由负责人决定。

**新增阻塞项：** D13 影子观测节点数量、D14 策略包签名密钥保管与轮换、D15 审计锚定后端与周期、D16 能力传输方式、D17 是否公开运维可信度指标。
