"""Stdout output helper. Command results are written as JSON to stdout; all
logging goes to stderr (see logging setup) so stdout stays machine-readable."""

import json
from typing import Any


def emit(obj: Any) -> None:
    print(json.dumps(obj, indent=2, ensure_ascii=False))
