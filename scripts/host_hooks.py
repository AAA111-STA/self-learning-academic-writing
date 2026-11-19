"""Adapt user-submission events and print optional host hook configurations."""

import argparse
import json
import os
import shlex
from pathlib import Path
import sys
from uuid import uuid4


HOSTS = ("codex", "claude", "qwen", "kimi", "zcode", "antigravity", "gemini", "deepseek", "generic")
CONTEXT_ONLY = {"gemini", "deepseek"}
EVENT = "UserPromptSubmit"


def submission(payload, host):
    if not isinstance(payload, dict):
        raise ValueError("Expected a JSON hook object.")
    if host == "antigravity":
        if not isinstance(payload.get("invocationNum"), int):
            raise ValueError("Expected an Antigravity PreInvocation event.")
        workspaces = payload.get("workspacePaths")
        prompt = payload.get("lastUserInput")
        if not isinstance(workspaces, list) or not workspaces or any(
            not isinstance(path, str) or not path for path in workspaces
        ) or not isinstance(prompt, str) or not prompt.strip():
            return None
        return {
            "prompt": prompt, "session": payload.get("conversationId"),
            "workspaces": workspaces, "turn": str(payload["invocationNum"]),
        }
    event = "BeforeAgent" if host == "gemini" else EVENT
    if payload.get("hook_event_name") != event:
        raise ValueError(f"Expected a {event} event for {host}.")

    # Qwen can fire this hook for model continuations and tool results as well.
    # Only the explicit submission field may authorize a workflow action.
    if host == "qwen":
        prompt = payload.get("submitted_prompt")
    elif host == "generic" and payload.get("role") != "user":
        return None
    else:
        prompt = payload.get("prompt")
    if not isinstance(prompt, str) or not prompt.strip():
        return None

    turn = next((
        payload[key] for key in ("turn_id", "prompt_id", "message_id")
        if isinstance(payload.get(key), str) and payload[key]
    ), None)
    return {
        "prompt": prompt,
        "session": payload.get("session_id"),
        "cwd": payload.get("cwd"),
        "turn": turn or uuid4().hex,
    }


def format_context(host, message):
    if host == "kimi":
        return message
    if host == "generic":
        return {"additional_context": message}
    if host == "gemini":
        return {"hookSpecificOutput": {"additionalContext": message}}
    if host == "antigravity":
        return {"injectSteps": [{"ephemeralMessage": message}]}
    return {"hookSpecificOutput": {"hookEventName": EVENT, "additionalContext": message}}


def shell_path(path, windows):
    text = path.as_posix()
    if not windows:
        return shlex.quote(text)
    if any(char in text for char in "\"%!\u0060$\r\n"):
        raise ValueError("Use a Windows path without quotes, percent signs, or shell expansions.")
    return f'"{text}"'


def format_config(host, workspace, windows=None):
    windows = os.name == "nt" if windows is None else windows
    workflow = Path(__file__).resolve().with_name("workflow.py")
    tool = "python" if windows else "python3"
    command = (
        f"{tool} {shell_path(workflow, windows)} prompt-hook"
        f" --host {host} --workspace {shell_path(workspace, windows)}"
    )
    if host == "generic":
        return command
    if host == "kimi":
        return f'[[hooks]]\nevent = "{EVENT}"\ncommand = {json.dumps(command, ensure_ascii=False)}\ntimeout = 10'
    handler = {"type": "command", "command": command, "timeout": 10}
    if host == "antigravity":
        return json.dumps({"academic-writing": {"PreInvocation": [handler]}}, ensure_ascii=False, indent=2)
    event = "BeforeAgent" if host == "gemini" else EVENT
    hooks = {event: [{"hooks": [handler]}]}
    if host == "zcode":
        hooks["enabled"] = True
    return json.dumps({"hooks": hooks}, ensure_ascii=False, indent=2)


def main():
    sys.stdout.reconfigure(encoding="utf-8")
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("host", choices=HOSTS)
    parser.add_argument("--workspace", type=Path, default=Path.cwd())
    args = parser.parse_args()
    try:
        print(format_config(args.host, args.workspace.resolve()))
    except ValueError as error:
        parser.error(str(error))


if __name__ == "__main__":
    main()
