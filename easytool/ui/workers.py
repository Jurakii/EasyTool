"""Run slow work (network, unzipping) off Maya's main thread and hand the result back to it.

Worker threads never touch Qt: they put results on a plain queue, and a timer on the main
thread delivers them. Creating or signalling Qt objects from Python threads crashes PySide2
inside Maya, so keep it that way.
"""
import itertools
import queue
import threading
import traceback

from easytool.qt import QtCore

_results = queue.Queue()
_callbacks = {}
_ids = itertools.count()
_timer = None


def _deliver() -> None:
    while True:
        try:
            job_id, result, error = _results.get_nowait()
        except queue.Empty:
            break
        on_done, on_error = _callbacks.pop(job_id)
        try:
            if error is None:
                on_done(result)
            else:
                on_error(error)
        except Exception:  # a broken callback must not stop the others
            traceback.print_exc()
    if not _callbacks:
        _timer.stop()


def run_async(fn, on_done, on_error) -> None:
    """Call fn() on a worker thread, then on_done(result) or on_error(message) on the main thread."""
    global _timer
    if _timer is None:
        _timer = QtCore.QTimer()
        _timer.setInterval(50)
        _timer.timeout.connect(_deliver)
    job_id = next(_ids)
    _callbacks[job_id] = (on_done, on_error)

    def work():
        try:
            _results.put((job_id, fn(), None))
        except Exception as exc:  # shown to the user by on_error
            traceback.print_exc()
            _results.put((job_id, None, str(exc) or exc.__class__.__name__))

    threading.Thread(target=work, name="EasyToolWorker", daemon=True).start()
    if not _timer.isActive():
        _timer.start()
