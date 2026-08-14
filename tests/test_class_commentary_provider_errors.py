from __future__ import annotations

import json
import unittest

from class_commentary_provider_errors import (
    build_provider_dispatch_interruption_snapshot,
    build_provider_failure_snapshot,
    classify_provider_error,
    normalize_provider_failure_snapshot,
)


class FakeResponse:
    def __init__(self, status_code: int, headers: dict | None = None):
        self.status_code = status_code
        self.headers = headers or {}


class FakeProviderError(Exception):
    def __init__(
        self,
        message: str,
        *,
        status_code: int,
        headers: dict | None = None,
        code: str = "",
    ):
        super().__init__(message)
        self.response = FakeResponse(status_code, headers)
        self.code = code


class BrokenStringProviderError(Exception):
    def __str__(self) -> str:
        raise RuntimeError("broken exception string")


class ClassCommentaryProviderErrorsTest(unittest.TestCase):
    def test_timeout_snapshot_is_specific_and_does_not_store_raw_message(self):
        secret = "sk-secret-value"
        snapshot = build_provider_failure_snapshot(
            TimeoutError(f"provider timed out with {secret}"),
            local_request_id="class-commentary-generation-235",
        )

        self.assertEqual(snapshot["error_code"], "provider_timeout")
        self.assertEqual(snapshot["result_state"], "unknown")
        self.assertTrue(snapshot["retryable"])
        self.assertEqual(snapshot["exception_type"], "builtins.TimeoutError")
        self.assertNotIn(secret, json.dumps(snapshot, ensure_ascii=False))

    def test_rate_limit_captures_safe_status_request_id_and_retry_after(self):
        error = FakeProviderError(
            "rate limit exceeded",
            status_code=429,
            headers={"Retry-After": "17", "X-Request-Id": "req_123"},
            code="rate_limit_exceeded",
        )

        snapshot = build_provider_failure_snapshot(
            error,
            local_request_id="class-commentary-generation-236",
        )

        self.assertEqual(snapshot["error_code"], "provider_rate_limited")
        self.assertEqual(snapshot["result_state"], "rejected")
        self.assertEqual(snapshot["http_status"], 429)
        self.assertEqual(snapshot["provider_request_id"], "req_123")
        self.assertEqual(snapshot["upstream_error_code"], "rate_limit_exceeded")
        self.assertEqual(snapshot["retry_after_seconds"], 17)

    def test_upstream_server_error_is_distinct_from_request_rejection(self):
        upstream = FakeProviderError("gateway failed", status_code=502)
        rejected = FakeProviderError("invalid model", status_code=400)

        self.assertEqual(
            classify_provider_error(upstream),
            ("provider_upstream_error", True, 30),
        )
        self.assertEqual(
            classify_provider_error(rejected),
            ("provider_request_rejected", False, 0),
        )

    def test_interrupted_dispatch_has_durable_local_request_identity(self):
        snapshot = build_provider_dispatch_interruption_snapshot(
            local_request_id="class-commentary-generation-237",
        )

        self.assertEqual(snapshot["error_code"], "provider_dispatch_interrupted")
        self.assertEqual(snapshot["result_state"], "unknown")
        self.assertEqual(
            snapshot["local_request_id"],
            "class-commentary-generation-237",
        )

    def test_snapshot_normalization_rejects_extra_untrusted_fields(self):
        snapshot = build_provider_dispatch_interruption_snapshot(
            local_request_id="class-commentary-generation-238",
        )
        snapshot["raw_message"] = "do not persist me"

        with self.assertRaisesRegex(ValueError, "fields are invalid"):
            normalize_provider_failure_snapshot(snapshot)

    def test_diagnostic_snapshot_survives_a_broken_exception_string(self):
        snapshot = build_provider_failure_snapshot(
            BrokenStringProviderError(),
            local_request_id="class-commentary-generation-239",
        )

        self.assertEqual(snapshot["error_code"], "provider_request_failed")
        self.assertEqual(
            snapshot["exception_type"],
            f"{__name__}.BrokenStringProviderError",
        )


if __name__ == "__main__":
    unittest.main()
