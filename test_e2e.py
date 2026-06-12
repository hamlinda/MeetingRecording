import requests
import time
import os

BASE_URL = "http://127.0.0.1:8083"

print("1. Starting test recording...")
start_res = requests.post(f"{BASE_URL}/api/recording/start", json={"record_mic": True})
start_res.raise_for_status()
data = start_res.json()
rec_id = data["recording_id"]
print(f"   -> Started successfully. ID: {rec_id}")

print("2. Sleeping 5 seconds for simulation...")
time.sleep(5)

print("3. Stopping recording...")
stop_res = requests.post(f"{BASE_URL}/api/recording/stop")
stop_res.raise_for_status()
print("   -> Stopped successfully.")

print("4. Verifying payload constraints...")
time.sleep(1) # buffer 1s

# Check JSON
json_path = os.path.join("recordings", f"{rec_id}.json")
assert os.path.exists(json_path), f"JSON State File does not exist at {json_path}!"
print("   -> JSON Exists!")

# Verify the media file exists if mp4 conversion failed (this implies it fell back to wav)
import json
with open(json_path, 'r') as f:
    state = json.load(f)

media_path = state.get("media_path")
assert media_path, "Media path is null/empty in JSON state!"
assert os.path.exists(media_path), f"Media file {media_path} structurally missing from disk!"
print(f"   -> Disk Media physically verified: {media_path}")

print("\n--- E2E TEST PASSED! ---")
