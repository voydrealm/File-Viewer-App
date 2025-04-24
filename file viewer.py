import sys
import os
import shutil
import time
import random
import json
from PyQt5.QtWidgets import QFileDialog
import shutil   
from PyQt5.QtWidgets import (QInputDialog, QMenu, QAction, QMessageBox, QSizePolicy,
    QApplication, QLabel, QWidget, QVBoxLayout, QHBoxLayout, QListWidget, QListWidgetItem,
    QPushButton, QFileDialog, QMessageBox, QCheckBox, QSplitter, QComboBox, QFrame, QMenuBar, QMenu,
    QSlider
)
from PyQt5.QtCore import QTimer
import subprocess
from PyQt5.QtGui import QPixmap, QMovie
from PyQt5.QtCore import QTimer
from PyQt5.QtCore import Qt, QUrl
import ctypes


APP_DIR = os.path.dirname(os.path.abspath(__file__))
PREF_FILE = os.path.join(APP_DIR, "preferences.json")
PLAYLIST_DIR = os.path.join(APP_DIR, "playlists")



# === VLC Setup === #
VLC_FOLDER = "C:/Program Files/VideoLAN/VLC"
libvlc_path = f"{VLC_FOLDER}/libvlc.dll"

# Explicitly load libvlc.dll before importing vlc
ctypes.CDLL(libvlc_path)

import vlc


CONFIG_FILE = "file_viewer_config.json"

IMAGE_EXTENSIONS = ['.png', '.jpg', '.jpeg', '.bmp']
VIDEO_EXTENSIONS = ['.mp4', '.avi', '.mov', '.mkv']
GIF_EXTENSIONS = ['.gif']

from PyQt5.QtWidgets import QListWidget

class FileListWidget(QListWidget):
    def keyPressEvent(self, event):
        # Ignore so parent widget can handle it
        event.ignore()

class FileViewer(QWidget):
    def __init__(self):
        super().__init__()
        os.makedirs(PLAYLIST_DIR, exist_ok=True)

        self.move_target_folder = None
        self.source_dir = ""
        self.dest_dir = ""
        self.files = []
        self.all_files = []
        self.current_index = 0
        self.fullscreen = False

        self.setWindowTitle("File Viewer")
        self.setGeometry(100, 100, 1000, 600)

        


        self.outer_layout = QVBoxLayout(self)
        self.setLayout(self.outer_layout)


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
        

        self.main_layout = QHBoxLayout()
        self.outer_layout.addLayout(self.main_layout)
        

        # Display Panel
        self.display_panel = QFrame()
        self.display_panel.setFrameShape(QFrame.StyledPanel)
        self.playback_slider = QSlider(Qt.Horizontal, self.display_panel)
        self.display_layout = QVBoxLayout(self.display_panel)
        
        self.display_layout.addWidget(self.playback_slider)

        
        self.playback_slider.setRange(0, 1000)
        self.playback_slider.setVisible(False)
        self.playback_slider.sliderPressed.connect(self.pause_video_for_scrub)
        self.playback_slider.sliderReleased.connect(self.scrub_video)

        self.playback_timer = QTimer()
        self.playback_timer.timeout.connect(self.update_playback_slider)


        self.label = QLabel("Click to select folder", self.display_panel)
        self.label.setAlignment(Qt.AlignCenter)
        self.label.setStyleSheet("QLabel { background-color: #333; color: #fff; font-size: 18px; }")
        self.label.setScaledContents(False)

        

        self.path_label = QLabel("", self.display_panel)
        self.path_label.setStyleSheet("QLabel { color: #999; font-size: 11px; }")
        self.path_label.setTextInteractionFlags(Qt.TextSelectableByMouse)

        self.display_layout.addWidget(self.path_label)
        self.display_layout.addWidget(self.label)

        self.path_label.setFixedHeight(18)
        self.path_label.setWordWrap(False)
        self.path_label.setSizePolicy(self.path_label.sizePolicy().horizontalPolicy(), QSizePolicy.Fixed)

        
        # VLC player instance
        vlc_args = [
    '--no-xlib',
    '--no-video-title-show',
    '--no-snapshot-preview',
    '--quiet',
    '--verbose=0'
]

        self.vlc_instance = vlc.Instance(vlc_args)
        self.vlc_player = self.vlc_instance.media_player_new()

        # Video frame for VLC
        self.video_widget = QFrame()
        self.video_widget.setFrameShape(QFrame.StyledPanel)
        self.video_widget.setStyleSheet("background-color: black;")
        self.video_widget.hide()

        self.display_layout.addWidget(self.label)
        self.display_layout.addWidget(self.video_widget)

        # Playlist Panel
        self.playlist_panel = QFrame()
        self.playlist_panel.setFrameShape(QFrame.StyledPanel)
        self.playlist_layout = QVBoxLayout(self.playlist_panel)

        # Menu Bar for playlist panel
        self.menu_bar = QMenuBar()
        self.controls_menu = QMenu("Controls", self)
        self.menu_bar.addMenu(self.controls_menu)

        self.playlist_dropdown = QComboBox()
        self.playlist_dropdown.view().setContextMenuPolicy(Qt.CustomContextMenu)
        self.playlist_dropdown.view().customContextMenuRequested.connect(self.show_playlist_context_menu)

        self.playlist_dropdown.addItem("All Files")
        self.playlist_dropdown.addItem("+ New Playlist")
        self.playlist_dropdown.currentIndexChanged.connect(self.playlist_dropdown_changed)
        
        self.menu_bar.setCornerWidget(self.playlist_dropdown, Qt.TopRightCorner)

        


        # Menu actions
        browse_source_action = self.controls_menu.addAction("Browse Source Folder")
        browse_source_action.triggered.connect(self.browse_source)

        select_dest_playlist_action = self.controls_menu.addAction("Select Destination Playlist")
        select_dest_playlist_action.triggered.connect(self.select_destination_playlist)


        randomize_action = self.controls_menu.addAction("Randomize Playlist")
        randomize_action.triggered.connect(self.randomize_files)

        #file list

        self.file_list = FileListWidget()

        #self.file_list.setFocusPolicy(Qt.NoFocus)
        self.file_list.setMinimumWidth(300)
        self.file_list.setMaximumWidth(500)
        self.file_list.itemClicked.connect(self.file_list_clicked)
        self.file_list.currentRowChanged.connect(self.update_view_from_list)
        self.file_list.setSelectionMode(QListWidget.ExtendedSelection)
        self.file_list.setContextMenuPolicy(Qt.CustomContextMenu)
        self.file_list.customContextMenuRequested.connect(self.show_file_list_context_menu)
        self.sort_combo = QComboBox()
        self.sort_combo.addItems([
            "Sort by Name (Asc)", "Sort by Name (Desc)",
            "Sort by Date (Asc)", "Sort by Date (Desc)",
            "Sort by Size (Asc)", "Sort by Size (Desc)",
            "Random"
        ])
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
        self.filter_menu.addAction("Images").setCheckable(True)
        self.filter_menu.addAction("Videos").setCheckable(True)
        self.filter_menu.addAction("GIFs").setCheckable(True)

        # Actions to control actual checkboxes
        self.filter_menu.actions()[0].toggled.connect(self.img_checkbox.setChecked)
        self.filter_menu.actions()[1].toggled.connect(self.vid_checkbox.setChecked)
        self.filter_menu.actions()[2].toggled.connect(self.gif_checkbox.setChecked)

        # Add the sort combo into the menu bar as well
        sort_action = QWidget()
        sort_layout = QVBoxLayout()
        sort_layout.addWidget(self.sort_combo)
        sort_action.setLayout(sort_layout)

        # Add filter menu and sort combo to menu bar
        self.menu_bar.addMenu(self.filter_menu)

        checkboxes_layout = QHBoxLayout()
        checkboxes_layout.addWidget(self.img_checkbox)
        checkboxes_layout.addWidget(self.vid_checkbox)
        checkboxes_layout.addWidget(self.gif_checkbox)

        self.playlist_layout.setMenuBar(self.menu_bar)
        self.playlist_layout.addWidget(self.sort_combo)
        self.playlist_layout.addWidget(self.file_list)

        # Main Splitter
        self.splitter = QSplitter(Qt.Horizontal)
        self.splitter.addWidget(self.display_panel)
        self.splitter.addWidget(self.playlist_panel)
        self.splitter.setSizes([self.width() - 300, 300])
        self.splitter.setCollapsible(0, False)
        self.splitter.setCollapsible(1, False)

        self.main_layout.addWidget(self.splitter)

        # VLC handles video now
        self.movie = None

        self.label.mousePressEvent = self.initial_folder_select
############################################################################################

        self.load_config()
        self.load_all_files()
        self.refresh_playlist_dropdown()
        self.load_preferences()
        self.current_playlist = None


############################################################################################


    def update_playback_slider(self):
        if self.vlc_player.is_playing():
            duration = self.vlc_player.get_length()
            current = self.vlc_player.get_time()
            if duration > 0:
                position = int((current / duration) * 1000)
                self.playback_slider.blockSignals(True)
                self.playback_slider.setValue(position)
                self.playback_slider.blockSignals(False)


    def pause_video_for_scrub(self):
        if self.vlc_player.is_playing():
            self.vlc_player.pause()

    def scrub_video(self):
        duration = self.vlc_player.get_length()
        if duration > 0:
            new_time = int((self.playback_slider.value() / 1000) * duration)
            self.vlc_player.set_time(new_time)
            self.vlc_player.play()


    def toggle_fullscreen(self):
        if self.fullscreen:
            self.showNormal()
            self.fullscreen = False
        else:
            self.showFullScreen()
            self.fullscreen = True

    def toggle_fullscreen(self):
        if self.fullscreen:
            self.showNormal()
            self.playlist_panel.show()
            self.fullscreen = False
        else:
            self.showFullScreen()
            self.playlist_panel.hide()
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
        print("Selected random folder:", selected_folder)

        collected_files = []
        for root, _, files in os.walk(selected_folder):
            for file in files:
                ext = os.path.splitext(file)[1].lower()
                if ext in IMAGE_EXTENSIONS + VIDEO_EXTENSIONS + GIF_EXTENSIONS:
                    collected_files.append(os.path.join(root, file))

        print("Files found:", len(collected_files))

        if not collected_files:
            QMessageBox.information(self, "No Files", "No supported files in selected folder.")
            return

        self.files = collected_files
        self.current_index = 0
        self.populate_file_list()
        self.show_file()
        self.file_list.setCurrentRow(0)
        self.show_toast(f"Random folder: {os.path.basename(selected_folder)}")



    def remove_selected_files_from_playlist(self, selected_files):
        if not self.current_playlist:
            return

        playlist_file = self.get_playlist_path(self.current_playlist)

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
            rel_path = os.path.relpath(abs_path, APP_DIR)
            if rel_path in playlist:
                playlist.remove(rel_path)
                removed += 1

        with open(playlist_file, "w") as f:
            json.dump(playlist, f, indent=2)

        self.load_playlist(self.current_playlist)
        QMessageBox.information(self, "Removed", f"{removed} file(s) removed from playlist.")

    def add_selected_files_to_playlist(self, selected_files):
        if not selected_files:
            return

        # Prompt for playlist if none set
        if not hasattr(self, 'dest_playlist') or not self.dest_playlist:
            if not os.path.isdir(PLAYLIST_DIR):
                if os.path.exists(PLAYLIST_DIR):
                    QMessageBox.warning(self, "Error", "'playlists' exists but is not a folder.")
                    return
                os.makedirs(PLAYLIST_DIR)

            playlists = [
                f.replace("_playlist.json", "").replace("_", " ")
                for f in os.listdir(PLAYLIST_DIR)
                if f.endswith("_playlist.json")
            ]

            if not playlists:
                QMessageBox.information(self, "No Playlists", "You don't have any playlists to add to.")
                return

            selected, ok = QInputDialog.getItem(self, "Select Playlist", "Add selected files to which playlist:", playlists, 0, False)
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
            rel_path = os.path.relpath(abs_path, APP_DIR)
            if rel_path not in playlist:
                playlist.append(rel_path)
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
        remove_from_playlist_action = None  # 🛠️ Define it safely here

        menu.addAction(add_to_playlist_action)

        # Only allow removal if a playlist (not "All Files") is active
        if hasattr(self, 'current_playlist') and self.current_playlist:
            remove_from_playlist_action = QAction("Remove Selected from Playlist", self)
            menu.addAction(remove_from_playlist_action)

        action = menu.exec_(self.file_list.mapToGlobal(position))
        selected_files = [self.files[self.file_list.row(item)] for item in selected_items]

        if action == add_to_playlist_action:
            self.add_selected_files_to_playlist(selected_files)

        elif remove_from_playlist_action and action == remove_from_playlist_action:
            self.remove_selected_files_from_playlist(selected_files)



    def get_playlist_path(self, name_or_label):
        base = self.normalize_playlist_name(name_or_label)
        return os.path.join(PLAYLIST_DIR, f"{base}_playlist.json")

    def normalize_playlist_name(self, name):
        return name.strip().lower().replace(" ", "_")


    def load_preferences(self):
        default_prefs = {
            "add_file_to_playlist": "Key_0",
            "next_file": "Key_Down",
            "previous_file": "Key_Up",
            "seek_left": "Key_Left",
            "seek_right": "Key_Right",
            "move_to_folder": "Key_Period",
            "play_random_folder": "Key_1",
            "toggle_fullscreen": "Key_F"



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



    def show_playlist_context_menu(self, position):
        index = self.playlist_dropdown.view().indexAt(position)
        if not index.isValid():
            return

        label = self.playlist_dropdown.itemText(index.row())

        # Skip protected entries
        if label in ["All Files", "+ New Playlist"]:
            return

        menu = QMenu()
        show_action = QAction("Show in Folder", self)
        delete_action = QAction("Delete Playlist", self)

        menu.addAction(show_action)
        menu.addAction(delete_action)

        action = menu.exec_(self.playlist_dropdown.mapToGlobal(position))

        # Get normalized filename from label
        playlist_filename = self.dropdown_label_to_filename.get(label)
        if not playlist_filename:
            return

        # Get full absolute path to playlist file
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
                    self.refresh_playlist_dropdown()
                    self.playlist_dropdown.setCurrentText("All Files")
                    self.load_all_files()
                except Exception as e:
                    QMessageBox.warning(self, "Error", f"Failed to delete playlist:\n{str(e)}")

        elif action == show_action:
            if os.path.exists(playlist_path):
                try:
                    if sys.platform == "win32":
                        subprocess.run(["explorer", "/select,", os.path.normpath(playlist_path)])
                    elif sys.platform == "darwin":
                        subprocess.run(["open", "-R", playlist_path])
                    else:
                        subprocess.run(["xdg-open", os.path.dirname(playlist_path)])
                except Exception as e:
                    QMessageBox.warning(self, "Error", f"Failed to open folder:\n{str(e)}")
            else:
                QMessageBox.warning(self, "Not Found", "Playlist file does not exist.")

    def load_all_files(self):
        if self.source_dir and os.path.exists(self.source_dir):
            self.load_files_recursive()
            self.populate_file_list()
            if self.files:
                self.current_index = 0
                self.show_file()

    def playlist_dropdown_changed(self, index):
        selected = self.playlist_dropdown.itemText(index)

        if selected == "All Files":
            self.load_all_files()

        elif selected == "+ New Playlist":
            self.prompt_new_playlist()

        else:
            # Treat anything else as a valid playlist file
            playlist_filename = self.dropdown_label_to_filename.get(selected)
            if playlist_filename:
                self.load_playlist(playlist_filename)



    def refresh_playlist_dropdown(self):
        self.playlist_dropdown.blockSignals(True)
        self.playlist_dropdown.clear()

        self.dropdown_label_to_filename = {}

        self.playlist_dropdown.addItem("All Files")

        if not os.path.exists(PLAYLIST_DIR):
            os.makedirs(PLAYLIST_DIR)

        for file in sorted(os.listdir(PLAYLIST_DIR)):
            if file.endswith("_playlist.json"):
                base = file.replace("_playlist.json", "")
                label = base.replace("_", " ")
                self.playlist_dropdown.addItem(label)
                self.dropdown_label_to_filename[label] = base

        self.playlist_dropdown.addItem("+ New Playlist")  # Always last
        self.playlist_dropdown.blockSignals(False)


    def prompt_new_playlist(self):
        name, ok = QInputDialog.getText(self, "New Playlist", "Enter playlist name:")
        if ok and name:
            base = self.normalize_playlist_name(name)  # ← this was missing
            playlist_path = self.get_playlist_path(base)

            if not os.path.exists(playlist_path):
                with open(playlist_path, 'w') as f:
                    json.dump([], f, indent=2)

            self.refresh_playlist_dropdown()
            self.playlist_dropdown.setCurrentText(name.strip())

    def load_playlist(self, name):
        playlist_path = self.get_playlist_path(name)

        if not os.path.exists(playlist_path):
            QMessageBox.warning(self, "Playlist Not Found", f"Playlist file not found:\n{playlist_path}")
            return

        with open(playlist_path, "r") as f:
            paths = json.load(f)

        self.files = []
        for rel_path in paths:
            abs_path = os.path.normpath(os.path.join(APP_DIR, rel_path))
            if os.path.exists(abs_path):
                self.files.append(abs_path)

        self.current_playlist = name  # ✅ Track the active playlist name

        self.current_index = 0

        if not self.files:
            self.label.setText("No valid files in this playlist.")
            self.label.setPixmap(QPixmap())
            self.video_widget.hide()
            self.file_list.clear()
            return

        self.populate_file_list()
        self.show_file()
        self.file_list.setCurrentRow(0)



    def select_destination_playlist(self):
        if not os.path.isdir(PLAYLIST_DIR):
            if os.path.exists(PLAYLIST_DIR):
                QMessageBox.warning(self, "Error", "'playlists' exists but is not a folder.")
                return
            os.makedirs(PLAYLIST_DIR)

        playlists = [
            f.replace("_playlist.json", "").replace("_", " ")
            for f in os.listdir(PLAYLIST_DIR)
            if f.endswith("_playlist.json")
        ]

        if not playlists:
            QMessageBox.information(self, "No Playlists", "You don't have any playlists to select.")
            return

        selected, ok = QInputDialog.getItem(self, "Select Destination Playlist", "Choose a playlist:", playlists, 0, False)

        if ok and selected:
            self.dest_playlist = self.normalize_playlist_name(selected)
            QMessageBox.information(self, "Destination Set", f"Selected destination: {selected}")


    def keyPressEvent(self, event):
        print("Pressed:", event.key(), "| Pref:", self.preferences["add_file_to_playlist"])
        if not self.files:
            super().keyPressEvent(event)
            return

        key = event.key()
        prefs = self.preferences
        full_path = os.path.relpath(self.files[self.current_index], APP_DIR)
        _, ext = os.path.splitext(full_path.lower())

        if key == prefs["previous_file"]:
            self.current_index = (self.current_index - 1) % len(self.files)
            self.file_list.setCurrentRow(self.current_index)
            self.show_file()
        
        elif key == self.preferences.get("toggle_fullscreen", Qt.Key_F):
            self.toggle_fullscreen()

        elif key == prefs["next_file"]:
            self.current_index = (self.current_index + 1) % len(self.files)
            self.file_list.setCurrentRow(self.current_index)
            self.show_file()

        elif key == prefs["seek_left"] and ext in VIDEO_EXTENSIONS:
            if self.vlc_player.is_playing():
                self.vlc_player.set_time(max(0, self.vlc_player.get_time() - 5000))

        elif key == prefs["seek_right"] and ext in VIDEO_EXTENSIONS:
            if self.vlc_player.is_playing():
                self.vlc_player.set_time(self.vlc_player.get_time() + 5000)

        elif key == prefs["add_file_to_playlist"]:
            self.add_file_to_playlist()

        elif key == self.preferences.get("move_to_folder", Qt.Key_Period):
            self.move_current_file_to_folder()

        elif key == self.preferences.get("play_random_folder"):
            self.play_random_folder()



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
            self.vlc_player.set_media(None)
            self.vlc_player.release()
            self.vlc_player = self.vlc_instance.media_player_new()
            self.vlc_player.set_hwnd(int(self.video_widget.winId()))

        if self.movie:
            self.movie.stop()
            self.movie = None

        QApplication.processEvents()
        time.sleep(0.1)

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




    def initial_folder_select(self, event):
        if not self.source_dir:
            self.browse_source()

    def browse_source(self):
        source = QFileDialog.getExistingDirectory(self, "Select Source Directory")
        if source:
            self.source_dir = source
            self.load_files_recursive()
            self.update_window_title()
            self.save_config()
            if not self.files:
                self.label.setText("No files found in the source directory.")
            else:
                self.show_file()
            

    def save_config(self):
        config = {'source_dir': self.source_dir, 'dest_dir': self.dest_dir}
        with open(CONFIG_FILE, 'w') as f:
            json.dump(config, f)

    def load_config(self):
        if os.path.exists(CONFIG_FILE):
            with open(CONFIG_FILE, 'r') as f:
                config = json.load(f)
                self.source_dir = config.get('source_dir', '')
                self.dest_dir = config.get('dest_dir', '')

                if self.source_dir and os.path.exists(self.source_dir):
                    self.load_files_recursive()
                    if self.files:
                        self.show_file()
                    self.update_window_title()
                    
                if self.dest_dir and os.path.exists(self.dest_dir):
                    self.update_window_title()

    def load_files_recursive(self):
        all_files = []
        for root, dirs, files in os.walk(self.source_dir):
            for file in files:
                full_path = os.path.join(root, file)
                if os.path.isfile(full_path):
                    all_files.append(full_path)
        self.all_files = all_files
        self.filter_files()
        self.populate_file_list()

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
            self.show_file()

    def populate_file_list(self):
        self.file_list.clear()
        for file in self.files:
            item = QListWidgetItem(os.path.basename(file))
            self.file_list.addItem(item)
        self.file_list.setCurrentRow(self.current_index)

    def update_window_title(self):
        title = f"File Viewer | Source: {self.source_dir}"
        if self.dest_dir:
            title += f" | Destination: {self.dest_dir}"
        self.setWindowTitle(title)

    def file_list_clicked(self, item):
        index = self.file_list.row(item)
        self.current_index = index
        self.show_file()

    def sort_files(self):
        current_sort = self.sort_combo.currentText()
        if "Name" in current_sort:
            reverse = "Desc" in current_sort
            self.files.sort(key=lambda x: os.path.basename(x).lower(), reverse=reverse)
        elif "Date" in current_sort:
            reverse = "Desc" in current_sort
            self.files.sort(key=lambda x: os.path.getmtime(x), reverse=reverse)
        elif "Size" in current_sort:
            reverse = "Desc" in current_sort
            self.files.sort(key=lambda x: os.path.getsize(x), reverse=reverse)
        elif "Random" in current_sort:
            random.shuffle(self.files)
        self.populate_file_list()
        if self.files:
            self.current_index = 0
            self.show_file()

    def show_file(self):
        if not self.files:
            return

        full_path = self.files[self.current_index]
        self.path_label.setText(os.path.relpath(full_path, APP_DIR))
        _, ext = os.path.splitext(full_path.lower())

        if self.movie:
            self.movie.stop()
            self.movie = None

        if self.vlc_player.is_playing():
            self.vlc_player.stop()

        self.playback_timer.stop()
        self.playback_slider.setVisible(False)
        self.label.clear()
        self.label.setPixmap(QPixmap())
        self.label.setText("")

        display_area_width = self.display_panel.width()
        display_area_height = self.display_panel.height() - 50

        if ext in IMAGE_EXTENSIONS:
            self.label.show()
            self.video_widget.hide()

            pixmap = QPixmap(full_path)
            if pixmap.isNull():
                self.label.setText(f"Cannot display: {os.path.basename(full_path)}")
            else:
                scaled = pixmap.scaled(display_area_width, display_area_height, Qt.KeepAspectRatio, Qt.SmoothTransformation)
                self.label.setPixmap(scaled)

        elif ext in GIF_EXTENSIONS:
            self.label.show()
            self.video_widget.hide()

            self.movie = QMovie(full_path)
            self.movie.setCacheMode(QMovie.CacheAll)
            self.movie.setSpeed(100)
            self.label.setMovie(self.movie)
            self.movie.start()

        elif ext in VIDEO_EXTENSIONS:
            self.label.hide()
            self.video_widget.show()

            self.vlc_player.stop()
            self.vlc_player.release()
            self.vlc_player = self.vlc_instance.media_player_new()
            self.vlc_player.set_hwnd(int(self.video_widget.winId()))

            media = self.vlc_instance.media_new(full_path)
            media.add_option("input-repeat=65535")
            self.vlc_player.set_media(media)
            self.vlc_player.play()

            self.playback_slider.setVisible(True)
            self.playback_slider.setValue(0)
            self.playback_timer.start(500)

        else:
            self.label.show()
            self.video_widget.hide()
            self.label.setText(f"File: {os.path.basename(full_path)}")




    def add_file_to_playlist(self):
        if not hasattr(self, 'dest_playlist') or not self.dest_playlist:
            # Prompt the user to choose a playlist
            if not os.path.isdir(PLAYLIST_DIR):
                if os.path.exists(PLAYLIST_DIR):
                    QMessageBox.warning(self, "Error", "'playlists' exists but is not a folder.")
                    return
                os.makedirs(PLAYLIST_DIR)

            # ✅ Correct path usage
            playlists = [
                f.replace("_playlist.json", "").replace("_", " ")
                for f in os.listdir(PLAYLIST_DIR)
                if f.endswith("_playlist.json")
            ]

            if not playlists:
                QMessageBox.information(self, "No Playlists", "You don't have any playlists to add to.")
                return

            selected, ok = QInputDialog.getItem(self, "Select Playlist", "Add file to which playlist:", playlists, 0, False)
            if not ok or not selected:
                return  # User canceled

            self.dest_playlist = self.normalize_playlist_name(selected)

        # Add the file to the selected playlist
        rel_path = os.path.relpath(self.files[self.current_index], APP_DIR)
        playlist_file = self.get_playlist_path(self.dest_playlist)

        if os.path.exists(playlist_file):
            with open(playlist_file, 'r') as f:
                playlist = json.load(f)
        else:
            playlist = []

        if rel_path not in playlist:
            playlist.append(rel_path)
            with open(playlist_file, 'w') as f:
                json.dump(playlist, f, indent=2)

            self.show_toast(f"Added to: {self.dest_playlist}")
        else:
            QMessageBox.information(self, "Already Exists", "This file is already in that playlist.")

    def show_toast(self, message, duration=2000):
        self.toast_label.setText(message)
        self.toast_label.adjustSize()

        # Position it near bottom-center
        margin = 20
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