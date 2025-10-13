# Coding Agents - A Comparison

I asked multiple AI coding agents to:

> Create a single-page web app at `index.html` that beautifully renders a GitHub user profile and activity comprehensively. Pick the ID in the URL `?id=...`, default to `?id=torvalds`.

Here are the results. 🔴 indicates failure.

| Tool              | Model                                | Quality | Cents | Seconds | Logs                                         |
| ----------------- | ------------------------------------ | ------: | ----: | ------: | -------------------------------------------- |
| [OpenCode][OC]    | [claude-sonnet-4.5][OC-CS45]         |       7 |  13.2 |      54 | [Logs](opencode/claude-sonnet-4.5/log)    |
| [OpenCode][OC]    | [gpt-5-codex][OC-GPT5]               |       6 |  14.9 |     105 | [Logs](opencode/gpt-5-codex/log.md)          |
| [Codex][CX]       | [gpt-5-codex][CX-GPT5] - medium      |       6 |  21.7 |     130 | [Logs](codex/gpt-5-codex-medium/log.md)      |
| [Claude Code][CC] | [claude-sonnet-4.5][CC-CS45]         |       5 |   9.3 |      66 | [Logs](claude-code/claude-sonnet-4.5/log.md) |
| [OpenCode][OC]    | [gemini-2.5-pro][OC-GEMINI25]        |       3 |  14.2 |      37 | [Logs](opencode/gemini-2.5-pro/log.md)       |
| [OpenCode][OC]    | [grok-4][OC-GROK4] (🔴 escaped HTML) |       1 |   8.4 |      65 | [Logs](opencode/grok-4/log.md)               |
| [OpenCode][OC]    | [glm-4.6][OC-GLM46] (🔴 no output)   |       0 |   1.8 |     143 | [Logs](opencode/glm-4.6/log.md)              |

[CC]: https://www.claude.com/product/claude-code
[CX]: https://openai.com/codex/
[OC]: https://opencode.ai/
[CC-CS45]: claude-code/claude-sonnet-4.5/index.html
[CX-GPT5]: codex/gpt-5-codex-medium/index.html
[OC-CS45]: opencode/claude-sonnet-4.5/index.html
[OC-GPT5]: opencode/gpt-5-codex/index.html
[OC-GLM46]: opencode/glm-4.6/index.html
[OC-GROK4]: opencode/grok-4/index.html
[OC-GEMINI25]: opencode/gemini-2.5-pro/index.html

My takeaways:

- Quality is the key difference. Some do well. Some models fail completely.
- Cost variation among the successful models is not too high. About 2X.
- Time variation is not too high either. About 2X.

# Setup

```bash
export ROOT=$(pwd)
export TASK='Create a single-page web app at `index.html` that beautifully renders a GitHub user profile and activity comprehensively. Pick the ID in the URL `?id=...`, default to `?id=torvalds`.'

# Claude Code - Claude 4.5 Sonnet
export DIR=$ROOT/claude-code/claude-sonnet-4.5
mkdir -p $DIR && cd $DIR
npx -y @anthropic-ai/claude-code \
  --model claude-sonnet-4-5-20250929 \
  --permission-mode acceptEdits \
  --print \
  "$TASK"

# Codex - GPT 5 Codex Medium
export DIR=$ROOT/codex/gpt-5-codex-medium
mkdir -p $DIR && cd $DIR
npx -y @openai/codex exec \
  --model gpt-5-codex \
  --config 'model_reasoning_effort="medium"' \
  --full-auto "$TASK"

# OpenCode - GLM 4.6
export DIR=$ROOT/opencode/glm-4.6
mkdir -p $DIR && cd $DIR
npx -y opencode-ai run \
  --model openrouter/z-ai/glm-4.6 \
  "$TASK"

# OpenCode - GPT 5 Codex
export DIR=$ROOT/opencode/gpt-5-codex
mkdir -p $DIR && cd $DIR
npx -y opencode-ai run \
  --model openrouter/openai/gpt-5-codex \
  "$TASK"

# OpenCode - Claude 4.5 Sonnet
export DIR=$ROOT/opencode/claude-sonnet-4.5
mkdir -p $DIR && cd $DIR
npx -y opencode-ai run \
  --model openrouter/anthropic/claude-sonnet-4.5 \
  "$TASK"

# OpenCode - Grok 4
export DIR=$ROOT/opencode/grok-4
mkdir -p $DIR && cd $DIR
npx -y opencode-ai run \
  --model openrouter/x-ai/grok-4 \
  "$TASK"

export DIR=$ROOT/opencode/gemini-2.5-pro
mkdir -p $DIR && cd $DIR
npx -y opencode-ai run \
  --model openrouter/google/gemini-2.5-pro \
  "$TASK"
```
