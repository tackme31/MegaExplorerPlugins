"""Keeps two MegaExplorer windows from running WD Tagger at the same time.

Each window starts its own plugin process, and two runs tagging the same files
overwrite each other's tags (MEGA's tag update replaces the whole list).
"""

import ctypes
import functools
from ctypes import wintypes

from megaexplorer_plugin import CommandError

MUTEX_NAME = "Local\\com.takumi.wdtagger.run"
ALREADY_RUNNING = ("WD Tagger is already running in another MegaExplorer window. "
                   "Try again once it has finished.")
_ERROR_ALREADY_EXISTS = 183

_kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)
_kernel32.CreateMutexW.restype = wintypes.HANDLE
_kernel32.CreateMutexW.argtypes = [wintypes.LPVOID, wintypes.BOOL, wintypes.LPCWSTR]
_kernel32.CloseHandle.argtypes = [wintypes.HANDLE]

_held = None


def claim():
    """Raises CommandError when another run holds the mutex. Otherwise keeps it
    until this process ends: Windows closes the handle however the process dies
    (finished, cancelled, killed), so a run never leaves a stale lock behind."""
    global _held
    if _held:
        return
    handle = _kernel32.CreateMutexW(None, False, MUTEX_NAME)
    error = ctypes.get_last_error()
    if not handle:
        raise CommandError(f"Could not check for another WD Tagger run (Windows error {error})")
    if error == _ERROR_ALREADY_EXISTS:
        _kernel32.CloseHandle(handle)
        raise CommandError(ALREADY_RUNNING)
    _held = handle


def one_at_a_time(command):
    """Decorator for a command function: claim() before anything else."""

    @functools.wraps(command)
    def wrapper(ctx):
        claim()
        return command(ctx)

    return wrapper
