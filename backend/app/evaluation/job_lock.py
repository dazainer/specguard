"""Fence artifact writers during recovery on the supported single host."""
from contextlib import contextmanager
import fcntl
import time


@contextmanager
def job_lock(store, run_id, timeout=45):
    directory=store.path.parent/'job-locks'
    directory.mkdir(parents=True,exist_ok=True,mode=0o700)
    with (directory/(run_id+'.lock')).open('a') as lock:
        deadline=time.monotonic()+timeout
        while True:
            try:
                fcntl.flock(lock,fcntl.LOCK_EX | fcntl.LOCK_NB)
                break
            except BlockingIOError:
                if time.monotonic()>=deadline:
                    raise RuntimeError('Previous job process has not released its artifact lock')
                time.sleep(.1)
        yield
