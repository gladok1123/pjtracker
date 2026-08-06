# PJTracker

PJTracker is a desktop torrent search application that runs in the system tray. It serves as a front-end for Jackett, providing a modern web interface with search, sorting, category filters, tracker selection, priority tracker support, and detailed torrent information with posters.

## Requirements

- Windows 7 or later
- Jackett installed and running (default: http://127.0.0.1:9117)
- TorrServer (optional, for status checks)

## Installation

1. Download `PJTracker.exe` from the releases page.
2. Run the executable. The app will appear in the system tray.
3. Right-click the tray icon to open the menu.

## Features

- Search torrents through Jackett
- Filter by category (Movies, TV Series, Games, etc.)
- Select a tracker or set a priority tracker
- Sort results by name, year, size, seeds, or tracker
- View detailed information and poster art for each torrent
- Encrypted storage of your Jackett API key
- Automatic prevention of duplicate instances
- Built-in Discord community link

## Configuration

Settings are stored in `config.json`. You can change the Jackett URL, API key, and TorrServer URL via the tray menu.

## Support

Join the Discord server: https://discord.gg/vyFhePgxh

## Build 

python -m PyInstaller --onefile --windowed --add-data "templates;templates" --add-data "icons;icons" --icon "icons/favicon.ico" --name "PJTracker" pjtracker_tray.py

## Screenshots
<img width="1466" height="785" alt="Снимок экрана 2026-08-06 194123" src="https://github.com/user-attachments/assets/d3111762-9b50-4ab3-8650-68e50dec9649" />


