"""Protect measurement semantics against portal schema changes."""

import unittest
from datetime import date

from brunata_client.errors import PortalFormatError
from brunata_client.parser import PortalHTML, discover_media, parse_monthly

from .helpers import FEBRUARY, JANUARY, LOGIN, OVERVIEW, chart


class ParserTests(unittest.TestCase):
    def test_actual_values_exclude_estimates_and_previous_period(self):
        data = parse_monthly(chart(), "Heizung", date(2025, 4, 1))
        self.assertEqual(len(data.readings), 1)
        self.assertEqual(data.latest.value, 12.5)
        self.assertEqual(data.latest.month, date(2025, 1, 1))

    def test_zero_is_a_reading_but_null_is_not(self):
        points = [
            {"x": JANUARY, "y": 0, "isHochrechnung": False},
            {"x": FEBRUARY, "y": None, "isHochrechnung": False},
        ]
        data = parse_monthly(chart(points), "Heizung", date(2025, 4, 1))
        self.assertEqual(data.latest.value, 0)

    def test_current_and_future_months_are_excluded(self):
        self.assertIsNone(parse_monthly(chart(), "Heizung", date(2025, 1, 15)).latest)

    def test_berlin_midnight_is_not_previous_utc_month(self):
        reading = parse_monthly(chart(), "Heizung", date(2025, 4, 1)).latest
        self.assertEqual(reading.month, date(2025, 1, 1))

    def test_missing_estimate_flag_fails_closed(self):
        with self.assertRaises(PortalFormatError):
            parse_monthly(chart([{"x": JANUARY, "y": 12}]), "Heizung")

    def test_non_finite_and_boolean_readings_are_rejected(self):
        for value in [float("nan"), float("inf"), True, "12"]:
            with self.subTest(value=value), self.assertRaises(PortalFormatError):
                parse_monthly(
                    chart([{"x": JANUARY, "y": value, "isHochrechnung": False}]),
                    "Heizung",
                )

    def test_duplicate_conflicts_are_rejected(self):
        points = [
            {"x": JANUARY, "y": 1, "isHochrechnung": False},
            {"x": JANUARY, "y": 2, "isHochrechnung": False},
        ]
        with self.assertRaises(PortalFormatError):
            parse_monthly(chart(points), "Heizung")

    def test_unknown_and_malformed_units_are_rejected(self):
        for unit in ["units", None, []]:
            with self.subTest(unit=unit), self.assertRaises(PortalFormatError):
                parse_monthly(chart(unit=unit), "Heizung")

    def test_water_volume_remains_volume(self):
        data = parse_monthly(chart(unit="m³", medium="Kaltwasser"), "Kaltwasser")
        self.assertEqual(data.latest.unit, "m³")

    def test_wrong_medium_is_rejected(self):
        with self.assertRaises(PortalFormatError):
            parse_monthly(chart(), "Warmwasser")

    def test_missing_or_broken_chart_is_rejected(self):
        for source in [
            "<html>maintenance</html>",
            '<script id="chart-data-a">'
            '{"mediumType":"Heizung","series":[bad]}</script>',
        ]:
            with self.subTest(source=source), self.assertRaises(PortalFormatError):
                parse_monthly(source, "Heizung")

    def test_only_advertised_same_origin_medium_links_are_used(self):
        source = OVERVIEW + (
            '<a href="https://other.invalid/legacy/Uvi/Nutzer/MonthCompare'
            '?mediumType=Warmwasser">bad</a>'
            '<a href="/legacy/Uvi/Nutzer/MonthCompare?mediumType=Unknown">bad</a>'
        )
        self.assertEqual(list(discover_media(PortalHTML(source))), ["Heizung"])

    def test_login_token_extraction_and_captcha_detection(self):
        page = PortalHTML(LOGIN)
        self.assertEqual(page.csrf, "synthetic-csrf")
        self.assertTrue(page.is_login)
        self.assertFalse(page.captcha)
        self.assertTrue(
            PortalHTML(LOGIN.replace('Attempts="0"', 'Attempts="2"')).captcha
        )
