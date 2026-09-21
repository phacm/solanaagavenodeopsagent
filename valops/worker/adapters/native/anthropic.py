"""Anthropic binding for the native loop: official `anthropic` SDK, base URL = model broker.

Server-side refusal fallbacks are deliberately NOT enabled: they would let a different
model answer, which the broker's pinned-model rule (D7, MB step 3) forbids and which
would pool results across configurations (plan §8.1). A refusal ends the loop; the step
then fails artefact validation and is retried or handed off.
"""
from __future__ import annotations

import sys

import anthropic

PLACEHOLDER = "placeholder-not-a-secret"  # the broker strips it and injects the real key


class AnthropicBinding:
    def __init__(self, base_url: str, model: str):
        self.client = anthropic.Anthropic(api_key=PLACEHOLDER, base_url=base_url, max_retries=0)
        self.model = model

    def start(self, system: str, user: str, tools: list[dict]) -> None:
        self.system = system
        self.tools = [{"name": t["name"], "description": t["description"], "input_schema": t["input_schema"]} for t in tools]
        self.messages: list[dict] = [{"role": "user", "content": user}]

    def step(self) -> list[tuple[str, str, dict]]:
        resp = self.client.messages.create(
            model=self.model, max_tokens=16000, system=self.system, tools=self.tools, messages=self.messages,
            thinking={"type": "adaptive"},
        )
        # Append the full content (incl. thinking blocks) unchanged; the history is append-only.
        self.messages.append({"role": "assistant", "content": resp.content})
        if resp.stop_reason == "refusal":
            print(f"anthropic: refusal ({getattr(resp.stop_details, 'category', None)})", file=sys.stderr)
            return []
        if resp.stop_reason != "tool_use":
            return []
        return [(b.id, b.name, b.input) for b in resp.content if b.type == "tool_use"]

    def add_results(self, results: list[tuple[str, str, str, bool]]) -> None:
        # All tool_result blocks for one assistant turn go back in a single user message.
        self.messages.append({"role": "user", "content": [
            {"type": "tool_result", "tool_use_id": cid, "content": text, "is_error": err} for cid, _, text, err in results]})
