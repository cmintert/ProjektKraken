# Date Parser Module

## Overview

This is a standalone date parser module copied from the [NeoWorldBuilder](https://github.com/cmintert/NeoWorldBuilder) project. It provides natural language date parsing capabilities for custom calendar systems.

**Source Information:**
- **Original File:** `src/date_parser_module/dateparser/core.py`
- **Commit:** `4fbd331e997fd978e52aaa6cbb63b9853fb54d79`
- **Status:** Not integrated with ProjektKraken yet

## Features

The date parser supports multiple date formats:
- Standard notation (15.3.3019, 3/15/3019)
- Natural language ("15th day of Wintermarch, 3019")
- Month-year ("Wintermarch 3019")
- Year only ("Year 3019")
- Seasons ("Early spring 3019")
- Relative dates ("2 days after Battle")
- Fuzzy dates ("Around Wintermarch 3019")
- Date ranges ("From Wintermarch to Summerday 3019")

## Usage Example

```python
from src.date_parser_module.dateparser import DateParser, ParsedDate, DatePrecision

# Define a custom calendar
calendar_data = {
    "month_names": ["Wintermarch", "Springbloom", "Summerday", "Harvestmoon"],
    "month_days": [30, 30, 30, 30],
    "year_length": 120,
    "current_year": 3019
}

# Initialize the parser
parser = DateParser(calendar_data)

# Parse various date formats
date1 = parser.parse_date("15th day of Wintermarch, 3019")
print(f"Year: {date1.year}, Month: {date1.month}, Day: {date1.day}")
print(f"Precision: {date1.precision}")

date2 = parser.parse_date("Springbloom 3019")
print(f"Year: {date2.year}, Month: {date2.month}")
print(f"Precision: {date2.precision}")

date3 = parser.parse_date("Early spring 3019")
print(f"Year: {date3.year}, Season: {date3.season}")
print(f"Precision: {date3.precision}")
```

## Integration Status

⚠️ **This module is intentionally NOT integrated with ProjektKraken.**

This is a standalone copy that can be used independently or integrated in future PRs. The module has no dependencies on ProjektKraken's existing date/time systems and uses only Python standard library modules.

## Future Work

Possible future enhancements:
- Integration with ProjektKraken's timeline system
- Adapter classes to convert between ParsedDate and ProjektKraken's date formats
- UI components for date input with natural language support
- Tests specific to ProjektKraken's calendar requirements

## Dependencies

This module uses only Python standard library:
- `enum`
- `dataclasses`
- `re`
- `typing`

No external dependencies are required.
