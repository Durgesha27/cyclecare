import unittest
from datetime import date
from services.cycle_calculator import analyze

TODAY = date(2026, 3, 10)


def P(start, end=None):
    return {"start_date": start, "end_date": end}


class CalculatorTests(unittest.TestCase):
    def test_no_periods(self):
        a = analyze([], TODAY)
        self.assertEqual(a["status"], "no_data")
        self.assertIsNone(a["next_period_start"]); self.assertIsNone(a["cycle_day"]); self.assertIsNone(a["days_until"])

    def test_one_period_has_cycle_day_but_no_estimate(self):
        a = analyze([P("2026-03-01")], TODAY)
        self.assertEqual(a["status"], "insufficient")
        self.assertEqual(a["cycle_day"], 10)
        self.assertIsNone(a["next_period_start"])

    def test_two_periods_limited_estimate(self):
        a = analyze([P("2026-01-01"), P("2026-01-30")], TODAY)
        self.assertEqual(a["estimated_cycle_length"], 29)
        self.assertEqual(a["confidence"], "limited")
        self.assertEqual(a["next_period_start"], "2026-02-28")
        self.assertEqual(a["days_until"], -10)  # estimate already passed: reported honestly

    def test_regular_intervals_use_median(self):
        a = analyze([P("2025-10-01"), P("2025-10-29"), P("2025-11-26"), P("2025-12-24"), P("2026-01-21")], TODAY)
        self.assertEqual(a["valid_intervals"], [28, 28, 28, 28])
        self.assertEqual(a["estimated_cycle_length"], 28)
        self.assertEqual(a["confidence"], "good"); self.assertEqual(a["regularity"], "steady")
        self.assertEqual(a["next_period_start"], "2026-02-18")

    def test_irregular_median_resists_outlier(self):
        starts = ["2025-01-01", "2025-01-29", "2025-02-26", "2025-04-30", "2025-05-28"]  # 28,28,63,28
        a = analyze([P(s) for s in starts], date(2025, 6, 1))
        self.assertEqual(a["estimated_cycle_length"], 28)
        self.assertEqual(a["variation"], 35); self.assertEqual(a["regularity"], "variable")

    def test_duplicates_counted_and_ignored(self):
        a = analyze([P("2026-01-01"), P("2026-01-01"), P("2026-01-29")], TODAY)
        self.assertEqual(a["duplicates"], 1); self.assertEqual(a["record_count"], 2)
        self.assertEqual(a["valid_intervals"], [28])

    def test_incomplete_record_is_valid_for_cycles(self):
        a = analyze([P("2026-01-01", "2026-01-05"), P("2026-01-29")], TODAY)
        self.assertEqual(a["incomplete"], 1); self.assertEqual(a["valid_intervals"], [28])
        self.assertEqual(a["durations"], [{"start_date": "2026-01-01", "days": 5}])

    def test_duration_is_not_cycle_length(self):
        a = analyze([P("2026-01-01", "2026-01-05"), P("2026-01-29", "2026-02-02")], TODAY)
        self.assertEqual(a["estimated_cycle_length"], 28); self.assertEqual(a["estimated_period_length"], 5)

    def test_month_and_year_boundaries(self):
        a = analyze([P("2025-12-20"), P("2026-01-17")], TODAY)
        self.assertEqual(a["valid_intervals"], [28]); self.assertEqual(a["next_period_start"], "2026-02-14")

    def test_leap_year(self):
        a = analyze([P("2024-02-10"), P("2024-03-09")], date(2024, 3, 12))
        self.assertEqual(a["valid_intervals"], [28])  # 29-day Feb
        self.assertEqual(a["next_period_start"], "2024-04-06")
        b = analyze([P("2023-02-10"), P("2023-03-10")], date(2023, 3, 12))
        self.assertEqual(b["valid_intervals"], [28])

    def test_future_and_invalid_dates_ignored(self):
        a = analyze([P("2026-01-01"), P("2026-06-01"), {"start_date": "nonsense", "end_date": None}], TODAY)
        self.assertEqual(a["record_count"], 1); self.assertEqual(a["ignored_future"], 1)
        self.assertEqual(a["cycle_day"], 69)

    def test_suspicious_interval_excluded(self):
        a = analyze([P("2026-01-01"), P("2026-01-05"), P("2026-02-02")], TODAY)
        self.assertEqual(a["suspicious"], 1); self.assertEqual(a["valid_intervals"], [28])

    def test_missing_preferences_and_preference_fallback(self):
        self.assertEqual(analyze([P("2026-03-01")], TODAY, None, None)["status"], "insufficient")
        a = analyze([P("2026-03-01")], TODAY, typical_cycle=30, typical_period=4)
        self.assertEqual(a["cycle_length_source"], "preference"); self.assertEqual(a["next_period_start"], "2026-03-31")
        self.assertEqual(len(a["predicted_dates"]), 4)

    def test_cycle_day_none_when_too_old(self):
        self.assertIsNone(analyze([P("2025-01-01")], TODAY)["cycle_day"])


if __name__ == "__main__":
    unittest.main()
