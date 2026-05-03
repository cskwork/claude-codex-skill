#!/usr/bin/env python3
"""
Reproducible test runner for claude-codex-skill.

Runs all checks and writes a fresh RESULTS.md as a trust record.

Usage:
  python tests/run.py             # run from repo root
  python tests/run.py --skip-image  # skip the codex image-gen test (no codex login required)

Exit code: 0 on all-pass, 1 on any failure.
"""

from __future__ import annotations

import argparse
import datetime as dt
import hashlib
import os
import platform
import re
import shutil
import subprocess
import sys
import time
import urllib.request
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
SKILL_PATH = REPO_ROOT / "SKILL.md"
RESULTS_PATH = REPO_ROOT / "tests" / "RESULTS.md"

OFFICIAL_FRONTMATTER_FIELDS = {
    "name", "description", "when_to_use", "argument-hint", "arguments",
    "disable-model-invocation", "user-invocable", "allowed-tools", "model",
    "effort", "context", "agent", "hooks", "paths", "shell",
}

RAW_BASE = "https://raw.githubusercontent.com/cskwork/claude-codex-skill/main"
URLS_TO_CHECK = [
    f"{RAW_BASE}/SKILL.md",
    f"{RAW_BASE}/install.ps1",
    f"{RAW_BASE}/install.sh",
    f"{RAW_BASE}/README.md",
    f"{RAW_BASE}/LICENSE",
]


def run_test(name: str, fn) -> tuple[bool, str]:
    print(f"  [.] {name} ... ", end="", flush=True)
    try:
        detail = fn() or ""
        print("PASS")
        return True, detail
    except AssertionError as e:
        print(f"FAIL\n      {e}")
        return False, f"FAIL: {e}"
    except Exception as e:
        print(f"ERROR ({type(e).__name__}: {e})")
        return False, f"ERROR: {type(e).__name__}: {e}"


def parse_frontmatter(text: str) -> dict:
    parts = text.split("---", 2)
    assert len(parts) >= 3, "SKILL.md missing --- delimiters"
    fm: dict[str, str] = {}
    for line in parts[1].strip().splitlines():
        if ":" not in line:
            continue
        k, _, v = line.partition(":")
        fm[k.strip()] = v.strip()
    return fm


def test_skill_exists() -> str:
    assert SKILL_PATH.exists(), f"{SKILL_PATH} not found"
    return f"size={SKILL_PATH.stat().st_size} bytes"


def test_frontmatter_required_fields() -> str:
    fm = parse_frontmatter(SKILL_PATH.read_text(encoding="utf-8"))
    assert "name" in fm, "missing required field: name"
    assert "description" in fm, "missing required field: description"
    assert fm["name"] == "codex-cli", f"name must be 'codex-cli', got {fm['name']!r}"
    return f"name={fm['name']!r}, description present ({len(fm['description'])} chars)"


def test_frontmatter_no_unknown_fields() -> str:
    fm = parse_frontmatter(SKILL_PATH.read_text(encoding="utf-8"))
    unknown = [k for k in fm if k not in OFFICIAL_FRONTMATTER_FIELDS]
    assert not unknown, (
        f"unknown frontmatter fields: {unknown}. "
        f"Official fields: {sorted(OFFICIAL_FRONTMATTER_FIELDS)}"
    )
    return f"all {len(fm)} fields are in the official spec"


def test_frontmatter_no_legacy_trigger() -> str:
    fm = parse_frontmatter(SKILL_PATH.read_text(encoding="utf-8"))
    assert "trigger" not in fm, (
        "found 'trigger:' field — this is NOT in the official Claude Code "
        "skill frontmatter spec; use 'when_to_use:' instead"
    )
    return "no legacy trigger: field"


def test_when_to_use_present() -> str:
    fm = parse_frontmatter(SKILL_PATH.read_text(encoding="utf-8"))
    assert "when_to_use" in fm, "when_to_use is the recommended replacement for trigger phrases"
    assert len(fm["when_to_use"]) > 20, "when_to_use too short to be useful"
    return f"{len(fm['when_to_use'])} chars"


def test_allowed_tools_present() -> str:
    fm = parse_frontmatter(SKILL_PATH.read_text(encoding="utf-8"))
    assert "allowed-tools" in fm, "allowed-tools missing — codex calls will require per-use approval"
    assert "codex" in fm["allowed-tools"], "allowed-tools should grant Bash(codex *)"
    return fm["allowed-tools"][:80]


def test_skill_length() -> str:
    lines = SKILL_PATH.read_text(encoding="utf-8").splitlines()
    assert len(lines) < 500, f"SKILL.md is {len(lines)} lines; official guidance recommends <500"
    return f"{len(lines)} lines (limit 500)"


def test_no_fake_slash_aliases() -> str:
    """README and SKILL.md must not promise /codex, /codex-review, etc.
    The skill directory is codex-cli/, so only /codex-cli exists."""
    fakes = [r"`/codex `", r"`/codex-review`", r"`/codex-impl`", r"`/codex-image`", r"`/codex`(?!-)"]
    for path in (SKILL_PATH, REPO_ROOT / "README.md"):
        text = path.read_text(encoding="utf-8")
        for pat in fakes:
            m = re.search(pat, text)
            assert not m, f"{path.name} promises non-existent slash command: {m.group()}"
    return "no fictitious /codex* aliases"


def test_install_urls_resolve() -> str:
    statuses: list[str] = []
    for url in URLS_TO_CHECK:
        req = urllib.request.Request(url, method="HEAD")
        with urllib.request.urlopen(req, timeout=15) as resp:
            assert resp.status == 200, f"{url} returned {resp.status}"
            statuses.append(f"{resp.status} {url.rsplit('/', 1)[1]}")
    return "; ".join(statuses)


def codex_bin() -> str:
    """Resolve codex absolute path. On Windows shutil.which finds .cmd shims;
    bare 'codex' in subprocess.run does not."""
    path = shutil.which("codex")
    if not path:
        raise AssertionError("codex CLI not found in PATH")
    return path


def test_codex_installed() -> str:
    bin_ = codex_bin()
    out = subprocess.run([bin_, "--version"], capture_output=True, text=True, timeout=10)
    assert out.returncode == 0, f"codex --version exit {out.returncode}: {out.stderr.strip()}"
    return out.stdout.strip()


def test_codex_logged_in() -> str:
    bin_ = codex_bin()
    out = subprocess.run([bin_, "login", "status"], capture_output=True, text=True, timeout=10)
    combined = (out.stdout or "") + (out.stderr or "")
    assert "Logged in" in combined, f"codex not logged in: {combined.strip()}"
    return combined.strip().splitlines()[0] if combined.strip() else ""


def test_codex_image_gen_e2e(out_dir: Path) -> str:
    """End-to-end: ask codex to generate an image; if Windows sandbox blocks
    the workspace copy, apply the documented workaround and verify the file."""
    out_dir.mkdir(parents=True, exist_ok=True)
    target = out_dir / "test-image.png"
    if target.exists():
        target.unlink()

    pre_count = len(list(Path.home().glob(".codex/generated_images/**/ig_*.png")))
    t0 = time.time()
    proc = subprocess.run(
        [
            codex_bin(), "exec", "--skip-git-repo-check",
            "-s", "workspace-write",
            "-C", str(out_dir),
            "Generate an image of a tiny green dragon, 1024x1024. "
            "Save the result as test-image.png in the current working directory.",
        ],
        capture_output=True, text=True, timeout=240,
    )
    elapsed = time.time() - t0
    post = sorted(
        Path.home().glob(".codex/generated_images/**/ig_*.png"),
        key=lambda p: p.stat().st_mtime, reverse=True,
    )
    new_files = post[: max(0, len(post) - pre_count)]
    if not target.exists():
        # Apply the documented Windows-sandbox workaround.
        assert post, (
            "codex produced no image in ~/.codex/generated_images/; "
            f"stderr: {proc.stderr[-400:].strip()}"
        )
        shutil.copy2(post[0], target)
    assert target.exists(), "test-image.png missing after copy workaround"
    sha = hashlib.sha256(target.read_bytes()).hexdigest()[:16]
    return (
        f"{target.stat().st_size} bytes, sha256={sha}..., "
        f"{elapsed:.1f}s, generated_via='{post[0].parent.name}' (newly added: {len(new_files)})"
    )


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--skip-image", action="store_true", help="skip the codex image-gen test")
    args = parser.parse_args()

    print(f"claude-codex-skill verification — {dt.datetime.now().isoformat(timespec='seconds')}")
    print(f"  python={sys.version.split()[0]}  os={platform.system()} {platform.release()}")
    print()

    image_out = REPO_ROOT / "tests" / "fixtures" / "verify-out"
    tests = [
        ("SKILL.md exists", test_skill_exists),
        ("frontmatter has required fields", test_frontmatter_required_fields),
        ("frontmatter uses only official fields", test_frontmatter_no_unknown_fields),
        ("frontmatter has no legacy `trigger:` field", test_frontmatter_no_legacy_trigger),
        ("frontmatter declares when_to_use", test_when_to_use_present),
        ("frontmatter declares allowed-tools", test_allowed_tools_present),
        ("SKILL.md length under 500 lines", test_skill_length),
        ("no fictitious slash aliases", test_no_fake_slash_aliases),
        ("install/raw URLs return HTTP 200", test_install_urls_resolve),
        ("codex CLI installed", test_codex_installed),
        ("codex CLI logged in", test_codex_logged_in),
    ]
    if not args.skip_image:
        tests.append(("end-to-end image generation", lambda: test_codex_image_gen_e2e(image_out)))

    results: list[tuple[str, bool, str]] = []
    for name, fn in tests:
        ok, detail = run_test(name, fn)
        results.append((name, ok, detail))

    n_pass = sum(1 for _, ok, _ in results if ok)
    n_fail = len(results) - n_pass
    print()
    print(f"{n_pass}/{len(results)} passed")

    write_results_md(results, args)
    return 0 if n_fail == 0 else 1


def write_results_md(results: list[tuple[str, bool, str]], args: argparse.Namespace) -> None:
    n_pass = sum(1 for _, ok, _ in results if ok)
    total = len(results)
    skipped: list[str] = []
    if args.skip_image:
        skipped.append("end-to-end image generation (--skip-image)")

    lines: list[str] = []
    lines.append("# Test Results — Trust Record\n")
    lines.append(
        "_Auto-generated by `python tests/run.py`. Re-run anytime to regenerate. "
        "Commit this file alongside skill changes so reviewers can see what was verified at the time._\n"
    )
    lines.append(f"## Last run\n")
    lines.append(f"- **Timestamp:** {dt.datetime.now().isoformat(timespec='seconds')}")
    lines.append(f"- **Platform:** {platform.system()} {platform.release()} (python {sys.version.split()[0]})")
    lines.append(f"- **Result:** {n_pass}/{total} passed")
    if skipped:
        lines.append(f"- **Skipped:** " + "; ".join(skipped))
    lines.append("")
    try:
        codex_path = shutil.which("codex")
        if codex_path:
            codex_ver = subprocess.run([codex_path, "--version"], capture_output=True, text=True, timeout=5).stdout.strip()
            lines.append(f"- **codex CLI:** {codex_ver}")
        else:
            lines.append("- **codex CLI:** not found on PATH")
    except Exception:
        lines.append("- **codex CLI:** not available")
    lines.append("")
    lines.append("## Checks\n")
    lines.append("| # | Check | Result | Detail |")
    lines.append("|---|---|---|---|")
    for i, (name, ok, detail) in enumerate(results, 1):
        marker = "PASS" if ok else "FAIL"
        safe = detail.replace("|", "\\|").replace("\n", " ")
        lines.append(f"| {i} | {name} | **{marker}** | {safe} |")
    lines.append("")
    lines.append("## Reproducing\n")
    lines.append("```bash")
    lines.append("# Full run (requires codex login + ChatGPT)")
    lines.append("python tests/run.py")
    lines.append("")
    lines.append("# Skip the image-gen E2E (still validates metadata, URLs, codex install)")
    lines.append("python tests/run.py --skip-image")
    lines.append("```")
    lines.append("")
    RESULTS_PATH.write_text("\n".join(lines), encoding="utf-8")
    print(f"  → wrote {RESULTS_PATH.relative_to(REPO_ROOT)}")


if __name__ == "__main__":
    sys.exit(main())
