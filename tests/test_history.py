"""Monthly imports preserve totals, dates and correction identity."""

import unittest
from datetime import date
from zoneinfo import ZoneInfo

from brunata_client.history import monthly_statistics
from brunata_client.models import MonthlyReading


class HistoryTests(unittest.TestCase):
    def test_repeat_and_correction_overwrite_same_timestamps(self):
        data = (
            MonthlyReading(date(2026, 1, 1), 10, "kWh"),
            MonthlyReading(date(2026, 2, 1), 20, "kWh"),
        )
        initial = monthly_statistics(data, 2026)
        self.assertEqual(initial, monthly_statistics(data, 2026))
        corrected = monthly_statistics(
            (MonthlyReading(date(2026, 1, 1), 15, "kWh"), data[1]), 2026
        )
        self.assertEqual([x["start"] for x in initial], [x["start"] for x in corrected])
        self.assertEqual(corrected[-1]["sum"], 35)

    def test_dst_month_end_stays_in_source_month(self):
        for month in (3, 10, 12):
            rows = monthly_statistics(
                (MonthlyReading(date(2026, month, 1), 9, "kWh"),), 2026
            )
            self.assertEqual(
                rows[-1]["start"].astimezone(ZoneInfo("Europe/Berlin")).month, month
            )
            self.assertEqual(rows[-1]["sum"] - rows[0]["sum"], 9)
            self.assertEqual(
                rows[-1]["start"].astimezone(ZoneInfo("Europe/Berlin")).hour, 23
            )

    def test_missing_month_is_not_zero(self):
        rows = monthly_statistics(
            (
                MonthlyReading(date(2026, 1, 1), 0, "kWh"),
                MonthlyReading(date(2026, 3, 1), 7, "kWh"),
            ),
            2026,
        )
        self.assertEqual(len(rows), 2)
        self.assertEqual(rows[-1]["sum"], 0)

    def test_previous_year_is_excluded(self):
        self.assertEqual(
            monthly_statistics((MonthlyReading(date(2025, 1, 1), 1, "kWh"),), 2026), []
        )

    def test_duplicates_units_and_negative_values_are_rejected(self):
        jan = MonthlyReading(date(2026, 1, 1), 10, "kWh")
        for data in (
            (jan, jan),
            (jan, MonthlyReading(date(2026, 2, 1), 1, "m³")),
            (MonthlyReading(date(2026, 1, 1), -1, "kWh"),),
        ):
            with self.assertRaises(ValueError):
                monthly_statistics(data, 2026)
