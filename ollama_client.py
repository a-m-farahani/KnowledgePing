import requests
from typing import Optional

OLLAMA_BASE_URL = "http://localhost:11434"
TIMEOUT_GENERATE = 90 
TIMEOUT_CONNECT  = 4 


def is_available() -> bool:
    try:
        r = requests.get(f"{OLLAMA_BASE_URL}/api/tags", timeout=TIMEOUT_CONNECT)
        return r.status_code == 200
    except Exception:
        return False


def list_models() -> list[str]:
    try:
        r = requests.get(f"{OLLAMA_BASE_URL}/api/tags", timeout=TIMEOUT_CONNECT)
        r.raise_for_status()
        return [m["name"] for m in r.json().get("models", [])]
    except Exception:
        return []


def _generate(prompt: str, model: str) -> Optional[str]:
    try:
        r = requests.post(
            f"{OLLAMA_BASE_URL}/api/generate",
            json={"model": model, "prompt": prompt, "stream": False, "think": False},
            timeout=TIMEOUT_GENERATE,
        )
        r.raise_for_status()
        return r.json().get("response", "").strip()
    except requests.exceptions.ConnectionError:
        return None  # Ollama not running
    except requests.exceptions.Timeout:
        return None
    except Exception:
        return None


def generate_lesson(topic: str, model: str) -> Optional[str]:
    prompt = (
        f"Write a concise micro-lesson (4–6 sentences) about: {topic}\n\n"
        "Rules:\n"
        "- Plain text only, absolutely no markdown, no bullet points, no headers\n"
        "- Stay under 120 words total\n"
        "- Be direct and educational"
    )
    return _generate(prompt, model)


def generate_quiz(topic: str, model: str) -> Optional[tuple[str, str]]:
    prompt = (
        f"Create one quiz question about: {topic}\n\n"
        "Your ENTIRE response must be exactly two lines:\n"
        "QUESTION: [the question]\n"
        "ANSWER: [the answer]\n\n"
        "Keep each line under 2 sentences. Plain text only. No markdown."
    )
    raw = _generate(prompt, model)
    if not raw:
        return None

    question = answer = ""
    for line in raw.strip().splitlines():
        line = line.strip()
        if line.upper().startswith("QUESTION:"):
            question = line[9:].strip()
        elif line.upper().startswith("ANSWER:"):
            answer = line[7:].strip()

    if question and answer:
        return question, answer
    return None
