"""Command palette file commands for the active view: move, duplicate, delete, copy path."""

from __future__ import annotations

import os
import shutil

import sublime
import sublime_plugin


def active_file(window: sublime.Window) -> str | None:
    view = window.active_view()
    return view.file_name() if view else None


def resolve(old: str, new: str) -> str:
    """Expand ~, resolve a relative path against the file's folder, and move
    into an existing folder when the destination is one."""
    new = os.path.expanduser(new.strip())
    if not os.path.isabs(new):
        new = os.path.join(os.path.dirname(old), new)
    new = os.path.normpath(new)
    if os.path.isdir(new):
        new = os.path.join(new, os.path.basename(old))
    return new


def same_file(a: str, b: str) -> bool:
    """True for an identical path, or a case-only rename on a case-insensitive volume."""
    try:
        return os.path.samefile(a, b)
    except OSError:
        return False


def confirm_overwrite(new: str) -> bool:
    return sublime.ok_cancel_dialog(
        f"{new}\n\nalready exists. Move it to the trash and replace it?", "Replace"
    )


def trash(path: str) -> None:
    # Sublime's built-in delete_file sends to the trash and closes the view
    sublime.active_window().run_command("delete_file", {"files": [path], "prompt": False})


def project_folder(window: sublime.Window, path: str) -> str | None:
    """The deepest project folder containing path."""
    matches = [f for f in window.folders() if path.startswith(f.rstrip(os.sep) + os.sep)]
    return max(matches, key=len) if matches else None


class PathInputHandler(sublime_plugin.TextInputHandler):
    """Full path to the file, with the name (minus extension) selected."""

    def __init__(self, path: str) -> None:
        self.path = path

    def name(self) -> str:
        return "new_path"

    def placeholder(self) -> str:
        return "New path (relative to the file's folder, or absolute)"

    def initial_text(self) -> str:
        return self.path

    def initial_selection(self) -> list[tuple[int, int]]:
        stem = os.path.splitext(os.path.basename(self.path))[0]
        start = len(self.path) - len(os.path.basename(self.path))
        return [(start, start + len(stem))]

    def validate(self, text: str) -> bool:
        return bool(text.strip())

    def preview(self, text: str) -> str:
        if not text.strip():
            return ""
        new = resolve(self.path, text)
        exists = os.path.exists(new) and not same_file(self.path, new)
        return new + ("  (exists, will ask to replace)" if exists else "")


class FileCommand(sublime_plugin.WindowCommand):
    def is_enabled(self, **kwargs) -> bool:
        return active_file(self.window) is not None


class FileCommandsMoveCommand(FileCommand):
    def run(self, new_path: str) -> None:
        old = active_file(self.window)
        if old is None:
            return
        new = resolve(old, new_path)
        if new == old:
            return
        same = same_file(old, new)
        if os.path.exists(new) and not same:
            if not confirm_overwrite(new):
                return
            trash(new)
        try:
            os.makedirs(os.path.dirname(new), exist_ok=True)
            if same:
                # case-only rename: go through a temporary name
                temp = new + ".file-commands-temp"
                os.rename(old, temp)
                os.rename(temp, new)
            else:
                shutil.move(old, new)
        except OSError as e:
            sublime.error_message(f"Unable to move:\n\n{old}\n\nto\n\n{new}\n\n{e.strerror or e}")
            return
        for window in sublime.windows():
            view = window.find_open_file(old)
            if view:
                view.retarget(new)
        sublime.status_message(f"Moved to {new}")

    def input(self, args: dict) -> sublime_plugin.CommandInputHandler | None:
        old = active_file(self.window)
        if "new_path" not in args and old:
            return PathInputHandler(old)
        return None

    def input_description(self) -> str:
        return "Move"


class FileCommandsDuplicateCommand(FileCommand):
    def run(self, new_path: str) -> None:
        old = active_file(self.window)
        if old is None:
            return
        new = resolve(old, new_path)
        if same_file(old, new) or new == old:
            sublime.error_message("The copy needs a different name or folder.")
            return
        if os.path.exists(new):
            if not confirm_overwrite(new):
                return
            trash(new)
        try:
            os.makedirs(os.path.dirname(new), exist_ok=True)
            shutil.copy2(old, new)
        except OSError as e:
            sublime.error_message(f"Unable to copy:\n\n{old}\n\nto\n\n{new}\n\n{e.strerror or e}")
            return
        self.window.open_file(new)

    def input(self, args: dict) -> sublime_plugin.CommandInputHandler | None:
        old = active_file(self.window)
        if "new_path" not in args and old:
            return PathInputHandler(old)
        return None

    def input_description(self) -> str:
        return "Duplicate As"


class FileCommandsDeleteCommand(FileCommand):
    def run(self) -> None:
        path = active_file(self.window)
        if path:
            self.window.run_command("delete_file", {"files": [path], "prompt": True})


class FileCommandsCopyNameCommand(FileCommand):
    def run(self) -> None:
        path = active_file(self.window)
        if path:
            sublime.set_clipboard(os.path.basename(path))
            sublime.status_message("Copied name")


class FileCommandsCopyPathCommand(FileCommand):
    def run(self) -> None:
        path = active_file(self.window)
        if path:
            sublime.set_clipboard(path)
            sublime.status_message("Copied path")


class FileCommandsCopyRelativePathCommand(FileCommand):
    def run(self) -> None:
        path = active_file(self.window)
        if path:
            folder = project_folder(self.window, path)
            sublime.set_clipboard(os.path.relpath(path, folder) if folder else path)
            sublime.status_message("Copied relative path")
