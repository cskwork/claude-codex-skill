---
name: codex-cli
description: Drive the OpenAI Codex CLI for three jobs — code review, code implementation, and image generation. Trigger when the user types /codex, /codex-cli, /codex-review, /codex-impl, or /codex-image, or asks to "use codex" / "ask codex" / "have codex" do something.
trigger: /codex, /codex-cli, /codex-review, /codex-impl, /codex-image
---

# /codex-cli

Wrap the local `codex` CLI (an OpenAI coding agent, `codex --version` ≥ 0.128.0) for three jobs you can hand off without leaving Claude Code.

| Mode | Backing tool | When to use |
|---|---|---|
| **review** | `codex review` | Second-opinion code review on uncommitted changes, a base branch, or a specific commit |
| **impl** | `codex exec` | Hand off a coding task to Codex non-interactively |
| **image** | `codex exec` (built-in `image_gen.imagegen` tool) | Generate a raster image — verified working with ChatGPT login alone, no API key needed |

## Prerequisites

```powershell
codex --version          # codex-cli ≥ 0.128.0
codex login status       # "Logged in using ChatGPT" (also works with API key login)
```

If not logged in, ask the user to run `! codex login` from the prompt — do not try to log them in.

## Argument parsing

Slash form: `/codex <subcommand> <args...>` where subcommand is `review | impl | image` (case-insensitive). If absent, infer:
- "review", "diff", "PR", "second opinion" → review
- "image", "picture", "render", "draw", "그려" → image
- otherwise → impl

## Mode 1 — review

```powershell
codex review --uncommitted                # staged + unstaged + untracked
codex review --base main                  # PR-style diff against base branch
codex review --commit <sha>               # one specific commit
"Focus on concurrency. Skip nits." | codex review --uncommitted -   # custom instructions via stdin
```

Paraphrase the findings into Claude's reply — do NOT dump raw output. Group by CRITICAL / HIGH / MEDIUM / LOW per `~/.claude/rules/common/code-review.md`. Cite `file:line` per finding.

Codex's review is a second opinion, not ground truth. If it contradicts something you already verified, flag the conflict instead of silently siding with Codex.

## Mode 2 — impl

```powershell
# One-shot (preferred)
codex exec "<prompt>" `
  -s workspace-write `
  -C "<absolute path>" `
  --output-last-message codex-out.txt

# Read-only research / planning
codex exec "<prompt>" -s read-only -C "<path>"

# Long prompt via stdin
Get-Content prompt.md | codex exec -s workspace-write -C "<path>" -

# Continue last session
codex exec resume --last "<follow-up>"
```

Sandbox rules:
- Default `workspace-write`. Edits inside `-C`, network on, writes outside repo blocked.
- Use `read-only` for analysis or planning where Codex shouldn't touch files.
- Never pass `--dangerously-bypass-approvals-and-sandbox`.
- Never pass `-s danger-full-access` without explicit per-run user approval.
- Always pass `-C` with an absolute path. Without it Codex uses its own cwd (`C:\Users\a` on this machine) and refuses most prompts.

After it finishes, read `codex-out.txt` (or the diff) and summarize what changed. Don't rerun `codex apply` without asking.

## Mode 3 — image (verified working)

Codex has a **built-in image generation tool** (`image_gen.imagegen`) exposed automatically when `codex features list` shows `image_generation = stable, true`. Authentication uses your `codex login` (ChatGPT login is enough — no `OPENAI_API_KEY` required).

### How to invoke

```powershell
codex exec --skip-git-repo-check `
  -s workspace-write `
  -C "<absolute path to output dir>" `
  "Generate an image of <prompt>, 1024x1024. Save the result as <name>.png in the current working directory."
```

**Critical prompt rule:** Do NOT tell Codex to "use the OpenAI API", "use curl", "use python", or "use openai CLI". Those instructions force it to shell out to a path that needs `OPENAI_API_KEY`. Instead, just say *generate an image and save it* — Codex will pick its built-in tool on its own.

### Where the file actually lands

Codex's image tool writes to `~/.codex/generated_images/<session_id>/ig_<hash>.png` first, then tries to copy/move it to the workspace via shell. On Windows codex-cli 0.128.0 the copy step often fails with `CreateProcessAsUserW failed: 5` (the `workspace-write` sandbox blocking PowerShell), even though generation succeeded.

If you see that error, do NOT escalate to `-s danger-full-access` — generation already worked. Just copy the file yourself:

```powershell
# Find the most recent generation and copy to the intended path
$src = Get-ChildItem "$env:USERPROFILE\.codex\generated_images" -Recurse -Filter "ig_*.png" | Sort-Object LastWriteTime -Descending | Select-Object -First 1
Copy-Item $src.FullName "<output path>\<name>.png"
```

Or POSIX-shell equivalent:

```bash
src=$(ls -t ~/.codex/generated_images/*/ig_*.png 2>/dev/null | head -1)
cp "$src" "<output path>/<name>.png"
```

Then show the user the absolute path. Do not embed the PNG bytes in chat.

### Size guidance

`1024x1024` (square), `1536x1024` (landscape), `1024x1536` (portrait). Pick a supported size; if the user asks for an unsupported one, list the choices instead of failing silently.

### Refusals

- No images depicting real, identifiable people without consent.
- No content that violates OpenAI usage policy.
- Borderline prompts: ask before running.

## Output discipline

- Don't stream Codex's stdout unless the user asked to see it. Summarize instead.
- Save long sessions to `codex-out.txt` and quote only what's relevant.
- Always state which mode ran and the exact command, so the user can rerun.

## Refusals

- Don't send confidential code/prompts to Codex without confirmation.
- Don't pass `--dangerously-bypass-approvals-and-sandbox` — that flag is for externally-sandboxed CI only.
- Don't pass `-s danger-full-access` without explicit user approval per run.
