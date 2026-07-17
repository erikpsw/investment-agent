from __future__ import annotations

import time
import unittest

import jwt
from cryptography.hazmat.primitives.asymmetric import rsa

from investment.api.auth import Auth0TokenVerifier


class _SigningKey:
    def __init__(self, key) -> None:
        self.key = key


class _StaticJwksClient:
    def __init__(self, public_key) -> None:
        self.public_key = public_key

    def get_signing_key_from_jwt(self, token: str):
        return _SigningKey(self.public_key)


class _UserInfoResponse:
    def raise_for_status(self) -> None:
        return None

    def json(self):
        return {
            "sub": "auth0|userinfo-user",
            "email": "userinfo@example.com",
        }


class Auth0VerifierTests(unittest.TestCase):
    def setUp(self) -> None:
        self.private_key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
        self.verifier = Auth0TokenVerifier(
            domain="https://tenant.example.com",
            audience="https://investment-agent-api",
        )
        self.verifier.jwks_client = _StaticJwksClient(self.private_key.public_key())

    def _token(self, audience: str) -> str:
        now = int(time.time())
        return jwt.encode(
            {
                "sub": "auth0|verified-user",
                "email": "verified@example.com",
                "iss": "https://tenant.example.com/",
                "aud": audience,
                "iat": now,
                "exp": now + 300,
            },
            self.private_key,
            algorithm="RS256",
            headers={"kid": "test-key"},
        )

    def test_valid_rs256_token_returns_authenticated_subject(self) -> None:
        user = self.verifier.verify(self._token("https://investment-agent-api"))

        self.assertEqual(user.sub, "auth0|verified-user")
        self.assertEqual(user.email, "verified@example.com")

    def test_wrong_audience_is_rejected(self) -> None:
        with self.assertRaises(jwt.InvalidAudienceError):
            self.verifier.verify(self._token("https://another-api"))

    def test_userinfo_token_returns_subject_when_audience_is_not_configured(self) -> None:
        calls = []
        verifier = Auth0TokenVerifier(
            domain="https://tenant.example.com",
            audience="",
        )
        verifier.userinfo_get = lambda url, headers, timeout: (
            calls.append((url, headers, timeout)) or _UserInfoResponse()
        )

        user = verifier.verify("opaque-userinfo-token")

        self.assertEqual(user.sub, "auth0|userinfo-user")
        self.assertEqual(user.email, "userinfo@example.com")
        self.assertEqual(calls[0][0], "https://tenant.example.com/userinfo")
        self.assertEqual(
            calls[0][1]["Authorization"],
            "Bearer opaque-userinfo-token",
        )
        self.assertEqual(calls[0][2], 10)


if __name__ == "__main__":
    unittest.main()
