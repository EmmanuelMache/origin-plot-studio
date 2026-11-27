"""The assistant of the Origin plot app: it links the app to an AI of your choice.

You type what you want in plain words ("name these Sample A (4 % additive), label the peak at 29.4 as alite, draw them and save in
D:\\Paper2"). The app sends your words and a short list of the loaded graphs to the AI. The AI answers with a list of
steps the app knows; the app carries them out with its own tested code. The AI never draws anything itself and never
changes your numbers.

Which AI: Claude (Anthropic), ChatGPT (OpenAI), Gemini (Google), a local model (Ollama), or any service that speaks the
OpenAI chat format. The app finds out which one from the key you paste, or from the address.

Only the Python standard library is used; nothing has to be installed.
"""
import os, re, json, datetime, urllib.request, urllib.error, urllib.parse

PROVIDERS = {
    "anthropic": dict(name="Claude (Anthropic)", base="https://api.anthropic.com", env="ANTHROPIC_API_KEY", prefer=r"sonnet", keypage="https://platform.claude.com/settings/keys"),
    "openai": dict(name="ChatGPT (OpenAI)", base="https://api.openai.com/v1", env="OPENAI_API_KEY", prefer=r"^gpt-", keypage="https://platform.openai.com/api-keys"),
    "gemini": dict(name="Gemini (Google)", base="https://generativelanguage.googleapis.com/v1beta", env="GEMINI_API_KEY", prefer=r"flash", keypage="https://aistudio.google.com/api-keys"),
    "kimi": dict(name="Kimi (Moonshot AI)", base="https://api.moonshot.ai/v1", env="MOONSHOT_API_KEY", prefer=r"kimi", keypage="https://platform.kimi.ai/console/api-keys"),
    "ollama": dict(name="Local model on this computer (Ollama, free)", base="http://localhost:11434/v1", env="", prefer=r"", keypage="https://ollama.com/download"),
    "other": dict(name="Other service (OpenAI-compatible address)", base="", env="", prefer=r"", keypage=""),
}
AUTO = "Automatic (paste a key, the app sees whose it is)"
CHOICES = [AUTO] + [p["name"] for p in PROVIDERS.values()]
NEEDS_KEY = ("anthropic", "openai", "gemini", "kimi")
# the first letters of a key say whose key it is. A Kimi key begins like an OpenAI key: choose Kimi in the list for it
KEY_HINTS = [("sk-ant-", "anthropic", ""), ("AIza", "gemini", ""), ("sk-or-", "other", "https://openrouter.ai/api/v1"), ("gsk_", "other", "https://api.groq.com/openai/v1"),
             ("xai-", "other", "https://api.x.ai/v1"), ("sk-", "openai", "")]
GUIDES = {
    None: "Easiest: copy the key of your AI and press Paste. The app sees from the key whose it is and connects by itself. No key yet? Choose your AI in the list, then 'Get a key…' opens its page. (A Kimi key looks like an OpenAI key: choose Kimi in the list.)",
    "anthropic": "'Get a key…' opens the Claude Console in your browser: sign in, press Create key, copy the key (it begins with sk-ant-). Come back and press Paste: the app connects by itself. If the Console offers a workspace when you create the key, choose one.",
    "openai": "'Get a key…' opens the OpenAI platform in your browser: sign in, create a key under API keys, copy it. Come back and press Paste: the app connects by itself. Billing must be set up there before the key works.",
    "gemini": "'Get a key…' opens Google AI Studio in your browser: sign in, press Create API key, copy it (it begins with AIza). Come back and press Paste: the app connects by itself.",
    "kimi": "'Get a key…' opens the Kimi platform in your browser: sign in, open API Keys, create a key and copy it. Come back and press Paste: the app connects by itself.",
    "ollama": "Free, and nothing leaves this computer. 'Get the program…' opens the Ollama page: install it and download one model in it. Then press Connect. Small local models follow instructions less reliably than the large ones.",
    "other": "For any service that speaks the OpenAI chat format: type its address (for example https://api.mistral.ai/v1), paste its key, press Connect.",
}

def provider_of(choice):
    """The provider behind a line of the list, or None for 'Automatic'."""
    return next((k for k, p in PROVIDERS.items() if p["name"] == choice), None)

def whose_key(key):
    """The provider a key belongs to, from its first letters, or None."""
    return next((p for pre, p, b in KEY_HINTS if str(key or "").strip().startswith(pre)), None)

ANTHROPIC_VERSION = "2023-06-01"
MAX_ROUNDS = 6


class AIError(Exception):
    """A problem with the AI service, already put in plain words."""


def _host_of(address):
    """(host name, port or None) of an address, parsed; ('', None) when it cannot be read."""
    try:
        p = urllib.parse.urlsplit(str(address).strip() if "//" in str(address) else "//" + str(address).strip())
        return (p.hostname or "").lower().rstrip("."), p.port
    except Exception: return "", None

def _is(host, domain): return host == domain or host.endswith("." + domain)

def detect(key="", address="", choice="", *, entered=None):
    """Which AI is this? Returns dict(provider, name, base, key, how, host). `choice` is the text of the list in the window.
    host is the name of the computer the requests (and the key) go to: show it when the user connects.
    entered=True: the user typed or pasted this key NOW for this address; the key is then bound to that service (see bind_key).
    Otherwise a key that was entered for one service is not sent to another one (key_check)."""
    key = (key or "").strip(); address = (address or "").strip().rstrip("/"); how = ""
    prov = provider_of(choice)
    if prov is None:
        if address:
            # the kind of service is read from the parsed HOST name, never from a word somewhere in the address
            host, port = _host_of(address)
            prov = ("anthropic" if _is(host, "anthropic.com") else "gemini" if _is(host, "googleapis.com") else "openai" if host == "api.openai.com"
                    else "kimi" if (_is(host, "moonshot.ai") or _is(host, "moonshot.cn") or _is(host, "kimi.ai") or _is(host, "kimi.com"))
                    else "ollama" if (_loopback(host) and (port == 11434 or not key)) else "other"); how = "from the address"
        elif key:
            hit = next(((p, b) for pre, p, b in KEY_HINTS if key.startswith(pre)), None)
            if hit: prov, address = hit[0], hit[1]; how = "from the key"
            else: raise AIError("I cannot tell from this key which AI it belongs to. Choose the AI in the list" + " (for a service not in the list: 'Other service' and its address).")
        else:
            env = next((k for k, p in PROVIDERS.items() if p["env"] and os.environ.get(p["env"])), None)
            if env: prov = env; key = os.environ[PROVIDERS[env]["env"]].strip(); how = f"from the key in the Windows variable {PROVIDERS[env]['env']}"
            else: prov = "ollama"; how = "no key given: looking for a local model (Ollama) on this computer"
    p = PROVIDERS[prov]
    if not key and p["env"] and os.environ.get(p["env"]): key = os.environ[p["env"]].strip()
    base = address or p["base"]
    if prov == "other" and not base: raise AIError("For 'Other service' the address is needed, for example https://api.mistral.ai/v1")
    if prov in NEEDS_KEY and not key: raise AIError(f"{p['name']} needs a key. Press 'Get a key…' if you have none yet, then Paste.")
    if prov == "anthropic": base = re.sub(r"/v1$", "", base)
    conn = dict(provider=prov, name=p["name"] if prov != "other" else service_host(base) or "Other service", base=base, key=key, how=how, host=service_host(base))
    if entered and key: bind_key(key, base)
    return conn


def _loopback(host):
    try:
        import outbound_policy
        return outbound_policy.is_loopback(host)
    except Exception: return False

def service_host(base):
    """The host name (with a port that is not the usual one) a service address really points to."""
    host, port = _host_of(base); usual = {"https": 443, "http": 80}.get(str(base).split("://", 1)[0].lower()) if "://" in str(base) else None
    return host + (f":{port}" if port and port != usual else "") if host else ""

def origin_text(base):
    """'https://host:port' of an address: what 'the same service' means for a key."""
    try:
        p = urllib.parse.urlsplit(str(base).strip()); s = (p.scheme or "").lower(); host = (p.hostname or "").lower().rstrip(".")
        port = p.port or (443 if s == "https" else 80 if s == "http" else 0)
        return f"{s}://{host}:{port}" if host and s else ""
    except Exception: return ""


# ----------------------------------------------------------------------------- a key belongs to the service it was entered for
_BOUND = {}          # fingerprint of a key (never the key) -> origin of the service it was entered for; in memory, and beside the key reference in assistant.json

def _fp(key):
    import hashlib
    return hashlib.sha256(("ops-key\0" + str(key)).encode("utf-8")).hexdigest()

def bind_key(key, base):
    """Say that this key was entered for the service at `base` (the user pasted it for that address)."""
    o = origin_text(base)
    if str(key or "").strip() and o: _BOUND[_fp(str(key).strip())] = o
    return o

def unbind_key(key):
    _BOUND.pop(_fp(str(key or "").strip()), None)

def key_check(conn):
    """Called before a key is put into a request. A key that was saved or entered for one service (bind_key: when it is pasted
    for an address, when it is saved, when it is read back from the settings) is never sent to another address: after the address
    of a service changed, the key has to be removed and entered again for the new one. A key the app has never stored or been
    told a service for (typed for this one request, or from a Windows variable) is not bound."""
    key = str(conn.get("key") or "").strip()
    if not key: return True
    was = _BOUND.get(_fp(key))
    if was is None: return True
    now = origin_text(conn.get("base", ""))
    if was != now:
        raise AIError(f"This key was entered for {service_host(was)}, but the address now points to {service_host(now) or 'an address that cannot be read'}. The key was NOT sent there. "
                      f"If that is the service you want, remove the saved key and enter the key of that service again.")
    return True


class AIBlocked(AIError, PermissionError):
    """The outbound policy or the address rules do not allow this request (also an outbound_policy-style PermissionError)."""


def _opener(local, origin_url):
    """The way requests leave: certificates verified against this computer's and the standard public list (net.py); a model on
    this computer is never reached through a proxy; a redirect is followed only to the SAME service over the same kind of
    connection - never to another host, port or down to plain http, so the key and your text cannot be sent on elsewhere."""
    import outbound_policy as op
    class SameOrigin(urllib.request.HTTPRedirectHandler):
        def redirect_request(self, req, fp, code, msg, headers, newurl):
            try: op.check_url(newurl, loopback_http=True)
            except op.Blocked as e: raise AIBlocked(f"{service_host(origin_url)} sent the request on to an address the app does not use ({e}). It was not followed; your key was not sent there.")
            if not op.same_origin(origin_url, newurl):
                raise AIBlocked(f"{service_host(origin_url)} sent the request on to another place ({service_host(newurl)}). It was not followed; your key and your text were not sent there.")
            return super().redirect_request(req, fp, code, msg, headers, newurl)
    if local: return urllib.request.build_opener(urllib.request.ProxyHandler({}), SameOrigin())
    try:
        import net; https_ = urllib.request.HTTPSHandler(context=net.context())       # trust this computer's certificates and the standard public list (see net.py)
    except Exception: https_ = urllib.request.HTTPSHandler()
    return urllib.request.build_opener(https_, SameOrigin())


def _redact(text):
    try:
        import outbound_policy
        return outbound_policy.redact(str(text))
    except Exception: return "(details withheld)"


def _http(method, url, headers, body=None, timeout=180):
    import outbound_policy as op
    # The policy is asked HERE, where the request leaves: local-only mode and the AI switch stop it, a remote address must be
    # https, and plain http is accepted only for a real loopback address of this computer on an approved port.
    try: parsed = op.require("ai", url, loopback_http=True)
    except op.Blocked as e: raise AIBlocked(str(e))
    data = None if body is None else json.dumps(body).encode("utf-8")
    h = {"Content-Type": "application/json", "Accept": "application/json", "User-Agent": "OriginPlotApp"}; h.update(headers or {})
    req = urllib.request.Request(url, data=data, headers=h, method=method)
    host = service_host(url)
    local = op.is_loopback(parsed.hostname)                           # the parsed host: 'localhost.example.net' is not this computer
    opener = _opener(local, url)
    try:
        with opener.open(req, timeout=timeout) as r: raw = r.read().decode("utf-8", "replace")
    except urllib.error.HTTPError as e:
        try: txt = e.read().decode("utf-8", "replace")
        except Exception: txt = ""
        msg = ""
        try:
            j = json.loads(txt); er = j.get("error", j) if isinstance(j, dict) else {}
            msg = (er.get("message") if isinstance(er, dict) else str(er)) or ""
        except Exception: msg = txt[:200]
        msg = _redact(re.sub(r"(key=)[^&\s]+", r"\1***", str(msg)))[:300]
        what = {400: "The AI service did not understand the request", 401: "The AI service did not accept the key", 403: "The key is not allowed to do this",
                404: "The AI service does not know this model or address", 429: "The limit of this key is reached (too many requests, or no credit left)",
                529: "The AI service is overloaded at the moment"}.get(e.code, "The AI service has a problem" if e.code >= 500 else "The AI service refused the request")
        if e.code in (301, 302, 303, 307, 308): what = "The AI service sent the request on to another address, which the app does not follow with your key"
        raise AIError(f"{what} ({host}, code {e.code})" + (f": {msg}" if msg else ""))
    except AIError: raise
    except urllib.error.URLError as e:
        if isinstance(getattr(e, "reason", None), AIError): raise e.reason
        if "CERTIFICATE_VERIFY_FAILED" in str(e).upper() or "SSL:" in str(e).upper():
            raise AIError(f"This computer could not verify the secure connection to {host}. That is usually an antivirus or a company or university network that inspects secure connections, or a wrong date on the computer. Ask whoever looks after the computer to trust that connection; nothing is wrong with your key.")
        raise AIError(f"I could not reach {host} ({_redact(getattr(e, 'reason', e))}). " + ("Is the local model program (Ollama) running?" if local else "Check the internet connection, or a firewall or proxy of the university network."))
    except Exception as e:
        raise AIError(f"I could not reach {host}: {_redact(e)}")
    try: return json.loads(raw)
    except Exception: raise AIError(f"{host} answered with something that is not the expected format: {_redact(raw[:160])}")


def _auth(conn):
    key_check(conn)                                                   # a key goes only to the service it was entered for
    if conn["provider"] == "anthropic":
        if conn.get("auth") == "bearer": return {"Authorization": "Bearer " + conn["key"], "anthropic-version": ANTHROPIC_VERSION}
        return {"x-api-key": conn["key"], "anthropic-version": ANTHROPIC_VERSION}
    if conn["provider"] == "gemini": return {"x-goog-api-key": conn["key"]}
    return {"Authorization": "Bearer " + conn["key"]} if conn.get("key") else {}


NOT_CHAT = re.compile(r"(?i)embed|whisper|tts|dall-e|image|audio|realtime|moderation|transcri|davinci|babbage|sora|search|rerank|guard|speech|video|vision-preview|instruct|codex")

def models(conn):
    """The models this key can use, the most suitable first. An empty list when the service does not tell."""
    p = conn["provider"]; b = conn["base"]
    try:
        if p == "anthropic":
            try: j = _http("GET", b + "/v1/models?limit=100", _auth(conn))
            except AIError as e:
                if "code 401" not in str(e) or conn.get("auth") == "bearer": raise
                conn["auth"] = "bearer"                               # the other way the Claude API takes a key
                try: j = _http("GET", b + "/v1/models?limit=100", _auth(conn))
                except AIError: conn.pop("auth", None); raise e
            ids = [m["id"] for m in j.get("data", []) if m.get("lifecycle", "active") != "retired"]
        elif p == "gemini":
            j = _http("GET", b + "/models?pageSize=1000", _auth(conn))
            ids = [m["name"].split("/", 1)[-1] for m in j.get("models", []) if "generateContent" in (m.get("supportedGenerationMethods") or ["generateContent"])]
            ids = [i for i in ids if not NOT_CHAT.search(i)]
        else:
            j = _http("GET", b + "/models", _auth(conn)); ids = [m["id"] for m in (j.get("data") or j.get("models") or []) if isinstance(m, dict) and m.get("id")]
            if p == "openai": ids = sorted((i for i in ids if not NOT_CHAT.search(i)), reverse=True)
    except AIError as e:
        if p in ("other", "ollama") and "code 404" in str(e): return []          # some services have no list of models: type the name
        if p == "openai" and "code 401" in str(e) and conn.get("how") == "from the key": raise AIError(str(e) + "  (If this key is from Kimi, choose Kimi in the list: its keys look like OpenAI keys.)")
        if p == "anthropic" and "workspace" in str(e).lower(): raise AIError(str(e) + "  (Create the key again in the Claude Console with a workspace chosen.)")
        raise
    pref = PROVIDERS[p]["prefer"]
    if pref: ids = [i for i in ids if re.search(pref, i)] + [i for i in ids if not re.search(pref, i)]
    return ids


def _parts(provider, content, api="chat"):
    """A message with pictures: content is text, or a list of {"type": "text", "text"} and {"type": "image", "mime", "data" (base64)};
    turned into the form each service reads (Claude, ChatGPT chat / Responses, Gemini, OpenAI-compatible)."""
    if isinstance(content, str):
        return [{"text": content}] if provider == "gemini" else content
    out = []
    for c in content:
        if c.get("type") == "image":
            if provider == "anthropic": out.append({"type": "image", "source": {"type": "base64", "media_type": c["mime"], "data": c["data"]}})
            elif provider == "gemini": out.append({"inline_data": {"mime_type": c["mime"], "data": c["data"]}})
            elif api == "responses": out.append({"type": "input_image", "image_url": f"data:{c['mime']};base64,{c['data']}"})
            else: out.append({"type": "image_url", "image_url": {"url": f"data:{c['mime']};base64,{c['data']}"}})
        else:
            t = c.get("text", "")
            out.append({"text": t} if provider == "gemini" else {"type": "input_text", "text": t} if api == "responses" else {"type": "text", "text": t})
    return out


def _msgs(provider, messages, api="chat"):
    return [dict(m, content=_parts(provider, m["content"], api)) for m in messages]


def chat(conn, model, system, messages, timeout=180):
    """One question to the AI. `messages` is [{'role': 'user' | 'assistant', 'content': text}, ...]. Returns the answer text."""
    p = conn["provider"]; b = conn["base"]
    if not model: raise AIError("Choose a model first (the list 'Model').")
    if p == "anthropic":
        j = _http("POST", b + "/v1/messages", _auth(conn), {"model": model, "max_tokens": 4096, "system": system, "messages": _msgs(p, messages)}, timeout)
        txt = "".join(c.get("text", "") for c in j.get("content", []) if isinstance(c, dict) and c.get("type") == "text")
        if not txt and j.get("stop_reason") == "refusal": raise AIError("The AI declined to answer this request.")
    elif p == "gemini":
        body = {"system_instruction": {"parts": [{"text": system}]},
                "contents": [{"role": "model" if m["role"] == "assistant" else "user", "parts": _parts("gemini", m["content"])} for m in messages]}
        j = _http("POST", f"{b}/models/{urllib.parse.quote(model, safe='')}:generateContent", _auth(conn), body, timeout)
        cand = (j.get("candidates") or [{}])[0]; txt = "".join(pt.get("text", "") for pt in ((cand.get("content") or {}).get("parts") or []) if isinstance(pt, dict) and not pt.get("thought"))
        if not txt: raise AIError("The AI gave no answer" + (f" (reason: {(j.get('promptFeedback') or {}).get('blockReason') or cand.get('finishReason')})" if (j.get("promptFeedback") or cand.get("finishReason")) else "") + ".")
    else:
        j = _http("POST", b + "/chat/completions", _auth(conn), {"model": model, "messages": [{"role": "system", "content": system}] + _msgs(p, messages)}, timeout)
        msg = ((j.get("choices") or [{}])[0].get("message") or {}); c = msg.get("content")
        txt = c if isinstance(c, str) else "".join(pt.get("text", "") for pt in (c or []) if isinstance(pt, dict))
    if not (txt or "").strip(): raise AIError("The AI gave an empty answer. Try again, or choose another model.")
    return txt


# ----------------------------------------------------------------------------- answers that may search the web (the modern window's assistant)
NEW_WEB_TOOL = re.compile(r"(?i)fable|mythos|opus-5|opus-4-[678]|sonnet-5|sonnet-4-6")

def web_capable(conn):
    """Can this AI search the web itself? Claude, ChatGPT, Gemini, and OpenRouter (any model)."""
    p = conn.get("provider"); b = str(conn.get("base", "")).lower()
    return p in ("anthropic", "openai", "gemini") or (p == "other" and "openrouter.ai" in b)


def chat_web(conn, model, system, messages, timeout=240):
    """Like chat(), but the AI may search the web. Returns (answer text, [(title, url), ...] of the pages it used).
    Only the conversation is sent; the search runs at the AI service (Claude: web search tool; ChatGPT: Responses API web_search;
    Gemini: Google Search grounding; OpenRouter: the model with ':online')."""
    p = conn["provider"]; b = conn["base"]; src = []
    if not model: raise AIError("Choose a model first (the list 'Model').")
    if not web_capable(conn):
        raise AIError(f"{conn.get('name', p)} cannot search the web from this app. Switch 'Search the web' off, or choose Claude, ChatGPT, Gemini or OpenRouter.")
    if p == "anthropic":
        tool = {"type": "web_search_20260209" if NEW_WEB_TOOL.search(model) else "web_search_20250305", "name": "web_search", "max_uses": 5}
        msgs = _msgs("anthropic", messages); txt = ""
        for _ in range(4):                                     # a long search can pause; send it back to let it continue
            body = {"model": model, "max_tokens": 8000, "system": system, "messages": msgs, "tools": [tool]}
            try: j = _http("POST", b + "/v1/messages", _auth(conn), body, timeout)
            except AIError as e:
                if "code 400" in str(e) and tool["type"] == "web_search_20260209":
                    tool["type"] = "web_search_20250305"; continue  # an older model: the basic search tool
                raise
            content = j.get("content") or []
            for c in content:
                if not isinstance(c, dict): continue
                if c.get("type") == "text":
                    txt += c.get("text", "")
                    for ci in c.get("citations") or []:
                        if ci.get("url"): src.append((ci.get("title") or ci["url"], ci["url"]))
            if j.get("stop_reason") == "pause_turn":
                msgs = msgs + [{"role": "assistant", "content": content}]; txt = ""; continue
            if j.get("stop_reason") == "refusal" and not txt: raise AIError("The AI declined to answer this request.")
            break
    elif p == "openai":
        body = {"model": model, "instructions": system, "tools": [{"type": "web_search"}],
                "input": [{"role": m["role"], "content": _parts("openai", m["content"], "responses")} for m in messages]}
        j = _http("POST", b + "/responses", _auth(conn), body, timeout); txt = ""
        for o in j.get("output") or []:
            if isinstance(o, dict) and o.get("type") == "message":
                for c in o.get("content") or []:
                    if isinstance(c, dict) and c.get("type") == "output_text":
                        txt += c.get("text", "")
                        for an in c.get("annotations") or []:
                            if an.get("type") == "url_citation" and an.get("url"): src.append((an.get("title") or an["url"], an["url"]))
    elif p == "gemini":
        body = {"system_instruction": {"parts": [{"text": system}]}, "tools": [{"google_search": {}}],
                "contents": [{"role": "model" if m["role"] == "assistant" else "user", "parts": _parts("gemini", m["content"])} for m in messages]}
        j = _http("POST", f"{b}/models/{urllib.parse.quote(model, safe='')}:generateContent", _auth(conn), body, timeout)
        cand = (j.get("candidates") or [{}])[0]
        txt = "".join(pt.get("text", "") for pt in ((cand.get("content") or {}).get("parts") or []) if isinstance(pt, dict) and not pt.get("thought"))
        for ch in ((cand.get("groundingMetadata") or {}).get("groundingChunks") or []):
            w = ch.get("web") or {}
            if w.get("uri"): src.append((w.get("title") or w["uri"], w["uri"]))
    else:                                                      # OpenRouter: any model, with web results
        m_ = model if model.endswith(":online") else model + ":online"
        j = _http("POST", b + "/chat/completions", _auth(conn), {"model": m_, "messages": [{"role": "system", "content": system}] + _msgs("other", messages)}, timeout)
        msg = ((j.get("choices") or [{}])[0].get("message") or {}); c = msg.get("content")
        txt = c if isinstance(c, str) else "".join(pt.get("text", "") for pt in (c or []) if isinstance(pt, dict))
        for an in msg.get("annotations") or []:
            u = (an.get("url_citation") or {}) if isinstance(an, dict) else {}
            if u.get("url"): src.append((u.get("title") or u["url"], u["url"]))
    if not (txt or "").strip(): raise AIError("The AI gave an empty answer. Try again, or choose another model.")
    seen = set(); out = []
    for t_, u_ in src:
        if u_ not in seen: seen.add(u_); out.append((str(t_)[:120], u_))
    return txt, out[:12]


def parse_reply(text):
    """The AI answers with one JSON object {say, actions, done}. Models sometimes wrap it in words or a code fence; find it.
    An answer without JSON is taken as plain talk: nothing is done."""
    t = (text or "").strip(); cands = [t]
    cands += [m.group(1) for m in re.finditer(r"```(?:json)?\s*(\{.*?\})\s*```", t, flags=re.S)]
    i = t.find("{")
    while i != -1 and len(cands) < 12:                     # every balanced {...} that starts at a '{'
        depth = 0; ins = False; esc = False
        for j in range(i, len(t)):
            ch = t[j]
            if ins:
                if esc: esc = False
                elif ch == "\\": esc = True
                elif ch == '"': ins = False
            elif ch == '"': ins = True
            elif ch == "{": depth += 1
            elif ch == "}":
                depth -= 1
                if depth == 0: cands.append(t[i:j + 1]); break
        i = t.find("{", i + 1)
    for c in cands:
        try: j = json.loads(c)
        except Exception: continue
        if isinstance(j, dict) and ("say" in j or "actions" in j):
            acts = j.get("actions") or []
            if isinstance(acts, dict): acts = [acts]
            acts = [a for a in acts if isinstance(a, dict) and a.get("do")]
            return {"say": str(j.get("say") or "").strip(), "actions": acts, "done": bool(j.get("done", not acts))}
    return {"say": t, "actions": [], "done": True}


# ----------------------------------------------------------------------------- what the AI is told
ACTIONS_DOC = """
ACTIONS (the only things you can do). "graph" and "graphs" are the numbers n of the list in STATE.
  {"do": "look", "graph": n}                      more about one graph: its columns with their ranges, the strongest peaks, the labels on it, the graph suggestions for this table. Use it before you label or restyle.
  {"do": "add_files", "paths": ["C:\\\\...\\\\a.csv"]}     load data files the user named with their full path.   {"do": "add_files", "ask": true} opens the file chooser for the user.
  {"do": "read_file", "path": "C:\\...\\a.txt"}       show you the first 40 lines of a text or Excel file with their row numbers. For a file in "files_that_gave_no_graph", or one the app read wrongly.
  {"do": "convert", "path": "C:\\...\\a.txt", "delimiter": "auto|comma|semicolon|tab|space", "decimal": ".|,", "header_row": 5, "first_data_row": 6, "last_data_row": 0, "transpose": false, "sheet": "<Excel only>", "columns": [{"column": 1, "name": "Temperature", "unit": "°C"}, ...], "sample": "<sample name>", "kind": "<one of KINDS, optional>"}
        turn a table the app could not read into a clean workbook and load it. You only say WHERE the table is and what the columns are called; the app reads the numbers itself. Rows and columns are numbered from 1 as "read_file" shows them; last_data_row 0 = to the end; header_row 0 = no header row; "transpose": true when every ROW is one quantity (its name first, then its values). In "columns" keep only the columns worth drawing and give them clean names with units (the app recognises the measurement from names such as "2theta (deg)", "Intensity (counts)", "Temperature (°C)", "Mass (%)", "Wavenumber (cm-1)", "Particle size (µm)", "Time (h)", "Heat flow (mW/g)"). The app remembers the layout: the next file like it is read without you.
  {"do": "sample", "graphs": [n, ...], "name": "Sample A (4 % additive)"}     give graphs a sample name. Graphs with the same sample name are put together (pattern + fit + peak list).
  {"do": "kind", "graph": n, "kind": "<one of KINDS>"}              say what kind of measurement a table is, when the app got it wrong.
  {"do": "suggestion", "graph": n, "choose": k}   draw the table as suggestion number k from "look".
  {"do": "own", "graph": n, "x": "<column>", "ys": ["<column>", ...], "style": "<one of OWN_STYLES>", "xtitle": "", "ytitle": "", "xlog": false, "xrev": false, "layout": "<one of OWN_LAYOUTS>"}     draw any table your way. Leave out what should stay.
  {"do": "labels", "graph": n, "labels": [{"x": 29.4, "text": "A"}], "replace": false}     put peak labels on a graph. ONLY texts the user typed in this chat, or that are already in the user's files. replace=true removes the labels typed before. {"do": "labels", "graph": n, "labels": [], "replace": true} removes them.
  {"do": "setting", "name": "<name from SETTINGS>", "value": "<allowed value>"}     change a setting for all graphs.
  {"do": "tick", "graphs": [n, ...]}              tick graphs for drawing ("graphs": "all" or "none" also work).
  {"do": "figure", "graphs": [n, ...]}            put up to 9 graphs together in one figure at the exact width of a journal page.
  {"do": "folder", "path": "D:\\\\Paper2\\\\figures"}     where everything is saved.   {"do": "folder", "ask": true} opens the folder chooser.
  {"do": "workbook"}                              write all loaded graphs as one Excel workbook that Origin (and this app) opens: one clean sheet per table, plus sheets for samples, phases and peak labels. {"do": "workbook", "template": true} writes the empty template instead.
  {"do": "draw", "graphs": [n, ...]}              draw graphs in Origin and save the pictures and publication files in the folder ("graphs": "ticked" or "all" also work). Do this last.
  {"do": "show", "graph": n}                      show a graph in the preview.
  {"do": "paper_figures", "workbook": "C:\\\\...\\\\book.xlsx", "recipe": "<name from STATE figure_recipes>", "only": ["Fig A", "Fig C"]}     composed figures for a paper (several panels, label sheets, Rietveld fit + difference + tick rows + zoomed inset, grouped bars with hatch), written as PDF and PNG at 600 dpi by the app from the sheets of a workbook. Leave out "workbook" when STATE "workbooks" holds the one that is meant, "recipe" when "recipe_that_fits" names one, "only" to draw every figure. Use this, not "own" or "draw", when the user's instructions describe figures like "Fig A ... Fig G" from a workbook: the recipe already holds those instructions. The result lists the files and NOTES about sheets or columns that were missing or labels that were moved: tell the user those notes in plain words.
  {"do": "paper_figures", "workbook": "...", "spec": {<one figure>}}     the same for a figure no recipe holds (for example grouped bars by sample). SPEC: A figure = {"name","file","width_mm","height_mm","layout":{"rows":[ratios],"cols":[ratios],"sharex":false},"panels":[...],"legend":{"where":"below","rows":1}}. Panel "type":"xy": {"cell":[row,col],"letter":"(a)","title","xtitle","ytitle","xlim","ylim","xticks","xreverse","yfrom0","series":[{"sheet","x":column,"y":column or [columns] or "others","kind":"line|markers|line+markers","color":"#hex","lw","ls":"-|--|:","marker":"o|s|^|D","filled":true,"label","optional":false}]}. Panel "type":"bars" (one group of bars per row of the sheet): {"cell","sheet","category":column,"bars":[{"column","color","hatch":"/","label"}],"points":{"column","label"},"xtitle","ytitle","ylim"}. A column is its exact name, {"contains":"text"} or a position (0 = first, -1 = last). Never put numbers into a spec: the app reads them from the sheets.
  {"do": "remember", "text": "..."}               save a lasting rule the user stated ("always ...", "never ...", "from now on ...") or a correction they made, in one short sentence. It is given to you in every later chat.

HOW YOU ANSWER
Answer with ONE JSON object and nothing else:
  {"say": "<a short message for the user, plain words>", "actions": [<actions, in order>], "done": true}
- "done": false means: carry out these actions, then show me the results and the new STATE, I have more to do. Use it after "look" and "add_files", and whenever a later step depends on a result.
- "done": true means you are finished (or you only answer a question, with "actions": []).
- After each round you get RESULTS (one line per action) and the new STATE. Graph numbers can change after a round: read the new STATE.
- If something is unclear and a wrong guess would matter (which sample is which, which peak), ask in "say" with "actions": [] instead of guessing.
- Recommend: when the user asks what to draw, use "look" and tell them the suggestions in "say", with your pick first and one reason each.
- A file that gave no graph (STATE "files_that_gave_no_graph", or the user says a file does not open): "read_file" first, then "convert" with what you saw, then say what came out and recommend a graph. If the file is not a table of numbers, say so plainly.
- STATE "last_problem" is the last error of the app. When the user asks about it, say in plain words what it means and what they can do. If your actions cannot solve it, tell them to press 'Problem report…' and send that file to whoever looks after the app. You cannot change the program itself.
"""

BUILT_IN_RULES = """
RULES THAT ALWAYS HOLD
- You do not see the numbers of the tables, only what STATE, "look" and "read_file" give you. Never state a value you were not given. Never retype or invent numbers: "convert" makes the app read them from the file.
- Never invent a phase or peak assignment. A label text must be words the user typed in this chat, or already in their files. If the user asks "label the peaks" without saying with what, ask which phases, or point to the setting "xrd_labels".
- Never change measured or calculated data. You cannot, and you do not suggest ways around it.
- The user chooses the folder. If they named none and none is set in STATE, ask before drawing.
- Curve and axis line weights stay at 1.5 pt or more.
- Keep "say" short. No headings, no lists longer than five lines.
"""

DEFAULT_INSTRUCTIONS = """# My instructions for the assistant of the Origin plot app
# The assistant reads this file before every answer. Change it as you like: one rule per line, plain words.
# Lines that begin with # are notes for you; they are also sent, so keep them short.

Sample names are written like "Sample A (4 % additive)" and "Reference (0 % additive)".
Figures are in landscape format, in the style of a high-impact journal: clean, not crowded, the same fonts and colours everywhere.
The observed XRD pattern is drawn as a line.
TG and DTG go together in one graph. DTG is not inverted.
Peak labels come only from my own files or from what I type. Never guess a phase.
A profile fit is called "Rwp (profile fit)". It is never presented as a Rietveld refinement.
In TGA, Ca(OH)2 and CaCO3 are only assigned when I say the material is cementitious.
Before drawing, tell me in one line what will be drawn and where it will be saved.
"""


def home(sp_store_dir):
    """The folder for the assistant's files: next to your phase store, outside the app folder, so it stays when you unzip a new version."""
    d = os.path.dirname(os.path.abspath(sp_store_dir)); os.makedirs(d, exist_ok=True); return d

def instructions_file(h):
    p = os.path.join(h, "assistant_instructions.txt")
    if not os.path.exists(p):
        try:
            with open(p, "w", encoding="utf-8") as f: f.write(DEFAULT_INSTRUCTIONS)
        except Exception: pass
    return p

def lessons_file(h):
    p = os.path.join(h, "assistant_lessons.txt")
    if not os.path.exists(p):
        try:
            with open(p, "w", encoding="utf-8") as f: f.write("# What the assistant has learned from you. One rule per line. Delete a line to make it forget.\n")
        except Exception: pass
    return p

def read_text(p, limit=6000):
    try:
        with open(p, "r", encoding="utf-8", errors="replace") as f: return f.read()[:limit]
    except Exception: return ""

def learn(h, text):
    """Add one lasting rule to the lessons file (not twice). Returns the line as saved, or '' when it was already there."""
    t = re.sub(r"\s+", " ", str(text or "")).strip().strip("-• ")[:300]
    if not t: return ""
    p = lessons_file(h); old = read_text(p, 100000)
    if any(re.sub(r"^\d{4}-\d{2}-\d{2}:\s*", "", l).strip().lower() == t.lower() for l in old.splitlines()): return ""
    with open(p, "a", encoding="utf-8") as f: f.write(f"{datetime.date.today().isoformat()}: {t}\n")
    return t

# ----------------------------------------------------------------------------- where a key is kept
# ONE store for every credential of the app: secure_store.py (Windows data protection, the keyring of other systems, or - when
# neither exists - only the memory of this session). A key is NEVER written to disk as plain text. assistant.json holds, per AI,
# only a reference {"store": "ai:<provider>", "origin": "https://host:443"}: where the key is kept and which service it was
# entered for. Keys saved by earlier versions ({"dpapi": ...} blobs in assistant.json) are still read, and move into the store at
# the next save. A plain key left by an old version is moved into the store when the settings are read, and removed from the file.
def _dpapi(data, protect):
    """Windows data protection (DPAPI): encrypts with your Windows login. Only your Windows account on this computer can read it back."""
    import ctypes
    import ctypes.wintypes as wt
    class BLOB(ctypes.Structure): _fields_ = [("cbData", wt.DWORD), ("pbData", ctypes.POINTER(ctypes.c_char))]
    buf = ctypes.create_string_buffer(data, len(data)); bin_ = BLOB(len(data), ctypes.cast(buf, ctypes.POINTER(ctypes.c_char))); bout = BLOB()
    fn = ctypes.windll.crypt32.CryptProtectData if protect else ctypes.windll.crypt32.CryptUnprotectData
    fn.argtypes = [ctypes.POINTER(BLOB), ctypes.c_void_p, ctypes.c_void_p, ctypes.c_void_p, ctypes.c_void_p, wt.DWORD, ctypes.POINTER(BLOB)]; fn.restype = wt.BOOL
    if not fn(ctypes.byref(bin_), None, None, None, None, 0x1, ctypes.byref(bout)): raise OSError("Windows could not " + ("protect" if protect else "read") + " the key")
    try: return ctypes.string_at(bout.pbData, bout.cbData)
    finally:
        free = ctypes.windll.kernel32.LocalFree; free.argtypes = [ctypes.c_void_p]; free.restype = ctypes.c_void_p; free(ctypes.cast(bout.pbData, ctypes.c_void_p))

STORAGE_NOTES = []           # plain lines about keys that were moved or could not be kept; a window shows them once (storage_notes())

def storage_notes():
    """What happened to stored keys since the last call (moved into the protected store, kept for this session only ...)."""
    out = list(dict.fromkeys(STORAGE_NOTES)); del STORAGE_NOTES[:]
    return out

def store_name(provider): return "ai:" + str(provider)

def protect_key(key, *, name=None):
    """A key in the form that may be written to disk, or None when it cannot be kept safely (then NOTHING is written: there is
    no plain-text form). On Windows: encrypted by Windows ({"dpapi": ...}). With `name`: the key is put into the app's
    protected store under that name and a reference {"store": name} is returned when it is kept there beyond this session."""
    import base64
    key = str(key or "").strip()
    if not key: return None
    if name:
        try:
            import secure_store
            return {"store": str(name)} if secure_store.put(str(name), key) in ("dpapi", "keyring") else None
        except Exception: return None
    if os.name != "nt": return None                              # no Windows protection here, and no name to keep it under: not stored
    try:
        enc = _dpapi(key.encode("utf-8"), True)
        if _dpapi(enc, False).decode("utf-8") != key: return None          # read it back before trusting it
        return {"dpapi": base64.b64encode(enc).decode("ascii")}
    except Exception: return None

def reveal_key(v):
    """The key back from its stored form; '' when it cannot be read (another computer, another Windows account, or a key that
    was kept for one session only). A reference that carries the service the key was entered for binds the key to it.
    A plain value is only still read so that it can be moved into the protected store (load_settings does that)."""
    import base64
    key = ""
    try:
        if isinstance(v, str): key = v.strip()                # a key saved by version 5.14.0 or 5.14.1 (plain): moved into the store when the settings are read
        elif isinstance(v, dict) and v.get("store"):
            import secure_store
            key = secure_store.get(str(v["store"]))
        elif isinstance(v, dict) and v.get("dpapi"): key = _dpapi(base64.b64decode(v["dpapi"]), False).decode("utf-8").strip()
        elif isinstance(v, dict) and v.get("plain") and os.name != "nt": key = str(v["plain"]).strip()      # left by an older version outside Windows
    except Exception: key = ""
    if key and isinstance(v, dict) and v.get("origin") and _fp(key) not in _BOUND: _BOUND[_fp(key)] = str(v["origin"])
    return key

def _key_origin(provider, d):
    """The service a saved key of this provider belongs to: the address saved with it, or the provider's own address."""
    return origin_text(str((d.get("addresses") or {}).get(provider) or "").strip().rstrip("/") or PROVIDERS.get(provider, {}).get("base", ""))

def _write_settings(h, d):
    p = os.path.join(h, "assistant.json"); tmp = p + ".tmp"
    with open(tmp, "w", encoding="utf-8") as f: json.dump(d, f, indent=1)
    try: os.chmod(tmp, 0o600)
    except Exception: pass
    os.replace(tmp, p)

def load_settings(h):
    """The settings of the assistant. A plain key that an older version left in the file is moved into the protected store here
    and removed from the file (when this system has no protected store it is kept for this session only, and storage_notes()
    says so). Every entry of "keys" comes back with the service it belongs to ("origin")."""
    try:
        with open(os.path.join(h, "assistant.json"), "r", encoding="utf-8") as f: d = json.load(f)
    except Exception: return {}
    if not isinstance(d, dict): return {}
    keys = d.get("keys") if isinstance(d.get("keys"), dict) else {}
    plain = {pr: (v if isinstance(v, str) else v.get("plain")) for pr, v in keys.items() if isinstance(v, str) or (isinstance(v, dict) and "plain" in v)}
    old = str(d.get("key") or "").strip() if isinstance(d.get("key"), str) else ""          # the single key of version 5.14.0
    if old and whose_key(old) and whose_key(old) not in keys: plain[whose_key(old)] = old
    if plain or "key" in d:
        try:
            import secure_store
            for pr, k in plain.items():
                k = str(k or "").strip()
                if not k: keys.pop(pr, None); continue
                how, _ = secure_store.migrate_plain(store_name(pr), k)
                keys[pr] = {"store": store_name(pr), "origin": _key_origin(pr, d)}
                name = PROVIDERS.get(pr, {}).get("name", pr)
                STORAGE_NOTES.append(f"The key of {name} was kept as plain text by an older version. It was moved into the protected store of this system and removed from the settings file."
                                     if how in ("dpapi", "keyring") else
                                     f"The key of {name} was kept as plain text by an older version. This system has no protected store the app can use, so the key was removed from the settings file and is kept only until the app closes. Paste it again next time.")
            d["keys"] = keys; d.pop("key", None)
            _write_settings(h, d)                             # the plain copy is gone from the disk
        except Exception: pass
    for pr, v in list(keys.items()):                          # a key saved before services were recorded belongs to the address saved with it
        if isinstance(v, dict) and not v.get("origin"): keys[pr] = dict(v, origin=_key_origin(pr, d))
    if keys: d["keys"] = keys
    return d

def save_settings(h, d):
    """Write the settings. A key goes into the protected store (secure_store); the file gets a reference to it, never the key.
    Returns the names of the AIs whose key could not be kept beyond this session (no protected store on this system): it
    works until the app closes and is asked for again."""
    import secure_store
    d = dict(d); lost = []; keys = {}
    try:
        with open(os.path.join(h, "assistant.json"), "r", encoding="utf-8") as f: before = (json.load(f) or {}).get("keys") or {}
    except Exception: before = {}
    for pr, k in (d.get("keys") or {}).items():
        if isinstance(k, dict): k = reveal_key(k)
        k = str(k or "").strip()
        if not k: continue
        origin = _BOUND.get(_fp(k)) or _key_origin(pr, d)
        if _fp(k) not in _BOUND and origin: _BOUND[_fp(k)] = origin
        try: how = secure_store.put(store_name(pr), k)
        except Exception: how = ""
        if how: keys[pr] = {"store": store_name(pr), "origin": origin}
        if how not in ("dpapi", "keyring"): lost.append(pr)
    for pr, v in before.items():                              # a key that is no longer listed is forgotten everywhere
        if pr not in keys and isinstance(v, dict) and v.get("store") == store_name(pr):
            try:
                gone = secure_store.get(store_name(pr))
                if gone: unbind_key(gone)
                secure_store.delete(store_name(pr))
            except Exception: pass
    d["keys"] = keys; d.pop("key", None)
    try: _write_settings(h, d)
    except Exception: pass
    return lost

def system_prompt(version, instructions, lessons, lists):
    """Everything the AI is told about its job. `lists` holds the allowed words: KINDS, OWN_STYLES, OWN_LAYOUTS, SETTINGS."""
    return ("You are the assistant inside the 'Origin plot app' (version " + version + "), a Windows program that reads data files of materials science "
            "(XRD patterns and fits, peak lists, TGA, FTIR, calorimetry, particle size, thermodynamic modelling tables, any table), recognises what they are, "
            "previews graphs and draws them in Origin. The user types instructions; you turn them into the app's actions. The app does the work with its own code.\n"
            + BUILT_IN_RULES + ACTIONS_DOC
            + "\nKINDS: " + json.dumps(lists.get("KINDS", []), ensure_ascii=False)
            + "\nOWN_STYLES: " + json.dumps(lists.get("OWN_STYLES", []), ensure_ascii=False)
            + "\nOWN_LAYOUTS: " + json.dumps(lists.get("OWN_LAYOUTS", []), ensure_ascii=False)
            + "\nSETTINGS (name: allowed values; a name without a list takes a number or a text):\n" + "\n".join(f"  {k}: {json.dumps(v, ensure_ascii=False) if v else '(free)'}" for k, v in (lists.get("SETTINGS") or {}).items())
            + "\n\nTHE USER'S OWN INSTRUCTIONS (follow them unless they conflict with the rules above):\n" + (instructions.strip() or "(none)")
            + "\n\nWHAT YOU HAVE LEARNED FROM THIS USER BEFORE:\n" + (lessons.strip() or "(nothing yet)") + "\n")

def typed_by_user(text, user_texts):
    """Did the user type this label text? Whole text, or each of its parts ('A+B' -> A and B), as a word in what they typed."""
    said = " \n ".join(user_texts).lower(); t = str(text).strip().lower()
    if not t: return False
    def word(w): return bool(re.search(r"(?<![A-Za-z0-9])" + re.escape(w) + r"(?![A-Za-z0-9])", said))
    parts = [w for w in re.split(r"[+/,]| and ", t) if w.strip()]
    return word(t) or (len(parts) > 1 and all(word(w.strip(" ()?")) for w in parts))
