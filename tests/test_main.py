import csv
import tempfile
import unittest
from datetime import date
from pathlib import Path

import sys
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from main import (
    AttendanceRecord, attendance_credit, calculate_metrics, parse_date,
    parse_time, parse_nonnegative_float, read_input, validate_and_clean, run
)
import logging


class AttendanceAnalyzerTests(unittest.TestCase):
    def test_parse_date_formats(self):
        self.assertEqual(parse_date("2026-10-01"), date(2026, 10, 1))
        self.assertEqual(parse_date("01/10/2026"), date(2026, 10, 1))

    def test_parse_time_and_hours(self):
        self.assertEqual(parse_time("09:30").hour, 9)
        self.assertIsNone(parse_time(""))
        self.assertEqual(parse_nonnegative_float("7.5", "hours_worked"), 7.5)
        with self.assertRaises(ValueError):
            parse_nonnegative_float("-1", "hours_worked")

    def test_attendance_credit(self):
        self.assertEqual(attendance_credit("PRESENT"), 1)
        self.assertEqual(attendance_credit("LATE"), 1)
        self.assertEqual(attendance_credit("HALF-DAY"), 0.5)
        self.assertEqual(attendance_credit("ABSENT"), 0)

    def test_duplicate_and_invalid_rows_rejected(self):
        rows = [
            {"employee_id":"E1","name":"A","date":"2026-10-01","status":"Present","hours_worked":"8"},
            {"employee_id":"E1","name":"A","date":"2026-10-01","status":"Present","hours_worked":"8"},
            {"employee_id":"E2","name":"B","date":"bad-date","status":"Present","hours_worked":"8"},
        ]
        logger = logging.getLogger("test")
        accepted, rejected = validate_and_clean(rows, logger)
        self.assertEqual(len(accepted), 1)
        self.assertEqual(len(rejected), 2)
        self.assertIn("duplicate", rejected[0]["rejection_reasons"])
        self.assertIn("date must use", rejected[1]["rejection_reasons"])

    def test_rejected_row_does_not_block_valid_row_for_same_date(self):
        rows = [
            {"employee_id": "E1", "name": "A", "date": "2026-10-01",
             "status": "Absent", "hours_worked": "8"},
            {"employee_id": "E1", "name": "A", "date": "2026-10-01",
             "status": "Present", "hours_worked": "8"},
        ]
        accepted, rejected = validate_and_clean(rows, logging.getLogger("test"))
        self.assertEqual(len(accepted), 1)
        self.assertEqual(accepted[0].status, "PRESENT")
        self.assertEqual(len(rejected), 1)
        self.assertIn("cannot have positive working hours", rejected[0]["rejection_reasons"])

    def test_absent_and_leave_with_reversed_times_are_rejected(self):
        rows = [
            {"employee_id": "E1", "name": "A", "date": "2026-10-01",
             "status": "Absent", "hours_worked": "", "login_time": "09:00", "logout_time": "08:00"},
            {"employee_id": "E2", "name": "B", "date": "2026-10-01",
             "status": "Leave", "hours_worked": "", "login_time": "09:00", "logout_time": "08:00"},
        ]
        accepted, rejected = validate_and_clean(rows, logging.getLogger("test"))
        self.assertEqual(accepted, [])
        self.assertEqual(len(rejected), 2)
        for row in rejected:
            self.assertIn("logout_time must be later than login_time", row["rejection_reasons"])

    def test_blank_name_is_rejected(self):
        rows = [{"employee_id": "E1", "name": " ", "date": "2026-10-01",
                 "status": "Present", "hours_worked": "8"}]
        accepted, rejected = validate_and_clean(rows, logging.getLogger("test"))
        self.assertEqual(accepted, [])
        self.assertEqual(len(rejected), 1)
        self.assertIn("name is required", rejected[0]["rejection_reasons"])

    def test_metrics_and_exceptions(self):
        records = [
            AttendanceRecord("E1","A",date(2026,10,1),"PRESENT","IT",8,None,None,2),
            AttendanceRecord("E1","A",date(2026,10,2),"LATE","IT",6,None,None,3),
            AttendanceRecord("E1","A",date(2026,10,3),"ABSENT","IT",0,None,None,4),
            AttendanceRecord("E1","A",date(2026,10,4),"LEAVE","IT",0,None,None,5),
        ]
        summaries, exceptions = calculate_metrics(records, 8)
        self.assertEqual(summaries[0]["eligible_days"], 3)
        self.assertEqual(summaries[0]["attendance_percentage"], 66.67)
        self.assertEqual(summaries[0]["total_working_hours"], 14)
        self.assertEqual(len(exceptions), 2)
        self.assertIn("Late", exceptions[0]["exception"])
        self.assertIn("Low hours", exceptions[0]["exception"])

    def test_present_record_metrics(self):
        records = [
            AttendanceRecord("E1", "A", date(2026, 10, 1), "PRESENT", "IT", 8, None, None, 2),
        ]
        summaries, exceptions = calculate_metrics(records)
        self.assertEqual(summaries[0]["records_count"], 1)
        self.assertEqual(summaries[0]["attended_day_equivalent"], 1.0)
        self.assertEqual(summaries[0]["attendance_percentage"], 100.0)
        self.assertEqual(summaries[0]["total_working_hours"], 8.0)
        self.assertEqual(exceptions, [])

    def test_end_to_end_creates_outputs(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            inp = root / "in.csv"
            inp.write_text(
                "employee_id,name,date,status,hours_worked\nE1,A,2026-10-01,Present,8\nE1,A,2026-10-02,Absent,0\n", encoding="utf-8"
            )
            out = root / "out"
            self.assertEqual(run(inp, out), 0)
            for name in ("cleaned_attendance.csv","rejected_records.csv",
                         "employee_summary.csv","attendance_exceptions.csv",
                         "summary_report.txt","application.log"):
                self.assertTrue((out / name).exists(), name)
            self.assertFalse((out / "attendance_report.html").exists())


if __name__ == "__main__":
    unittest.main(verbosity=2)
