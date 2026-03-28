"""Unit tests for harvest.agent_sandbox.llm_errors.classify_llm_error."""


import pytest

from harvest.agent_sandbox.llm_errors import LLMErrorKind, classify_llm_error


# -- UNRECOVERABLE ----------------------------------------------------------


def test_anthropic_insufficient_credits():
    exc = Exception("Your credit balance is too low to access the Anthropic API")
    assert classify_llm_error(exc) == LLMErrorKind.UNRECOVERABLE


def test_openai_quota_exceeded():
    exc = Exception("You exceeded your current quota, please check your plan")
    assert classify_llm_error(exc) == LLMErrorKind.UNRECOVERABLE


def test_gemini_api_key_invalid():
    exc = Exception("API_KEY_INVALID: the provided API key is not valid")
    assert classify_llm_error(exc) == LLMErrorKind.UNRECOVERABLE


# -- RETRYABLE ---------------------------------------------------------------


def test_litellm_rate_limit_error():
    RateLimitError = type("RateLimitError", (Exception,), {})
    exc = RateLimitError("rate limited")
    assert classify_llm_error(exc) == LLMErrorKind.RETRYABLE


def test_http_429():
    exc = Exception("HTTP 429 Too Many Requests")
    assert classify_llm_error(exc) == LLMErrorKind.RETRYABLE


def test_http_503():
    exc = Exception("HTTP 503 Service Unavailable")
    assert classify_llm_error(exc) == LLMErrorKind.RETRYABLE


def test_anthropic_529_overload():
    exc = Exception("Error code: 529 - Anthropic is temporarily overloaded")
    assert classify_llm_error(exc) == LLMErrorKind.RETRYABLE


# -- UNKNOWN -----------------------------------------------------------------


def test_arbitrary_value_error():
    exc = ValueError("something unexpected happened")
    assert classify_llm_error(exc) == LLMErrorKind.UNKNOWN
