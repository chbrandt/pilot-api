"""
tests/api/test_login_api.py — Tests for POST /api/auth/verify —
the public token-paste login endpoint used by the Pilot App (GUI), which
must never validate JWTs locally.
"""

import hashlib
import time
from unittest.mock import patch

VALIDATE_PATCH = "api.login.validate_token"
FETCH_USERINFO_PATCH = "api.login.fetch_userinfo"
CHECK_GROUP_PATCH = "api.login.check_group_access"
DERIVE_NS_PATCH = "api.login.derive_namespace"
LOAD_AUDIENCE_PATCH = "api.login.load_oidc_audience"
LOAD_SITE_PATCH = "api.login.load_site_config"

FAKE_SUB = "test-user-sub-12345678"
FAKE_CLAIMS = {
    "sub": FAKE_SUB,
    "iss": "https://aai.egi.eu/auth/realms/egi",
    "exp": int(time.time()) + 3600,
    "iat": int(time.time()),
}
FAKE_NS = "user-" + hashlib.sha256(FAKE_SUB.encode()).hexdigest()[:16]


class TestVerifyToken:
    URL = "/api/auth/verify"

    def test_missing_token_returns_400(self, client):
        resp = client.post(self.URL, json={})
        assert resp.status_code == 400

    def test_valid_token_returns_claims_and_namespace(self, client):
        with (
            patch(VALIDATE_PATCH, return_value=dict(FAKE_CLAIMS)),
            patch(DERIVE_NS_PATCH, return_value=FAKE_NS),
            patch(LOAD_AUDIENCE_PATCH, return_value=None),
            patch(LOAD_SITE_PATCH, return_value={}),
        ):
            resp = client.post(self.URL, json={"access_token": "tok"})

        assert resp.status_code == 200
        data = resp.get_json(force=True)
        assert data["token"] == "tok"
        assert data["namespace"] == FAKE_NS
        assert data["claims"]["sub"] == FAKE_SUB

    def test_trims_whitespace(self, client):
        with (
            patch(VALIDATE_PATCH, return_value=dict(FAKE_CLAIMS)),
            patch(DERIVE_NS_PATCH, return_value=FAKE_NS),
            patch(LOAD_AUDIENCE_PATCH, return_value=None),
            patch(LOAD_SITE_PATCH, return_value={}),
        ):
            resp = client.post(self.URL, json={"access_token": "  tok  "})

        assert resp.status_code == 200
        assert resp.get_json(force=True)["token"] == "tok"

    def test_validation_failure_returns_401(self, client):
        with patch(VALIDATE_PATCH, side_effect=ValueError("bad signature")):
            resp = client.post(self.URL, json={"access_token": "tok"})

        assert resp.status_code == 401
        assert "bad signature" in resp.get_json(force=True)["error"]

    def test_group_denied_returns_403(self, client):
        with (
            patch(VALIDATE_PATCH, return_value=dict(FAKE_CLAIMS)),
            patch(LOAD_AUDIENCE_PATCH, return_value=None),
            patch(LOAD_SITE_PATCH, return_value={"allowed_groups": ["hpc-wg"]}),
            patch(FETCH_USERINFO_PATCH, return_value={}),
            patch(
                CHECK_GROUP_PATCH,
                side_effect=ValueError("Access denied: no required group."),
            ),
        ):
            resp = client.post(self.URL, json={"access_token": "tok"})

        assert resp.status_code == 403

    def test_userinfo_unavailable_returns_503(self, client):
        with (
            patch(VALIDATE_PATCH, return_value=dict(FAKE_CLAIMS)),
            patch(LOAD_AUDIENCE_PATCH, return_value=None),
            patch(LOAD_SITE_PATCH, return_value={"allowed_groups": ["hpc-wg"]}),
            patch(FETCH_USERINFO_PATCH, side_effect=ValueError("unreachable")),
        ):
            resp = client.post(self.URL, json={"access_token": "tok"})

        assert resp.status_code == 503

    def test_rejects_non_string_token(self, client):
        for bad in (None, 123, ["tok"]):
            resp = client.post(self.URL, json={"access_token": bad})
            assert resp.status_code == 400
