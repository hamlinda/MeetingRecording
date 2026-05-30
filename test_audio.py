import time
import os
from backend.recorder import AudioRecorder

try:
    recorder = AudioRecorder()
    print("Starting recorder...")
    recorder.start(record_mic=True)
    
    print("Recording for 5 seconds...")
    time.sleep(5)
    
    output_base = os.path.join(os.getcwd(), "backend", "recordings", "test_recording.mp4")
    print("Stopping recorder...")
    paths, mp4 = recorder.stop(output_base)
    
    print("\nResults:")
    print("Loopback path:", paths.get("loopback"), "Exists?", os.path.exists(paths.get("loopback", "")))
    print("Mic path:", paths.get("mic"), "Exists?", os.path.exists(paths.get("mic", "")))
    print("MP4 path:", mp4)
except Exception as e:
    print(f"Exception caught: {e}")
