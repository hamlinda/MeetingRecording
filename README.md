# Meeting Recorder Application

A local, privacy-first meeting companion and voice intelligence tool. It features a modern **Vite/React frontend** and a **Python FastAPI backend** that records system loopback audio (Zoom, Teams, Discord, browser output) alongside microphone input, transcribes the voice content offline using `faster-whisper`, and generates structured summaries using local `Ollama` language models.

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

### 2. File-Based Storage & Migration Architecture
Each session receives a UUID and stores its data under `backend/recordings/<UUID>/`:
- `metadata.json`: Logs session status (completed/error), timestamps, configuration settings, transcriptions, and summaries.
- `audio_system.wav`: Raw loopback audio (system output).
- `audio_mic.wav`: Raw microphone audio.
- `media_output.mp4` / `media_output.webm`: Combined session audio/video file.

#### Legacy Storage Migration
The backend automatically executes a migration routine on startup to normalize previous flat-file structures into standardized subdirectories. It converts legacy files from:
- `backend/recordings/<recording_id>_system.wav` ➔ `backend/recordings/<recording_id>/audio_system.wav`
- `backend/recordings/<recording_id>_mic.wav` ➔ `backend/recordings/<recording_id>/audio_mic.wav`
- `backend/recordings/<recording_id>.mp4` ➔ `backend/recordings/<recording_id>/media_output.mp4`
- `backend/recordings/<recording_id>.webm` ➔ `backend/recordings/<recording_id>/media_output.webm`
- `backend/recordings/<recording_id>.json` ➔ `backend/recordings/<recording_id>/metadata.json`

It also rewrites internal path references inside `metadata.json` to conform to relative directories.

### 3. AI Pipeline (`backend/transcriber.py` & `backend/summarizer.py`)
- **Transcription**: Uses `faster-whisper` (CTranslate2 port of OpenAI's Whisper) running locally. It generates high-accuracy, timestamped diarized segments. Runs on CPU by default with `int8` quantization for wide compatibility and efficient speed.
- **Diarization & Summarization**: Interacts with a local `Ollama` server. First, it diarizes speaker segments into a clean transcript by prompting the local LLM to replace generic `Meeting` tags with `Speaker 1`, `Speaker 2`, etc., keeping the configured system speaker name intact. Then it processes this transcript against customizable summary prompts to extract decisions, action points, and key topics.

---

## 🎨 User Experience (UX) Modes & Interaction Requirements

Depending on how the application is deployed, the design is experienced in two distinct ways:

### 💻 Standalone Desktop Experience (Windows native app mode)
This mode provides a seamless desktop integration without keeping command prompt windows open.
*   **Silent Background Startup (`Launch.vbs`)**: Double-clicking this script triggers WScript to start the FastAPI backend silently in the background using `pythonw.exe` on port `8081`. It terminates any old stuck backend processes beforehand.
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

## 🎯 Use Cases

*   **Remote Work Meetings**: Capture high-fidelity audio from Zoom, Microsoft Teams, Slack, or Google Meet. Summarize actionable checklists and decisions instantly using local LLMs.
*   **Lectures & Presentations**: Record microphone audio in note-taking mode. Transcribe hours of lectures and let Ollama organize them into structured outline formats.
*   **Privacy-First Transcription**: Transcribe sensitive customer conversations locally. Since `faster-whisper` and `Ollama` run fully offline, no audio or text data is sent to external clouds (e.g. OpenAI).
*   **Meeting Vault**: Organize recordings under a single centralized server to search transcripts, review audio timelines, and re-run summarizations using updated LLM prompts.

---

## ⚙️ Dependencies

### Frontend Dependencies (`frontend/package.json`)
*   **React (`^19.2.4`) & React-DOM (`^19.2.4`)**: Core application framework.
*   **React Markdown (`^10.1.0`)**: Renders transcribed segments and summaries in beautifully structured markdown.
*   **Vite (`^8.0.1`)**: Fast build system and dev server.
*   **ESLint (`^9.39.4`) & Plugins**: Code analysis and linting.

### Backend Python Packages (`backend/requirements.txt`)
*   **fastapi**: Web framework for building RESTful API endpoints.
*   **uvicorn**: ASGI server for running the FastAPI backend.
*   **faster-whisper**: CTranslate2 implementation of Whisper for fast, local CPU-bound transcription.
*   **pyaudiowpatch**: Cross-platform audio capture library that enables loopback recording on WASAPI.
*   **requests**: HTTP library for communicating with the local Ollama API server.
*   **pydantic**: Data validation and setting structures.

### System-Level Dependencies
*   **Python (3.10+)**
*   **Node.js (20+) & npm**
*   **FFmpeg**: Must be added to the system `PATH` to multiplex individual system and microphone WAV tracks into a single `.mp4` file.
*   **Ollama**: Must be running locally (default: `http://localhost:11434`) with the chosen language model pulled (e.g., `llama3.1`, `llama3.2`).
*   **PortAudio & GCC** (For Linux / Docker compilation of PyAudio bindings).

---

## 🚀 Detailed Installation Instructions

### Windows Standalone Desktop Mode
1.  **Clone the Repository** and navigate to the project directory.
2.  **Build the Frontend Assets**:
    Run the provided `build_native.bat` script. This installs npm packages and compiles the React application to the static `frontend/dist/` directory.
    ```cmd
    build_native.bat
    ```
3.  **Set up the Python Virtual Environment**:
    Create and activate a virtual environment, then install Python requirements:
    ```powershell
    cd backend
    python -m venv venv
    .\venv\Scripts\activate
    pip install -r requirements.txt
    ```
4.  **Launch the Desktop App**:
    Double-click the **`Launch.vbs`** file in the root folder.
    *This runs the FastAPI server headlessly and opens the application in Microsoft Edge app mode.*

### Docker Web-App Mode (Linux / Servers)
1.  Navigate to the `MeetingRecording` root.
2.  Build and run the Docker containers:
    ```bash
    docker compose up --build
    ```
3.  Open `http://localhost/meeting` in your web browser.
4.  Recorded sessions will mount to your local machine under `./backend/recordings`.

---

## 🔌 API Reference & Ruleset

All backend routes are prefixed under `/api`. Below is the complete API ruleset:

| Endpoint | Method | Input (Body / Query) | Output (JSON) | Description |
| :--- | :--- | :--- | :--- | :--- |
| `/api/config` | `GET` | *None* | `ConfigModel` | Fetches current config (`ollama_url`, `ollama_model`, `summary_prompt`, `system_speaker_name`). |
| `/api/config` | `POST` | `ConfigModel` (JSON) | `{"status": "success"}` | Saves new Ollama url, model, custom prompt, and speaker name. |
| `/api/recording/start` | `POST` | `{"record_mic": bool}` (JSON) | `{"status": "success", "recording_id": str}` | Initializes session UUID, updates status to "recording", and starts audio streams. |
| `/api/recording/stop` | `POST` | `video_data` (Optional Form Upload) | `{"status": "success", "recording_id": str}` | Stops recording, runs FFmpeg multiplexer, and spawns the background AI pipeline task. |
| `/api/recording/status` | `GET` | *None* | `{"is_recording": bool, "current_recording_id": str/null}` | Inspects if the recorder is active and returns the current active UUID. |
| `/api/recordings` | `GET` | *None* | `List[RecordingMetadata]` | Reads all directory metadata under `recordings/` and returns records sorted by timestamp. |
| `/api/recording/{rec_id}` | `DELETE` | Path Parameter: `rec_id` | `{"status": "success"}` | Deletes the folder containing all session wav files, mp4 video/audio, and metadata JSON. |
| `/api/recording/{rec_id}/rename` | `POST` | Path Parameter: `rec_id`<br>Body: `{"title": str}` (JSON) | `{"status": "success"}` | Updates the meeting's human-readable title inside its `metadata.json`. |
| `/api/recording/{rec_id}/suggest-title` | `POST` | Path Parameter: `rec_id` | `{"status": "success", "title": str}` | Calls Ollama to suggest a short title (max 5 words) based on the transcript and updates metadata. |
| `/api/recording/{rec_id}/reprocess` | `POST` | Path Parameter: `rec_id` | `{"status": "success"}` | Re-runs transcription and summarization asynchronously using current configs. |
| `/api/ai-check` | `GET` | *None* | `{"status": "online/offline", "url": str}` | Connects to the local Ollama server's `/api/tags` route to perform a connectivity health check. |
| `/api/ollama/models` | `GET` | Query Parameter: `url` | `{"status": "success/error", "models": List[str]}` | Contacts the specified Ollama server's `/v1/models` route to fetch all currently downloaded models. |

### API Processing Rules & Pipelines
1.  **Concurrency Rule**: Only one recording session can be active at a time. Trying to call `/api/recording/start` while a session is running yields a `400 Bad Request`.
2.  **Headless Handling**: Standard outputs are redirected (`sys.stdout`/`sys.stderr`) when launched using `pythonw.exe` to avoid system pipe crashes, logging errors to `backend/backend_error.log`.
3.  **Background Pipeline Executions**:
    - Transcription and summarization run as background tasks on the ASGI server so API calls return instantly without blocking the client.
    - If the user provides a video stream (`video_data` uploaded from the frontend screen-capture mechanism), the backend converts or bundles this video (`webm` or `mp4`) with loopback audio using `FFmpeg`.
    - If transcription fails, or Ollama is unresponsive, the session enters an `"error"` status state, storing the traceback in `error_detail` inside `metadata.json`. This can be resolved and triggered again using `/api/recording/{rec_id}/reprocess` without losing the original WAV files.
