---
name: codex-cli
description: Delegate code review, code implementation, or image generation to the OpenAI Codex CLI for a second opinion. Image generation works through ChatGPT login alone — no OPENAI_API_KEY required.
when_to_use: User types /codex-cli, or asks to "use codex" / "ask codex" / "have codex" do X, or wants a second-opinion code review, or requests an image that Codex can produce.
allowed-tools: Bash(codex *) Bash(cp *) Bash(ls *) Bash(Get-ChildItem *) Bash(Copy-Item *) Read
---

Wrap the local `codex` CLI (`codex --version` ≥ 0.128.0) so Claude Code can hand off three kinds of work without leaving the conversation:

- **review** — second-opinion code review on a diff
- **impl** — non-interactive coding task in a sandbox
- **image** — image generation via Codex's built-in `image_gen.imagegen` tool (no API key, ChatGPT login is enough)

## Verify once per session

```bash
codex --version          # codex-cli ≥ 0.128.0
codex login status       # must say "Logged in"
```

If not logged in, tell the user to run `! codex login` from the prompt. Do not log in on their behalf.

## Pick the mode

Parse `$ARGUMENTS`. The first token selects the mode (`review | impl | image`); everything after it is the prompt or flags. If the user invoked `/codex-cli` with no subcommand, infer:

- mentions "review", "diff", "PR", "second opinion" → review
- mentions "image", "picture", "render", "draw", "그려" → image
- otherwise → impl

State the mode you picked in your reply so the user can correct you.

## Mode: review

```bash
codex review --uncommitted              # staged + unstaged + untracked
codex review --base main                # PR-style against base branch
codex review --commit <sha>             # one specific commit
"Focus on concurrency. Skip nits." | codex review --uncommitted -
```

After it returns, paraphrase the findings — do NOT dump raw output. Group by **CRITICAL / HIGH / MEDIUM / LOW** per `~/.claude/rules/common/code-review.md`. Cite `file:line` per finding.

Codex's review is a second opinion, not ground truth. If it contradicts something already verified in this session, flag the conflict to the user instead of silently siding with Codex.

## Mode: impl

```bash
# One-shot non-interactive (preferred)
codex exec "<prompt>" \
  -s workspace-write \
  -C "<absolute path>" \
  --output-last-message codex-out.txt

# Read-only research / planning
codex exec "<prompt>" -s read-only -C "<path>"

# Long prompt via stdin
cat prompt.md | codex exec -s workspace-write -C "<path>" -

# Continue most recent session
codex exec resume --last "<follow-up>"
```

Sandbox policy:

- Default `workspace-write` (network on, writes inside `-C` only).
- Use `read-only` when the user wants analysis or a written plan with no edits.
- Always pass `-C` with an absolute path. Without it, Codex uses its own cwd and refuses most prompts.
- Do NOT pass `-s danger-full-access` or `--dangerously-bypass-approvals-and-sandbox` without explicit per-run user approval. The first turns off the sandbox; the second turns off both sandbox and approval gates.

After Codex finishes, read `codex-out.txt` (or the diff) and summarize what changed. Do not rerun `codex apply` without asking.

## Mode: image

Codex has a built-in image tool (`image_gen.imagegen`). It activates automatically when `codex features list` shows `image_generation = stable, true`. Authentication uses your `codex login` — ChatGPT login is enough; no `OPENAI_API_KEY` needed.

Invoke:

```bash
codex exec --skip-git-repo-check \
  -s workspace-write \
  -C "<absolute path to output dir>" \
  "Generate an image of <prompt>, 1024x1024. Save the result as <name>.png in the current working directory."
```

**Critical prompt rule.** Do NOT tell Codex to "use the OpenAI API", "use curl", "use python", or "use openai CLI". Those instructions force a shell-out path that needs `OPENAI_API_KEY`. Just say *generate and save* — Codex picks its built-in tool.

**Where the file lands.** Codex writes the PNG to `~/.codex/generated_images/<session_id>/ig_<hash>.png`, then tries to copy it to the workspace via shell. On Windows codex-cli 0.128.0 the copy step often fails (`CreateProcessAsUserW failed: 5`) even though generation succeeded. Do NOT escalate to `-s danger-full-access` for this — copy the file yourself:

```powershell
# PowerShell
$src = Get-ChildItem "$env:USERPROFILE\.codex\generated_images" -Recurse -Filter "ig_*.png" |
  Sort-Object LastWriteTime -Descending | Select-Object -First 1
Copy-Item $src.FullName "<output path>\<name>.png"
```

```bash
# bash / zsh
src=$(ls -t ~/.codex/generated_images/*/ig_*.png 2>/dev/null | head -1)
cp "$src" "<output path>/<name>.png"
```

Show the user the absolute path. Do not embed PNG bytes in chat.

**Supported sizes:** `1024x1024` (square), `1536x1024` (landscape), `1024x1536` (portrait). For unsupported sizes, list the valid options instead of failing silently.

## Safety

- Do not send code or prompts the user marked confidential to Codex without confirming.
- Do not generate images depicting real, identifiable people without consent or that violate OpenAI usage policy. Ask the user on borderline prompts.
- Do not pass `--dangerously-bypass-approvals-and-sandbox` — that flag is for externally-sandboxed CI only.
- Do not pass `-s danger-full-access` without explicit per-run user approval.

## Output discipline

- Don't stream Codex's stdout unless the user asked. Summarize.
- Save long sessions to `codex-out.txt` and quote only what's relevant.
- Always state the mode you ran and the exact command, so the user can rerun it.
