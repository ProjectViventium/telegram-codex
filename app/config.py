from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path

import yaml


def _read_env_file(path: Path) -> dict[str, str]:
    data: dict[str, str] = {}
    if not path.exists():
        return data
    for raw_line in path.read_text(encoding="utf-8").splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        data[key.strip()] = value.strip()
    return data


def _resolve_path(root: Path, raw: str) -> Path:
    path = Path(raw)
    if path.is_absolute():
        return path
    return (root / path).resolve()


def _pick_config_file(root: Path, tracked_name: str) -> Path:
    tracked_path = root / tracked_name
    if tracked_path.exists():
        return tracked_path
    example_path = tracked_path.with_name(f"{tracked_path.stem}.example{tracked_path.suffix}")
    if example_path.exists():
        return example_path
    raise RuntimeError(f"Missing config file: {tracked_path}")


@dataclass(frozen=True)
class BotSettings:
    token: str
    username: str
    private_chat_only: bool


@dataclass(frozen=True)
class PairingSettings:
    host: str
    port: int
    link_ttl_minutes: int
    bootstrap_if_empty: bool

    @property
    def base_url(self) -> str:
        return f"http://{self.host}:{self.port}"


@dataclass(frozen=True)
class CodexSettings:
    command: str
    model: str
    sandbox: str
    approval_policy: str
    skip_git_repo_check: bool


@dataclass(frozen=True)
class TranscriptionSettings:
    whisper_mode: str
    language: str
    model_name: str
    model_path: str
    threads: int


@dataclass(frozen=True)
class RuntimeSettings:
    root: Path
    logs_dir: Path
    sessions_path: Path
    paired_users_path: Path
    pending_pairs_path: Path
    project_registry_path: Path


@dataclass(frozen=True)
class AppConfig:
    root: Path
    bot: BotSettings
    pairing: PairingSettings
    codex: CodexSettings
    transcription: TranscriptionSettings
    runtime: RuntimeSettings


def load_config(root: Path | None = None) -> AppConfig:
    project_root = root or Path(__file__).resolve().parents[1]
    settings_override = (
        os.environ.get("TELEGRAM_CODEX_SETTINGS_FILE")
        or os.environ.get("VIVENTIUM_TELEGRAM_CODEX_SETTINGS_FILE")
        or ""
    )
    settings_path = (
        Path(settings_override).expanduser().resolve()
        if settings_override
        else _pick_config_file(project_root, "config/settings.yaml")
    )
    raw = yaml.safe_load(settings_path.read_text(encoding="utf-8")) or {}

    bot_raw = raw.get("bot") or {}
    pairing_raw = raw.get("pairing") or {}
    codex_raw = raw.get("codex") or {}
    transcription_raw = raw.get("transcription") or {}
    runtime_raw = raw.get("runtime") or {}
    projects_raw = raw.get("projects") or {}

    env_file_path = str(
        os.environ.get("TELEGRAM_CODEX_ENV_FILE")
        or os.environ.get("VIVENTIUM_TELEGRAM_CODEX_ENV_FILE")
        or bot_raw.get("env_file")
        or ".env"
    )
    env_file = _resolve_path(project_root, env_file_path)
    merged_env = dict(_read_env_file(env_file))
    merged_env.update(os.environ)

    token = str(merged_env.get("TELEGRAM_CODEX_BOT_TOKEN") or merged_env.get("BOT_TOKEN") or "").strip()
    if not token:
        raise RuntimeError(
            f"TELEGRAM_CODEX_BOT_TOKEN is missing. Set it in {env_file} or export it in the environment."
        )

    username = str(
        merged_env.get("TELEGRAM_CODEX_BOT_USERNAME") or merged_env.get("TELEGRAM_BOT_USERNAME") or ""
    ).strip()

    project_registry_override = (
        os.environ.get("TELEGRAM_CODEX_PROJECTS_FILE")
        or os.environ.get("VIVENTIUM_TELEGRAM_CODEX_PROJECTS_FILE")
        or ""
    )

    return AppConfig(
        root=project_root,
        bot=BotSettings(
            token=token,
            username=username,
            private_chat_only=bool(bot_raw.get("private_chat_only", True)),
        ),
        pairing=PairingSettings(
            host=str(pairing_raw.get("host") or "127.0.0.1"),
            port=int(pairing_raw.get("port") or 8765),
            link_ttl_minutes=int(pairing_raw.get("link_ttl_minutes") or 15),
            bootstrap_if_empty=bool(pairing_raw.get("bootstrap_if_empty", True)),
        ),
        codex=CodexSettings(
            command=str(codex_raw.get("command") or "codex"),
            model=str(codex_raw.get("model") or "gpt-5.4"),
            sandbox=str(codex_raw.get("sandbox") or "workspace-write"),
            approval_policy=str(codex_raw.get("approval_policy") or "never"),
            skip_git_repo_check=bool(codex_raw.get("skip_git_repo_check", False)),
        ),
        transcription=TranscriptionSettings(
            whisper_mode=str(transcription_raw.get("whisper_mode") or "pywhispercpp"),
            language=str(transcription_raw.get("language") or "en"),
            model_name=str(transcription_raw.get("model_name") or "large-v3-turbo"),
            model_path=str(transcription_raw.get("model_path") or ""),
            threads=int(transcription_raw.get("threads") or 8),
        ),
        runtime=RuntimeSettings(
            root=project_root,
            logs_dir=_resolve_path(project_root, str(runtime_raw.get("logs_dir") or "runtime/logs")),
            sessions_path=_resolve_path(
                project_root, str(runtime_raw.get("sessions_path") or "runtime/state/chat_sessions.json")
            ),
            paired_users_path=_resolve_path(
                project_root, str(runtime_raw.get("paired_users_path") or "runtime/state/paired_users.json")
            ),
            pending_pairs_path=_resolve_path(
                project_root, str(runtime_raw.get("pending_pairs_path") or "runtime/state/pair_tokens.json")
            ),
            project_registry_path=(
                Path(project_registry_override).expanduser().resolve()
                if project_registry_override
                else _resolve_path(project_root, str(projects_raw.get("registry_file") or "config/projects.yaml"))
            ),
        ),
    )
