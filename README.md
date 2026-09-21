# valops-agent — M0

A read-only incident-analysis assistant for **one Agave validator on testnet**, working for a named on-call operator. It is **not** an autonomous operator: nothing in this codebase can change the validator. Specified by `solana-agave-node-ops-agent-plan-v0.5.md` (governs) and `valops-agent-mvp-hld-v0.5.md`.

> **Gate status:** both documents are a *conditional no-go until G0*. This code has no gate weight until G0 approves the delivery package, and G1 needs the M0A suites to pass on real boundaries. See `docs/IMPLEMENTATION-NOTES.md` for what is done, what deviates from the documents and why, and what still needs the pinned configuration.

## Architecture (HLD §4)

```
OPS HOST (one uid per process class)                                   VALIDATOR HOST
  sentinel ─┐                                                           valops-observerd (user valops)
  controller (trusted: state machine, tokens, artefact validation)        read-only command table (OD-3)
     │ fork/exec per step, one scoped token                               rate limit · concurrency 1 · RPC breaker
     ▼                                                                    local hash chain → signed checkpoints
  worker (untrusted, bubblewrap: no fs writes, no net but the model broker)      ▲ mTLS, command id only
     ONE adapter: Claude SDK │ codex exec │ agy -p │ native loop                 │
     │ UDS                                                                       │
  episode-broker → store-agent      observer-broker ─────────────────────────────┘
  report-broker  → store-agent-report · alert sink
  model-broker   → Anthropic │ OpenAI │ Google   (sole key holder, only worker egress)
  audit-sequencer (sole chain writer) ──► external anchor (WORM)
  episode store: control · verify · agent · observe endpoints   verifier (only writer of `resolved`)
```

## Layout

| Path | Contents |
|---|---|
| `valops/common/` | UDS JSON-RPC with `SO_PEERCRED` principals, capability tokens, Ed25519, tool catalogue, schema validator |
| `valops/store/` | Episode store: append-only log, fold, CAS transitions, idempotency, contracts, judge view |
| `valops/audit/` | Audit sequencer, anchor stores, chain verification, buffered client |
| `valops/bundle/` | Bundle builder (from the parameter register), registry: verify / activate / drain / revoke / rollback |
| `valops/brokers/` | Episode, observer, report and model brokers |
| `valops/controller/` | Runner state machine, artefact validation, pre-flight tiers, worker spawn |
| `valops/sentinel/`, `valops/verifier/`, `valops/consensus.py` | Deterministic detection, recovery confirmation, consensus-mode cross-check |
| `valops/observer/` | Validator-host daemon |
| `valops/worker/` | Worker entry point, adapters, MCP stubs, hooks, loopback bridge |
| `valops/eval/`, `eval/` | Wilson bounds, frozen fixtures, fault injection with ground-truth log, rubric capture |
| `policy/bundle-src/` | Bundle source: command table, prompts, skills, verifier rules, Judge checklist, providers |
| `policy/dev/` | Development register values and overlay (**no gate weight**) |
| `docs/registers/` | Parameter (P-01…P-31), target (Q-1…Q-8) and decision registers |
| `docs/runbooks/` | RB-01 … RB-14 |
| `deploy/` | systemd units and example configs (ops host, validator host); `deploy/dev/up.sh` |
| `tests/` | containment, policy, concurrency, unit, integration, recovery, conformance, judge |

## Quick start (development)

```bash
python3 -m venv .venv && .venv/bin/pip install -e '.[dev]'
.venv/bin/pytest -q                      # ~100 tests; sandbox tests need bubblewrap
./deploy/dev/up.sh                       # dev keys + dev bundle + configs in ./var/dev
.venv/bin/valops observerd --config var/dev/observerd.yaml &
.venv/bin/valops serve --config var/dev/ops.yaml all
```

The dev stack refuses to call any model until `var/dev/d21-approvals.yaml` records an approval and a real key is in `var/dev/secrets/`. Until then an episode is handed off with `provider_unapproved` (MB-5), which is the intended fail-closed behaviour.

## Operator commands

```bash
valops alerts --config /etc/valops/ops.yaml          # list alerts
valops ack <alert-id> --config /etc/valops/ops.yaml  # AW-3 acknowledgement
valops chain verify --config /etc/valops/ops.yaml    # walk the chain against the anchors
valops bundle list|verify|activate|rollback|revoke --config ...
valops observe-only clear --config ...               # only after the RB-3 / RB-10 exit condition holds
valops check-write-path                              # static write-path-absence check
```
