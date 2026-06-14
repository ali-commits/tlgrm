from importlib.metadata import version, PackageNotFoundError

try:
    __version__ = version("tlgrm")
except PackageNotFoundError:  # not installed (e.g. running from a source tree)
    __version__ = "0.0.0+dev"
