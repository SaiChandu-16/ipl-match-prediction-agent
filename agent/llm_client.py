"""
agent/llm_client.py
--------------------
Free LLM client with automatic fallback.
Primary:  Groq (Llama 3.3 70B) — 14,400 free req/day, tool calling supported
Fallback: Google Gemini 2.0 Flash — 1500 free req/day, tool calling supported

Sign up:
  Groq  → console.groq.com  → API Keys (free, no card needed)
  Gemini → aistudio.google.com → Get API Key (free, no card needed)
"""

import os
import json
import logging
from typing import Optional

logger = logging.getLogger(__name__)

GROQ_API_KEY   = os.getenv("GROQ_API_KEY", "")
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY", "")


def _call_groq(messages: list, tools: list, system: str) -> dict:
    """Call Groq API (Llama 3.3 70B) with tool support."""
    import requests

    headers = {
        "Authorization": f"Bearer {GROQ_API_KEY}",
        "Content-Type": "application/json",
    }

    # Prepend system as first message for Groq
    all_messages = [{"role": "system", "content": system}] + messages

    payload = {
        "model": "llama-3.3-70b-versatile",
        "messages": all_messages,
        "tools": tools,
        "tool_choice": "auto",
        "max_tokens": 4096,
        "temperature": 0.3,
    }

    resp = requests.post(
        "https://api.groq.com/openai/v1/chat/completions",
        headers=headers,
        json=payload,
        timeout=60,
    )
    resp.raise_for_status()
    return resp.json()


def _call_gemini(messages: list, tools: list, system: str) -> dict:
    """Call Google Gemini 2.0 Flash API with tool support."""
    import requests

    # Convert OpenAI-style messages to Gemini format
    gemini_contents = []
    for m in messages:
        role = "user" if m["role"] == "user" else "model"
        content = m.get("content", "")

        if isinstance(content, list):
            # Handle tool results
            parts = []
            for item in content:
                if item.get("type") == "tool_result":
                    parts.append({"functionResponse": {
                        "name": item.get("tool_use_id", "tool"),
                        "response": {"content": item.get("content", "")}
                    }})
                elif item.get("type") == "text":
                    parts.append({"text": item["text"]})
            gemini_contents.append({"role": role, "parts": parts})
        else:
            gemini_contents.append({"role": role, "parts": [{"text": str(content)}]})

    # Convert tools to Gemini function declarations
    gemini_tools = []
    for t in tools:
        gemini_tools.append({
            "name": t["name"],
            "description": t["description"],
            "parameters": t["input_schema"],
        })

    payload = {
        "system_instruction": {"parts": [{"text": system}]},
        "contents": gemini_contents,
        "tools": [{"function_declarations": gemini_tools}],
        "generationConfig": {"temperature": 0.3, "maxOutputTokens": 4096},
    }

    resp = requests.post(
        f"https://generativelanguage.googleapis.com/v1beta/models/"
        f"gemini-2.0-flash:generateContent?key={GEMINI_API_KEY}",
        json=payload,
        timeout=60,
    )
    resp.raise_for_status()

    # Normalise Gemini response to OpenAI format
    gemini_resp = resp.json()
    candidate = gemini_resp["candidates"][0]["content"]
    parts = candidate.get("parts", [])

    tool_calls = []
    text_content = ""
    for part in parts:
        if "functionCall" in part:
            fc = part["functionCall"]
            tool_calls.append({
                "id": f"tc_{fc['name']}",
                "type": "function",
                "function": {
                    "name": fc["name"],
                    "arguments": json.dumps(fc.get("args", {})),
                },
            })
        elif "text" in part:
            text_content += part["text"]

    normalized = {
        "choices": [{
            "message": {
                "role": "assistant",
                "content": text_content or None,
                "tool_calls": tool_calls if tool_calls else None,
            },
            "finish_reason": "tool_calls" if tool_calls else "stop",
        }]
    }
    return normalized


def chat_with_tools(
    messages: list,
    tools: list,
    system: str,
    provider: str = "auto",
) -> dict:
    """
    Call the free LLM with tool support.
    Returns OpenAI-compatible response dict.

    provider: "groq" | "gemini" | "auto" (tries groq first, falls back to gemini)
    """
    if provider == "groq" or (provider == "auto" and GROQ_API_KEY):
        try:
            logger.info("Using Groq (Llama 3.3 70B)")
            return _call_groq(messages, tools, system)
        except Exception as e:
            logger.warning(f"Groq failed: {e}")
            if provider == "groq":
                raise

    if GEMINI_API_KEY:
        try:
            logger.info("Using Google Gemini 2.0 Flash")
            return _call_gemini(messages, tools, system)
        except Exception as e:
            logger.error(f"Gemini also failed: {e}")
            raise

    raise RuntimeError(
        "No LLM API key found. Set GROQ_API_KEY (free at console.groq.com) "
        "or GEMINI_API_KEY (free at aistudio.google.com)"
    )


def extract_tool_calls(response: dict) -> list:
    """Extract tool calls from an OpenAI-compatible response."""
    msg = response["choices"][0]["message"]
    return msg.get("tool_calls") or []


def extract_text(response: dict) -> str:
    """Extract text content from an OpenAI-compatible response."""
    msg = response["choices"][0]["message"]
    return msg.get("content") or ""


def is_done(response: dict) -> bool:
    """True if the model is done (no more tool calls)."""
    return not extract_tool_calls(response)
