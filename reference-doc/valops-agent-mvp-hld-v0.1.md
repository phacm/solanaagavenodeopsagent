# High-Level Design: Solana Validator Ops Agent — MVP (M0)

| Field | Value |
|---|---|
| Document | High-Level Design (HLD), v0.1 — DRAFT for review |
| Product | Solana Validator Node Self-Operating Agent ("valops-agent") |
| Milestone | **M0 — MVP: Observe, Diagnose, Recommend** |
| Author | Peng Huang (peng.huang@acm.org) |
| Date | 2026-09-17 |
| Parent document | `solana-validator-ops-agent-plan-v0.2.md` (governs; this HLD refines it) |
| Governing language | English (Chinese summary in §16 is informational) |
| Status | Awaiting owner decisions in §14 |

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

**Evidence tags.** `[E]` externally verifiable (§15). `[A]` design choice made here. `[H]` hypothesis to validate. `[U]` unknown, must be resolved.

No performance, cost, stake, or reward figure is asserted. Every threshold is **TBD by owner**.

---

## 1. Purpose and Position

Plan v0.2 describes the full system across six phases. This HLD specifies **only M0**, the smallest deployable increment that delivers value with **zero availability risk to the validator**, while building the complete control-plane skeleton that later milestones plug into.

**M0 thesis [A].** The riskiest parts of this system are not the actions — they are the *judgement* and the *containment*. M0 therefore ships the judgement path (diagnose → recommend → independently judge → report) and the entire containment layer (policy integrity, sandbox, audit chain, deterministic verification), but ships **no ability to change the validator**. The value delivered is faster, better-evidenced diagnosis handed to a human operator; the risk taken is bounded by the fact that no write path to the validator exists in the binary.

---

## 2. MVP Scope

### 2.1 In Scope (M0)

| # | Capability | Maps to plan v0.2 |
|---|---|---|
| C1 | Deterministic periodic health checks against one Agave validator | FR-1, FR-3, §4.1 Sentinel |
| C2 | Episode lifecycle with a framework-owned, append-only record | FR-9, §5.7 |
| C3 | Hypothesis-driven diagnosis by an LLM role session (read-only tools) | §5.5, FR-8 |
| C4 | Remediation **recommendation** for a human to execute manually | §5.1 T1 |
| C5 | Independent `proposal-judge` verdict on every recommendation | FR-11, SR-12 |
| C6 | Incident report + alert to the operator channel | FR-9, FR-2 |
| C7 | Deterministic recovery confirmation and episode closure | FR-7 (adapted), §5.6 |
| C8 | Policy integrity (read-only, hashed), OS sandbox, hash-chained audit | SR-10, SR-11, SR-13 |
| C9 | Consensus-mode detection (Tower BFT file vs. Alpenglow vote-history file) | FR-8 |

### 2.2 Out of Scope (M0) — deferred to M1+

| Deferred | Target milestone | Reason |
|---|---|---|
| Any T2 execution (restart, upgrade) | M1 | M0 has no write path to the validator by construction [A] |
| Approval service and signed approval tokens | M1 | Only needed once T2 exists |
| Configuration repository and deploy-by-commit | M1 | Same |
| Post-action verification (as opposed to recovery confirmation) | M1 | No actions in M0 |
| Mainnet-beta deployment | M2 | M0 runs on testnet only (D3) |
| Multi-validator fleet | Later | Plan §2.3 |
| Offline tuning loop | Research track | Plan §11, D10 |
| Any withdrawer-key or stake operation | Never | Plan §2.3 [E] S4 |

### 2.3 MVP Anti-Goals (enforced, not merely stated)

All plan §2.4 anti-patterns apply. Two are enforced structurally in M0 [A]:

1. **No write path exists.** The executor's command table contains only read-only commands. There is no code path from any tool to a state-changing command. A T2 tool cannot be "accidentally enabled" by configuration alone; it requires a code change plus a policy-manifest change plus a new hash.
2. **The agent cannot close an episode.** Closure is computed by the deterministic verifier from re-sampled signals.

---

## 3. Target Deployment (M0)

```
Cluster:    testnet (D3)
Validator:  1 × Agave validator, systemd, user `sol`               [E] S4
Ops host:   1 × separate small Linux host (no keypairs present)    [E] S2 rationale; [A] applied to agent
Watchtower: agave-watchtower on the ops host or a third host       [E] S2
Operator:   1 human on-call, receives alerts and reports           [A]
```

---

## 4. Architecture

### 4.1 Component View

```
┌────────────────────────────── OPS HOST ───────────────────────────────────────────────┐
│                                                                                        │
│  [1] Sentinel  ──opens/updates──►  [3] Episode Store  ◄──reads──  [7] Reporter output  │
│      (deterministic, no LLM)            (append-only API, SoT)                          │
│         │ trigger                             ▲                                         │
│         ▼                                     │ append (T1 tools only)                  │
│  ┌──────────────── [2] Episode Runner ────────┼──────────────────────────────────────┐ │
│  │  deterministic state machine; one FRESH SDK session per step                      │ │
│  │                                                                                    │ │
│  │   ┌── OS SANDBOX (SR-11) ────────────────────────────────────────────────────┐    │ │
│  │   │  step A  diagnostician   → hypotheses                                     │    │ │
│  │   │  step B  change-planner  → recommendation                                 │    │ │
│  │   │  step C  proposal-judge  → PASS / FAIL + checked evidence  (isolated in)  │    │ │
│  │   │  step D  reporter        → incident report + alert                        │    │ │
│  │   │  tools: in-process MCP server "valops" (role-scoped) — nothing else       │    │ │
│  │   │  hooks: PreToolUse policy gate + audit; PostToolUse(+Failure) audit       │    │ │
│  │   └───────────────────────────────────────────────────────────────────────────┘    │ │
│  └────────────────────────────────────────────────────────────────────────────────────┘ │
│                                                                                        │
│  [4] Policy Mount (read-only, SHA-256 manifest)   [5] Audit Chain (append-only)         │
│      command_table · thresholds · prompts ·           hash-chained JSON Lines           │
│      skills · verifier rules · judge checklist                                          │
│                                                                                        │
│  [6] Recovery Verifier (deterministic) ── the ONLY writer of episode state `resolved`   │
│  [8] Alert Sink (operator channel, D5)                                                  │
│                                                                                        │
│            │ HTTPS + mTLS, typed requests, command-id allowlist                          │
└────────────┼───────────────────────────────────────────────────────────────────────────┘
             ▼
┌────────────────────────────── VALIDATOR HOST ──────────────────────────────────────────┐
│  [9] Observer Daemon  (user `valops`, non-root, no keypair read access)                 │
│      fixed READ-ONLY command table · argument validation · output caps · rate limits    │
│      ── executes only the commands in §7.2; no state-changing command exists in M0      │
│  agave-validator (user `sol`, systemd)                                        [E] S4    │
└─────────────────────────────────────────────────────────────────────────────────────────┘
```

### 4.2 Trust Boundaries

| Boundary | Crossed by | Control |
|---|---|---|
| LLM ↔ everything | MCP tool calls only | `PreToolUse` policy gate; deny wins over allow in all modes [E] S7, S8 |
| Agent process ↔ ops host filesystem/network | syscalls | OS sandbox (D11): writes only to the episode-store socket; egress only to Claude API, observer daemon, alert sink [A] |
| Ops host ↔ validator host | mTLS HTTPS | Command-id allowlist; the daemon accepts an enum, never a shell string [A] |
| Anyone ↔ policy | file writes | Read-only mount + SHA-256 manifest verified at start-up and at every episode open [A] |
| Validator output ↔ LLM context | tool results | Structured, size-capped, redacted; treated as untrusted data (SR-6) [A] |

### 4.3 Key Design Decisions

| ID | Decision | Rationale | Tag |
|---|---|---|---|
| DD-1 | The **Episode Store is the source of truth**, not any model context | No single context spans an episode; survives restarts and long waits (NFR-4) | [A]; motivation [H] |
| DD-2 | **One fresh SDK session per step**, not one session with subagents | Guarantees the Judge's context isolation (SR-12), which subagent inheritance rules do not | [A]; SDK subagent inheritance [E] S7 |
| DD-3 | The observer daemon takes a **command id**, not a command string | Removes shell injection and argument smuggling as a class | [A] |
| DD-4 | Closure is computed, never asserted by the model | Prevents self-grading (plan §2.4) | [A]; pattern [E] R2 |
| DD-5 | M0 ships **no state-changing command at all** | Availability risk of the MVP is structurally zero, not policy-zero | [A] |
| DD-6 | `permission_mode="dontAsk"` with role-scoped allowlists | Anything not pre-approved is denied; `canUseTool` is never invoked in this mode, so no approval logic may depend on it | [E] S7 |
| DD-7 | Reference implementation language: **Python** (`claude-agent-sdk`) | Concrete interfaces required for an HLD; see §14 D1 — TypeScript changes §6.4 hook coverage only | [A], pending D1 |

---

## 5. Component Specifications

### 5.1 [1] Sentinel

Deterministic scheduler. Contains no LLM call.

| Property | Value |
|---|---|
| Trigger | Fixed interval per check (values in `policy/thresholds.yaml`, **TBD by owner**) |
| Inputs | Observer daemon read-only commands; `agave-watchtower` notifications |
| Outputs | `episode.open` / `episode.update_signal` on the Episode Store |
| Rules | Pure functions over signals → severity class; no model involvement |

**Checks (M0)**

| Check | Signal source | Basis |
|---|---|---|
| Delinquency | validator monitor / catch-up status | [E] S2 |
| Catch-up progress (slot distance trend) | `solana catchup --our-localhost 8899` | [E] S5 |
| Identity account balance below floor | `solana balance <identity pubkey>` | [E] S3 |
| Process/unit state | systemd unit status | [A] |
| Disk headroom on ledger and accounts volumes | filesystem stats | [A] |
| Running version drift vs. expected | log line `Starting validator with` | [E] S3 |
| Own leader slots approaching | `solana leader-schedule` filtered to own identity | [E] S3 |
| Consensus-mode state files present | tower file vs. `vote_history-<IDENTITY>.bin` | [E] S5 |

**De-duplication [A].** One open episode per (check-class, validator). A repeat signal updates the open episode instead of opening a new one. This is enforced in the store, not in a prompt, so an agent cannot manufacture episode churn.

### 5.2 [2] Episode Runner

Deterministic state machine. Owns which step runs, with what inputs, and under which budget.

```
open ──► diagnosing ──► recommending ──► judging ──┬─► reporting ──► awaiting_operator
                             ▲                     │                        │
                             └──── FAIL (retry ≤ N)┘                        ▼
                                                              (verifier re-samples)
                                                                            │
                                                          ┌─────────────────┴───────────┐
                                                          ▼                             ▼
                                                      resolved                     handed_off
```

| Rule | Detail | Tag |
|---|---|---|
| R-1 | Every step is a new SDK session; no `resume`, no `continue_conversation` | [A] |
| R-2 | Step input is assembled by the runner from the episode record — the model never chooses its own context | [A] |
| R-3 | Judge FAIL returns to `recommending`, at most **N** times (N **TBD**, D6); on exhaustion → `handed_off` + alert | [A] |
| R-4 | Any exception, budget exhaustion, or integrity failure → `handed_off` + alert. Never a silent stop | NFR-2 [A] |
| R-5 | Per-session `max_turns` and `max_budget_usd` set from policy | [E] S9 for the options |
| R-6 | The runner records `cost.per_role_usd` and `turns` per step from the SDK result | [E] S9 |

### 5.3 [3] Episode Store

Append-only service. The only writable surface inside the sandbox.

```
open_episode(trigger, policy_hash, consensus_mode)          -> episode_id
append_signal(episode_id, snapshot)                          -> snapshot_ref
append_hypothesis(episode_id, {claim,test,expected_evidence})-> hypothesis_id
append_recommendation(episode_id, {...})                     -> recommendation_id
append_verdict(episode_id, {recommendation_id, result, checks, session_id})
append_report(episode_id, markdown_ref)
set_state(episode_id, state, actor)      # rejects actor="agent" for resolved/verified
read_episode(episode_id[, view])         # `view` limits fields — used for Judge isolation
```

**Invariants [A]**
- No update, no delete. Corrections are new entries.
- `set_state` rejects `resolved` and any `verification` write from an agent principal. This is a server-side check, not a prompt instruction.
- Every write records the calling role, session id, and audit-chain reference.
- `read_episode(view="judge")` returns raw signals, the recommendation, and the skill preconditions only — never hypotheses' prose reasoning, planner rationale, or prior verdicts (SR-12).

### 5.4 [4] Policy Mount

Read-only for the agent process. Contains everything that decides behaviour.

```
policy/
├── command_table.yaml          # observer daemon allowlist (read-only commands only)
├── thresholds.yaml             # all values TBD by owner
├── prompts/{diagnostician,change_planner,proposal_judge,reporter}.md
├── skills/<skill>/SKILL.md     # §5.8 of plan v0.2; each cites its Anza source section
├── verifier/<signal>.yaml      # deterministic recovery-confirmation rules
├── judge_checklist.yaml
└── MANIFEST.sha256
```

**Integrity procedure [A]**
1. At process start and at every `open_episode`, recompute SHA-256 over every file and compare with `MANIFEST.sha256`.
2. On mismatch: enter **observe-only mode** (sentinel and store keep running; no LLM step executes), raise a high-severity alert naming the changed path, and record the event in the audit chain.
3. The manifest itself is signed; the public key lives outside the mount. Rotation procedure is **TBD by owner**.

### 5.5 [5] Audit Chain

Append-only JSON Lines, hash-chained: `entry.prev = SHA256(previous entry canonical form)`.

Written by: the `PreToolUse`/`PostToolUse` hooks, the observer daemon, the runner, and the verifier. **Not** writable by any MCP tool exposed to the model [A].

| Field | Meaning |
|---|---|
| `seq`, `ts`, `prev` | chain position, timestamp, previous hash |
| `actor` | `hook`/`daemon`/`runner`/`verifier` + role + session id |
| `event` | `tool_call`, `tool_result`, `tool_denied`, `state_change`, `integrity_fail`, `alert` |
| `payload_ref` | pointer to capped payload; large outputs stored by reference, never inline |

### 5.6 [6] Recovery Verifier

Deterministic. Runs on a timer while an episode is open and after `awaiting_operator`.

| Aspect | Detail |
|---|---|
| Inputs | Re-sampled signals from the observer daemon; rules from `policy/verifier/` |
| Rule form | Per-signal predicate plus a *stability window* (e.g. "not delinquent **and** catch-up distance below the threshold for W consecutive samples"). W and thresholds **TBD by owner** |
| Commands | `agave-validator monitor` and `solana catchup --our-localhost 8899` [E] S5 |
| Output | Immutable verification record; `set_state(resolved)` on success |
| Constraint | The only component permitted to set `resolved` (DD-4) |

### 5.7 [7] Role Sessions

| Role | Tools | Input view | Output |
|---|---|---|---|
| `diagnostician` | T0 read tools | Full episode record | 1..k hypotheses via `add_hypothesis` |
| `change-planner` | T0 read tools + `propose_recommendation` | Episode record incl. hypotheses | One recommendation, bound to one hypothesis |
| `proposal-judge` | T0 read tools + `submit_verdict` | **Judge view only** (§5.3) | PASS/FAIL + list of checks performed |
| `reporter` | `write_incident_report`, `send_alert` | Episode record incl. verification records | Markdown report + alert |

**Hypothesis contract [A].** A hypothesis is only accepted by the store if it carries all three of `claim`, `test` (an observation that could refute it), and `expected_evidence`. A claim with no refuting test is rejected at the API, which forces falsifiable diagnosis rather than narrative.

**Recommendation contract [A].** A recommendation must name: the action in operator terms, the runbook skill it came from, the preconditions to verify before acting, the expected post-condition, and the hypothesis it addresses. In M0 the action is text for a human; the system contains no code that performs it.

### 5.8 [9] Observer Daemon (validator host)

```
POST /observe   { command_id, args: {...}, request_id }
                → { status, structured, truncated, collected_at, audit_ref }
```

| Rule | Detail | Tag |
|---|---|---|
| OD-1 | `command_id` is an enum defined in `command_table.yaml`. An unknown id is rejected before any process spawn | [A] |
| OD-2 | Arguments are typed and validated per command (e.g. `pubkey` must match base58 and an expected length; `lines` must be an integer within a bound) | [A] |
| OD-3 | Every command is read-only in M0. No state-changing command is implemented | [A], DD-5 |
| OD-4 | Output is capped, structured where parseable, and redacted (paths, any key-like token) before return | [A] |
| OD-5 | Per-command rate limits; a breach returns an error and writes an audit entry | [A] |
| OD-6 | Runs as non-root `valops`; the validator's keypair files are not readable by this user | [E] S4 for non-root; [A] for the separate user |
| OD-7 | Timeout per command; a timeout is a normal, reported outcome, never a retry storm | [A] |

---

## 6. Agent Configuration

### 6.1 Session Options (reference, Python — D1)

```python
ClaudeAgentOptions(
    setting_sources=[],                                  # no filesystem settings      [E] S9
    tools=[],                                            # built-ins off               [E] S9 / [U] exact semantics — Phase-0 item
    disallowed_tools=["Bash", "Write", "Edit", "NotebookEdit",
                      "WebFetch", "WebSearch"],          # removed from context         [E] S7
    mcp_servers={"valops": valops_server_for(role)},     # role-scoped surface          [E] S9
    strict_mcp_config=True,                              #                              [E] S9
    allowed_tools=TOOLS_BY_ROLE[role],                   # exact list, no globs
    permission_mode="dontAsk",                           # unapproved ⇒ denied          [E] S7
    hooks={
        "PreToolUse":        [HookMatcher(hooks=[policy_gate]),
                              HookMatcher(hooks=[audit_append])],
        "PostToolUse":        [HookMatcher(hooks=[audit_append_result])],
        "PostToolUseFailure": [HookMatcher(hooks=[audit_append_failure])],
    },
    skills=SKILLS_BY_ROLE[role],                         # read-only skills library     [E] S9 / [U] loading with setting_sources=[]
    sandbox=SDK_SANDBOX_PROFILE,                         # third layer, not the only one [E] S9 option / [U] sufficiency
    system_prompt={"type": "file",
                   "path": f"policy/prompts/{role}.md"}, #                              [E] S9
    max_turns=POLICY.max_turns[role],                    # TBD by owner
    max_budget_usd=POLICY.max_budget_usd[role],          # TBD by owner
    model=POLICY.model[role],                            # pinned (D7)
)
```

### 6.2 Facts This Configuration Relies On

All [E] from S7/S8/S9:
- Permission order: hooks → deny rules → ask rules → permission mode → allow rules → `canUseTool`.
- A `PreToolUse` hook deny applies in every mode; when hooks disagree, deny wins.
- A timed-out `PreToolUse` hook means the tool does **not** run.
- In `dontAsk`, `canUseTool` is never called — so no control in this design may depend on it.
- A bare name in `disallowed_tools` removes the tool from the model's context entirely.
- The Python SDK does not expose `SessionStart`, `SessionEnd`, or `StopFailure` callback hooks; the TypeScript SDK does. M0 therefore performs start/end work in the runner, not in hooks (this is the only material D1 difference in M0).

### 6.3 Policy Gate Hook (`PreToolUse`)

Runs on every call, before any other permission step. Checks, in order [A]:

1. Tool is in this role's allowlist. (Defence in depth — the SDK already enforces this.)
2. Arguments conform to the tool schema and to policy bounds.
3. Rate and quota limits for this role and episode are not exceeded.
4. Episode is in a state where this tool is legal (for example, `submit_verdict` only in `judging`).
5. Policy manifest hash still matches the value recorded at episode open.

Any failure returns `permissionDecision: "deny"` with a reason, and writes an audit entry.

### 6.4 Prompt-Injection Handling (SR-6)

| Layer | Measure |
|---|---|
| Tool output | Structured fields where parseable; hard size caps; suspicious-pattern flagging (imperative verbs targeting known command names) |
| Prompt | Role prompts state that all tool output is untrusted data, never instruction |
| Judge | Explicit check: does the recommendation contain any instruction traceable to log or RPC text? |
| Structural | Even a fully persuaded model cannot act — no write path exists (DD-5) |

---

## 7. Data and Interface Contracts

### 7.1 Episode Record (M0 subset of plan §5.7)

```json
{
  "episode_id": "uuid",
  "opened_at": "RFC3339",
  "trigger": { "source": "sentinel|watchtower", "check": "delinquency|balance|...", "severity": "..." },
  "policy_hash": "sha256:...",
  "consensus_mode": "tower|alpenglow|unknown",
  "signals":        [ { "t": "...", "command_id": "...", "ref": "...", "summary": {} } ],
  "hypotheses":     [ { "id": "h1", "claim": "...", "test": "...", "expected_evidence": "...",
                        "status": "open|supported|refuted", "evidence_refs": [] } ],
  "recommendations":[ { "id": "r1", "hypothesis": "h1", "action_text": "...", "skill": "restart-idle-window",
                        "preconditions": [], "expected_postcondition": "..." } ],
  "verdicts":       [ { "recommendation": "r1", "result": "PASS|FAIL", "checks": [], "session_id": "..." } ],
  "verifications":  [ { "t": "...", "rule": "...", "result": "pass|fail", "by": "verifier" } ],
  "report_ref": "...",
  "state": "open|diagnosing|recommending|judging|reporting|awaiting_operator|resolved|handed_off",
  "cost": { "per_role_usd": {}, "turns": {} }
}
```

### 7.2 Observer Command Table (M0 — all read-only)

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
| `consensus_state_files` | presence of `tower-*.bin` vs. `vote_history-*.bin` | — | [E] S5 |

**M0 contains no other command.** Adding one is a code change plus a manifest change plus review.

### 7.3 MCP Tool Surface by Role

| Tool | Roles | Tier |
|---|---|---|
| `get_validator_monitor`, `get_catchup`, `get_leader_schedule`, `get_identity_balance`, `get_running_version`, `tail_validator_log`, `get_host_metrics`, `get_host_hygiene`, `get_consensus_state_files` | diagnostician, change-planner, proposal-judge | T0 |
| `get_verification_result` | change-planner, proposal-judge, reporter | T0 |
| `add_hypothesis` | diagnostician | T1 |
| `propose_recommendation` | change-planner | T1 |
| `submit_verdict` | proposal-judge | T1 |
| `write_incident_report`, `send_alert` | reporter | T1 |
| `draft_failover_runbook` | change-planner (text output only) | T1 [E] S5 for content |

---

## 8. Primary Flow (worked example — delinquency)

```
t0  Sentinel: catchup distance exceeds threshold for 2 consecutive samples
      → open_episode(trigger=delinquency, policy_hash, consensus_mode=<detected>)
      → append_signal × n   (monitor, catchup, host_metrics, leader_schedule_self)

t1  Runner → diagnostician (fresh session, episode view)
      hypotheses:
        h1 "ledger volume is full"      test: disk headroom + write errors in log
        h2 "version drift after update" test: running_version vs. expected
      tool calls re-sample as needed; store marks h1 refuted, h2 supported

t2  Runner → change-planner (fresh session)
      r1 = { hypothesis h2, action "restart into an idle window to pick up version X",
             skill restart-idle-window, preconditions [ no own leader slot within window,
             snapshot policy: do not fetch on routine restart ], expected postcondition
             [ running_version == X, catch-up distance recovers within W samples ] }

t3  Runner → proposal-judge (fresh session, JUDGE VIEW ONLY)
      checks: preconditions match the skill for the detected consensus mode;
              h2 evidence present in raw signals; least-impact option;
              no success-gaming pattern; no instruction sourced from log text
      → PASS with the check list recorded

t4  Runner → reporter → incident report + alert to operator (recommendation + Judge evidence
      + raw signals) ; state = awaiting_operator

t5  Operator acts manually (outside the system). Verifier keeps re-sampling.
      Recovery predicate holds for W consecutive samples → verifier sets `resolved`
      and writes the verification record. If it never holds within the window
      → state stays awaiting_operator and the alert escalates.
```

---

## 9. Failure Modes

| Failure | Detection | Behaviour | Tag |
|---|---|---|---|
| Claude API unavailable or slow | SDK error / timeout | Episode → `handed_off` with the signals gathered so far; alert; sentinel and verifier continue | [A] |
| Budget or turn limit hit | SDK result | Same as above | [A] |
| Judge FAILs N times | Runner counter | `handed_off` + alert carrying every FAIL reason | [A] |
| Policy hash mismatch | Integrity check | Observe-only mode; high-severity alert; no LLM step runs | [A] |
| Observer daemon unreachable | Request error | Sentinel degrades to watchtower-only signals; alert; no episode opened on missing data alone | [A] |
| Episode store write failure | API error | Runner aborts the step; alert; nothing is assumed written | [A] |
| Agent attempts a denied tool | Policy gate / SDK deny | Denied, audited, surfaced in the report | [E] S7 mechanism |
| Sandbox violation attempt | OS sandbox | Blocked, audited, alert | [A] |
| Validator itself fails | Out of scope for the agent | systemd restart policy and watchtower are unaffected by the agent (NFR-1) | [A] |

**Degradation ordering [A].** Full operation → observe-only (policy or integrity problem) → sentinel-and-alert only (agent unavailable) → watchtower only (ops host down). The validator's own availability does not depend on any of these tiers.

---

## 10. Testing Strategy (M0 exit gates)

| Suite | Contents | Gate |
|---|---|---|
| **Policy** (CI-blocking) | Removed built-ins denied; role calling another role's tool denied; out-of-state tool call denied; hook timeout ⇒ no execution; agent write to policy mount fails at the OS level | 100% pass, every run |
| **Write-path absence** | Static check: no state-changing command id in `command_table.yaml`; no code path from a tool to such a command | 100% pass, every run |
| **Tamper** | Mutate each policy file in turn ⇒ observe-only + alert, every time | 100% pass |
| **Sandbox** | Disallowed egress and filesystem writes blocked | 100% pass |
| **Judge adversarial** | Seeded bad recommendations: alert silencing; recovery claimed from process liveness alone; repeated restarts; snapshot download renamed; log-injected instruction; precondition mismatched to consensus mode | Every seeded case returns FAIL; suite frozen before the run |
| **Judge isolation** | Runner asserts the Judge input contains no planner or diagnostician prose | 100% pass |
| **Closure ownership** | Agent attempts `set_state(resolved)` and a verification write ⇒ rejected by the store | 100% pass |
| **Falsifiability** | Hypothesis lacking `test` rejected at the API | 100% pass |
| **Functional (testnet)** | Injected faults: stop the validator; drain the testnet identity balance; fill the ledger volume; introduce version drift | Correct episode, correct hypothesis ranked first, correct recommendation |
| **Degradation** | API down; store down; daemon down; budget exhausted | Correct degradation tier; validator unaffected |
| **Consensus mode** | Tower and vote-history fixtures | Correct skill variant selected |
| **Repetition** | Every safety-relevant suite repeated over **N** trials (**TBD**, D6) | No single-trial pass counts |

---

## 11. Observability and Metrics (targets TBD by owner)

| Metric | Purpose |
|---|---|
| Episodes opened, by check and severity | Volume and noise |
| MTTD vs. watchtower alone | Does the sentinel add detection value |
| Hypothesis precision (human-rated first-ranked hypothesis correct) | Diagnosis quality |
| Judge FAIL rate; share of FAILs a human confirms as correct | Is the Judge useful or merely obstructive |
| Recommendation acceptance rate (operator acted on it as written) | Recommendation quality |
| Unauthorized executions | **Hard requirement: zero** |
| Denials, tamper events, sandbox blocks | Containment health |
| Cost and turns per role, per episode and per day | Budget planning before M1 (D6) |
| Time from episode open to report delivered | Operator experience |

---

## 12. Work Breakdown

Ordered by dependency. Complexity is a relative rating **[A]**; calendar duration is **TBD by owner** — no estimate is asserted here.

| # | Work item | Depends on | Complexity | Notes |
|---|---|---|---|---|
| W1 | Phase-0 SDK verification spike | — | M | Confirms `tools=[]`, `dontAsk` + role allowlists, hook deny/timeout, `skills` loading with `setting_sources=[]`, SDK `sandbox` behaviour. Blocks everything; result may amend §6 |
| W2 | Observer daemon + command table + mTLS | — | M | Can proceed in parallel with W1 |
| W3 | Episode store + schema + invariants | — | M | Server-side rejection of agent closure is the core of DD-4 |
| W4 | Audit chain | W3 | S | |
| W5 | Policy mount, manifest, integrity fallback | — | S | |
| W6 | OS sandbox profile (D11) | W1 | M | Must be shown to work with the SDK process |
| W7 | MCP tool server, role-scoped | W1, W2, W3 | M | |
| W8 | Hooks: policy gate + audit | W4, W5, W7 | M | |
| W9 | Sentinel + thresholds | W2, W3 | M | |
| W10 | Episode runner state machine | W3, W7, W8 | L | |
| W11 | Skills library v1 (from Anza docs, with compatibility matrix) | W5 | M | Content work, not code |
| W12 | Role prompts + Judge checklist | W11 | M | |
| W13 | Recovery verifier | W2, W3, W5 | M | |
| W14 | Reporter + alert sink (D5) | W7, W3 | S | |
| W15 | Test suites §10 incl. fault injection harness | W9, W10, W13 | L | |
| W16 | Testnet deployment and run-in | all | M | |

---

## 13. Milestone Exit Criteria (M0 → M1)

M0 is complete when **all** hold:

1. Every CI-blocking suite in §10 passes, repeated over N trials, with zero unauthorized executions.
2. The write-path-absence check passes on the shipped artefact.
3. Every seeded Judge adversarial case returns FAIL, on a suite frozen before the run.
4. Four injected fault classes on testnet each produce a correct episode, a correctly ranked hypothesis, and a recommendation an operator judges actionable.
5. Tamper and sandbox tests each force the expected degraded state.
6. Per-role cost has been measured over the run-in period, so D6 budgets can be set from data rather than guessed.
7. The Phase-0 verification log is written, and §6 has been amended wherever the SDK behaved differently from the assumptions here.

**Kill criteria** (plan §12 applies unchanged; the M0-specific trigger): if W1 shows the SDK's permission, hook, or sandbox semantics cannot guarantee SR-3, SR-4, SR-10, or SR-11 on the pinned version, stop and redesign the containment layer before writing further code.

---

## 14. Open Decisions Blocking M0

| ID | Decision | Blocks | Note |
|---|---|---|---|
| **D1** | Implementation language | W1 and all code | Python assumed here (DD-7). TypeScript's extra hook events would move start/end work from the runner into hooks — a small change in M0 |
| D3 | Target cluster for M0 | W16 | This HLD assumes testnet |
| D5 | Alert channel | W14 | watchtower supports Slack, Discord, Telegram, Twilio [E] S2 |
| D6 | Thresholds and budgets | W9, W10, W15 | Balance floor, check intervals, `max_turns`, `max_budget_usd`, retry budget N, stability window W, trial count N |
| D7 | Pinned model id(s) | W1, W10 | A separate, cheaper model for the Judge is possible but unproven [H] |
| D9 | Consensus mode on target cluster | W11, W13 | Is Alpenglow active at deployment? [U] |
| D11 | OS sandbox backend | W6 | Must be demonstrated in W1 |
| — | Manifest signing-key custody and rotation | W5 | Not yet specified; **TBD by owner** |

D2 (client), D4 (upgrade method), D8 (tier table), D10 (offline tuning), and D12 (approver policy) do not block M0: M0 targets Agave only, performs no upgrade, exposes only T0/T1, and has no approval step.

---

## 15. Sources

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
| — | `solana-validator-ops-agent-plan-v0.2.md`; `plan-review-vs-vibeserve.md` (2026-09-17) |

All sources accessed 2026-09-17. Re-verify during W1.

---

## 16. 中文摘要（参考用，以英文为准）

**M0（最小可行产品）定位：** 只做"观测—诊断—建议"，**不具备任何改动验证节点的能力**。这不是靠策略约束，而是结构性保证：M0 的命令表中根本不存在任何改变状态的命令（DD-5）。交付价值是更快、证据更充分的故障诊断，交给人工执行；承担的可用性风险为零。

**纳入 M0 的能力：** 确定性哨兵定期健康检查；事件（episode）记录为唯一事实来源，仅可追加；以可证伪假设形式诊断；生成人工可执行的处置建议；独立评审者（proposal-judge）在隔离上下文中核查建议；事故报告与告警；由确定性验证器重新采样确认恢复并独占"已解决"状态写入权；策略只读哈希校验、操作系统沙箱、哈希链审计。

**推迟到 M1 及以后：** 任何 T2 执行（重启、升级）、审批服务与签名令牌、配置仓库、主网部署、多节点、离线调优。提款密钥与质押操作**永不纳入**。

**关键设计决策：**
- DD-1 事件记录（而非模型上下文）是事实来源；
- DD-2 每个步骤开启全新会话，而非会话内子智能体——这是保证评审者上下文隔离的唯一可靠方式；
- DD-3 观测守护进程只接受命令枚举 id，不接受命令字符串，从根本上消除注入与参数夹带；
- DD-4 事件关闭由验证器计算得出，模型无权断言；
- DD-6 `dontAsk` 模式下 SDK 永不调用 `canUseTool`，故本设计任何管控均不得依赖它。

**退化顺序：** 完整运行 → 只读观测（策略/完整性异常）→ 仅哨兵告警（智能体不可用）→ 仅 watchtower（运维主机宕机）。验证节点自身可用性不依赖上述任何一层。

**M0 完成判据：** 所有阻断性测试套件在 N 次重复试验中全部通过且零越权执行；写路径缺失静态检查通过；所有预置"伪成功"用例均被评审者判为 FAIL；测试网四类注入故障均产出正确事件与可执行建议；篡改与沙箱测试均触发预期降级；按角色成本实测完成，以便用数据而非猜测设定预算。

**阻塞项：** D1 开发语言（本文档以 Python 为参考实现）、D3 目标集群、D5 告警渠道、D6 各阈值与预算、D7 模型版本、D9 目标集群共识模式、D11 沙箱后端，以及清单签名密钥保管与轮换方案（尚未指定）。

所有数值目标均标注为"由项目负责人决定（TBD）"，本文档未编造任何性能、成本或收益指标。
