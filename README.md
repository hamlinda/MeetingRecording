# Meeting Recorder Application

A local meeting companion and voice intelligence tool. It features a modern **Vite/React frontend** and a **Python FastAPI backend** that records system loopback audio (Zoom, Teams, Discord, browser output) alongside microphone input, transcribes the voice content offline using `faster-whisper`, and generates structured summaries using local `Ollama` language models.

---

## 🏗️ Core Architecture & Implementation Details

The system is split into two primary layers: a web frontend and an API backend, sharing a modular file-based data pipeline:

```
MeetingRecording/
├── backend/               # FastAPI backend
│   ├── main.py            # API routes, app lifecycle, static file hosting
│   ├── recorder.py        # Audio capture engine (WASAPI loopback + mic)
│   ├── transcriber.py     # Offline Voice-to-Text via faster-whisper
│   ├── summarizer.py      # LLM integration via Ollama
│   ├── config.json        # Ollama URL, model, and prompt settings
│   └── recordings/        # Output directory for structured session data
├── frontend/              # React single-page app (Vite + CSS)
├── Launch.vbs             # Windows background startup script
├── build_native.bat       # Windows build automation script
└── docker-compose.yml     # Multi-container Docker configuration
```

### 1. Audio Capture Pipeline (`backend/recorder.py`)
- Uses `pyaudiowpatch` (a PyAudio fork) to hook into Windows WASAPI loopback devices.
- Spins up dual concurrent threads: one recording system loopback audio (what you hear) and another recording the microphone audio (what you speak).
- Combines the separate tracks, matching timestamps, and packages them. If `FFmpeg` is found in the system PATH, it multiplexes them into a single synced `.mp4` media file; otherwise, it falls back to saving separate raw `.wav` files.

### 2. File-Based Storage Architecture
Each session receives a UUID and stores its data under `backend/recordings/<UUID>/`:
- `metadata.json`: Logs session status (completed/error), timestamps, configuration settings, transcriptions, and summaries.
- `audio_system.wav`: Raw loopback audio (system output).
- `audio_mic.wav`: Raw microphone audio.
- `media_output.mp4` / `media_output.webm`: Combined session audio/video file.

### 3. AI Pipeline (`transcriber.py` & `summarizer.py`)
- **Transcription**: Uses `faster-whisper` (CTranslate2 port of OpenAI's Whisper) running locally. It generates high-accuracy, timetamped diarized segments.
- **Summarization & Title Suggestion**: Interacts with a local `Ollama` server. It diarizes speaker segments into clear transcripts and processes them against customizable markdown summary prompts (e.g. Action items, Key Decisions).

---

## 🎨 User Experience (UX) Designs

Depending on how the application is deployed, the design is experienced in two distinct ways:

### 💻 Standalone Desktop Experience (Windows native app mode)
This mode provides a seamless desktop integration without keeping command prompt windows open.

*   **Silent Background Startup (`Launch.vbs`)**: Double-clicking this script triggers WScript to start the FastAPI backend silently in the background using `pythonw.exe`.
*   **Single-Port Serving**: The backend automatically detects production execution (`sys.executable` ending with `pythonw.exe` or `PRODUCTION=1`) and hosts the pre-built React files directly on FastAPI port `8081`.
*   **Chromeless Chromium Window**: It launches Microsoft Edge in **Application Mode** (`msedge.exe --app=http://127.0.0.1:8081`). This spawns the interface in a dedicated window without browser navigation buttons, search bars, or tabs, mimicking a native desktop utility.
*   **Full Audio Loopback Capabilities**: In standalone mode, the app has direct access to the Windows WASAPI audio subsystems to capture loopback meetings.
*   **Shutdown hook**: Closing the Edge browser window stops the session, and the script terminates any background python processes.

### 🌐 Browser Web-App Experience (Dockerized / Multi-container)
This mode is designed for deployment on central servers or non-Windows hosts.

*   **Multi-Container Orchestration**: Runs the frontend (Vite/React dev or prod server) and FastAPI backend in separate isolated Docker containers routed through a Traefik proxy.
*   **Remote Management**: Users can host the app on a central server (e.g., home server/NAS) and access the interface remotely via any browser (`http://<server-ip>/meeting`).
*   **Container Limitations on Audio Capture**: Because Docker runs in Linux namespaces, the container cannot directly capture local Windows WASAPI loopback audio streams. This mode is used for note-taking (via microphone input pass-through), re-transcribing/summarizing previously recorded wav files, or central repository management.

---

## 🚀 Detailed Installation Instructions

### Prerequisites
- **Python 3.10 or higher**
- **Node.js 20+** & **npm** (for compiling the frontend)
- **FFmpeg** (added to system `PATH` to allow MP4 media muxing)
- **Ollama** (installed locally and running for summarization)

---

### 1. Standalone Desktop Mode (Windows)

1.  **Clone the Repository** and navigate to the `MeetingRecording` directory.
2.  **Build the Frontend Assets**:
    Run `build_native.bat` to automatically install npm packages and compile the React application to the static `frontend/dist/` directory.
    ```cmd
    build_native.bat
    ```
3.  **Set up the Python Virtual Environment**:
    Open a terminal in the `MeetingRecording` root and run:
    ```powershell
    cd backend
    python -m venv venv
    .\venv\Scripts\activate
    pip install -r requirements.txt
    ```
    *(Critical libraries: `fastapi`, `uvicorn`, `pyaudiowpatch`, `soundfile`, `numpy`, `faster-whisper`, `requests`, `av`)*
4.  **Launch the Desktop App**:
    Simply double-click the **`Launch.vbs`** file in the root folder.
    *This runs the FastAPI server headlessly and opens the application in Microsoft Edge app mode.*

---

### 2. Docker Web-App Mode (Linux / Servers)

1.  Navigate to the `MeetingRecording` root.
2.  Build and run the Docker containers:
    ```bash
    docker compose up --build
    ```
3.  Open `http://localhost/meeting` (or the configured routing port) in your web browser.
4.  Recorded sessions will mount to your local machine under `./backend/recordings`.

---

## 🎯 Use Cases

*   **Remote Work Meetings**: Capture high-fidelity audio from Zoom, Microsoft Teams, Slack, or Google Meet. Summarize actionable checklists and decisions instantly using local LLMs.
*   **Lectures & Presentations**: Record microphone audio in note-taking mode. Transcribe hours of lectures and let Ollama organize them into structured outline formats.
*   **Privacy-First Transcription**: Transcribe sensitive customer conversations locally. Since `faster-whisper` and `Ollama` run fully offline, no audio or text data is sent to external clouds (e.g. OpenAI).
*   **Meeting Vault**: Organise recordings under a single centralized server to search transcripts, review audio timelines, and re-run summarizations using updated LLM prompts.

---

## ⚙️ Critical Dependencies

| Dependency | Purpose | Mode |
| :--- | :--- | :---: |
| **pyaudiowpatch** | Accesses Windows WASAPI audio subsystem for speaker loopback capture | Standalone |
| **faster-whisper** | Core offline transcription engine (tiny/base models) | Both |
| **Ollama** | API client for local LLM text summarization and title generation | Both |
| **FFmpeg (System)** | Muxes dual audio tracks (system output + mic) into a single `.mp4` file | Both |
| **FastAPI / Uvicorn** | Serves REST API routes and hosts static frontend files in production | Both |
| **Vite & React** | Core single-page frontend user interface | Both |
| **WScript (Launch.vbs)** | Automates headless Python daemon execution and runs Edge in App mode | Standalone |
