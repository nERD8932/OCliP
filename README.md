# OCliP
A simple app meant to improve the copied clipboard content by running it through an Ollama model

It's meant to skip the hassle of having to copy-paste content over twice when editing documents or emails.

## Features

 - Inbuilt notifications for state toggles.
 - Includes flag and config options for custom Ollama models, system prompts and hot keys.
 - Tray icon for quick access.

## Usage

### Recommended
The simplest approach is to download a prebuilt version from GitHub.

### Through Python
 - Clone the repository
 - Open a terminal inside the repository folder
 - Install the dependancies with 
    ```
    python -m venv .venv
    pip install -r requirements.txt
    ```
 - Run 
    ```
    ./.venv/Scripts/activate
    python impclip.py
    ```
 - Or build a standalone executable with
    ```
    pip install pyinstaller
    pyinstaller OCliP.spec
   # The generated EXE will be in the dist folder. A first-time build may take a few minutes.
    ```

**NOTE: This app uses Ollama to serve models. If you don't already have it installed, the app will ask and download it for you.**

**NOTE: This app needs administrator privileges to have the keyboard listeners and notifications to work properly.**

## License
[GPL-3.0-only](/COPYING)