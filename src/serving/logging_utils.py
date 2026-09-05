"""Small stdout/stderr tee used by the local planner entrypoints."""

from __future__ import annotations

from contextlib import contextmanager
from pathlib import Path
import sys
from collections.abc import Iterator
from typing import TextIO


class _Tee(TextIO):
    """Mirror text written to a stream into a line-buffered log file."""

    def __init__(self, stream: TextIO, log_file: TextIO) -> None:
        self._stream = stream
        self._log_file = log_file

    def write(self, text: str) -> int:
        self._stream.write(text)
        self._log_file.write(text)
        return len(text)

    def flush(self) -> None:
        self._stream.flush()
        self._log_file.flush()

    def fileno(self) -> int:
        return self._stream.fileno()

    def isatty(self) -> bool:
        return self._stream.isatty()

    @property
    def encoding(self) -> str | None:
        return self._stream.encoding


@contextmanager
def tee_output(path: Path, *, mode: str = "w") -> Iterator[None]:
    """Mirror an entrypoint's Python stdout and stderr to ``path``.

    Isaac Sim owns native stdout / stderr while its Kit application is starting.
    Redirecting those file descriptors through a Python pipe can change Kit's
    process behaviour.  Keep this logger deliberately small: BEHAVIOR's own
    progress, planner actions, and Python exceptions are mirrored here, while
    Isaac's native diagnostics remain in its standard Kit log.
    """
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open(mode, encoding="utf-8", buffering=1) as log_file:
        old_stdout, old_stderr = sys.stdout, sys.stderr
        sys.stdout = _Tee(old_stdout, log_file)
        sys.stderr = _Tee(old_stderr, log_file)
        try:
            yield
        finally:
            sys.stdout.flush()
            sys.stderr.flush()
            sys.stdout, sys.stderr = old_stdout, old_stderr
