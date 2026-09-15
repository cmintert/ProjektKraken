"""Low-overhead host and process resource measurements."""

from __future__ import annotations

import ctypes
import os
import platform
import sqlite3
import sys
import time
from ctypes import wintypes
from typing import Any


def process_memory_bytes() -> dict[str, int | None]:
    """Return whole-process memory figures without an external dependency."""
    if sys.platform != "win32":
        return {"working_set": None, "private_bytes": None}

    class ProcessMemoryCountersEx(ctypes.Structure):
        _fields_ = [
            ("cb", wintypes.DWORD),
            ("PageFaultCount", wintypes.DWORD),
            ("PeakWorkingSetSize", ctypes.c_size_t),
            ("WorkingSetSize", ctypes.c_size_t),
            ("QuotaPeakPagedPoolUsage", ctypes.c_size_t),
            ("QuotaPagedPoolUsage", ctypes.c_size_t),
            ("QuotaPeakNonPagedPoolUsage", ctypes.c_size_t),
            ("QuotaNonPagedPoolUsage", ctypes.c_size_t),
            ("PagefileUsage", ctypes.c_size_t),
            ("PeakPagefileUsage", ctypes.c_size_t),
            ("PrivateUsage", ctypes.c_size_t),
        ]

    counters = ProcessMemoryCountersEx()
    counters.cb = ctypes.sizeof(counters)
    get_process = ctypes.windll.kernel32.GetCurrentProcess
    get_process.restype = wintypes.HANDLE
    get_memory = ctypes.windll.psapi.GetProcessMemoryInfo
    get_memory.argtypes = [
        wintypes.HANDLE,
        ctypes.POINTER(ProcessMemoryCountersEx),
        wintypes.DWORD,
    ]
    get_memory.restype = wintypes.BOOL
    handle = get_process()
    ok = get_memory(
        handle, ctypes.byref(counters), counters.cb
    )
    if not ok:
        return {"working_set": None, "private_bytes": None}
    return {
        "working_set": int(counters.WorkingSetSize),
        "private_bytes": int(counters.PrivateUsage),
    }


def environment_metadata() -> dict[str, Any]:
    """Describe the runtime sufficiently for honest report comparison."""
    try:
        from PySide6 import __version__ as pyside_version
    except ImportError:
        pyside_version = "unavailable"
    return {
        "platform": platform.platform(),
        "system": platform.system(),
        "release": platform.release(),
        "machine": platform.machine(),
        "processor": platform.processor(),
        "logical_cpu_count": os.cpu_count(),
        "python": platform.python_version(),
        "pyside": pyside_version,
        "sqlite": sqlite3.sqlite_version,
        "power_state": windows_power_state(),
        "background_cpu_percent": system_cpu_percent(),
        "process_memory": process_memory_bytes(),
    }


def windows_power_state() -> str:
    """Return AC/battery state on Windows, or an explicit unavailable value."""
    if sys.platform != "win32":
        return "unavailable"

    class SystemPowerStatus(ctypes.Structure):
        _fields_ = [
            ("ACLineStatus", wintypes.BYTE),
            ("BatteryFlag", wintypes.BYTE),
            ("BatteryLifePercent", wintypes.BYTE),
            ("SystemStatusFlag", wintypes.BYTE),
            ("BatteryLifeTime", wintypes.DWORD),
            ("BatteryFullLifeTime", wintypes.DWORD),
        ]

    status = SystemPowerStatus()
    if not ctypes.windll.kernel32.GetSystemPowerStatus(ctypes.byref(status)):
        return "unknown"
    return {0: "battery", 1: "ac"}.get(status.ACLineStatus, "unknown")


def system_cpu_percent(sample_seconds: float = 0.1) -> float | None:
    """Sample whole-system CPU utilization for comparison context."""
    if sys.platform != "win32":
        try:
            load = os.getloadavg()[0]
        except (AttributeError, OSError):
            return None
        cpu_count = os.cpu_count() or 1
        return min(100.0, max(0.0, load / cpu_count * 100.0))

    class FileTime(ctypes.Structure):
        _fields_ = [("low", wintypes.DWORD), ("high", wintypes.DWORD)]

        def value(self) -> int:
            return (int(self.high) << 32) | int(self.low)

    get_times = ctypes.windll.kernel32.GetSystemTimes
    get_times.argtypes = [
        ctypes.POINTER(FileTime),
        ctypes.POINTER(FileTime),
        ctypes.POINTER(FileTime),
    ]
    get_times.restype = wintypes.BOOL

    def sample() -> tuple[int, int] | None:
        idle = FileTime()
        kernel = FileTime()
        user = FileTime()
        if not get_times(ctypes.byref(idle), ctypes.byref(kernel), ctypes.byref(user)):
            return None
        return idle.value(), kernel.value() + user.value()

    first = sample()
    time.sleep(max(0.01, sample_seconds))
    second = sample()
    if first is None or second is None:
        return None
    idle_delta = second[0] - first[0]
    total_delta = second[1] - first[1]
    if total_delta <= 0:
        return None
    return min(100.0, max(0.0, (1.0 - idle_delta / total_delta) * 100.0))
