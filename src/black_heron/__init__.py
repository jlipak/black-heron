"""Black Heron — multi-lens repository audit with an adversarial verifier."""
from importlib.metadata import PackageNotFoundError, version

try:
    __version__ = version("black-heron")
except PackageNotFoundError:  # source checkout without an install
    __version__ = "0.0.0+unknown"

__all__ = ["__version__"]
