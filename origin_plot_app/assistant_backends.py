"""Optional ways to turn a sentence into an action. All of them return {"action", "params"} that assistant_actions.validate accepts,
or fall back to the keyword parser. A model sees only: the action list, the names of the loaded files, and the sentence. Never a data row."""
import json, os, re, shutil, subprocess, urllib.request, urllib.error
import assistant_actions as aa, assistant_parser as ap, assistant_secrets as sec

def _prompt(sentence, file_names):
    return ("You translate one sentence into exactly one action for a plotting program. Answer with a single JSON object "
            '{"action": <name>, "params": {...}} and nothing else. Allowed actions:\n' + aa.action_list_text() +
            "\nLoaded files: " + ", ".join(map(str, file_names or [])) + "\nSentence: " + sentence)

def _extract(text):
    """First JSON object in the model's answer, validated. Anything else is an error (the caller falls back to the parser)."""
    m = re.search(r"\{.*\}", str(text), re.S)
    if not m: raise aa.ActionError("the model gave no JSON")
    try: return aa.validate(json.loads(m.group(0)))
    except json.JSONDecodeError as e: raise aa.ActionError("the model's JSON could not be read") from e

def _post(url, body, headers, timeout=60):
    req = urllib.request.Request(url, json.dumps(body).encode("utf-8"), headers, "POST")
    with urllib.request.urlopen(req, timeout=timeout) as r: return json.loads(r.read().decode("utf-8"))      # certificate checks stay on

def ollama(sentence, file_names, model="llama3.1", address="http://localhost:11434"):
    r = _post(address.rstrip("/") + "/api/chat", {"model": model, "stream": False, "format": "json", "messages": [{"role": "user", "content": _prompt(sentence, file_names)}]}, {"Content-Type": "application/json"})
    return _extract(r["message"]["content"])

def api_key(sentence, file_names, model="claude-sonnet-5-5", key=None, endpoint="https://api.anthropic.com/v1/messages"):
    key = key or sec.load()
    if not key: raise aa.ActionError("no API key is set")
    r = _post(endpoint, {"model": model, "max_tokens": 300, "messages": [{"role": "user", "content": _prompt(sentence, file_names)}]},
              {"x-api-key": key, "anthropic-version": "2023-06-01", "content-type": "application/json"})
    return _extract("".join(b.get("text", "") for b in r.get("content", [])))

def test_connection(model="claude-sonnet-5-5", key=None, endpoint="https://api.anthropic.com/v1/messages"):
    """(ok, message). The message never contains the key."""
    key = key or sec.load()
    if not key: return False, "No key set."
    try:
        _post(endpoint, {"model": model, "max_tokens": 5, "messages": [{"role": "user", "content": "ping"}]}, {"x-api-key": key, "anthropic-version": "2023-06-01", "content-type": "application/json"}, 20)
        return True, "Connected."
    except urllib.error.HTTPError as e: return False, f"The service answered {e.code}."
    except Exception as e: return False, sec.redact(f"Could not connect: {type(e).__name__}")

CLI_PROGRAMS = {"claude": ["claude", "-p"], "gemini": ["gemini", "-p"]}
CLI_NOTE = "This uses the command-line program you signed in to yourself. Check that its terms of service allow use from other programs."

def cli_available(program="claude"): return program in CLI_PROGRAMS and shutil.which(CLI_PROGRAMS[program][0]) is not None

def cli(sentence, file_names, program="claude", timeout=90):
    """Runs the program once, non-interactively, with the prompt as an argument. Token files of the program are never read by this app."""
    if not cli_available(program): raise aa.ActionError(f"the program '{program}' is not on PATH")
    p = subprocess.run(CLI_PROGRAMS[program] + [_prompt(sentence, file_names)], capture_output=True, text=True, timeout=timeout, stdin=subprocess.DEVNULL)
    return _extract(p.stdout)

def interpret(sentence, file_names=(), backend="parser", config=None):
    """Sentence -> (action or None, message). Model backends that fail or give something invalid fall back to the keyword parser."""
    c = config or {}; note = ""
    try:
        if backend == "ollama": return ollama(sentence, file_names, **{k: v for k, v in (c.get("ollama") or {}).items() if k in ("model", "address")}), ""
        if backend == "api": return api_key(sentence, file_names, model=(c.get("api") or {}).get("model", "claude-sonnet-5-5")), ""
        if backend == "cli": return cli(sentence, file_names, (c.get("cli") or {}).get("program", "claude")), ""
    except Exception as e: note = sec.redact(f"({backend} backend not used: {type(e).__name__}) ")
    a, msg = ap.run(sentence)
    if a:
        try: return aa.validate(a), note
        except aa.ActionError as e: return None, note + f"I understood the request, but: {e}"
    return None, note + msg
