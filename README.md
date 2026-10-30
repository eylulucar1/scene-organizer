# Scene Organizer

Scene Organizer is a Windows desktop application for automatically organizing downloaded video files into folders. It watches a source folder, such as the Downloads folder, and moves matching video files into destination folders based on configurable title keywords.

The application also supports organizing matched files by episode number and runs in the background with a system-tray icon.

## Features

- Watches the Downloads folder or another configured source folder
- Moves video files according to title keywords
- Supports common video formats such as MP4, MOV, MKV, AVI, WEBM, and M4V
- Optionally creates episode subfolders such as `Episode 1`, `Episode 2`, and so on
- Provides a graphical interface for adding or deleting rules
- Supports Turkish character normalization in file names
- Keeps running in the Windows system tray

## Requirements

- Windows
- Python 3.10 or newer

## Installation and setup

1. Clone the repository:

   ```bat
   git clone <repository-url>
   cd scene-organizer
   ```

2. Create and activate a virtual environment:

   ```bat
   python -m venv .venv
   .venv\Scripts\activate
   ```

3. Install the dependencies:

   ```bat
   python -m pip install -r requirements.txt
   ```

4. Start the application:

   ```bat
   python main.py
   ```

You can also use `baslat.bat` on Windows to start the program without showing a console window. Update the Python path in that file if it does not match your installation.

## Configuration

The application creates `config.json` automatically the first time it starts. The main settings are:

- `source_dir`: folder to watch, for example the Downloads folder
- `destination_dir`: root folder where organized videos will be moved
- `video_extensions`: file extensions considered by the organizer
- `organize_by_episode`: whether files should be placed in episode subfolders
- `rules`: folder names and filename keywords used to match videos

Example rule:

```json
{
  "folder_name": "Example Series",
  "keywords": ["example series", "es"]
}
```

You can also add and remove rules from the application interface. Changes are saved to `config.json`.

## Running in the background

Closing the application window minimizes it to the system tray. Use the tray icon to reopen the interface, run a scan immediately, or exit the application.

## Dependencies

- watchdog: monitors folder changes
- pystray: provides the Windows system-tray icon
- Pillow: creates the tray icon image
