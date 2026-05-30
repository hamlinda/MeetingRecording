import logging
from faster_whisper import WhisperModel

logger = logging.getLogger(__name__)

class AudioTranscriber:
    def __init__(self, model_size="base"):
        # You can configure to "tiny", "base", "small", "medium", "large-v3"
        logger.info(f"Loading Whisper model '{model_size}'...")
        # Run on CPU by default to ensure maximum compatibility unless CUDA is requested,
        # but let's try auto detection. In faster-whisper 'cuda' will fail if not installed.
        # We will use 'cpu' with INT8 quantization for wide compatibility and decent speed.
        self.model = WhisperModel(model_size, device="cpu", compute_type="int8")
        logger.info("Whisper model loaded successfully.")

    def transcribe(self, audio_file_path: str) -> list:
        logger.info(f"Transcribing {audio_file_path}...")
        try:
            segments_gen, info = self.model.transcribe(audio_file_path, beam_size=5)
            logger.info("Detected language '%s' with probability %f" % (info.language, info.language_probability))
            
            segments = []
            for segment in segments_gen:
                segments.append({
                    "start": segment.start,
                    "end": segment.end,
                    "text": segment.text.strip()
                })
                
            return segments
        except Exception as e:
            logger.error(f"Error during transcription: {e}")
            return [{"start": 0, "end": 0, "text": f"Error: {e}"}]
