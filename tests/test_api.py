"""Verify cold login, session reuse and controlled failures."""

import unittest

from brunata_client.api import BrunataClient
from brunata_client.errors import (
    AuthenticationError,
    CaptchaRequired,
    ConnectionError,
    NoSupportedData,
    PortalFormatError,
)

from .helpers import LOGIN, OVERVIEW, FakeResponse, FakeSession, chart


def logged_in(*responses):
    """A synthetic successful login followed by protected responses."""
    return [
        FakeResponse(LOGIN),
        FakeResponse("<main>Portal landing</main>"),
        FakeResponse('{"remaining":60000}'),
        FakeResponse('{"Role":"Tenant","ShowTermsOfServicePage":false}'),
        FakeResponse(OVERVIEW),
        *responses,
    ]


class ClientTests(unittest.IsolatedAsyncioTestCase):
    async def test_login_precedes_consumption_and_session_is_reused(self):
        session = FakeSession(
            logged_in(
                FakeResponse(OVERVIEW),
                FakeResponse(chart()),
                FakeResponse(OVERVIEW),
                FakeResponse(chart()),
            )
        )
        client = BrunataClient("user", "password", session=session)
        data = await client.async_fetch()
        self.assertEqual(data["Heizung"].latest.value, 12.5)
        self.assertTrue(session.calls[0][1].endswith("/legacy/login"))
        self.assertEqual(session.calls[1][0], "POST")
        self.assertTrue(session.calls[4][1].endswith("/legacy/Nutzer/Nutzeinheiten"))
        self.assertTrue(session.calls[5][1].endswith("/legacy/Uvi/Nutzer/Index"))
        self.assertTrue(client.safe_diagnostics["protected_overview_verified"])
        await client.async_fetch()
        self.assertEqual(sum(c[0] == "POST" for c in session.calls), 1)
        self.assertFalse(client.safe_diagnostics["credential_submission_started"])

    async def test_login_headers_wire_names_and_default_landing(self):
        session = FakeSession(
            [
                FakeResponse(LOGIN),
                FakeResponse(status=302, headers={"Location": "/portal"}),
                FakeResponse("<main>Portal landing</main>"),
                FakeResponse('{"remaining":60000}'),
                FakeResponse('{"Role":"Tenant","ShowTermsOfServicePage":false}'),
                FakeResponse(OVERVIEW),
                FakeResponse(OVERVIEW),
                FakeResponse(chart()),
            ]
        )
        await BrunataClient("user", "password", session=session).async_fetch()
        method, url, arguments = session.calls[1]
        self.assertEqual(method, "POST")
        self.assertTrue(url.endswith("/legacy/Account/Login"))
        self.assertEqual(arguments["data"]["Username"], "user")
        self.assertEqual(
            arguments["data"]["__RequestVerificationToken"], "synthetic-csrf"
        )
        self.assertEqual(arguments["data"]["returnUrl"], "/Dashboard")
        self.assertEqual(
            arguments["headers"]["Origin"], "https://online.brunata-koeln.de"
        )
        self.assertEqual(
            arguments["headers"]["Referer"],
            "https://online.brunata-koeln.de/legacy/login",
        )
        self.assertIsNone(session.calls[2][2]["data"])
        self.assertEqual(session.calls[2][2]["headers"], {})

    async def test_credentials_rejected_without_retry_or_response_leak(self):
        session = FakeSession(
            [
                FakeResponse(LOGIN),
                FakeResponse('{"Fails":1,"Message":"synthetic-secret"}'),
            ]
        )
        client = BrunataClient("user", "password", session=session)
        with self.assertRaises(AuthenticationError) as raised:
            await client.async_fetch()
        self.assertNotIn("synthetic-secret", str(raised.exception))
        self.assertEqual(len(session.calls), 2)

    async def test_captcha_prevents_credential_submission(self):
        session = FakeSession(
            [FakeResponse(LOGIN.replace('Attempts="0"', 'Attempts="2"'))]
        )
        with self.assertRaises(CaptchaRequired):
            await BrunataClient("user", "password", session=session).async_fetch()
        self.assertTrue(all(c[0] == "GET" for c in session.calls))

    async def test_cross_origin_redirect_is_not_followed(self):
        session = FakeSession(
            [FakeResponse(status=302, headers={"Location": "https://other.invalid/"})]
        )
        with self.assertRaises(PortalFormatError):
            await BrunataClient("user", "password", session=session).async_fetch()
        self.assertEqual(len(session.calls), 1)

    async def test_post_307_never_replays_credentials(self):
        session = FakeSession(
            [
                FakeResponse(LOGIN),
                FakeResponse(status=307, headers={"Location": "/another"}),
            ]
        )
        with self.assertRaises(PortalFormatError):
            await BrunataClient("user", "password", session=session).async_fetch()
        self.assertEqual(len(session.calls), 2)

    async def test_public_login_outage_does_not_submit_credentials(self):
        for status in [429, 503]:
            session = FakeSession([FakeResponse(status=status)])
            client = BrunataClient("user", "password", session=session)
            with self.subTest(status=status), self.assertRaises(ConnectionError):
                await client.async_fetch()
            self.assertFalse(client.safe_diagnostics["credential_submission_started"])
            self.assertEqual(len(session.calls), 1)

    async def test_no_data_is_not_zero(self):
        session = FakeSession(logged_in(FakeResponse("<html>no readings</html>")))
        with self.assertRaises(NoSupportedData):
            await BrunataClient("user", "password", session=session).async_fetch()

    async def test_expired_session_on_medium_is_an_auth_error(self):
        session = FakeSession(logged_in(FakeResponse(OVERVIEW), FakeResponse(LOGIN)))
        with self.assertRaises(AuthenticationError):
            await BrunataClient("user", "password", session=session).async_fetch()

    async def test_expired_verified_session_reauthenticates_once(self):
        session = FakeSession(
            logged_in(
                FakeResponse(OVERVIEW),
                FakeResponse(chart()),
                FakeResponse(LOGIN),
                *logged_in(FakeResponse(OVERVIEW), FakeResponse(chart())),
            )
        )
        client = BrunataClient("user", "password", session=session)
        await client.async_fetch()
        await client.async_fetch()
        self.assertEqual(sum(c[0] == "POST" for c in session.calls), 2)

    async def test_preflight_never_submits_credentials(self):
        session = FakeSession([FakeResponse(LOGIN)])
        client = BrunataClient("private-user", "private-password", session=session)
        diagnostics = await client.async_preflight()
        self.assertEqual(len(session.calls), 1)
        self.assertIsNone(session.calls[0][2]["data"])
        self.assertTrue(diagnostics["csrf_field_present"])
        for secret in ("synthetic-csrf", "private-user", "private-password"):
            self.assertNotIn(secret, str(diagnostics))

    async def test_server_error_includes_safe_status_and_stage(self):
        session = FakeSession([FakeResponse("private-body", status=503)])
        client = BrunataClient("user", "password", session=session)
        with self.assertRaises(ConnectionError) as raised:
            await client.async_preflight()
        self.assertIn("HTTP 503", str(raised.exception))
        self.assertIn("stage=login_page", str(raised.exception))
        self.assertNotIn("private-body", str(raised.exception))

    async def test_overview_500_distinguishes_post_login_failure(self):
        session = FakeSession(logged_in(FakeResponse(status=500)))
        client = BrunataClient("user", "password", session=session)
        with self.assertRaises(ConnectionError):
            await client.async_fetch()
        diagnostics = client.safe_diagnostics
        self.assertTrue(diagnostics["credential_submission_started"])
        self.assertTrue(diagnostics["login_response_received"])
        self.assertFalse(diagnostics["protected_overview_verified"])
        self.assertEqual(diagnostics["stage"], "consumption_overview")
        self.assertEqual(sum(c[0] == "POST" for c in session.calls), 1)

    async def test_verification_failure_does_not_claim_wrong_password(self):
        session = FakeSession(
            [
                FakeResponse(LOGIN),
                FakeResponse(
                    '{"Fails":0,"Message":"RequestVerificationToken private-body"}'
                ),
            ]
        )
        client = BrunataClient("user", "password", session=session)
        with self.assertRaises(AuthenticationError) as raised:
            await client.async_fetch()
        self.assertEqual(
            client.safe_diagnostics["login_category"], "request_verification"
        )
        self.assertNotIn("credentials rejected", str(raised.exception))
        self.assertNotIn("private-body", str(client.safe_diagnostics))

    async def test_captcha_field_matches_frontend_model(self):
        login = LOGIN.replace(
            'faildAttempts="0"', 'faildAttempts="0" captchaToken="synthetic-captcha"'
        )
        session = FakeSession([FakeResponse(login), FakeResponse('{"Fails":1}')])
        client = BrunataClient("user", "password", session=session)
        with self.assertRaises(AuthenticationError):
            await client.async_fetch()
        self.assertEqual(
            session.calls[1][2]["data"]["CaptchaDeText"], "synthetic-captcha"
        )
        self.assertNotIn("synthetic-captcha", str(client.safe_diagnostics))

    async def test_interactive_challenge_stops_before_retry(self):
        session = FakeSession(
            [
                FakeResponse(LOGIN),
                FakeResponse('{"Fails":0,"Message":"Captcha required"}'),
            ]
        )
        with self.assertRaises(CaptchaRequired):
            await BrunataClient("user", "password", session=session).async_fetch()
        self.assertEqual(len(session.calls), 2)

    async def test_bootstrap_matches_spa_requests_and_cookie_scope(self):
        session = FakeSession(logged_in(FakeResponse(OVERVIEW), FakeResponse(chart())))
        client = BrunataClient("user", "password", session=session)
        await client.async_fetch()
        self.assertTrue(session.calls[2][1].endswith("/account/refreshSession"))
        self.assertTrue(session.calls[3][1].endswith("/spa/currentUser"))
        for index in (2, 3):
            self.assertEqual(
                session.calls[index][2]["headers"]["X-Requested-With"],
                "XMLHttpRequest",
            )
        self.assertEqual(session.cookie_jar[".contentOnly"], "true")
        self.assertEqual(
            str(session.cookie_jar.response_url), "https://online.brunata-koeln.de"
        )
        self.assertTrue(client.safe_diagnostics["portal_bootstrap_complete"])

    async def test_bootstrap_failure_stops_before_consumption(self):
        session = FakeSession(
            [
                FakeResponse(LOGIN),
                FakeResponse("<main>Portal</main>"),
                FakeResponse(status=500),
            ]
        )
        client = BrunataClient("user", "password", session=session)
        with self.assertRaises(ConnectionError):
            await client.async_fetch()
        self.assertEqual(client.safe_diagnostics["stage"], "session_initialization")
        self.assertFalse(client.safe_diagnostics["portal_bootstrap_complete"])
        self.assertFalse(any(c[1].endswith("/Uvi/Nutzer/Index") for c in session.calls))

    async def test_bootstrap_html_login_is_not_a_verified_session(self):
        session = FakeSession(
            [
                FakeResponse(LOGIN),
                FakeResponse("<main>Portal</main>"),
                FakeResponse(LOGIN),
            ]
        )
        with self.assertRaises(AuthenticationError):
            await BrunataClient("user", "password", session=session).async_fetch()

    async def test_bootstrap_rejects_unsupported_account_role(self):
        session = FakeSession(
            [
                FakeResponse(LOGIN),
                FakeResponse("<main>Portal</main>"),
                FakeResponse('{"remaining":60000}'),
                FakeResponse('{"Role":"MainUser","Name":"private-name"}'),
            ]
        )
        client = BrunataClient("user", "password", session=session)
        with self.assertRaises(NoSupportedData):
            await client.async_fetch()
        self.assertNotIn("private-name", str(client.safe_diagnostics))

    async def test_required_terms_review_is_never_accepted_automatically(self):
        session = FakeSession(
            [
                FakeResponse(LOGIN),
                FakeResponse("<main>Portal</main>"),
                FakeResponse('{"remaining":60000}'),
                FakeResponse('{"Role":"Tenant","ShowTermsOfServicePage":true}'),
            ]
        )
        with self.assertRaises(AuthenticationError):
            await BrunataClient("user", "password", session=session).async_fetch()
        self.assertFalse(any("AcceptTerms" in c[1] for c in session.calls))

    async def test_bootstrap_rejects_malformed_json_without_body_leak(self):
        session = FakeSession(
            [
                FakeResponse(LOGIN),
                FakeResponse("<main>Portal</main>"),
                FakeResponse("private-server-message"),
            ]
        )
        with self.assertRaises(PortalFormatError) as raised:
            await BrunataClient("user", "password", session=session).async_fetch()
        self.assertNotIn("private-server-message", str(raised.exception))
