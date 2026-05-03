# Tests — trust record

Reproducible verification for `claude-codex-skill`. Every change to `SKILL.md`, `README.md`, or install scripts should run these checks and update [`RESULTS.md`](RESULTS.md) so reviewers can see what was actually verified.

## What is verified

| # | Check | Why it matters |
|---|---|---|
| 1 | `SKILL.md` exists | Skill cannot load without this file |
| 2 | Frontmatter has `name` + `description` | Required by Claude Code skill loader |
| 3 | Frontmatter uses only official fields | Unknown fields are silently ignored — they look like they work but don't |
| 4 | No legacy `trigger:` field | `trigger:` is not in the official spec; `when_to_use:` is the replacement |
| 5 | `when_to_use:` declared | Lets Claude auto-load the skill on natural-language phrasings |
| 6 | `allowed-tools:` declared | Pre-approves codex calls so users aren't prompted on every invocation |
| 7 | `SKILL.md` under 500 lines | Anthropic's recommendation; longer skills should split into bundled files |
| 8 | No fictitious slash aliases | Slash commands are derived from the directory name (`codex-cli/` → `/codex-cli`); only that one exists |
| 9 | Install / raw URLs return HTTP 200 | One-liner installers must work for new users |
| 10 | `codex` CLI installed | Skill is useless without it |
| 11 | `codex` CLI logged in | Required for image generation and most commands |
| 12 | End-to-end image generation | Proves the whole pipeline still works — codex generates a PNG without `OPENAI_API_KEY`, and the documented Windows copy-workaround retrieves it |

## Run

```bash
# Full run (requires `codex login` with ChatGPT)
python tests/run.py

# Skip the image-gen E2E (still covers metadata, URLs, codex install)
python tests/run.py --skip-image
```

The runner regenerates `tests/RESULTS.md` on every run.

## Adding a new check

Add a function to `tests/run.py` that raises `AssertionError` on failure. Append it to the `tests` list in `main()`. That's it.

## Why a "trust record"

Anyone considering installing this skill should be able to see, at a glance, what was verified, when, and on what platform. The committed `RESULTS.md` answers that without requiring them to run the suite themselves first. When the skill changes, the record changes — drift becomes visible in git diff.
