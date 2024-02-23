from sys import platform
from warnings import warn
from watchdog.utils import UnsupportedLibc

if platform.startswith("linux"):
    try:
        from watchdog.observers.inotify import InotifyObserver as Observer
    except UnsupportedLibc:
        from watchdog.observers.polling import PollingObserver as Observer

elif platform.startswith("darwin"):
    try:
        from watchdog.observers.fsevents import FSEventsObserver as Observer
    except Exception:
        try:
            from watchdog.observers.kqueue import KqueueObserver as Observer
            warn("Failed to import fsevents. Fall back to kqueue")
        except Exception:
            from watchdog.observers.polling import PollingObserver as Observer

            warn("Failed to import fsevents and kqueue. Fall back to polling.")

elif platform in ("dragonfly", "freebsd", "netbsd", "openbsd", "bsd"):
    from watchdog.observers.kqueue import KqueueObserver as Observer

elif platform.startswith("win"):
    try:
        from win_no_delay_observer import WindowsNoDelayObserver as Observer
    except Exception:
        from watchdog.observers.polling import PollingObserver as Observer

        warn("Failed to import read_directory_changes. Fall back to polling.")

else:
    from watchdog.observers.polling import PollingObserver as Observer

__all__ = ["Observer"]
