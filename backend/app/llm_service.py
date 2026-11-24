import litellm
from typing import List, Dict, Optional, Tuple
from app.config import settings
import time
import logging

logger = logging.getLogger(__name__)

# Configure LiteLLM
litellm.cache = litellm.Cache() if settings.cache_enabled else None
litellm.set_verbose = False


class LLMRouter:
    def __init__(self):
        self.keys = settings.api_keys_list
        self.cache_enabled = settings.cache_enabled

    def _build_model_list(self) -> List[Dict]:
        """Build LiteLLM router model list with all keys."""
        model_list = []
        for idx, key in enumerate(self.keys, 1):
            # Detect provider from key format
            model_name = self._detect_model_from_key(key)
            model_list.append({
                "model_name": model_name,
                "litellm_params": {
                    "model": model_name,
                    "api_key": key,
                },
                "model_info": {
                    "id": f"key_{idx}"
                }
            })
        return model_list

    def _detect_model_from_key(self, key: str) -> str:
        """Detect model provider from API key prefix."""
        if key.startswith("sk-"):
            return "gpt-4o-mini"
        if key.startswith("gsk_"):
            return "groq/openai/gpt-oss-20b"
        if settings.llm_model in ["gemini/gemini-2.0-flash", "gemini/gemini-1.5-flash", "gemini-1.5-flash", "gemini-2.0-flash", "gemini/gemini-3-flash-preview"]:
            return "gemini/gemini-3.5-flash-lite"
        return settings.llm_model

    async def chat_completion(
        self,
        messages: List[Dict[str, str]],
        simulate_failures: Optional[Dict[str, int]] = None
    ) -> Tuple[str, Dict]:
        """
        Send chat completion with automatic failover.

        Returns:
            Tuple of (reply_text, metadata)
        """
        start_time = time.time()
        fallback_attempts = 0
        last_error = None

        # Try each key in order
        for idx, key in enumerate(self.keys, 1):
            key_id = f"key_{idx}"

            # Check if we should simulate failure for this key
            if simulate_failures and settings.enable_failure_simulation:
                if "*" in simulate_failures:
                    simulated_status = simulate_failures["*"]
                    logger.info(f"Simulating failure for {key_id}: {simulated_status}")
                    fallback_attempts += 1
                    continue
                elif key_id in simulate_failures:
                    simulated_status = simulate_failures[key_id]
                    logger.info(f"Simulating failure for {key_id}: {simulated_status}")
                    fallback_attempts += 1
                    continue

            # Candidate models for this key (primary detected, then stable fallbacks)
            primary_model = self._detect_model_from_key(key)
            models_to_try = [primary_model]
            if key.startswith("gsk_"):
                for fallback_m in ["groq/openai/gpt-oss-20b", "groq/openai/gpt-oss-120b"]:
                    if fallback_m not in models_to_try:
                        models_to_try.append(fallback_m)
            elif not key.startswith("sk-"):
                for fallback_m in ["gemini/gemini-3.5-flash-lite", "gemini/gemini-flash-lite-latest"]:
                    if fallback_m not in models_to_try:
                        models_to_try.append(fallback_m)

            model_succeeded = False
            for model_name in models_to_try:
                try:
                    # Make the call
                    response = await litellm.acompletion(
                        model=model_name,
                        messages=messages,
                        api_key=key,
                        caching=self.cache_enabled,
                        timeout=15,
                        num_retries=0
                    )

                    # Calculate latency
                    latency_ms = int((time.time() - start_time) * 1000)

                    # Extract reply
                    reply = response.choices[0].message.content

                    # Check if from cache
                    cache_hit = hasattr(response, '_hidden_params') and \
                               response._hidden_params.get('cache_hit', False)

                    resolution_source = "LLM_CACHE" if cache_hit else "LIVE_INFERENCE"

                    # Build metadata
                    metadata = {
                        "resolution_source": resolution_source,
                        "model": model_name,
                        "latency_ms": latency_ms,
                        "input_tokens": response.usage.prompt_tokens,
                        "output_tokens": response.usage.completion_tokens,
                        "key_id": None if cache_hit else key_id,
                        "fallback_attempts": fallback_attempts if not cache_hit else 0
                    }

                    return reply, metadata

                except Exception as e:
                    logger.warning(f"Key {key_id} model {model_name} failed: {e}")
                    last_error = e
                    continue

            # All candidate models failed for this key
            fallback_attempts += 1

        # All keys failed
        raise Exception(f"all providers unavailable ({last_error})")


llm_router = LLMRouter()
