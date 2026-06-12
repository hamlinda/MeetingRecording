try:
    import pyaudiowpatch as pyaudio
except ImportError:
    try:
        import pyaudio
    except ImportError:
        pyaudio = None

import wave
import threading
import logging
import subprocess
import os

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

class AudioRecorder:
    def __init__(self):
        if pyaudio is None:
            self.p = None
            logger.warning("PyAudio/pyaudiowpatch is not installed. Audio recording features are disabled.")
        else:
            self.p = pyaudio.PyAudio()
        self.is_recording = False
        
        self.stream_loopback = None
        self.frames_loopback = []
        self.worker_loopback = None
        self.loopback_channels = 2
        
        self.stream_mic = None
        self.frames_mic = []
        self.worker_mic = None
        self.mic_channels = 1
        
        self.sample_rate = 48000
        self.record_mic = False
        
    def start(self, record_mic: bool = True):
        if pyaudio is None or self.p is None:
            raise Exception("Audio recording is disabled because PyAudio/pyaudiowpatch is not installed on this system.")

        if self.is_recording:
            return
            
        self.record_mic = record_mic
        self.frames_loopback = []
        self.frames_mic = []
        self.is_recording = True
        
        try:
            wasapi_info = self.p.get_host_api_info_by_type(pyaudio.paWASAPI)
        except OSError:
            self.is_recording = False
            raise Exception("WASAPI is not available on the system.")

        default_speakers = self.p.get_device_info_by_index(wasapi_info["defaultOutputDevice"])
        
        if not default_speakers["isLoopbackDevice"]:
            for loopback in self.p.get_loopback_device_info_generator():
                if default_speakers["name"] in loopback["name"]:
                    default_speakers = loopback
                    break
            else:
                # fallback loopback
                for loopback in self.p.get_loopback_device_info_generator():
                    default_speakers = loopback
                    break

        self.loopback_channels = default_speakers["maxInputChannels"]
        self.sample_rate = int(default_speakers["defaultSampleRate"])
        
        try:
            self.stream_loopback = self.p.open(
                format=pyaudio.paInt16,
                channels=self.loopback_channels,
                rate=self.sample_rate,
                frames_per_buffer=pyaudio.get_sample_size(pyaudio.paInt16),
                input=True,
                input_device_index=default_speakers["index"],
            )
        except Exception as e:
            self.is_recording = False
            raise Exception(f"Failed to open loopback stream '{default_speakers['name']}': {str(e)}")

        if self.record_mic:
            try:
                default_mic = self.p.get_default_input_device_info()
                self.mic_channels = default_mic["maxInputChannels"]
                self.stream_mic = self.p.open(
                    format=pyaudio.paInt16,
                    channels=self.mic_channels,
                    rate=self.sample_rate,
                    frames_per_buffer=1024,
                    input=True,
                    input_device_index=default_mic["index"],
                )
            except Exception as e:
                self.is_recording = False
                self.stream_loopback.close()
                raise Exception(f"Failed to open microphone stream: {str(e)}")

        self.worker_loopback = threading.Thread(target=self._record_loopback_loop)
        self.worker_loopback.start()
        
        if self.record_mic:
            self.worker_mic = threading.Thread(target=self._record_mic_loop)
            self.worker_mic.start()

    def _record_loopback_loop(self):
        while self.is_recording:
            try:
                data = self.stream_loopback.read(1024, exception_on_overflow=False)
                self.frames_loopback.append(data)
            except Exception as e:
                pass
                
    def _record_mic_loop(self):
        while self.is_recording:
            try:
                data = self.stream_mic.read(1024, exception_on_overflow=False)
                self.frames_mic.append(data)
            except Exception as e:
                pass

    def stop(self, output_media: str, video_path: str = None):
        self.is_recording = False
        
        # Stop streams proactively to break deadlocked read() loops
        if self.stream_loopback:
            try: self.stream_loopback.stop_stream()
            except: pass
        if self.record_mic and self.stream_mic:
            try: self.stream_mic.stop_stream()
            except: pass
            
        # Join workers with a strict timeout to gracefully abandon them if Windows Audio is completely asleep
        if self.worker_loopback:
            self.worker_loopback.join(timeout=1.0)
        if self.record_mic and self.worker_mic:
            self.worker_mic.join(timeout=1.0)
            
        # Safely shut down streams
        if self.stream_loopback:
            try: self.stream_loopback.close()
            except: pass
        if self.record_mic and self.stream_mic:
            try: self.stream_mic.close()
            except: pass
            
        loopback_wav = os.path.join(os.path.dirname(output_media), "audio_system.wav")
        self._write_wav(loopback_wav, self.frames_loopback, self.loopback_channels)
        
        mic_wav = None
        if self.record_mic:
            mic_wav = os.path.join(os.path.dirname(output_media), "audio_mic.wav")
            self._write_wav(mic_wav, self.frames_mic, self.mic_channels)
            
        try:
            if video_path and os.path.exists(video_path):
                if self.record_mic:
                    cmd = ['ffmpeg', '-y', '-i', video_path, '-i', loopback_wav, '-i', mic_wav, '-filter_complex', '[1:a][2:a]amix=inputs=2:duration=longest[a]', '-map', '0:v', '-map', '[a]', '-c:v', 'copy', '-c:a', 'libopus', '-b:a', '192k', output_media]
                else:
                    cmd = ['ffmpeg', '-y', '-i', video_path, '-i', loopback_wav, '-c:v', 'copy', '-c:a', 'libopus', '-b:a', '192k', output_media]
            else:
                if self.record_mic:
                    cmd = ['ffmpeg', '-y', '-i', loopback_wav, '-i', mic_wav, '-filter_complex', 'amix=inputs=2:duration=longest', '-c:a', 'aac', '-b:a', '192k', output_media]
                else:
                    cmd = ['ffmpeg', '-y', '-i', loopback_wav, '-c:a', 'aac', '-b:a', '192k', output_media]
                    
            subprocess.run(cmd, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, check=True)
            return {"loopback": loopback_wav, "mic": mic_wav}, output_media
        except Exception:
            # Fallback to the pristine unmixed loopback WAV file if FFmpeg fails or doesn't exist
            return {"loopback": loopback_wav, "mic": mic_wav}, loopback_wav

    def _write_wav(self, path, frames, channels):
        wf = wave.open(path, 'wb')
        wf.setnchannels(channels)
        wf.setsampwidth(self.p.get_sample_size(pyaudio.paInt16))
        wf.setframerate(self.sample_rate)
        wf.writeframes(b''.join(frames))
        wf.close()
