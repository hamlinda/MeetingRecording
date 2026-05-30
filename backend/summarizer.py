import requests
import logging

logger = logging.getLogger(__name__)

class ContentSummarizer:
    def __init__(self, ollama_url="http://localhost:11434", model="llama3.1"):
        self.ollama_url = ollama_url
        self.model = model

    def summarize(self, text: str, custom_prompt: str = None) -> str:
        logger.info(f"Summarizing {len(text)} characters using Ollama...")
        if custom_prompt:
            prompt = f"{custom_prompt}\n\nTranscript:\n{text}"
        else:
            prompt = f"Summarize the following meeting transcription:\n\n{text}"
        
        url = f"{self.ollama_url}/api/generate"
        payload = {
            "model": self.model,
            "prompt": prompt,
            "stream": False
        }
        
        try:
            response = requests.post(url, json=payload, timeout=120)
            response.raise_for_status()
            result = response.json()
            return result.get("response", "No response from model.")
        except requests.exceptions.RequestException as e:
            logger.error(f"Error communicating with local Ollama server: {e}")
            return f"Summarization Error: Make sure your Ollama URL {self.ollama_url} is correct and the server is running."

    def diarize(self, transcript: str, system_speaker: str) -> str:
        logger.info(f"Diarizing {len(transcript)} characters using Ollama...")
        prompt = (
            f"You are an AI tasked strictly with re-formatting transcripts. "
            f"The following transcript contains segments from **{system_speaker}** (which is me) and **Meeting** (which is a group of other people). "
            f"Your job is to read the conversational context and systematically replace the **Meeting** tags with **Speaker 1**, **Speaker 2**, etc., "
            f"whenever there are multiple distinct people talking inside the Meeting block. Leave **{system_speaker}** perfectly intact. "
            f"Do NOT summarize, shorten, or alter the actual spoken text. ONLY correct the speaker tags and return the identically worded full transcript.\n\n"
            f"Transcript:\n{transcript}"
        )
        
        url = f"{self.ollama_url}/api/generate"
        payload = {
            "model": self.model,
            "prompt": prompt,
            "stream": False
        }
        
        try:
            response = requests.post(url, json=payload, timeout=120)
            response.raise_for_status()
            result = response.json()
            return result.get("response", transcript)
        except Exception as e:
            logger.error(f"Error during AI Diarization logic: {e}")
            return transcript

