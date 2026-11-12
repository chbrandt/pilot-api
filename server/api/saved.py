"""
api/saved.py — REST endpoints for saved deployment configuration management.

All routes are JSON-only and protected by Bearer-token auth.

Endpoints
---------
POST   /api/saved/seed
    Idempotently seed the default Helm chart configs (from the unified
    configuration file) into the authenticated user's saved-config store.
    Safe to call on every login — entries already present (by stable ID) are
    left untouched.

GET    /api/saved?kind=<kind>
    List the caller's saved configurations, optionally filtered by kind.
POST   /api/saved
    Persist a new saved configuration. Body: {"kind": ..., "config": {...}}
GET    /api/saved/<config_id>
    Return one saved configuration.
DELETE /api/saved/<config_id>
    Remove one saved configuration.
"""

import json
import logging

from flask import Blueprint, request

from api.auth import get_request_claims, require_token
from api.site_config import load_site_config
from lib.saved_deployments import (
    delete_config,
    get_config,
    list_configs,
    save_config,
    seed_defaults,
)

logger = logging.getLogger(__name__)

saved_bp = Blueprint("api_saved", __name__, url_prefix="/api")


def _ok(data: dict | list, code: int = 200) -> tuple[str, int, dict]:
    return json.dumps(data), code, {"Content-Type": "application/json"}


def _err(message: str, code: int = 400) -> tuple[str, int, dict]:
    return json.dumps({"error": message}), code, {"Content-Type": "application/json"}


@saved_bp.route("/saved/seed", methods=["POST"])
@require_token
def seed_saved_defaults() -> tuple[str, int, dict]:
    """
    Idempotently seed the default configs for the authenticated user.

    Seeds Helm chart defaults (from the unified configuration file) in a
    single call.  Already-seeded entries (identified by their stable IDs)
    are never duplicated.
    """
    claims = get_request_claims()
    namespace = claims["namespace"]
    try:
        site_cfg = load_site_config()
        seed_defaults(namespace, site_cfg)
        return _ok({"seeded": True, "namespace": namespace})
    except Exception as exc:
        logger.error("seed_saved_defaults failed for %s: %s", namespace, exc)
        return _err(str(exc), 500)


# ── Saved-config CRUD ──────────────────────────────────────────────────


@saved_bp.route("/saved", methods=["GET"])
@require_token
def list_saved() -> tuple[str, int, dict]:
    """List the caller's saved configurations, optionally filtered by kind."""
    claims = get_request_claims()
    namespace = claims["namespace"]
    kind = request.args.get("kind") or None
    return _ok(list_configs(namespace, kind=kind))


@saved_bp.route("/saved", methods=["POST"])
@require_token
def create_saved() -> tuple[str, int, dict]:
    """Persist a new saved configuration for the caller."""
    claims = get_request_claims()
    namespace = claims["namespace"]

    body = request.get_json(silent=True) or {}
    kind = body.get("kind")
    config = body.get("config")
    if not isinstance(kind, str) or not kind.strip():
        return _err('"kind" is required (e.g. "container" or "helm").')
    if not isinstance(config, dict) or not config:
        return _err('"config" must be a non-empty object.')

    entry = save_config(namespace=namespace, kind=kind.strip(), config=config)
    return _ok(entry, code=201)


@saved_bp.route("/saved/<config_id>", methods=["GET"])
@require_token
def get_saved(config_id: str) -> tuple[str, int, dict]:
    """Return one saved configuration."""
    claims = get_request_claims()
    namespace = claims["namespace"]

    entry = get_config(namespace, config_id)
    if entry is None:
        return _err("Saved configuration not found.", 404)
    return _ok(entry)


@saved_bp.route("/saved/<config_id>", methods=["DELETE"])
@require_token
def delete_saved(config_id: str) -> tuple[str, int, dict]:
    """Remove one saved configuration."""
    claims = get_request_claims()
    namespace = claims["namespace"]

    entry = get_config(namespace, config_id)
    if entry is None:
        return _err("Saved configuration not found.", 404)
    delete_config(namespace, config_id)
    return _ok({"deleted": config_id})
