import json
import os
import threading
import sys
import queue
import asyncio
import pyaudio
from groq import Groq
from websockets.sync.client import connect

# Constants
TIMEOUT = 0.050
FORMAT = pyaudio.paInt16
CHANNELS = 1
RATE = 48000
CHUNK = 8000

# Environment Variables
DEEPGRAM_URL = f"wss://api.deepgram.com/v1/speak?encoding=linear16&sample_rate={RATE}"
DEEPGRAM_TOKEN = os.getenv("DEEPGRAM_API_KEY")
GROQ_TOKEN = os.getenv("GROQ_API_KEY")

class Speaker:
    """Class to handle audio playback."""
    def __init__(self, rate=RATE, chunk=CHUNK, channels=CHANNELS):
        self._exit = threading.Event()
        self._queue = queue.Queue()
        self._audio = pyaudio.PyAudio()
        self._stream = self._audio.open(
            format=FORMAT, channels=channels, rate=rate, output=True,
            frames_per_buffer=chunk
        )
        self.playback_finished = threading.Event()

    def start(self):
        """Start audio playback."""
        threading.Thread(target=self._play, daemon=True).start()

    def stop(self):
        """Stop audio playback."""
        self._exit.set()
        self._stream.stop_stream()
        self._stream.close()

    def play(self, data):
        """Queue audio data for playback."""
        self._queue.put(data)

    def _play(self):
        """Play queued audio."""
        while not self._exit.is_set():
            try:
                data = self._queue.get(timeout=TIMEOUT)
                self._stream.write(data)
            except queue.Empty:
                if self._queue.empty():
                    self.playback_finished.set()
                continue

print(f"Connecting to {DEEPGRAM_URL}")

# Initialize Groq client
client = Groq(api_key=GROQ_TOKEN)

# Connect to Deepgram TTS WebSocket
_socket = connect(
    DEEPGRAM_URL,
    additional_headers={"Authorization": f"Token {DEEPGRAM_TOKEN}"},
)

_exit = threading.Event()

def answer(question):
    speaker = Speaker()
    speaker.start()
    speaker.playback_finished.clear()

    def handle_message(message):
        """Process WebSocket message."""
        if isinstance(message, str):
            if "Flushed" not in message:  # Skip unnecessary metadata
                print(message)
        elif isinstance(message, bytes):
            speaker.play(message)

    async def receiver():
        """Receive and play TTS audio."""
        try:
            while not _exit.is_set():
                message = _socket.recv()
                handle_message(message)
        except Exception as e:
            print(f"Receiver error: {e}")
        finally:
            
            speaker.stop()

    receiver_thread = threading.Thread(target=asyncio.run, args=(receiver(),), daemon=True)
    receiver_thread.start()

    try:
        # Groq API request
        completion = client.chat.completions.create(
            model="llama3-8b-8192",
            messages=[{"role": "user", "content": question}],
            stream=True,
        )

        # Process streaming response
        for chunk in completion:
            llm_output = chunk.choices[0].delta.content
            if llm_output:
                _socket.send(json.dumps({"type": "Speak", "text": llm_output}))
                sys.stdout.write(llm_output)
                sys.stdout.flush()

        # Finalize audio stream
        _socket.send(json.dumps({"type": "Flush"}))

        # Wait for playback to finish
        speaker.playback_finished.wait()
        
    except Exception as e:
        print(f"LLM Exception: {e}")

    # Ensure the receiver thread is finished
    receiver_thread.join()

if __name__ == "__main__":
    print("ready")
    answer("How are you ? answer under 10 words")

    _exit.set()
    _socket.close()