import os.path as ospath
from platform import system, python_implementation
from threading import Lock
from time import sleep
from watchdog.observers.api import DEFAULT_EMITTER_TIMEOUT, BaseObserver, EventEmitter

assert system() == "Windows"
from watchdog.events import (
    DirCreatedEvent,
    DirDeletedEvent,
    DirModifiedEvent,
    DirMovedEvent,
    FileCreatedEvent,
    FileDeletedEvent,
    FileModifiedEvent,
    FileMovedEvent,
    generate_sub_created_events,
    generate_sub_moved_events,
)

from watchdog.observers.winapi import close_directory_handle, get_directory_handle, read_events  # noqa: E402

class WindowsNoDelayApiEmitter(EventEmitter):
    """
    Windows API-based emitter that uses ReadDirectoryChangesW
    to detect file system changes for a watch.
    """

    def __init__(self, event_queue, watch, timeout=DEFAULT_EMITTER_TIMEOUT):
        super().__init__(event_queue, watch, timeout)
        self._lock = Lock()
        self._handle = None

    def on_thread_start(self):
        self._handle = get_directory_handle(self.watch.path)

    if python_implementation() == "PyPy":

        def start(self):
            """PyPy needs some time before receiving events, see #792."""
            super().start()
            sleep(0.01)

    def on_thread_stop(self):
        if self._handle:
            close_directory_handle(self._handle)

    def _read_events(self):
        return read_events(self._handle, self.watch.path, self.watch.is_recursive)

    def queue_events(self, timeout):
        winapi_events = self._read_events()
        with self._lock:
            last_renamed_src_path = ""
            for winapi_event in winapi_events:
                src_path = ospath.join(self.watch.path, winapi_event.src_path)

                if winapi_event.is_renamed_old:
                    last_renamed_src_path = src_path
                elif winapi_event.is_renamed_new:
                    dest_path = src_path
                    src_path = last_renamed_src_path
                    if ospath.isdir(dest_path):
                        event = DirMovedEvent(src_path, dest_path)
                        if self.watch.is_recursive:
                            # HACK: We introduce a forced delay before
                            # traversing the moved directory. This will read
                            # only file movement that finishes within this
                            # delay time.
                            # time.sleep(WATCHDOG_TRAVERSE_MOVED_DIR_DELAY)
                            # The following block of code may not
                            # obtain moved events for the entire tree if
                            # the I/O is not completed within the above
                            # delay time. So, it's not guaranteed to work.
                            # TODO: Come up with a better solution, possibly
                            # a way to wait for I/O to complete before
                            # queuing events.
                            for sub_moved_event in generate_sub_moved_events(
                                src_path, dest_path
                            ):
                                self.queue_event(sub_moved_event)
                        self.queue_event(event)
                    else:
                        self.queue_event(FileMovedEvent(src_path, dest_path))
                elif winapi_event.is_modified:
                    cls = (
                        DirModifiedEvent
                        if ospath.isdir(src_path)
                        else FileModifiedEvent
                    )
                    self.queue_event(cls(src_path))
                elif winapi_event.is_added:
                    isdir = ospath.isdir(src_path)
                    cls = DirCreatedEvent if isdir else FileCreatedEvent
                    self.queue_event(cls(src_path))
                    if isdir and self.watch.is_recursive:
                        # If a directory is moved from outside the watched folder to inside it
                        # we only get a created directory event out of it, not any events for its children
                        # so use the same hack as for file moves to get the child events
                        # time.sleep(WATCHDOG_TRAVERSE_MOVED_DIR_DELAY)
                        sub_events = generate_sub_created_events(src_path)
                        for sub_created_event in sub_events:
                            self.queue_event(sub_created_event)
                elif winapi_event.is_removed:
                    self.queue_event(FileDeletedEvent(src_path))
                elif winapi_event.is_removed_self:
                    self.queue_event(DirDeletedEvent(self.watch.path))
                    self.stop()

class WindowsNoDelayObserver(BaseObserver):
    def __init__(self, timeout=1):
        super().__init__(emitter_class=WindowsNoDelayApiEmitter, timeout=timeout)