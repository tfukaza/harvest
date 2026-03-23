"""LLM error classification for the agent retry loop.

Each LLM provider returns errors in different formats. This module centralises
the detection logic so that changes to provider error messages or new providers
only require edits here, not in the agent lifecycle code.

Error categories
----------------
UNRECOVERABLE
    The error will not resolve by retrying. The agent should shut down cleanly.
    Examples: insufficient credits, invalid API key, model not found.

RETRYABLE
    The error is transient and the agent should back off and retry.
    Examples: rate limit exceeded, temporary server overload.

UNKNOWN
    Unclassified. The caller decides what to do (typically crash after exhausting
    retries).
"""

from __future__ import annotations

from enum import Enum, auto


class LLMErrorKind(Enum):
    UNRECOVERABLE = auto()
    RETRYABLE = auto()
    UNKNOWN = auto()


def classify_llm_error(exc: Exception) -> LLMErrorKind:
    """Classify an exception raised by the LLM completion call.

    Checks both the exception type name and the string representation so that
    this works whether or not litellm is installed (unit tests may mock the
    completion function).

    Args:
        exc: The exception to classify.

    Returns:
        :class:`LLMErrorKind` indicating how the caller should respond.
    """
    exc_name = type(exc).__name__
    exc_str = str(exc)

    # ------------------------------------------------------------------
    # UNRECOVERABLE — these will not resolve with retries
    # ------------------------------------------------------------------

    # Billing / quota exhausted
    # Anthropic:   "Your credit balance is too low to access the Anthropic API"
    # OpenAI:      "You exceeded your current quota"
    # Gemini:      "Quota exceeded for quota metric"
    # OpenRouter:  "insufficient_credits"
    if any(phrase in exc_str for phrase in (
        "credit balance is too low",
        "exceeded your current quota",
        "Quota exceeded for quota metric",
        "billing_hard_limit_reached",
        "insufficient_quota",
        "insufficient_credits",
    )):
        return LLMErrorKind.UNRECOVERABLE

    # Authentication / API key problems
    # litellm:    AuthenticationError
    # Anthropic:  "invalid x-api-key"
    # OpenAI:     "Incorrect API key provided"
    # Gemini:     "API_KEY_INVALID"
    # OpenRouter: "No auth credentials found", "Invalid API key"
    if "AuthenticationError" in exc_name:
        return LLMErrorKind.UNRECOVERABLE
    if any(phrase in exc_str for phrase in (
        "invalid x-api-key",
        "Incorrect API key provided",
        "API_KEY_INVALID",
        "invalid_api_key",
        "No API key provided",
        "No auth credentials found",
        "Invalid API key",
    )):
        return LLMErrorKind.UNRECOVERABLE

    # litellm-specific unrecoverable exception types
    if "InsufficientQuotaError" in exc_name:
        return LLMErrorKind.UNRECOVERABLE

    # Model not found / permission denied
    # OpenAI:    "model_not_found"
    # Anthropic: "model: ... is not supported"
    # litellm:   NotFoundError, PermissionDeniedError
    if any(name in exc_name for name in (
        "NotFoundError",
        "PermissionDeniedError",
    )):
        return LLMErrorKind.UNRECOVERABLE
    if any(phrase in exc_str for phrase in (
        "model_not_found",
        "is not supported",
        "does not exist",
        "No endpoints found",  # OpenRouter: model not available
    )):
        return LLMErrorKind.UNRECOVERABLE

    # ------------------------------------------------------------------
    # RETRYABLE — transient errors that back-off can resolve
    # ------------------------------------------------------------------

    # Rate limits
    # litellm: RateLimitError
    # HTTP 429 from any provider
    if "RateLimitError" in exc_name:
        return LLMErrorKind.RETRYABLE
    if "429" in exc_str or "rate_limit" in exc_str.lower():
        return LLMErrorKind.RETRYABLE

    # Temporary server-side errors
    # HTTP 502 Bad Gateway, 503 Service Unavailable, 529 Anthropic overload
    if any(name in exc_name for name in (
        "APIConnectionError",
        "APITimeoutError",
        "ServiceUnavailableError",
    )):
        return LLMErrorKind.RETRYABLE
    if any(code in exc_str for code in ("502", "503", "529")):
        return LLMErrorKind.RETRYABLE

    # Gemini: RESOURCE_EXHAUSTED maps to retryable overload (distinct from quota)
    if "RESOURCE_EXHAUSTED" in exc_str and "Quota exceeded" not in exc_str:
        return LLMErrorKind.RETRYABLE

    # ------------------------------------------------------------------
    # UNKNOWN — caller decides
    # ------------------------------------------------------------------
    return LLMErrorKind.UNKNOWN
