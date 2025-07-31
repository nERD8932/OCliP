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


class ImproveClipboard:

    client = None
    ollama_started = False
    ollama_path = shutil.which("ollama")
    monitoring_enabled = True
    triggered = False
    stop_event = threading.Event()
    notifications_enabled = True

    def __init__(self, model_name, sys_prompt, ollama_path, force_path):
        signal.signal(signal.SIGINT, self.signal_handler)
        signal.signal(signal.SIGTERM, self.signal_handler)
        self.setLogger()

        self.model_name = model_name
        self.sys_prompt = sys_prompt + "\nOutput only the requested text and nothing, this is extremely important."
        self.force_path = force_path

        try:
            self.checkForOllama(ollama_path)
            self.initOllama()
        except OllamaNotFoundException as e:
            logging.critical(f"Error while checking for Ollama. Are you sure it's installed?\n{e}")
            sys.exit(-1)
        except Exception as e:
            logging.critical(f"Error initializing Ollama client!\n{e}")
            self.killOllama()
            sys.exit(-1)
        
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
        self.stop_event.set()
        if self.thread.is_alive():
            self.thread.join()
        self.killOllama()
        sys.exit(0)
    
    def killOllama(self):
        if platform.system() == "Windows":
            subprocess.run(['taskkill', '/F', '/IM', 'ollama.exe'])
        else:
            subprocess.run(['pkill', '-f', 'ollama'])

    def setLogger(self):
        logging.basicConfig(
        level=logging.INFO,
        format="[%(asctime)s] [%(levelname)s] %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S"
    )
    
    def setup_hotkey(self):
        def toggle_monitor():
            self.monitoring_enabled = not self.monitoring_enabled
            state = "enabled" if self.monitoring_enabled else "disabled"
            logging.info(f"Clipboard monitoring {state}.")
            self.notify("Clipboard Monitor", f"Monitoring {state}.")

        def toggle_trigger():
            if not self.triggered and self.monitoring_enabled:
                self.triggered = True
                logging.info(f"Clipboard updated triggered.")
                self.notify("Improving...", "Running clipboard improvement...")

        def toggle_notifications():
            self.notifications_enabled = not self.notifications_enabled

        keyboard.add_hotkey('ctrl+shift+c', toggle_monitor)
        keyboard.add_hotkey('ctrl+c', toggle_trigger)
        keyboard.add_hotkey('ctrl+n', toggle_notifications)

    def initOllama(self):
        try:

            if not self.ollama_started:
                subprocess.Popen(['ollama', 'serve'],
                                 stdout=subprocess.DEVNULL,
                                 stderr=subprocess.DEVNULL,)

            self.client = ollama.Client()

            if self.model_name not in self.client.list():
                t = threading.Thread(target=self.pull_model, daemon=True)
                t.start()
                print()
                prefix = "Pulling Ollama model"
                while(t.is_alive()):
                    p = f"."
                    logging.info("\r" + prefix + p )
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
                        self.notify("Clipboard Improved", "Text has been processed and updated.")
                    except KeyboardInterrupt:
                        break
                    except Exception as e:
                        logging.error(f"Error while monitoring clipboard: {e}")
                self.triggered = False
                time.sleep(0.5)

        return threading.Thread(target=monitor, daemon=True)

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
            logging.error(f"Text improvement failed: {e}")
            return clipboard_text
    
    def notify(self, title, message):
        if self.notifications_enabled:
            try:
                notification.notify(
                    title=title,
                    message=message,
                    timeout=0.5
                    name="OCiP"
                    icon="./icon.ico"
                )
            except Exception as e:
                logging.warning(f"Notification failed: {e}")

class OllamaNotFoundException(Exception):
    def __init__(self, *args):
        super().__init__(*args)

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
    
    impClip = ImproveClipboard(args.model, args.sys_prompt, args.ollama_path, args.force_path)
    try:
        while impClip.thread.is_alive():
            time.sleep(5)
    except KeyboardInterrupt:
        impClip.signal_handler(signal.SIGINT, None)