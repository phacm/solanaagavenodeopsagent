"""Policy bundle builder (HLD §5.4, W5).

src dir + parameter register -> immutable, hash-addressed, signed bundle directory.

    bundles/<bundle-id>/                 bundle-id = sha256(MANIFEST.sha256)
      command_table.yaml thresholds.yaml deployment.yaml providers.yaml pricing.yaml
      fault_classes.yaml judge_checklist.yaml
      prompts/<role>.md  prompts/<role>.inlined.md   (§6.2 skills fallback, always built)
      skills/index.yaml  skills/<skill>/SKILL.md
      verifier/<rule>.yaml
      MANIFEST.sha256  MANIFEST.sha256.sig
"""
from __future__ import annotations

import json
import os
import shutil
import stat
import tempfile
from pathlib import Path

import yaml

from ..common.canonical import b64u, sha256_hex
from ..common.crypto import Signer
from ..common.tokens import ROLES
from ..observer.table import load_table_data
from ..verifier.rules import validate_rule
from .params import generate_thresholds

MANIFEST = "MANIFEST.sha256"
SIG = "MANIFEST.sha256.sig"
REQUIRED = ("command_table.yaml", "deployment.yaml", "providers.yaml", "pricing.yaml",
            "fault_classes.yaml", "judge_checklist.yaml", "skills/index.yaml")
ADAPTERS = ("claude_sdk", "codex_cli", "antigravity_cli", "native")
PROVIDERS = ("anthropic", "openai", "google")
ADMISSION = ("pending", "admitted", "native_only", "not_admitted")
CONSENSUS_MODES = ("tower", "alpenglow")


class BuildError(ValueError):
    pass


def compute_manifest(root: Path) -> bytes:
    lines = []
    for p in sorted(root.rglob("*")):
        if p.is_dir():
            continue
        rel = p.relative_to(root).as_posix()
        if rel in (MANIFEST, SIG):
            continue
        lines.append(f"{sha256_hex(p.read_bytes())}  {rel}")
    return ("\n".join(lines) + "\n").encode()


def _y(root: Path, rel: str):
    with open(root / rel) as f:
        return yaml.safe_load(f)


def _validate(root: Path) -> None:
    for rel in REQUIRED:
        if not (root / rel).is_file():
            raise BuildError(f"missing {rel}")
    load_table_data(_y(root, "command_table.yaml"))  # OD-3: refuses any non-read-only entry

    dep = _y(root, "deployment.yaml")
    if dep.get("client") != "agave":
        raise BuildError("M0 supports the Agave client only (D2)")
    if dep.get("declared_consensus_mode") not in CONSENSUS_MODES:
        raise BuildError("deployment.declared_consensus_mode must be tower|alpenglow")
    for k in ("validator_id", "identity_pubkey", "expected_version", "cluster"):
        if not dep.get(k):
            raise BuildError(f"deployment.{k} required")
    if dep["cluster"] != "testnet":
        raise BuildError("M0 runs on testnet only (D3)")

    prov = _y(root, "providers.yaml")
    confs = prov.get("configurations") or {}
    pricing = _y(root, "pricing.yaml") or {}
    used = set((prov.get("roles") or {}).values())
    for name, c in confs.items():
        if c.get("provider") not in PROVIDERS:
            raise BuildError(f"configuration {name}: provider must be one of {PROVIDERS}")
        if c.get("adapter") not in ADAPTERS:
            raise BuildError(f"configuration {name}: adapter must be one of {ADAPTERS}")
        if c.get("admission") not in ADMISSION:
            raise BuildError(f"configuration {name}: admission must be one of {ADMISSION}")
        if name not in used:
            continue  # declared for the provider track; pinned and priced when a role uses it
        if not c.get("model") or not (c.get("runtime") or {}).get("version") or "REPLACE" in str(c.get("model")) \
                or "REPLACE" in str(c["runtime"]["version"]):
            raise BuildError(f"configuration {name}: exact model and runtime version are required (D7)")
        price = (pricing.get(c["provider"]) or {}).get(c["model"])
        if not price or not all(isinstance(price.get(k), (int, float)) for k in ("input_per_mtok", "output_per_mtok")):
            raise BuildError(f"configuration {name}: no numeric price for {c['provider']}/{c['model']} (P-31)")
    roles = prov.get("roles") or {}
    for r in ROLES:
        if roles.get(r) not in confs:
            raise BuildError(f"providers.roles.{r} must name a configuration")
    if len({roles[r] for r in ROLES}) != 1 and not prov.get("allow_mixed_configurations"):
        # plan §5.12.4 default: one configuration serves all roles; a cross-provider judge is D22.
        raise BuildError("one configuration must serve all roles in M0 (D22 not used)")
    for p in (prov.get("endpoints") or {}):
        if p not in PROVIDERS:
            raise BuildError(f"unknown provider endpoint {p}")

    idx = _y(root, "skills/index.yaml") or {}
    for name, s in (idx.get("skills") or {}).items():
        if not (root / "skills" / name / "SKILL.md").is_file():
            raise BuildError(f"skill {name} has no SKILL.md")
        modes = s.get("modes")
        if modes != "any" and (not isinstance(modes, list) or not set(modes) <= set(CONSENSUS_MODES)):
            raise BuildError(f"skill {name}: modes must be 'any' or a subset of {CONSENSUS_MODES}")
        for r in s.get("roles", []):
            if r not in ROLES:
                raise BuildError(f"skill {name}: unknown role {r}")
    for r in ROLES:
        if not (root / "prompts" / f"{r}.md").is_file():
            raise BuildError(f"missing prompts/{r}.md")
    for p in sorted((root / "verifier").glob("*.yaml")):
        validate_rule(_y(root, f"verifier/{p.name}"), p.name)


def _inline_skills(root: Path) -> None:
    """§6.2 fallback: concatenate each role's permitted skills into its prompt file."""
    idx = (_y(root, "skills/index.yaml") or {}).get("skills") or {}
    for r in ROLES:
        parts = [(root / "prompts" / f"{r}.md").read_text()]
        for name, s in sorted(idx.items()):
            if r in s.get("roles", []):
                body = (root / "skills" / name / "SKILL.md").read_text()
                parts.append(f"\n\n---\n## Skill: {name} (modes: {s.get('modes')})\n\n{body}")
        (root / "prompts" / f"{r}.inlined.md").write_text("".join(parts))


def _make_read_only(root: Path) -> None:
    for p in sorted(root.rglob("*"), reverse=True):
        mode = stat.S_IMODE(p.stat().st_mode)
        os.chmod(p, mode & ~0o222)
    os.chmod(root, stat.S_IMODE(root.stat().st_mode) & ~0o222)


def build(src: Path, register: dict, out_root: Path, *, signer: Signer | None, key_id: str,
          overlay: Path | None = None) -> str:
    """Build a bundle. Returns the bundle id. With ``signer=None`` the bundle is left
    unsigned in a staging directory for offline (hardware-token) signing (D14)."""
    thresholds = generate_thresholds(register)
    out_root.mkdir(parents=True, exist_ok=True)
    stage = Path(tempfile.mkdtemp(prefix=".stage-", dir=out_root))
    try:
        shutil.copytree(src, stage, dirs_exist_ok=True)
        if overlay is not None:  # development overlays only (policy/dev/overlay); marked in deployment.yaml
            shutil.copytree(overlay, stage, dirs_exist_ok=True)
        for junk in list(stage.rglob("__pycache__")) + list(stage.rglob("*.pyc")):
            shutil.rmtree(junk, ignore_errors=True) if junk.is_dir() else junk.unlink()
        with open(stage / "thresholds.yaml", "w") as f:
            yaml.safe_dump(thresholds, f, sort_keys=True)
        _validate(stage)
        _inline_skills(stage)
        manifest = compute_manifest(stage)
        (stage / MANIFEST).write_bytes(manifest)
        bundle_id = sha256_hex(manifest)
        if signer is None:
            unsigned = out_root / f".unsigned-{bundle_id}"
            if unsigned.exists():
                shutil.rmtree(unsigned)
            stage.rename(unsigned)
            return bundle_id
        attach_signature(stage, key_id, signer.sign(manifest))
        final = out_root / bundle_id
        if final.exists():
            shutil.rmtree(stage)  # content-addressed: identical bundle already present
            return bundle_id
        _make_read_only(stage)
        stage.rename(final)
        return bundle_id
    except Exception:
        shutil.rmtree(stage, ignore_errors=True)
        raise


def attach_signature(bundle_dir: Path, key_id: str, sig: bytes) -> None:
    (bundle_dir / SIG).write_text(json.dumps({"key_id": key_id, "sig": b64u(sig)}))
