"""Static write-path-absence check (HLD §10.2, G2 safety item 2).

  * `executor/` and `approval/` are absent from the artefact (M1+ only, §0.1);
  * every bundle's command table (source and built) passes the OD-3 loader;
  * no module in the shipped package spawns a process except the audited sites below,
    and none of those take argv from a tool call.
"""
from __future__ import annotations

import re
from pathlib import Path

import yaml

from .observer.table import TableError, load_table_data

# The only modules allowed to spawn processes, and why none is a validator write path.
SPAWN_ALLOWED = {
    "valops/observer/daemon.py": "argv from the OD-3-validated read-only command table",
    "valops/observer/builtins.py": "fixed read-only argv: systemctl is-active, ss -ltnH",
    "valops/controller/spawn.py": "launches the sandboxed worker on the ops host",
    "valops/sandbox/bwrap.py": "bwrap availability probe",
    "valops/worker/adapters/codex_cli/launcher.py": "codex runtime inside the worker sandbox",
    "valops/worker/adapters/antigravity_cli/launcher.py": "agy runtime inside the worker sandbox",
}
_SPAWN = re.compile(r"\b(subprocess\.|os\.system|os\.exec|os\.spawn|Popen\()")


def check(root: Path) -> list[str]:
    problems = []
    for d in ("executor", "approval", "valops/executor", "valops/approval"):
        if (root / d).exists():
            problems.append(f"{d}/ present: M0 must not ship an executor or approval service")
    for tbl in list(root.glob("policy/**/command_table.yaml")) + list(root.glob("var/**/command_table.yaml")):
        try:
            load_table_data(yaml.safe_load(tbl.read_text()))
        except TableError as e:
            problems.append(f"{tbl}: {e}")
    for py in (root / "valops").rglob("*.py"):
        rel = py.relative_to(root).as_posix()
        if _SPAWN.search(py.read_text()) and rel not in SPAWN_ALLOWED and rel != "valops/writepath.py":
            problems.append(f"{rel}: spawns a process outside the audited sites")
    return problems
