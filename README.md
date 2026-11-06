# 🎵 BitChord Qobuz Source Addon

> **High-Quality Lossless & Hi-Res (up to 24-bit / 192 kHz) FLAC Streaming Source for [BitChord App](https://github.com/kushagrasinghx/BitChord), powered by [qobuz-dl](https://github.com/vitiko98/qobuz-dl).**

---

## 📖 Overview

**BitChord** is a modern, open-source Android music client (featuring an Apple Music-inspired interface) with a pluggable **Module Sources & Addon Protocol**.

This project bridges **Qobuz's** audiophile-grade Lossless and Hi-Res catalog directly into BitChord. Built upon the core API mechanics, bundle scraping, and request signing from [vitiko98/qobuz-dl](https://github.com/vitiko98/qobuz-dl), this addon allows BitChord to stream studio-quality **FLAC** directly from the very first note.

### ✨ Highlights

* **True Hi-Res FLAC Streaming**: Stream up to **24-bit / 192 kHz** Studio Masters and **16-bit / 44.1 kHz** CD-Quality FLAC.
* **BitChord Addon Protocol Compliant**: Exposes `GET /manifest.json`, `GET /search?q=...`, and `GET /stream/{id}` matching BitChord's strict wire format.
* **Direct Source Stream**: Plays directly from the addon without mid-song quality drops or buffering delays.
* **Low-Latency Audio Proxy**: Built-in HTTP Range (`206 Partial Content`) proxy ensuring smooth track seeking and scrubber jumping in BitChord's ExoPlayer.
* **Web Setup & Audition Dashboard**: Includes a sleek Apple Music / BitChord-themed web UI (`/setup`) to configure tokens, test catalog search, and preview FLAC streams right in your browser.
* **Auto-Credential Scraper**: Dynamically extracts `app_id` and request signing secrets from Qobuz's web player bundle (with built-in reliable fallbacks).
* **Zero Dependencies**: Core server runs on Python 3 standard library (`http.server`, `urllib`, `hashlib`) without requiring heavy packages.
* **Self-Hosting Ready**: Includes `Dockerfile` and `docker-compose.yml` for 1-click container deployment.

---

## 🚀 Quick Start

### Option 1: Native Python (macOS / Linux / Windows)

No external libraries required! Just clone and run with Python 3.9+:

```bash
# Clone the repository
git clone https://github.com/your-username/bitchord-qobuz-addon.git
cd bitchord-qobuz-addon

# Run the server
./run.sh
# or
python3 server.py
```

The server will display your local IP and connection links:
```text
================================================================
  🎵 BitChord Qobuz Source Addon (High Quality FLAC Streaming)
================================================================
  • Local Dashboard:     http://localhost:8080/setup
  • Network Dashboard:   http://192.168.1.50:8080/setup
  • BitChord Source URL: http://192.168.1.50:8080/manifest.json
----------------------------------------------------------------
  • Max Format Quality:  27 (24b/192k FLAC)
  • Ready for BitChord! Press Ctrl+C to stop.
```

### Option 2: Docker Compose

```bash
docker compose up -d
```

Access the setup panel at `http://<your-server-ip>:8080/setup`.

---

## 📱 Connecting to BitChord App

1. Ensure your Android phone running BitChord is connected to the same Wi-Fi network (or your server is reachable over LAN / reverse proxy / Cloudflare Tunnel).
2. Open **BitChord** on your device.
3. Tap the **Settings** icon (gear) → **Sources**.
4. Tap **Add Module Source** (or **+**).
5. Enter your Manifest link:
   ```text
   http://<YOUR_LOCAL_IP>:8080/manifest.json
   ```
6. Tap **Add / Verify**.
7. In the Sources list, **drag Qobuz FLAC to the top** so that BitChord prioritizes your high-res FLAC source for all playback.

---

## 🖥️ Web Setup Dashboard (`/setup`)

Open `http://localhost:8080/setup` in your browser to access the management interface:

* **One-Click Link Copying**: Copy your LAN Manifest or Root URL for BitChord with a single click.
* **Qobuz Authentication**:
  * **Login with Email & Password**: Automatically retrieves your `user_auth_token`.
  * **Manual Token Entry**: Paste your token extracted from the Qobuz web player (`play.qobuz.com`).
  * *Note: Even without a paid subscription, searches work and 30-second full-quality FLAC previews can be streamed for testing.*
* **Quality Selector**:
  * `24-bit / 192 kHz FLAC` (Format `27` — Studio Master)
  * `24-bit / 96 kHz FLAC` (Format `7` — Hi-Res)
  * `16-bit / 44.1 kHz FLAC` (Format `6` — CD Lossless)
  * `320 kbps MP3` (Format `5` — Standard)
* **Audition & Search Tester**: Test any song, view album artwork and audio bit depth/sample rate, and play the FLAC stream directly with seeking support.

---

## 📡 API Endpoints (BitChord Addon Protocol)

| Route | Method | Description |
| :--- | :---: | :--- |
| `/manifest.json` | `GET` | Addon discovery manifest declaring identity, capabilities, and resources. |
| `/search?q={query}` | `GET` | Searches Qobuz catalog and returns matching tracks in BitChord format. |
| `/stream/{id}` | `GET` | Resolves track ID into stream descriptor JSON or direct audio stream. |
| `/audio/{id}.flac` | `GET`, `HEAD`| Audio proxy endpoint with HTTP `206 Partial Content` Range seeking. |
| `/health` | `GET` | Health check endpoint for uptime verification. |
| `/setup` | `GET` | Browser-based setup and testing dashboard. |

### Manifest Example (`GET /manifest.json`)

```json
{
  "id": "org.bitchord.addon.qobuz",
  "name": "Qobuz FLAC",
  "version": "1.0.0",
  "description": "High Quality Lossless & Hi-Res FLAC Streaming Source for BitChord powered by Qobuz",
  "icon": "http://192.168.1.50:8080/static/icon.svg",
  "resources": [
    "search",
    "stream"
  ],
  "types": [
    "music"
  ],
  "formats": [
    "flac"
  ],
  "qualities": [
    "HI_RES",
    "LOSSLESS",
    "24B_192K",
    "24B_96K",
    "16B_44K"
  ]
}
```

### Search Response Example (`GET /search?q=Daft+Punk+Get+Lucky`)

```json
{
  "tracks": [
    {
      "id": "18491294",
      "title": "Get Lucky (Radio Edit)",
      "artist": "Daft Punk feat. Pharrell Williams",
      "album": "Random Access Memories",
      "duration": 248,
      "artworkURL": "https://static.qobuz.com/images/covers/...",
      "format": "flac",
      "audioQuality": "HI_RES",
      "bitDepth": 24,
      "sampleRate": 88200,
      "streamURL": "http://192.168.1.50:8080/stream/18491294"
    }
  ]
}
```

---

## ⚙️ Configuration & Environment Variables

You can configure the server using CLI arguments, environment variables, or the Web UI:

| Variable | CLI Flag | Default | Description |
| :--- | :--- | :--- | :--- |
| `BITCHORD_PORT` | `--port` | `8080` | Port to bind the HTTP server. |
| `BITCHORD_HOST` | `--host` | `0.0.0.0` | Host interface to listen on. |
| `QOBUZ_USER_TOKEN` | `--token` | `""` | Qobuz user authentication token. |
| `QOBUZ_QUALITY` | `--quality` | `27` | Maximum streaming format (`27`, `7`, `6`, `5`). |
| `QOBUZ_APP_ID` | `--app-id` | `""` | Custom Qobuz App ID (auto-scraped if omitted). |
| `QOBUZ_APP_SECRET`| `--app-secret` | `""` | Custom Qobuz App Secret for MD5 signatures. |
| `BITCHORD_CONFIG` | `--config` | `config.json` | Path to persistent JSON configuration file. |

---

## 🧪 Testing

Run the automated test suite:

```bash
python3 -m unittest discover tests
```

---

## 🔒 Reverse Proxy & HTTPS Note

If accessing BitChord remotely or outside your home Wi-Fi network:
* Configure a reverse proxy (e.g. **Caddy**, **Nginx**, or **Cloudflare Tunnel**) with HTTPS.
* Ensure response buffering is disabled in your reverse proxy for chunked streaming:
  ```nginx
  proxy_buffering off;
  proxy_request_buffering off;
  ```

---

## 📜 Credits & License

* Reverse engineering & Qobuz API logic based on **[vitiko98/qobuz-dl](https://github.com/vitiko98/qobuz-dl)**.
* Designed for **[BitChord](https://github.com/kushagrasinghx/BitChord)** by Kushagra Singh.
* Licensed under the GNU General Public License v3.0 (GPLv3).

