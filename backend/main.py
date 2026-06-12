import sys
import os
import platform
import logging

# Fix for pythonw.exe where standard streams are None
if sys.stdout is None:
    sys.stdout = open(os.devnull, "w")
if sys.stderr is None:
    sys.stderr = open(os.path.join(os.path.dirname(os.path.abspath(__file__)), "backend_error.log"), "a")

# Configure basic logging
logging.basicConfig(level=logging.INFO, stream=sys.stderr)

from fastapi import FastAPI, BackgroundTasks, HTTPException, File, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel
from fastapi.responses import FileResponse
import zipfile
import shutil
import uuid
import traceback
import json
import requests
from datetime import datetime
from typing import List, Optional

# Local imports
from recorder import AudioRecorder
from transcriber import AudioTranscriber
from summarizer import ContentSummarizer

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

app = FastAPI(title="Meeting Recorder backend")

# Config custom port on frontend usually runs at Vite default, but we don't know it yet. Enable all.
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Global State
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
RECORDINGS_DIR = os.path.join(BASE_DIR, "recordings")
CONFIG_FILE = os.path.join(BASE_DIR, "config.json")
os.makedirs(RECORDINGS_DIR, exist_ok=True)

def get_rec_dir(rec_id: str):
    return os.path.join(RECORDINGS_DIR, rec_id)

def get_metadata_path(rec_id: str):
    return os.path.join(get_rec_dir(rec_id), "metadata.json")

def migrate_storage():
    """Migrate legacy flat files into the new subfolder structure."""
    if not os.path.exists(RECORDINGS_DIR):
        return
        
    for f in os.listdir(RECORDINGS_DIR):
        if f.endswith('.json') and f != 'metadata.json':
            rec_id = f.replace('.json', '')
            rec_dir = get_rec_dir(rec_id)
            os.makedirs(rec_dir, exist_ok=True)
            
            # Move JSON
            old_json = os.path.join(RECORDINGS_DIR, f)
            new_json = get_metadata_path(rec_id)
            if not os.path.exists(new_json):
                shutil.move(old_json, new_json)
                logger.info(f"Migrated {f} to {rec_id}/metadata.json")
            
            # Move other associated files
            for associated in os.listdir(RECORDINGS_DIR):
                if associated.startswith(rec_id) and associated != f:
                    old_path = os.path.join(RECORDINGS_DIR, associated)
                    # Check if it's a file (not the newly created directory)
                    if os.path.isfile(old_path):
                        # Determine new name (e.g., b2379..._mic.wav -> audio_mic.wav)
                        new_name = associated
                        if "_mic.wav" in associated: new_name = "audio_mic.wav"
                        elif "_system.wav" in associated: new_name = "audio_system.wav"
                        elif associated.endswith(".mp4"): new_name = "media_output.mp4"
                        elif associated.endswith(".webm"): new_name = "media_output.webm"
                        
                        new_path = os.path.join(rec_dir, new_name)
                        if not os.path.exists(new_path):
                            shutil.move(old_path, new_path)
                            logger.info(f"Migrated {associated} to {rec_id}/{new_name}")
            
            # Update migrated JSON with new internal paths
            try:
                with open(new_json, 'r') as f_in:
                    data = json.load(f_in)
                
                changed = False
                if 'media_path' in data:
                    ext = ".mp4" if data['media_path'].endswith(".mp4") else ".webm"
                    new_media_rel = os.path.join(rec_id, f"media_output{ext}")
                    if data['media_path'] != new_media_rel:
                        data['media_path'] = new_media_rel
                        changed = True
                
                if 'wav_files' in data:
                    # Update to new standardized names
                    data['wav_files'] = {
                        "loopback": os.path.join(rec_id, "audio_system.wav"),
                        "mic": os.path.join(rec_id, "audio_mic.wav")
                    }
                    changed = True
                
                if changed:
                    with open(new_json, 'w') as f_out:
                        json.dump(data, f_out)
                    logger.info(f"Updated metadata.json for {rec_id} with new paths")
            except Exception as e:
                logger.error(f"Failed to update migrated JSON for {rec_id}: {e}")

# Run migration
migrate_storage()

# App State

class AppState:
    def __init__(self):
        self.recorder = AudioRecorder()
        self.transcriber = None 
        self.current_recording_id = None
        
state = AppState()

# Load/Save Config
def load_config():
    default_prompt = "Provide a comprehensive summary of the meeting. Focus on:\n- Key Topics discussed\n- Decisions made\n- Action points (formatted as a bold checklist)"
    if os.path.exists(CONFIG_FILE):
        with open(CONFIG_FILE, 'r') as f:
            data = json.load(f)
            if "summary_prompt" not in data:
                data["summary_prompt"] = default_prompt
            if "system_speaker_name" not in data:
                data["system_speaker_name"] = "Me"
            return data
    return {"ollama_url": "http://localhost:11434", "ollama_model": "llama3.1", "summary_prompt": default_prompt, "system_speaker_name": "Me"}

def save_config(config_data):
    with open(CONFIG_FILE, 'w') as f:
        json.dump(config_data, f)
        
class ConfigModel(BaseModel):
    ollama_url: str
    ollama_model: str
    summary_prompt: Optional[str] = "Please summarize the following meeting transcript. Highlight key decisions and action items."
    system_speaker_name: Optional[str] = "Me"

class RecordingRecord(BaseModel):
    id: str
    status: str
    transcription: Optional[str] = None
    summary: Optional[str] = None
    media_path: Optional[str] = None

# We store meeting results in JSON files
def get_recording_info(rec_id: str):
    path = get_metadata_path(rec_id)
    if os.path.exists(path):
        with open(path, 'r') as f:
            return json.load(f)
    return None

def update_recording_info(rec_id: str, data: dict):
    os.makedirs(get_rec_dir(rec_id), exist_ok=True)
    path = get_metadata_path(rec_id)
    # Load existing if exists
    existing = get_recording_info(rec_id) or {}
    existing.update(data)
    with open(path, 'w') as f:
        json.dump(existing, f)

# Background pipeline task
def process_recording(rec_id: str, wavs: dict, media_path: str, video_path: str = None):
    logger.info(f"Starting processing for {rec_id}...")
    try:
        update_recording_info(rec_id, {"status": "loading AI transcription engine", "error_detail": None})
        if state.transcriber is None:
            logger.info("Initializing AudioTranscriber...")
            state.transcriber = AudioTranscriber(model_size="tiny")
            
        update_recording_info(rec_id, {"status": "transcribing"})
        t_transcription_start = datetime.now().isoformat()
        
        config = load_config()
        system_speaker = config.get("system_speaker_name", "Me")
        
        all_segments = []
        
        loop_wav = wavs.get("loopback")
        loop_segs = []
        if loop_wav and os.path.exists(loop_wav):
            logger.info(f"Transcribing loopback audio: {loop_wav}")
            loop_segs = state.transcriber.transcribe(loop_wav)
            for s in loop_segs:
                all_segments.append({"start": s.get("start", 0), "text": s.get("text", ""), "speaker": "Meeting"})
                
        mic_wav = wavs.get("mic")
        if mic_wav and os.path.exists(mic_wav):
            logger.info(f"Transcribing microphone audio: {mic_wav}")
            mic_segs = state.transcriber.transcribe(mic_wav)
            for s in mic_segs:
                all_segments.append({"start": s.get("start", 0), "text": s.get("text", ""), "speaker": system_speaker})
                
        t_transcription_end = datetime.now().isoformat()
        all_segments.sort(key=lambda x: x["start"])
        
        record_type = "Meeting" if len(loop_segs) > 0 else "Note Taking"
        
        unified_transcript = ""
        current_speaker = None
        for s in all_segments:
            start_time = s.get("start", 0)
            minutes = int(start_time // 60)
            seconds = int(start_time % 60)
            timestamp = f"[{minutes:02d}:{seconds:02d}]"
            
            if s["speaker"] != current_speaker:
                unified_transcript += f"\n\n{timestamp} **{s['speaker']}**: {s['text']}"
                current_speaker = s["speaker"]
            else:
                unified_transcript += f" {s['text']}"
                
        unified_transcript = unified_transcript.strip()
        if not unified_transcript:
            unified_transcript = "No audio detected."
            
        update_recording_info(rec_id, {"transcription": unified_transcript, "status": "LLM restructuring..."})
        
        # Instantiate summarizer and rewrite transcript
        logger.info(f"Connecting to Ollama at {config['ollama_url']}...")
        summarizer = ContentSummarizer(ollama_url=config["ollama_url"], model=config["ollama_model"])
        if record_type == "Meeting":
            logger.info("Diarizing external speakers")
            unified_transcript = summarizer.diarize(unified_transcript, system_speaker)
            
        update_recording_info(rec_id, {"transcription": unified_transcript, "status": "summarizing"})
        
        t_summary_start = datetime.now().isoformat()
        summary_prompt = config.get("summary_prompt", "Summarize the following meeting transcript.")
        summary = summarizer.summarize(unified_transcript, custom_prompt=summary_prompt)
        t_summary_end = datetime.now().isoformat()
        
        # NOTE: We no longer delete .wav files here to allow re-processing.
        # Temp video files (webm) should still be cleaned up if converted to mp4.
        try:
            if video_path and os.path.exists(video_path) and video_path != media_path:
                os.remove(video_path)
        except Exception as e:
            logger.error(f"Could not remove temp video file: {e}")
                
        update_recording_info(rec_id, {
            "summary": summary, 
            "status": "completed",
            "record_type": record_type,
            "transcription_model": "faster-whisper: tiny",
            "transcription_start": t_transcription_start,
            "transcription_end": t_transcription_end,
            "summarization_model": f"ollama: {config['ollama_model']}",
            "summarization_start": t_summary_start,
            "summarization_end": t_summary_end,
            "summary_prompt_used": summary_prompt,
            "wav_files": wavs,
            "media_path": media_path
        })
        logger.info(f"Completed processing for {rec_id}.")

    except Exception as e:
        err_msg = str(e)
        stack = traceback.format_exc()
        logger.error(f"Error in pipeline for {rec_id}: {err_msg}\n{stack}")
        update_recording_info(rec_id, {
            "status": "error",
            "error_detail": f"{err_msg}\n\nTraceback:\n{stack[-1000:]}"
        })


@app.get("/api/config")
def get_config():
    return load_config()

@app.post("/api/config")
def set_config(config: ConfigModel):
    save_config(config.dict())
    return {"status": "success"}

class StartRecordingRequest(BaseModel):
    record_mic: bool = True

@app.post("/api/recording/start")
def start_recording(req: StartRecordingRequest):
    if state.recorder.is_recording:
        raise HTTPException(status_code=400, detail="Already recording.")
        
    state.current_recording_id = str(uuid.uuid4())
    logger.info(f"Starting recording session: {state.current_recording_id} (Mic: {req.record_mic})")
    
    update_recording_info(state.current_recording_id, {
        "id": state.current_recording_id,
        "title": "Untitled Meeting",
        "start_time": datetime.now().isoformat(),
        "status": "recording"
    })
    
    try:
        state.recorder.start(record_mic=req.record_mic)
        return {"status": "success", "recording_id": state.current_recording_id}
    except Exception as e:
        logger.error(f"Failed to start recording: {e}")
        raise HTTPException(status_code=500, detail=str(e))

class RenameRequest(BaseModel):
    title: str

@app.delete("/api/recording/{rec_id}")
def delete_recording(rec_id: str):
    rec_dir = get_rec_dir(rec_id)
    if os.path.exists(rec_dir):
        try:
            shutil.rmtree(rec_dir)
            return {"status": "success"}
        except Exception as e:
            logger.error(f"Failed to delete directory {rec_dir}: {e}")
            raise HTTPException(status_code=500, detail=str(e))
    
    raise HTTPException(status_code=404, detail="Not found")

@app.post("/api/recording/{rec_id}/rename")
def rename_recording(rec_id: str, req: RenameRequest):
    if not get_recording_info(rec_id):
        raise HTTPException(status_code=404, detail="Not found")
    update_recording_info(rec_id, {"title": req.title})
    return {"status": "success"}

@app.post("/api/recording/{rec_id}/suggest-title")
def suggest_title(rec_id: str):
    info = get_recording_info(rec_id)
    if not info:
        raise HTTPException(status_code=404, detail="Not found")
        
    transcript = info.get("transcription")
    if not transcript or transcript == "No audio detected.":
        raise HTTPException(status_code=400, detail="No transcript available to summarize.")
        
    config = load_config()
    
    # Construct an explicitly brief prompt
    prompt = f"Come up with a very short title (maximum 5 words) that summarizes the main topic of this transcript. Respond ONLY with the title itself, without any punctuation or quotes.\n\nTranscript:\n{transcript}"
    
    try:
        url = config["ollama_url"]
        if url.endswith("/"): url = url[:-1]
        
        response = requests.post(f"{url}/api/generate", json={
            "model": config["ollama_model"],
            "prompt": prompt,
            "stream": False
        }, timeout=60)
        
        response.raise_for_status()
        data = response.json()
        title = data.get("response", "").strip().strip('"').strip('*')
        
        update_recording_info(rec_id, {"title": title})
        return {"status": "success", "title": title}
    except Exception as e:
        logger.error(f"Error calling ollama for title: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/api/recording/{rec_id}/reprocess")
def reprocess_recording(rec_id: str, background_tasks: BackgroundTasks):
    info = get_recording_info(rec_id)
    if not info:
        raise HTTPException(status_code=404, detail="Recording not found")
    
    rec_dir = get_rec_dir(rec_id)
    wavs = info.get("wav_files")
    if not wavs:
        # Fallback: Try to find files by naming convention within the subfolder
        system_wav = os.path.join(rec_dir, "audio_system.wav")
        mic_wav = os.path.join(rec_dir, "audio_mic.wav")
        # Legacy fallback
        old_system_wav = os.path.join(rec_dir, f"{rec_id}_system.wav")
        old_mic_wav = os.path.join(rec_dir, f"{rec_id}_mic.wav")
        
        wavs = {}
        if os.path.exists(system_wav): wavs["loopback"] = system_wav
        elif os.path.exists(old_system_wav): wavs["loopback"] = old_system_wav
            
        if os.path.exists(mic_wav): wavs["mic"] = mic_wav
        elif os.path.exists(old_mic_wav): wavs["mic"] = old_mic_wav
    
    if not wavs:
        raise HTTPException(status_code=400, detail="Original audio files not found for this recording.")
    
    # Check if files actually exist
    found_wavs = {}
    missing = []
    for k, v in wavs.items():
        if v:
            # Handle both absolute and relative paths
            abs_v = v if os.path.isabs(v) else os.path.join(os.getcwd(), v)
            if os.path.exists(abs_v):
                found_wavs[k] = v
            else:
                # Try relative to the rec_dir if the stored path is just the filename
                alt_v = os.path.join(rec_dir, os.path.basename(v))
                if os.path.exists(alt_v):
                    found_wavs[k] = alt_v
                else:
                    missing.append(k)
    
    if not found_wavs:
        raise HTTPException(status_code=400, detail=f"Required audio files missing: {', '.join(missing)}")

    # Update metadata_path for processed media (media_output.mp4)
    media_path = os.path.join(rec_dir, "media_output.mp4")
    if not os.path.exists(media_path):
        # check webm
        webm_path = os.path.join(rec_dir, "media_output.webm")
        if os.path.exists(webm_path): media_path = webm_path
    
    update_recording_info(rec_id, {
        "status": "re-processing",
        "error_detail": None,
        "wav_files": found_wavs,
        "media_path": media_path
    })
    
    background_tasks.add_task(process_recording, rec_id, found_wavs, media_path)
    return {"status": "success"}

@app.post("/api/recording/stop")
def stop_recording(background_tasks: BackgroundTasks, video_data: Optional[UploadFile] = File(None)):
    if not state.recorder.is_recording:
        raise HTTPException(status_code=400, detail="Not currently recording.")
        
    rec_id = state.current_recording_id
    rec_dir = get_rec_dir(rec_id)
    os.makedirs(rec_dir, exist_ok=True)
    
    video_path = None
    output_media = os.path.join(rec_dir, "media_output.mp4")
    
    if video_data and video_data.filename:
        video_path = os.path.join(rec_dir, "media_output.webm")
        with open(video_path, "wb") as buffer:
            shutil.copyfileobj(video_data.file, buffer)
        output_media = video_path # WebM is the output if video is present
    
    logger.info(f"Stopping recording session: {rec_id}")
    
    update_recording_info(rec_id, {
        "status": "processing",
        "end_time": datetime.now().isoformat()
    })
    
    wavs, final_media = state.recorder.stop(output_media, video_path)
    update_recording_info(rec_id, {"media_path": final_media, "wav_files": wavs})
    
    state.current_recording_id = None
    
    background_tasks.add_task(process_recording, rec_id, wavs, final_media, video_path)
    
    return {"status": "success", "recording_id": rec_id}

@app.get("/api/recording/status")
def get_status():
    return {
        "is_recording": state.recorder.is_recording,
        "current_recording_id": state.current_recording_id,
        "audio_recording_available": state.recorder.p is not None
    }

@app.get("/api/recordings")
def list_recordings():
    results = []
    if os.path.exists(RECORDINGS_DIR):
        for rec_id in os.listdir(RECORDINGS_DIR):
            rec_dir = os.path.join(RECORDINGS_DIR, rec_id)
            if os.path.isdir(rec_dir):
                metadata_path = os.path.join(rec_dir, "metadata.json")
                if os.path.exists(metadata_path):
                    try:
                        with open(metadata_path, 'r') as file:
                            data = json.load(file)
                            data['id'] = data.get('id') or rec_id
                            results.append(data)
                    except Exception as e:
                        logger.error(f"Failed to read metadata for {rec_id}: {e}")
                    
    return results

@app.get("/api/ai-check")
def check_ai_status():
    """Verify if the configured AI services are responsive."""
    config = load_config()
    url = config.get("ollama_url", "").strip()
    if not url:
        return {"status": "offline", "detail": "No URL configured"}
    
    if not url.startswith("http"):
        url = f"http://{url}"
        
    try:
        # Check basic connectivity to the Ollama server
        response = requests.get(f"{url}/api/tags", timeout=3)
        if response.status_code == 200:
            return {"status": "online", "url": url}
    except Exception:
        pass
    
    return {"status": "offline", "url": url}

@app.get("/api/ollama/models")
def get_ollama_models(url: str):
    """Fetch available models from the specified Ollama server."""
    try:
        url = url.strip()
        if not url.startswith("http"):
            url = f"http://{url}"
            
        if url.endswith("/"):
            url = url[:-1]
            
        full_url = url if url.endswith("v1/models") else f"{url}/v1/models"
            
        response = requests.get(full_url, timeout=10)
        response.raise_for_status()
        data = response.json()
        models = [m.get("id") for m in data.get("data", [])]
        return {"status": "success", "models": models}
    except Exception as e:
        return {"status": "error", "detail": str(e), "models": []}

@app.get("/api/download/windows-standalone")
def download_windows_standalone(background_tasks: BackgroundTasks):
    """Bundle the application files into a ZIP for local Windows execution."""
    temp_dir = os.path.join(RECORDINGS_DIR, "tmp_downloads")
    os.makedirs(temp_dir, exist_ok=True)
    zip_filename = f"meeting_recorder_windows_{uuid.uuid4().hex[:8]}.zip"
    zip_path = os.path.join(temp_dir, zip_filename)
    
    root_dir = os.path.abspath(os.path.join(BASE_DIR, ".."))
    
    try:
        with zipfile.ZipFile(zip_path, 'w', zipfile.ZIP_DEFLATED) as zipf:
            for root, dirs, files in os.walk(root_dir):
                # Exclude version control, environments, node modules, cache, and recordings data
                dirs[:] = [d for d in dirs if d not in ('.git', 'venv', '.venv', 'node_modules', 'recordings', '__pycache__')]
                
                for file in files:
                    file_path = os.path.join(root, file)
                    # Exclude logs, system tracking PIDs, and compiled python bytecode
                    if file.endswith(('.log', '.pid', '.pyc', '.pyo', '.swp')):
                        continue
                    if 'backend/recordings' in file_path:
                        continue
                        
                    # Write file with relative archive path
                    arcname = os.path.relpath(file_path, root_dir)
                    zipf.write(file_path, arcname)
                    
        # Schedule cleanup task to remove the zip after file is transmitted
        def clean_temp_zip(path: str):
            try:
                if os.path.exists(path):
                    os.remove(path)
            except Exception as e:
                logger.error(f"Error deleting temp zip: {e}")
                
        background_tasks.add_task(clean_temp_zip, zip_path)
        
        return FileResponse(
            path=zip_path,
            filename="meeting_recorder_windows.zip",
            media_type="application/zip"
        )
    except Exception as e:
        logger.error(f"Failed to generate windows standalone zip: {e}")
        raise HTTPException(status_code=500, detail=str(e))

# Setup static mounts LAST to avoid shadowing API routes
app.mount("/recordings", StaticFiles(directory=RECORDINGS_DIR), name="recordings")

def setup_frontend(app):
    frontend_path = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "frontend", "dist"))
    if os.path.exists(frontend_path):
        assets_path = os.path.join(frontend_path, "assets")
        if os.path.exists(assets_path):
            app.mount("/assets", StaticFiles(directory=assets_path), name="frontend-assets")
        app.mount("/", StaticFiles(directory=frontend_path, html=True), name="frontend-root")

setup_frontend(app)

if __name__ == "__main__":
    import uvicorn
    import sys
    is_prod = os.environ.get("PRODUCTION") == "1" or sys.executable.lower().endswith("pythonw.exe")
    host = os.environ.get("HOST", "0.0.0.0")
    port = int(os.environ.get("PORT", 8083))
    uvicorn.run("main:app", host=host, port=port, reload=not is_prod)
