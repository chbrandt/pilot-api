"""
api/site.py — Public site-metadata endpoint.

Returns a *display-safe* subset of the site configuration so remote clients
(the Pilot App GUI in particular) can discover:

* the shared site hostname and wstunnel ports,
* the default container image proposed in the Submit Job form, and
* the OIDC client_id / issuer behind the "Log in with EGI Check-in" button.

No secrets (client_secret, session keys, …) are ever exposed here.
"""

import json
import logging

from flask import Blueprint

from api.site_config import load_oidc_config, load_site_config

logger = logging.getLogger(__name__)

site_bp = Blueprint("api_site", __name__, url_prefix="/api")

_DEFAULT_ISSUER = "https://aai.egi.eu/auth/realms/egi"


def _ok(data, code: int = 200) -> tuple[str, int, dict]:
    return json.dumps(data), code, {"Content-Type": "application/json"}


@site_bp.route("/site", methods=["GET"])
def site_meta() -> tuple[str, int, dict]:
    """Public, unauthenticated site metadata for remote GUI clients."""
    cfg = load_site_config()
    oidc = load_oidc_config()

    wst = cfg.get("wstunnel") if isinstance(cfg.get("wstunnel"), dict) else {}
    if not isinstance(oidc, dict):
        oidc = {}

    client_id = oidc.get("client_id", "") or ""
    data = {
        "hostname": cfg.get("hostname", "dev.local"),
        "default_image": cfg.get("default_image") or "ubuntu:22.04",
        "wstunnel": {
            "port": wst.get("port", 443),
            "local_port": wst.get("local_port", 4000),
        },
        "oidc": {
            "enabled": bool(client_id),
            "client_id": client_id,
            "issuer": oidc.get("issuer") or _DEFAULT_ISSUER,
        },
    }
    return _ok(data)
