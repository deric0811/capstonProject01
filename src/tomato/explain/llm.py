"""LLM 호출은 이 파일 한 곳에만 둔다 (spec §6). 가격은 예측하지 않고 설명만 만든다.

제공자는 설정(.env 또는 환경변수)으로만 고른다. 둘 다 OpenAI 호환 chat completions로 부른다.
- local: 데모 서버(RTX 2080 Ti 22GB)에서 띄운 학생 모델 서버. 사고(thinking) 출력은 skip_reasoning으로 끈다.
- api:   GPU가 없는 환경의 대체. 사용자 키(BYOK, .env의 GEMINI_API_KEY)를 쓴다. 기본은 Gemini의 OpenAI 호환 주소,
         모델 gemini-3.1-flash-lite (gemini-2.5-flash는 새 사용자에게 제공 중단, 2026-11-12 확인).
  주의: 사고(thinking) 토큰이 max_tokens 안에서 먼저 쓰이는 모델은 해설이 잘린다(gemini-3.5-flash는 512토큰에서 24자만 나옴).
  모델을 바꾸면 한 번 호출해 출력 길이를 확인한다.
- auto:  local 서버가 응답하면 local, 아니면 키가 있을 때 api, 둘 다 안 되면 None(템플릿 유지).
키는 .env에서 읽고 출력하거나 파일에 쓰지 않는다. 오류 메시지에서도 가린다.
"""
import json
import os
import time
import urllib.error
import urllib.request
from dataclasses import dataclass, field

from tomato import config

DEFAULTS = {
    "local": {"base_url": "http://localhost:8081/v1", "model": "hyperclovax-seed-think-14b-tomato",
              "extra": {"chat_template_kwargs": {"skip_reasoning": True}}},
    "api": {"base_url": "https://generativelanguage.googleapis.com/v1beta/openai", "model": "gemini-3.1-flash-lite",
            "extra": {}},
}


@dataclass(frozen=True)
class LLMSettings:
    provider: str
    base_url: str
    model: str
    api_key: str = field(default="", repr=False)
    timeout: float = 60.0
    extra: dict = field(default_factory=dict)


def _env(env_file=config.ROOT / ".env"):
    return {**config._load_dotenv(env_file), **os.environ}


def settings_for(provider, env=None):
    env = _env() if env is None else env
    d = DEFAULTS[provider]
    p = provider.upper()
    return LLMSettings(
        provider=provider,
        base_url=env.get(f"LLM_{p}_BASE_URL", d["base_url"]).rstrip("/"),
        model=env.get(f"LLM_{p}_MODEL", d["model"]),
        api_key=env.get("GEMINI_API_KEY", "") if provider == "api" else env.get("LLM_LOCAL_API_KEY", ""),
        timeout=float(env.get("LLM_TIMEOUT", 60)),
        extra=d["extra"],
    )


def _local_alive(s):
    try:
        with urllib.request.urlopen(f"{s.base_url}/models", timeout=2):
            return True
    except (urllib.error.URLError, OSError, ValueError):
        return False


def resolve(env=None):
    """LLM_PROVIDER = template | local | api | auto. 쓸 수 있는 설정 또는 None(템플릿)."""
    env = _env() if env is None else env
    choice = env.get("LLM_PROVIDER", "template")
    if choice == "template":
        return None
    if choice in ("local", "api"):
        return settings_for(choice, env)
    if choice != "auto":
        raise ValueError(f"LLM_PROVIDER는 template, local, api, auto 중 하나: {choice}")
    local = settings_for("local", env)
    if _local_alive(local):
        return local
    api = settings_for("api", env)
    return api if api.api_key else None


def chat(s, messages, temperature=0.0, max_tokens=512):
    """(문장, 걸린 초). 실패하면 RuntimeError (키는 가린다)."""
    body = {"model": s.model, "messages": messages, "temperature": temperature, "max_tokens": max_tokens, **s.extra}
    headers = {"Content-Type": "application/json"}
    if s.api_key:
        headers["Authorization"] = f"Bearer {s.api_key}"
    req = urllib.request.Request(f"{s.base_url}/chat/completions", data=json.dumps(body).encode(), headers=headers)
    t0 = time.time()
    try:
        with urllib.request.urlopen(req, timeout=s.timeout) as resp:
            out = json.loads(resp.read())
    except urllib.error.HTTPError as e:
        detail = e.read().decode(errors="replace")[:300]
        raise RuntimeError(config.mask(f"{s.provider} HTTP {e.code}: {detail}", [s.api_key] if s.api_key else [])) from None
    except (urllib.error.URLError, OSError) as e:
        raise RuntimeError(config.mask(f"{s.provider} 연결 실패: {e}", [s.api_key] if s.api_key else [])) from None
    return out["choices"][0]["message"]["content"].strip(), time.time() - t0
