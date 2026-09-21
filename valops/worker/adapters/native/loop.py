"""Native API adapter (HLD §6.5, plan §5.12.3, W23): the project's own minimal tool-calling
loop. No built-in tools exist; the model is offered ONLY the role's `valops` tools. Runs
inside the worker sandbox (untrusted: it parses model output). Every provider client is
pointed at the model-broker loopback with a placeholder credential (PC-4).

Loop: send system prompt + episode view + tool schemas; execute returned tool calls
against the stubs; return results; stop when the model stops calling tools or after
P-05 iterations. The artefact is whatever the tools wrote to the store -- the final text
is never parsed for one (§5.8).
"""
from __future__ import annotations

import sys
from typing import Protocol

from ...tools.stubs import ToolStubs, user_message


class Binding(Protocol):
    def start(self, system: str, user: str, tools: list[dict]) -> None: ...
    def step(self) -> list[tuple[str, str, dict]]: ...          # -> [(call_id, name, args)]
    def add_results(self, results: list[tuple[str, str, str, bool]]) -> None: ...  # (call_id, name, text, is_error)


def run(binding: Binding, spec: dict, system_prompt: str, stubs: ToolStubs) -> None:
    binding.start(system_prompt, user_message(spec), stubs.schemas())
    for _i in range(int(spec["max_turns"])):
        calls = binding.step()
        if not calls:
            return
        results = []
        for call_id, name, args in calls:
            if name not in stubs.allowed:
                res = {"error": "forbidden", "message": f"{name} is not available to this role"}
            else:
                res = stubs.call(name, args if isinstance(args, dict) else {})
            results.append((call_id, name, ToolStubs.render(res), "error" in res))
        binding.add_results(results)
    print(f"native loop: stopped at max_turns={spec['max_turns']}", file=sys.stderr)


def binding_for(provider: str, spec: dict) -> Binding:
    base = f"http://127.0.0.1:{spec['model_port']}"
    model = spec["configuration"]["model"]
    if provider == "anthropic":
        from .anthropic import AnthropicBinding
        return AnthropicBinding(base + "/anthropic", model)
    if provider == "openai":
        from .openai import OpenAIBinding
        return OpenAIBinding(base + "/openai/v1", model)
    if provider == "google":
        from .gemini import GeminiBinding
        return GeminiBinding(base + "/google", model)
    raise ValueError(f"unknown provider {provider}")
