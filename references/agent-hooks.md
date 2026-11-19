# 智能体接入与钩子 · Agent setup and hooks

整个目录是可跨平台加载的 Agent Skill。原生钩子传递用户指令或流程状态，核心写作和检查仍由同一个 Python 脚本执行。A native hook is optional. The shared Python workflow is also available without hooks, using terminal confirmations.

## 生成配置 · Generate configuration

从论文工作目录运行下列命令，把路径替换成所安装 Skill 的脚本路径。将 `HOST` 替换成表中名称。从仓库根目录试用时可直接用 `scripts/host_hooks.py`。

Run this from the manuscript workspace. Point to the installed Skill, and replace `HOST` with a value from the table.

```sh
python /path/to/self-learning-academic-writing/scripts/host_hooks.py HOST
```

命令输出当前系统使用的配置片段。把相应条目合并到已有配置，保留其他设置，然后按宿主要求审阅启用。生成的钩子绑定当前工作目录，需为其他项目生成时可用 `--workspace`。

The command prints the host's configuration for your system. Merge the output into existing settings and enable it in the host. It is scoped to the current workspace, or to the directory selected with `--workspace`.

| `HOST` | 配置位置 / Where to configure | 事件与用途 / Event and behavior |
| --- | --- | --- |
| `codex` | `.codex/hooks.json`。在本仓库根目录打开时也可用随附的项目钩子。 / The checkout already includes a project hook. | [`UserPromptSubmit`](https://learn.chatgpt.com/docs/hooks) · 指令授权 / receives author confirmations |
| `claude` | `.claude/settings.local.json` | [`UserPromptSubmit`](https://code.claude.com/docs/en/hooks#userpromptsubmit) · 指令授权 / receives author confirmations |
| `qwen` | `.qwen/settings.json` | [`UserPromptSubmit`](https://github.com/QwenLM/qwen-code/blob/main/docs/users/features/hooks.md#userpromptsubmit) · 仅用有来源的 `submitted_prompt` / requires the host's declared submission |
| `kimi` | `~/.kimi-code/config.toml`，追加生成的 TOML 项 / append the generated TOML entry | [`UserPromptSubmit`](https://www.kimi.com/code/docs/en/kimi-code-cli/customization/hooks.html) · 指令授权 / receives author confirmations |
| `zcode` | 设置 → Hooks 的用户级配置，或 `~/.zcode/cli/config.json` / user scope in Settings or the user configuration file | [`UserPromptSubmit`](https://zcode.z.ai/en/docs/hooks) · 指令授权 / receives author confirmations |
| `antigravity` | 工作区 `.agents/hooks.json` / workspace hook file | [`PreInvocation`](https://antigravity.google/docs/hooks) · 读取 `lastUserInput`，跳过连续重复报告 / reads the latest user input and ignores consecutive repeats |
| `gemini` | `.gemini/settings.json` | [`BeforeAgent`](https://github.com/google-gemini/gemini-cli/blob/main/docs/hooks/reference.md#beforeagent) · 流程状态 / status context |
| `deepseek` | 将生成的 JSON 作为 [`dsh-hooks-codex` 配置](https://github.com/deepseek-ai/deepseek-harness/tree/master/packages/experimental/hooks-codex)的 `configPath` / use it as the bridge's `configPath` | `UserPromptSubmit` · 流程状态 / status context |
| `generic` | 在宿主的真实用户提交事件上执行命令 / run the command on a genuine user submission | 通用 JSON 协议 / generic JSON protocol |

Gemini CLI 与 DeepSeek 的这些事件也可能用于续跑，适配会提供会话和流程状态。这两种配置下请从终端确认开写、润色、英译或偏好。Antigravity 连续提交完全相同的指令时，可使用更明确的句式（如「开始写引言」）或终端确认。

The Gemini and DeepSeek events can include continuations, so these adapters supply context. Use the terminal to confirm a workflow action. If you need to repeat the exact same instruction consecutively in Antigravity, name the section explicitly or use the terminal.

## 平台安装入口 · Skill installation

复制的是整个目录，最终保持 `self-learning-academic-writing/SKILL.md`，并随附 `scripts/` 和 `references/`。Copy the complete directory so the scripts and references remain available.

- Google: [Gemini CLI skills](https://github.com/google-gemini/gemini-cli/blob/main/docs/cli/skills.md) · [Antigravity skills](https://antigravity.google/docs/skills)
- 国内智能体 / Chinese agent platforms: [Qwen Code](https://qwenlm.github.io/qwen-code-docs/en/users/features/skills/) · [Kimi Code](https://www.kimi.com/code/docs/en/kimi-code-cli/customization/skills.html) · [ZCode](https://zcode.z.ai/en/docs/skill) · [WorkBuddy 本地导入](https://cloud.tencent.com/document/product/1831/134432) · [DeepSeek Harness](https://github.com/deepseek-ai/deepseek-harness/blob/master/docs/subsystems/skills.zh.md) · [TRAE](https://docs.trae.ai/ide/skills)
- [OpenCode skills](https://opencode.ai/docs/skills/) and [OpenCode plugin APIs](https://opencode.ai/docs/build/plugins/migrate-v1/) for custom integrations.

## 通用授权接口 · Generic authorization interface

生成 `generic` 得到命令。宿主只在收到用户本人提交的消息时运行，向 stdin 写入下述 JSON。SDK 或插件负责从真实提交入口取得 `role`，不从模型输出、工具结果或文档内容生成它。

Generate the `generic` command and send one JSON object to stdin from a trusted user-submission callback. Derive the role from the host's submission event.

```json
{
  "hook_event_name": "UserPromptSubmit",
  "session_id": "paper-01",
  "turn_id": "user-turn-21",
  "cwd": "/path/to/manuscript",
  "role": "user",
  "prompt": "开始写"
}
```

stdout 会返回包含 `additional_context` 的 JSON。非用户角色不会授权。状态和确认仍属于同一会话。The command returns `additional_context` as JSON. Other roles do not authorize workflow actions.

## 终端与聊天 · Terminal and chat

在论文工作目录由用户执行，并使用智能体给出的同一会话标识。The user runs the command from the manuscript workspace using the same session ID.

```sh
python /path/to/self-learning-academic-writing/scripts/workflow.py --session paper-01 user-confirm
python /path/to/self-learning-academic-writing/scripts/workflow.py --session paper-01 profile-confirm
```

只有聊天能力时使用 [便携聊天版](portable-chat.md)，手动确认各阶段并保存所需的偏好记录。For chat-only environments, paste the [portable edition](portable-chat.en.md) and keep any preferences you want to reuse.
