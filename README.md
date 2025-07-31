# OCliP
A simple app meant to improve the copied clipboard content by running it through an Ollama model

It's meant to skip the hassle of having to copy-paste content over twice when editing documents or emails.

## Features

 - Inbuilt notifications when the processing is done that works across different operating systems.
 - Includes flag options for custom Ollama models, Ollama path, system prompts.
 - Hotkeys to enable or disable features.

## Usage

**NOTE: This app uses Ollama to serve models. First step is to download [Ollama](www.ollama.com).**

### Recommended
The simplest approach is to download a prebuilt version from GitHub.

### Through Python
Or through Python:
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

**NOTE: This app needs administrator privileges to have the keyboard listeners and notifications to work properly.**

## License
[GPL-3.0-only](/COPYING)