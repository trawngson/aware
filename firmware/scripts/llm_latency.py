"""Time LLM mode from the Mac: the request the board sends in "mode llm"
(include/llm_prompt.h, the model in include/config.h), over TLS 1.2 on one
kept-open connection, straight to the ChatGPT Codex backend.

It signs in with the Mac's own Codex login (~/.codex/auth.json, or
$CODEX_HOME/auth.json) and only reads it: if the token has expired, run any
codex command once to refresh it.

usage (from firmware/):
  python3 scripts/llm_latency.py sim/photos/*.jpg
  python3 scripts/llm_latency.py --rounds 3 --model gpt-6-luna sim/photos/0*.jpg
Each photo is sent as it is, the way the board sends its camera's JPEG.
sim/photos/sources.json, when there, gives the stream each photo should go to.
"""

import argparse
import base64
import http.client
import json
import os
import re
import socket
import ssl
import statistics
import sys
import time
import uuid
from pathlib import Path

FIRMWARE = Path(__file__).resolve().parent.parent
HOST = "chatgpt.com"
PATH = "/backend-api/codex/responses"
# routing-v1 (include/routing.h): class -> stream
STREAMS = {
    "paper": "paper",
    "plastic_bottle": "plastic_bottles",
    "paper_cup": "other",
    "plastic_container": "other",
    "plastic_cutlery": "other",
    "tissue": "other",
    "food_wrapper": "other",
}


def header_value(pattern, path, flags=0):
    match = re.search(pattern, path.read_text(), flags)
    if not match:
        sys.exit(f"Could not find {pattern!r} in {path}")
    return match.group(1)


def route(labels):
    if not labels:
        return "other"
    streams = {STREAMS.get(label, "unknown") for label in labels}
    return streams.pop() if len(streams) == 1 and "unknown" not in streams else "other"


def codex_login():
    home = Path(os.environ.get("CODEX_HOME", Path.home() / ".codex"))
    try:
        tokens = json.loads((home / "auth.json").read_text())["tokens"]
        return tokens["access_token"], tokens.get("account_id") or ""
    except (OSError, KeyError, TypeError, ValueError):
        sys.exit(f"No ChatGPT sign-in in {home}/auth.json: run `codex login` first.")


class Link:
    """One kept-open HTTPS connection with the board's TLS version and send buffer."""

    def __init__(self):
        self.conn = None

    def open(self):
        context = ssl.create_default_context()
        context.maximum_version = ssl.TLSVersion.TLSv1_2
        self.conn = http.client.HTTPSConnection(HOST, context=context, timeout=60)
        t0 = time.perf_counter()
        self.conn.connect()
        self.conn.sock.setsockopt(socket.SOL_SOCKET, socket.SO_SNDBUF, 65534)
        self.conn.sock.setsockopt(socket.IPPROTO_TCP, socket.TCP_NODELAY, 1)
        return time.perf_counter() - t0

    def post(self, body, headers):
        connect = self.open() if self.conn is None else 0.0
        t0 = time.perf_counter()
        self.conn.request("POST", PATH, body=body, headers=headers)
        reply = self.conn.getresponse()
        first = time.perf_counter() - t0
        result = {"connect": connect, "first": first, "status": reply.status}
        if reply.status != 200:
            result["error"] = reply.read()[:300].decode(errors="replace")
            return result
        for line in iter(reply.readline, b""):
            if not line.startswith(b"data:"):
                continue
            event = json.loads(line[5:])
            kind = event.get("type", "")
            if kind == "response.output_text.done":
                result["answer"] = time.perf_counter() - t0
                result["text"] = event.get("text", "")
            elif kind in ("response.failed", "response.incomplete", "error"):
                result["error"] = json.dumps(event)[:300]
            if kind in ("response.completed", "response.failed", "response.incomplete", "error"):
                reply.read()
                break
        result["done"] = time.perf_counter() - t0
        if reply.will_close:
            self.conn.close()
            self.conn = None
        return result


def main():
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("photos", nargs="+", type=Path)
    parser.add_argument("--model", help="model slug (default: LLM_DEFAULT_MODEL in include/config.h)")
    parser.add_argument("--rounds", type=int, default=1, help="send every photo this many times")
    parser.add_argument("--effort", help="reasoning effort: none, low, ... (default: LLM_REASONING_EFFORT in include/config.h)")
    parser.add_argument("--detail", help="image detail: low, high or auto (default: LLM_IMAGE_DETAIL in include/config.h)")
    args = parser.parse_args()

    prompt_h = FIRMWARE / "include/llm_prompt.h"
    config_h = FIRMWARE / "include/config.h"
    instructions = header_value(r'LLM_INSTRUCTIONS\[\] = R"\((.*?)\)";', prompt_h, re.S)
    schema = json.loads(header_value(r'LLM_SCHEMA\[\] = R"\((.*?)\)";', prompt_h, re.S))
    model = args.model or header_value(r'#define LLM_DEFAULT_MODEL "([^"]+)"', config_h)
    effort = args.effort or header_value(r'#define LLM_REASONING_EFFORT "([^"]+)"', config_h)
    detail = args.detail or header_value(r'#define LLM_IMAGE_DETAIL "([^"]+)"', config_h)
    version = header_value(r'#define FIRMWARE_VERSION "([^"]+)"', config_h)
    expected = {}
    sources = FIRMWARE / "sim/photos/sources.json"
    if sources.exists():
        expected = {item["photo"]: item.get("expected_stream") for item in json.loads(sources.read_text())}

    token, account = codex_login()
    headers = {
        "Authorization": f"Bearer {token}",
        "Content-Type": "application/json",
        "Accept": "text/event-stream",
        "User-Agent": f"aware-bin/{version}",
        "originator": "aware_bin",
        "session-id": str(uuid.uuid4()),
    }
    if account:
        headers["ChatGPT-Account-ID"] = account

    print(f"{model}, reasoning {effort}, image detail {detail}, TLS 1.2, one kept-open connection to {HOST}")
    link = Link()
    answers, wrong, failed = [], 0, 0
    for _ in range(args.rounds):
        for path in args.photos:
            jpeg = path.read_bytes()
            body = {
                "model": model,
                "instructions": instructions,
                "store": False,
                "stream": True,
                "reasoning": {"effort": effort},
                "text": {"format": {"type": "json_schema", "name": "bin_items", "strict": True, "schema": schema}},
                "input": [{"type": "message", "role": "user", "content": [{
                    "type": "input_image", "detail": detail,
                    "image_url": "data:image/jpeg;base64," + base64.b64encode(jpeg).decode()}]}],
            }
            try:
                r = link.post(json.dumps(body).encode(), headers)
            except (OSError, http.client.HTTPException) as error:
                link.conn = None
                r = {"status": 0, "connect": 0, "first": 0, "error": repr(error)}
            name = path.name
            if r["status"] == 401:
                sys.exit("ChatGPT refused the Mac's Codex token (401): run any codex command once to refresh it.")
            if "answer" not in r:
                failed += 1
                print(f"{name:28s} {len(jpeg) // 1024:3d} KB  [{r['status']}] {r.get('error', 'no answer')}")
                continue
            labels = [item["label"] for item in json.loads(r["text"])["items"]]
            stream = route(labels)
            want = (expected.get(name) or "").split(" ")[0] or None  # "other (mixed)" -> "other"
            mark = "" if want is None else ("ok" if want == stream else f"WRONG, expected {want}")
            wrong += bool(want and want != stream)
            answers.append(r["answer"])
            connect = f"connect {r['connect'] * 1000:4.0f}  " if r["connect"] else ""
            print(f"{name:28s} {len(jpeg) // 1024:3d} KB  {connect}first byte {r['first'] * 1000:5.0f}  "
                  f"answer {r['answer'] * 1000:5.0f} ms  {','.join(labels) or 'nothing'} -> {stream}  {mark}")
    if answers:
        answers.sort()
        print(f"\n{len(answers)} answered, {failed} failed, {wrong} routed wrong | answer median "
              f"{statistics.median(answers) * 1000:.0f} ms, slowest {answers[-1] * 1000:.0f} ms")
    sys.exit(1 if failed or wrong else 0)


if __name__ == "__main__":
    main()
