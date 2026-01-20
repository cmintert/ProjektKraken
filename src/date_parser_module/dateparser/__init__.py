"""
Date Parser Module

This module provides natural language date parsing for custom calendar systems.
It was copied from the NeoWorldBuilder project to be used as a standalone module.

Source: NeoWorldBuilder - src/date_parser_module/dateparser/core.py
Commit: 4fbd331e997fd978e52aaa6cbb63b9853fb54d79

The module is intentionally not integrated with ProjektKraken yet.
Future integration can be added in separate PRs.
"""

from .core import DateParser, ParsedDate, DatePrecision

__all__ = ["DateParser", "ParsedDate", "DatePrecision"]
