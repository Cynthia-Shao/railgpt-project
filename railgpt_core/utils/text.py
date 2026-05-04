from __future__ import annotations

from pathlib import Path


COMMON_ENCODINGS = ("utf-8", "utf-8-sig", "gb18030", "gbk")


def read_text_file(path: str | Path) -> str:
    file_path = Path(path)
    last_error: UnicodeDecodeError | None = None

    for encoding in COMMON_ENCODINGS:
        try:
            return file_path.read_text(encoding=encoding)
        except UnicodeDecodeError as exc:
            last_error = exc

    if last_error is not None:
        raise last_error

    return file_path.read_text()


def normalize_text(text: str) -> str:
    return text.replace("\r\n", "\n").replace("\r", "\n").strip()
