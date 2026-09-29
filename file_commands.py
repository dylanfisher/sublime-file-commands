"""File commands for the active view: rename, move, duplicate, delete, copy path."""

from __future__ import annotations

import functools
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


def show_path_panel(window: sublime.Window, caption: str, old: str, text: str, on_done) -> None:
    """Ask for a path in the input panel at the bottom of the window, with the
    file name (minus extension) selected when it starts from the file's own
    path or name."""
    window.run_command("hide_panel")
    view = window.show_input_panel(caption, text, on_done, None, None)
    name = os.path.basename(old)
    if text in (old, name):
        start = len(text) - len(name)
        view.sel().clear()
        view.sel().add(sublime.Region(start, start + len(os.path.splitext(name)[0])))


class FileCommand(sublime_plugin.WindowCommand):
    def is_enabled(self, **kwargs) -> bool:
        return active_file(self.window) is not None


class FileCommandsMoveCommand(FileCommand):
    def run(self, new_path: str | None = None) -> None:
        old = active_file(self.window)
        if old is None:
            return
        if new_path is None:
            self.show_panel(old, old)
        else:
            self.move(old, new_path)

    def show_panel(self, old: str, text: str) -> None:
        show_path_panel(self.window, "New Location:", old, text, functools.partial(self.move, old))

    def move(self, old: str, new_path: str) -> None:
        if not new_path.strip():
            return
        new = resolve(old, new_path)
        if new == old:
            return
        same = same_file(old, new)
        if os.path.exists(new) and not same:
            if not confirm_overwrite(new):
                self.show_panel(old, new_path)
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
            self.show_panel(old, new_path)
            return
        for window in sublime.windows():
            view = window.find_open_file(old)
            if view:
                view.retarget(new)
        sublime.status_message(f"Moved to {new}")


class FileCommandsRenameCommand(FileCommandsMoveCommand):
    """Move, starting from just the file name. A name resolves against the
    file's folder, so a relative or absolute path still moves it."""

    def run(self, new_name: str | None = None) -> None:
        old = active_file(self.window)
        if old is None:
            return
        if new_name is None:
            self.show_panel(old, os.path.basename(old))
        else:
            self.move(old, new_name)

    def show_panel(self, old: str, text: str) -> None:
        show_path_panel(self.window, "New Name:", old, text, functools.partial(self.move, old))


class FileCommandsDuplicateCommand(FileCommand):
    def run(self, new_path: str | None = None) -> None:
        old = active_file(self.window)
        if old is None:
            return
        if new_path is None:
            self.show_panel(old, old)
        else:
            self.duplicate(old, new_path)

    def show_panel(self, old: str, text: str) -> None:
        show_path_panel(
            self.window, "Duplicate As:", old, text, functools.partial(self.duplicate, old)
        )

    def duplicate(self, old: str, new_path: str) -> None:
        if not new_path.strip():
            return
        new = resolve(old, new_path)
        if same_file(old, new) or new == old:
            sublime.error_message("The copy needs a different name or folder.")
            self.show_panel(old, new_path)
            return
        if os.path.exists(new):
            if not confirm_overwrite(new):
                self.show_panel(old, new_path)
                return
            trash(new)
        try:
            os.makedirs(os.path.dirname(new), exist_ok=True)
            shutil.copy2(old, new)
        except OSError as e:
            sublime.error_message(f"Unable to copy:\n\n{old}\n\nto\n\n{new}\n\n{e.strerror or e}")
            self.show_panel(old, new_path)
            return
        self.window.open_file(new)


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
