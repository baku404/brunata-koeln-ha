"""Optional comparison transport must preserve actual own readings."""

import json
import unittest

from brunata_client.api import BrunataClient

from .helpers import OVERVIEW, FakeResponse, FakeSession, chart
from .test_api import logged_in


class ComparisonTransportTests(unittest.IsolatedAsyncioTestCase):
    async def test_advertised_comparison_is_fetched_and_parsed(self):
        overview = (
            OVERVIEW + '<a href="/legacy/Uvi/Nutzer/LiegenschaftCompare">Compare</a>'
        )
        average = chart(unit="kWh je Nutzeinheit").replace(
            json.dumps("Ausgewählter Abrechnungszeitraum"),
            json.dumps("Durchschnitt der Liegenschaft"),
        )
        session = FakeSession(
            logged_in(
                FakeResponse(overview), FakeResponse(chart()), FakeResponse(average)
            )
        )
        result = await BrunataClient(
            "synthetic", "password", session=session
        ).async_fetch(include_comparison=True)
        self.assertEqual(result["Heizung"].property_average[0].value, 12.5)
        self.assertIn("LiegenschaftCompare?mediumType=Heizung", session.calls[-1][1])

    async def test_malformed_optional_comparison_does_not_discard_consumption(self):
        overview = (
            OVERVIEW + '<a href="/legacy/Uvi/Nutzer/LiegenschaftCompare">Compare</a>'
        )
        session = FakeSession(
            logged_in(
                FakeResponse(overview),
                FakeResponse(chart()),
                FakeResponse("<main>No comparison</main>"),
            )
        )
        client = BrunataClient("synthetic", "password", session=session)
        result = await client.async_fetch(include_comparison=True)
        self.assertEqual(result["Heizung"].latest.value, 12.5)
        self.assertEqual(result["Heizung"].property_average, ())
        self.assertTrue(client.safe_diagnostics["comparison_unavailable"])
