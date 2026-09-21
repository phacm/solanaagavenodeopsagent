# Plan: Solana Validator Node Self-Operating Agent (Claude Agent SDK)

| Field | Value |
|---|---|
| Document | Implementation plan, **v0.2** (DRAFT — for review before any code is written) |
| Author | Peng Huang (peng.huang@acm.org) |
| Date | 2026-09-17 |
| Supersedes | v0.1 (2026-08-10) |
| Status | Awaiting owner decisions in §12 |
| Governing language | English (Chinese summary in §15 is informational) |

---

## Change Log

| Version | Change | Driver |
|---|---|---|
| v0.1 | Initial plan | — |
| v0.2 | Added an independent `proposal-judge` subagent in front of human approval | Review F1 |
| v0.2 | Post-action verification and the "resolved" state are now owned by a deterministic framework verifier, not the LLM. Policy artifacts are read-only and hash-checked | Review F2 |
| v0.2 | Replaced resumed long sessions with a structured episode record and a fresh session per step. Diagnosis is expressed as falsifiable hypotheses | Review F3 |
| v0.2 | Added an operating-system sandbox for the agent process | Review F4 |
| v0.2 | Replaced free-form prompts with a versioned skills library that carries compatibility matrices | Review F5 |
| v0.2 | Added an optional offline tuning loop as a research track (not a v1 dependency) | Review F6 |
| v0.2 | Added a git-backed configuration repository and a hash-chained audit log | Review F7 |
| v0.2 | Added per-role cost measurement | Review F8 |
| v0.2 | Recorded search-and-revert on live systems, self-expansion of scope, and single-seed evaluation as explicit anti-patterns | Review §4 |

All v0.2 changes derived from the review are design choices **[A]**. The inspiring reference (R1) is an unreviewed preprint in a different domain and does not validate any requirement (see §1.1).

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
| OS | Operating System |
| JSON | JavaScript Object Notation |
| UUID | Universally Unique Identifier |
| MTTD / MTTR | Mean Time To Detect / Mean Time To Recover |
| USD | United States Dollar |
| PDF | Portable Document Format |
| TBD | To Be Decided |

## 1. Evidence Grading

- **[E]** Externally verifiable — traceable to a source in §14.
- **[A]** Assumption or design choice — not externally validated; must be reviewed.
- **[H]** Hypothesis — expected to hold; must be validated in testing.
- **[U]** Unknown from public sources — must be resolved before dependent work.

No performance target, stake threshold, reward figure, or cost estimate is asserted in this plan. Every such value is **TBD by owner**.

### 1.1 Status of the VibeServe / VibeSys Reference

R1 (arXiv:2605.06068) is a preprint. Its authors state its limitations: single-seed runs, a user-supplied correctness checker, and a non-trivial compute budget [E R1 §6]. It studies *build-time* synthesis of LLM serving code in isolated, revertible workspaces, and its evaluation used Codex CLI [E R1 §3.2, §4.1]. This plan adopts only R1's *structural safeguards*. R1's search mechanism is not used against the live validator (§2.4).

---

## 2. Scope

### 2.1 Goal

Build an agent, using the Claude Agent SDK, that performs day-to-day operations of a single Solana validator (Agave client). The agent observes health continuously, diagnoses problems, recommends remediation, and executes a small set of actions that are independently judged and approved by a human. It works under safety limits that are enforced outside the model.

### 2.2 In Scope (v1)

1. Health observation: delinquency, catch-up status, identity account balance, leader schedule, service state, disk and log signals.
2. Hypothesis-driven diagnosis and incident reports.
3. Gated actions (restart in an idle window, upgrade workflow). Every gated action passes an independent judge, a human approval, and framework verification.
4. A tamper-evident audit trail.

### 2.3 Out of Scope (v1)

| Item | Reason | Tag |
|---|---|---|
| Any operation using the authorized withdrawer keypair | The withdrawer key must never be stored on the validator; withdrawals are done on a trusted computer | [E] S3, S4 |
| Autonomous identity failover (`set-identity`) | A safety-critical procedure with strict preconditions. v1 only drafts the runbook | [E] S5 for the procedure; [A] for keeping it human-only |
| Stake, delegation, and commission management | Financial actions | [A] |
| Clients other than Agave | Commands not verified for other clients | [U] (D2) |
| Multi-validator fleet orchestration | Deferred | [A] |
| Offline tuning loop (§11) | Research track | [A] (D10) |

### 2.4 Anti-Patterns (explicitly prohibited)

| Prohibited | Reason | Tag |
|---|---|---|
| Try-measure-revert search on the live validator | Reverting does not undo downtime or missed leader slots | [A]; leader-slot concern from [E] S3 |
| Agent widening its own scope, tiers, thresholds, or benchmark conditions | Tiers are fixed by the owner. R1 reports its agent escalating benchmark load on its own [E R1 §4.2]; that behavior is unacceptable here | [A] |
| Agent writing to executor code, validator configuration, policy, skills, or the audit log | Integrity of the control plane | [A] |
| Agent marking an episode "resolved" or grading its own action | Self-grading; see §5.6 | [A], inspired by [E] R2 |
| Single-trial safety evaluation | Safety claims need repeated trials (count TBD) | [A] |

---

## 3. Requirements

### 3.1 Functional Requirements

| ID | Requirement | Source / Tag |
|---|---|---|
| FR-1 | Detect delinquency and alert promptly | [E] S2 |
| FR-2 | Integrate with `agave-watchtower`, running on a server separate from the validator | [E] S2 |
| FR-3 | Check identity account balance regularly and alert below a floor (**TBD by owner**) | [E] S3 |
| FR-4 | Restarts avoid leader slots, using `agave-validator exit` under systemd or `wait-for-restart-window` | [E] S3, S5 |
| FR-5 | Upgrade flow: install while the validator runs → restart in an idle window → verify version with `grep -B1 'Starting validator with' <logfile>` | [E] S3 |
| FR-6 | Default to `--no-snapshot-fetch` on routine restarts and run `solana catchup <pubkey>` afterwards. The agent never downloads a snapshot on its own in v1 | [E] S3; [A] "never" |
| FR-7 | **Framework verifier** confirms post-action state with `agave-validator monitor` or `solana catchup --our-localhost 8899` and records an immutable result | [E] S5 for commands; [A] framework ownership |
| FR-8 | Detect consensus mode (tower file vs. `vote_history-<IDENTITY>.bin`) and select the matching skill variant | [E] S5; activation on the target cluster is [U] |
| FR-9 | Every anomaly produces an episode record (§5.7) and an incident report | [A] |
| FR-10 | Optional metrics reporting via `SOLANA_METRICS_CONFIG` | [E] S2 |
| FR-11 | Each T2 proposal carries a Judge verdict (PASS or FAIL, with evidence) before it reaches a human | [A] |

### 3.2 Security and Safety Requirements

| ID | Requirement | Source / Tag |
|---|---|---|
| SR-1 | Validator runs as non-root `sol`. Executor runs as a separate non-root `valops` user that cannot read keypairs | [E] S4 (non-root); [A] |
| SR-2 | No withdrawer keypair on the validator host or the ops host | [E] S4 |
| SR-3 | No arbitrary shell. Only typed, allowlisted tools, enforced in three layers: SDK deny rules, OS sandbox, executor command table | [A]; SDK deny semantics [E] S7 |
| SR-4 | Every tool call passes a `PreToolUse` policy hook and an audit hook. Hook deny applies in all modes | [E] S7, S8 |
| SR-5 | `bypassPermissions` is prohibited | [A]; rationale [E] S7 |
| SR-6 | Logs, gossip, and RPC data are untrusted input. Tool outputs are structured, truncated, and redacted. No instruction from those sources is acted on | [A] |
| SR-7 | Host hygiene is report-only: pending updates, SSH password authentication, fail2ban, open ports | [E] S4 for the checks; [A] report-only |
| SR-8 | Claude API authenticated by API key | [E] S6 |
| SR-9 | Per-session `max_turns` and `max_budget_usd`, plus a per-episode retry budget. Values **TBD** | [E] S9 for options; [A] retry budget |
| SR-10 | **Policy integrity.** Executor command table, thresholds, hook code, system prompts, skills, and verifier code are mounted read-only for the agent and hash-checked at startup and on every episode start. On mismatch the system falls back to observe-only (T0) and alerts | [A] |
| SR-11 | **OS sandbox.** The agent process runs with no filesystem writes except the episode store's append Application Programming Interface (API). Network egress is limited to the Claude API, the executor endpoint, and the alert and approval channels | [A]; backend choice D11 |
| SR-12 | **Judge isolation.** `proposal-judge` runs in a fresh session. It receives only the raw signal snapshot, the proposal, and the skill preconditions, never the orchestrator's or planner's reasoning | [A] |
| SR-13 | **Audit integrity.** Audit log is append-only and hash-chained, written by hooks and the executor, not by agent tools | [A] |

### 3.3 Non-Functional Requirements

| ID | Requirement | Tag |
|---|---|---|
| NFR-1 | The LLM is not in the keep-alive path. systemd and watchtower work without the agent | [A] |
| NFR-2 | Any agent failure (API error, budget exhausted, retry budget exhausted, Judge FAIL after retries) means no action and a human alert | [A] |
| NFR-3 | Actions are idempotent or guarded by preconditions re-checked by the executor | [A] |
| NFR-4 | No single agent context spans a whole episode. State lives in the episode record | [A]; motivation [H] from R1 §1 (compaction drift) |

---

## 4. Architecture

### 4.1 Component View

```
┌──────────────────────────── Ops host (separate from validator) ─────────────────────────────────┐
│                                                                                                  │
│  agave-watchtower ─────┐                                                                         │
│                        ▼                                                                         │
│  Sentinel (deterministic) ── opens episode ──► Episode Store (framework-owned, append-only API)   │
│                                                   ▲        ▲                                     │
│  ┌──────────── OS sandbox (SR-11) ───────────────┼────────┼───────────────────────────────────┐ │
│  │ Episode Runner (deterministic step machine)    │        │                                   │ │
│  │   each step = FRESH Claude Agent SDK session reading the episode record                    │ │
│  │   ├─ diagnostician   (T0 tools)  → hypotheses                                              │ │
│  │   ├─ change-planner  (T0 tools)  → proposal                                                │ │
│  │   ├─ proposal-judge  (T0 tools, isolated inputs, SR-12) → PASS / FAIL + evidence           │ │
│  │   └─ reporter        (T1 tools)  → incident report, alert                                  │ │
│  │   hooks: PreToolUse policy gate + audit; PostToolUse / PostToolUseFailure audit            │ │
│  │   tools: in-process MCP server "valops" only                                               │ │
│  └───────────────────────────────────────────────────────────────────────────────────────────┘ │
│                                                                                                  │
│  Read-only policy mount (SR-10): command_table · thresholds · hooks · prompts · skills · verifier│
│  Approval service ◄──► Human approver (sees proposal + Judge verdict)                           │
│  Framework Verifier (deterministic) ── writes verification results & "resolved" state           │
│                         │ typed RPC over mTLS, allowlist                                        │
└─────────────────────────┼────────────────────────────────────────────────────────────────────────┘
                          ▼
┌──────────────────────── Validator host ──────────────────────────────────────────────────────────┐
│ Executor daemon (user `valops`, non-root, no keypair access): fixed command table, argument      │
│ validation, approval-token check, precondition re-check, rate limits, audit append               │
│ agave-validator (user `sol`, systemd)                                                             │
│ Config repository checkout (signed commits; deploy-by-commit; rollback = previous commit)         │
└──────────────────────────────────────────────────────────────────────────────────────────────────┘
```

### 4.2 Design Rationale

| Decision | Tag |
|---|---|
| Ops host separate from validator (same reasoning as watchtower placement) | [E] S2 for watchtower; [A] applied to agent |
| Deterministic sentinel and episode runner frame the LLM steps | [A] |
| Role separation with an independent Judge | [A]; pattern from [E] R1 §3.3 |
| Framework (not an agent) runs canonical verification | [A]; pattern from [E] R2 |
| Fresh session per step over persistent structured state | [A]; pattern from [E] R1 §3.3, R2 |
| Claude Agent SDK rather than raw Client SDK or Managed Agents | [E] S6 for product definitions; [A] preference for self-hosting near private infrastructure |

---

## 5. Agent Design

### 5.1 Autonomy Tiers

| Tier | Meaning | Examples | Enforcement |
|---|---|---|---|
| **T0 Observe** | Read-only | status, catch-up, leader schedule, balance, log tail, disk, version, consensus files | In `allowed_tools`; audit hook |
| **T1 Low-risk** | No validator impact | send alert, write report section, append a hypothesis to the episode | Policy hook with rate limits |
| **T2 Gated** | Affects availability | idle-window restart, stage upgrade, apply configuration commit | Planner → **Judge PASS** → human approval token → executor preconditions → execute → **framework verification** |
| **T3 Forbidden** | Agent may only draft text | failover, snapshot download, key operations, withdraw, host security changes, editing policy or skills | No such tools exist; built-ins removed |

Tier assignment is [A] and requires owner approval (D8).

### 5.2 SDK Configuration (per official reference)

A factory builds options for each step session. Common settings are shown first, then the per-role differences.

```python
# common to every step session
ClaudeAgentOptions(
    setting_sources=[],                          # no filesystem settings           [E] S9
    tools=[],                                    # built-ins off (verify, Phase 0)  [E] S9 / [U] semantics
    disallowed_tools=["Bash", "Write", "Edit", "NotebookEdit",
                      "WebFetch", "WebSearch"],  # removed from context              [E] S7
    mcp_servers={"valops": valops_server_for(role)},  # role-scoped tool set         [E] S9
    strict_mcp_config=True,                      #                                  [E] S9
    permission_mode="dontAsk",                   # unapproved → denied              [E] S7
    hooks={
        "PreToolUse":  [HookMatcher(hooks=[policy_gate]), HookMatcher(hooks=[audit_append])],
        "PostToolUse": [HookMatcher(hooks=[audit_append_result])],
        "PostToolUseFailure": [HookMatcher(hooks=[audit_append_failure])],
    },
    skills=[...role-specific skill names...],    # read-only skills library          [E] S9 / [U] loading with setting_sources=[]
    sandbox=...,                                 # SDK sandbox as an extra layer     [E] S9 option / [U] sufficiency
    max_turns=TBD, max_budget_usd=TBD,           #                                  [E] S9
    system_prompt={"type": "file", "path": f"policy/prompts/{role}.md"},  #          [E] S9
)
```

| Role | `allowed_tools` | Input given to session |
|---|---|---|
| diagnostician | T0 tools | Episode record (signals, prior hypotheses) |
| change-planner | T0 tools + `propose_action` | Episode record + supported hypotheses |
| proposal-judge | T0 tools + `submit_verdict` | **Only** raw signal snapshot, proposal, skill preconditions (SR-12) |
| reporter | `write_incident_report`, `send_alert` | Episode record incl. framework verification results |

SDK facts relied on (all [E] S7/S8/S9):
- Evaluation order: hooks → deny rules → ask rules → permission mode → allow rules → `canUseTool`.
- In `dontAsk` mode, `canUseTool` is never called. That is why T2 approval is enforced in the executor.
- When hooks conflict, `deny` wins. A timed-out `PreToolUse` hook means the tool does not run.
- Python `AgentDefinition` fields use camelCase. The Python SDK does not expose `SessionStart`, `SessionEnd`, or `StopFailure` callback hooks.
- v0.2 uses separate top-level sessions per role rather than in-session subagents. This ensures a clean context for the Judge. Subagents remain an option for sub-steps within a role [A].

### 5.3 Tool Catalog (MCP server `valops`, role-scoped)

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
| `get_consensus_state_files` | T0 | detect `tower-*.bin` / `vote_history-*.bin` | [E] S5 |
| `get_verification_result` | T0 | read framework verifier record | [A] |
| `add_hypothesis` | T1 | append hypothesis `{claim, test, expected_evidence}` to episode | [A] |
| `propose_action` | T1 | append proposal (no execution) | [A] |
| `submit_verdict` | T1 | Judge only: PASS or FAIL + checked evidence | [A] |
| `send_alert` | T1 | alert channel | [A] |
| `write_incident_report` | T1 | report store | [A] |
| `draft_failover_runbook` | T1 (text) | checklist per S5; executes nothing | [E] S5 |

T2 execution is **not** an agent tool in v0.2. After Judge PASS, the episode runner (deterministic) submits the approved proposal to the approval service. The executor runs it only with a valid token [A].

### 5.4 T2 Action Pipeline

```
change-planner ──propose_action──► Episode record
        │
        ▼
proposal-judge (fresh session, isolated inputs)
        ├─ FAIL (with evidence) ──► back to planner; retry budget N (TBD) ──► exhausted ⇒ hand off to human
        └─ PASS
             ▼
Episode runner ──► Approval service ──► Human sees: proposal + Judge evidence + raw signals
                                            ├─ reject ⇒ close as handed-off
                                            └─ approve ⇒ signed token {action_uuid, command_hash, expiry}
                                                   ▼
                                    Executor: verify token + hash; re-check preconditions
                                    (e.g., not in/near own leader slot per leader schedule)
                                                   ▼ execute
                                    Framework Verifier (deterministic): FR-7 checks
                                    → immutable verification record → sets episode state
```

### 5.5 Judge Checklist (minimum, extended via skills)

| Check | Tag |
|---|---|
| Proposal's preconditions match the runbook skill for the detected consensus mode and client | [E] S3/S5 for content; [A] check |
| Supporting hypothesis is testable and its evidence is present in the raw snapshot | [A] |
| Action is the least-impact option that addresses the hypothesis (for example, no restart for a balance alert) | [A] |
| **Success-gaming patterns** (domain analogue of R1's reward-hacking checks [E R1 §3.3]): resolving by silencing or deduplicating alerts; declaring recovery on process liveness without catch-up or vote evidence; repeated restarts to clear symptoms; proposing a snapshot download (a T3 action) under another name | [A] |
| Proposal contains no instruction copied from log or RPC text (SR-6) | [A] |

### 5.6 Verification and Resolution Ownership

- Only the **Framework Verifier** writes verification results and changes episode state to `resolved` [A].
- Verification commands are fixed per action type in `policy/verifier/` (read-only, hashed) [A]. Commands are from S3 and S5 [E].
- The agent reads the results with `get_verification_result` and can only describe them.

### 5.7 Episode Record and Lifecycle

**Record schema (framework-owned JSON, append-only API) [A]**

```json
{
  "episode_id": "uuid",
  "opened_at": "...", "trigger": {"source": "sentinel|watchtower", "signal": "..."},
  "policy_hash": "sha256 of read-only policy mount at open",
  "consensus_mode": "tower|alpenglow|unknown",
  "snapshots": [{"t": "...", "tool": "...", "output_ref": "..."}],
  "hypotheses": [{"id": "h1", "claim": "...", "test": "...", "status": "open|supported|refuted", "evidence_refs": []}],
  "proposals":  [{"id": "p1", "action": "...", "command_hash": "...", "preconditions": [], "hypothesis": "h1"}],
  "verdicts":   [{"proposal": "p1", "result": "PASS|FAIL", "checks": [], "session_id": "..."}],
  "approvals":  [{"proposal": "p1", "by": "...", "decision": "...", "token_expiry": "..."}],
  "executions": [{"proposal": "p1", "executor_result": "...", "audit_ref": "..."}],
  "verifications": [{"proposal": "p1", "checks": [], "result": "pass|fail", "by": "framework"}],
  "state": "open|diagnosing|proposed|judged|awaiting_approval|executing|verifying|resolved|handed_off",
  "cost": {"per_role_usd": {}, "turns": {}}
}
```

**Lifecycle.** The episode runner is a deterministic state machine. Each LLM step is a new session that reads the record and writes only through T1 tools. No step resumes a prior transcript (NFR-4) [A].

```
open → diagnosing (diagnostician) → proposed (change-planner) → judged (proposal-judge)
     → awaiting_approval → executing (executor) → verifying (framework) → resolved | handed_off
     (any failure / budget exhaustion / tamper ⇒ handed_off + alert)
     reporter runs at resolved | handed_off
```

### 5.8 Skills Library

| Skill | Content source | Compatibility matrix fields |
|---|---|---|
| `restart-idle-window` | [E] S3, S5 | consensus mode · client · docs version and access date |
| `upgrade-agave` | [E] S3 | same + upgrade method (D4) |
| `catchup-diagnosis` | [E] S3 (snapshot policy, catch-up) | same |
| `identity-balance` | [E] S3 | same |
| `failover-runbook-draft` | [E] S5 (Tower BFT and Alpenglow sections) | same; output is text only |
| `host-hygiene-report` | [E] S4 | OS distribution |
| `judge-checklist` | §5.5 | — |

Rules [A]:
- Skills are read-only to agents and part of the hashed policy mount (SR-10).
- Every factual step cites its source section. Unverified clients are marked [U] and blocked from T2.
- Changes go through human review as signed commits.
- A long-term `ops-memory.md` of lessons is appended by the reporter role only into a *staging* file. A human reviews it before promotion into the policy mount.

---

## 6. Repository Layout

```
valops-agent/
├── PLAN.md
├── pyproject.toml | package.json        # D1
├── policy/                              # READ-ONLY to agent; hashed (SR-10)
│   ├── command_table.yaml
│   ├── thresholds.yaml                  # values TBD by owner
│   ├── prompts/{diagnostician,change_planner,proposal_judge,reporter}.md
│   ├── skills/<skill>/SKILL.md          # §5.8
│   ├── verifier/<action>.yaml           # fixed verification per action
│   └── MANIFEST.sha256
├── agent/
│   ├── runner.py                        # deterministic episode state machine
│   ├── options.py                       # per-role ClaudeAgentOptions factory
│   ├── hooks/{policy_gate,audit}.py
│   ├── tools/valops_server.py           # role-scoped @tool definitions
│   └── integrity.py                     # manifest check → observe-only fallback
├── episodes/
│   ├── schema.json
│   └── store.py                         # append-only API
├── verifier/verifier.py                 # framework-owned verification
├── approval/{service,client}.py
├── sentinel/{checks,scheduler}.py
├── executor/{daemon.py,validate.py}     # validator host
├── audit/chain.py                       # hash-chained log
├── sandbox/                             # OS sandbox profiles (D11)
├── config-repo/                         # signed validator config commits (F7)
├── ops-memory/staging.md                # human-reviewed before promotion
└── tests/
    ├── unit/
    ├── policy/        # denial, tamper, sandbox escape attempts
    ├── judge/         # success-gaming and injection proposals
    ├── integration/   # testnet fault injection
    └── replay/        # recorded incident corpus (also used by §11)
```

---

## 7. Phased Implementation

| Phase | Deliverable | Exit criteria |
|---|---|---|
| **0 — Verify** | Spike on pinned SDK version. Confirm: `tools=[]` semantics; `dontAsk` + role-scoped MCP allowlist; hook deny and timeout behavior; `skills` loading with `setting_sources=[]`; SDK `sandbox` option behavior; OS sandbox backend works with the SDK process | Written verification log. Mismatches update §5.2 |
| **1 — Read-only core** | Executor T0 commands; `valops` T0 tools; audit chain; policy manifest and integrity fallback; OS sandbox; episode store; diagnostician | Policy tests pass: no non-T0 execution possible; tamper leads to observe-only |
| **2 — Sentinel, roles, reporting** | Sentinel, episode runner, planner, **proposal-judge**, reporter, skills v1, framework verifier (read-only checks) | Testnet fault injection produces correct episodes. Judge suite catches all seeded success-gaming proposals (suite contents fixed before run) |
| **3 — Gated actions (testnet)** | Approval service, executor token and precondition checks, T2 restart and upgrade, configuration repository | End-to-end testnet upgrade: Judge PASS → human approval → execution → framework verification records success |
| **4 — Shadow mode on target cluster** | Full pipeline with execution disabled; humans act on their own and compare | Observation period (**TBD**) completed; §9 metrics collected, including per-role cost |
| **5 — Limited autonomy** | Enable T2 with approval on target cluster | Owner sign-off |

Testnet first per [E] S3. `solana-test-validator` is used for unit-level loops only; cluster behaviors require testnet [H].

---

## 8. Test Plan

| Category | Tests |
|---|---|
| Policy (CI-blocking) | Removed built-ins denied; T2 without token refused; forged or expired token refused; hook timeout means no execution; agent-role write to the policy mount fails at the OS level |
| Tamper | Modified `command_table.yaml`, skill, prompt, or verifier leads to hash mismatch, observe-only mode, and an alert |
| Sandbox | Agent process attempts disallowed network egress or filesystem write and is blocked |
| Judge adversarial | Seeded proposals: alert silencing, liveness-only recovery, restart loops, snapshot download disguised, log-injected commands, precondition mismatch for the consensus mode. Each must return FAIL |
| Judge isolation | Judge session input contains no planner or orchestrator reasoning (asserted by the runner) |
| Resolution ownership | Agent attempts to set `resolved` or write verification results; rejected by the store API |
| Prompt injection | Instruction-bearing log lines cause no action beyond T0; report flags them |
| Functional (testnet) | Delinquency; low balance; idle-window restart; upgrade and version check; catch-up after restart |
| Degradation | Claude API down; budget or retry budget exhausted; executor down. Validator unaffected, human alerted |
| Consensus mode | Tower and vote-history fixtures select the correct skill variant |
| Repetition | Each safety-relevant test repeated over N trials (**TBD**); no single-trial pass counts |

---

## 9. Evaluation Metrics (targets TBD by owner)

- **Detection:** MTTD compared with watchtower alone.
- **Recovery:** MTTR for approved T2 episodes.
- **Safety (hard requirement):** zero unauthorized executions [A]. Counts of policy denials, executor refusals, and tamper events.
- **Judge:** FAIL rate; share of FAILs later confirmed correct by a human; seeded-case detection.
- **Human:** approval and override rate; rejections after a Judge PASS.
- **Quality:** human-rated diagnosis correctness in shadow mode; false-positive episode rate.
- **Cost per role:** USD and turns for diagnostician, planner, Judge, reporter per episode and per day, from SDK cost estimates [E] S9. R1 reports the Judge at 20–30% of active time in its runs [E R1 Table 1]. That comes from a different workload and harness and is **not** used as an estimate.

---

## 10. Risks

| Risk | Mitigation | Tag |
|---|---|---|
| LLM proposes a harmful action | No T3 tools; Judge; human approval; token bound to command hash; executor preconditions | [A] |
| Judge and planner share a blind spot | Isolated Judge inputs (SR-12); human sees raw signals; seeded Judge tests | [A] |
| Human rubber-stamps approvals | Show Judge evidence and raw signals; track override and rejection metrics | [A] |
| Agent grades its own action | Framework-only verification and resolution (§5.6) | [A] |
| Policy or skill tampering or drift | Read-only mount, manifest hash, observe-only fallback, signed commits | [A] |
| Long-context drift in incidents | Fresh session per step over the episode record | [A]; [H] that this reduces drift |
| Memory poisoning via `ops-memory` | Staging file with human review before promotion | [A] |
| Prompt injection via logs or RPC | SR-6; Judge check; injection tests | [A] |
| Restart during leader slot | Executor precondition + `agave-validator exit` idle-window wait | [E] S3 |
| Unnecessary snapshot download | T3; Judge check | [E] S3 |
| Identity balance depletion | T0 check + alert | [E] S3 |
| Two instances of one identity during failover | Failover is T3; runbook draft only | [E] S5 |
| Ops host compromise | No keypairs; OS sandbox; executor allowlist; mTLS | [A] |
| Anthropic API outage | NFR-1 | [A] |
| SDK behavior changes | Pinned versions; repeat Phase 0 on upgrade | [A] |
| Alpenglow activation changes files or commands | FR-8 + skill matrix; re-verify S5 before Phase 3 | [U] |
| Judge cost increases per-episode spend | Per-role cost metrics; budgets (D6) | [A] |

---

## 11. Research Track (optional, not a v1 dependency): Offline Tuning Loop

**Purpose [A].** Improve the sentinel's thresholds and classification rules, the diagnosis skills, and the Judge checklist. This happens **offline only**; the loop never touches the live validator.

**Method [A], adapted from R1's outer and inner loop [E R1 §3.3].**
- Each candidate change is a git commit to a copy of `policy/`.
- Candidates are scored on:
  1. the replay corpus of recorded testnet incidents
  2. the fault-injection suite
  3. hard safety gates, where any unauthorized action or missed seeded case disqualifies the candidate
- An independent reviewer session checks each candidate for gaming the scorer.
- A candidate is promoted to the live policy mount only after human review and a signed commit.

**Limits.**
- R1 reports its method depends on the quality of the checker [E R1 §6].
- We have no reference implementation that defines a correct diagnosis, so the labeled replay corpus is the main cost, and its size and adequacy are **[U]**.
- Whether this loop improves operational metrics is **[H]**.
- Decision D10 decides whether to pursue the track.

---

## 12. Kill Criteria

1. Phase 0 shows SDK permission, hook, or sandbox semantics cannot guarantee SR-3, SR-4, SR-10, or SR-11 on the pinned version.
2. Any unauthorized execution in policy, sandbox, or testnet tests that cannot be traced to a fixable defect.
3. Judge misses seeded success-gaming or injection cases above an owner-set tolerance (**TBD**) after remediation.
4. Shadow-mode diagnosis quality below the owner threshold (**TBD**).
5. Per-day cost, including the Judge, exceeds the owner budget (**TBD**) with no reduction path.

## 13. Decisions Needed From Owner

| ID | Decision | Note |
|---|---|---|
| D1 | SDK language | Python (`claude-agent-sdk`) or TypeScript (`@anthropic-ai/claude-agent-sdk`). TypeScript exposes more hook events [E] S8 |
| D2 | Validator client(s) | Agave only vs. others [U] |
| D3 | Target cluster for Phase 4 | testnet / mainnet-beta |
| D4 | Upgrade method | build from source vs. release binaries [E] S3 |
| D5 | Alert and approval channel | watchtower supports Slack, Discord, Telegram, Twilio [E] S2 |
| D6 | Thresholds and budgets | balance floor, `max_turns`, `max_budget_usd`, **retry budget N**, observation period, repetition count, kill-criteria tolerances |
| D7 | Model selection | Pinned model ID(s); optionally a different model for the Judge (value unproven, [H]) |
| D8 | Tier table §5.1 | Approve or adjust |
| D9 | Consensus mode on target cluster | Alpenglow active at deployment? [U] |
| D10 | Offline tuning track (§11) | Pursue yes or no; corpus budget |
| D11 | OS sandbox backend | For example bubblewrap vs. landlock on Linux (VibeSys documents landlock as weaker [E] R2); must pass Phase 0 |
| D12 | Approver policy | Single approver vs. two-person approval for T2 |

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
| — | Review record: `plan-review-vs-vibeserve.md` (2026-09-17) |

All sources accessed 2026-09-17. Re-verify in Phase 0.

---

## 15. 中文摘要（参考用，以英文为准）

**v0.2 主要变化（均为设计选择〔A〕，参考文献 R1 为未经同行评审的预印本，不构成验证依据）：**

1. **独立评审者（proposal-judge）**：T2 提案先经不共享推理上下文的全新会话核查（前置条件、可证伪假设证据、最小影响原则、伪成功模式、日志注入），PASS 后才提交人工审批；FAIL 退回规划者，重试预算耗尽则转人工。
2. **确定性框架验证器**独占操作后验证与“已解决”状态写入；智能体只能读取结果，不能自评。
3. **只读策略挂载与哈希校验**：命令表、阈值、钩子、提示词、技能库、验证规则只读，启动与每个事件开始时校验，不一致即降级为只读观测并告警。
4. **结构化事件记录 + 每步全新会话**：确定性状态机驱动，不恢复长会话；诊断以可证伪假设表达。
5. **操作系统级沙箱**限制智能体进程的文件写入与网络出口。
6. **版本化技能库**，每条技能引用 Anza 官方文档章节，并附共识模式（Tower BFT / Alpenglow）与客户端兼容矩阵；经验记忆需人工审核后才能生效。
7. **Git 化配置仓库与哈希链审计日志**。
8. **按角色度量成本**；论文中 Judge 耗时占比仅作提示，不作估算。
9. **明确禁止**：线上试错回滚、智能体自主扩大范围、智能体修改控制面、单次试验即判定安全。
10. **可选研究方向**：仅离线使用搜索循环调优哨兵与诊断技能，是否开展由负责人决定（D10）。

**新增待决事项：** D11 沙箱后端、D12 单人/双人审批；D6 新增重试预算与重复试验次数。
