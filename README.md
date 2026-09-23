# FileCommands

Command palette file commands for the active file, split out of SideBarEnhancements:

- **File: Move**: edit the full path (relative paths resolve against the file's folder, an existing folder moves the file into it, missing folders get created). Any open views follow the file.
- **File: Duplicate**: copy to a new path and open it.
- **File: Reveal**: show the file in Finder.
- **File: Locate**: select the file in the side bar.
- **File: Delete**: move to the trash (Sublime's built-in `delete_file`).
- **File: Copy Name / Copy Path / Copy Relative Path**

Sublime's built-in **File: Rename File** covers renaming in place.

Install by symlinking this repo into `Packages/FileCommands`.
