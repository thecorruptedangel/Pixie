import json
import os
import threading
import asyncio
import queue

import websockets
import pyaudio
from groq import Groq

TIMEOUT = 0.050
FORMAT = pyaudio.paInt16
CHANNELS = 1
RATE = 48000
CHUNK = 4000

DEFAULT_URL = f"wss://api.deepgram.com/v1/speak?encoding=linear16&sample_rate={RATE}"
DEFAULT_DEEPGRAM_TOKEN = os.environ.get("DEEPGRAM_API_KEY")
DEFAULT_GROQ_TOKEN = os.environ.get("GROQ_API_KEY")

def groq_text_generator(prompt, max_tokens=200, model="llama-3.1-8b-instant"):
    client = Groq(api_key=DEFAULT_GROQ_TOKEN)
    messages = [
        {"role": "system", "content": "You are a helpful assistant."},
        {"role": "user", "content": prompt},
    ]
    stream = client.chat.completions.create(
        messages=messages,
        model=model,
        max_tokens=max_tokens,
        stream=True,
    )
    for chunk in stream:
        if chunk.choices[0].delta.content is not None:
            yield chunk.choices[0].delta.content

class Speaker:
    def __init__(self, rate=RATE, chunk=CHUNK, channels=CHANNELS):
        self._exit = threading.Event()
        self._queue = queue.Queue()
        self._audio = pyaudio.PyAudio()
        self._chunk = chunk
        self._rate = rate
        self._format = FORMAT
        self._channels = channels
        self._stream = None
        self._thread = None

    def start(self):
        self._stream = self._audio.open(
            format=self._format,
            channels=self._channels,
            rate=self._rate,
            input=False,
            output=True,
            frames_per_buffer=self._chunk,
        )
        self._thread = threading.Thread(
            target=self._play, daemon=True
        )
        self._thread.start()
        self._stream.start_stream()

    def stop(self):
        self._exit.set()
        if self._stream:
            self._stream.stop_stream()
            self._stream.close()
        if self._thread:
            self._thread.join()
        self._audio.terminate()

    def play(self, data):
        self._queue.put(data)

    def _play(self):
        while not self._exit.is_set():
            try:
                data = self._queue.get(timeout=TIMEOUT)
                self._stream.write(data)
            except queue.Empty:
                pass

async def receiver(websocket, speaker):
    try:
        async for message in websocket:
            if isinstance(message, bytes):
                speaker.play(message)
    except websockets.exceptions.ConnectionClosed:
        print("WebSocket connection closed")

async def main():
    speaker = Speaker()
    speaker.start()

    question = input("What would you like to ask the AI?\n")

    try:
        async with websockets.connect(
            DEFAULT_URL,
            extra_headers={"Authorization": f"Token {DEFAULT_DEEPGRAM_TOKEN}"}
        ) as websocket:
            receiver_task = asyncio.create_task(receiver(websocket, speaker))

            try:
                for llm_output in groq_text_generator(question):
                    await websocket.send(json.dumps({"type": "Speak", "text": llm_output}))
                    print(llm_output, end='', flush=True)
                await websocket.send(json.dumps({"type": "Flush"}))
            except Exception as e:
                print(f"\nError: {e}")

            await receiver_task
    finally:
        speaker.stop()

    print("\nPress Enter to exit...")

if __name__ == "__main__":
    asyncio.run(main())