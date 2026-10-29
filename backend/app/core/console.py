"""Keep console output safe on terminals with limited character encodings."""
import sys


def configure_console_output() -> None:
    """Escape unsupported characters while preserving the terminal's encoding."""
    for stream in (sys.stdout, sys.stderr):
        reconfigure = getattr(stream, "reconfigure", None)
        if reconfigure is not None:
            reconfigure(errors="backslashreplace")
