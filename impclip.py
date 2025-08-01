import asyncio

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
from PySide6.QtWidgets import QApplication, QMainWindow, QPlainTextEdit, QLabel
from PySide6.QtGui import QFont, QIcon, Qt, QMovie
from PySide6.QtCore import QTimer, QSize, Signal, Slot, QThread
import playsound as ps


class ConsoleOutput(QPlainTextEdit):
    def __init__(self, parent=None):
        super().__init__(parent=parent)
        self.setReadOnly(True)
        self.setFont(QFont("Consolas", 10))

    def write(self, message):
        if '\r' in message:
            message=message.replace('\r', '')
            cursor = self.textCursor()
            cursor.movePosition(cursor.MoveOperation.StartOfBlock, cursor.MoveMode.KeepAnchor)
            cursor.removeSelectedText()
            cursor.deletePreviousChar()
            self.setTextCursor(cursor)

        self.insertPlainText(message)

    def flush(self):
        pass

class OcliPWindow(QMainWindow):

    def __init__(self, model, sys_prompt, ollama_path, force_path, app_icon):
        super().__init__()
        self.setWindowIcon(app_icon)
        self.setWindowTitle("OCliP")

        self.console = ConsoleOutput(self)

        self.label = QLabel(self)
        self.loading_screen = QMovie(str(resource_path("./images/loading.gif")))
        self.loading_screen.setScaledSize(QSize(64, 64))
        self.label.setMovie(self.loading_screen)
        self.loading_screen.start()
        self.label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.label.setStyleSheet("""
                    QLabel {
                        color: white;
                        font-size: 64pt;
                        font-weight: bold;
                        background-color: #1e1e1e;
                    }
                """)


        self.setCentralWidget(self.label)

        self.setStyleSheet(
            """
                QMainWindow {
                    background-color: #1e1e1e;
                }
                QPlainTextEdit {
                    background-color: #2e2e2e;
                    color: #d4d4d4;
                    font-family: Consolas;
                    font-size: 11pt;
                    padding: 2px;
                    margin: 4px;
                    border-radius: 10px;
                    border: none;
                }
            """
        )

        self.model = model
        self.sys_prompt = sys_prompt
        self.ollama_path = ollama_path
        self.force_path = force_path

        self.impClip = None
        self.worker = None

        sys.stdout = self.console
        sys.stderr = self.console

        QTimer.singleShot(0, self.on_load)


    @Slot()
    def on_load(self):
        self.impClip = ImproveClipboard(
            self.model,
            self.sys_prompt,
            self.ollama_path,
            self.force_path,
        )
        self.worker = WorkerThread(self.impClip)
        self.worker.finished.connect(self.change_screen)
        self.worker.start()

    @Slot(bool)
    def change_screen(self, finished):
        self.setCentralWidget(self.console)
        self.loading_screen.stop()
        self.label.deleteLater()


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



class ImproveClipboard:

    client = None
    ollama_started = False
    ollama_path = shutil.which("ollama")
    monitoring_enabled = True
    triggered = False
    stop_event = threading.Event()
    notifications_enabled = True
    sys_os = platform.system() 
    tray_icon = None
    app_name = "OCliP"
    tray = None
    thread = None

    def __init__(self, model_name, sys_prompt, ollama_path, force_path):
        signal.signal(signal.SIGINT, self.signal_handler)
        signal.signal(signal.SIGTERM, self.signal_handler)
        self.setLogger()

        self.model_name = model_name
        self.sys_prompt = sys_prompt + "\nOutput only the requested text and nothing, this is extremely important."
        self.force_path = force_path
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
            logging.info("Ollama is already running; if you wish to run the it specifically from the specified path, use --force-path.")
            self.ollama_started = True
            return
        if ollama_path is None:
            if self.force_path:
                logging.info("Can't force custom Ollama path as it is not defined!")
                raise OllamaNotFoundException("Ollama executable not found at specified path.")
            else:
                try:
                    pathobj = Path(self.ollama_path).resolve().absolute()
                    if not pathobj.exists():
                        raise OllamaNotFoundException("Ollama executable not found at specified path.")
                    else:
                        self.ollama_path = pathobj
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
        os.environ["PATH"] = os.environ.get("PATH", "") + os.pathsep + str(self.ollama_path.parent)
            
                

    def signal_handler(self, sig, frame):
        logging.info("Shutdown signal received. Exiting.")
        self.stop_threads()

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

    def setLogger(self):
        logging.basicConfig(
        level=logging.INFO,
        format="[%(asctime)s] [%(levelname)s] %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S"
    )
        
    def toggle_monitor(self):
        self.monitoring_enabled = not self.monitoring_enabled
        state = "enabled" if self.monitoring_enabled else "disabled"
        logging.info(f"Clipboard monitoring {state}.")
        self.notify("OCliP", f"Clipboard monitoring {state}.")

    def toggle_trigger(self):
        if not self.triggered and self.monitoring_enabled:
            self.triggered = True
            logging.info(f"Clipboard updated triggered.")
            # self.notify("Improving...", "Running clipboard improvement...")

    def toggle_notifications(self):
        self.notifications_enabled = not self.notifications_enabled
        if self.notifications_enabled:
            self.notify("OCliP", "Notifications Enabled")
    
    def setup_hotkey(self):
        keyboard.add_hotkey('ctrl+shift+c', self.toggle_monitor)
        keyboard.add_hotkey('ctrl+c', self.toggle_trigger)
        keyboard.add_hotkey('ctrl+n', self.toggle_notifications)

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
            prefix = "\rPulling Ollama model"
            while(t.is_alive()):
                p = f"."
                logging.info(prefix + p )
                if len(p)==3:
                    p = f"."
                else:
                    p += "."
                time.sleep(1)
            
            logging.info("Done!")

            logging.info("Loading Model...")
            _ = self.client.generate(model=self.model_name, prompt="Hello")
            logging.info("Done!")

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
                        current_text = pyperclip.paste()
                        logging.info("Clipboard changed. Improving text...")
                        improved = self.improve_text(current_text)
                        pyperclip.copy(improved)
                        logging.info("Clipboard updated with improved text.")
                        # self.notify("Clipboard Improved", "Text has been processed and updated.")
                        threading.Thread(target=self.notify_sound, daemon=True, name="NotifSound").start()
                    except KeyboardInterrupt:
                        break
                    except Exception as e:
                        logging.error(f"Error while monitoring clipboard:\n{e}")
                self.triggered = False
                time.sleep(0.5)

        return threading.Thread(
            target=monitor, 
            daemon=True,
            name="KeyboardMonitor"
            )
    
    def make_tray_icon(self):
        menu = Menu(
            MenuItem('Toggle Monitoring', self.toggle_monitor, checked=lambda item: self.monitoring_enabled),
            MenuItem('Toggle Notifications', self.toggle_notifications, checked=lambda item: self.notifications_enabled),
            MenuItem('Quit', self.stop_threads)
        )
        icon_image = Image.open(self.app_icon)
        return Icon("OCliP", icon=icon_image, menu=menu)

    def improve_text(self, clipboard_text):
        try:
            response = self.client.generate(
                model=self.model_name,
                prompt=clipboard_text,
                system=self.sys_prompt,
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
    

class OllamaNotFoundException(Exception):
    def __init__(self, *args):
        super().__init__(*args)


def resource_path(relative_path):
        base_path = Path(getattr(sys, '_MEIPASS', Path.cwd()))
        return base_path / relative_path

if __name__ == "__main__":

    default_model_name = "gemma3"
    default_sys_prompt = "Improve the following text without significantly changing the word count or meaning."

    parser = argparse.ArgumentParser()

    parser.add_argument('--model',
                    type=str,
                    required=False,
                    default=default_model_name,
                    help='Ollama model to run.')
    
    parser.add_argument('--sys-prompt', 
                        type=str, 
                        required=False, 
                        help='System prompt to use for model output.',
                        default=default_sys_prompt)
    
    parser.add_argument('--ollama-path', 
                        type=str, 
                        required=False, 
                        help='Path to Ollama executable. If undefined, the app will try to find it in your PATH.',
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