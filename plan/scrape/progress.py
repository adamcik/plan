import sys
from contextlib import contextmanager

import tqdm
from tqdm.contrib.logging import logging_redirect_tqdm


def _bar(*args, **kwargs):
    if "disable" not in kwargs:
        stream = kwargs.get("file", sys.stderr)
        is_tty = bool(getattr(stream, "isatty", lambda: False)())
        kwargs["disable"] = not is_tty
    return tqdm.tqdm(*args, **kwargs)


@contextmanager
def progress(*args, **kwargs):
    with logging_redirect_tqdm():
        with _bar(*args, **kwargs) as bar:
            yield bar
