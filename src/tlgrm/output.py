"""Stdout output helper. Command results are written as JSON to stdout; all
logging goes to stderr (see logging setup) so stdout stays machine-readable."""

import json


def emit(obj):
    print(json.dumps(obj, indent=2, ensure_ascii=False))
