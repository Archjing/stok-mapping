from __future__ import annotations

import json
import os
from typing import Any

import httpx
from mcp.server.fastmcp import FastMCP


MODEL = os.getenv("DEEPSEEK_MODEL", "deepseek-v4-pro")
BASE_URL = os.getenv("DEEPSEEK_BASE_URL", "https://api.deepseek.com").rstrip("/")
API_KEY = os.getenv("DEEPSEEK_API_KEY", "")
TIMEOUT = float(os.getenv("DEEPSEEK_TIMEOUT", "120"))

mcp = FastMCP(
    name="deepseekAgentMcp",
    instructions=(
        "DeepSeek-backed research helper for stok-mapping. "
        "Use it for second opinions, report summarization, and strategy review. "
        "It must not generate direct trading instructions."
    ),
)


SYSTEM_GUARDRAIL = (
    "You are a research assistant for stok-mapping, an A-share quant research and pre-market analysis project. "
    "You may summarize, critique, compare, and explain. "
    "Do not output direct trading instructions such as buy, sell, full position, clear position, or stock recommendation language. "
    "Prefer concise Chinese output unless the caller explicitly requests otherwise."
)


class DeepSeekConfigError(RuntimeError):
    pass


def _require_config() -> None:
    if not API_KEY:
        raise DeepSeekConfigError("DEEPSEEK_API_KEY is not configured")


def _chat(messages: list[dict[str, Any]], *, temperature: float = 0.2, max_tokens: int = 2000) -> dict[str, Any]:
    _require_config()
    url = f"{BASE_URL}/chat/completions"
    payload = {
        "model": MODEL,
        "messages": messages,
        "temperature": temperature,
        "max_tokens": max_tokens,
        "response_format": {"type": "json_object"},
    }
    headers = {
        "Authorization": f"Bearer {API_KEY}",
        "Content-Type": "application/json",
    }
    with httpx.Client(timeout=TIMEOUT) as client:
        response = client.post(url, headers=headers, json=payload)
        response.raise_for_status()
        data = response.json()
    content = data["choices"][0]["message"]["content"]
    return json.loads(content)


@mcp.tool(name="deepseek_second_opinion", description="Get a second-opinion review on a report, candidate, or research note.")
def deepseek_second_opinion(context: str, question: str) -> dict[str, Any]:
    messages = [
        {"role": "system", "content": SYSTEM_GUARDRAIL},
        {
            "role": "user",
            "content": (
                "Review the following context and answer the question with a research-only second opinion. "
                "Return JSON with keys: summary, risks, contradictions, next_actions.\n\n"
                f"Question:\n{question}\n\n"
                f"Context:\n{context}"
            ),
        },
    ]
    return _chat(messages)


@mcp.tool(name="deepseek_report_summarize", description="Summarize a markdown report into structured Chinese JSON.")
def deepseek_report_summarize(report_text: str, focus: str = "summary, risk_flags, next_actions") -> dict[str, Any]:
    messages = [
        {"role": "system", "content": SYSTEM_GUARDRAIL},
        {
            "role": "user",
            "content": (
                "Summarize the following report for the stok-mapping project. "
                "Return JSON with keys: summary, key_metrics, risk_flags, next_actions. "
                f"Focus on: {focus}.\n\n"
                f"Report:\n{report_text}"
            ),
        },
    ]
    return _chat(messages)


@mcp.tool(name="deepseek_strategy_review", description="Review a strategy candidate and return a structured critique.")
def deepseek_strategy_review(candidate_name: str, metrics: dict[str, Any], logic: str, constraints: str = "research only") -> dict[str, Any]:
    messages = [
        {"role": "system", "content": SYSTEM_GUARDRAIL},
        {
            "role": "user",
            "content": (
                "Review this strategy candidate for stok-mapping. "
                "Return JSON with keys: candidate, summary, strengths, weaknesses, gate_risks, next_actions.\n\n"
                f"Candidate: {candidate_name}\n"
                f"Metrics: {json.dumps(metrics, ensure_ascii=False)}\n"
                f"Logic: {logic}\n"
                f"Constraints: {constraints}"
            ),
        },
    ]
    return _chat(messages)


@mcp.tool(name="deepseek_signal_explain", description="Explain a watchlist symbol or signal in research language.")
def deepseek_signal_explain(symbol: str, context: str) -> dict[str, Any]:
    messages = [
        {"role": "system", "content": SYSTEM_GUARDRAIL},
        {
            "role": "user",
            "content": (
                "Explain the following symbol context for a pre-market research note. "
                "Return JSON with keys: symbol, summary, risk_flags, invalid_conditions, note.\n\n"
                f"Symbol: {symbol}\n"
                f"Context: {context}"
            ),
        },
    ]
    return _chat(messages)


if __name__ == "__main__":
    mcp.run()
