"""Observer command table loader (HLD §5.11 OD-1 … OD-3, §7.4).

The loader REFUSES the whole table (the daemon does not start, the bundle does not
build) if any entry:
  * is not marked ``read_only: true``;
  * uses an executable/subcommand pair outside the read-only allowlist;
  * contains a state-changing token (denylist, belt and braces);
  * contains a shell metacharacter, or a placeholder not in the known set.
argv is a list; it is executed without a shell (OD-2). M0 contains no state-changing
command (DD-5); adding one requires a code change here plus a new bundle plus review.
"""
from __future__ import annotations

import re
from dataclasses import dataclass, field
from pathlib import Path

import yaml


class TableError(ValueError):
    pass


# (executable, first positional subcommand) pairs that only read. Anything else refused.
READ_ONLY_EXEC = {
    "solana": {"catchup", "balance", "leader-schedule", "epoch-info", "slot", "cluster-version", "validators", "feature"},
    "agave-validator": {"monitor"},
}
BUILTINS = {"host_metrics", "host_hygiene", "consensus_state_files", "rpc_latency", "log_tail", "running_version"}
STATE_CHANGING = {
    "exit", "set-identity", "authorized-voter", "set-log-filter", "set-public-address", "repair-whitelist",
    "staked-nodes-overrides", "wait-for-restart-window", "transfer", "pay", "airdrop", "deploy", "program",
    "withdraw-stake", "withdraw-from-vote-account", "delegate-stake", "deactivate-stake", "split-stake",
    "merge-stake", "create-stake-account", "create-vote-account", "close-vote-account", "vote-authorize-voter",
    "vote-authorize-withdrawer", "vote-update-validator", "vote-update-commission", "stake-authorize",
    "redelegate-stake", "rm", "mv", "cp", "dd", "kill", "pkill", "killall", "systemctl", "service", "reboot",
    "shutdown", "restart", "stop", "start", "sudo", "su", "chmod", "chown", "tee", "truncate", "curl", "wget",
    "sh", "bash", "python", "python3", "--no-snapshot-fetch", "--snapshot", "download",
}
PLACEHOLDERS = {"ledger", "logfile", "identity_pubkey", "rpc_url", "epoch", "lines"}
_META = re.compile(r"[;|&$`<>(){}*?!\\\n\r'\"~]")
_PLACEHOLDER = re.compile(r"^\{([a-z_]+)\}$")
ARG_TYPES = {"int", "pubkey"}


@dataclass(frozen=True)
class ArgSpec:
    type: str
    min: int | None = None
    max: int | None = None
    required: bool = False


@dataclass(frozen=True)
class Command:
    id: str
    kind: str                         # exec | builtin | unavailable
    argv: tuple[str, ...] = ()
    optional_argv: dict[str, tuple[str, ...]] = field(default_factory=dict)
    args: dict[str, ArgSpec] = field(default_factory=dict)
    parser: str | None = None
    timeout_s: float = 15.0
    output_cap_bytes: int = 16384
    timeout_is_sample: bool = False   # e.g. `monitor` never exits; the capped output is the sample
    rpc_backed: bool = False          # suspended while the OD-9 breaker is open


@dataclass(frozen=True)
class CommandTable:
    version: int
    commands: dict[str, Command]


def _check_tokens(cid: str, tokens: list[str]) -> None:
    for tok in tokens:
        if not isinstance(tok, str) or not tok:
            raise TableError(f"{cid}: argv tokens must be non-empty strings")
        m = _PLACEHOLDER.match(tok)
        if m:
            if m.group(1) not in PLACEHOLDERS:
                raise TableError(f"{cid}: unknown placeholder {tok}")
            continue
        if _META.search(tok):
            raise TableError(f"{cid}: shell metacharacter in token {tok!r}")
        if tok.lower() in STATE_CHANGING:
            raise TableError(f"{cid}: state-changing token {tok!r}")


def load_table_data(data: dict) -> CommandTable:
    if not isinstance(data, dict) or not isinstance(data.get("commands"), dict):
        raise TableError("command table must have a `commands` mapping")
    out: dict[str, Command] = {}
    for cid, e in data["commands"].items():
        if not re.fullmatch(r"[a-z][a-z0-9_]{1,40}", cid):
            raise TableError(f"bad command id {cid!r}")
        if e.get("read_only") is not True:
            raise TableError(f"{cid}: every M0 command must be marked read_only: true (OD-3)")
        kind = e.get("kind")
        args = {}
        for aname, a in (e.get("args") or {}).items():
            if aname not in PLACEHOLDERS or a.get("type") not in ARG_TYPES:
                raise TableError(f"{cid}: bad arg spec {aname}")
            args[aname] = ArgSpec(a["type"], a.get("min"), a.get("max"), bool(a.get("required")))
        if kind == "exec":
            argv = list(e.get("argv") or [])
            if not argv:
                raise TableError(f"{cid}: empty argv")
            exe = argv[0]
            if exe not in READ_ONLY_EXEC:
                raise TableError(f"{cid}: executable {exe!r} not in the read-only allowlist")
            sub = next((t for t in argv[1:] if not t.startswith("-") and not _PLACEHOLDER.match(t)), None)
            if sub not in READ_ONLY_EXEC[exe]:
                raise TableError(f"{cid}: {exe} {sub!r} is not a read-only subcommand")
            _check_tokens(cid, argv)
            opt = {}
            for aname, toks in (e.get("optional_argv") or {}).items():
                if aname not in args:
                    raise TableError(f"{cid}: optional_argv for undeclared arg {aname}")
                _check_tokens(cid, list(toks))
                opt[aname] = tuple(toks)
            cmd = Command(cid, kind, tuple(argv), opt, args, e.get("parser"), float(e.get("timeout_s", 15)),
                          int(e.get("output_cap_bytes", 16384)), bool(e.get("timeout_is_sample", False)),
                          bool(e.get("rpc_backed", False)))
        elif kind == "builtin":
            if cid not in BUILTINS:
                raise TableError(f"{cid}: no such builtin")
            cmd = Command(cid, kind, args=args, timeout_s=float(e.get("timeout_s", 10)),
                          output_cap_bytes=int(e.get("output_cap_bytes", 16384)), rpc_backed=bool(e.get("rpc_backed", False)))
        elif kind == "unavailable":
            cmd = Command(cid, kind)
        else:
            raise TableError(f"{cid}: kind must be exec|builtin|unavailable")
        out[cid] = cmd
    return CommandTable(int(data.get("version", 1)), out)


def load_table(path: str | Path) -> CommandTable:
    with open(path) as f:
        return load_table_data(yaml.safe_load(f))
