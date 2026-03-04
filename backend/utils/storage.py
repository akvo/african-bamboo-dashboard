import os
import shutil
from pathlib import Path

from django.conf import settings


def get_path(path: str):
    """Return the full filesystem path for a
    path relative to settings.STORAGE_PATH."""
    return f"{settings.STORAGE_PATH}/{path}"


def upload(
    file: str,
    folder: str = None,
    filename: str = None,
):
    """Copy *file* into persistent storage.

    Returns the path **relative to
    settings.STORAGE_PATH** so it can be passed directly
    to check() / delete() / get_path().
    """
    if not filename:
        filename = file.split("/")[-1]
    if folder:
        rel_path = f"{folder}/{filename}"
    else:
        rel_path = filename
    full = get_path(rel_path)
    Path(full).parent.mkdir(
        parents=True, exist_ok=True
    )
    shutil.copy2(file, full)
    return rel_path


def delete(path: str):
    """Remove a file from storage.

    *path* is relative to settings.STORAGE_PATH.
    """
    os.remove(get_path(path))
    return path


def check(path: str):
    """Return True if *path* exists in storage.

    *path* is relative to settings.STORAGE_PATH.
    """
    return Path(get_path(path)).is_file()


def download(path: str):
    """Copy a storage file to ./tmp/ and return
    the tmp path.

    *path* is relative to settings.STORAGE_PATH.
    """
    tmp_file = path.split("/")[-1]
    tmp_file = f"./tmp/{tmp_file}"
    shutil.copy2(get_path(path), tmp_file)
    return tmp_file
