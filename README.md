# File Viewer

A portable, keyboard-driven multimedia file viewer and playlist handler written in Python using PyQt5 and VLC. This app allows you to view and make playlists to sort files . Display, randomize, save and relocate files with customizable key binds. Moderately fast, lots of code, lots of bugs, but still useable and a good platform to build off of. Most of the code was generated using GPT 4o. Feel free to fork and build off of :)

---

## Features

### 🖼️ Media Viewer
- Supports images (`.png`, `.jpg`, `.bmp`), GIFs, and videos (`.mp4`, `.avi`, `.mov`, `.mkv`)
- Automatically scales media to fit
- Displays file path above the viewer (truncated, selectable)

### 🎛️ Keybind Navigation
- Navigate media using keybinds (customizable via `preferences.json`)
- Default keys:
  - `↑ / ↓` — Move between files
  - `← / →` — Seek video (±5 sec)
  - `0` — Add current file to playlist
  - `.` — Move current file to a target folder
  - `1` — Load random folder of files
- Click left/right half of viewer to move previous/next

### 🧠 Playlists
- Create multiple playlists saved as `.json`
- Right-click any playlist to:
  - Rename
  - Delete
  - Clean missing entries
  - Show in folder
- Files are stored as relative paths for portability

### 🖱️ Right-Click File List Actions
- Add selected to playlist
- Show in folder
- Delete from disk
- Rename file
- Copy file paths to clipboard

### 📁 Move Mode
- Press `.` to move the current file to a selected destination folder
- Path is remembered for session
- Viewer automatically advances to next file

### 🔄 Playlist Auto-Recovery (planned)
- If files are moved, viewer can attempt to relocate them by filename

---

## Configuration

### `preferences.json`
Customize keybindings:

```json
{
  "add_file_to_playlist": "Key_0",
  "next_file": "Key_Down",
  "previous_file": "Key_Up",
  "seek_left": "Key_Left",
  "seek_right": "Key_Right",
  "play_random_folder": "Key_1",
  "move_to_folder": "Key_Period"
}
