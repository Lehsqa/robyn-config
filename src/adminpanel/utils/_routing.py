"""Server route registration helpers for adminpanel scaffolding."""

from __future__ import annotations

import re
from pathlib import Path


def _ensure_call_before_main_guard(file_path: Path, call_line: str) -> None:
    if not file_path.exists():
        return

    lines = file_path.read_text().split("\n")
    stripped_call = call_line.strip()
    if any(line.strip() == stripped_call for line in lines):
        return

    for idx, line in enumerate(lines):
        if line.startswith("if __name__") and "__main__" in line:
            lines.insert(idx, call_line)
            if idx + 1 < len(lines) and lines[idx + 1].strip():
                lines.insert(idx + 1, "")
            file_path.write_text("\n".join(lines))
            return

    if lines and lines[-1].strip():
        lines.append("")
    lines.append(call_line)
    file_path.write_text("\n".join(lines))


def _ensure_route_registrar(file_path: Path, registrar: str) -> bool:
    if not file_path.exists():
        return False

    lines = file_path.read_text().split("\n")
    if any(registrar in line for line in lines):
        return True

    for idx, line in enumerate(lines):
        if "route_registrars=" not in line:
            continue

        key = "route_registrars="
        value_start = line.find(key)

        if "(" in line and ")" in line and value_start != -1:
            tuple_start = line.find("(", value_start + len(key))
            if tuple_start == -1:
                continue

            depth = 0
            tuple_end = None
            for position in range(tuple_start, len(line)):
                char = line[position]
                if char == "(":
                    depth += 1
                elif char == ")":
                    depth -= 1
                    if depth == 0:
                        tuple_end = position
                        break
            if tuple_end is None:
                continue

            inner = line[tuple_start + 1 : tuple_end]
            items = [item.strip() for item in inner.split(",") if item.strip()]
            items.append(registrar)

            if len(items) == 1:
                replacement = f"({items[0]},)"
            else:
                replacement = f"({', '.join(items)})"

            lines[idx] = (
                f"{line[:tuple_start]}{replacement}{line[tuple_end + 1 :]}"
            )
            file_path.write_text("\n".join(lines))
            return True

        start_idx = idx
        end_idx = None
        for j in range(start_idx + 1, len(lines)):
            if ")" in lines[j]:
                end_idx = j
                break
        if end_idx is None:
            return False

        if any(registrar in lines[j] for j in range(start_idx + 1, end_idx)):
            return True

        indent = None
        for j in range(start_idx + 1, end_idx):
            if lines[j].strip():
                indent = re.match(r"(\s*)", lines[j]).group(1)
                break
        if indent is None:
            indent = re.match(r"(\s*)", lines[start_idx]).group(1) + "    "

        lines.insert(end_idx, f"{indent}{registrar},")
        file_path.write_text("\n".join(lines))
        return True

    return False
