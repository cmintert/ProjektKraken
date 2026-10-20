"""Own native descendants for the lifetime of one supervised interpreter."""

from __future__ import annotations

import ctypes
import os
import signal
import subprocess
import sys
from ctypes import wintypes
from typing import Any

RESUME_FAILED = 0xFFFFFFFF


def ensure_runtime() -> None:
    """Reject Store broker launches that escape Windows job inheritance."""
    base = getattr(sys, "_base_executable", sys.executable).replace("\\", "/").lower()
    if sys.platform == "win32" and "/microsoft/windowsapps/" in base:
        raise ValueError(
            "WindowsApps Python launches escape native process containment. "
            "Use a non-WindowsApps Python 3.13 environment for release regression."
        )


def resume(pid: int) -> None:
    """Resume the sole initial thread after assigning its suspended process."""

    class ThreadEntry(ctypes.Structure):
        _fields_ = [
            ("size", wintypes.DWORD),
            ("usage", wintypes.DWORD),
            ("thread", wintypes.DWORD),
            ("owner", wintypes.DWORD),
            ("base_priority", wintypes.LONG),
            ("delta_priority", wintypes.LONG),
            ("flags", wintypes.DWORD),
        ]

    kernel = ctypes.WinDLL("kernel32", use_last_error=True)
    kernel.CreateToolhelp32Snapshot.argtypes = [wintypes.DWORD, wintypes.DWORD]
    kernel.CreateToolhelp32Snapshot.restype = wintypes.HANDLE
    kernel.Thread32First.argtypes = [wintypes.HANDLE, ctypes.POINTER(ThreadEntry)]
    kernel.Thread32Next.argtypes = [wintypes.HANDLE, ctypes.POINTER(ThreadEntry)]
    kernel.OpenThread.argtypes = [wintypes.DWORD, wintypes.BOOL, wintypes.DWORD]
    kernel.OpenThread.restype = wintypes.HANDLE
    kernel.ResumeThread.argtypes = [wintypes.HANDLE]
    kernel.ResumeThread.restype = wintypes.DWORD
    kernel.CloseHandle.argtypes = [wintypes.HANDLE]
    snapshot = kernel.CreateToolhelp32Snapshot(0x00000004, 0)  # TH32CS_SNAPTHREAD
    if snapshot == wintypes.HANDLE(-1).value:
        raise ctypes.WinError(ctypes.get_last_error())
    try:
        entry = ThreadEntry()
        entry.size = ctypes.sizeof(entry)
        available = kernel.Thread32First(snapshot, ctypes.byref(entry))
        while available:
            if entry.owner == pid:
                thread = kernel.OpenThread(0x0002, False, entry.thread)
                if not thread:
                    raise ctypes.WinError(ctypes.get_last_error())
                try:
                    if kernel.ResumeThread(thread) == RESUME_FAILED:
                        raise ctypes.WinError(ctypes.get_last_error())
                    return
                finally:
                    kernel.CloseHandle(thread)
            available = kernel.Thread32Next(snapshot, ctypes.byref(entry))
        raise OSError(f"Cannot find suspended thread for process {pid}")
    finally:
        kernel.CloseHandle(snapshot)


class WindowsJob:
    """Close a kill-on-close job even if its original Python process has exited."""

    def __init__(self, process: subprocess.Popen[Any]) -> None:
        """Assign the just-created interpreter before it can launch native work."""

        class BasicLimits(ctypes.Structure):
            _fields_ = [
                ("per_process", ctypes.c_int64),
                ("per_job", ctypes.c_int64),
                ("flags", wintypes.DWORD),
                ("min_working_set", ctypes.c_size_t),
                ("max_working_set", ctypes.c_size_t),
                ("active_processes", wintypes.DWORD),
                ("affinity", ctypes.c_size_t),
                ("priority", wintypes.DWORD),
                ("scheduling", wintypes.DWORD),
            ]

        class IoCounters(ctypes.Structure):
            _fields_ = [
                (name, ctypes.c_uint64)
                for name in (
                    "read_ops",
                    "write_ops",
                    "other_ops",
                    "read_bytes",
                    "write_bytes",
                    "other_bytes",
                )
            ]

        class ExtendedLimits(ctypes.Structure):
            _fields_ = [
                ("basic", BasicLimits),
                ("io", IoCounters),
                ("process_memory", ctypes.c_size_t),
                ("job_memory", ctypes.c_size_t),
                ("peak_process_memory", ctypes.c_size_t),
                ("peak_job_memory", ctypes.c_size_t),
            ]

        kernel = ctypes.WinDLL("kernel32", use_last_error=True)
        kernel.CreateJobObjectW.argtypes = [ctypes.c_void_p, wintypes.LPCWSTR]
        kernel.CreateJobObjectW.restype = wintypes.HANDLE
        kernel.SetInformationJobObject.argtypes = [
            wintypes.HANDLE,
            ctypes.c_int,
            ctypes.c_void_p,
            wintypes.DWORD,
        ]
        kernel.AssignProcessToJobObject.argtypes = [wintypes.HANDLE, wintypes.HANDLE]
        kernel.OpenProcess.argtypes = [wintypes.DWORD, wintypes.BOOL, wintypes.DWORD]
        kernel.OpenProcess.restype = wintypes.HANDLE
        kernel.CloseHandle.argtypes = [wintypes.HANDLE]
        self.kernel = kernel
        self.handle = kernel.CreateJobObjectW(None, None)
        if not self.handle:
            raise ctypes.WinError(ctypes.get_last_error())
        limits = ExtendedLimits()
        limits.basic.flags = 0x2000  # JOB_OBJECT_LIMIT_KILL_ON_JOB_CLOSE
        configured = kernel.SetInformationJobObject(
            self.handle, 9, ctypes.byref(limits), ctypes.sizeof(limits)
        )
        # AssignProcessToJobObject requires PROCESS_SET_QUOTA | PROCESS_TERMINATE.
        process_handle = kernel.OpenProcess(0x0101, False, process.pid)
        try:
            assigned = (
                configured
                and process_handle
                and kernel.AssignProcessToJobObject(self.handle, process_handle)
            )
        finally:
            if process_handle:
                kernel.CloseHandle(process_handle)
        if not assigned:
            error = ctypes.WinError(ctypes.get_last_error())
            self.close()
            raise error

    def close(self) -> None:
        """Release the job and terminate any remaining native descendants."""
        if self.handle:
            self.kernel.CloseHandle(self.handle)
            self.handle = None


def cleanup(process: subprocess.Popen[Any], job: WindowsJob | None) -> None:
    """End a module's process tree on normal completion as well as timeout."""
    if job is not None:
        job.close()
    elif sys.platform != "win32":
        try:
            os.killpg(process.pid, signal.SIGKILL)
        except ProcessLookupError:
            pass
    elif process.poll() is None:
        subprocess.run(
            ["taskkill", "/PID", str(process.pid), "/T", "/F"],
            capture_output=True,
            check=False,
        )
    process.wait(timeout=15)
