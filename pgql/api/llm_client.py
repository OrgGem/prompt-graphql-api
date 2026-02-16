# pgql/api/llm_client.py
"""OpenAI-compatible LLM client for direct chat."""

import json
import logging
import requests
from typing import Optional, List, Dict

logger = logging.getLogger("pgql_llm_client")


class LLMClient:
    """Client for OpenAI-compatible LLM APIs (OpenAI, Ollama, LM Studio, vLLM, etc.)."""

    def __init__(
        self,
        api_key: str,
        base_url: str,
        model: str = "gpt-3.5-turbo",
        temperature: float = 0.7,
        max_tokens: int = 4096,
    ):
        self.api_key = api_key
        self.base_url = base_url.rstrip("/")
        self.model = model
        self.temperature = temperature
        self.max_tokens = max_tokens

    def chat(
        self,
        message: str,
        system_instructions: Optional[str] = None,
        history: Optional[List[Dict]] = None,
    ) -> dict:
        """Send a chat completion request.

        Args:
            message: User message text
            system_instructions: Optional system prompt
            history: Optional prior messages [{"role": "...", "content": "..."}]

        Returns:
            Dict with success, content, model, usage info
        """
        messages = []

        if system_instructions:
            messages.append({"role": "system", "content": system_instructions})

        if history:
            messages.extend(history)

        messages.append({"role": "user", "content": message})

        url = f"{self.base_url}/chat/completions" if self.base_url.rstrip("/").endswith("/v1") else f"{self.base_url}/v1/chat/completions"
        headers = {
            "Content-Type": "application/json",
        }
        if self.api_key:
            headers["Authorization"] = f"Bearer {self.api_key}"

        payload = {
            "model": self.model,
            "messages": messages,
            "temperature": self.temperature,
            "max_tokens": self.max_tokens,
        }

        try:
            logger.info(f"LLM request to {url} model={self.model}")
            resp = requests.post(url, headers=headers, json=payload, timeout=120)

            if resp.status_code != 200:
                error_detail = ""
                try:
                    error_detail = resp.json().get("error", {}).get("message", resp.text[:300])
                except (ValueError, KeyError):
                    error_detail = resp.text[:300]
                return {
                    "success": False,
                    "error": f"LLM API error ({resp.status_code}): {error_detail}",
                }

            data = resp.json()
            choice = data.get("choices", [{}])[0]
            content = choice.get("message", {}).get("content", "")
            usage = data.get("usage", {})

            return {
                "success": True,
                "content": content,
                "model": data.get("model", self.model),
                "usage": {
                    "prompt_tokens": usage.get("prompt_tokens", 0),
                    "completion_tokens": usage.get("completion_tokens", 0),
                    "total_tokens": usage.get("total_tokens", 0),
                },
                "finish_reason": choice.get("finish_reason", ""),
            }

        except requests.exceptions.Timeout:
            return {"success": False, "error": "LLM request timed out (120s)"}
        except requests.exceptions.ConnectionError as e:
            return {"success": False, "error": f"Cannot connect to LLM API at {self.base_url}: {e}"}
        except json.JSONDecodeError as e:
            logger.error(f"LLM response parse error: {e}")
            return {"success": False, "error": f"Failed to parse LLM response: {e}"}
        except Exception as e:
            logger.error(f"LLM client unexpected error: {e}", exc_info=True)
            return {"success": False, "error": f"LLM error: {str(e)}"}
