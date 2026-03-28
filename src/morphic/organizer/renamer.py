"""
Batch file renaming with fixed token templates.

Supported tokens: ``{date}``, ``{datetime}``, ``{seq}``, ``{seq:N}``,
``{original}``, ``{ext}``.
"""

from __future__ import annotations

import logging
import os
import re
import shutil
from pathlib import Path

from morphic.organizer.date_sorter import get_file_date
from morphic.shared.constants import ALL_EXTENSIONS
from morphic.shared.utils import find_files_by_extension

logger = logging.getLogger(__name__)


def _render_name(
    template: str,
    path: str,
    seq: int,
) -> str:
    """Expand a rename template for a single file.

    Tokens
    ------
    ``{date}``
        ``YYYY-MM-DD`` from EXIF or mtime.
    ``{datetime}``
        ``YYYY-MM-DD_HH-MM-SS``.
    ``{seq}``
        Zero-padded sequence number (default 4 digits).
    ``{seq:N}``
        Sequence number padded to *N* digits.
    ``{original}``
        Original filename without extension.
    ``{ext}``
        Original extension including the dot.
    """
    dt = get_file_date(path)
    p = Path(path)

    result = template
    result = result.replace("{date}", dt.strftime("%Y-%m-%d"))
    result = result.replace("{datetime}", dt.strftime("%Y-%m-%d_%H-%M-%S"))
    result = result.replace("{original}", p.stem)
    result = result.replace("{ext}", p.suffix)

    # Handle {seq:N} patterns
    seq_pattern = re.compile(r"\{seq:(\d+)\}")
    match = seq_pattern.search(result)
    if match:
        pad = int(match.group(1))
        result = seq_pattern.sub(str(seq).zfill(pad), result)
    # Handle plain {seq} (default 4-digit padding)
    result = result.replace("{seq}", str(seq).zfill(4))

    return result


def plan_rename(
    folder: str,
    template: str = "{date}_{seq}_{original}{ext}",
    operation: str = "move",
    start_seq: int = 1,
    output_folder: str | None = None,
) -> list[dict]:
    """Generate a rename plan without executing it.

    Parameters
    ----------
    folder : str
        Source folder to scan.
    template : str
        Naming template with tokens.
    operation : str
        ``"move"`` (rename in place) or ``"copy"`` (write to
        *output_folder*).
    start_seq : int
        Starting sequence number.
    output_folder : str, optional
        Destination folder for copies. Defaults to *folder*.

    Returns
    -------
    list[dict]
        List of ``{"source", "new_name", "destination", "conflict"}``
        entries.
    """
    dest_base = output_folder or folder
    paths = find_files_by_extension(folder, ALL_EXTENSIONS)

    # Sort by date then name for consistent sequencing
    dated = []
    for path in paths:
        dt = get_file_date(path)
        dated.append((dt, path))
    dated.sort(key=lambda x: (x[0], x[1]))

    plan: list[dict] = []
    seen_destinations: set[str] = set()

    for i, (dt, path) in enumerate(dated):
        seq = start_seq + i
        new_name = _render_name(template, path, seq)
        dest = os.path.join(dest_base, new_name)

        conflict = dest in seen_destinations or (
            os.path.exists(dest)
            and os.path.abspath(dest) != os.path.abspath(path)
        )
        seen_destinations.add(dest)

        plan.append(
            {
                "source": path,
                "new_name": new_name,
                "destination": dest,
                "conflict": conflict,
            }
        )

    return plan


def execute_rename(
    plan: list[dict],
    operation: str = "move",
) -> dict:
    """Execute a previously generated rename plan.

    Parameters
    ----------
    plan : list[dict]
        Plan from :func:`plan_rename`.
    operation : str
        ``"move"`` or ``"copy"``.

    Returns
    -------
    dict
        ``{"completed", "errors", "skipped", "total", "results"}``
    """
    if operation not in ("move", "copy"):
        raise ValueError("operation must be 'move' or 'copy'")

    results: list[dict] = []
    completed = 0
    errors = 0
    skipped = 0

    for entry in plan:
        src = entry["source"]
        dest = entry["destination"]

        if entry.get("conflict"):
            skipped += 1
            results.append(
                {
                    "source": src,
                    "destination": dest,
                    "status": "skipped",
                    "reason": "name conflict",
                }
            )
            continue

        try:
            os.makedirs(os.path.dirname(dest), exist_ok=True)
            if operation == "move":
                shutil.move(src, dest)
            else:
                shutil.copy2(src, dest)
            completed += 1
            results.append(
                {
                    "source": src,
                    "destination": dest,
                    "status": "ok",
                }
            )
        except Exception as e:
            errors += 1
            results.append(
                {
                    "source": src,
                    "destination": dest,
                    "status": "error",
                    "error": str(e),
                }
            )

    return {
        "completed": completed,
        "errors": errors,
        "skipped": skipped,
        "total": len(plan),
        "results": results,
    }
