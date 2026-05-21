import inspect
import os
import threading
import time
from typing import Callable, Iterable, Optional

from utils.console import info, warn

DEFAULT_MODEL = "gpt-4o-mini"
DEFAULT_PROVIDER = "openai"
DEFAULT_MAX_TURNS = 8
DEFAULT_CHUNK_SIZE = 48

_CHAT_ACTIVE = False
_ENV_LOADED = False
_SESSION = None
_SESSION_LOCK = threading.Lock()


def set_chat_active(active: bool) -> None:
    global _CHAT_ACTIVE
    _CHAT_ACTIVE = active


def is_chat_active() -> bool:
    return _CHAT_ACTIVE


def chatgpt_command(args, kwargs=None):
    if kwargs is None:
        kwargs = {}

    if _wants_close(args, kwargs):
        set_chat_active(False)
        info("ChatGPT session closed.")
        return

    if _wants_reset(args, kwargs):
        reset_chat_session()
        info("ChatGPT session reset.")

    set_chat_active(True)
    info("You are now talking to chatgpt")
    info("Type /exit to return to commands. Use /reset to clear chat history.")


def stream_chat_response(
    message: str,
    on_chunk: Optional[Callable[[str], None]] = None,
    on_done: Optional[Callable[[str], None]] = None,
    on_error: Optional[Callable[[Exception], None]] = None,
    chunk_size: Optional[int] = None,
) -> None:
    if on_chunk is None:
        on_chunk = lambda _: None
    if on_done is None:
        on_done = lambda _: None
    if on_error is None:
        on_error = lambda _: None

    def _worker():
        try:
            session = _get_chat_session()
            response = session.generate(message)
            size = chunk_size or _read_int("LLM_STREAM_CHUNK_SIZE", DEFAULT_CHUNK_SIZE)
            delay = _read_float("LLM_STREAM_DELAY", 0.0)
            for chunk in _chunk_text(response, size):
                on_chunk(chunk)
                if delay and delay > 0:
                    time.sleep(delay)
            on_done(response)
        except Exception as exc:
            on_error(exc)

    threading.Thread(target=_worker, daemon=True).start()


def reset_chat_session() -> None:
    global _SESSION
    with _SESSION_LOCK:
        _SESSION = None


def _wants_close(args, kwargs) -> bool:
    if "close" in kwargs or "hide" in kwargs:
        return True
    if args:
        value = str(args[0]).strip().lower()
        return value in {"close", "hide", "exit", "quit"}
    return False


def _wants_reset(args, kwargs) -> bool:
    if "reset" in kwargs or "clear" in kwargs:
        return True
    if args:
        value = str(args[0]).strip().lower()
        return value in {"reset", "clear"}
    return False


def _get_chat_session():
    global _SESSION
    with _SESSION_LOCK:
        if _SESSION is None:
            _load_env_file()
            _SESSION = ChatSession()
        return _SESSION


class ChatSession:
    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._history = []
        self._max_turns = _read_int("CHAT_MAX_TURNS", DEFAULT_MAX_TURNS)
        self._system_prompt = os.getenv("CHAT_SYSTEM_PROMPT", "").strip()

        dspy = _load_dspy()
        self._module = _build_chat_module(dspy)
        self._configure_lm(dspy)

    def generate(self, message: str) -> str:
        history_text = self._format_history()
        result = self._module(history=history_text, message=message)
        response = str(result.response).strip()

        with self._lock:
            self._history.append(("user", message))
            self._history.append(("assistant", response))

        return response

    def _format_history(self) -> str:
        with self._lock:
            history = list(self._history)
            max_turns = self._max_turns
            system_prompt = self._system_prompt

        if max_turns > 0:
            history = history[-(max_turns * 2) :]

        lines = []
        if system_prompt:
            lines.append(f"System: {system_prompt}")

        for role, content in history:
            prefix = "User" if role == "user" else "Assistant"
            lines.append(f"{prefix}: {content}")

        return "\n".join(lines).strip()

    def _configure_lm(self, dspy):
        provider = _resolve_provider()
        model = _resolve_model(provider)
        api_key = _resolve_api_key(provider)
        if not api_key:
            raise RuntimeError(
                "Missing API key. Set LLM_API_KEY or OPENAI_API_KEY in .env."
            )

        options = {"api_key": api_key}
        temperature = _read_float("LLM_TEMPERATURE")
        if temperature is not None:
            options["temperature"] = temperature
        max_tokens = _read_int("LLM_MAX_TOKENS")
        if max_tokens is not None:
            options["max_tokens"] = max_tokens

        lm = _build_lm(dspy, provider, model, options)
        if hasattr(dspy, "configure"):
            dspy.configure(lm=lm)
        elif hasattr(dspy, "settings") and hasattr(dspy.settings, "configure"):
            dspy.settings.configure(lm=lm)
        else:
            raise RuntimeError("DSPy is missing a configure method.")


def _build_chat_module(dspy):
    class ChatSignature(dspy.Signature):
        """Simple chat assistant."""

        history = dspy.InputField(desc="Conversation history")
        message = dspy.InputField(desc="New user message")
        response = dspy.OutputField(desc="Assistant response")

    class ChatModule(dspy.Module):
        def __init__(self):
            super().__init__()
            self.respond = dspy.Predict(ChatSignature)

        def forward(self, history: str, message: str):
            return self.respond(history=history, message=message)

    return ChatModule()


def _build_lm(dspy, provider: str, model: str, options: dict):
    if hasattr(dspy, "LM"):
        return _instantiate(dspy.LM, model=model, **options)

    if hasattr(dspy, "OpenAI"):
        base_model = model.split("/", 1)[-1]
        return _instantiate(dspy.OpenAI, model=base_model, **options)

    raise RuntimeError("No supported DSPy LLM backend found.")


def _instantiate(factory, **kwargs):
    params = inspect.signature(factory).parameters
    accepts_kwargs = any(
        param.kind == inspect.Parameter.VAR_KEYWORD for param in params.values()
    )
    if accepts_kwargs:
        filtered = dict(kwargs)
    else:
        filtered = {}
        for key, value in kwargs.items():
            if key in params:
                filtered[key] = value
    if "model" not in params and "model" in kwargs and "model_name" in params:
        filtered["model_name"] = kwargs["model"]
    return factory(**filtered)


def _resolve_provider() -> str:
    value = os.getenv("LLM_PROVIDER") or DEFAULT_PROVIDER
    return str(value).strip().lower()


def _resolve_model(provider: str) -> str:
    model = (os.getenv("LLM_MODEL") or DEFAULT_MODEL).strip()
    if not model:
        model = DEFAULT_MODEL
    if "/" not in model:
        model = f"{provider}/{model}"
    return model


# TODO: Change this to .env loading
def _resolve_api_key(provider: str) -> Optional[str]:
    api_key = os.getenv("LLM_API_KEY")
    if api_key:
        return api_key

    provider_keys = {
        "openai": "OPENAI_API_KEY",
        "anthropic": "ANTHROPIC_API_KEY",
        "azure": "AZURE_OPENAI_API_KEY",
        "google": "GOOGLE_API_KEY",
    }
    key_name = provider_keys.get(provider, "OPENAI_API_KEY")
    return os.getenv(key_name) or os.getenv("OPENAI_API_KEY")


def _load_env_file(path: str = ".env") -> None:
    global _ENV_LOADED
    if _ENV_LOADED:
        return
    _ENV_LOADED = True

    if not os.path.exists(path):
        return

    try:
        with open(path, "r", encoding="utf-8") as file:
            for raw_line in file:
                line = raw_line.strip()
                if not line or line.startswith("#"):
                    continue
                if line.startswith("export "):
                    line = line[len("export ") :]
                if "=" not in line:
                    continue
                key, value = line.split("=", 1)
                key = key.strip()
                value = value.strip().strip('"').strip("'")
                if key and key not in os.environ:
                    os.environ[key] = value
    except Exception as exc:
        warn(f"Failed to load .env: {exc}")


def _load_dspy():
    try:
        import dspy

        return dspy
    except Exception as exc:
        raise RuntimeError(
            "dspy-ai is required. Install with: pip install dspy-ai"
        ) from exc


def _chunk_text(text: str, chunk_size: int) -> Iterable[str]:
    if chunk_size <= 0:
        yield text
        return

    for idx in range(0, len(text), chunk_size):
        yield text[idx : idx + chunk_size]


def _read_int(name: str, default: Optional[int] = None) -> Optional[int]:
    raw = os.getenv(name)
    if raw is None or str(raw).strip() == "":
        return default
    try:
        return int(raw)
    except ValueError:
        warn(f"Invalid {name} value: {raw}")
        return default


def _read_float(name: str, default: Optional[float] = None) -> Optional[float]:
    raw = os.getenv(name)
    if raw is None or str(raw).strip() == "":
        return default
    try:
        return float(raw)
    except ValueError:
        warn(f"Invalid {name} value: {raw}")
        return default
