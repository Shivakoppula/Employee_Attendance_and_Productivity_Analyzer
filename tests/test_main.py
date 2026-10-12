# unittest runs checks automatically; tempfile provides isolated files for the pipeline test.
import csv
import json
import tempfile
import unittest
# datetime date objects let tests compare parsed values without comparing strings.
from datetime import date
from pathlib import Path

import sys
# Add the project directory so unittest can import the application module from this test file.
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from main import (
    AttendanceRecord, attendance_credit, calculate_metrics, parse_date,
    parse_time, parse_nonnegative_float, read_input, validate_and_clean, run,
    write_browser_report, write_reports
)
import logging


class AttendanceAnalyzerTests(unittest.TestCase):
    # Supported input date formats should produce the same Python date value.
    def test_parse_date_formats(self):
        self.assertEqual(parse_date("2026-10-01"), date(2026, 10, 1))
        self.assertEqual(parse_date("01/10/2026"), date(2026, 10, 1))

    # Optional fields may be blank, while provided hour values must be valid and nonnegative.
    def test_parse_time_and_hours(self):
        self.assertEqual(parse_time("09:30").hour, 9)
        self.assertIsNone(parse_time(""))
        self.assertEqual(parse_nonnegative_float("7.5", "hours_worked"), 7.5)
        with self.assertRaises(ValueError):
            parse_nonnegative_float("-1", "hours_worked")

    # Attendance percentage uses full credit, half credit, or no credit by status.
    def test_attendance_credit(self):
        self.assertEqual(attendance_credit("PRESENT"), 1)
        self.assertEqual(attendance_credit("LATE"), 1)
        self.assertEqual(attendance_credit("HALF-DAY"), 0.5)
        self.assertEqual(attendance_credit("ABSENT"), 0)

    # The first valid row wins a duplicate date; malformed dates are also rejected.
    def test_duplicate_and_invalid_rows_rejected(self):
        # Lists and dictionaries mirror the row structure returned by read_input.
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

    # An invalid row must not reserve its employee/date and block a later valid row.
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

    # Time-only records for absent/leave statuses still need a forward-moving shift interval.
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

    # Names are required so summary and exception reports can identify employees.
    def test_blank_name_is_rejected(self):
        rows = [{"employee_id": "E1", "name": " ", "date": "2026-10-01",
                 "status": "Present", "hours_worked": "8"}]
        accepted, rejected = validate_and_clean(rows, logging.getLogger("test"))
        self.assertEqual(accepted, [])
        self.assertEqual(len(rejected), 1)
        self.assertIn("name is required", rejected[0]["rejection_reasons"])

    # Leave does not lower the attendance percentage; absent, late, and short hours affect metrics/exceptions.
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

    # A single complete present record should produce full attendance and no exceptions.
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

    # More than eight hours is overtime; exactly eight hours is not.
    def test_overtime_export_and_browser_report(self):
        records = [
            AttendanceRecord("E1", "Present at limit", date(2026, 10, 1), "PRESENT", "IT", 8.0, None, None, 2),
            AttendanceRecord("E2", "Present overtime", date(2026, 10, 1), "PRESENT", "IT", 8.5, None, None, 3),
            AttendanceRecord("E3", "Late overtime", date(2026, 10, 1), "LATE", "IT", 9.0, None, None, 4),
            AttendanceRecord("E4", "Half day", date(2026, 10, 1), "HALF-DAY", "IT", 4.0, None, None, 5),
            AttendanceRecord("E5", "Absent", date(2026, 10, 1), "ABSENT", "IT", 0.0, None, None, 6),
            AttendanceRecord("E6", "On leave", date(2026, 10, 1), "LEAVE", "IT", 0.0, None, None, 7),
        ]
        summaries, exceptions = calculate_metrics(records)

        with tempfile.TemporaryDirectory() as temp:
            output_dir = Path(temp)
            logger = logging.getLogger("overtime_test")
            write_reports(records, [], summaries, exceptions, output_dir, logger)

            with (output_dir / "overtime_records.csv").open(newline="", encoding="utf-8") as handle:
                overtime_rows = list(csv.DictReader(handle))
            self.assertEqual([row["employee_id"] for row in overtime_rows], ["E2", "E3"])
            self.assertIn("Overtime records (more than 8 hours): 2",
                          (output_dir / "summary_report.txt").read_text(encoding="utf-8"))

            browser_path = output_dir / "attendance_report.html"
            write_browser_report(browser_path, records, [], summaries, exceptions)
            html = browser_path.read_text(encoding="utf-8")
            embedded_data = html.split("const DATA = ", 1)[1].split(";\n", 1)[0]
            report_data = json.loads(embedded_data)
            overtime_flags = {row["employee_id"]: row["overtime"] for row in report_data["records"]}
            self.assertEqual(report_data["overtime_threshold"], 8.0)
            self.assertEqual(overtime_flags["E1"], False)
            self.assertEqual(overtime_flags["E2"], True)
            self.assertEqual(overtime_flags["E3"], True)
            self.assertEqual(overtime_flags["E5"], False)
            self.assertEqual(overtime_flags["E6"], False)
            self.assertIn('data-mode="overtime"', html)

    # Absent and leave rows cannot be counted as overtime when positive hours are supplied.
    def test_absent_and_leave_with_positive_hours_are_rejected(self):
        rows = [
            {"employee_id": "E1", "name": "A", "date": "2026-10-01",
             "status": "Absent", "hours_worked": "9"},
            {"employee_id": "E2", "name": "B", "date": "2026-10-01",
             "status": "Leave", "hours_worked": "9"},
        ]
        accepted, rejected = validate_and_clean(rows, logging.getLogger("test"))
        self.assertEqual(accepted, [])
        self.assertEqual(len(rejected), 2)
        for row in rejected:
            self.assertIn("cannot have positive working hours", row["rejection_reasons"])

    # Exercise the complete read-clean-calculate-write pipeline using a temporary CSV.
    def test_end_to_end_creates_outputs(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            inp = root / "in.csv"
            # File handling: create a temporary CSV for run() to read without changing the sample input.
            inp.write_text(
                "employee_id,name,date,status,hours_worked\nE1,A,2026-10-01,Present,8\nE1,A,2026-10-02,Absent,0\n", encoding="utf-8"
            )
            out = root / "out"
            self.assertEqual(run(inp, out), 0)
            for name in ("cleaned_attendance.csv","rejected_records.csv",
                         "employee_summary.csv","attendance_exceptions.csv",
                         "overtime_records.csv","summary_report.txt","application.log"):
                self.assertTrue((out / name).exists(), name)
            # run() does not open the optional browser report unless requested.
            self.assertFalse((out / "attendance_report.html").exists())


if __name__ == "__main__":
    unittest.main(verbosity=2)
