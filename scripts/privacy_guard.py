"""Block personal identities and sensitive files before public Git updates.

Reports contain object IDs, paths and categories, never matched contact/secret values.
GitHub's read-only PR/cache refs are a separate platform cleanup boundary.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import re
import subprocess
import sys
from pathlib import Path, PurePosixPath

EMAIL = re.compile(rb"[A-Za-z0-9_.+\-]+@[A-Za-z0-9.\-]+\.[A-Za-z]{2,}")
PATTERNS = {
    "github-token": rb"(?:gh[pousr]_[A-Za-z0-9]{30,}|github_pat_[A-Za-z0-9_]{50,})",
    "openai-key": rb"sk-(?:proj-|svcacct-)?[A-Za-z0-9_-]{32,}",
    "google-api-key": rb"AIza[0-9A-Za-z_-]{30,}",
    "private-key": rb"-----BEGIN (?:RSA |EC |OPENSSH |ENCRYPTED )?PRIVATE KEY-----[\s\S]{40,}?"
    rb"-----END (?:RSA |EC |OPENSSH |ENCRYPTED )?PRIVATE KEY-----",
    "personal-path": rb"(?i)[a-z]:[\\/]+Users[\\/]+(?!Public\b|Default\b)[\w.-]+[\\/]",
    "unix-personal-path": rb"/(?:Users|home)/[A-Za-z0-9_.-]+/",
    "credential-url": rb"https?://[^\s/<>:@]+:[^\s/<>@]+@[^\s<>]+",
    "phone-shaped-value": rb"(?<![A-Za-z0-9])1[3-9][0-9]{9}(?![A-Za-z0-9])",
}
PRIVATE_NAMES = {".env", "history.json", "id_rsa", "id_ed25519", "credentials.json", "auth.json"}
PRIVATE_DIRS = {".git", ".venv", "__pycache__", "archive", "release", "build", "deployment", "history"}


def git(root: Path, *args: str) -> bytes:
    return subprocess.run(["git", "-C", str(root), *args], check=True, capture_output=True).stdout


def safe_identity(email: str) -> bool:
    return re.fullmatch(r"[^\s<>@]+@users\.noreply\.github\.com|noreply@github\.com", email, re.I) is not None


def private_path(name: str) -> bool:
    path = PurePosixPath(name.replace("\\", "/"))
    return (
        path.name.lower() in PRIVATE_NAMES
        or (path.name.lower().startswith(".env.") and path.name.lower() != ".env.example")
        or (path.name.upper().startswith("PRIVATE_") and path.suffix.lower() not in {".py", ".qml"})
        or any(part.lower() in PRIVATE_DIRS for part in path.parts)
        or "docs/audits/" in str(path).lower()
    )


def allowed_contacts(root: Path) -> set[str]:
    policy = json.loads((root / ".privacy-policy.json").read_text(encoding="utf-8"))
    if policy.get("schema_version") != 1:
        raise ValueError("Unsupported privacy policy")
    return set(policy["reviewed_public_contact_sha256"]) | {
        "binary:" + digest for digest in policy.get("reviewed_font_contact_sha256", [])
    }


def representations(data: bytes) -> list[bytes]:
    values = [data]
    if b"\0" in data:
        values.extend(data[i:].decode("utf-16-le", errors="ignore").encode() for i in (0, 1))
    return values


def contact_categories(data: bytes, allowed: set[str]) -> list[str]:
    # Only exact reviewed font bytes may contain random email-shaped glyph-table data.
    # Changed fonts and all other categories still go through the normal scan.
    if "binary:" + hashlib.sha256(data).hexdigest() in allowed:
        return []
    for value in representations(data):
        for match in EMAIL.finditer(value):
            email = match[0].decode("ascii").lower()
            domain = email.rsplit("@", 1)[1]
            synthetic = domain in {"example.com", "example.net", "example.org"} or domain.endswith(
                (".example", ".invalid", ".test")
            )
            if (
                not safe_identity(email)
                and not synthetic
                and hashlib.sha256(email.encode()).hexdigest() not in allowed
            ):
                return ["unreviewed-contact-email"]
    return []


def content_categories(data: bytes, allowed: set[str]) -> list[str]:
    values = representations(data)
    return contact_categories(data, allowed) + [
        name for name, pattern in PATTERNS.items() if any(re.search(pattern, value) for value in values)
    ]


def audit_metadata(root: Path, refs: list[str], *, tags: bool = True) -> list[dict[str, str]]:
    findings = []
    records = git(root, "log", "--format=%H%x00%ae%x00%ce", *refs, "--").decode("utf-8").splitlines()
    for row in records:
        oid, author, committer = row.split("\0")
        for role, email in (("author", author), ("committer", committer)):
            if not safe_identity(email):
                findings.append({"commit": oid, "role": role, "category": "non-noreply-identity"})
    candidates = list(refs)
    if tags:
        candidates.extend(git(root, "for-each-ref", "refs/tags", "--format=%(refname)").decode().splitlines())
    for ref in dict.fromkeys(candidates):
        oid = git(root, "rev-parse", "--verify", ref).decode().strip()
        # Follow nested annotated tags, rather than inspecting only the outer tagger.
        while git(root, "cat-file", "-t", oid).strip() == b"tag":
            raw = git(root, "cat-file", "-p", oid)
            tagger = re.search(rb"^tagger .*<([^<>]+)> \d+ [+-]\d+$", raw, re.M)
            if tagger is None or not safe_identity(tagger[1].decode(errors="replace")):
                findings.append({"object": oid, "role": "tagger", "category": "non-noreply-identity"})
            oid = raw.splitlines()[0].split()[1].decode()
    return findings


def audit_content(root: Path, refs: list[str], *, staged: bool, history: bool) -> list[dict[str, str]]:
    allowed = allowed_contacts(root)
    findings = []

    def check(oid: str, name: str, data: bytes) -> None:
        categories = content_categories(data, allowed)
        if private_path(name):
            categories.append("private-artifact-path")
        findings.extend({"object": oid, "path": name, "category": c} for c in categories)

    if staged:
        names = git(root, "diff", "--cached", "--name-only", "--diff-filter=ACMR", "-z").decode().split("\0")
        for name in filter(None, names):
            check("index", name, git(root, "show", ":" + name))
        return findings
    if not history:
        names = git(root, "ls-files", "-z").decode().split("\0")
        for name in filter(None, names):
            path = root / name
            if path.is_file():
                check("working-tree", name, path.read_bytes())
        return findings
    entries = git(root, "rev-list", "--objects", *refs, "--").decode().splitlines()
    process = subprocess.Popen(
        ["git", "-C", str(root), "cat-file", "--batch"], stdin=subprocess.PIPE, stdout=subprocess.PIPE
    )
    assert process.stdin is not None and process.stdout is not None
    try:
        for row in entries:
            oid, _, name = row.partition(" ")
            process.stdin.write((oid + "\n").encode())
            process.stdin.flush()
            header = process.stdout.readline().split()
            data = process.stdout.read(int(header[2]))
            process.stdout.read(1)
            if header[1] == b"blob":
                check(oid, name, data)
            elif header[1] in {b"commit", b"tag"}:
                # Names/messages can also contain contact data; timestamps are not phone numbers.
                message = data.partition(b"\n\n")[2]
                check(oid, "", message)
                for identity in re.findall(rb"^(?:author|committer|tagger) (.*?) <[^<>]+>", data, re.M):
                    check(oid, "", identity)
    finally:
        process.stdin.close()
        process.stdout.close()
        process.wait(timeout=30)
    # Check every advertised tip path even when a blob has multiple path aliases.
    for ref in refs:
        for name in git(root, "ls-tree", "-r", "--name-only", ref).decode().splitlines():
            if private_path(name):
                findings.append({"path": name, "category": "private-artifact-path"})
    return findings


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, default=Path(__file__).resolve().parents[1])
    parser.add_argument("--refs", nargs="+", default=["HEAD"])
    parser.add_argument("--tags", action="store_true")
    parser.add_argument("--staged", action="store_true")
    parser.add_argument("--working-tree", action="store_true")
    parser.add_argument("--check-identities", action="store_true")
    parser.add_argument("--pre-push", action="store_true")
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()
    refs = args.refs
    if args.pre_push:
        refs = [
            parts[1]
            for line in sys.stdin
            for parts in [line.split()]
            if len(parts) == 4 and set(parts[1]) != {"0"}
        ]
        if not refs:
            return 0
    if args.tags and not args.staged and not args.working_tree:
        refs = list(
            dict.fromkeys(
                refs
                + git(args.root, "for-each-ref", "refs/tags", "--format=%(refname)").decode().splitlines()
            )
        )
    findings = []
    if args.check_identities:
        for role in ("AUTHOR", "COMMITTER"):
            identity = git(args.root, "var", "GIT_" + role + "_IDENT")
            email = re.search(rb"<([^<>]+)>", identity)
            if email is None or not safe_identity(email[1].decode(errors="replace")):
                findings.append({"role": role.lower(), "category": "non-noreply-identity"})
    if not args.staged and not args.working_tree:
        findings.extend(audit_metadata(args.root, refs, tags=args.tags))
    findings.extend(audit_content(args.root, refs, staged=args.staged, history=not args.working_tree))
    report = {"passed": not findings, "findings": findings}
    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(json.dumps(report, indent=2, ensure_ascii=True), encoding="utf-8")
    # ASCII JSON is safe on Windows consoles; matched values are never included.
    print(json.dumps(report, ensure_ascii=True))
    return 0 if report["passed"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
