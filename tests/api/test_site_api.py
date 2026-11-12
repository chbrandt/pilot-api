"""
tests/api/test_site_api.py — Tests for the public GET /api/site endpoint.

/api/site exposes a display-safe subset of the site configuration so the
Pilot App (GUI) can render pages and build the OIDC authorization URL
without importing lib/ or reading the configuration file.
"""

from unittest.mock import patch

SITE_PATCH = "api.site.load_site_config"
OIDC_PATCH = "api.site.load_oidc_config"


def _fake_site() -> dict:
    return {
        "hostname": "site.example.org",
        "default_image": "alpine:3.19",
        "wstunnel": {"port": 443, "local_port": 4000},
    }


class TestSiteMeta:
    URL = "/api/site"

    def test_is_public(self, client):
        """No authentication is required (the GUI needs it before login)."""
        with patch(SITE_PATCH, return_value=_fake_site()):
            resp = client.get(self.URL)
        assert resp.status_code == 200

    def test_payload_shape(self, client):
        with patch(SITE_PATCH, return_value=_fake_site()):
            data = client.get(self.URL).get_json(force=True)

        assert data["hostname"] == "site.example.org"
        assert data["default_image"] == "alpine:3.19"
        assert data["wstunnel"] == {"port": 443, "local_port": 4000}
        assert set(data.keys()) == {"hostname", "default_image", "wstunnel", "oidc"}

    def test_oidc_not_configured(self, client):
        with patch(SITE_PATCH, return_value=_fake_site()):
            data = client.get(self.URL).get_json(force=True)

        assert data["oidc"]["enabled"] is False
        assert data["oidc"]["client_id"] == ""
        assert data["oidc"]["audience"] == ""

    def test_oidc_configured(self, client):
        with patch(
            OIDC_PATCH,
            return_value={
                "client_id": "pilot",
                "issuer": "https://idp.example.org",
                "audience": "hpc-pilot-aud",
            },
        ):
            data = client.get(self.URL).get_json(force=True)

        assert data["oidc"]["enabled"] is True
        assert data["oidc"]["client_id"] == "pilot"
        assert data["oidc"]["issuer"] == "https://idp.example.org"
        assert data["oidc"]["audience"] == "hpc-pilot-aud"

    def test_never_exposes_client_secret(self, client):
        """The OIDC client_secret must never appear in the public payload."""
        with patch(
            OIDC_PATCH,
            return_value={
                "client_id": "pilot",
                "issuer": "https://idp.example.org",
                "client_secret": "super-secret",
            },
        ):
            data = client.get(self.URL).get_json(force=True)

        assert "client_secret" not in data["oidc"]
        assert "super-secret" not in str(data)

    def test_defaults_when_config_empty(self, client):
        with patch(SITE_PATCH, return_value={}):
            data = client.get(self.URL).get_json(force=True)

        assert data["hostname"] == "dev.local"
        assert data["wstunnel"]["port"] == 443
        assert data["wstunnel"]["local_port"] == 4000
