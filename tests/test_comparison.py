"""Validate synthetic property-average data without retaining personal labels."""

import json
import unittest
from datetime import date

from brunata_client.errors import PortalFormatError
from brunata_client.parser import parse_property_average

from .helpers import chart


class ComparisonTests(unittest.TestCase):
    def source(self):
        return chart(unit="kWh je Nutzeinheit").replace(
            json.dumps("Ausgewählter Abrechnungszeitraum"),
            json.dumps("Durchschnitt der Liegenschaft"),
        )

    def test_average_excludes_estimates(self):
        rows = parse_property_average(self.source(), "Heizung", date(2026, 1, 1))
        self.assertEqual(len(rows), 1)
        self.assertEqual(rows[0].unit, "kWh")
        self.assertEqual(rows[0].value, 12.5)

    def test_personal_series_is_never_used_as_average(self):
        with self.assertRaises(PortalFormatError):
            parse_property_average(
                self.source().replace(
                    "Durchschnitt der Liegenschaft", "Synthetic private label"
                ),
                "Heizung",
            )

    def test_unsupported_normalization_and_wrong_medium_fail(self):
        for source in (
            self.source().replace("kWh je Nutzeinheit", "kWh je m²"),
            self.source().replace('"Heizung"', '"Warmwasser"'),
        ):
            with self.assertRaises(PortalFormatError):
                parse_property_average(source, "Heizung")
