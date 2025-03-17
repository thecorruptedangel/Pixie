import pvorca
import sounddevice as sd
import numpy as np
import time
from queue import Queue, Empty
import threading

ACCESS_KEY = ''
orca = pvorca.create(access_key=ACCESS_KEY)

SAMPLE_RATE = 22050
BUFFER_SIZE = 20  # Increased buffer size
CHUNK_SIZE = 4096  # Larger chunk size for smoother playback
MIN_AUDIO_LENGTH = CHUNK_SIZE * 2  # Minimum audio length before starting playback

audio_queue = Queue(maxsize=BUFFER_SIZE)
stop_event = threading.Event()

def play_audio():
    buffer = np.array([], dtype=np.int16)
    while len(buffer) < MIN_AUDIO_LENGTH and not stop_event.is_set():
        try:
            pcm = audio_queue.get(timeout=0.1)
            if isinstance(pcm, list):
                audio_data = np.array(pcm, dtype=np.int16)
            else:
                audio_data = np.frombuffer(pcm, dtype=np.int16)
            buffer = np.concatenate((buffer, audio_data))
        except Empty:
            continue

    with sd.OutputStream(samplerate=SAMPLE_RATE, channels=1, dtype='int16') as stream:
        while not stop_event.is_set() or len(buffer) > 0:
            if len(buffer) >= CHUNK_SIZE:
                chunk = buffer[:CHUNK_SIZE]
                buffer = buffer[CHUNK_SIZE:]
                stream.write(chunk)
            else:
                try:
                    pcm = audio_queue.get(timeout=0.1)
                    if isinstance(pcm, list):
                        audio_data = np.array(pcm, dtype=np.int16)
                    else:
                        audio_data = np.frombuffer(pcm, dtype=np.int16)
                    buffer = np.concatenate((buffer, audio_data))
                except Empty:
                    if stop_event.is_set():
                        break
    
def stream_synthesis(text_generator):
    print("Starting stream synthesis")
    stream = orca.stream_open()
    
    playback_thread = threading.Thread(target=play_audio)
    playback_thread.start()
    
    for text_chunk in text_generator():
        pcm = stream.synthesize(text_chunk)
        if pcm is not None:
            audio_queue.put(pcm)
    
    pcm = stream.flush()
    if pcm is not None:
        audio_queue.put(pcm)
    
    stop_event.set()
    playback_thread.join()
    stream.close()

def word_generator():
    sentences = [
        "The quick brown fox jumps over the lazy dog. ",
        "It was a dark and stormy night. ",
        "To be or not to be, that is the question. ",
        "All that glitters is not gold. ",
        "Where there's a will, there's a way. "
    ]
    
    for sentence in sentences:
        yield sentence
        time.sleep(np.random.uniform(0.5, 1.0))  # Longer pause between sentences

if __name__ == "__main__":
    print("Starting streaming synthesis...")
    stream_synthesis(word_generator)
    print("ended stream")
    orca.delete()
  