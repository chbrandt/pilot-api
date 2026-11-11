"""
tests/api/test_saved_api.py — Integration tests for api.saved endpoints.

Uses the Flask test client from conftest + patches saved_deployments and
site_config helpers so no real filesystem access is needed.
"""

from unittest.mock import patch

import pytest


# ---------------------------------------------------------------------------
# Patch targets
# ---------------------------------------------------------------------------

SEED_DEFAULTS_PATCH = "api.saved.seed_defaults"
LOAD_SITE_CONFIG_PATCH = "api.saved.load_site_config"
LIST_PATCH = "api.saved.list_configs"
SAVE_PATCH = "api.saved.save_config"
GET_PATCH = "api.saved.get_config"
DELETE_PATCH = "api.saved.delete_config"

_FAKE_SITE_CFG = {"hostname": "test.local"}


# ---------------------------------------------------------------------------
# POST /api/saved/seed
# ---------------------------------------------------------------------------


class TestSeedSavedDefaults:
    URL = "/api/saved/seed"

    def test_requires_auth(self, client):
        assert client.post(self.URL).status_code == 401

    def test_success_returns_200(self, client, auth_headers):
        headers, fake_ns = auth_headers
        with (
            patch(LOAD_SITE_CONFIG_PATCH, return_value=_FAKE_SITE_CFG),
            patch(SEED_DEFAULTS_PATCH),
        ):
            resp = client.post(self.URL, headers=headers)

        assert resp.status_code == 200
        data = resp.get_json(force=True)
        assert data["seeded"] is True
        assert data["namespace"] == fake_ns

    def test_seed_defaults_called_with_site_config(self, client, auth_headers):
        """seed_defaults must receive the site config loaded by api.site_config."""
        headers, fake_ns = auth_headers
        with (
            patch(LOAD_SITE_CONFIG_PATCH, return_value=_FAKE_SITE_CFG),
            patch(SEED_DEFAULTS_PATCH) as mock_seed,
        ):
            client.post(self.URL, headers=headers)

        mock_seed.assert_called_once_with(fake_ns, _FAKE_SITE_CFG)

    def test_seed_exception_returns_500(self, client, auth_headers):
        headers, _ = auth_headers
        with (
            patch(LOAD_SITE_CONFIG_PATCH, return_value=_FAKE_SITE_CFG),
            patch(SEED_DEFAULTS_PATCH, side_effect=RuntimeError("disk error")),
        ):
            resp = client.post(self.URL, headers=headers)

        assert resp.status_code == 500
        assert "error" in resp.get_json(force=True)


# ---------------------------------------------------------------------------
# GET/POST /api/saved  ·  GET/DELETE /api/saved/<config_id>
# ---------------------------------------------------------------------------


class TestListSaved:
    URL = "/api/saved"

    def test_requires_auth(self, client):
        assert client.get(self.URL).status_code == 401

    def test_lists_all_configs(self, client, auth_headers):
        headers, fake_ns = auth_headers
        with patch(LIST_PATCH, return_value=[{"id": "a", "kind": "container"}]) as m:
            resp = client.get(self.URL, headers=headers)

        assert resp.status_code == 200
        assert resp.get_json(force=True) == [{"id": "a", "kind": "container"}]
        assert m.call_args[0][0] == fake_ns  # scoping by caller namespace

    def test_kind_query_param_is_forwarded(self, client, auth_headers):
        headers, _ = auth_headers
        with patch(LIST_PATCH, return_value=[]) as m:
            client.get(self.URL + "?kind=container", headers=headers)

        assert m.call_args[1].get("kind") == "container"


class TestCreateSaved:
    URL = "/api/saved"

    def test_requires_auth(self, client):
        assert client.post(self.URL, json={}).status_code == 401

    def test_creates_and_returns_201(self, client, auth_headers):
        headers, fake_ns = auth_headers
        entry = {"id": "abc123", "kind": "container", "name": "j1", "saved_at": "now"}
        with patch(SAVE_PATCH, return_value=entry) as m:
            resp = client.post(
                self.URL,
                json={"kind": "container", "config": {"name": "j1"}},
                headers=headers,
            )

        assert resp.status_code == 201
        assert resp.get_json(force=True) == entry
        assert m.call_args[1].get("namespace") == fake_ns
        assert m.call_args[1].get("kind") == "container"

    def test_rejects_missing_kind(self, client, auth_headers):
        headers, _ = auth_headers
        resp = client.post(
            self.URL, json={"config": {"name": "j1"}}, headers=headers
        )
        assert resp.status_code == 400

    def test_rejects_missing_config(self, client, auth_headers):
        headers, _ = auth_headers
        resp = client.post(self.URL, json={"kind": "container"}, headers=headers)
        assert resp.status_code == 400


class TestGetSaved:
    def test_requires_auth(self, client):
        assert client.get("/api/saved/abc").status_code == 401

    def test_returns_entry(self, client, auth_headers):
        headers, _ = auth_headers
        entry = {"id": "abc", "kind": "helm", "release_name": "interlink"}
        with patch(GET_PATCH, return_value=entry):
            resp = client.get("/api/saved/abc", headers=headers)

        assert resp.status_code == 200
        assert resp.get_json(force=True) == entry

    def test_unknown_id_returns_404(self, client, auth_headers):
        headers, _ = auth_headers
        with patch(GET_PATCH, return_value=None):
            resp = client.get("/api/saved/nope", headers=headers)

        assert resp.status_code == 404


class TestDeleteSaved:
    def test_requires_auth(self, client):
        assert client.delete("/api/saved/abc").status_code == 401

    def test_deletes_existing_entry(self, client, auth_headers):
        headers, _ = auth_headers
        entry = {"id": "abc", "kind": "container"}
        with (
            patch(GET_PATCH, return_value=entry),
            patch(DELETE_PATCH, return_value=True) as m,
        ):
            resp = client.delete("/api/saved/abc", headers=headers)

        assert resp.status_code == 200
        assert resp.get_json(force=True) == {"deleted": "abc"}
        assert m.call_args[0][1] == "abc"

    def test_unknown_id_returns_404(self, client, auth_headers):
        headers, _ = auth_headers
        with patch(GET_PATCH, return_value=None):
            resp = client.delete("/api/saved/nope", headers=headers)

        assert resp.status_code == 404

