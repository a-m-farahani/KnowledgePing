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


def _generate(prompt: str, model: str, json_mode: bool = False) -> Optional[str]:
    payload = {"model": model, "prompt": prompt, "stream": False, "think": False}
    if json_mode:
        payload["format"] = "json"
    try:
        r = requests.post(
            f"{OLLAMA_BASE_URL}/api/generate",
            json=payload,
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
        f"""
        You are an English speaking practice tutor for beginners.

        Your ONLY job is to output ONE short, practical English sentence for the given topic. Do NOT add explanations, translations, grammar rules, or extra text.

        Follow these rules strictly:
        - Each sentence: maximum 10 words
        - Use only common, everyday words (A1/A2 level)
        - Sentences must be useful for real conversation: greetings, shopping, eating out, asking for help, talking about daily routines, talking about work
        - Use natural contractions (I'm, don't, it's)

        Topic: {topic}

        Example output for topic "ordering coffee":
        I'd like a coffee please.

        Now output a sentence for the topic below. ONLY sentence, nothing else.

        Topic: {topic}
    """
    )
    return _generate(prompt, model)


def generate_quiz(topic: str, model: str) -> Optional[tuple[str, str]]:
    prompt = f"""Generate a short English quiz for the topic "{topic}".

Return ONLY a JSON object with exactly two keys, no other text, no markdown:
{{"question": "the question text", "answer": "the answer text"}}

Rules:
- The question must be a fill-in-the-blank or error-correction prompt.
- The answer must be 1-5 words, A1/A2 vocabulary.
- Do not include any explanation, greeting, or extra lines."""

    raw = _generate(prompt, model, json_mode=True)
    if not raw:
        return None

    try:
        import json
        data = json.loads(raw)
        question = str(data.get("question", "")).strip()
        answer = str(data.get("answer", "")).strip()
        if question and answer:
            return question, answer
    except Exception:
        pass

    cleaned = raw.strip()
    if cleaned.startswith("```"):
        cleaned = cleaned.strip("`").strip()
        if "\n" in cleaned and not cleaned.lstrip().startswith(
            ("Q:", "A:", "Question:", "Answer:")
        ):
            cleaned = cleaned.split("\n", 1)[1].strip()

    question = answer = ""
    for line in cleaned.splitlines():
        line = line.strip()
        if not line:
            continue
        upper = line.upper()
        matched = False
        for prefix in ("QUESTION:", "Q:"):
            if upper.startswith(prefix):
                question = line[len(prefix):].strip()
                matched = True
                break
        if matched:
            continue
        for prefix in ("ANSWER:", "A:"):
            if upper.startswith(prefix):
                answer = line[len(prefix):].strip()
                break

    if question and answer:
        return question, answer
    return None
