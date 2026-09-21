"""OpenAI binding for the native loop: official `openai` SDK (Chat Completions), base URL =
model broker. Package and version pinned under D7; verified in W1-O [U]."""
from __future__ import annotations

import json

from openai import OpenAI

PLACEHOLDER = "placeholder-not-a-secret"


class OpenAIBinding:
    def __init__(self, base_url: str, model: str):
        self.client = OpenAI(api_key=PLACEHOLDER, base_url=base_url, max_retries=0)
        self.model = model

    def start(self, system: str, user: str, tools: list[dict]) -> None:
        self.tools = [{"type": "function", "function": {"name": t["name"], "description": t["description"],
                                                        "parameters": t["input_schema"]}} for t in tools]
        self.messages: list[dict] = [{"role": "system", "content": system}, {"role": "user", "content": user}]

    def step(self) -> list[tuple[str, str, dict]]:
        resp = self.client.chat.completions.create(model=self.model, messages=self.messages, tools=self.tools)
        msg = resp.choices[0].message
        self.messages.append(msg.model_dump(exclude_none=True))
        out = []
        for tc in msg.tool_calls or []:
            try:
                args = json.loads(tc.function.arguments or "{}")
            except ValueError:
                args = {"__invalid_json__": True}
            out.append((tc.id, tc.function.name, args))
        return out

    def add_results(self, results: list[tuple[str, str, str, bool]]) -> None:
        for cid, _, text, _err in results:
            self.messages.append({"role": "tool", "tool_call_id": cid, "content": text})
