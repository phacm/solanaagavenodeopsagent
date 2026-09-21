"""Gemini API binding for the native loop: official `google-genai` SDK, base URL = model
broker, automatic function calling disabled (the loop executes calls itself against the
stubs). Package and version pinned under D7; verified in W1-G [U]."""
from __future__ import annotations

import copy

from google import genai
from google.genai import types

PLACEHOLDER = "placeholder-not-a-secret"
_UNSUPPORTED = ("additionalProperties", "pattern", "minLength", "maxLength")


def _clean(schema: dict) -> dict:
    """Gemini function declarations accept an OpenAPI subset; drop keys it rejects. The
    brokers still validate the full schema, so nothing is weakened."""
    s = copy.deepcopy(schema)

    def walk(n):
        if isinstance(n, dict):
            for k in _UNSUPPORTED:
                n.pop(k, None)
            for v in n.values():
                walk(v)
        elif isinstance(n, list):
            for v in n:
                walk(v)
    walk(s)
    return s


class GeminiBinding:
    def __init__(self, base_url: str, model: str):
        self.client = genai.Client(api_key=PLACEHOLDER, http_options=types.HttpOptions(base_url=base_url))
        self.model = model

    def start(self, system: str, user: str, tools: list[dict]) -> None:
        decls = [types.FunctionDeclaration(name=t["name"], description=t["description"],
                                           parameters=_clean(t["input_schema"])) for t in tools]
        self.config = types.GenerateContentConfig(
            system_instruction=system, tools=[types.Tool(function_declarations=decls)],
            automatic_function_calling=types.AutomaticFunctionCallingConfig(disable=True))
        self.contents: list = [types.Content(role="user", parts=[types.Part(text=user)])]

    def step(self) -> list[tuple[str, str, dict]]:
        resp = self.client.models.generate_content(model=self.model, contents=self.contents, config=self.config)
        if not resp.candidates:
            return []
        self.contents.append(resp.candidates[0].content)
        return [(fc.id or fc.name, fc.name, dict(fc.args or {})) for fc in (resp.function_calls or [])]

    def add_results(self, results: list[tuple[str, str, str, bool]]) -> None:
        self.contents.append(types.Content(role="user", parts=[
            types.Part.from_function_response(name=name, response={"result": text}) for _, name, text, _ in results]))
