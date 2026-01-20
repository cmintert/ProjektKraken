import sys
import os

# Ensure src is in path
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "../..")))

from src.date_parser_module.dateparser import DateParser


def run_demo():
    # Setup a standard calendar (similar to Gregorian for familiarity)
    calendar_data = {
        "month_names": [
            "January",
            "February",
            "March",
            "April",
            "May",
            "June",
            "July",
            "August",
            "September",
            "October",
            "November",
            "December",
        ],
        "month_days": [31, 28, 31, 30, 31, 30, 31, 31, 30, 31, 30, 31],
        "year_length": 365,
        "current_year": 2024,
    }

    parser = DateParser(calendar_data)

    print(f"{'Input String':<40} | {'Parsed Date':<40} | {'Timestamp':<10}")
    print("-" * 100)

    inputs = [
        # Standard Numeric
        "15.3.3019",
        "15.03.3019",
        # Numeric US
        "3/15/3019",
        # Natural Language
        "15th of March, 3019",
        "15 January 1200",
        # Time Only (defaults to current year 2024, 1.1)
        "14:30",
        "23:59:59",
        # Combined Date + Time
        "15.3.3019 14:30",
        "15th of March, 3019 14:30",
        "1/1/1 00:00:00",  # Epoch start
        "1.1.2 00:00",  # Start of year 2
        # Negative Years (Pre-Epoch)
        "-100.1.1",  # 100 years before Epoch
        "0.1.1",  # Year 0 (immediate pre-epoch year)
        "0.12.31 23:59:59",  # Last second before Epoch (should be approx -0.000something)
        # Boundaries
        "1.1.1 12:00",  # Noon on first day (0.5)
        "1.12.31",  # Last day of Year 1
        # Edge Cases & Errors
        "1.13.2024",  # Month 13 (Invalid)
        "32.1.2024",  # Day 32 (Invalid)
        "1.1.2024 25:00",  # Hour 25 (Invalid)
        "29.2.2024",  # Feb 29 (Valid in Gregorian, but let's see our config)
    ]

    for date_str in inputs:
        try:
            parsed = parser.parse_date(date_str)
            if parsed:
                try:
                    ts = parser.calculate_timestamp(parsed)
                    # Format parsed date for display
                    date_repr = f"Y{parsed.year} M{parsed.month} D{parsed.day}"
                    if parsed.hour is not None:
                        date_repr += f" {parsed.hour:02}:{parsed.minute:02}:{parsed.second or 0:02}"

                    print(f"{date_str:<40} | {date_repr:<40} | {ts:<10.4f}")
                except ValueError as e:
                    print(
                        f"{date_str:<40} | {'Invalid Calculation: ' + str(e):<40} | {'ERROR':<10}"
                    )
            else:
                print(f"{date_str:<40} | {'Failed to Parse':<40} | {'N/A':<10}")
        except ValueError as e:
            print(f"{date_str:<40} | {f'Failed to Parse: {e}':<40} | {'N/A':<10}")


if __name__ == "__main__":
    run_demo()
