# Implementation notes — M0 codebase vs. plan v0.5 / HLD v0.5

**Status.** Both documents say *conditional no-go for implementation until G0*. This code was
written ahead of G0 at the owner's request. It carries **no gate weight** until G0 approves the
delivery package, and nothing in it counts toward G1 until the M0A suites run on real boundaries
(HLD §10.1). Values that the registers mark *set at G0* are left unset; the bundle builder refuses
to build until they are set.

## 1. Work items → code

| HLD item | What it is | Where |
|---|---|---|
| W2 | Observer daemon: command table + OD-3 loader, typed args, redaction, rate limit, concurrency 1, RPC breaker, local chain, mTLS, systemd limits | `valops/observer/`, `deploy/validator-host/` |
| W3 | Episode store: three endpoints (+ N-1), CAS, idempotency, append-only triggers, contract checks incl. rank uniqueness and the evidence-reference bridge | `valops/store/` |
| W4 | Audit sequencer: single writer, server-stamped actor, fsync, payloads by reference, signed anchors (file / S3 object lock), daemon checkpoints, `verify_chain` | `valops/audit/` |
| W5 | Policy bundles: build from register, sign, verify per bound id, activate, drain, revoke, rollback, retired keys | `valops/bundle/`, `policy/bundle-src/` |
| W6 | Controller spawn, token minting, bwrap sandbox (fail closed), adapter framework, Claude adapter | `valops/controller/spawn.py`, `valops/sandbox/`, `valops/worker/` |
| W6b | Model broker: per-session UDS, route/model/limit checks, credential strip + inject, metering, transcript audit, D21 gate | `valops/brokers/model_broker.py`, `providers.py` |
| W7 | Episode / observer / report brokers re-enforcing every hook check | `valops/brokers/` |
| W9 | MCP tool stubs (in-process for Claude SDK; stdio server for Codex/Antigravity) | `valops/worker/tools/` |
| W10 | `PreToolUse` policy gate + audit hooks (defence in depth) | `valops/worker/hooks/` |
| W11 | Sentinel + telemetry probes | `valops/sentinel/` |
| W12 | Controller state machine + artefact validation | `valops/controller/runner.py`, `artefacts.py` |
| W13/W14 | Skills v1 with compatibility matrix, inlined-prompt fallback, role prompts, Judge checklist | `policy/bundle-src/` |
| W15 | Recovery verifier + consensus-mode determination | `valops/verifier/`, `valops/consensus.py` |
| W16 | Reporter path: report store, alert sinks, AW-3 escalation, closure report | `valops/brokers/report_broker.py`, `alerts.py` |
| W17 | Test suites | `tests/` |
| W19 | Evaluation support: injections + ground-truth log, rubric capture, frozen fixtures, Wilson bounds | `eval/`, `valops/eval/` |
| W21–W23 | Codex / Antigravity launchers (guarded), native API adapter for all three providers | `valops/worker/adapters/` |
| — | Static write-path-absence check | `valops/writepath.py` (`valops check-write-path`) |

`executor/` and `approval/` are absent by design (§0.1, §2.2).

## 2. Deviations and design decisions to review

| ID | Where the documents say | What the code does | Why |
|---|---|---|---|
| N-1 | Store has three endpoints (§5.3) | Adds a narrow `store-observe` socket for the observer broker: `append_observation` only | A tool-driven re-sample must become a citable signal, or `evidence_refs` could only cite sentinel samples. The content comes from the daemon via the broker, never from the worker. |
| N-2 | One `store-agent` endpoint | Split per broker: `agent.sock` (episode broker) and `agent-report.sock` (report broker, `append_report` + `read_episode` only) | The socket is the principal; with one shared socket the principal would depend on a uid map. |
| N-3 | Broker sockets are "inherited fds" (§4.1) | Socket files are bind-mounted into the sandbox and the worker connects itself | `SO_PEERCRED` is captured at `connect()`. A socket connected by the controller and inherited by the worker would carry the controller's credentials. |
| N-4 | §7.2: `judging → reporting` when Judge retries are exhausted; R-3, §9, RB-2: `handed_off` | `handed_off` + alert with every FAIL reason | Three places say hand-off; it is the safer reading. The HLD should reconcile §7.2. |
| N-5 | §5.7 text: no-action "routes the episode to reporting"; §7.2 table: `recommending → judging` for either artefact | No-action is judged like a recommendation (checklist item `no_action_justified`) | The transition table is normative and has no `recommending → reporting` row. |
| N-6 | Judge view = signals, proposal, skill preconditions (SR-12) | Also verification records and recovery observations | §7.5 gives the Judge `get_verification_result`; these are deterministic observations, not reasoning. |
| N-7 | Mode-specific proposals under `unknown` are caught by the Judge | The store also rejects a recommendation whose skill is mode-specific when the mode is `unknown` or mismatched | Deterministic layer in front of an MQ control. |
| N-8 | Reporter sends the AW-2 alert | The report broker fills severity, fault class, top hypothesis, recommendation, verdict and report link **from the record**; the model supplies only a labelled summary | A persuaded reporter cannot misstate the verdict in the alert. |
| N-9 | Terminal states accept only reports (§7.2) | Also recovery observations (§7.3 requires them after hand-off) and controller bookkeeping (cost, step, annotation) | The closure step's cost must be recorded somewhere. |
| N-10 | — | The Anthropic native binding does **not** enable server-side refusal fallbacks | A fallback would answer with a different model, which the pinned-model rule (D7, MB step 3) forbids and which would pool results across configurations. |
| N-11 | MB step 9 audit, step 10 return | The broker relays the response, then audits | Streaming relay. The transcript entry follows the response by milliseconds. |
| N-12 | Usage from the provider response | If usage can't be parsed, the session is charged estimated input plus the clamped maximum output | Conservative, so limits still bind. |
| N-13 | `draft_failover_runbook` (text only) | Returns the bound bundle's failover checklist section for the **confirmed** mode; withheld under `unknown` | No new store operation is needed; nothing executes. |
| N-14 | Controller spawns workers under the worker uid | The controller unit keeps only `CAP_SETUID` and `CAP_SETGID` | Needed for `Popen(user=…)`. |
| N-15 | Delinquency check from "validator monitor / catch-up status" | Uses catch-up distance over P-03 consecutive samples | `monitor` output is not a stable interface [U]. Parsers are W2 items. |
| N-16 | Per-role quotas | Episode-broker writes ≤ 4 × P-05; hook tool calls ≤ 3 × P-05; observer tools ≤ P-14 per session | Not in the register. Candidates for P-3x rows via change control. |
| N-17 | Judge-isolation assertion (§10.2) | Checks the view **minus** the artefact under judgement, which is planner-written by definition | Otherwise any planner that quotes a hypothesis would trip it. |

## 3. Not done — needs the pinned configuration, real boundaries or credentials

- **W0/G0.** No decision is closed. Every `REPLACE_AT_*` in `policy/bundle-src/` and every `null` in `docs/registers/` must be set at G0.
- **W1, W1-O, W1-G.** The Claude SDK options (`valops/worker/adapters/claude_sdk/options.py`) follow HLD §6.1 but have not been run against a pinned SDK. Open items: `tools=["Skill", …]`, skills with `setting_sources=[]`, `ANTHROPIC_BASE_URL` routing, and `failIfUnavailable`. Fail-closed currently comes from the controller's bwrap pre-flight. The Codex `config.toml` keys marked [U] are unverified. The Antigravity launcher refuses to run until W1-G records a verified endpoint override.
- **Real-boundary runs (G1).** None yet: separate uids per class, the minimal per-runtime rootfs (`worker-rootfs/README.md`), the S3 object-lock anchor store (implemented, not exercised), mTLS between hosts (implemented, not exercised; tests use the daemon in-process), and real provider keys through the broker.
- **MQ suites.** Judge adversarial (judge layer), diagnosis quality and operator value need a live model and the testnet validator. The fixtures and statistics are in place (`eval/`).
- **Watchtower integration.** The sentinel only checks a heartbeat file (`watchtower_heartbeat`). Ingesting watchtower notifications as `source: watchtower` triggers is not built.
- **Offline signing (D14).** `valops bundle build` without `--key` leaves an unsigned staging bundle. The hardware-token signing step and `attach_signature` wiring into the CLI still need to be done.

## 4. Running the tests

    python3 -m venv .venv && .venv/bin/pip install -e '.[dev]'
    .venv/bin/pytest -q

The tests use real Unix sockets, real SQLite, real Ed25519 signatures and the local bubblewrap
backend (the sandbox tests skip without it). They run under one uid with a file anchor store, a
fake observer and a fake provider, so they are **development evidence only**.
