from __future__ import annotations

import hashlib
import io
import json
import os
import re
import subprocess
import sys
import tarfile
from datetime import UTC, datetime
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
DIST = ROOT / "dist"
BUNDLE_NAME = os.environ.get("DEPLOY_BUNDLE_NAME", "ethusdc-pivot-bot-original-pivot-fast-smoke.tar.gz")
BUNDLE = DIST / BUNDLE_NAME
REPORTS = ROOT / "reports"
BUNDLE_REPORT_NAME = os.environ.get("DEPLOY_BUNDLE_REPORT_NAME", "deploy_bundle_original_pivot.json")
BUNDLE_REPORT = REPORTS / BUNDLE_REPORT_NAME
BUNDLE_PHASE = os.environ.get("DEPLOY_BUNDLE_PHASE", "original_pivot_strategy_fast_smoke")

INCLUDE_TOP_LEVEL = {
    "config",
    "deploy",
    "src",
    "tests",
    "tools",
    "docs",
    "scripts",
    "README.md",
    "pyproject.toml",
    "pytest.ini",
    ".env.example",
    ".gitignore",
}

SECRET_PATTERNS = [
    re.compile(b"-----BE" + b"GIN " + rb"[A-Z ]*" + b"PRIVATE" + b" KEY-----"),
    re.compile(rb"(?m)^BINANCE_API_KEY[ \t]*=[ \t]*[^ \t\r\n#]+"),
    re.compile(rb"(?m)^BINANCE_API_SECRET[ \t]*=[ \t]*[^ \t\r\n#]+"),
    re.compile(rb"(?m)^TELEGRAM_BOT_TOKEN[ \t]*=[ \t]*[^ \t\r\n#]+"),
    re.compile(rb"(?m)^TELEGRAM_CHAT_ID[ \t]*=[ \t]*[^ \t\r\n#]+"),
]


def should_include(path: Path) -> bool:
    rel = path.relative_to(ROOT)
    parts = rel.parts
    if not parts:
        return False

    allowed_keep = {("logs", ".gitkeep"), ("data", ".gitkeep"), ("reports", ".gitkeep")}
    if parts[0] not in INCLUDE_TOP_LEVEL and parts[:2] not in allowed_keep:
        return False
    if any(part in {".venv", ".git", "__pycache__", ".pytest_cache", "dist"} for part in parts):
        return False
    if rel.name == ".env":
        return False
    if parts[0] == "logs":
        return rel.as_posix() == "logs/.gitkeep"
    if parts[0] == "data":
        return rel.as_posix() == "data/.gitkeep"
    if parts[0] == "reports":
        return rel.as_posix() == "reports/.gitkeep"
    if rel.suffix in {".pyc", ".pyo"}:
        return False
    return path.is_file()


def secret_scan(path: Path) -> None:
    data = path.read_bytes()
    if path.name == ".env.example":
        # Empty placeholders are expected here; nonempty values are still caught.
        pass
    for pattern in SECRET_PATTERNS:
        if pattern.search(data):
            raise RuntimeError(f"refusing to bundle possible secret in {path.relative_to(ROOT)}")


def add_empty_dir(tar: tarfile.TarFile, name: str) -> None:
    info = tarfile.TarInfo(name)
    info.type = tarfile.DIRTYPE
    info.mode = 0o755
    tar.addfile(info)


def add_file_normalized(tar: tarfile.TarFile, path: Path, arcname: str) -> None:
    if path.suffix == ".sh":
        data = path.read_text(encoding="utf-8").replace("\r\n", "\n").replace("\r", "\n").encode("utf-8")
        info = tarfile.TarInfo(arcname)
        info.size = len(data)
        info.mode = 0o755
        info.mtime = int(path.stat().st_mtime)
        tar.addfile(info, io.BytesIO(data))
        return
    tar.add(path, arcname=arcname, recursive=False)


def main() -> int:
    DIST.mkdir(exist_ok=True)
    REPORTS.mkdir(exist_ok=True)
    if BUNDLE.exists():
        BUNDLE.unlink()

    subprocess.run([sys.executable, str(ROOT / "scripts" / "scan_secrets.py")], cwd=ROOT, check=True)

    files = sorted(path for path in ROOT.rglob("*") if should_include(path))
    for path in files:
        secret_scan(path)

    with tarfile.open(BUNDLE, "w:gz") as tar:
        add_empty_dir(tar, "ethusdc-pivot-bot")
        for path in files:
            rel = path.relative_to(ROOT).as_posix()
            add_file_normalized(tar, path, f"ethusdc-pivot-bot/{rel}")

    digest = hashlib.sha256(BUNDLE.read_bytes()).hexdigest()
    sha_path = BUNDLE.with_suffix(BUNDLE.suffix + ".sha256")
    sha_path.write_text(f"{digest}  {BUNDLE.name}\n", encoding="utf-8")
    BUNDLE_REPORT.write_text(
        json.dumps(
            {
                "bundle": str(BUNDLE.relative_to(ROOT)),
                "sha256": digest,
                "files": len(files),
                "generated_at_utc": datetime.now(tz=UTC).isoformat(),
                "phase": BUNDLE_PHASE,
                "excludes": [
                    ".venv",
                    ".git",
                    "__pycache__",
                    ".pytest_cache",
                    "logs/* except .gitkeep",
                    "data/*.sqlite*",
                    ".env",
                    "dist",
                    "runtime reports except reports/.gitkeep",
                ],
            },
            indent=2,
            sort_keys=True,
        ),
        encoding="utf-8",
    )
    print(f"bundle={BUNDLE}")
    print(f"sha256={digest}")
    print(f"files={len(files)}")
    print(f"report={BUNDLE_REPORT}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
