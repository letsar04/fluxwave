from __future__ import annotations

import base64
import hashlib
import hmac
import os


class SessionAuthenticator:
    """Small HMAC challenge-response primitive for trusted experiments.

    This is not a replacement for TLS. It prevents accidental unauthenticated
    peer access when a shared secret is configured.
    """

    def __init__(self, secret: bytes):
        if len(secret) < 16:
            raise ValueError("secret must contain at least 16 bytes")
        self.secret = secret

    def challenge(self) -> str:
        return base64.urlsafe_b64encode(os.urandom(24)).decode("ascii")

    def response(self, challenge: str) -> str:
        return hmac.new(
            self.secret,
            challenge.encode("ascii"),
            hashlib.sha256,
        ).hexdigest()

    def verify(self, challenge: str, response: str) -> bool:
        return hmac.compare_digest(self.response(challenge), response)
