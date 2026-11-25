"""SabreBat: battery level of the Corsair Sabre v2 Pro wireless mouse on Linux."""

from .cli import main

__all__ = ["main"]


def __getattr__(name):
    # __version__ is looked up on first use, so a plain battery query does not
    # pay for importing importlib.metadata.
    if name == "__version__":
        from importlib.metadata import PackageNotFoundError, version

        try:
            value = version("SabreBat")
        except PackageNotFoundError:
            value = "unknown"

        globals()["__version__"] = value
        return value

    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
