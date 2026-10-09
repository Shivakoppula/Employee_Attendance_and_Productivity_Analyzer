# Employee Attendance & Productivity Analyzer

A beginner-friendly Core Python capstone that reads attendance records, validates them, calculates employee attendance metrics, identifies exceptions, and creates reports and an application log.

## Requirements

- Python 3.10 or newer recommended.
- CSV input works with the Python standard library only.
- Optional Excel input (`.xlsx`) requires `pandas` and `openpyxl`:
  `python -m pip install pandas openpyxl`

## Python modules used

The CSV workflow uses only modules included with Python:

- `argparse` reads command-line options such as the input path and low-hours threshold.
- `csv` reads rows by column name and writes the generated CSV reports.
- `logging` sends progress, rejection warnings, and errors to the console and `application.log`.
- `sys` gives logging and error messages access to the console output streams.
- `collections.defaultdict` groups attendance records by employee ID when metrics are calculated.
- `dataclasses.dataclass` defines a clear structure for each validated attendance record.
- `datetime` parses dates and times and calculates working hours from login/logout times.
- `pathlib.Path` builds input and output paths in a way that works across operating systems.
- `typing.Any` describes report rows that contain values of different types.
- `__future__.annotations` keeps type annotations from needing immediate evaluation.

For Excel input only, `pandas` reads spreadsheet rows and `openpyxl` provides the `.xlsx` reader engine. These packages are imported only when the input file is Excel, so they are not needed for CSV runs. The unused regular-expression import was removed; this project does not currently need regex processing.

## Run

From this project directory:

```bash
python main.py
```

This reads `data/attendance_sample.csv` and writes files into `output/`.

Choose an input and output directory:

```bash
python main.py --input data/attendance_sample.csv --output-dir output
```

Set a different low-hours threshold:

```bash
python main.py --input data/attendance_sample.csv --output-dir output --low-hours-threshold 6
```

## Input schema

Required columns:

- `employee_id`
- `name`
- `date`
- `status`

Optional columns:

- `login_time`
- `logout_time`
- `hours_worked`
- `department`

Date formats accepted: `YYYY-MM-DD`, `DD/MM/YYYY`, `MM/DD/YYYY`.
Time formats accepted: `HH:MM`, `HH:MM:SS`.
For attended records (`Present`, `Late`, `Half-Day`), provide `hours_worked` or both login and logout times. Explicit `hours_worked` takes precedence if both are supplied. Overnight shifts are not supported.

Status values accepted (case-insensitive): `Present`, `Absent`, `Late`, `Half-Day`, `Leave`. `Half_Day` is also normalized to `Half-Day`.

## Business rules and assumptions

The source brief requires attendance percentage, working hours, absent/late/low-hours exceptions, a summary report, and an output file. It does not specify all formulas and thresholds. This implementation uses these explicit assumptions:

1. Attendance percentage = (Present days + Late days + 0.5 × Half-Day records) / eligible records × 100.
2. Approved `Leave` records are excluded from eligible records. The source file has no leave-approval field, so every `Leave` status is treated as approved.
3. A `Late` record counts as attended and is separately flagged.
4. Low hours means an attended record below 8 hours by default; configure with `--low-hours-threshold`.
5. `Absent` and `Leave` records cannot have positive working hours.
6. Duplicate `(employee_id, date)` rows are rejected so they cannot inflate totals.
7. Invalid rows are excluded from calculations and written to `rejected_records.csv` with row number and reason.
8. Employees are grouped by employee ID. The most recent accepted row supplies the displayed name and department if those fields vary across records.
9. Each row is treated as one scheduled workday. Holidays, weekends, and different employee schedules are not inferred because the input format does not supply a calendar.
10. A time-only shift must have logout later than login. Overnight shifts and breaks are not modeled.

These are project defaults, not company attendance policies. Adjust them to match the rules supplied by your instructor or organization.

## Outputs

- `cleaned_attendance.csv`: normalized, accepted records with calculated hours.
- `rejected_records.csv`: invalid and duplicate rows with explanations.
- `employee_summary.csv`: employee-level attendance percentages, total hours, and status counts.
- `attendance_exceptions.csv`: absent, late, and low-hours records.
- `summary_report.txt`: concise overall report.
- `application.log`: processing, rejection, and completion messages.

The console also displays progress and a final summary through logging.

## Run tests

```bash
python -m unittest discover -s tests -v
```

The tests cover date/time parsing, numeric validation, attendance credit, duplicate and invalid row rejection, metrics, exception detection, and end-to-end output generation.

## Project design

- `read_input`: loads CSV or optional XLSX.
- `parse_date`, `parse_time`, `parse_nonnegative_float`: parse and validate values.
- `validate_and_clean`: checks schema and each row, then separates accepted and rejected records.
- `attendance_credit`: converts status into attendance-day credit.
- `calculate_metrics`: aggregates employee metrics and creates exceptions.
- `write_csv`, `write_reports`: persist outputs.
- `configure_logging`: configures console and file logs.
- `run` and `main`: orchestrate execution and command-line options.

## Suggested demo (5–10 minutes)

1. Explain the input columns and status rules.
2. Run the project with the sample CSV.
3. Open `employee_summary.csv` and explain attendance percentage and total hours.
4. Open `attendance_exceptions.csv` to show absent, late, and low-hours flags.
5. Open `rejected_records.csv` to show invalid-date, duplicate, and blank-name handling.
6. Show `application.log` and run the unit tests.
7. Explain the assumptions and how the low-hours threshold can be changed.
