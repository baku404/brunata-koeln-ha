"""Account-isolated async HTTP client for the Cologne legacy portal."""

import asyncio
import json
from dataclasses import replace
from urllib.parse import urljoin, urlsplit

from aiohttp import ClientError, ClientSession, ClientTimeout, CookieJar
from yarl import URL

from .errors import (
    AuthenticationError,
    BrunataError,
    CaptchaRequired,
    ConnectionError,
    NoSupportedData,
    PortalFormatError,
)
from .models import MediumReadings
from .parser import (
    ORIGIN,
    OVERVIEW_PATH,
    PortalHTML,
    discover_media,
    parse_monthly,
    parse_property_average,
)

LOGIN_PATH = "/legacy/login"
POST_LOGIN_PATH = "/legacy/Account/Login"
REFRESH_PATH = "/legacy/account/refreshSession"
CURRENT_USER_PATH = "/legacy/spa/currentUser"
TENANCY_PATH = "/legacy/Nutzer/Nutzeinheiten"
MAX_RESPONSE_BYTES = 4 * 1024 * 1024


def _route_kind(url: str) -> str:
    """Describe redirects without returning URLs or query parameters."""
    return {
        "/legacy/login": "login_page",
        "/legacy/account/login": "login_handler",
        "/dashboard": "portal_landing",
        "/uvi/nutzer/index": "portal_shell",
        "/legacy/uvi/nutzer/index": "consumption_overview",
        "/legacy/account/refreshsession": "session_initialization",
        "/legacy/spa/currentuser": "user_context_initialization",
        "/legacy/nutzer/nutzeinheiten": "tenancy_initialization",
        "/nutzer/nutzeinheiten": "tenancy_shell",
    }.get(urlsplit(url).path.casefold(), "other")


def _server_error_category(body: str) -> str:
    """Return only fixed exception categories, never server text."""
    for marker, category in (
        ("NullReferenceException", "null_reference"),
        ("AntiForgeryException", "request_verification"),
        ("HttpRequestValidationException", "request_validation"),
        ("InvalidOperationException", "invalid_operation"),
    ):
        if marker in body:
            return category
    return "unspecified"


def create_cookie_jar() -> CookieJar:
    """Match browser cookie transmission; the legacy backend rejects octal quoting."""
    return CookieJar(quote_cookie=False)


def _login_category(message) -> str:
    """Map untrusted server text to a fixed label; never return the text."""
    if not isinstance(message, str):
        return "unspecified"
    text = message.casefold()
    if any(word in text for word in ("captcha", "sicherheitscode")):
        return "interactive_challenge"
    if any(
        word in text for word in ("csrf", "verification", "antiforgery", "anti-forgery")
    ):
        return "request_verification"
    if any(word in text for word in ("wartung", "maintenance")):
        return "maintenance"
    if any(word in text for word in ("gesperrt", "locked", "too many", "zu viele")):
        return "account_or_rate_limit"
    if any(
        word in text for word in ("passwort", "password", "credentials", "anmeldedaten")
    ):
        return "credential_or_form_error"
    return "unspecified"


class BrunataClient:
    """Own a private cookie session; never log account data or HTTP bodies."""

    def __init__(self, username: str, password: str, *, session=None):
        self._username = username
        self._password = password
        self._session = session
        self._owns_session = session is None
        self._lock = asyncio.Lock()
        self._diagnostics: dict[str, object] = {}
        self._session_verified = False

    @property
    def safe_diagnostics(self) -> dict[str, object]:
        """Return an allowlist, excluding account data, URLs and cookie values."""
        return {
            **self._diagnostics,
            "cookie_count": len(getattr(self._session, "cookie_jar", ())),
        }

    async def async_preflight(self) -> dict[str, object]:
        """Check public login markup and cookies without submitting credentials."""
        page = PortalHTML(await self._request("GET", LOGIN_PATH))
        return {
            **self.safe_diagnostics,
            "login_markup_found": page.is_login,
            "csrf_field_present": bool(page.csrf),
            "captcha_required": page.captcha,
        }

    def _cookie_diagnostics(self, url: str) -> dict[str, object]:
        """Inspect cookie applicability without returning names or values."""
        jar = getattr(self._session, "cookie_jar", None)
        if jar is None or not hasattr(jar, "filter_cookies"):
            return {}
        cookies = jar.filter_cookies(URL(url))
        names = [name.casefold() for name in cookies]
        return {
            "applicable_cookie_count": len(cookies),
            "auth_cookie_present": any(
                "applicationcookie" in name or name in (".aspxauth", ".aspnet.cookies")
                for name in names
            ),
            "session_cookie_present": any(
                name in ("asp.net_sessionid", ".aspnetcore.session") for name in names
            ),
            "quoted_cookie_count": sum(
                cookie.coded_value != cookie.value for cookie in cookies.values()
            ),
        }

    async def async_diagnose_session(self) -> list[dict[str, object]]:
        """Probe existing-session reads after failure; never submit credentials."""
        if self._session is None:
            return []
        original = self._diagnostics
        results = []
        try:
            # Match the public SPA's non-authentication iframe display preference.
            self._session.cookie_jar.update_cookies(
                {".contentOnly": "true"}, response_url=URL(ORIGIN)
            )
            for path in (CURRENT_USER_PATH, OVERVIEW_PATH):
                self._diagnostics = {}
                try:
                    body = await self._request(
                        "GET", path, ajax=path == CURRENT_USER_PATH
                    )
                    self._diagnostics["login_page_returned"] = PortalHTML(body).is_login
                    if path == CURRENT_USER_PATH:
                        try:
                            profile = json.loads(body)
                        except ValueError:
                            profile = None
                        self._diagnostics["tenant_context_present"] = (
                            isinstance(profile, dict)
                            and profile.get("Role") == "Tenant"
                        )
                except (AuthenticationError, ConnectionError, PortalFormatError):
                    pass
                results.append(self.safe_diagnostics)
        finally:
            self._diagnostics = original
        return results

    async def async_close(self):
        """Release the private session."""
        if self._owns_session and self._session is not None:
            await self._session.close()

    async def _request(self, method: str, path: str, *, data=None, ajax=False) -> str:
        """Follow safe GET redirects; never replay credentials across redirects."""
        if self._session is None:
            self._session = ClientSession(
                cookie_jar=create_cookie_jar(),
                timeout=ClientTimeout(total=30),
                headers={"User-Agent": "brunata-koeln-ha/0.1 (Home Assistant)"},
            )
        url = urljoin(ORIGIN, path)
        stage = {
            LOGIN_PATH: "login_page",
            POST_LOGIN_PATH: "credential_submission",
            OVERVIEW_PATH: "consumption_overview",
            REFRESH_PATH: "session_initialization",
            CURRENT_USER_PATH: "user_context_initialization",
            TENANCY_PATH: "tenancy_initialization",
        }.get(urlsplit(url).path, "consumption_detail")
        self._diagnostics.update(stage=stage, http_status=None)
        for _ in range(6):
            parsed = urlsplit(url)
            if (
                parsed.scheme != "https"
                or parsed.netloc != urlsplit(ORIGIN).netloc
                or parsed.username is not None
            ):
                raise PortalFormatError("Untrusted portal redirect")
            try:
                headers = {"X-Requested-With": "XMLHttpRequest"} if ajax else {}
                if method == "POST":
                    headers = {
                        "Origin": ORIGIN,
                        "Referer": urljoin(ORIGIN, LOGIN_PATH),
                        "Content-Type": (
                            "application/x-www-form-urlencoded; charset=UTF-8"
                        ),
                    }
                cookie_info = self._cookie_diagnostics(url)
                async with self._session.request(
                    method, url, data=data, headers=headers, allow_redirects=False
                ) as response:
                    self._diagnostics["http_status"] = response.status
                    trace = {
                        "stage": stage,
                        "route_kind": _route_kind(url),
                        "method": method,
                        "status": response.status,
                        **cookie_info,
                    }
                    history = self._diagnostics.setdefault("http_trace", [])
                    if len(history) < 20:
                        history.append(trace)
                    if method == "POST":
                        self._diagnostics["credential_post_http_status"] = (
                            response.status
                        )
                    if response.status in (301, 302, 303, 307, 308):
                        location = response.headers.get("Location")
                        if not location:
                            raise PortalFormatError("Portal redirect is missing")
                        if method == "POST" and response.status in (307, 308):
                            raise PortalFormatError("Credential replay was prevented")
                        url = urljoin(url, location)
                        trace["redirect_kind"] = _route_kind(url)
                        method, data = "GET", None
                        continue
                    if response.status in (401, 403):
                        raise AuthenticationError(
                            f"Portal authentication required (HTTP {response.status}; "
                            f"stage={stage})"
                        )
                    if response.status == 429 or response.status >= 500:
                        error_bytes = bytearray()
                        async for chunk in response.content.iter_chunked(65536):
                            error_bytes.extend(chunk[: 65536 - len(error_bytes)])
                            if len(error_bytes) >= 65536:
                                break
                        self._diagnostics["server_error_category"] = (
                            _server_error_category(
                                error_bytes.decode("utf-8", "replace")
                            )
                        )
                        raise ConnectionError(
                            f"Portal temporarily unavailable (HTTP {response.status}; "
                            f"stage={stage})"
                        )
                    if response.status != 200:
                        raise PortalFormatError(
                            f"Unexpected portal response (HTTP {response.status}; "
                            f"stage={stage})"
                        )
                    body = bytearray()
                    async for chunk in response.content.iter_chunked(65536):
                        body.extend(chunk)
                        if len(body) > MAX_RESPONSE_BYTES:
                            raise PortalFormatError(
                                "Portal response exceeds size limit"
                            )
                    return body.decode("utf-8", errors="replace")
            except (ClientError, TimeoutError):
                raise ConnectionError("Portal connection failed") from None
        raise PortalFormatError("Too many portal redirects")

    async def _login(self):
        """Submit the verified form once; do not retry rejected credentials."""
        self._session_verified = False
        page = PortalHTML(await self._request("GET", LOGIN_PATH))
        if page.captcha:
            raise CaptchaRequired("Interactive portal login required")
        if not page.csrf:
            raise PortalFormatError("Login verification field is missing")
        self._diagnostics["credential_submission_started"] = True
        response = await self._request(
            "POST",
            POST_LOGIN_PATH,
            data={
                "Username": self._username,
                "Password": self._password,
                "CaptchaInputText": "",
                "CaptchaDeText": page.captcha_token,
                "returnUrl": "/Dashboard",
                "__RequestVerificationToken": page.csrf,
            },
        )
        self._diagnostics["login_response_received"] = True
        try:
            result = json.loads(response)
        except ValueError:
            result = None
        if isinstance(result, dict) and "Fails" in result:
            fails = result["Fails"]
            category = _login_category(result.get("Message"))
            self._diagnostics["login_category"] = category
            if type(fails) is int and 0 <= fails <= 10000:
                self._diagnostics["failure_count"] = fails
            if category == "interactive_challenge" or (
                type(fails) is int and fails >= 2
            ):
                raise CaptchaRequired("Interactive portal login required")
            raise AuthenticationError(
                f"Portal login was not completed (category={category})"
            )
        page = PortalHTML(response)
        if page.captcha:
            raise CaptchaRequired("Interactive portal login required")
        if page.is_login:
            self._diagnostics["login_category"] = "login_page_returned"
            raise AuthenticationError("Portal returned the login page after submission")
        await self._initialize_portal()

    async def _initialize_portal(self):
        """Mirror the SPA's session/user setup and legacy iframe display cookie."""
        for path in (REFRESH_PATH, CURRENT_USER_PATH):
            source = await self._request("GET", path, ajax=True)
            if PortalHTML(source).is_login:
                raise AuthenticationError(
                    "Portal initialization requires authentication"
                )
            try:
                payload = json.loads(source)
            except ValueError:
                raise PortalFormatError(
                    "Portal initialization did not return JSON"
                ) from None
            if not isinstance(payload, dict):
                raise PortalFormatError("Invalid portal initialization response")
            if path == CURRENT_USER_PATH:
                if payload.get("ShowTermsOfServicePage"):
                    raise AuthenticationError(
                        "Complete the portal's required interactive review in a browser"
                    )
                if payload.get("Role") != "Tenant":
                    raise NoSupportedData(
                        "Only tenant accounts are currently supported"
                    )
        self._session.cookie_jar.update_cookies(
            {".contentOnly": "true"}, response_url=URL(ORIGIN)
        )
        # This endpoint establishes the tenant's session context before UVI access.
        source = await self._request("GET", TENANCY_PATH)
        page = PortalHTML(source)
        if page.is_login:
            raise AuthenticationError("Portal tenancy context requires authentication")
        if not discover_media(page):
            raise NoSupportedData(
                "No automatic tenancy context with supported media is available; "
                "explicit tenancy selection may be required"
            )
        self._diagnostics["tenancy_context_verified"] = True
        self._diagnostics["portal_bootstrap_complete"] = True

    async def _overview(self) -> PortalHTML:
        """Require advertised protected data, not just a successful redirect."""
        source = await self._request("GET", OVERVIEW_PATH)
        page = PortalHTML(source)
        if page.is_login:
            raise AuthenticationError("Portal authentication required")
        return page

    async def async_fetch(
        self, *, include_comparison: bool = False
    ) -> dict[str, MediumReadings]:
        """Discover available media and retrieve the selected tenancy's months."""
        async with self._lock:
            self._diagnostics = {
                "credential_submission_started": False,
                "login_response_received": False,
                "protected_overview_verified": False,
                "portal_bootstrap_complete": False,
                "tenancy_context_verified": False,
            }
            if not self._session_verified:
                await self._login()
                overview = await self._overview()
            else:
                try:
                    overview = await self._overview()
                except AuthenticationError:
                    await self._login()
                    overview = await self._overview()
            links = discover_media(overview)
            if not links:
                raise NoSupportedData("No supported consumption media available")
            self._session_verified = True
            self._diagnostics["protected_overview_verified"] = True
            readings = {}
            for medium, path in links.items():
                try:
                    source = await self._request("GET", path)
                except AuthenticationError:
                    self._session_verified = False
                    raise
                if PortalHTML(source).is_login:
                    self._session_verified = False
                    raise AuthenticationError("Portal session expired")
                readings[medium] = replace(
                    parse_monthly(source, medium),
                    forecasts=parse_monthly(source, medium, forecast=True).readings,
                )
            if include_comparison:
                comparison_path = "/legacy/Uvi/Nutzer/LiegenschaftCompare"
                advertised = any(
                    urlsplit(urljoin(ORIGIN, link)).path == comparison_path
                    and urlsplit(urljoin(ORIGIN, link)).netloc
                    == urlsplit(ORIGIN).netloc
                    for link in overview.links
                )
                if advertised:
                    for medium in readings:
                        try:
                            source = await self._request(
                                "GET", f"{comparison_path}?mediumType={medium}"
                            )
                            if PortalHTML(source).is_login:
                                raise AuthenticationError("Portal session expired")
                            average = parse_property_average(source, medium)
                            readings[medium] = replace(
                                readings[medium],
                                property_average=average,
                                property_forecasts=parse_property_average(
                                    source, medium, forecast=True
                                ),
                            )
                        except AuthenticationError:
                            self._session_verified = False
                            raise
                        except BrunataError:
                            # Keep actual consumption when optional comparison fails.
                            self._diagnostics["comparison_unavailable"] = True
            return readings
