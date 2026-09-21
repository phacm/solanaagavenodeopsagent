#!/usr/bin/env bash
# Development bootstrap: dev keys, a dev bundle (dev register + dev overlay), configs.
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/../.." && pwd)"
V="$ROOT/var/dev"
PY="${PYTHON:-$ROOT/.venv/bin/python}"
mkdir -p "$V"
[ -f "$V/keys/token.pem" ] || "$PY" -m valops.cli keygen "$V/keys"
BID=$("$PY" -m valops.cli bundle build --src "$ROOT/policy/bundle-src" --overlay "$ROOT/policy/dev/overlay" \
      --register "$ROOT/policy/dev/parameters.dev.yaml" --out "$V/bundles" --key "$V/keys/bundle.pem" --key-id dev-1 | tail -1)
RUN="/tmp/valops-dev-$(id -u)"
cat > "$V/ops.yaml" <<YAML
development: true
dev_single_uid: true
runtime_dir: $RUN
state_dir: $V/state
bundles_dir: $V/bundles
keys:
  token_private: $V/keys/token.pem
  token_public: $V/keys/token.pub.pem
  chain_private: $V/keys/chain.pem
  chain_public: $V/keys/chain.pub.pem
  chain_key_id: dev-chain
  daemon_public: $V/keys/daemon.pub.pem
  bundle_trusted: [{key_id: dev-1, public: $V/keys/bundle.pub.pem, status: active}]
anchor_interval_min: 15
anchor: {kind: file, path: $V/anchors.jsonl}
observer: {url: "http://127.0.0.1:18443"}
alerts: {kind: file, path: $V/alerts.jsonl}
model_broker:
  keys: {anthropic: $V/secrets/anthropic.key}
  approvals_file: $V/d21-approvals.yaml
sandbox: {host_ro_dev: true, python_path: /opt/valops}
YAML
mkdir -p "$V/secrets" && [ -f "$V/secrets/anthropic.key" ] || { echo "REPLACE_WITH_DEV_KEY" > "$V/secrets/anthropic.key"; chmod 600 "$V/secrets/anthropic.key"; }
cat > "$V/d21-approvals.yaml" <<YAML
providers: {anthropic: {approved: false, record: null}}   # set approved+record only with a real D21 approval
YAML
cat > "$V/observerd.yaml" <<YAML
development: true
listen: {host: 127.0.0.1, port: 18443}
command_table: $V/bundles/$BID/command_table.yaml
rate_per_min: 6
breaker_threshold_ms: 500
local: {ledger: $V/ledger, logfile: $V/validator.log, identity_pubkey: "11111111111111111111111111111111", rpc_url: "http://127.0.0.1:8899", unit_name: sol.service}
chain: {path: $V/observer-chain.jsonl, key: $V/keys/daemon.pem}
YAML
mkdir -p "$V/ledger" && touch "$V/validator.log"
"$PY" -m valops.cli bundle activate "$BID" --config "$V/ops.yaml" --by dev
echo "dev bundle $BID active; configs in $V"
