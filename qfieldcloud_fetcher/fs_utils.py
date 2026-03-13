#!/usr/bin/env python3
import os
import pwd
import grp
import stat
from pathlib import Path


def current_user_label() -> str:
    uid = os.geteuid()
    gid = os.getegid()
    try:
        user = pwd.getpwuid(uid).pw_name
    except KeyError:
        user = str(uid)
    try:
        group = grp.getgrgid(gid).gr_name
    except KeyError:
        group = str(gid)
    return f"{user}:{group}"


def describe_path(path: Path) -> str:
    try:
        st = path.stat()
    except FileNotFoundError:
        return f"{path} [missing]"
    except PermissionError:
        return f"{path} [permission denied]"

    try:
        owner = pwd.getpwuid(st.st_uid).pw_name
    except KeyError:
        owner = str(st.st_uid)
    try:
        group = grp.getgrgid(st.st_gid).gr_name
    except KeyError:
        group = str(st.st_gid)

    mode = stat.S_IMODE(st.st_mode)
    return f"{path} [owner={owner}:{group} mode={mode:o}]"


def nearest_existing_parent(path: Path) -> Path:
    probe = path
    while True:
        try:
            probe.stat()
            return probe
        except FileNotFoundError:
            if probe.parent == probe:
                return probe
            probe = probe.parent
        except PermissionError:
            return probe


def require_directory_access(path: Path, purpose: str) -> None:
    existing = nearest_existing_parent(path)
    if path.exists():
        if os.access(path, os.W_OK | os.X_OK):
            return
        raise SystemExit(permission_error_message(path, existing, purpose))

    if os.access(existing, os.W_OK | os.X_OK):
        return
    raise SystemExit(permission_error_message(path, existing, purpose))


def require_replaceable_tree(path: Path, purpose: str) -> None:
    parent = path.parent
    if not os.access(parent, os.W_OK | os.X_OK):
        raise SystemExit(permission_error_message(path, nearest_existing_parent(parent), purpose))

    if not path.exists():
        return

    blocked: Path | None = None

    def onerror(err):
        nonlocal blocked
        blocked = Path(getattr(err, "filename", path))

    for root, dirnames, _filenames in os.walk(path, onerror=onerror):
        root_path = Path(root)
        if not os.access(root_path, os.W_OK | os.X_OK):
            blocked = root_path
            break
        for dirname in dirnames:
            dir_path = root_path / dirname
            if not os.access(dir_path, os.W_OK | os.X_OK):
                blocked = dir_path
                break
        if blocked is not None:
            break

    if blocked is not None:
        raise SystemExit(permission_error_message(path, blocked, purpose))


def permission_error_message(target: Path, blocked: Path, purpose: str) -> str:
    return (
        f"Permission error while trying to {purpose}.\n"
        f"Current user: {current_user_label()}\n"
        f"Target: {describe_path(target)}\n"
        f"Blocked at: {describe_path(blocked)}\n"
        "This pipeline must run with a single service user, or you need to fix ownership/permissions "
        "on the existing project folders before retrying."
    )
