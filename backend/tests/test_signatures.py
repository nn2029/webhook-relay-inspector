import unittest

from app.core.signatures import compute_hmac_signature, verify_hmac_signature


class SignatureVerificationTests(unittest.TestCase):
    def test_valid_signature_matches_raw_body(self) -> None:
        body = b'{"id":"evt_123","type":"checkout.completed"}'
        signature = compute_hmac_signature("top-secret", body)

        self.assertTrue(
            verify_hmac_signature("top-secret", body, signature),
        )

    def test_signature_rejects_tampered_payload(self) -> None:
        body = b'{"amount":1000}'
        signature = compute_hmac_signature("top-secret", body)

        self.assertFalse(
            verify_hmac_signature("top-secret", b'{"amount":9000}', signature),
        )

    def test_timestamp_tolerance_rejects_stale_payloads(self) -> None:
        body = b'{"event":"invoice.paid"}'
        timestamp = "1000"
        signature = compute_hmac_signature("top-secret", body, timestamp)

        self.assertTrue(
            verify_hmac_signature(
                "top-secret",
                body,
                signature,
                timestamp_header=timestamp,
                now=1001,
                tolerance_seconds=60,
            )
        )
        self.assertFalse(
            verify_hmac_signature(
                "top-secret",
                body,
                signature,
                timestamp_header=timestamp,
                now=1200,
                tolerance_seconds=60,
            )
        )

    def test_stripe_style_header_uses_embedded_timestamp(self) -> None:
        body = b'{"type":"payment_intent.succeeded"}'
        timestamp = "2000"
        digest = compute_hmac_signature("top-secret", body, timestamp).split("=", 1)[1]
        signature_header = f"t={timestamp},v1={digest}"

        self.assertTrue(
            verify_hmac_signature(
                "top-secret",
                body,
                signature_header,
                now=2001,
                tolerance_seconds=60,
            )
        )


if __name__ == "__main__":
    unittest.main()
