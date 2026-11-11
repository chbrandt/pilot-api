"""
tests/api/test_oidc_exchange_api.py — Tests for POST /api/auth/oidc/exchange.

The OAuth authorization-code + PKCE exchange now happens server-side (the
client secret never leaves the API) and returns the same validated payload
as POST /api/auth/verify.
"""

import hashlib
import time
from contextlib import ExitStack
from unittest.mock import MagicMock, patch

VALIDATE_PATCH = "api.login.validate_token"
FETCH_USERINFO_PATCH = "api.login.fetch_userinfo"
CHECK_GROUP_PATCH = "api.login.check_group_access"
DERIVE_NS_PATCH = "api.login.derive_namespace"
LOAD_AUDIENCE_PATCH = "api.login.load_oidc_audience"
LOAD_SITE_PATCH = "api.login.load_site_config"
LOAD_OIDC_PATCH = "api.login.load_oidc_config"
REQUESTS_PATCH = "api.login.requests"

FAKE_SUB = "test-user-sub-12345678"
FAKE_CLAIMS = {
    "sub": FAKE_SUB,
    "iss": "https://aai.egi.eu/auth/realms/egi",
    "exp": int(time.time()) + 3600,
    "iat": int(time.time()),
}
FAKE_NS = "user-" + hashlib.sha256(FAKE_SUB.encode()).hexdigest()[:16]


class TestOidcExchange:
    URL = "/api/auth/oidc/exchange"
    BODY = {
        "code": "auth-code",
        "code_verifier": "pkce-verifier",
        "redirect_uri": "http://localhost:5000/oauth/callback",
    }

    @staticmethod
    def _oidc_config(secret="yaml-secret"):
        return {
            "client_id": "pilot",
            "client_secret": secret,
            "issuer": "https://aai.egi.eu/auth/realms/egi",
        }

    @staticmethod
    def _verified_response(mock_requests, access_token="tok"):
        mock_resp = MagicMock(status_code=200)
        mock_resp.json.return_value = {"access_token": access_token}
        mock_requests.post.return_value = mock_resp

    def test_missing_fields_returns_400(self, client):
        resp = client.post(self.URL, json={"code": "c"})
        assert resp.status_code == 400

    def test_not_configured_returns_503(self, client):
        with patch(LOAD_OIDC_PATCH, return_value={}):
            resp = client.post(self.URL, json=self.BODY)
        assert resp.status_code == 503

    def test_success_returns_credentials(self, client):
        with (
            patch(LOAD_OIDC_PATCH, return_value=self._oidc_config()),
            patch(VALIDATE_PATCH, return_value=dict(FAKE_CLAIMS)),
            patch(DERIVE_NS_PATCH, return_value=FAKE_NS),
            patch(LOAD_AUDIENCE_PATCH, return_value=None),
            patch(LOAD_SITE_PATCH, return_value={}),
            patch(REQUESTS_PATCH) as mock_requests,
        ):
            self._verified_response(mock_requests)
            resp = client.post(self.URL, json=self.BODY)

        assert resp.status_code == 200
        data = resp.get_json(force=True)
        assert data["token"] == "tok"
        assert data["namespace"] == FAKE_NS

    def test_sends_pkce_and_client_secret_to_idp(self, client):
        with (
            patch(LOAD_OIDC_PATCH, return_value=self._oidc_config()),
            patch(VALIDATE_PATCH, return_value=dict(FAKE_CLAIMS)),
            patch(DERIVE_NS_PATCH, return_value=FAKE_NS),
            patch(LOAD_AUDIENCE_PATCH, return_value=None),
            patch(LOAD_SITE_PATCH, return_value={}),
            patch(REQUESTS_PATCH) as mock_requests,
        ):
            self._verified_response(mock_requests)
            client.post(self.URL, json=self.BODY)

        sent = mock_requests.post.call_args[1]["data"]
        assert sent["grant_type"] == "authorization_code"
        assert sent["code"] == "auth-code"
        assert sent["code_verifier"] == "pkce-verifier"
        assert sent["client_id"] == "pilot"
        assert sent["redirect_uri"] == self.BODY["redirect_uri"]
        # The secret lives server-side; it must still reach the IdP.
        assert sent["client_secret"] == "yaml-secret"

    def test_env_secret_overrides_yaml_secret(self, client, monkeypatch):
        monkeypatch.setenv("PILOT_OIDC_CLIENT_SECRET", "env-secret")
        with (
            # Let the real load_oidc_config run so the env-override logic
            # applies; only stub out the site config it reads from.
            patch(
                "api.site_config.load_site_config",
                return_value={"oidc": self._oidc_config()},
            ),
            patch(VALIDATE_PATCH, return_value=dict(FAKE_CLAIMS)),
            patch(DERIVE_NS_PATCH, return_value=FAKE_NS),
            patch(LOAD_AUDIENCE_PATCH, return_value=None),
            patch(LOAD_SITE_PATCH, return_value={}),
            patch(REQUESTS_PATCH) as mock_requests,
        ):
            self._verified_response(mock_requests)
            client.post(self.URL, json=self.BODY)

        sent = mock_requests.post.call_args[1]["data"]
        assert sent["client_secret"] == "env-secret"

    def test_idp_error_returns_401(self, client):
        mock_resp = MagicMock(status_code=400, text="invalid_grant")
        with (
            patch(LOAD_OIDC_PATCH, return_value=self._oidc_config()),
            patch(REQUESTS_PATCH) as mock_requests,
        ):
            mock_requests.post.return_value = mock_resp
            resp = client.post(self.URL, json=self.BODY)

        assert resp.status_code == 401

    def test_idp_unreachable_returns_502(self, client):
        with (
            patch(LOAD_OIDC_PATCH, return_value=self._oidc_config()),
            patch(REQUESTS_PATCH) as mock_requests,
        ):
            mock_requests.post.side_effect = ConnectionError("boom")
            resp = client.post(self.URL, json=self.BODY)

        assert resp.status_code == 502

    def test_no_access_token_in_idp_response_returns_401(self, client):
        mock_resp = MagicMock(status_code=200)
        mock_resp.json.return_value = {}
        with (
            patch(LOAD_OIDC_PATCH, return_value=self._oidc_config()),
            patch(REQUESTS_PATCH) as mock_requests,
        ):
            mock_requests.post.return_value = mock_resp
            resp = client.post(self.URL, json=self.BODY)

        assert resp.status_code == 401

    def test_group_denied_after_exchange_returns_403(self, client):
        with ExitStack() as stack:
            stack.enter_context(
                patch(LOAD_OIDC_PATCH, return_value=self._oidc_config())
            )
            stack.enter_context(patch(VALIDATE_PATCH, return_value=dict(FAKE_CLAIMS)))
            stack.enter_context(patch(LOAD_AUDIENCE_PATCH, return_value=None))
            stack.enter_context(
                patch(LOAD_SITE_PATCH, return_value={"allowed_groups": ["hpc-wg"]})
            )
            stack.enter_context(patch(FETCH_USERINFO_PATCH, return_value={}))
            stack.enter_context(
                patch(
                    CHECK_GROUP_PATCH,
                    side_effect=ValueError("Access denied: no required group."),
                )
            )
            mock_requests = stack.enter_context(patch(REQUESTS_PATCH))
            self._verified_response(mock_requests)
            resp = client.post(self.URL, json=self.BODY)

        assert resp.status_code == 403

