"""Forecasts enrich only daily history and are replaced by actual months."""

import unittest
from datetime import date, datetime
from zoneinfo import ZoneInfo

from brunata_client.history import daily_average_statistics
from brunata_client.models import MediumReadings, MonthlyReading, daily_sources
from brunata_client.parser import parse_monthly, parse_property_average

from .helpers import chart


class ForecastTests(unittest.TestCase):
    def test_parser_separates_actual_current_and_future_forecasts(self):
        berlin = ZoneInfo("Europe/Berlin")
        points = [
            {
                "x": datetime(2026, m, 1, tzinfo=berlin).timestamp() * 1000,
                "y": 31,
                "isHochrechnung": m != 1,
            }
            for m in (1, 2, 3)
        ]
        source = chart(points)
        self.assertEqual(
            [
                r.month.month
                for r in parse_monthly(source, "Heizung", date(2026, 2, 10)).readings
            ],
            [1],
        )
        self.assertEqual(
            [
                r.month.month
                for r in parse_monthly(
                    source, "Heizung", date(2026, 2, 10), forecast=True
                ).readings
            ],
            [2],
        )
        import json

        comparison = chart(points, unit="kWh je Nutzeinheit").replace(
            json.dumps("Ausgewählter Abrechnungszeitraum"),
            json.dumps("Durchschnitt der Liegenschaft"),
        )
        self.assertEqual(
            [
                r.month.month
                for r in parse_property_average(
                    comparison, "Heizung", date(2026, 2, 10), forecast=True
                )
            ],
            [2],
        )

    def test_forecast_replaced_without_affecting_actual_sources(self):
        jan = MonthlyReading(date(2026, 1, 1), 31, "kWh")
        forecast = MonthlyReading(date(2026, 2, 1), 56, "kWh")
        data = MediumReadings("Heizung", (jan,), forecasts=(forecast,))
        before = daily_average_statistics(
            daily_sources(data),
            2026,
            as_of=datetime(2026, 2, 10, 12, tzinfo=ZoneInfo("Europe/Berlin")),
        )
        self.assertEqual(data.latest, jan)
        self.assertEqual(before[-1]["sum"], 51)
        self.assertTrue(
            all(
                x["start"]
                <= datetime(2026, 2, 10, 12, tzinfo=ZoneInfo("Europe/Berlin"))
                for x in before
            )
        )
        actual = MonthlyReading(forecast.month, 28, "kWh")
        final_data = MediumReadings("Heizung", (jan, actual), forecasts=(forecast,))
        selected = daily_sources(final_data)
        self.assertEqual(selected[-1], actual)
        final = daily_average_statistics(
            selected, 2026, as_of=datetime(2026, 3, 1, tzinfo=ZoneInfo("Europe/Berlin"))
        )
        self.assertEqual(final[-1]["sum"], 59)
        # Every provisional timestamp is updated by the actual import.
        self.assertTrue({r["start"] for r in before} <= {r["start"] for r in final})
        self.assertEqual(final_data.readings, (jan, actual))

    def test_current_day_timestamps_are_stable_and_zero_prognosis_is_valid(self):
        reading = MonthlyReading(date(2026, 2, 1), 0, "kWh")
        timezone = ZoneInfo("Europe/Berlin")
        morning = daily_average_statistics(
            (reading,), 2026, as_of=datetime(2026, 2, 1, 0, tzinfo=timezone)
        )
        evening = daily_average_statistics(
            (reading,), 2026, as_of=datetime(2026, 2, 1, 20, tzinfo=timezone)
        )
        self.assertEqual(morning, evening)
        self.assertEqual(len(morning), 1)
        self.assertEqual(morning[0]["sum"], 0)
