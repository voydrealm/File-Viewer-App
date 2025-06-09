import sys
import os
import pygame
import shutil
import time
import random
import json
import ctypes 
import base64
import subprocess
from PyQt5.QtWidgets import (QInputDialog, QMenu, QAction, QMessageBox, QSizePolicy,
    QApplication, QLabel, QWidget, QVBoxLayout, QHBoxLayout, QListWidget, QListWidgetItem,
    QFileDialog, QMessageBox, QCheckBox, QSplitter, QComboBox, QFrame, QMenuBar, QMenu,
    QSlider, QTreeView, QFileSystemModel, QMainWindow, QDialog, QDialogButtonBox, QStackedWidget, QPushButton, )
from PyQt5.QtGui import QPixmap, QMovie, QTransform, QKeyEvent, QColor, QPainter, QIcon, QFont, QBrush
from PyQt5.QtCore import Qt, QTimer, QThread, pyqtSignal, QObject, QEvent, QElapsedTimer, QDir

DEBUG = True

def dprint(*args, **kwargs):
        if DEBUG:
            print(*args, **kwargs)


DOCUMENTS_DIR = os.path.join(os.path.expanduser("~"), "Documents")
ASSETS_DIR = os.path.join(DOCUMENTS_DIR, "assets")

APP_DIR = os.path.dirname(os.path.abspath(__file__))
PREF_FILE = os.path.join(ASSETS_DIR, "preferences.json")
PLAYLIST_DIR = os.path.join(ASSETS_DIR, "playlists")
os.makedirs(PLAYLIST_DIR, exist_ok=True)
CONFIG_FILE = os.path.join(ASSETS_DIR,"config.json")
FAVORITES_FILE = os.path.join(ASSETS_DIR, "favorites.json")
COLLECTION_PATH = os.path.join(PLAYLIST_DIR, "collection.json")

IMAGE_EXTENSIONS = ['.png', '.jpg', '.jpeg', '.bmp']
VIDEO_EXTENSIONS = ['.mp4', '.avi', '.mov', '.mkv']
GIF_EXTENSIONS = ['.gif']

def resource_path(relative):
    # Handle PyInstaller _MEIPASS or fallback to script's directory
    try:
        base_path = sys._MEIPASS
    except AttributeError:
        base_path = os.path.dirname(os.path.abspath(__file__))
    return os.path.join(base_path, relative)

vlc_dir = resource_path("bin/vlc")
os.environ["PATH"] = vlc_dir + os.pathsep + os.environ.get("PATH", "")

libvlc_path = os.path.join(vlc_dir, "libvlc.dll")
libvlccore_path = os.path.join(vlc_dir, "libvlccore.dll")

try:
    if os.path.exists(libvlc_path) and os.path.exists(libvlccore_path):
        ctypes.CDLL(libvlc_path)
        ctypes.CDLL(libvlccore_path)
    else:
        print("❌ VLC DLLs not found in", vlc_dir)
except Exception as e:
    print("❌ Failed to load VLC DLLs:", e)

import vlc
#vlc_instance = vlc.Instance(["--quiet"])


def safe_relpath(path, base):
    try:
        return os.path.relpath(path, base)
    except ValueError:
        return path  # fallback to absolute path if drives differ
    
def encode_path(path):
    return base64.urlsafe_b64encode(path.encode("utf-8")).decode("ascii")

def decode_path(encoded):
    
    return base64.urlsafe_b64decode(encoded.encode("ascii")).decode("utf-8")




from PyQt5.QtCore import QObject, pyqtSignal, QThread

from PyQt5.QtCore import QObject, QThread, pyqtSignal

class FileListWorker(QObject):
    finished = pyqtSignal(list)  # emits list of QListWidgetItem
    def __init__(self, files, collection, app_dir):
        super().__init__()
        self.files = files
        self.collection = collection
        self.app_dir = app_dir

    def run(self):
        items = []
        for path in self.files:
            name = os.path.basename(path)
            rel_path = safe_relpath(path, self.app_dir)

            # Ensure file is in collection
            if rel_path not in self.collection["files"]:
                self.collection["files"][rel_path] = {
                    "duration": None,
                    "imported": False,
                    "tags": []
                }

            meta = self.collection["files"].get(rel_path, {})
            imported = meta.get("imported", False)
            tags = meta.get("tags", [])
            exists = os.path.exists(path)

            # Label
            prefix = ""
            if not exists:
                prefix = "⚠️ "
            elif not imported:
                prefix = "🕓 "
            elif "favorite" in tags:
                prefix = "⭐ "

            label = f"{prefix}{name}"
            item = QListWidgetItem(label)

            # Style
            if not exists:
                item.setForeground(QBrush(QColor("#888")))
            elif not imported:
                item.setForeground(QBrush(QColor("#666")))
            elif "favorite" in tags:
                item.setForeground(QBrush(QColor("#ffd700")))

            items.append(item)

        dprint(f"📦 run(): emitting {len(items)} items")
        self.finished.emit(items)


class HandleSlider(QSlider):
    def __init__(self, viewer, *args, **kwargs):
        super().__init__(Qt.Horizontal, viewer)
        self.viewer = viewer
        self.setFixedHeight(30)
        self.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)
        self.setStyleSheet("background-color: transparent;")
        self.setMouseTracking(True)
        self.setFocusPolicy(Qt.StrongFocus)
        self.setAttribute(Qt.WA_TransparentForMouseEvents, False)

        self.smoothing_factor = 0.1  # Default smoothness
        self.current_pos = 0.0
        self.target_pos = 0.0

        self.start_handle = None  # Normalized 0–1
        self.end_handle = None
        self.drag_mode = None     # 'start', 'end', 'playhead'

        


    def format_time(self, seconds):
        minutes = int(seconds // 60)
        secs = int(seconds % 60)
        return f"{minutes:02}:{secs:02}"


    def update_smooth_position(self):
        #dprint("[TIMER] updating")  # 👈 add this
        if self.drag_mode:
            return
        speed = 0.25
        diff = self.target_pos - self.current_pos
        if abs(diff) < 0.001:
            self.current_pos = self.target_pos
        else:
            self.current_pos += diff * speed
        self.update()


    
    

    def paintEvent(self, event):
        painter = QPainter(self)
        w = self.width()
        h = self.height()

        bar_x = 50
        bar_w = w - 100  # 50px padding
        center_y = h // 2

        painter.setRenderHint(QPainter.Antialiasing)

        # Draw base slider bar
        painter.setPen(Qt.gray)
        painter.drawLine(bar_x, center_y, bar_x + bar_w, center_y)

        # Get zoom window and video info
        zoom_start = self.viewer.clip_zoom_start
        zoom_end = self.viewer.clip_zoom_end
        zoom_range = max(zoom_end - zoom_start, 0.01)
        full_duration = max(self.viewer.video_duration, 0.01)

        # Convert seconds to pixel position within zoom
        def to_px(seconds):
            return int(((seconds - zoom_start) / zoom_range) * bar_w + bar_x)

        # Draw selection highlight
        if self.start_handle is not None and self.end_handle is not None:
            start_sec = self.start_handle * full_duration
            end_sec = self.end_handle * full_duration

            if zoom_start <= end_sec and start_sec <= zoom_end:
                x1 = to_px(start_sec)
                x2 = to_px(end_sec)
                painter.setPen(Qt.NoPen)

                # Yellow selection bar
                painter.setBrush(QColor("yellow"))
                painter.drawRect(x1, center_y - 4, x2 - x1, 8)

                # Orange handles
                painter.setBrush(QColor("orange"))
                painter.drawRect(x1 - 4, 4, 8, h - 8)
                painter.drawRect(x2 - 4, 4, 8, h - 8)

        # Draw red playhead
        playhead_sec = self.viewer.current_time_sec
        if zoom_start <= playhead_sec <= zoom_end:
            px = to_px(playhead_sec)
            painter.setBrush(QColor("red"))
            painter.setPen(Qt.NoPen)
            painter.drawEllipse(px - 6, center_y - 6, 12, 12)

        # Draw zoom timestamps
        painter.setPen(QColor("white"))
        painter.drawText(5, center_y + 6, self.viewer.format_time(zoom_start))
        painter.drawText(w - 45, center_y + 6, self.viewer.format_time(zoom_end))



    def mousePressEvent(self, event):
        x = event.x()
        w = self.width()
        bar_x = 50
        bar_w = w - 100
        full_duration = self.viewer.video_duration
        zoom_start = self.viewer.clip_zoom_start
        zoom_end = self.viewer.clip_zoom_end
        zoom_range = max(zoom_end - zoom_start, 0.01)

        start_handle = self.start_handle or 0
        end_handle = self.end_handle or 1
        start_sec = start_handle * full_duration
        end_sec = end_handle * full_duration
        playhead_sec = self.current_pos * full_duration

        def to_px(sec):
            return int(((sec - zoom_start) / zoom_range) * bar_w + bar_x)

        x1 = to_px(start_sec)
        x2 = to_px(end_sec)
        px = to_px(playhead_sec)

        HIT_RADIUS = 10

        if abs(x - x1) < HIT_RADIUS:
            self.drag_mode = 'start'
        elif abs(x - x2) < HIT_RADIUS:
            self.drag_mode = 'end'
        elif abs(x - px) < HIT_RADIUS:
            self.drag_mode = 'playhead'
            if hasattr(self.parent(), "pause_video_for_scrub"):
                self.parent().pause_video_for_scrub()
        else:
            self.drag_mode = None



    def mouseMoveEvent(self, event):
        if not self.drag_mode:
            return

        x = event.x()
        w = self.width()
        bar_x = 50
        bar_w = w - 100
        pos = (x - bar_x) / bar_w
        pos = max(0, min(1, pos))

        zoom_start = self.viewer.clip_zoom_start
        zoom_end = self.viewer.clip_zoom_end
        zoom_range = max(zoom_end - zoom_start, 0.01)
        full_duration = self.viewer.video_duration

        absolute_time = zoom_start + pos * zoom_range
        normalized = max(0, min(1, absolute_time / full_duration))

        start = self.start_handle if self.start_handle is not None else 0
        end = self.end_handle if self.end_handle is not None else 1

        if self.drag_mode == 'start':
            self.start_handle = min(normalized, self.end_handle - 0.01)
        elif self.drag_mode == 'end':
            self.end_handle = max(normalized, self.start_handle - 0.01)
        elif self.drag_mode == 'playhead':
            self.current_pos = normalized
            self.target_pos = normalized
            self.seek_parent_video()



        self.update()



    def mouseReleaseEvent(self, event):
        if self.drag_mode == 'playhead':
            if hasattr(self.parent(), "scrub_video"):
                self.parent().scrub_video()

        # === Trigger zoom expansion after dragging handle ===
        video_duration = self.viewer.video_duration
        start_sec = (self.start_handle or 0) * video_duration
        end_sec = (self.end_handle or 1) * video_duration
        zoom_start = self.viewer.clip_zoom_start
        zoom_end = self.viewer.clip_zoom_end
        buffer = 1
        expand = 10

        if self.drag_mode == 'start' and start_sec - zoom_start < buffer:
            self.viewer.clip_zoom_start = max(0, zoom_start - expand)

        if self.drag_mode == 'end' and zoom_end - end_sec < buffer:
            self.viewer.clip_zoom_end = min(video_duration, zoom_end + expand)

        self.update()  # redraw with new zoom window
        self.drag_mode = None


    def set_playback_position(self, pos):
        self.current_pos = max(0, min(1, pos))
        self.update()

    def seek_parent_video(self):
        if hasattr(self.viewer, "vlc_player") and self.viewer.vlc_player:
            duration = self.viewer.vlc_player.get_length()
            if duration > 0:
                seek_ms = int(self.current_pos * duration)
                self.viewer.vlc_player.set_time(seek_ms)
                
class FileListWidget(QListWidget):
    def keyPressEvent(self, event):
        # Ignore so parent widget can handle it
        event.ignore()

class DuplicateScanWorker(QObject):
    finished = pyqtSignal(list)
    def __init__(self, all_files):
        super().__init__()
        self.all_files = all_files

    def run(self):
        from collections import defaultdict
        from PIL import Image
        import cv2
        import os

        key_map = defaultdict(list)

        for path in self.all_files:
            try:
                size = os.path.getsize(path)
                _, ext = os.path.splitext(path.lower())

                if ext in VIDEO_EXTENSIONS:
                    cap = cv2.VideoCapture(path)
                    length = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
                    fps = cap.get(cv2.CAP_PROP_FPS)
                    duration = round(length / fps, 2) if fps > 0 else 0
                    cap.release()
                    key = ("video", size, duration)

                elif ext in IMAGE_EXTENSIONS + GIF_EXTENSIONS:
                    with Image.open(path) as img:
                        width, height = img.size
                    key = ("image", size, width, height)

                else:
                    continue

                key_map[key].append(path)

            except Exception as e:
                dprint(f"⚠️ Error processing {path}: {e}")

        duplicates = [group for group in key_map.values() if len(group) > 1]
        flat_list = [item for group in duplicates for item in group]
        self.finished.emit(flat_list)

class FileLoaderWorker(QObject):
    finished = pyqtSignal(list)

    def __init__(self, source_dir):
        super().__init__()
        self.source_dir = source_dir

    def run(self):
        all_files = []
        for root, dirs, files in os.walk(self.source_dir):
            for file in files:
                full_path = os.path.join(root, file)
                if os.path.isfile(full_path):
                    all_files.append(full_path)
        self.finished.emit(all_files)

from PyQt5.QtWidgets import QLineEdit
from PyQt5.QtCore import Qt

class KeyCaptureLineEdit(QLineEdit):
    def keyPressEvent(self, event):
        qt_key = event.key()

        key_map = {
            Qt.Key_Space: "space",
            Qt.Key_Escape: "esc",
            Qt.Key_Return: "enter",
            Qt.Key_Enter: "enter",
            Qt.Key_Tab: "tab",
            Qt.Key_Backspace: "backspace",
            Qt.Key_Up: "up",
            Qt.Key_Down: "down",
            Qt.Key_Left: "left",
            Qt.Key_Right: "right",
        }

        if Qt.Key_F1 <= qt_key <= Qt.Key_F35:
            key_name = f"f{qt_key - Qt.Key_F1 + 1}"
        elif Qt.Key_0 <= qt_key <= Qt.Key_9:
            key_name = chr(qt_key)
        elif Qt.Key_A <= qt_key <= Qt.Key_Z:
            key_name = chr(qt_key).lower()
        else:
            key_name = key_map.get(qt_key, "")

        self.setText(key_name)



class PreferencesDialog(QDialog):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Preferences")
        self.setModal(True)
        self.setMinimumSize(500, 300)
        

        main_layout = QHBoxLayout(self)

        # === Left Sidebar ===
        self.sidebar = QListWidget()
        self.sidebar.setFixedWidth(200)
        self.sidebar.addItems(["Keybinds"])

        self.sidebar.setCurrentRow(0)
        main_layout.addWidget(self.sidebar)

        # === Right Content Area ===
        self.stack = QStackedWidget()
        main_layout.addWidget(self.stack)

        # Add individual pages
        #self.stack.addWidget(self.create_general_page())
        #self.stack.addWidget(self.create_viewers_page())
        #self.stack.addWidget(self.create_sorting_page())
        self.stack.addWidget(self.create_keybinds_page())
        self.load_keybinds()


        # Connect list to stack
        self.sidebar.currentRowChanged.connect(self.stack.setCurrentIndex)

        # === Buttons ===
        buttons = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)
        main_layout.addWidget(buttons)

    def create_keybinds_page(self):
        from PyQt5.QtWidgets import QFormLayout, QLineEdit
        from PyQt5.QtCore import Qt

        self.keybind_fields = {}
        widget = QWidget()
        layout = QFormLayout(widget)

        self.actions = {
            "add_file_to_playlist": "Add File to Playlist",
            "next_file": "Next File",
            "previous_file": "Previous File",
            "seek_left": "Seek Left",
            "seek_right": "Seek Right",
            "move_to_folder": "Move File",
            "play_random_folder": "Play Random Folder",
            "toggle_fullscreen": "Toggle Fullscreen",
            "rotate_left": "Rotate Left",
            "rotate_right": "Rotate Right",
            "randomize_list": "Randomize List"
        }

        for action, label in self.actions.items():
            field = KeyCaptureLineEdit()

            field.setPlaceholderText("e.g., A, space, esc, 1")
            self.keybind_fields[action] = field
            layout.addRow(label, field)

        
        layout.setAlignment(Qt.AlignTop)
        return widget

    def load_keybinds(self):
        try:
            with open(PREF_FILE, "r") as f:
                prefs = json.load(f)
        except Exception:
            prefs = {}

        for action, field in self.keybind_fields.items():
            raw = prefs.get(action, "")

            # Convert Qt key names to friendly strings
            if raw.startswith("Key_"):
                suffix = raw[4:].upper()

                # Special cases
                if suffix == "space":
                    field.setText("space")
                elif suffix == "escape":
                    field.setText("esc")
                elif suffix == "return":
                    field.setText("enter")
                elif suffix.startswith("num"):
                    field.setText(suffix)  # e.g. num1
                else:
                    field.setText(suffix)
            else:
                field.setText(raw)

    def create_general_page(self):
        widget = QWidget()
        layout = QVBoxLayout(widget)
        layout.addWidget(QLabel("General settings here."))
        layout.addStretch()
        return widget

    def create_viewers_page(self):
        widget = QWidget()
        layout = QVBoxLayout(widget)
        layout.addWidget(QLabel("Viewer layout, scaling, etc."))
        layout.addStretch()
        return widget

    def create_sorting_page(self):
        widget = QWidget()
        layout = QVBoxLayout(widget)

        layout.addWidget(QLabel("Default Sort Order:"))
        self.sort_combo = QComboBox()
        self.sort_combo.addItems([
            "Name (Asc)", "Name (Desc)",
            "Date (Oldest)", "Date (Newest)",
            "Size (Largest)", "Size (Smallest)",
            "Random",
        ])
        layout.addWidget(self.sort_combo)
        layout.addStretch()
        return widget
    
    def accept(self):
        from PyQt5.QtCore import Qt
        prefs = {}

        qt_keys = {v: k for k, v in Qt.__dict__.items() if isinstance(v, int) and k.startswith("Key_")}

        for action, field in self.keybind_fields.items():
            raw = field.text().strip()
            if not raw:
                continue

            key_upper = raw.upper()
            if not key_upper.startswith("KEY_"):
                # Try to auto-correct to valid Qt key name
                if len(key_upper) == 1 and key_upper.isalnum():
                    raw = f"Key_{key_upper}"
                elif key_upper == "SPACE":
                    raw = "Key_Space"
                elif key_upper == "ESC":
                    raw = "Key_Escape"
                elif key_upper == "ENTER":
                    raw = "Key_Return"
                elif key_upper == "TAB":
                    raw = "Key_Tab"
                elif key_upper.startswith("NUM") and key_upper[3:].isdigit():
                    raw = f"Key_{key_upper}"  # e.g., num1 → Key_Num1

            prefs[action] = raw

        try:
            with open(PREF_FILE, "w") as f:
                json.dump(prefs, f, indent=2)
            self.parent().load_preferences()
        except Exception as e:
            QMessageBox.warning(self, "Error", f"Failed to save preferences:\n{str(e)}")

        super().accept()





class ViewerPanel(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.layout = QVBoxLayout(self)
        self.label = QLabel("No file loaded")
        self.label.setAlignment(Qt.AlignCenter)
        self.label.setStyleSheet("background-color: #222; color: #aaa; padding: 20px;")
        self.layout.addWidget(self.label)
        self.file_path = None
        self.setStyleSheet("border: 1px solid #444;")

    def load_file(self, path):
        self.file_path = path
        self.label.setText(f"Loaded:\n{os.path.basename(path)}")

##################################################################################################################
##################################################################################################################
##################################################################################################################
class FileViewer(QMainWindow):
    def __init__(self):
        super().__init__()

         
        self._vlc_busy = False
        self._threads = []
        self.move_target_folder = None
        self.source_dir = ""
        self.dest_dir = ""
        self.files = []
        self.all_files = []
        self.current_index = 0
        self.fullscreen = False
        self.rotation_angle = 0  # 0, 90, 180, 270
        self.playlist_dir = PLAYLIST_DIR
        self.last_button_states = {}
        self._vlc_binding_pending = False
        self._last_video_path = None
        self.current_time_sec = 0.0
        self.collection = {"files": {}}
        self.active_threads = set()


        
        self.play_timer = QElapsedTimer()
        self.play_start_time = 0
        self.video_duration = 1  # fallback default
        
        self.clip_zoom_start = 0
        self.clip_zoom_end = 1  # Default to full video range

        self.clip_mode_active = False
        self.clip_start_sec = None
        self.clip_end_sec = None
      
        self.setWindowTitle("EDGR")
        self.resize(1200, 800)
        self.showMaximized()

        

        self.central_widget = QWidget()
        self.setCentralWidget(self.central_widget)
        self.outer_layout = QVBoxLayout(self.central_widget)




        self.main_layout = QHBoxLayout()
        self.main_layout.setContentsMargins(0, 0, 0, 0)
        self.main_layout.setSpacing(0)
        self.outer_layout.addLayout(self.main_layout)

        menu_bar = self.menuBar()

        # File Menu
        file_menu = menu_bar.addMenu("File")
        

        exit_action = QAction("Exit", self)
        exit_action.setShortcut("Ctrl+Q")
        exit_action.triggered.connect(self.close)


        preferences_action = QAction("Preferences", self)
        preferences_action.setShortcut("Ctrl+,")
        preferences_action.triggered.connect(self.open_preferences)
        file_menu.addAction(preferences_action)


        # Edit Menu
        edit_menu = menu_bar.addMenu("Edit")

        


        self.toast_label = QLabel("", self)
        self.toast_label.setStyleSheet("""
            QLabel {
                background-color: #222;
                color: white;
                padding: 6px 12px;
                border-radius: 6px;
                font-size: 12pt;
            }
        """)
        self.toast_label.setAlignment(Qt.AlignCenter)
        self.toast_label.setVisible(False)
        self.toast_label.setFixedHeight(30)
        self.toast_label.setAttribute(Qt.WA_TransparentForMouseEvents)
        
        
        QApplication.setStyle("Fusion")

        # Info Panel (Left Panel)
        self.info_panel = QFrame()
        self.info_panel.setMinimumWidth(300)
        self.info_panel.setMaximumWidth(300)
        self.info_panel.setStyleSheet("background-color: #1a1a1a; padding: 8px;")
        self.info_layout = QVBoxLayout(self.info_panel)

        self.source_label = QLabel("📁 Source: Not Set")
        self.dest_label = QLabel("📦 Destination: Not Set")


        self.fs_view = QTreeView()
        self.fs_model = QFileSystemModel()
        self.fs_model.setRootPath(self.source_dir or QDir.homePath())
        self.fs_model.setFilter(QDir.AllDirs | QDir.Files | QDir.NoDotAndDotDot)
        self.fs_model.setNameFilters(["*.png", "*.jpg", "*.mp4", "*.mov", "*.gif"])
        self.fs_model.setNameFilterDisables(False)
        self.fs_model.setFilter(QDir.AllDirs | QDir.NoDotAndDotDot | QDir.Drives)
        self.fs_view.setModel(self.fs_model)

        for lbl in [self.source_label, self.dest_label]:
            lbl.setWordWrap(True)
            lbl.setStyleSheet("color: #bbb; font-size: 10pt;")
            self.info_layout.addWidget(lbl)
        
        self.info_layout.addStretch()

        # -- File Explorer Panel (wrapped with header) --
        self.fs_panel = QWidget()
        fs_layout = QVBoxLayout(self.fs_panel)
        fs_layout.setContentsMargins(0, 0, 0, 0)
        fs_layout.setSpacing(0)

        fs_label = QLabel("📁 File Explorer:")
        fs_label.setStyleSheet("""
            QLabel {
                background-color: #2a2a2a;
                color: #ccc;
                padding: 4px 8px;
                font-size: 9pt;
                font-weight: bold;
            }
        """)

        self.fs_list = QListWidget()
        self.fs_list.setStyleSheet("QListWidget { font-size: 9pt; }")
        self.fs_list.setSelectionMode(QListWidget.SingleSelection)
        self.fs_list.setContextMenuPolicy(Qt.CustomContextMenu)
        self.fs_list.itemDoubleClicked.connect(self.handle_explorer_item_click)
        self.fs_list.customContextMenuRequested.connect(self.show_explorer_context_menu)
        self.fs_list.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)

        fs_layout.addWidget(fs_label)
        fs_layout.addWidget(self.fs_list)

        # -- Favorites Panel --
        self.fav_panel = QWidget()
        fav_layout = QVBoxLayout(self.fav_panel)
        fav_layout.setContentsMargins(0, 0, 0, 0)
        fav_layout.setSpacing(0)

        # Header label with light background
        fav_label = QLabel("⭐ Favorite Folders")
        fav_label.setStyleSheet("""
            QLabel {
                background-color: #2a2a2a;
                color: #ccc;
                padding: 4px 8px;
                font-size: 9pt;
                font-weight: bold;
            }
        """)

        self.fav_list = QListWidget()
        self.fav_list.setStyleSheet("QListWidget { font-size: 9pt; }")
        self.fav_list.setFixedHeight(100)
        self.fav_list.itemClicked.connect(self.handle_favorite_selected)
        self.fav_list.setContextMenuPolicy(Qt.CustomContextMenu)
        self.fav_list.customContextMenuRequested.connect(self.show_favorite_context_menu)


        fav_layout.addWidget(fav_label)
        fav_layout.addWidget(self.fav_list)

        # -- Playlists Panel (no outer border) --
        self.playlist_panel = QWidget()
        playlist_layout = QVBoxLayout(self.playlist_panel)
        playlist_layout.setContentsMargins(0, 0, 0, 0)
        playlist_layout.setSpacing(0)

        playlist_header = QWidget()
        playlist_header.setStyleSheet("background-color: #2a2a2a;")

        playlist_header_layout = QHBoxLayout(playlist_header)
        playlist_header_layout.setContentsMargins(0, 0, 0, 0)
        playlist_header_layout.setSpacing(0)

        playlist_label = QLabel("🎵 Playlists:")
        playlist_label.setStyleSheet("""
            QLabel {
                background-color: #2a2a2a;
                color: #ccc;
                padding: 4px 8px;
                font-size: 9pt;
                font-weight: bold;
            }
        """)

        add_playlist_btn = QPushButton("+")
        add_playlist_btn.setFixedSize(20, 20)
        add_playlist_btn.setStyleSheet("""
            QPushButton {
                background-color: grey;
                color: #ccc;
                border: none;
                font-size: 9pt;
                font-weight: bold;
            }
            QPushButton:hover {
                color: white;
                background-color: #3a3a3a;
                border-radius: 4px;
            }
        """)
        #add_playlist_btn.setToolTip("Add New Playlist")
        add_playlist_btn.clicked.connect(self.prompt_new_playlist)

        playlist_header_layout.addWidget(playlist_label)
        playlist_header_layout.addStretch()
        playlist_header_layout.addWidget(add_playlist_btn)

        self.playlist_list = QListWidget()
        self.playlist_list.setStyleSheet("QListWidget { font-size: 9pt; }")
        self.playlist_list.setFixedHeight(100)
        self.playlist_list.itemClicked.connect(self.handle_playlist_selected)
        self.playlist_list.setContextMenuPolicy(Qt.CustomContextMenu)
        self.playlist_list.customContextMenuRequested.connect(self.show_playlist_context_menu)


        playlist_layout.addWidget(playlist_header)
        playlist_layout.addWidget(self.playlist_list)

        # Add both panels to the info layout
        self.info_layout.addWidget(self.fav_panel)
        self.info_layout.addWidget(self.playlist_panel)
        self.info_layout.addWidget(self.fs_panel, stretch=1)

        # VLC player instance
        vlc_args = [
        '--no-xlib',
        '--no-video-title-show',
        '--no-snapshot-preview',
        '--quiet',
        '--verbose=0',
        '--avcodec-hw=none',
        
        ]

        self.vlc_instance = vlc.Instance(vlc_args)
        self.vlc_player = None

        
        # Display Panel
        self.display_panel = QFrame()
        self.display_panel.setFrameShape(QFrame.NoFrame)

        self.playback_slider = HandleSlider(self)
        self.play_timer = QTimer()
        self.play_timer.timeout.connect(self.playback_slider.update_smooth_position)
        self.play_timer.start(16)  # ~60fps

        self.display_layout = QVBoxLayout(self.display_panel)
        self.display_layout.setContentsMargins(0, 0, 0, 0)
        self.display_layout.setSpacing(0)      

        self.playback_slider.setRange(0, 1000)
        self.playback_slider.setVisible(False)
        self.playback_slider.sliderPressed.connect(self.pause_video_for_scrub)
        self.playback_slider.sliderReleased.connect(self.scrub_video)
    
        self.interp_timer = QTimer()
        self.interp_timer.setInterval(16)
        self.interp_timer.timeout.connect(self.playback_slider.update_smooth_position)
        self.interp_timer.start()

        self.poll_timer = QTimer()
        self.poll_timer.setInterval(50)
        self.poll_timer.timeout.connect(self.update_vlc_position)
        self.poll_timer.start()
        
        self.label = QLabel("Click to select folder", self.display_panel)
        self.label.setAlignment(Qt.AlignCenter)
        self.label.setStyleSheet("QLabel { background-color: black; color: #fff; font-size: 18px; }") #viewer color
        self.label.setScaledContents(False)
        self.label.setSizePolicy(QSizePolicy.Ignored, QSizePolicy.Ignored)

        self.display_layout.addWidget(self.label)
        
        # VLC player instance
        vlc_args = [
    '--no-xlib',
    '--no-video-title-show',
    '--no-snapshot-preview',
    '--quiet',
    '--verbose=0',
    '--avcodec-hw=none',
    
    ]

        self.vlc_instance = vlc.Instance(vlc_args)
        self.vlc_player = self.vlc_instance.media_player_new()

        # Video frame for VLC
        self.video_widget = QWidget()
        self.video_widget.setStyleSheet("background-color: black;")
        self.video_widget.setAttribute(Qt.WA_NativeWindow, True)
        #self.video_widget.hide()

        self.display_layout.addWidget(self.label)
        self.display_layout.addWidget(self.video_widget)
        

        # Playlist Panel
        self.playlist_panel = QFrame()
        
        self.playlist_panel.setMinimumWidth(300)
        self.playlist_panel.setMaximumWidth(300)

        self.playlist_layout = QVBoxLayout(self.playlist_panel)

        # Menu Bar for playlist panel
        self.controls_menu = QMenu("Options", self)
        menu_bar.addMenu(self.controls_menu)


        browse_source_action = self.controls_menu.addAction("Select Source Folder")
        browse_source_action.triggered.connect(self.browse_source)

        load_fav_action = self.controls_menu.addAction("Load Favorite Folder")
        load_fav_action.triggered.connect(self.load_favorite_folder)

        save_fav_action = self.controls_menu.addAction("Save Current Folder as Favorite")
        save_fav_action.triggered.connect(self.save_favorite_folder)

        select_playlist_dir_action = self.controls_menu.addAction("Select Playlist Directory")
        select_playlist_dir_action.triggered.connect(self.select_playlist_directory)

        select_dest_playlist_action = self.controls_menu.addAction("Select Destination Playlist")
        select_dest_playlist_action.triggered.connect(self.select_destination_playlist)

        scan_duplicates_action = self.controls_menu.addAction("Scan for Duplicates")
        scan_duplicates_action.triggered.connect(self.scan_for_duplicates)

        self.file_list = FileListWidget()
        self.file_list.setMinimumWidth(300)
        self.file_list.itemClicked.connect(self.file_list_clicked)
        self.file_list.currentRowChanged.connect(self.update_view_from_list)
        self.file_list.setSelectionMode(QListWidget.ExtendedSelection)
        self.file_list.setContextMenuPolicy(Qt.CustomContextMenu)
        self.file_list.customContextMenuRequested.connect(self.show_file_list_context_menu)
        self.file_list.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        self.file_list.setWordWrap(False)  # prevent ugly multi-line breaks
        self.file_list.setUniformItemSizes(True)  # speeds up rendering
        self.file_list.setStyleSheet("QListWidget::item { padding-right: 10px; }")
        self.file_list.setTextElideMode(Qt.ElideRight)

        self.search_bar = QLineEdit()
        self.search_bar.setPlaceholderText("Search files...")
        self.search_bar.setStyleSheet("""
            QLineEdit {
                padding: 4px 8px;
                background-color: #1e1e1e;
                color: #ccc;
                border: 1px solid #444;
                border-radius: 4px;
                font-size: 9pt;
            }
        """)
        self.search_bar.textChanged.connect(self.filter_file_list)

        
        self.sort_combo = QComboBox()
        self.sort_combo.addItems([
            "Name (Asc)", "Name (Desc)",
            "Date (Oldest)", "Date (Newest)",
            "Size (Largest)", "Size (Smallest)",
            "Random",            
        ])
        self.sort_combo.setCurrentIndex(3) #default date
        self.sort_combo.currentIndexChanged.connect(self.sort_files)

        # Create a dropdown menu for checkboxes and sort combo
        self.filter_menu = QMenu("Filters", self)

        self.img_checkbox = QCheckBox("Images")
        self.img_checkbox.setChecked(True)
        self.img_checkbox.stateChanged.connect(self.refresh_files)

        self.vid_checkbox = QCheckBox("Videos")
        self.vid_checkbox.setChecked(True)
        self.vid_checkbox.stateChanged.connect(self.refresh_files)

        self.gif_checkbox = QCheckBox("GIFs")
        self.gif_checkbox.setChecked(True)
        self.gif_checkbox.stateChanged.connect(self.refresh_files)

        # Add checkboxes and sort combo to filter menu
        img_action = self.filter_menu.addAction("Images")
        img_action.setCheckable(True)
        img_action.setChecked(True)

        vid_action = self.filter_menu.addAction("Videos")
        vid_action.setCheckable(True)
        vid_action.setChecked(True)

        gif_action = self.filter_menu.addAction("GIFs")
        gif_action.setCheckable(True)
        gif_action.setChecked(True)

        # Link menu actions to actual checkboxes
        img_action.toggled.connect(self.img_checkbox.setChecked)
        vid_action.toggled.connect(self.vid_checkbox.setChecked)
        gif_action.toggled.connect(self.gif_checkbox.setChecked)

        # Add the sort combo into the menu bar as well
        sort_action = QWidget()
        sort_layout = QVBoxLayout()
        sort_layout.addWidget(self.sort_combo)
        sort_action.setLayout(sort_layout)

        # Add filter menu and sort combo to menu bar
        self.controls_menu.addMenu(self.filter_menu)

        checkboxes_layout = QHBoxLayout()
        checkboxes_layout.addWidget(self.img_checkbox)
        checkboxes_layout.addWidget(self.vid_checkbox)
        checkboxes_layout.addWidget(self.gif_checkbox)

        #self.playlist_layout.setMenuBar(self.menu_bar)
        self.playlist_layout.addWidget(self.sort_combo)
        self.playlist_layout.addWidget(self.search_bar)
        self.playlist_layout.addWidget(self.file_list)


        # Main Splitter
        self.splitter = QSplitter(Qt.Horizontal)
        self.splitter.addWidget(self.info_panel)       # New panel
        self.splitter.addWidget(self.display_panel)
        self.splitter.addWidget(self.playlist_panel)
        self.splitter.setSizes([300, self.width() - 600, 300])

        self.main_layout.addWidget(self.splitter)

        
        self.movie = None
        self.label.mousePressEvent = self.initial_folder_select
        self.file_list.setFocus()
        self.current_playlist = None
        self.display_layout.addWidget(self.playback_slider)
        self.playback_slider.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)
        if self.vlc_player and self.vlc_player.get_media():
            self.target_pos = self.vlc_player.get_position()
        else:
            self.target_pos = 0.0
        app.setWindowIcon(QIcon(resource_path("rabbit_icon.ico")))
        self.load_config()
        self.load_all_files()
        self.load_preferences()
        
        self.load_collection()
        self.populate_favorite_list()
        self.populate_playlist_list()
        #self.sort_files()

###################################################################################################################
###################################################################################################################
###################################################################################################################

        pygame.init()
        pygame.joystick.init()
        #self.controller_timer = QTimer(self)
        #self.controller_timer.timeout.connect(self.check_controller_input)
        #self.controller_timer.start(100)

    def populate_favorite_list(self):
        self.fav_list.clear()

        if not os.path.exists(FAVORITES_FILE):
            return

        with open(FAVORITES_FILE, "r") as f:
            favorites = json.load(f)
            for name in sorted(favorites.keys()):
                self.fav_list.addItem(name)

    def populate_playlist_list(self):
        self.playlist_list.clear()

        if not os.path.exists(self.playlist_dir):
            os.makedirs(self.playlist_dir)

        for file in sorted(os.listdir(self.playlist_dir)):
            if file.endswith(".json"):
                name = file.replace(".json", "").replace("_", " ")
                self.playlist_list.addItem(name)

    def handle_favorite_selected(self, item):
        name = item.text()
        with open(FAVORITES_FILE, "r") as f:
            favorites = json.load(f)
        folder = favorites.get(name)
        if folder and os.path.exists(folder):
            self.source_dir = folder
            self.save_config()
            self.populate_file_explorer()
            self.load_files_recursive()
            self.refresh_files()
            self.update_window_title()
    
    def handle_playlist_selected(self, item):
        dprint('Playlist Selected')
        name = item.text()
        base = name.strip().lower().replace(" ", "_")
        dprint(name, base)
        self.load_playlist(base)

    def format_time(self, seconds):
        minutes = int(seconds) // 60
        secs = int(seconds) % 60
        return f"{minutes:02}:{secs:02}"

    def show_explorer_context_menu(self, position):
        item = self.fs_list.itemAt(position)
        if not item:
            return

        name = item.text()
        if name == "..":
            path = os.path.dirname(self.source_dir.rstrip(os.sep))
        else:
            path = os.path.join(self.source_dir, name)

        if not os.path.isdir(path):
            return

        menu = QMenu(self)
        set_source_action = QAction("Set as Source Folder", self)
        menu.addAction(set_source_action)

        action = menu.exec_(self.fs_list.viewport().mapToGlobal(position))
        if action == set_source_action:
            self.source_dir = path
            self.save_config()
            self.update_window_title()
            self.load_files_recursive()
            self.refresh_files()
            self.populate_file_explorer()

            self.fs_view.setRootIndex(self.fs_model.index(path))

    def scan_for_duplicates(self):
        if not self.all_files:
            QMessageBox.information(self, "No Files", "No files loaded.")
            return

        self.setEnabled(False)
        self.show_toast("Scanning for duplicates...")

        self.dup_thread = QThread(self)
        self.dup_worker = DuplicateScanWorker(self.all_files)
        self.dup_worker.moveToThread(self.dup_thread)

        self.dup_thread.started.connect(self.dup_worker.run)
        self.dup_worker.finished.connect(self.on_duplicates_found)
        self.dup_worker.finished.connect(self.dup_thread.quit)
        self.dup_worker.finished.connect(self.dup_worker.deleteLater)
        self.dup_thread.finished.connect(self.dup_thread.deleteLater)

        self._threads.append(self.dup_thread)
        self.dup_thread.start()

    def on_duplicates_found(self, duplicates):
        self.setEnabled(True)

        if duplicates:
            # Save playlist
            playlist_name = "duplicates"
            playlist_file = self.get_playlist_path(playlist_name)

            encoded_list = [encode_path(safe_relpath(path, APP_DIR)) for path in duplicates]

            with open(playlist_file, "w") as f:
                json.dump(encoded_list, f, indent=2)

            self.populate_playlist_list()
            self.load_playlist(playlist_name)

            self.show_toast(f"{len(duplicates)} duplicate files saved to playlist.")
        else:
            QMessageBox.information(self, "No Duplicates", "No duplicate files found.")

    def check_controller_input(self):
        if pygame.joystick.get_count() == 0:
            return

        if not self.files:
            return

        joystick = pygame.joystick.Joystick(0)
        joystick.init()
        pygame.event.pump()
        for i in range(joystick.get_numbuttons()):
            if joystick.get_button(i):
                dprint(f"Pressed: {i}")

        prefs = self.preferences
        keymap = {
            11: prefs["previous_file"],  # D-pad Up → W
            12: prefs["next_file"],      # D-pad Down → S
            13: prefs["seek_left"],      # D-pad Left → A
            14: prefs["seek_right"],     # D-pad Right → D
        }

        for button, qt_key in keymap.items():
            current = joystick.get_button(button)
            prev = self.last_button_states.get(button, 0)

            if current == 1 and prev == 0:
                event = QKeyEvent(QEvent.KeyPress, qt_key, Qt.NoModifier)
                self.keyPressEvent(event)

            self.last_button_states[button] = current

    def populate_file_explorer(self):
        self.fs_list.clear()

        if not self.source_dir or not os.path.exists(self.source_dir):
            return

        # ".." goes at the top if not at root
        parent_dir = os.path.dirname(self.source_dir.rstrip(os.sep))
        if parent_dir and parent_dir != self.source_dir:
            self.fs_list.addItem("..")

        try:
            entries = sorted(os.listdir(self.source_dir))
            for name in entries:
                full_path = os.path.join(self.source_dir, name)
                if os.path.isdir(full_path):
                    self.fs_list.addItem(name)
        except Exception as e:
            dprint(f"⚠️ Error reading directory: {e}")

    def handle_explorer_item_click(self, item):
        name = item.text()
        if name == "..":
            new_dir = os.path.dirname(self.source_dir.rstrip(os.sep))
        else:
            new_dir = os.path.join(self.source_dir, name)

        if os.path.isdir(new_dir):
            self.source_dir = new_dir
            self.populate_file_explorer()

    def save_favorite_folder(self):
        if not self.source_dir:
            QMessageBox.warning(self, "No Source", "No source folder to save.")
            return

        name, ok = QInputDialog.getText(self, "Save Favorite", "Enter a name for this folder:")
        if not ok or not name.strip():
            return

        try:
            if os.path.exists(FAVORITES_FILE):
                with open(FAVORITES_FILE, "r") as f:
                    favorites = json.load(f)
            else:
                favorites = {}

            favorites[name.strip()] = self.source_dir

            with open(FAVORITES_FILE, "w") as f:
                json.dump(favorites, f, indent=2)

            QMessageBox.information(self, "Saved", f"Saved as favorite: {name.strip()}")

        except Exception as e:
            QMessageBox.warning(self, "Error", f"Could not save favorite:\n{e}")

        self.populate_favorite_list()

    def show_favorite_context_menu(self, position):
        item = self.fav_list.itemAt(position)
        if not item:
            return

        label = item.text()

        try:
            with open(FAVORITES_FILE, "r") as f:
                favorites = json.load(f)
        except Exception:
            favorites = {}

        folder = favorites.get(label)
        if not folder:
            return

        menu = QMenu(self)
        show_action = menu.addAction("Show in Folder")
        remove_action = menu.addAction("Remove Favorite")

        action = menu.exec_(self.fav_list.viewport().mapToGlobal(position))

        if action == show_action:
            if os.path.exists(folder):
                try:
                    if sys.platform == "win32":
                        subprocess.run(["explorer", "/select,", os.path.normpath(folder)])
                except Exception as e:
                    QMessageBox.warning(self, "Error", f"Failed to open folder:\n{e}")
            else:
                QMessageBox.warning(self, "Not Found", "Folder does not exist.")

        elif action == remove_action:
            confirm = QMessageBox.question(
                self,
                "Remove Favorite",
                f"Are you sure you want to remove '{label}' from favorites?",
                QMessageBox.Yes | QMessageBox.No,
                QMessageBox.No
            )
            if confirm == QMessageBox.Yes:
                try:
                    favorites.pop(label, None)
                    with open(FAVORITES_FILE, "w") as f:
                        json.dump(favorites, f, indent=2)
                    self.populate_favorite_list()
                except Exception as e:
                    QMessageBox.warning(self, "Remove Failed", f"Could not update favorites:\n{e}")


    def load_favorite_folder(self):
        if not os.path.exists(FAVORITES_FILE):
            QMessageBox.information(self, "No Favorites", "No favorite folders saved yet.")
            return

        with open(FAVORITES_FILE, "r") as f:
            favorites = json.load(f)

        if not favorites:
            QMessageBox.information(self, "No Favorites", "Favorites list is empty.")
            return

        names = list(favorites.keys())
        selected, ok = QInputDialog.getItem(self, "Load Favorite", "Select a favorite folder:", names, 0, False)

        if ok and selected:
            folder = favorites[selected]
            if os.path.exists(folder):
                self.source_dir = folder
                self.populate_file_explorer()
                self.load_files_recursive()
                self.update_window_title()
                self.refresh_files()
                self.save_config()
                if self.files:
                    self.set_current_file(0)
                else:
                    self.label.setText("No files found in this folder.")
                    self.label.setPixmap(QPixmap())
            else:
                QMessageBox.warning(self, "Not Found", f"The folder '{folder}' no longer exists.")

    def update_playback_slider(self):
        if self.vlc_player.is_playing() and not self.playback_slider.drag_mode:
            current_time_ms = self.vlc_player.get_time()
            duration_ms = self.vlc_player.get_length()

            if duration_ms <= 0:
                return
            if not self.vlc_player.get_media():
                return


            current_time_sec = current_time_ms / 1000
            duration_sec = duration_ms / 1000

            if self.clip_mode_active:
                start_handle = self.playback_slider.start_handle or 0
                end_handle = self.playback_slider.end_handle or 1

                self.clip_start_sec = start_handle * duration_sec
                self.clip_end_sec = end_handle * duration_sec

                if current_time_sec >= self.clip_end_sec:
                    dprint(f"🔁 Looping: {current_time_sec:.2f}s → {self.clip_start_sec:.2f}s")
                    self.vlc_player.set_time(int(self.clip_start_sec * 1000))
                    self.playback_slider.current_pos = start_handle  # 🔴 jump red dot
                    self.playback_slider.update()
                    return

            # Normal red dot update via interpolation
            pos = self.vlc_player.get_time() / self.vlc_player.get_length()
            self.playback_slider.target_pos = pos

    def open_preferences(self):
        dialog = PreferencesDialog(self)
        if dialog.exec_() == QDialog.Accepted:
            selected_sort = dialog.sort_combo.currentText()
            dprint(f"✅ Preferences saved. Default sort: {selected_sort}")
            # You could apply this sort mode or store in config here


    def update_vlc_position(self):
        try:
            if not self.vlc_player or not self.vlc_player.get_media():
                return

            if self.vlc_player.is_playing() and not self.playback_slider.drag_mode:
                self.playback_slider.target_pos = self.vlc_player.get_position()
                self.update_playback_slider()

            current_ms = self.vlc_player.get_time()
            if current_ms < 0:
                return

            current_sec = current_ms / 1000.0
            self.current_time_sec = current_sec

            if hasattr(self, 'time_label'):
                self.time_label.setText(self.format_time(current_sec))

            # ✅ Debug playback state
            if not hasattr(self, '_last_debug_time') or time.time() - self._last_debug_time > 1:
                #print(f"🕒 VLC time: {self.format_time(current_sec)} | Position: {self.vlc_player.get_position():.3f}")
                self._last_debug_time = time.time()

        except Exception as e:
            dprint("⚠️ update_vlc_position crash:", e)


    def print_current_file_info(self):
        if not self.files or not (0 <= self.current_index < len(self.files)):
            dprint("⚠️ No file selected.")
            return

        path = self.files[self.current_index]
        name = os.path.basename(path)

        time_str = ""
        if hasattr(self, "vlc_player") and self.vlc_player:
            try:
                time_ms = self.vlc_player.get_time()
                dur_ms = self.vlc_player.get_length()
                if time_ms >= 0 and dur_ms > 0:
                    cur = self.format_time(time_ms / 1000)
                    dur = self.format_time(dur_ms / 1000)
                    time_str = f" | {cur} / {dur}"
            except:
                pass

        dprint(f"[{self.current_index}] {name} — {path}{time_str}")





    def pause_video_for_scrub(self):
        if self.vlc_player.is_playing():
            self.vlc_player.pause()

    def scrub_video(self):
        try:
            if not self.vlc_player or not self.vlc_player.get_media():
                return

            duration = self.vlc_player.get_length()
            if duration > 0:
                new_time = int((self.playback_slider.value() / 1000) * duration)
                self.vlc_player.set_time(new_time)

                state = self.vlc_player.get_state()
                if state in [vlc.State.Stopped, vlc.State.Paused]:
                    self.vlc_player.play()
                    dprint("▶️ VLC .play() called")

        except Exception as e:
            dprint("⚠️ scrub_video crash:", e)



    def toggle_fullscreen(self):
        if self.fullscreen:
            self.setWindowFlags(self.windowFlags() & ~Qt.FramelessWindowHint)
            self.showMaximized()
            self.playlist_panel.show()
            self.info_panel.show()
            self.menuBar().show()  # 👈 Show menu bar again
            self.fullscreen = False
        else:
            self.setWindowFlags(self.windowFlags() | Qt.FramelessWindowHint)
            self.showFullScreen()
            self.playlist_panel.hide()
            self.info_panel.hide()
            self.menuBar().hide()  # 👈 Hide menu bar
            self.fullscreen = True

    def play_random_folder(self):
        if not self.source_dir or not os.path.isdir(self.source_dir):
            QMessageBox.warning(self, "No Source", "Source directory is not set.")
            return

        all_folders = []
        for root, dirs, _ in os.walk(self.source_dir):
            for d in dirs:
                folder_path = os.path.join(root, d)
                all_folders.append(folder_path)

        if not all_folders:
            QMessageBox.information(self, "No Folders", "No subfolders found in the source directory.")
            return

        selected_folder = random.choice(all_folders)

        collected_files = []
        for root, _, files in os.walk(selected_folder):
            for file in files:
                ext = os.path.splitext(file)[1].lower()
                if ext in IMAGE_EXTENSIONS + VIDEO_EXTENSIONS + GIF_EXTENSIONS:
                    collected_files.append(os.path.join(root, file))

        if not collected_files:
            QMessageBox.information(self, "No Files", "No supported files in selected folder.")
            return

        self.files = collected_files
        self.current_index = 0
        self.populate_file_list()
        self.set_current_file(0)
        self.file_list.setCurrentRow(0)
        self.show_toast(f"Random folder: {os.path.basename(selected_folder)}")

    def remove_selected_files_from_playlist(self, selected_files):
        if not self.current_playlist:
            return

        playlist_file = self.get_playlist_path(self.current_playlist)
        dprint(playlist_file)
        if not os.path.exists(playlist_file):
            QMessageBox.warning(self, "Error", "Playlist file not found.")
            return

        confirm = QMessageBox.question(
            self,
            "Remove from Playlist",
            f"Are you sure you want to remove {len(selected_files)} file(s) from '{self.current_playlist}'?",
            QMessageBox.Yes | QMessageBox.No,
            QMessageBox.No
        )

        if confirm != QMessageBox.Yes:
            return

        with open(playlist_file, "r") as f:
            playlist = json.load(f)

        removed = 0
        for abs_path in selected_files:
            rel_path = abs_path  # ✅ store full absolute path

            encoded = encode_path(rel_path)
            if encoded in playlist:
                playlist.remove(encoded)
                removed += 1

        with open(playlist_file, "w") as f:
            json.dump(playlist, f, indent=2)

        
        QMessageBox.information(self, "Removed", f"{removed} file(s) removed from playlist.")
        self.load_playlist(self.current_playlist)

    def add_selected_files_to_playlist(self, selected_files):
        if not selected_files:
            return

        if not hasattr(self, 'dest_playlist') or not self.dest_playlist:
            if not os.path.isdir(self.playlist_dir):
                if os.path.exists(self.playlist_dir):
                    QMessageBox.warning(self, "Error", "'playlists' exists but is not a folder.")
                    return
                os.makedirs(self.playlist_dir)

            playlists = [
                f.replace(".json", "").replace("_", " ")
                for f in os.listdir(self.playlist_dir)
                if f.endswith(".json")
            ]

            if not playlists:
                QMessageBox.information(self, "No Playlists", "You don't have any playlists to add to.")
                return

            selected, ok = QInputDialog.getItem(
                self, "Select Playlist", "Add selected files to which playlist:", playlists, 0, False
            )
            if not ok or not selected:
                return

            self.dest_playlist = self.normalize_playlist_name(selected)

        playlist_file = self.get_playlist_path(self.dest_playlist)

        # Load or initialize the playlist
        if os.path.exists(playlist_file):
            with open(playlist_file, 'r') as f:
                playlist = json.load(f)
        else:
            playlist = []

        added = 0
        for abs_path in selected_files:
            encoded = encode_path(os.path.abspath(abs_path))  # ✅ use absolute path
            if encoded not in playlist:
                playlist.append(encoded)
                added += 1

        with open(playlist_file, 'w') as f:
            json.dump(playlist, f, indent=2)

        QMessageBox.information(self, "Files Added", f"{added} file(s) added to '{self.dest_playlist}' playlist.")


    def show_file_list_context_menu(self, position):
        selected_items = self.file_list.selectedItems()
        if not selected_items:
            return

        menu = QMenu()
        add_to_playlist_action = QAction("Add Selected to Playlist", self)
        show_in_folder_action = QAction("Show File Location", self)
        remove_from_playlist_action = None

        menu.addAction(add_to_playlist_action)
        menu.addAction(show_in_folder_action)

        if hasattr(self, 'current_playlist') and self.current_playlist:
            remove_from_playlist_action = QAction("Remove Selected from Playlist", self)
            menu.addAction(remove_from_playlist_action)

        action = menu.exec_(self.file_list.mapToGlobal(position))
        selected_files = [self.files[self.file_list.row(item)] for item in selected_items]

        if action == add_to_playlist_action:
            self.add_selected_files_to_playlist(selected_files)

        elif action == show_in_folder_action and selected_files:
            for path in selected_files:
                self.reveal_in_explorer(path)

        elif remove_from_playlist_action and action == remove_from_playlist_action:
            self.remove_selected_files_from_playlist(selected_files)

    def reveal_in_explorer(self, path):
        if os.path.exists(path):
            if sys.platform == "win32":
                subprocess.run(["explorer", "/select,", os.path.normpath(path)])

    def get_playlist_path(self, name_or_label):
        base = self.normalize_playlist_name(name_or_label)
        return os.path.join(self.playlist_dir, f"{base}.json")




    def normalize_playlist_name(self, name):
        return name.strip().lower().replace(" ", "_")

    def load_preferences(self):
        default_prefs = {
            "add_file_to_playlist": "Key_Q",
            "next_file": "Key_S",
            "previous_file": "Key_W",
            "seek_left": "Key_A",
            "seek_right": "Key_D",
            "move_to_folder": "Key_E",
            "play_random_folder": "Key_1",
            "toggle_fullscreen": "Key_F",
            "rotate_left": "Key_Z",
            "rotate_right": "Key_X",
            "randomize_list": "Key_2",
        }

        try:
            with open(PREF_FILE, "r") as f:
                raw = json.load(f)
        except (FileNotFoundError, json.JSONDecodeError):
            raw = default_prefs
            with open(PREF_FILE, "w") as f:
                json.dump(raw, f, indent=2)

        self.preferences = {
            action: getattr(Qt, keyname, None)
            for action, keyname in raw.items()
        }

    def filter_file_list(self, text):
        text = text.lower()
        self.file_list.clear()

        for file in self.files:
            name = os.path.basename(file)
            if text in name.lower():
                self.file_list.addItem(name)

        self.file_list.setCurrentRow(0)


    def show_playlist_context_menu(self, position):
        index = self.playlist_dropdown.view().indexAt(position)
        if not index.isValid():
            return

        label = self.playlist_dropdown.itemText(index.row())

        if label in ["All Files", "+ New Playlist"]:
            return

        menu = QMenu()
        show_action = QAction("Show in Folder", self)
        delete_action = QAction("Delete Playlist", self)

        menu.addAction(show_action)
        menu.addAction(delete_action)

        action = menu.exec_(self.playlist_dropdown.mapToGlobal(position))

        playlist_filename = self.dropdown_label_to_filename.get(label)
        if not playlist_filename:
            return

        playlist_path = self.get_playlist_path(playlist_filename)

        if action == delete_action:
            confirm = QMessageBox.question(
                self,
                "Delete Playlist",
                f"Are you sure you want to delete the playlist '{label}'?",
                QMessageBox.Yes | QMessageBox.No,
                QMessageBox.No
            )

            if confirm == QMessageBox.Yes:
                try:
                    os.remove(playlist_path)
                    self.populate_playlist_list()
                    self.load_all_files()
                except Exception as e:
                    QMessageBox.warning(self, "Error", f"Failed to delete playlist:\n{str(e)}")

        elif action == show_action:
            if os.path.exists(playlist_path):
                try:
                    if sys.platform == "win32":
                        subprocess.run(["explorer", "/select,", os.path.normpath(playlist_path)])
                except Exception as e:
                    QMessageBox.warning(self, "Error", f"Failed to open folder:\n{str(e)}")
            else:
                QMessageBox.warning(self, "Not Found", "Playlist file does not exist.")

    def load_all_files(self):
        if self.source_dir and os.path.exists(self.source_dir):
            self.populate_file_explorer()
            self.load_files_recursive()
            self.update_window_title()
            self.populate_file_list()
            if self.files:
                self.current_index = 0
                self.set_current_file(0)

    def get_video_duration(self, full_path):
        try:
            media = self.vlc_instance.media_new(full_path)
            media.parse_with_options(vlc.MediaParseFlag.local, timeout=2 * 1000)  # wait max 2s
            duration_ms = media.get_duration()
            if duration_ms > 0:
                return duration_ms / 1000.0
        except Exception as e:
            dprint(f"❌ Failed to preload duration: {e}")
        return 0.0

    def load_collection(self):
        os.makedirs(ASSETS_DIR, exist_ok=True)

        if os.path.exists(COLLECTION_PATH):
            try:
                with open(COLLECTION_PATH, "r") as f:
                    self.collection = json.load(f)
                    dprint("📂 collection.json loaded")
            except Exception as e:
                dprint(f"❌ Failed to load collection: {e}")
                self.collection = {"files": {}}
        else:
            dprint("📁 Creating new collection.json")
            self.collection = {"files": {}}
            self.save_collection()


    def save_collection(self):
        try:
            with open(COLLECTION_PATH, "w") as f:
                json.dump(self.collection, f, indent=2)
            dprint("💾 collection.json saved")
        except Exception as e:
            dprint(f"❌ Failed to save collection: {e}")


    def register_file(self, path):
        rel = safe_relpath(path, APP_DIR)
        if rel in self.collection["files"]:
            dprint ("File is in collection: Skipping registry")
            return  
        dprint(f"📥 Registering new file")
        self.collection["files"][rel] = {
            "duration": None,
            "imported": False,
            "tags": []
        }
        self.save_collection()
            
    def import_file_metadata(self, path):
        rel = safe_relpath(path, APP_DIR)

        # Ensure the file is in the registry
        if rel not in self.collection["files"]:
            self.register_file(path)

        _, ext = os.path.splitext(path.lower())
        if ext not in VIDEO_EXTENSIONS:
            dprint(f"⏭️ Skipping metadata import (not a video): {rel}")
            return

        duration = self.get_video_duration(path)
        self.collection["files"][rel]["duration"] = duration
        self.collection["files"][rel]["imported"] = True
        
        self.refresh_file_list_item(path)  # 👈 update the UI item here



    def show_playlist_context_menu(self, position):
        item = self.playlist_list.itemAt(position)
        if not item:
            return

        label = item.text()
        base_name = self.normalize_playlist_name(label)
        playlist_path = self.get_playlist_path(base_name)

        menu = QMenu(self)
        rename_action = menu.addAction("Rename Playlist")
        delete_action = menu.addAction("Delete Playlist")

        action = menu.exec_(self.playlist_list.viewport().mapToGlobal(position))

        if action == rename_action:
            new_name, ok = QInputDialog.getText(self, "Rename Playlist", "Enter new name:", text=label)
            if ok and new_name.strip():
                new_base = self.normalize_playlist_name(new_name)
                new_path = self.get_playlist_path(new_base)

                if os.path.exists(new_path):
                    QMessageBox.warning(self, "Error", "A playlist with that name already exists.")
                    return

                try:
                    os.rename(playlist_path, new_path)
                    self.populate_playlist_list()
                except Exception as e:
                    QMessageBox.warning(self, "Rename Failed", f"Could not rename:\n{e}")

        elif action == delete_action:
            confirm = QMessageBox.question(
                self,
                "Delete Playlist",
                f"Are you sure you want to delete '{label}'?",
                QMessageBox.Yes | QMessageBox.No,
                QMessageBox.No
            )
            if confirm == QMessageBox.Yes:
                try:
                    os.remove(playlist_path)
                    self.populate_playlist_list()
                    if self.current_playlist == base_name:
                        self.files = []
                        self.populate_file_list()
                        self.label.setText("Playlist deleted.")
                except Exception as e:
                    QMessageBox.warning(self, "Delete Failed", f"Could not delete:\n{e}")


    def prompt_new_playlist(self):
        name, ok = QInputDialog.getText(self, "New Playlist", "Enter playlist name:")
        if ok and name:
            base = self.normalize_playlist_name(name)
            playlist_path = self.get_playlist_path(base)

            if not os.path.exists(playlist_path):
                with open(playlist_path, 'w') as f:
                    json.dump([], f, indent=2)

            # ✅ Refresh the sidebar playlist list
            self.populate_playlist_list()

            # ✅ Auto-select and highlight the new playlist
            for i in range(self.playlist_list.count()):
                item = self.playlist_list.item(i)
                if item.text().lower() == name.strip().lower():
                    self.playlist_list.setCurrentRow(i)
                    break

            # ✅ Optionally load it immediately (comment out if not desired)
            self.load_playlist(base)

            
            

    def load_playlist(self, name):
        playlist_path = self.get_playlist_path(name)

        if not os.path.exists(playlist_path):
            QMessageBox.warning(self, "Playlist Not Found", f"Playlist file not found:\n{playlist_path}")
            return

        with open(playlist_path, "r") as f:
            encoded_paths = json.load(f)

        self.files = []
        for encoded in encoded_paths:
            try:
                decoded = decode_path(encoded)

                if not os.path.isabs(decoded):
                    decoded = os.path.abspath(os.path.join(APP_DIR, decoded))

                if os.path.exists(decoded):
                    self.files.append(decoded)
            except Exception:
                continue

        self.current_playlist = name
        self.current_index = 0

        if not self.files:
            self.label.setText("No valid files in this playlist.")
            self.label.setPixmap(QPixmap())
            self.video_widget.hide()
            self.file_list.clear()
            return

        self.populate_file_list()
        self.set_current_file(0)
        self.show_file()
        self.file_list.setCurrentRow(0)



    def handle_explorer_double_click(self, index):
        path = self.fs_model.filePath(index)

        if os.path.basename(path) == "..":
            parent = os.path.dirname(self.source_dir.rstrip(os.sep))
            if os.path.exists(parent):
                self.source_dir = parent
                self.fs_view.setRootIndex(self.fs_model.index(parent))
                self.populate_file_explorer()
                self.load_files_recursive()
                self.update_window_title()
                self.refresh_files()
            return

        if os.path.isdir(path):
            self.source_dir = path
            self.fs_view.setRootIndex(self.fs_model.index(path))
            self.populate_file_explorer()
            self.load_files_recursive()
            self.update_window_title()
            self.refresh_files()
        elif os.path.isfile(path):
            self.files = [path]
            self.current_index = 0
            self.populate_file_list()
            self.set_current_file(0)




    def select_destination_playlist(self):
        if not os.path.isdir(self.playlist_dir):
            if os.path.exists(self.playlist_dir):
                QMessageBox.warning(self, "Error", "'playlists' exists but is not a folder.")
                return
            os.makedirs(self.playlist_dir)

        playlists = [
            f.replace(".json", "").replace("_", " ")
            for f in os.listdir(self.playlist_dir)
            if f.endswith(".json")
        ]

        if not playlists:
            QMessageBox.information(self, "No Playlists", "You don't have any playlists to select.")
            return

        selected, ok = QInputDialog.getItem(self, "Select Destination Playlist", "Choose a playlist:", playlists, 0, False)

        if ok and selected:
            self.dest_playlist = self.normalize_playlist_name(selected)
            QMessageBox.information(self, "Destination Set", f"Selected destination: {selected}")

    def keyPressEvent(self, event):
        self.file_list.setFocus()
        if not self.files:
            super().keyPressEvent(event)
            return

        key = event.key()
        prefs = self.preferences
        full_path = safe_relpath(self.files[self.current_index], APP_DIR)
        _, ext = os.path.splitext(full_path.lower())

        if key == prefs["previous_file"]:
            self.current_index = (self.current_index - 1) % len(self.files)
            self.file_list.setCurrentRow(self.current_index)
            self.show_file()
        
        elif key == self.preferences.get("toggle_fullscreen", Qt.Key_F):
            self.toggle_fullscreen()

        elif event.key() == Qt.Key_Escape:
            if self.fullscreen:
                self.toggle_fullscreen()
            else:
                self.close()

        elif key == prefs["next_file"]:
            self.current_index = (self.current_index + 1) % len(self.files)
            self.file_list.setCurrentRow(self.current_index)
            self.show_file()

        elif key == prefs["seek_left"] and ext in VIDEO_EXTENSIONS:
            current_time = self.vlc_player.get_time()
            duration = self.vlc_player.get_length()
            new_time = current_time - 5000
            if new_time < 0:
                new_time = duration - 1000  
            self.vlc_player.set_time(new_time)

        elif key == prefs["seek_right"] and ext in VIDEO_EXTENSIONS:
            current_time = self.vlc_player.get_time()
            duration = self.vlc_player.get_length()
            new_time = current_time + 5000
            if new_time > duration - 500:
                new_time = 0  # Wrap to start
            self.vlc_player.set_time(new_time)

        elif key == prefs["add_file_to_playlist"]:
            self.add_file_to_playlist()

        elif key == self.preferences.get("move_to_folder", Qt.Key_Period):
            self.move_current_file_to_folder()

        elif key == self.preferences.get("play_random_folder"):
            self.play_random_folder()

        elif event.key() == Qt.Key_2:
            self.randomize_files()

        elif event.key() == Qt.Key_Space:
            self.playback_slider.setFocus()  # 👈 shift focus to the slider
            if self.vlc_player.is_playing():
                self.vlc_player.pause()
            else:
                self.vlc_player.play()
                dprint("▶️ VLC .play() called")

            return  # 👈 prevent spacebar from triggering other widgets (like list scrolling)f


        elif key == Qt.Key_Z:
            self.rotation_angle = (self.rotation_angle - 90) % 360
            self.apply_rotation()

        elif key == Qt.Key_X:
            self.rotation_angle = (self.rotation_angle + 90) % 360
            self.apply_rotation()
        
        elif key == Qt.Key_Delete:
            self.delete_current_file()
            return
        
        elif key == Qt.Key_C:
            if not self.files or os.path.splitext(self.files[self.current_index])[1].lower() not in VIDEO_EXTENSIONS:
                self.show_toast("Not a video file.")
                return

            duration_sec = self.video_duration

            if self.clip_mode_active:
                # 🔄 Cancel clip mode
                self.clip_mode_active = False
                self.clip_start_sec = None
                self.clip_end_sec = None
                self.clip_zoom_start = 0
                self.clip_zoom_end = duration_sec
                self.playback_slider.start_handle = None
                self.playback_slider.end_handle = None
                self.playback_slider.update()
                self.show_toast("❌ Clip mode canceled")
            else:
                # 🎬 Activate clip mode
                current_sec = self.vlc_player.get_time() / 1000
                self.clip_start_sec = max(0, current_sec)
                self.clip_end_sec = min(duration_sec, self.clip_start_sec + 5.0)

                # 🔍 Zoom in around the clip with 10s padding
                padding = 10
                self.clip_zoom_start = max(0, self.clip_start_sec - padding)
                self.clip_zoom_end = min(duration_sec, self.clip_end_sec + padding)

                self.clip_mode_active = True

                # Slider handles (still use full duration to normalize)
                self.playback_slider.start_handle = self.clip_start_sec / duration_sec
                self.playback_slider.end_handle = self.clip_end_sec / duration_sec
                self.playback_slider.update()

                self.show_toast(f"🎬 Clip mode: {int(self.clip_start_sec)}s to {int(self.clip_end_sec)}s")



        elif key in (Qt.Key_Enter, Qt.Key_Return) and self.clip_mode_active:
            self.export_current_clip()
            self.clip_mode_active = False
            self.clip_start_sec = None
            self.clip_end_sec = None
            self.playback_slider.start_handle = None
            self.playback_slider.end_handle = None
            self.playback_slider.update()
            self.show_toast("Clip saved!")


    def export_current_clip(self):
        import ffmpeg

        input_path = self.files[self.current_index]
        base, ext = os.path.splitext(os.path.basename(input_path))
        output_dir = os.path.dirname(input_path)

        # Create unique output filename
        counter = 1
        output_path = os.path.join(output_dir, f"{base}_clip{ext}")
        while os.path.exists(output_path):
            output_path = os.path.join(output_dir, f"{base}_clip{counter}{ext}")
            counter += 1

        try:
            # Run ffmpeg to export the clip
            ffmpeg.input(input_path, ss=self.clip_start_sec, to=self.clip_end_sec) \
                .output(output_path, vcodec='libx264', acodec='aac', preset='medium') \
                .run(overwrite_output=True)

            dprint(f"✅ Clip saved: {output_path}")
            self.show_toast(f"Clip saved as: {os.path.basename(output_path)}")

            # Insert new clip into file list
            if os.path.exists(output_path):
                insert_index = self.current_index + 1
                self.files.insert(insert_index, output_path)
                item = QListWidgetItem(os.path.basename(output_path))
                self.file_list.insertItem(insert_index, item)

                # Auto-add to 'clips' playlist
                playlist_name = "clips"
                playlist_file = self.get_playlist_path(playlist_name)

                if os.path.exists(playlist_file):
                    with open(playlist_file, "r") as f:
                        playlist = json.load(f)
                else:
                    playlist = []

                rel_path = safe_relpath(output_path, APP_DIR)
                encoded = encode_path(rel_path)

                if encoded not in playlist:
                    playlist.append(encoded)
                    with open(playlist_file, "w") as f:
                        json.dump(playlist, f, indent=2)
                    dprint(f"✅ Added to playlist: {playlist_name}")

        except ffmpeg.Error as e:
            dprint("❌ ffmpeg error:", e)
            self.show_toast("Error saving clip")


    def move_current_file_to_folder(self):
        if not self.move_target_folder:
            folder = QFileDialog.getExistingDirectory(self, "Select Move-To Folder")
            if not folder:
                return
            self.move_target_folder = folder

        source_path = self.files[self.current_index]
        filename = os.path.basename(source_path)
        dest_path = os.path.join(self.move_target_folder, filename)

        self.label.clear()
        self.label.setPixmap(QPixmap())
        self.label.setText("")
        self.video_widget.hide()

        if self.vlc_player:
            self.vlc_player.stop()
            QApplication.processEvents()
            #time.sleep(0.05)
            self.vlc_player.set_media(None)
            del self.vlc_player
            self.vlc_player = self.vlc_instance.media_player_new()
            self.vlc_player.set_hwnd(int(self.video_widget.winId()))


        if self.movie:
            self.movie.stop()
            self.movie = None

        QApplication.processEvents()
        #time.sleep(0.1)

        try:
            shutil.move(source_path, dest_path)
            self.show_toast(f"Moved to: {self.move_target_folder}")
            del self.files[self.current_index]

            if self.files:
                self.current_index %= len(self.files)
                self.populate_file_list()
                self.show_file()
                self.file_list.setCurrentRow(self.current_index)
            else:
                self.label.setText("No files remaining.")
                self.file_list.clear()
        except Exception as e:
            QMessageBox.warning(self, "Move Failed", f"Could not move file:\n{str(e)}")

    def apply_rotation(self):
        if not self.files:
            return

        full_path = self.files[self.current_index]
        _, ext = os.path.splitext(full_path.lower())

        if ext in IMAGE_EXTENSIONS:
            pixmap = QPixmap(full_path)
            if pixmap.isNull():
                return
            transform = QTransform().rotate(self.rotation_angle)
            rotated = pixmap.transformed(transform, Qt.SmoothTransformation)
            scaled = rotated.scaled(
                self.display_panel.width(),
                self.display_panel.height() - 50,
                Qt.KeepAspectRatio,
                Qt.SmoothTransformation
            )
            self.label.setPixmap(scaled)

    def select_playlist_directory(self):
        directory = QFileDialog.getExistingDirectory(self, "Select Playlist Directory")
        if directory:
            self.playlist_dir = directory
            self.save_config()
            QMessageBox.information(self, "Playlist Directory Set", f"Now using:\n{directory}")

    def initial_folder_select(self, event):
        if not self.source_dir:
            self.browse_source()

    def browse_source(self):
        source = QFileDialog.getExistingDirectory(self, "Select Source Directory")
        if source:
            self.source_dir = source
            self.save_config()
            self.populate_file_explorer()  # 👈 Add this
            self.load_files_recursive()
            self.update_window_title()
            if not self.files:
                self.label.setText("No files found in the source directory.")
            else:
                self.set_current_file(0)
            
    def save_config(self):
        config = {
        'source_dir': self.source_dir,
        'dest_dir': self.dest_dir,
        'playlist_dir': self.playlist_dir
        }
        with open(CONFIG_FILE, 'w') as f:
            json.dump(config, f)

    def load_config(self):
        if os.path.exists(CONFIG_FILE):
            with open(CONFIG_FILE, 'r') as f:
                config = json.load(f)
                self.source_dir = config.get('source_dir', '')
                self.dest_dir = config.get('dest_dir', '')

                if self.source_dir and os.path.exists(self.source_dir):
                    self.populate_file_explorer()
                    self.load_files_recursive()
                    self.update_window_title()
                    if self.files:
                        self.set_current_file(0)

    def load_files_recursive(self):
        all_files = []
        for root, _, files in os.walk(self.source_dir):
            for name in files:
                full_path = os.path.join(root, name)
                all_files.append(full_path)
        self.all_files = all_files
        self.filter_files()
        


        def walk_limited(path, max_depth):
            base_depth = path.rstrip(os.sep).count(os.sep)
            for root, _, files in os.walk(path):
                current_depth = root.rstrip(os.sep).count(os.sep)
                if current_depth - base_depth > max_depth:
                    continue
                for name in files:
                    yield os.path.join(root, name)


        self.all_files = list(walk_limited(self.source_dir, max_depth=2))

        self.filter_files()
        self.populate_file_list()
        self.setEnabled(True)
        if self.files:
            self.current_index = 0
            self.set_current_file(0)
        if hasattr(self, "search_bar"):
            self.search_bar.clear()

    def on_files_loaded(self, file_list):
        self.all_files = file_list
        self.filter_files()
        self.populate_file_list()
        self.setEnabled(True)

        if self.files:
            self.current_index = 0
            self.set_current_file(0)

        self.loader_thread = None 

    def closeEvent(self, event):
        for thread in self._threads:
            if thread.isRunning():
                thread.quit()
                thread.wait()
        event.accept()

    def filter_files(self):
        active_exts = []
        if self.img_checkbox.isChecked():
            active_exts += IMAGE_EXTENSIONS
        if self.vid_checkbox.isChecked():
            active_exts += VIDEO_EXTENSIONS
        if self.gif_checkbox.isChecked():
            active_exts += GIF_EXTENSIONS

        self.files = [f for f in self.all_files if os.path.splitext(f)[1].lower() in active_exts]
        self.current_index = 0
        
    def refresh_files(self):
        self.filter_files()
        self.populate_file_list()
        if not self.files:
            self.label.setText("No files found with the selected filters.")
            self.label.setPixmap(QPixmap())
            self.video_widget.hide()
        else:
            self.set_current_file(0)
            self.file_list.setFocus()


    def on_file_list_ready(self, items):
        dprint("🎯 on_file_list_ready() triggered")
        for item in items:
            self.file_list.addItem(item)
        self.file_list.setCurrentRow(self.current_index)
        self.save_collection()  # optional: save once after batch registration
        self.set_current_file(0)

    def populate_file_list(self):
        self.file_list.clear()

        for path in self.files:
            name = os.path.basename(path)
            rel_path = safe_relpath(path, APP_DIR)
            

            # Register if missing
            #if rel_path not in self.collection["files"]:
             #   self.register_file(path)
                #self.save_collection()
                

            # Get metadata
            meta = self.collection["files"].get(rel_path, {})
            imported = meta.get("imported", False)
            tags = meta.get("tags", [])
            exists = os.path.exists(path)

            # # Label
            prefix = ""
            # if not exists:
            #     prefix = "⚠️ "
            # elif not imported:
            #     prefix = "🕓 "
            # elif "favorite" in tags:
            #     prefix = "⭐ "

            label = f"{prefix}{name}"
            item = QListWidgetItem(label)
            item.setData(Qt.UserRole, rel_path)
                
            # Style
            if  exists:
                item.setForeground(QBrush(QColor("#888")))
            elif imported:
                item.setForeground(QBrush(QColor("#666")))
            elif "favorite" in tags:
                item.setForeground(QBrush(QColor("#ffd700")))

            self.file_list.addItem(item)


        # ✅ Make sure first file is loaded
        if self.files:
            self.current_index = 0
            self.set_current_file(0)

    def refresh_file_list_item(self, path):
        rel_path = safe_relpath(path, APP_DIR)
        name = os.path.basename(path)

        # Find matching item in the list
        for i in range(self.file_list.count()):
            item = self.file_list.item(i)
            if item.data(Qt.UserRole) == rel_path:
                meta = self.collection["files"].get(rel_path, {})
                imported = meta.get("imported", False)
                tags = meta.get("tags", [])
                exists = os.path.exists(path)

                # Determine label prefix
                prefix = ""
                if not exists:
                    prefix = "⚠️ "
                elif not imported:
                    prefix = "🕓 "
                elif "favorite" in tags:
                    prefix = "⭐ "

                # Update label and style
                item.setText(f"{prefix}{name}")

                if not exists:
                    item.setForeground(QBrush(QColor("#888")))
                elif not imported:
                    item.setForeground(QBrush(QColor("#666")))
                elif "favorite" in tags:
                    item.setForeground(QBrush(QColor("#ffd700")))
                else:
                    item.setForeground(QBrush(QColor("#fff")))

                break


    def update_window_title(self):
        title = f"EDGR - Enhanced Directory Gooning Register"
        self.source_label.setText(f"📁 Source:\n{self.source_dir or 'Not Set'}")
        self.dest_label.setText(f"📦 Destination:\n{self.dest_dir or 'Not Set'}")
        self.setWindowTitle(title)

    def file_list_clicked(self, item):
        index = self.file_list.row(item)
        self.current_index = index
        self.show_file()

    def sort_files(self):
        mode = self.sort_combo.currentText()
        self.current_sort_mode = mode  #  Track sort mode

        if mode == "Name (Asc)":
            self.files.sort()
        elif mode == "Name (Desc)":
            self.files.sort(reverse=True)
        elif mode == "Date (Oldest)":
            self.files.sort(key=os.path.getmtime)
        elif mode == "Date (Newest)":
            self.files.sort(key=os.path.getmtime, reverse=True)
        elif mode == "Size (Largest)":
            self.files.sort(key=os.path.getsize)
        elif mode == "Size (Smallest)":
            self.files.sort(key=os.path.getsize, reverse=True)
        elif mode == "Random":
            random.shuffle(self.files)

        self.current_index = 0
        self.populate_file_list()
        self.file_list.setFocus()

    def safe_stop_and_release_vlc(self):
        if self.vlc_player:
            try:
                self.vlc_player.stop()
                QApplication.processEvents()

                timer = QElapsedTimer()
                timer.start()
                while True:
                    try:
                        state = self.vlc_player.get_state()
                    except:
                        break
                    if state in [vlc.State.NothingSpecial, vlc.State.Stopped] or timer.elapsed() > 1000:
                        break
                    QApplication.processEvents()
                    #time.sleep(0.05)

                self.vlc_player.set_media(None)
                dprint("🛑 Releasing old VLC player")
                self.vlc_player.release()
                self.vlc_player = None
                self._last_video_path = None  # ✅ allow reloading same file later

            except Exception as e:
                dprint("⚠️ VLC cleanup error:", e)



    def show_file(self):
        if self._vlc_busy:
            dprint("⏳ VLC busy -- skipping show_file")
            return
        if not self.files or getattr(self, "_vlc_busy", False):
            return

        self._vlc_busy = True

        full_path = self.files[self.current_index]
        #self.register_file(full_path)


        if getattr(self, '_last_loaded_path', None) == full_path:
            self._vlc_busy = False
            return

        self._last_loaded_path = full_path

        try:
            _, ext = os.path.splitext(full_path.lower())

            try:
                self.poll_timer.blockSignals(True)
                self.poll_timer.timeout.disconnect(self.update_vlc_position)
            except:
                pass

            self.safe_stop_and_release_vlc()

            if self.movie:
                self.movie.stop()
                self.movie = None

            self.label.clear()
            self.label.setText("")
            self.label.setPixmap(QPixmap())
            self.video_widget.hide()
            self.label.show()
            #self.print_current_file_info()
            


            if ext in IMAGE_EXTENSIONS:
                self.show_image(full_path)
                self.playback_slider.setVisible(False)

            elif ext in VIDEO_EXTENSIONS:
                #self.import_file_metadata(full_path)
                self.show_video(full_path)

            elif ext in GIF_EXTENSIONS:
                self.show_gif(full_path)

            else:
                self.label.setText("Unsupported file type")

        except Exception as e:
            dprint(f"❌ Failed to load file: {full_path}\n{e}")
            self.label.setText("⚠️ Error loading file")
            self.label.show()
            self.video_widget.hide()

        finally:
            self.poll_timer.blockSignals(False)
            self._vlc_busy = False

            #self.preload_next_file_metadata()

            if hasattr(self, '_last_requested_index') and self._last_requested_index != self.current_index:
                idx = self._last_requested_index
                self._last_requested_index = None
                self.current_index = idx
                QTimer.singleShot(0, self.show_file)


    def show_image(self, path):
        self.video_widget.hide()
        self.label.show()

        pixmap = QPixmap(path)
        if pixmap.isNull():
            raise ValueError("Image failed to load.")
        scaled = pixmap.scaled(
            self.display_panel.width(),
            self.display_panel.height() - 50,
            Qt.KeepAspectRatio,
            Qt.SmoothTransformation
        )
        self.label.setPixmap(scaled)



    def show_video(self, full_path):
        if self._vlc_binding_pending:
            d("⏳ VLC bind already in progress, skipping duplicate call.")
            return
        self._vlc_binding_pending = True

        if full_path == getattr(self, "_last_video_path", None):
            print("🔁 Duplicate show_video call skipped (same file)")
            return
        self._last_video_path = full_path

        def bind_and_play():
            try:
                self.vlc_player = self.vlc_instance.media_player_new()
                win_id = int(self.video_widget.winId())
                dprint(f"🎯 Binding VLC to HWND: {win_id}")
                self.vlc_player.set_hwnd(win_id)

                media = self.vlc_instance.media_new(full_path)
                media.add_option("audio-filter=compressor,normvol")
                media.add_option("compressor-ratio=10")
                media.add_option("compressor-threshold=-30")
                media.add_option("compressor-attack=10")
                media.add_option("compressor-release=200")
                media.add_option("compressor-makeup-gain=15")
                media.add_option("normvol-level=2")

                self.vlc_player.set_media(media)
                self.vlc_player.play()
                dprint("▶️ VLC .play() called")


                try:
                    self.poll_timer.timeout.disconnect()
                except:
                    pass
                self.poll_timer.timeout.connect(self.update_vlc_position)

                self.playback_slider.setVisible(True)
                self.playback_slider.setValue(0)
                self.video_duration = 1
                QTimer.singleShot(500, self.set_video_duration)

            except Exception as e:
                dprint("⚠️ show_video crash:", e)
                self.label.setText("⚠️ Error playing video")
                self.label.show()
                self.video_widget.hide()
            finally:
                self._vlc_binding_pending = False

        self.video_widget.setAttribute(Qt.WA_NativeWindow, True)
        self.video_widget.show()
        self.label.hide()
        QApplication.processEvents()
        self.video_widget.winId()
        QTimer.singleShot(0, bind_and_play)



    def show_gif(self, path):
        self.video_widget.hide()
        self.label.show()

        self.movie = QMovie(path)
        self.movie.setCacheMode(QMovie.CacheAll)
        self.movie.setSpeed(100)
        self.label.setMovie(self.movie)
        self.movie.start()

    def set_current_file(self, index):
        if not (0 <= index < len(self.files)):
            return

        if hasattr(self, '_last_loaded_path'):
            current_path = self.files[index]
            if current_path == self._last_loaded_path:
                return  # ✅ Skip redundant reload

        self.current_index = index
        self._last_loaded_path = self.files[index]

        if self.file_list.currentRow() != index:
            self.file_list.setCurrentRow(index)

        self.show_file()

    def preload_next_file_metadata(self):
        if self.current_index + 1 >= len(self.files):
            return

        next_path = self.files[self.current_index + 1]
        rel = safe_relpath(next_path, APP_DIR)

        if self.collection["files"].get(rel, {}).get("imported", False):
            dprint(f"✅ Next file already imported: {rel}")
            return

        dprint(f"📦 Preloading metadata for next file: {os.path.basename(next_path)}")
        #self.import_file_metadata(next_path)


    def set_video_duration(self):
        if not self.vlc_player:
            dprint("⏱️ Skipping set_video_duration: vlc_player is None")
            return

        try:
            duration_ms = self.vlc_player.get_length()
            if duration_ms <= 0:
                dprint("⏱️ VLC returned invalid duration.")
                return

            duration = duration_ms / 1000
            self.video_duration = duration

            if not self.clip_mode_active:
                self.clip_zoom_start = 0
                self.clip_zoom_end = self.video_duration

            self.playback_slider.update()
            dprint(f"⏱️ Video duration set to {duration:.2f} seconds")

        except Exception as e:
            dprint(f"⚠️ Failed to set video duration: {e}")


    def add_file_to_playlist(self):
        if not hasattr(self, 'dest_playlist') or not self.dest_playlist:
            if not os.path.isdir(self.playlist_dir): 
                if os.path.exists(self.playlist_dir):
                    QMessageBox.warning(self, "Error", "'playlists' exists but is not a folder.")
                    return
                os.makedirs(self.playlist_dir)

            playlists = [
                f.replace(".json", "").replace("_", " ")
                for f in os.listdir(self.playlist_dir)
                if f.endswith(".json")
            ]

            if not playlists:
                QMessageBox.information(self, "No Playlists", "You don't have any playlists to add to.")
                return

            selected, ok = QInputDialog.getItem(
                self, "Select Playlist", "Add file to which playlist:", playlists, 0, False
            )
            if not ok or not selected:
                return

            self.dest_playlist = self.normalize_playlist_name(selected)

        playlist_path = self.get_playlist_path(self.dest_playlist)

        # Use absolute path for encoding
        abs_path = os.path.abspath(self.files[self.current_index])
        encoded = encode_path(abs_path)

        # Load or initialize the playlist
        if os.path.exists(playlist_path):
            with open(playlist_path, 'r') as f:
                playlist = json.load(f)
        else:
            playlist = []

        if encoded not in playlist:
            playlist.append(encoded)
            with open(playlist_path, 'w') as f:
                json.dump(playlist, f, indent=4)
            self.show_toast(f"✅ Added to playlist: {self.dest_playlist}")
        else:
            self.show_toast("Already in playlist.")


    def show_toast(self, message, duration=2000):
        self.toast_label.setText(message)
        self.toast_label.adjustSize()

        # Position it near bottom-center
        margin = 50
        width = self.toast_label.width()
        height = self.toast_label.height()
        x = (self.width() - width) // 2
        y = self.height() - height - margin
        self.toast_label.move(x, y)
        self.toast_label.setVisible(True)
        QTimer.singleShot(duration, lambda: self.toast_label.setVisible(False))

    def randomize_files(self):
        random.shuffle(self.files)
        self.populate_file_list()
        if self.files:
            self.current_index = 0
            self.show_file()

    def update_view_from_list(self, row):
        if 0 <= row < len(self.files):
            self.current_index = row
            self.show_file()

    

if __name__ == "__main__":
    app = QApplication(sys.argv)
    dark_stylesheet = """
    QWidget {
        background-color: #121212;
        color: #e0e0e0;
        font-family: Segoe UI, sans-serif;
        font-size: 10pt;
    }

    QListWidget, QComboBox, QMenuBar, QMenu {
        background-color: #1e1e1e;
        border: 1px solid #333;
    }

    QListWidget::item:selected {
        background-color: #2d89ef;
        color: white;
    }

    QPushButton {
        background-color: #2b2b2b;
        border: 1px solid #444;
        padding: 6px 12px;
        border-radius: 4px;
    }

    QPushButton:hover {
        background-color: #3a3a3a;
    }

    QCheckBox, QLabel {
        color: #ccc;
    }
    """
    app.setStyleSheet(dark_stylesheet)
    viewer = FileViewer()
    viewer.show()
    sys.exit(app.exec_())