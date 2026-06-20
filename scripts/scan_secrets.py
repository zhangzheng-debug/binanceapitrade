from __future__ import annotations

import argparse
import json
import re
import sys
from dataclasses import asdict, dataclass
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from bot.safety import redact_secret  # noqa: E402

EXCLUDED_DIRS = {".venv", ".git", "__pycache__", ".pytest_cache", "logs", "data", "dist"}
TEXT_SUFFIXES = {
    "",
    ".cfg",
    ".env",
    ".example",
    ".ini",
    ".json",
    ".md",
    ".ps1",
    ".py",
    ".sh",
    ".toml",
    ".txt",
    ".yaml",
    ".yml",
}

VALUE_PATTERN = r"(?:\"([^\"\r\n#]+)\"|'([^'\r\n#]+)'|([^ \t\r\n#,]+))"
ASSIGNMENT_PATTERNS = [
    ("BINANCE_API_KEY", re.compile(rf"(?m)^[ \t]*BINANCE_API_KEY[ \t]*=[ \t]*{VALUE_PATTERN}[ \t]*$")),
    ("BINANCE_API_SECRET", re.compile(rf"(?m)^[ \t]*BINANCE_API_SECRET[ \t]*=[ \t]*{VALUE_PATTERN}[ \t]*$")),
    ("TELEGRAM_BOT_TOKEN", re.compile(rf"(?m)^[ \t]*TELEGRAM_BOT_TOKEN[ \t]*=[ \t]*{VALUE_PATTERN}[ \t]*$")),
    ("WEBHOOK_TOKEN", re.compile(rf"(?m)^[ \t]*[A-Z0-9_]*WEBHOOK[A-Z0-9_]*TOKEN[ \t]*=[ \t]*{VALUE_PATTERN}[ \t]*$")),
    (
        "GENERIC_SECRET_ASSIGNMENT",
        re.compile(rf"(?m)^[ \t]*[A-Z0-9_]*(?:SECRET|PRIVATE_KEY|PASSWORD)[ \t]*=[ \t]*{VALUE_PATTERN}[ \t]*$"),
    ),
]
PRIVATE_KEY_PATTERN = re.compile(r"-----BEGIN [A-Z ]*PRIVATE KEY-----")
SSH_PRIVATE_KEY_HINT = re.compile(r"(?im)^\s*(?:openssh-key-v1|Proc-Type:\s*4,ENCRYPTED)\s*$")
LONG_RANDOM_ASSIGNMENT = re.compile(
    r"(?m)^[ \t]*[A-Z0-9_]*(?:KEY|SECRET|TOKEN|WEBHOOK)[A-Z0-9_]*[ \t]*=[ \t]*([A-Za-z0-9_\-+/=]{32,})[ \t]*$"
)


@dataclass(frozen=True)
class Finding:
    path: str
    line: int
    kind: str
    key: str
    redacted_value: str


def should_skip(path: Path) -> bool:
    rel = path.relative_to(ROOT)
    if any(part in EXCLUDED_DIRS for part in rel.parts):
        return True
    if path.name.startswith(".env") and path.name != ".env.example":
        return True
    if path.is_dir():
        return True
    if path.suffix not in TEXT_SUFFIXES and path.name != ".env.example":
        return True
    return False


def line_number(text: str, index: int) -> int:
    return text.count("\n", 0, index) + 1


def scan_text(path: Path, text: str) -> list[Finding]:
    findings: list[Finding] = []
    try:
        rel = path.relative_to(ROOT).as_posix()
    except ValueError:
        rel = path.as_posix()
    for key, pattern in ASSIGNMENT_PATTERNS:
        for match in pattern.finditer(text):
            value = next((group for group in match.groups() if group is not None), "").strip()
            if not value:
                continue
            findings.append(Finding(rel, line_number(text, match.start()), "nonempty_secret_assignment", key, redact_secret(value)))
    for match in LONG_RANDOM_ASSIGNMENT.finditer(text):
        value = match.group(1).strip().strip("\"'")
        if value:
            findings.append(Finding(rel, line_number(text, match.start()), "long_random_secret_like_assignment", "secret_like", redact_secret(value)))
    for match in PRIVATE_KEY_PATTERN.finditer(text):
        findings.append(Finding(rel, line_number(text, match.start()), "private_key_block", "PRIVATE_KEY", "***"))
    for match in SSH_PRIVATE_KEY_HINT.finditer(text):
        findings.append(Finding(rel, line_number(text, match.start()), "ssh_private_key_hint", "SSH_PRIVATE_KEY", "***"))
    return findings


def scan(root: Path = ROOT) -> list[Finding]:
    findings: list[Finding] = []
    for path in sorted(root.rglob("*")):
        if should_skip(path):
            continue
        try:
            text = path.read_text(encoding="utf-8")
        except UnicodeDecodeError:
            continue
        findings.extend(scan_text(path, text))
    return findings


def main() -> int:
    parser = argparse.ArgumentParser(description="Scan project files for accidentally committed secrets.")
    parser.add_argument("--json", action="store_true", help="emit machine-readable JSON")
    args = parser.parse_args()

    findings = scan(ROOT)
    payload = {
        "passed": not findings,
        "findings_count": len(findings),
        "findings": [asdict(finding) for finding in findings],
    }
    if args.json:
        print(json.dumps(payload, indent=2, sort_keys=True))
    else:
        status = "passed" if not findings else "failed"
        print(f"secret_scan={status}")
        print(f"findings_count={len(findings)}")
        for finding in findings:
            print(
                f"{finding.path}:{finding.line} "
                f"kind={finding.kind} key={finding.key} value={finding.redacted_value}"
            )
    return 0 if not findings else 1


if __name__ == "__main__":
    raise SystemExit(main())
