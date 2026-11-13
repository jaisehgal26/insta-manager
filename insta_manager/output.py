from __future__ import annotations

import json
import sys
from typing import Any

from rich.console import Console

console = Console(stderr=True)


def emit(data: Any, *, json_mode: bool) -> None:
    if json_mode:
        print(json.dumps(data, indent=2, default=str))
    else:
        if isinstance(data, (dict, list)):
            console.print_json(json.dumps(data, default=str))
        else:
            console.print(data)


def error_exit(message: str, *, code: int = 1, json_mode: bool = False, detail: Any = None) -> None:
    payload = {"ok": False, "error": message}
    if detail is not None:
        payload["detail"] = detail
    if json_mode:
        print(json.dumps(payload, indent=2, default=str))
    else:
        console.print(f"[red]Error:[/red] {message}")
        if detail:
            console.print(detail)
    raise SystemExit(code)
