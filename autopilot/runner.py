"""Run one headless `claude -p` session with hard caps and parse its stream-json result.

The exit code and the model's text are recorded, never trusted: exit 0 with subtype
"success" happens on do-nothing runs (verified on 2.1.286).
"""
from __future__ import annotations

import json
import os
import subprocess
import time
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any

from .procs import kill_group

# Credentials a session must not see when the run is subscription-only.
KEY_VARS = ("ANTHROPIC_API_KEY", "ANTHROPIC_AUTH_TOKEN", "CLAUDE_CODE_USE_BEDROCK", "CLAUDE_CODE_USE_VERTEX")


@dataclass
class SessionConfig:
    claude_cmd: list[str] = field(default_factory=lambda: ["claude"])
    model: str = "claude-sonnet-5-5"
    max_turns: int | None = None       # passed only when set and supported by the CLI
    max_budget_usd: float = 2.0
    timeout_s: float = 1800
    allowed_tools: list[str] = field(default_factory=list)
    permission_mode: str = "acceptEdits"
    setting_sources: str = "project,local"
    disable_slash_commands: bool = True
    extra_args: list[str] = field(default_factory=list)
    env: dict[str, str] = field(default_factory=dict)
    auth: str = "subscription"         # scrub KEY_VARS; a session that reports a key is refused. "api-key" permits one


@dataclass
class SessionResult:
    exit_code: int | None
    subtype: str
    is_error: bool
    total_cost_usd: float
    num_turns: int
    session_id: str
    structured_output: dict[str, Any] | None
    result_text: str
    permission_denials: list[Any]
    transcript_path: str
    stderr_path: str
    timed_out: bool
    duration_s: float
    started: bool = True          # the CLI emitted at least one event
    has_result: bool = True       # a `result` event was seen (cost figures are real)
    stderr_tail: str = ""
    api_key_source: str | None = None   # init event `apiKeySource`: "none" means the subscription login

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)

    @property
    def used_api_key(self) -> bool:
        return self.api_key_source not in (None, "none")


def build_argv(cfg: SessionConfig, prompt: str, schema: dict[str, Any] | None = None,
               system_prompt: str | None = None) -> list[str]:
    argv = [*cfg.claude_cmd, "-p", prompt, "--model", cfg.model,
            "--output-format", "stream-json", "--verbose",
            "--permission-mode", cfg.permission_mode, "--permission-prompts", "none",
            "--no-session-persistence", "--setting-sources", cfg.setting_sources,
            "--max-budget-usd", str(cfg.max_budget_usd)]
    if cfg.max_turns:
        argv += ["--max-turns", str(cfg.max_turns)]
    if schema is not None:
        argv += ["--json-schema", json.dumps(schema)]
    if system_prompt:
        argv += ["--append-system-prompt", system_prompt]
    if cfg.disable_slash_commands:
        argv.append("--disable-slash-commands")
    argv += list(cfg.extra_args)
    if cfg.allowed_tools:
        argv += ["--allowedTools", *cfg.allowed_tools]   # variadic: keep it last
    return argv


def parse_transcript(transcript: Path) -> dict[str, Any] | None:
    """The last `result` event, or None when the run died before emitting one."""
    last: dict[str, Any] | None = None
    if not transcript.exists():
        return None
    for line in transcript.read_text(errors="replace").splitlines():
        try:
            ev = json.loads(line)
        except json.JSONDecodeError:
            continue
        if isinstance(ev, dict) and ev.get("type") == "result":
            last = ev
    return last


def init_event(transcript: Path) -> dict[str, Any] | None:
    """The first `system`/`init` event: model, cwd and `apiKeySource` of the session."""
    if not transcript.exists():
        return None
    for line in transcript.read_text(errors="replace").splitlines():
        try:
            ev = json.loads(line)
        except json.JSONDecodeError:
            continue
        if isinstance(ev, dict) and ev.get("type") == "system" and ev.get("subtype") == "init":
            return ev
    return None


def transcript_has_events(transcript: Path) -> bool:
    if not transcript.exists():
        return False
    for line in transcript.read_text(errors="replace").splitlines():
        try:
            if isinstance(json.loads(line), dict):
                return True
        except json.JSONDecodeError:
            continue
    return False


def run_session(cfg: SessionConfig, prompt: str, cwd: str | Path, out_dir: str | Path,
                schema: dict[str, Any] | None = None, system_prompt: str | None = None,
                name: str = "session") -> SessionResult:
    out_dir = Path(out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    transcript = out_dir / f"{name}.transcript.jsonl"
    stderr = out_dir / f"{name}.stderr.txt"
    (out_dir / f"{name}.prompt.txt").write_text(prompt)
    argv = build_argv(cfg, prompt, schema, system_prompt)
    (out_dir / f"{name}.argv.json").write_text(json.dumps(argv, indent=1))
    env = {**os.environ, **cfg.env}
    if cfg.auth == "subscription":
        for k in KEY_VARS:
            env.pop(k, None)
    t0 = time.monotonic()
    timed_out = False
    with open(transcript, "wb") as fo, open(stderr, "wb") as fe:
        proc = subprocess.Popen(argv, cwd=str(cwd), stdout=fo, stderr=fe, stdin=subprocess.DEVNULL,
                                start_new_session=True, env=env)
        try:
            proc.wait(timeout=cfg.timeout_s)
        except subprocess.TimeoutExpired:
            kill_group(proc)
            timed_out = True
        except BaseException:          # Ctrl-C or a crash must not leave claude running
            kill_group(proc)
            raise
    duration = time.monotonic() - t0
    ev, started = parse_transcript(transcript), transcript_has_events(transcript)
    init = init_event(transcript)
    source = str(init["apiKeySource"]) if init and "apiKeySource" in init else None
    tail = "\n".join(stderr.read_text(errors="replace").splitlines()[-20:]) if stderr.exists() else ""
    if ev is None:
        return SessionResult(proc.returncode, "timeout" if timed_out else "no_result", True, 0.0, 0, "",
                             None, "", [], str(transcript), str(stderr), timed_out, duration,
                             started=started, has_result=False, stderr_tail=tail, api_key_source=source)
    so = ev.get("structured_output")
    return SessionResult(
        exit_code=proc.returncode,
        subtype=str(ev.get("subtype", "unknown")),
        is_error=bool(ev.get("is_error", False)),
        total_cost_usd=float(ev.get("total_cost_usd") or 0.0),
        num_turns=int(ev.get("num_turns") or 0),
        session_id=str(ev.get("session_id", "")),
        structured_output=so if isinstance(so, dict) else None,
        result_text=str(ev.get("result", "") or ""),
        permission_denials=list(ev.get("permission_denials") or []),
        transcript_path=str(transcript), stderr_path=str(stderr),
        timed_out=timed_out, duration_s=duration, started=True, has_result=True, stderr_tail=tail,
        api_key_source=source)
