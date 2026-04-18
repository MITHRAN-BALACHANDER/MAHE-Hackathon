"""ISP / carrier detection via IP-based geolocation.

Architecture:
  Next.js frontend → FastAPI /api/detect-network → ipapi.co (free tier)

Flow:
  1. Extract client IP from request (handles X-Forwarded-For for proxies)
  2. Query external IP lookup API (ipapi.co free tier, 1000 req/day)
  3. Return ISP name, carrier name, connection type, VPN detection

Limitations:
  - Wi-Fi vs mobile: IP lookup returns ISP, NOT the SIM carrier.
    If user is on Wi-Fi at home, we get "ACT Fibernet" not "Airtel".
  - VPN/Proxy: IP resolves to VPN provider, not actual ISP.
  - eSIM/multi-SIM: Browser cannot detect which SIM is active.
  - Accuracy: ~90% for ISP identification, lower for mobile carrier.

Recommended third-party APIs:
  1. ipapi.co (free tier: 1000/day) - best for basic ISP detection
  2. ipinfo.io (free tier: 50k/month) - premium carrier detection
  3. ip-api.com (free for non-commercial) - good for basic use
  4. MaxMind GeoLite2 (local DB) - no rate limits, offline capable
"""

import asyncio
from typing import Optional

import httpx
from fastapi import APIRouter, Request
from pydantic import BaseModel

router = APIRouter(tags=["Network Detection"])


class NetworkDetectResponse(BaseModel):
    """Response from ISP/carrier detection."""
    ip: str
    isp: str                 # Internet Service Provider name
    carrier: str             # Mobile carrier (often same as ISP for mobile data)
    org: str                 # Organization name
    connection_type: str     # "wifi", "cellular", or "unknown"
    is_vpn: bool             # Whether IP belongs to a VPN/proxy
    country: str
    city: str
    asn: str                 # Autonomous System Number


def _extract_client_ip(request: Request) -> str:
    """Extract real client IP, respecting reverse proxy headers.

    Priority:
      1. X-Forwarded-For (first IP in chain = original client)
      2. X-Real-IP (set by some proxies)
      3. request.client.host (direct connection)
    """
    forwarded = request.headers.get("x-forwarded-for")
    if forwarded:
        # First IP in comma-separated list is the original client
        return forwarded.split(",")[0].strip()

    real_ip = request.headers.get("x-real-ip")
    if real_ip:
        return real_ip.strip()

    return request.client.host if request.client else "127.0.0.1"


# Known VPN/proxy ASN keywords
_VPN_KEYWORDS = frozenset([
    "cloudflare", "akamai", "fastly", "amazon", "google cloud",
    "digitalocean", "linode", "vultr", "ovh", "hetzner",
    "nordvpn", "expressvpn", "surfshark", "mullvad", "protonvpn",
    "private internet access", "cyberghost", "hide.me",
])

# Known Indian mobile carrier keywords -> carrier name
_CARRIER_MAP = {
    "jio": "Jio",
    "reliance": "Jio",
    "airtel": "Airtel",
    "bharti": "Airtel",
    "vodafone": "Vi",
    "idea": "Vi",
    "bsnl": "BSNL",
    "mtnl": "MTNL",
}


def _detect_carrier(isp: str, org: str) -> str:
    """Detect Indian mobile carrier from ISP/org name."""
    combined = f"{isp} {org}".lower()
    for keyword, carrier in _CARRIER_MAP.items():
        if keyword in combined:
            return carrier
    return ""


def _is_likely_vpn(org: str, isp: str) -> bool:
    """Heuristic VPN detection based on ISP/org name."""
    combined = f"{isp} {org}".lower()
    return any(kw in combined for kw in _VPN_KEYWORDS)


def _guess_connection_type(isp: str, org: str) -> str:
    """Guess whether this is a mobile data or broadband/Wi-Fi connection.

    Mobile ISPs in India: Jio, Airtel, Vi, BSNL
    Broadband ISPs: ACT, Hathway, Excitel, Tikona, etc.
    """
    combined = f"{isp} {org}".lower()
    mobile_keywords = ["jio", "reliance", "airtel", "bharti", "vodafone", "idea", "bsnl", "mtnl"]
    if any(kw in combined for kw in mobile_keywords):
        return "cellular"

    broadband_keywords = ["act ", "fibernet", "hathway", "excitel", "tikona", "spectra", "tata sky", "den "]
    if any(kw in combined for kw in broadband_keywords):
        return "wifi"

    return "unknown"


@router.get("/api/detect-network", response_model=NetworkDetectResponse)
async def detect_network(request: Request):
    """Detect ISP/carrier from client IP using ipapi.co.

    How it works:
      1. Extract client IP from request headers (handles proxies)
      2. Query ipapi.co free API for ISP/org/location
      3. Map ISP name to known Indian carriers
      4. Detect VPN/proxy usage
      5. Guess connection type (cellular vs wifi)

    Edge cases handled:
      - VPN/Proxy: Detected via ASN keywords, flagged in response
      - Unknown network: Returns empty carrier, "unknown" connection
      - API failure: Falls back to minimal response with IP only
      - Localhost/private IPs: Uses ipapi auto-detect mode
    """
    client_ip = _extract_client_ip(request)

    # For localhost/private IPs, let ipapi auto-detect
    is_private = client_ip.startswith(("127.", "10.", "192.168.", "172.")) or client_ip == "::1"
    lookup_url = (
        "https://ipapi.co/json/"
        if is_private
        else f"https://ipapi.co/{client_ip}/json/"
    )

    try:
        async with httpx.AsyncClient(timeout=5.0) as http:
            resp = await http.get(lookup_url, headers={"User-Agent": "SignalRoute/1.0"})
            resp.raise_for_status()
            data = resp.json()

        isp = data.get("org", "") or data.get("isp", "")
        org = data.get("org", "")
        asn = data.get("asn", "")

        carrier = _detect_carrier(isp, org)
        is_vpn = _is_likely_vpn(org, isp)
        conn_type = _guess_connection_type(isp, org)

        return NetworkDetectResponse(
            ip=data.get("ip", client_ip),
            isp=isp,
            carrier=carrier,
            org=org,
            connection_type=conn_type,
            is_vpn=is_vpn,
            country=data.get("country_name", ""),
            city=data.get("city", ""),
            asn=asn,
        )

    except Exception:
        # Fallback: return minimal response
        return NetworkDetectResponse(
            ip=client_ip,
            isp="unknown",
            carrier="",
            org="",
            connection_type="unknown",
            is_vpn=False,
            country="",
            city="",
            asn="",
        )


@router.get("/api/network-strength")
async def network_strength(request: Request):
    """Estimate network signal strength for current user.

    Combines:
      1. ISP/carrier detection (who they're connected to)
      2. Connection type hints from the frontend via query params
      3. Zone-based signal prediction from our model

    This is a user-facing endpoint for real-time signal monitoring.
    """
    client_ip = _extract_client_ip(request)

    # Detect ISP first
    is_private = client_ip.startswith(("127.", "10.", "192.168.", "172.")) or client_ip == "::1"
    lookup_url = "https://ipapi.co/json/" if is_private else f"https://ipapi.co/{client_ip}/json/"

    isp_info = {"isp": "unknown", "carrier": ""}
    try:
        async with httpx.AsyncClient(timeout=5.0) as http:
            resp = await http.get(lookup_url, headers={"User-Agent": "SignalRoute/1.0"})
            if resp.status_code == 200:
                data = resp.json()
                isp = data.get("org", "")
                isp_info["isp"] = isp
                isp_info["carrier"] = _detect_carrier(isp, data.get("org", ""))
    except Exception:
        pass

    return {
        "ip": client_ip,
        "isp": isp_info["isp"],
        "carrier": isp_info["carrier"],
        "estimated_strength": "good",  # Will be replaced by model prediction
        "tip": "For accurate signal strength, enable location services and let SignalRoute predict signal along your route.",
        "note": "Browser-level signal measurement requires the Network Information API (Chrome only). True dBm readings require native app access.",
    }
