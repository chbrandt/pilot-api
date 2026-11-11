"""
api/login.py — Public token-verification and OIDC-login endpoints.

These endpoints let the Pilot App (GUI — a separate service in the
``pilot-app`` repository) log users in *without* importing ``lib/``, parsing
JWTs locally, or ever seeing the OIDC client secret:

    POST /api/auth/verify          { "access_token": "<jwt>" }
        Validate a pasted EGI Check-in access token and return the
        verified claims plus the derived namespace.

    POST /api/auth/oidc/exchange   { "code", "code_verifier", "redirect_uri" }
        Complete the OAuth 2.0 authorization-code + PKCE exchange
        server-side and return the same payload as /verify.

Both endpoints enforce the exact same validation, group-access and
namespace-derivation rules as ``require_token`` on protected routes.
"""

import json
import logging

import requests
from flask import Blueprint, request

from api.site_config import load_oidc_audience, load_oidc_config, load_site_config
from lib.token_auth import (
    check_group_access,
    derive_namespace,
    fetch_userinfo,
    validate_token,
)

logger = logging.getLogger(__name__)

login_bp = Blueprint("api_login", __name__, url_prefix="/api/auth")

_DEFAULT_ISSUER = "https://aai.egi.eu/auth/realms/egi"


class _AuthError(Exception):
    """Login failure carrying the HTTP status code to return."""

    def __init__(self, message: str, code: int):
        super().__init__(message)
        self.message = message
        self.code = code


def _ok(data, code: int = 200):
    return json.dumps(data), code, {"Content-Type": "application/json"}


def _err(message: str, code: int = 400):
    return json.dumps({"error": message}), code, {"Content-Type": "application/json"}


def _validate_and_enrich(token: str) -> dict:
    """
    Validate *token* and return the enriched claims dict.

    Mirrors the checks inside :func:`api.auth.require_token`:

    1. JWT signature/expiry/issuer (+ optional audience),
    2. group-access control via the UserInfo endpoint (when configured),
    3. namespace derivation from the ``sub`` claim.

    Raises
    ------
    _AuthError
        With the appropriate HTTP status code (401 / 403 / 503) on failure.
    """
    try:
        claims = validate_token(token, audience=load_oidc_audience())
    except ValueError as exc:
        raise _AuthError(f"Token validation failed: {exc}", 401)

    allowed_groups = load_site_config().get("allowed_groups") or []
    if allowed_groups:
        try:
            userinfo = fetch_userinfo(token, claims["iss"])
            claims = {**claims, **userinfo}
        except ValueError as exc:
            raise _AuthError(
                f"Could not verify group membership "
                f"(UserInfo endpoint unavailable): {exc}",
                503,
            )
    try:
        check_group_access(claims, allowed_groups)
    except ValueError as exc:
        raise _AuthError(str(exc), 403)

    claims["namespace"] = derive_namespace(claims["sub"])
    return claims


# ── Routes ─────────────────────────────────────────────────────────────


@login_bp.route("/verify", methods=["POST"])
def verify_token():
    """Validate a pasted access token; return claims + namespace."""
    body = request.get_json(silent=True) or {}
    token = body.get("access_token")
    if not isinstance(token, str) or not token.strip():
        return _err("'access_token' is required.", 400)
    token = token.strip()

    try:
        claims = _validate_and_enrich(token)
    except _AuthError as exc:
        logger.warning("Token verification failed: %s", exc.message)
        return _err(exc.message, exc.code)

    return _ok({"token": token, "claims": claims, "namespace": claims["namespace"]})


@login_bp.route("/oidc/exchange", methods=["POST"])
def oidc_exchange():
    """Exchange an OAuth authorization code (PKCE) for validated credentials."""
    body = request.get_json(silent=True) or {}
    code = body.get("code")
    code_verifier = body.get("code_verifier")
    redirect_uri = body.get("redirect_uri")
    if not all(isinstance(v, str) and v for v in (code, code_verifier, redirect_uri)):
        return _err("'code', 'code_verifier' and 'redirect_uri' are required.", 400)

    oidc = load_oidc_config()
    client_id = oidc.get("client_id", "")
    if not client_id:
        return _err("EGI Check-in login is not configured.", 503)

    issuer = (oidc.get("issuer") or _DEFAULT_ISSUER).rstrip("/")
    token_url = f"{issuer}/protocol/openid-connect/token"

    data = {
        "grant_type": "authorization_code",
        "code": code,
        "redirect_uri": redirect_uri,
        "client_id": client_id,
        "code_verifier": code_verifier,
    }
    client_secret = oidc.get("client_secret")
    if client_secret:
        data["client_secret"] = client_secret

    try:
        resp = requests.post(token_url, data=data, timeout=30)
    except Exception as exc:
        logger.error("OAuth token exchange request failed: %s", exc)
        return _err("Could not reach the identity provider during token exchange.", 502)

    if resp.status_code != 200:
        logger.warning(
            "OAuth token exchange failed (HTTP %s): %s",
            resp.status_code,
            resp.text[:200],
        )
        return _err("Could not exchange the authorization code.", 401)

    try:
        tokens = resp.json()
    except Exception:
        return _err("Malformed response from the identity provider.", 502)

    access_token = tokens.get("access_token")
    if not access_token:
        return _err("No access token in the identity provider response.", 401)

    try:
        claims = _validate_and_enrich(access_token)
    except _AuthError as exc:
        logger.warning("Post-exchange token validation failed: %s", exc.message)
        return _err(exc.message, exc.code)

    return _ok(
        {"token": access_token, "claims": claims, "namespace": claims["namespace"]}
    )
