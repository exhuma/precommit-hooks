#!/usr/bin/env python3
"""
This script checks for the presence of debug markers in the code.
"""
import sys
from difflib import unified_diff
from io import BytesIO
from subprocess import CalledProcessError
from typing import Iterable, cast

from git import Diff, Repo
from git.objects.base import Object


def read_blob(blob: Object | None) -> str:
    """
    Read the contents of a blob from GitPython and return it as a string.

    :param blob: The blob to read
    :return: The contents of the blob as a string
    """
    if not blob:
        return ""
    buffer = BytesIO()
    blob.stream_data(buffer)  # type: ignore
    try:
        return buffer.getvalue().decode("utf8")
    except UnicodeDecodeError:
        # Not a text-file most likely and we'll ignore it
        return ""


def parse_line_number(line: str) -> int:
    """
    Given a unified-diff header in the format of "@@ -14,0 +15 @@", extract the
    line-number as it appears in the target file.

    :param line: A single line from a unified-diff
    :return: The line number

    Example:

    >>> parse_line_number('@@ -14,0 +20,3 @@')
    20
    """
    if not line.startswith("@@"):
        raise ValueError("Not a unified-diff header")
    parts = line.split(" ")
    if len(parts) != 4:
        raise ValueError("Not a unified-diff header")
    return int(parts[2].split(",")[0])


def collect_errors(filename: str, data_a: str, data_b: str) -> list[str]:
    """
    Given two versions of a file, collect all lines that contain a debug marker.

    :param filename: The name of the file
    :param data_a: The original version of the file
    :param data_b: The new version of the file
    :return: A list of errors that should be reported
    """
    errors: list[str] = []
    diff_result = unified_diff(
        data_b.splitlines(), data_a.splitlines(), lineterm="", n=0
    )
    line_number = 1
    for line in diff_result:
        if line.startswith("@@"):
            line_number = parse_line_number(line)
        if not line.startswith("+") or line.strip() == "+++":
            # Only lines with a "+" are incoming changes. We should not complain
            # if a debug-marker is *removed* so we skip those.
            continue
        if "# xxx" in line.lower():
            errors.append(f"Debug marker detected at {filename}:{line_number}")
        if line.startswith("+"):
            line_number += 1
    return errors


def main():
    """
    Main entry-point for the pre-commit hook.
    """
    repo = Repo(".")
    try:
        against = repo.git.rev_parse("HEAD", verify=True)
    except CalledProcessError:
        against = ""
    if not against:
        # Initial commit: diff against an empty tree object
        against = "4b825dc642cb6eb9a060e54bf8d69288fbee4904"
    errors: list[str] = []
    diff_result = cast(Iterable[Diff], repo.index.diff(against))  # type: ignore
    for diff in diff_result:
        if diff.a_blob == diff.b_blob or diff.b_blob is None:
            continue
        data_a = read_blob(diff.a_blob)
        data_b = read_blob(diff.b_blob)
        errors.extend(collect_errors(diff.b_path or "", data_a, data_b))
    if errors:
        for error in errors:
            print(error)
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
