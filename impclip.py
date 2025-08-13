import io
import zipfile
import psutil
import pyperclip
import ollama
import argparse
import threading
import time
import signal
import sys
import logging
from pathlib import Path
import shutil
import platform
import subprocess
import os
import keyboard
from plyer import notification
from pystray import Icon, MenuItem, Menu
from PIL import Image
from PySide6.QtWidgets import QApplication, QMainWindow, QPlainTextEdit, QLabel, QVBoxLayout, QWidget, QHBoxLayout, \
    QLineEdit, QCheckBox, QDialog, QPushButton, QStyle, QProgressBar
from PySide6.QtGui import QFont, QIcon, Qt, QMovie
from PySide6.QtCore import QTimer, QSize, Signal, Slot, QThread, QObject, QSignalBlocker
import playsound as ps
import requests


class ConsoleOutput(QPlainTextEdit):
    def __init__(self, parent=None):
        super().__init__(parent=parent)
        self.setReadOnly(True)
        self.setFont(QFont("Consolas", 11))

    def write(self, message):
        self.insertPlainText(message)
        self.verticalScrollBar().setValue(self.verticalScrollBar().maximum())

    def flush(self):
        pass

class OcliPWindow(QMainWindow):

    notifications_button = None
    checkrows = None
    monitor_button = None
    top_row = None
    sys_p_layout = None
    sys_p_widget = None
    top_widget = None
    sys_prompt_input = None
    worker = None
    impClip = None
    layout = None
    widget = None
    infoLabel = None
    loading_screen = None
    movieLabel = None
    checkrowswidget = None
    sys_prompt_label = None
    title = None
    auto_button = None
    signal_download = Signal()

    def __init__(self, model, sys_prompt, ollama_path, force_path, app_icon):
        super().__init__()

        self.setWindowIcon(app_icon)
        self.setWindowTitle("OCliP")

        self.signal_download.connect(self.prompt_ollama_download)

        self.model = model
        self.sys_prompt = sys_prompt
        self.ollama_path = ollama_path
        self.force_path = force_path

        self.textStyle = """
            QMainWindow { background-color: #1e1e1e; margin: 2px }
            QPlainTextEdit, QLineEdit {
                background-color: #2e2e2e;
                color: #d4d4d4;
                font-family: Consolas;
                font-size: 11pt;
                padding: 3px;
                margin: 2px;
                border-radius: 5px;
                border: none;
            }
            QLabel {
                margin: 2px; 
                padding: 2px;
                color: #d4d4d4;
            }
            QCheckBox { 
                font-family: Consolas;
                font-size: 11pt;
                color: #d4d4d4; 
                margin: 1px; 
                padding: 1px; 
            }
            QProgressBar {
                border-radius: 14px;
                font-family: Consolas;
                font-size: 11pt;
                font-weight: bold;
                background-color: #2e2e2e;
                padding: 5px;
            }
            QProgressBar::text {
                color: #d4d4d4;
                font-family: Consolas;
                font-size: 11pt;
                font-weight: bold;
            }
            QProgressBar::chunk {
                background-color: #5cba47;
                font-family: Consolas;
                font-size: 11pt;
                border-radius: 14px;
                font-weight: bold;
            }
            QPushButton {
                font-family: Consolas;
                font-size: 11pt;
                background-color: #2e2e2e;
                width: 70px;
                color: #d4d4d4;
                padding: 5px;
                margin: 5px;
            }
        """

        self.console = ConsoleOutput()
        self.setup_loading_screen()
        self.setup_ui()

        self.setStyleSheet(self.textStyle)
        sys.stdout = self.infoLabel
        sys.stderr = self.infoLabel

        QTimer.singleShot(0, self.on_load)

    def setup_loading_screen(self):
        self.movieLabel = QLabel(alignment=Qt.AlignmentFlag.AlignCenter)
        self.loading_screen = QMovie(str(resource_path("./images/loading.gif")))
        self.loading_screen.setScaledSize(QSize(32, 32))
        self.movieLabel.setMovie(self.loading_screen)
        self.loading_screen.start()

        self.infoLabel = QLabel("Loading...", alignment=Qt.AlignmentFlag.AlignCenter)
        self.infoLabel.setFont(QFont("Consolas", 11, weight=2))
        self.infoLabel.write = self.info_write  # attach custom method

    def setup_ui(self):
        self.widget = QWidget()
        self.layout = QVBoxLayout(self.widget)
        self.layout.setSpacing(0)
        self.layout.setAlignment(Qt.AlignmentFlag.AlignCenter)

        self.layout.addWidget(self.movieLabel)
        self.layout.addWidget(self.infoLabel)

        self.setCentralWidget(self.widget)

    def info_write(self, x):
        try:
            msg = x[:-1].split("]")[1] if "]" in x else x
            self.infoLabel.setText(msg)
        except Exception as e:
            self.infoLabel.setText(x)
            self.console.write(str(e))
        self.console.write(x)

    @Slot()
    def on_load(self):
        self.impClip = ImproveClipboard(
            self.model,
            self.sys_prompt,
            self.ollama_path,
            self.force_path,
            self.update_flag,
            self.signal_download
        )
        self.worker = WorkerThread(self.impClip)
        self.worker.finished.connect(self.change_screen)
        self.worker.start()

    @Slot()
    def prompt_ollama_download(self):
        download = DownloadDialog()
        download.setStyleSheet(self.textStyle)
        download.setWindowIcon(download.style().standardIcon(QStyle.StandardPixmap.SP_MessageBoxWarning))
        download.exec()
        self.impClip.wait_for_download = False

    @Slot(bool)
    def change_screen(self, _):
        sys.stdout = self.console
        sys.stderr = self.console

        self.layout.removeWidget(self.movieLabel)
        self.layout.removeWidget(self.infoLabel)

        self.title = QLabel("OCliP")
        self.title.setFont(QFont("Consolas", 24, QFont.Weight.Bold))
        self.title.setContentsMargins(0, 0, 40, 0)

        self.sys_prompt_label = QLabel()
        self.sys_prompt_label.setFont(QFont("Consolas", 14))
        self.sys_prompt_label.setText("System Prompt")
        self.sys_prompt_input = QLineEdit(clearButtonEnabled=True)
        self.sys_prompt_input.setText(self.impClip.sys_prompt)
        self.sys_prompt_input.setCursorPosition(-len(self.impClip.sys_prompt))

        def update_prompt():
            self.impClip.set_sys_prompt(self.sys_prompt_input.text())
            self.impClip.update_config()

        self.sys_prompt_input.editingFinished.connect(update_prompt)

        self.checkrows = QVBoxLayout()
        self.checkrows.setContentsMargins(0, 0, 20, 0)

        self.notifications_button = QCheckBox("Notifications")
        self.notifications_button.setToolTip("Show notifications for setting changes. (Ctrl+N)")
        self.notifications_button.setChecked(self.impClip.notifications_enabled)
        self.notifications_button.stateChanged.connect(lambda x: self.update_flag("notifications", not self.impClip.notifications_enabled))
        self.notifications_button.setContentsMargins(0, 0, 0, 0)
        self.monitor_button = QCheckBox("Monitor Clipboard")
        self.monitor_button.setToolTip("Check clipboard for new content. (Ctrl+Shift+C)")
        self.monitor_button.setChecked(self.impClip.monitoring_enabled)
        self.monitor_button.stateChanged.connect(lambda x: self.update_flag("monitor", not self.impClip.monitoring_enabled))
        self.monitor_button.setContentsMargins(0, 0, 0, 0)
        self.auto_button = QCheckBox("Auto Paste")
        self.auto_button.setToolTip("Automatically paste the enhanced content. (Ctrl+Shift+C)")
        self.auto_button.setChecked(self.impClip.auto_paste)
        self.auto_button.stateChanged.connect(lambda x: self.update_flag("auto", not self.impClip.auto_paste))
        self.auto_button.setContentsMargins(0, 0, 0, 0)

        self.checkrows.addWidget(self.auto_button)
        self.checkrows.addWidget(self.monitor_button)
        self.checkrows.addWidget(self.notifications_button)

        self.top_row = QHBoxLayout()
        self.sys_p_layout = QVBoxLayout()
        self.sys_p_layout.addWidget(self.sys_prompt_label)
        self.sys_p_layout.addWidget(self.sys_prompt_input)

        self.top_row.addWidget(self.title)
        self.top_row.addLayout(self.checkrows)
        self.top_row.addLayout(self.sys_p_layout)

        self.layout.addLayout(self.top_row)
        self.layout.addWidget(self.console)

        self.loading_screen.stop()
        self.movieLabel.deleteLater()

    def update_flag(self, flag, val):
        match flag:
            case "auto":
                with QSignalBlocker(self.auto_button):
                    self.auto_button.setChecked(val)
                self.impClip.toggle_auto_paste()
                return
            case "notifications":
                with QSignalBlocker(self.notifications_button):
                    self.notifications_button.setChecked(val)
                self.impClip.toggle_notifications()
                return
            case "monitor":
                with QSignalBlocker(self.monitor_button):
                    self.monitor_button.setChecked(val)
                self.impClip.toggle_monitor()
                return
            case _:
                logging.info(f"Unknown Flag: {flag}")

    def closeEvent(self, event):
        logging.info("Shutting down...")
        self.impClip.signal_handler(signal.SIGINT, None)
        event.accept()


class WorkerThread(QThread):
    finished = Signal(bool)

    def __init__(self, imp):
        super().__init__()
        self.imp = imp


    def run(self):
        self.imp.initialize()
        self.finished.emit(True)


class DownloadDialog(QDialog):
    def __init__(self, dest_folder="ollama"):
        super().__init__()
        self.dest_folder = dest_folder
        self.setWindowTitle("Warning")
        self.setMinimumWidth(400)

        layout = QVBoxLayout()
        layout.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.label = QLabel("Ollama executable not found! Please download it to continue (1.24 GB).")
        self.label.setFont(QFont("Consolas", 11))
        layout.addWidget(self.label)

        self.progressBar = QProgressBar()
        self.progressBar.setFixedWidth(self.width()-100)
        self.progressBar.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.progressBar.hide()
        layout.addWidget(self.progressBar)

        self.download_btn = QPushButton("Download")
        self.download_btn.clicked.connect(self.download)

        button_layout = QHBoxLayout()
        button_layout.setAlignment(Qt.AlignmentFlag.AlignCenter)
        button_layout.addWidget(self.download_btn)

        layout.addLayout(button_layout)
        self.setLayout(layout)

        self.signals = DownloadSignals()
        self.pwidth = self.progressBar.width()
        self.pheight = self.progressBar.height()

        def updateProgress(progress):
            self.progressBar.setValue(progress)
            r = str(min(int(progress*self.pheight/200), 11))
            self.progressBar.setStyleSheet("QProgressBar::chunk { border-radius: " + r + "px; }")

        self.signals.progress.connect(updateProgress)
        self.signals.done.connect(self.on_download_done)


    @Slot(bool, str)
    def on_download_done(self, success, message):
        if success:
            self.label.setText("Download complete. Ollama is ready to use.")
            self.download_btn.setEnabled(False)
        else:
            self.label.setText(f"Download failed: {message}")
            self.download_btn.setEnabled(True)
        self.progressBar.hide()
        self.accept()

    @Slot()
    def download(self):
        self.download_btn.setEnabled(False)
        self.label.setText("Downloading... Please wait.")
        self.progressBar.setRange(0, 100)
        self.progressBar.setValue(0)
        self.progressBar.show()
        def run():
            sys_os = platform.system()
            if sys_os == "Linux":
                url = "https://github.com/ollama/ollama/releases/latest/download/ollama-linux-amd64.tgz"
            elif sys_os == "Darwin":
                url = "https://github.com/ollama/ollama/releases/latest/download/Ollama-darwin.zip"
            elif sys_os == "Windows":
                url = "https://github.com/ollama/ollama/releases/latest/download/ollama-windows-amd64.zip"
            else:
                self.signals.done.emit(False, "Unsupported OS.")
                self.download_btn.setEnabled(True)
                return

            try:
                with requests.get(url, stream=True) as r:
                    r.raise_for_status()
                    total = int(r.headers.get('Content-Length', 0))
                    downloaded = 0
                    chunks = []
                    for chunk in r.iter_content(chunk_size=8192):
                        if chunk:
                            chunks.append(chunk)
                            downloaded += len(chunk)
                            percent = int(downloaded * 100 / total)
                            self.signals.progress.emit(percent)

                    zip_data = b''.join(chunks)
                    os.makedirs(self.dest_folder, exist_ok=True)
                    if url.endswith(".zip"):
                        with zipfile.ZipFile(io.BytesIO(zip_data)) as z:
                            z.extractall(self.dest_folder)
                    elif url.endswith(".tgz") or url.endswith(".tar.gz"):
                        import tarfile
                        with tarfile.open(fileobj=io.BytesIO(zip_data), mode="r:gz") as tar:
                            tar.extractall(self.dest_folder)
                    else:
                        raise Exception("Unsupported archive format.")

                    self.signals.done.emit(True, "Download complete.")

            except Exception as e:
                self.signals.done.emit(False, f"Failed: {str(e)}")

        threading.Thread(target=run, daemon=True).start()


class DownloadSignals(QObject):
    progress = Signal(int)
    done = Signal(bool, str)


class ImproveClipboard:

    client = None
    ollama_started = False
    installed_ollama_path = shutil.which("ollama")
    ollama_path = str(Path(installed_ollama_path).parent) if installed_ollama_path is not None else "./ollama/"
    monitoring_enabled = True
    triggered = False
    stop_event = threading.Event()
    notifications_enabled = True
    auto_paste = False
    sys_os = platform.system() 
    tray_icon = None
    app_name = "OCliP"
    tray = None
    thread = None
    wait_for_download = False
    default_model_name = "gemma3"
    default_sys_prompt = "Improve the following text without significantly changing the word count or meaning."
    sys_postfix = "Output only the requested text in the format of the text itself and nothing else, this is extremely important. "

    def __init__(
            self,
            model_name,
            sys_prompt,
            ollama_path,
            force_path,
            update_flag,
            signal_download,):

        signal.signal(signal.SIGINT, self.signal_handler)
        signal.signal(signal.SIGTERM, self.signal_handler)
        self.setLogger()

        self.model_name = model_name
        self.sys_prompt = sys_prompt
        self.config_pth = Path("./oclip.cfg").resolve().absolute()

        self.notif_hotkey = "ctrl+n"
        self.monitor_hotkey = "ctrl+m"
        self.trigger_hotkey = "ctrl+c"
        self.auto_paste_hotkey = "ctrl+shift+a"

        lines = self.get_config()
        if self.model_name is None:
            self.model_name = lines.get("model", self.default_model_name)
        self.sys_postfix = lines.get("sys_postfix", self.sys_postfix)
        if self.sys_prompt is None:
            self.sys_prompt = lines.get("sys_prompt", self.default_sys_prompt)
        self.notif_hotkey = lines.get("notif_hotkey", self.notif_hotkey)
        self.monitor_hotkey = lines.get("monitor_hotkey", self.monitor_hotkey)
        self.auto_paste_hotkey = lines.get("auto_paste_hotkey", self.auto_paste_hotkey)

        with open(self.config_pth, "w") as f:
            f.write("### OCliP Configuration File\n")
            f.write("# Ollama model name. Please ensure that the model actually exists in the Ollama Repo.\n")
            f.write(f"model={self.model_name}\n")
            f.write("# System prompt to use for model output (needs to be in one line).\n")
            f.write(f"sys_prompt={self.sys_prompt}\n")
            f.write("# System prompt postfix.\n")
            f.write(f"sys_postfix={self.sys_postfix}\n")
            f.write("# Notification toggle hotkey.\n")
            f.write(f"notif_hotkey={self.notif_hotkey}\n")
            f.write("# Clipboard monitoring toggle hotkey.\n")
            f.write(f"monitor_hotkey={self.monitor_hotkey}\n")
            f.write("# Auto Paste toggle hotkey.\n")
            f.write(f"auto_paste_hotkey={self.auto_paste_hotkey}\n")

        self.force_path = force_path
        self.update_flag = update_flag
        self.signal_download = signal_download

        if self.sys_os == "Windows":
            self.app_icon = str(resource_path("./icons/icon.ico"))
        else:
            self.app_icon = str(resource_path("./icons/icon.png"))
        
        self.notif_audio = str(resource_path("./sounds/notify.mp3"))

        self.user_ollama_path = ollama_path

    def initialize(self):
        try:
            self.checkForOllama(self.user_ollama_path)
            self.initOllama()
        except OllamaNotFoundException as e:
            logging.critical(f"Error while checking for Ollama. Are you sure it's installed?\n{e}")
            self.exit_app(-1, False)
        except Exception as e:
            logging.critical(f"Error initializing Ollama client!\n{e}")
            self.exit_app(-1)

        self.tray_icon = self.make_tray_icon()
        self.tray = threading.Thread(
            target=self.tray_icon.run,
            daemon=True,
            name="TrayIcon"
        )
        self.tray.start()
        self.setup_hotkey()
        self.thread = self.start_clipboard_monitor()
        self.thread.start()
        
    def checkForOllama(self, ollama_path):
        if self.is_ollama_running() and not self.force_path:
            logging.info("Ollama is already running; Use --force-path to force specified path.")
            self.ollama_started = True
            return
        if ollama_path is None:
            if self.force_path:
                logging.info("Can't force custom Ollama path as it is not defined!")
                raise OllamaNotFoundException("Ollama executable not found at specified path.")
            else:
                try:
                    if self.ollama_path is None:
                        self.signal_download.emit()
                        self.wait_for_download = True
                    else:
                        pathobj = Path(str(self.ollama_path))
                        if not pathobj.exists():
                            self.signal_download.emit()
                            self.wait_for_download = True
                        else:
                            self.ollama_path = pathobj.resolve().absolute()
                except Exception as e:
                    logging.info("Invalid Ollama path in system PATH!")
                    raise OllamaNotFoundException(e)
        else:
            try:
                pathobj = Path(ollama_path).resolve().absolute()
                if not pathobj.exists():
                    raise OllamaNotFoundException("Ollama executable not found at specified path.")
                else:
                    self.ollama_path = pathobj
            except Exception as e:
                logging.info("Invalid Ollama path specified!")
                raise OllamaNotFoundException(e)

        if self.wait_for_download:
            while self.wait_for_download:
                time.sleep(5)
            self.ollama_path = Path(self.ollama_path).resolve().absolute()
        os.environ["PATH"] = os.environ.get("PATH", "") + os.pathsep + str(self.ollama_path)

    def signal_handler(self, sig, frame):
        logging.info("Shutdown signal received. Exiting.")
        self.update_config()
        self.stop_threads()

    def get_config(self):
        try:
            with open(self.config_pth, "r") as f:
                lines = {}
                for line in f:
                    if "=" in line and not line.startswith("#"):
                        key, val = line.strip().split("=", 1)
                        lines[key] = val
            return lines
        except Exception as e:
            return {}

    def update_config(self):
        lines = self.get_config()
        mn = lines.get("model", self.model_name)
        spfx = lines.get("sys_postfix", self.sys_postfix)
        sp = lines.get("sys_prompt", self.sys_prompt)
        n = lines.get("notif_hotkey", self.notif_hotkey)
        m = lines.get("monitor_hotkey", self.monitor_hotkey)
        a = lines.get("auto_paste_hotkey", self.auto_paste_hotkey)
        with open(self.config_pth, "w") as f:
            f.write("### OCliP Configuration File\n")

            f.write("# Ollama model name. Please ensure that the model actually exists in the Ollama Repo.\n")
            if self.model_name != mn:
                f.write(f"model={self.model_name}\n")
            else:
                f.write(f"model={mn}\n")

            f.write("# System prompt to use for model output (needs to be in one line).\n")
            if self.sys_prompt != sp:
                f.write(f"sys_prompt={self.sys_prompt}\n")
            else:
                f.write(f"sys_prompt={sp}\n")

            f.write("# System prompt postfix.\n")
            if self.sys_postfix != spfx:
                f.write(f"sys_postfix={self.sys_postfix}\n")
            else:
                f.write(f"sys_postfix={spfx}\n")

            f.write("# Notification toggle hotkey\n")
            if self.notif_hotkey != n:
                f.write(f"notif_hotkey={self.notif_hotkey}\n")
            else:
                f.write(f"notif_hotkey={n}\n")

            f.write("# Clipboard monitoring toggle hotkey.\n")
            if self.monitor_hotkey != m:
                f.write(f"monitor_hotkey={self.monitor_hotkey}\n")
            else:
                f.write(f"monitor_hotkey={m}\n")

            f.write("# Auto Paste toggle hotkey.\n")
            if self.auto_paste_hotkey != a:
                f.write(f"auto_paste_hotkey={self.auto_paste_hotkey}\n")
            else:
                f.write(f"auto_paste_hotkey={a}\n")

        logging.info("Config updated!")

    def stop_threads(self):
        self.stop_event.set()
        if self.thread.is_alive():
            self.thread.join()
        self.exit_app()

    def notify_sound(self):
        if self.notifications_enabled:
            ps.playsound(self.notif_audio)
    
    def exit_app(self, code=0, kill_o=True):
        if kill_o:
            self.killOllama()
        try:
            if self.tray_icon is not None:
                self.tray_icon.stop()
        except Exception as e:
            logging.info(f"Couldn't stop tray icon:\n{e}")
        os._exit(code)

    def killOllama(self):
        if self.sys_os == "Windows":
            subprocess.run(['taskkill', '/F', '/IM', 'ollama.exe'], creationflags=subprocess.CREATE_NO_WINDOW)
        else:
            subprocess.run(['pkill', '-f', 'ollama'])

    @staticmethod
    def setLogger():
        logging.basicConfig(
            level=logging.INFO,
            format='[%(asctime)s] %(message)s',
            datefmt='%H:%M:%S',
            handlers = [
                logging.FileHandler("latest.log", mode="a", encoding="utf-8"),
                logging.StreamHandler()
            ],
        )
        logging.getLogger("httpx").setLevel(logging.WARNING)
        logging.getLogger("httpcore").setLevel(logging.WARNING)
        logging.getLogger("urllib3").setLevel(logging.WARNING)
        logging.getLogger("ollama").setLevel(logging.WARNING)
        
    def toggle_monitor(self):
        self.monitoring_enabled = not self.monitoring_enabled
        state = "enabled" if self.monitoring_enabled else "disabled"
        logging.info(f"Clipboard monitoring {state}.")
        self.tray_icon.update_menu()
        if self.notifications_enabled:
            self.notify("OCliP", f"Clipboard monitoring {state}.")

    def toggle_auto_paste(self):
        self.auto_paste = not self.auto_paste
        state = "enabled" if self.auto_paste else "disabled"
        logging.info(f"Auto Paste {state}.")
        self.tray_icon.update_menu()
        if self.notifications_enabled:
            self.notify("OCliP", f"Auto Paste {state}.")

    def toggle_trigger(self):
        if not self.triggered and self.monitoring_enabled:
            self.triggered = True
            logging.info(f"Clipboard updated triggered.")

    def toggle_notifications(self):
        self.notifications_enabled = not self.notifications_enabled
        state = "enabled" if self.notifications_enabled else "disabled"
        logging.info(f"Notifications {state}.")
        self.tray_icon.update_menu()
        if self.notifications_enabled:
            self.notify("OCliP", "Notifications Enabled")
    
    def setup_hotkey(self):
        keyboard.add_hotkey(
            self.monitor_hotkey,
            lambda: self.update_flag("monitor", not self.monitoring_enabled)
        )
        keyboard.add_hotkey(
            self.auto_paste_hotkey,
            lambda: self.update_flag("auto", not self.auto_paste)
        )
        keyboard.add_hotkey(
            self.trigger_hotkey,
            self.toggle_trigger
        )
        keyboard.add_hotkey(
            self.notif_hotkey,
            lambda: self.update_flag("notifications", not self.notifications_enabled)
        )

    def initOllama(self):
        try:
            if not self.ollama_started:
                kwargs = {}
                if self.sys_os == "Windows":
                    kwargs["creationflags"] = subprocess.CREATE_NO_WINDOW
                subprocess.Popen(['ollama', 'serve'],
                                 stdout=subprocess.DEVNULL,
                                 stderr=subprocess.DEVNULL,
                                 **kwargs
                )

            self.client = ollama.Client()

            t = threading.Thread(
                target=self.pull_model, 
                daemon=True,
                name="PullModel"
            )
            t.start()
            prefix = "Pulling Ollama model"
            while(t.is_alive()):
                p = f"."
                logging.info(prefix + p )
                if len(p)==3:
                    p = f"."
                else:
                    p += "."
                time.sleep(1)
            
            logging.info("Done pulling model! Loading Model...")
            _ = self.client.generate(model=self.model_name, prompt="Hello", )
            logging.info("Done loading model!")

        except Exception as e:
            raise e
    
    def pull_model(self):
        self.client.pull(self.model_name)

    def is_ollama_running(self):
        for proc in psutil.process_iter(['cmdline']):
            try:
                cmdline = proc.info['cmdline']
                if cmdline and 'ollama' in cmdline and 'serve' in cmdline:
                    return True
            except (psutil.NoSuchProcess, psutil.AccessDenied):
                continue
        return False

    def start_clipboard_monitor(self):
        def monitor():
            logging.info("Clipboard monitoring started.")
            while not self.stop_event.is_set():
                if self.monitoring_enabled and self.triggered:
                    try:
                        keyboard.press_and_release('ctrl+c')
                        time.sleep(0.1)
                        current_text = pyperclip.paste()
                        logging.info("Clipboard changed. Improving text...")
                        improved = self.improve_text(current_text)
                        pyperclip.copy(improved)
                        if self.auto_paste:
                            keyboard.send('ctrl+v')
                        logging.info("Clipboard updated with improved text.")
                        # self.notify("Clipboard Improved", "Text has been processed and updated.")
                        threading.Thread(target=self.notify_sound, daemon=True, name="NotifSound").start()
                    except KeyboardInterrupt:
                        break
                    except Exception as e:
                        logging.error(f"Error while monitoring clipboard:\n{e}")
                self.triggered = False
                time.sleep(0.1)

        return threading.Thread(
            target=monitor, 
            daemon=True,
            name="KeyboardMonitor"
        )

    def make_tray_icon(self):
        menu = Menu(
            MenuItem('Toggle Auto Paste',
                     lambda x: self.update_flag("auto", not self.auto_paste),
                     checked=lambda item: self.auto_paste),
            MenuItem(
                'Toggle Monitoring',
                lambda x: self.update_flag("monitor", not self.monitoring_enabled),
                checked=lambda item: self.monitoring_enabled),
            MenuItem('Toggle Notifications',
                     lambda x: self.update_flag("notifications", not self.notifications_enabled),
                     checked=lambda item: self.notifications_enabled),
            MenuItem('Quit', self.stop_threads)
        )
        icon_image = Image.open(self.app_icon)
        return Icon("OCliP", icon=icon_image, menu=menu)

    def improve_text(self, clipboard_text):
        try:
            response = self.client.generate(
                model=self.model_name,
                prompt=clipboard_text,
                system=self.sys_prompt+self.sys_postfix,
                keep_alive=10.0
            )
            return response['response'].strip()
        except Exception as e:
            logging.error(f"Text improvement failed:\n{e}")
            return clipboard_text
    
    def notify(self, title, message):
        if self.notifications_enabled:
            try:
                notification.notify(
                    title=title,
                    message=message,
                    timeout=0.5,
                    app_name=self.app_name,
                    app_icon=self.app_icon,
                    ticker='ticker',
                    toast=True
                )
            except Exception as e:
                logging.warning(f"Notification failed:\n{e}")

    def set_sys_prompt(self, prompt):
        self.sys_prompt = prompt
        self.update_config()
    

class OllamaNotFoundException(Exception):
    def __init__(self, *args):
        super().__init__(*args)

def resource_path(relative_path):
        base_path = Path(getattr(sys, '_MEIPASS', Path.cwd()))
        return base_path / relative_path

if __name__ == "__main__":

    parser = argparse.ArgumentParser()

    parser.add_argument('--model',
                        type=str,
                        required=False,
                        default=None,
                        help='Ollama model to run. Defaults to "gemma3"')
    
    parser.add_argument('--sys-prompt', 
                        type=str, 
                        required=False, 
                        help='System prompt to use for model output.',
                        default=None)
    
    parser.add_argument('--ollama-path', 
                        type=str, 
                        required=False, 
                        help='Path to Ollama executable. If undefined, the app will try to find it in your PATH, or prompt you to download it.',
                        default=None)
    
    parser.add_argument('--force-path',
                        action='store_true',
                        help='Force Ollama execution on the specified path.')
    
    args = parser.parse_args()

    app = QApplication(sys.argv)

    if platform.system() == "Windows":
        app_icon = QIcon(str(resource_path("./icons/icon.ico")))
    else:
        app_icon = QIcon(str(resource_path("./icons/icon.png")))

    app.setWindowIcon(app_icon)
    app.setApplicationName("OCliP")
    app.setApplicationDisplayName("OCliP")
    window = OcliPWindow(args.model, args.sys_prompt, args.ollama_path, args.force_path, app_icon)
    window.resize(900, 400)
    window.show()
    app.exec()