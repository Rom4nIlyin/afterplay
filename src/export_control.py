"""Cooperative cancellation of one editor export and its exact FFmpeg process."""
import subprocess
import threading


class ExportCancelled(Exception):
    pass


class ExportControl:
    def __init__(self, job):
        self.job = job
        self.lock = threading.RLock()
        self.cancelled = threading.Event()
        self.process = None
        self.sealed = False
        job.update(cancellable=True, cancel_requested=False)

    def check(self):
        if self.cancelled.is_set():
            raise ExportCancelled('Экспорт отменён')

    def start(self, command, **kwargs):
        with self.lock:
            self.check()
            self.process = subprocess.Popen(command, **kwargs)
            return self.process

    def release(self, process):
        with self.lock:
            if self.process is process:
                self.process = None

    def cancel(self):
        with self.lock:
            if self.sealed:
                return False
            self.cancelled.set()
            self.job.update(cancel_requested=True, cancellable=False, message='Отмена экспорта…')
            if self.process is not None and self.process.poll() is None:
                try:
                    self.process.terminate()
                except OSError:
                    # A process that exited during the check needs no further signal.
                    if self.process.poll() is None:
                        raise
            return True

    def commit(self):
        """Serialize the final rename against cancel; never acknowledge both."""
        with self.lock:
            self.check()
            self.sealed = True
            self.job.update(cancellable=False, message='Завершение экспорта…')
