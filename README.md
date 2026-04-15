# Raspi Audiobook Player

Lokaler Tkinter-Player für den **Raspberry Pi (CM5)** — dunkles Cover-Grid, exakte Wiedergabeposition pro Buch (SQLite), MPV-Wiedergabe.

## Features

- **Cover-Grid** — Covers aus ID3/FLAC/MP4-Tags oder `cover.jpg`
- **Positionsspeicher** — Datei + genaue Sekunde pro Buch (SQLite, `~/.audiobook_player/`)
- **Bibliotheks-Scanner** — beliebiger Ordner; Unterordner = Bücher
- **MPV-Backend** — Hardware-Audio über `python-mpv`
- **Steuerung** — Play/Pause, ±15/30 s überspringen, Lautstärke, Kapitelsprung
- **Tastatur** — `Space` Play/Pause, `←` −15 s, `→` +30 s
- **Einstellungen** — Bibliothekspfad zur Laufzeit ändern

---

## Ordnerstruktur

```
~/Audiobooks/
├── Der Hobbit/
│   ├── cover.jpg          ← optional
│   ├── 01-kapitel.mp3
│   └── 02-kapitel.mp3
└── Harry Potter 1/
    └── harry_potter.m4b
```

Unterstützte Formate: `.mp3 .m4a .m4b .flac .ogg .aac .wav .opus`

---

## Installation (Raspberry Pi)

### 1. Systempakete

```bash
sudo apt update
sudo apt install -y mpv python3-pip python3-venv python3-tk python3-dbus python3-gi gir1.2-glib-2.0 bluez
# mpris-proxy einmalig starten (oder als systemd-Service)
mpris-proxy &
```

### 2. Python-Umgebung

```bash
cd /home/pi/raspi-audiobook
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
```

### 3. Starten

```bash
source venv/bin/activate
python3 app.py
```

---

## Autostart via systemd (mit Display)

```ini
# /etc/systemd/system/audiobook.service
[Unit]
Description=Audiobook Player
After=graphical-session.target

[Service]
User=pi
Environment=DISPLAY=:0
Environment=XAUTHORITY=/home/pi/.Xauthority
WorkingDirectory=/home/pi/raspi-audiobook
ExecStart=/home/pi/raspi-audiobook/venv/bin/python3 app.py
Restart=on-failure

[Install]
WantedBy=graphical-session.target
```

```bash
sudo systemctl enable audiobook
sudo systemctl start audiobook
```

---

## Konfiguration

Wird automatisch gespeichert in `~/.audiobook_player/config.json`:

```json
{
  "library_path": "/home/pi/Audiobooks"
}
```

Kann auch über den ⚙-Button in der App geändert werden.
