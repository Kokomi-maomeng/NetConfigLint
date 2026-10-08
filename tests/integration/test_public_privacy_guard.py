"""Privacy gates must reject historical/merge/tag identities and never print detected values."""

from __future__ import annotations

import json
import os
import subprocess
from pathlib import Path

import pytest

from scripts import audit_release, privacy_guard

SAFE = "test-maintainer@users.noreply.github.com"
PRIVATE = "synthetic-person" + "@" + "contact.invalid"


def run(root: Path, *args: str, email: str = SAFE, committer: str = SAFE) -> bytes:
    env = dict(os.environ)
    env.update(
        GIT_AUTHOR_NAME="Synthetic contributor",
        GIT_COMMITTER_NAME="Synthetic contributor",
        GIT_AUTHOR_EMAIL=email,
        GIT_COMMITTER_EMAIL=committer,
        GIT_CONFIG_NOSYSTEM="1",
    )
    return subprocess.run(["git", "-C", str(root), *args], env=env, check=True, capture_output=True).stdout


def repository(root: Path) -> None:
    run(root, "init", "-b", "main")
    run(root, "config", "core.hooksPath", str(root / "absent-hooks"))
    (root / "file.txt").write_text("synthetic data\n", encoding="utf-8")
    (root / ".privacy-policy.json").write_text(
        json.dumps({"schema_version": 1, "reviewed_public_contact_sha256": []}), encoding="utf-8"
    )
    run(root, "add", ".")
    run(root, "commit", "-m", "Initial synthetic fixture")


def test_historical_private_author_never_passes_a_release_baseline(tmp_path: Path) -> None:
    repository(tmp_path)
    run(tmp_path, "commit", "--allow-empty", "-m", "Synthetic private author", email=PRIVATE)
    baseline = run(tmp_path, "rev-parse", "HEAD").decode().strip()
    run(tmp_path, "commit", "--allow-empty", "-m", "Later safe author")
    result = audit_release.audit_repository(tmp_path, baseline)
    assert not result["passed"]
    assert result["metadata_findings"][0]["role"] == "author"
    assert PRIVATE not in json.dumps(result)


def test_github_merge_committer_cannot_exempt_private_author(tmp_path: Path) -> None:
    repository(tmp_path)
    run(tmp_path, "checkout", "-b", "feature")
    run(tmp_path, "commit", "--allow-empty", "-m", "Synthetic feature")
    run(tmp_path, "checkout", "main")
    run(
        tmp_path,
        "merge",
        "--no-ff",
        "feature",
        "-m",
        "Merge pull request #4 from synthetic/feature",
        email=PRIVATE,
        committer="noreply@github.com",
    )
    result = privacy_guard.audit_metadata(tmp_path, ["HEAD"])
    assert result and result[0]["role"] == "author"
    assert PRIVATE not in json.dumps(result)


def test_private_tagger_is_checked_even_when_commits_are_safe(tmp_path: Path) -> None:
    repository(tmp_path)
    # tag uses the committer identity; override through the environment for this test.
    env = dict(os.environ, GIT_COMMITTER_NAME="Synthetic tagger", GIT_COMMITTER_EMAIL=PRIVATE)
    subprocess.run(
        ["git", "-C", str(tmp_path), "tag", "-a", "v1.0", "-m", "Synthetic tag"],
        env=env,
        check=True,
        capture_output=True,
    )
    findings = privacy_guard.audit_metadata(tmp_path, ["HEAD"], tags=True)
    assert findings and findings[0]["role"] == "tagger"
    assert PRIVATE not in json.dumps(findings)


def test_staged_private_contact_is_detected_without_echoing(tmp_path: Path) -> None:
    repository(tmp_path)
    contact = "synthetic-person" + "@" + "unlisted.demo"
    (tmp_path / "file.txt").write_text(contact, encoding="utf-8")
    run(tmp_path, "add", "file.txt")
    findings = privacy_guard.audit_content(tmp_path, ["HEAD"], staged=True, history=False)
    assert any(f["category"] == "unreviewed-contact-email" for f in findings)
    assert contact not in json.dumps(findings)


def test_deleting_private_current_content_does_not_clean_history(tmp_path: Path) -> None:
    repository(tmp_path)
    (tmp_path / "file.txt").write_text("synthetic-person" + "@" + "unlisted.demo", encoding="utf-8")
    run(tmp_path, "add", ".")
    run(tmp_path, "commit", "-m", "Synthetic contact fixture")
    (tmp_path / "file.txt").write_text("removed\n", encoding="utf-8")
    run(tmp_path, "add", ".")
    run(tmp_path, "commit", "-m", "Safe current contents")
    assert privacy_guard.audit_content(tmp_path, ["HEAD"], staged=False, history=True)


@pytest.mark.parametrize("encoding", ["utf-8", "utf-16-le"])
def test_tokens_and_phone_shapes_are_checked_without_values(encoding: str) -> None:
    token = "ghp_" + "A" * 36
    phone = "155" + "0" * 8
    assert "github-token" in privacy_guard.content_categories(token.encode(encoding), set())
    assert "phone-shaped-value" in privacy_guard.content_categories(phone.encode(encoding), set())


def test_changed_font_cannot_inherit_exact_binary_contact_exception() -> None:
    import hashlib

    font = b"synthetic font bytes: " + b"glyph" + b"@" + b"unlisted.demo"
    allowed = {"binary:" + hashlib.sha256(font).hexdigest()}
    assert privacy_guard.contact_categories(font, allowed) == []
    assert privacy_guard.contact_categories(font + b"changed", allowed) == ["unreviewed-contact-email"]
