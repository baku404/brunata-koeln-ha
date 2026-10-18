"""Calendar-day allocations preserve actual monthly totals across DST."""

import unittest
from datetime import date
from zoneinfo import ZoneInfo

from brunata_client.history import daily_average_statistics
from brunata_client.models import MonthlyReading


class DailyHistoryTests(unittest.TestCase):
    def test_month_total_and_equal_days_including_dst(self):
        for year, month, days in (
            (2026, 3, 31),
            (2026, 10, 31),
            (2024, 2, 29),
            (2026, 2, 28),
        ):
            reading = MonthlyReading(date(year, month, 1), 70, "kWh")
            rows = daily_average_statistics((reading,), year)
            self.assertEqual(len(rows), days * 2)
            self.assertEqual(rows[-1]["sum"], 70)
            self.assertEqual(len({row["start"] for row in rows}), len(rows))
            for start, end in zip(rows[::2], rows[1::2], strict=True):
                self.assertAlmostEqual(end["sum"] - start["sum"], 70 / days)
                local_start = start["start"].astimezone(ZoneInfo("Europe/Berlin"))
                local_end = end["start"].astimezone(ZoneInfo("Europe/Berlin"))
                self.assertEqual(local_start.date(), local_end.date())
                self.assertEqual(local_start.hour, 0)
                self.assertEqual(local_end.hour, 23)

    def test_repeated_import_and_revisions_keep_timestamps(self):
        jan = MonthlyReading(date(2026, 1, 1), 31, "kWh")
        feb = MonthlyReading(date(2026, 2, 1), 28, "kWh")
        initial = daily_average_statistics((jan, feb), 2026)
        self.assertEqual(initial, daily_average_statistics((jan, feb), 2026))
        revised = daily_average_statistics(
            (MonthlyReading(jan.month, 62, "kWh"), feb), 2026
        )
        self.assertEqual([x["start"] for x in initial], [x["start"] for x in revised])
        self.assertEqual(revised[-1]["sum"], 90)

    def test_gaps_and_zero_follow_monthly_contract(self):
        rows = daily_average_statistics(
            (
                MonthlyReading(date(2026, 1, 1), 0, "m³"),
                MonthlyReading(date(2026, 3, 1), 31, "m³"),
            ),
            2026,
        )
        self.assertEqual(len(rows), 62)
        self.assertTrue(all(x["sum"] == 0 for x in rows))
