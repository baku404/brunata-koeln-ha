"""Exercise real HTTPS, redirects and cookies against a local synthetic portal."""

import ssl
import unittest
from unittest.mock import patch

import aiohttp
import trustme
from aiohttp import web
from brunata_client.api import BrunataClient, create_cookie_jar
from brunata_client.errors import ConnectionError

from .helpers import LOGIN, OVERVIEW, chart

AUTH_VALUE = "synthetic-auth/with+symbols="
SESSION_VALUE = "synthetic-session"


class HTTPTransportTests(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self):
        self.posts = 0
        self.fail_refresh = False
        self.auth_path = "/"
        self.tenancy_selected = False
        self.requires_choice = False
        ca = trustme.CA()
        certificate = ca.issue_cert("localhost")
        server_tls = ssl.SSLContext(ssl.PROTOCOL_TLS_SERVER)
        certificate.configure_cert(server_tls)
        client_tls = ssl.create_default_context()
        ca.configure_trust(client_tls)
        self.client_tls = client_tls
        app = web.Application()
        app.router.add_get("/legacy/login", self.login_page)
        app.router.add_post("/legacy/Account/Login", self.login_post)
        app.router.add_get("/Dashboard", self.landing)
        app.router.add_get("/legacy/account/refreshSession", self.refresh)
        app.router.add_get("/legacy/spa/currentUser", self.current_user)
        app.router.add_get("/legacy/Nutzer/Nutzeinheiten", self.select_tenancy)
        app.router.add_get("/nutzer/nutzeinheiten", self.landing)
        app.router.add_get("/legacy/Uvi/Nutzer/Index", self.overview)
        app.router.add_get("/legacy/Uvi/Nutzer/MonthCompare", self.monthly)
        self.runner = web.AppRunner(app)
        await self.runner.setup()
        site = web.TCPSite(self.runner, "127.0.0.1", 0, ssl_context=server_tls)
        await site.start()
        port = self.runner.addresses[0][1]
        self.origin_patch = patch(
            "brunata_client.api.ORIGIN", f"https://localhost:{port}"
        )
        self.origin_patch.start()
        self.session = aiohttp.ClientSession(
            connector=aiohttp.TCPConnector(ssl=client_tls),
            cookie_jar=create_cookie_jar(),
        )
        self.client = BrunataClient(
            "synthetic-user", "synthetic-password", session=self.session
        )

    async def asyncTearDown(self):
        await self.session.close()
        await self.runner.cleanup()
        self.origin_patch.stop()

    def authenticated(self, request):
        return (
            request.cookies.get(".AspNet.ApplicationCookie") == AUTH_VALUE
            and request.cookies.get("ASP.NET_SessionId") == SESSION_VALUE
            and "PortalContext=synthetic,context" in request.headers.get("Cookie", "")
        )

    async def login_page(self, request):
        response = web.Response(text=LOGIN, content_type="text/html")
        response.set_cookie("ASP.NET_SessionId", SESSION_VALUE, path="/", secure=True)
        response.set_cookie(
            "__RequestVerificationToken", "synthetic-csrf", path="/", secure=True
        )
        return response

    async def login_post(self, request):
        self.posts += 1
        form = await request.post()
        self.assertEqual(form["Password"], "synthetic-password")
        self.assertEqual(form["__RequestVerificationToken"], "synthetic-csrf")
        self.assertEqual(
            request.cookies["__RequestVerificationToken"], "synthetic-csrf"
        )
        response = web.HTTPFound("/Dashboard?token=synthetic-private-query")
        response.set_cookie(
            ".AspNet.ApplicationCookie",
            AUTH_VALUE,
            path=self.auth_path,
            secure=True,
            httponly=True,
        )
        response.set_cookie("PortalContext", "synthetic,context", path="/", secure=True)
        raise response

    async def landing(self, request):
        return web.Response(text="<main>Portal shell</main>", content_type="text/html")

    async def refresh(self, request):
        if self.fail_refresh or not self.authenticated(request):
            return web.Response(
                status=500, text="NullReferenceException synthetic-private-body"
            )
        self.assertEqual(request.headers["X-Requested-With"], "XMLHttpRequest")
        return web.json_response({"remaining": 60000})

    async def current_user(self, request):
        if not self.authenticated(request):
            return web.Response(
                status=500, text="NullReferenceException synthetic-private-body"
            )
        return web.json_response({"Role": "Tenant", "Name": "synthetic-private-name"})

    async def select_tenancy(self, request):
        if not self.authenticated(request):
            return web.Response(status=401)
        if self.requires_choice:
            return web.Response(text="<form>Select a unit</form>")
        self.tenancy_selected = True
        raise web.HTTPFound("/legacy/Uvi/Nutzer/Index")

    async def overview(self, request):
        if not self.tenancy_selected:
            raise web.HTTPFound("/nutzer/nutzeinheiten")
        if (
            not self.authenticated(request)
            or request.cookies.get(".contentOnly") != "true"
        ):
            return web.Response(status=500)
        return web.Response(text=OVERVIEW, content_type="text/html")

    async def monthly(self, request):
        self.assertTrue(self.authenticated(request))
        return web.Response(text=chart(), content_type="text/html")

    async def test_real_tls_cookies_redirects_and_monthly_fetch(self):
        data = await self.client.async_fetch()
        self.assertEqual(data["Heizung"].latest.value, 12.5)
        self.assertEqual(self.posts, 1)
        trace = self.client.safe_diagnostics["http_trace"]
        refresh = next(
            item for item in trace if item["stage"] == "session_initialization"
        )
        self.assertTrue(refresh["auth_cookie_present"])
        self.assertTrue(refresh["session_cookie_present"])
        self.assertNotIn("synthetic-private-query", str(trace))
        self.assertNotIn(AUTH_VALUE, str(trace))
        self.assertEqual(refresh["quoted_cookie_count"], 0)
        self.assertTrue(self.tenancy_selected)
        self.assertTrue(self.client.safe_diagnostics["tenancy_context_verified"])

    async def test_default_quoting_reproduces_the_legacy_cookie_failure(self):
        await self.session.close()
        self.session = aiohttp.ClientSession(
            connector=aiohttp.TCPConnector(ssl=self.client_tls),
            cookie_jar=aiohttp.CookieJar(),
        )
        self.client = BrunataClient(
            "synthetic-user", "synthetic-password", session=self.session
        )
        with self.assertRaises(ConnectionError):
            await self.client.async_fetch()
        trace = self.client.safe_diagnostics["http_trace"][-1]
        self.assertEqual(trace["status"], 500)
        self.assertGreater(trace["quoted_cookie_count"], 0)

    async def test_explicit_unit_choice_is_not_guessed(self):
        from brunata_client.errors import NoSupportedData

        self.requires_choice = True
        with self.assertRaises(NoSupportedData):
            await self.client.async_fetch()
        self.assertFalse(self.tenancy_selected)

    async def test_cookie_scope_failure_is_visible_without_disclosing_values(self):
        self.auth_path = "/unrelated"
        with self.assertRaises(ConnectionError):
            await self.client.async_fetch()
        diagnostics = self.client.safe_diagnostics
        trace = diagnostics["http_trace"][-1]
        self.assertFalse(trace["auth_cookie_present"])
        self.assertTrue(trace["session_cookie_present"])
        self.assertEqual(diagnostics["server_error_category"], "null_reference")
        self.assertNotIn("synthetic-private-body", str(diagnostics))

    async def test_failed_auxiliary_refresh_can_be_diagnosed_without_relogin(self):
        self.fail_refresh = True
        with self.assertRaises(ConnectionError):
            await self.client.async_fetch()
        original = self.client.safe_diagnostics
        probes = await self.client.async_diagnose_session()
        self.assertEqual(self.posts, 1)
        self.assertTrue(probes[0]["tenant_context_present"])
        self.assertEqual(probes[1]["http_status"], 200)
        self.assertEqual(
            self.client.safe_diagnostics["http_trace"], original["http_trace"]
        )
        self.assertEqual(self.client.safe_diagnostics["stage"], original["stage"])
        self.assertNotIn("synthetic-private-name", str(probes))
