import groq
import os
import pvorca
import sounddevice as sd
import pvporcupine
from pvrecorder import PvRecorder
import numpy as np
from queue import Queue, Empty
import threading
from dotenv import load_dotenv
from deepgram import (
    DeepgramClient,
    DeepgramClientOptions,
    LiveTranscriptionEvents,
    LiveOptions,
    Microphone,
)
import sys
import shutil
import time
import string
import re

load_dotenv()

# Constants
SAMPLE_RATE = 22050
BUFFER_SIZE = 20
CHUNK_SIZE = 1024
MIN_AUDIO_LENGTH = CHUNK_SIZE * 1
MAX_HISTORY = 50

# Global variables
current_sentence = ""
displayed_sentence = ""
last_update_time = time.time()
microphone = None
conversation_history = []
exit_flag = threading.Event()
processing_lock = threading.Lock()

# API clients
client = groq.Groq(api_key=os.getenv("GROQ_API_KEY"))
SYSTEM_PROMPT = os.getenv("GROQ_SYSTEM_PROMPT")
INTENT_PROMPT = os.getenv("INTENT_PROMPT")

porcupine_access_key = os.getenv('PICOVOICE_ACCESS_KEY')
if not porcupine_access_key:
    print("Error: Porcupine access key not found in .env file.")
    sys.exit(1)

wakeword_path = "pixy_windows.ppn"  # Replace with your .ppn file path
sensitivity = 1

class TTSManager:
    def __init__(self, access_key):
        self.access_key = access_key
        self.orca = pvorca.create(access_key=access_key)
        self.text_queue = Queue()
        self.audio_queue = Queue(maxsize=BUFFER_SIZE)
        self.stop_event = threading.Event()
        self.synthesis_thread = None
        self.playback_thread = None

    def synthesize_speech(self):
        stream = self.orca.stream_open()
        while not self.stop_event.is_set():
            try:
                text_chunk = self.text_queue.get(timeout=0.1)
                if text_chunk is None:
                    break
                pcm = stream.synthesize(text_chunk)
                if pcm is not None:
                    self.audio_queue.put(pcm)
            except Empty:
                continue

        pcm = stream.flush()
        if pcm is not None:
            self.audio_queue.put(pcm)
        stream.close()
        self.audio_queue.put(None)  # Signal end of audio synthesis

    def play_audio(self):
        buffer = np.array([], dtype=np.int16)
        with sd.OutputStream(samplerate=SAMPLE_RATE, channels=1, dtype='int16') as stream:
            while not self.stop_event.is_set():
                while len(buffer) < MIN_AUDIO_LENGTH:
                    try:
                        pcm = self.audio_queue.get(timeout=0.1)
                        if pcm is None:  # End of audio
                            self.stop_event.set()
                            break
                        if isinstance(pcm, list):
                            audio_data = np.array(pcm, dtype=np.int16)
                        else:
                            audio_data = np.frombuffer(pcm, dtype=np.int16)
                        buffer = np.concatenate((buffer, audio_data))
                    except Empty:
                        if self.stop_event.is_set():
                            break

                if len(buffer) >= CHUNK_SIZE:
                    chunk = buffer[:CHUNK_SIZE]
                    buffer = buffer[CHUNK_SIZE:]
                    stream.write(chunk)

    def speak(self, text):
        self.stop_event.clear()
        self.text_queue.put(text)
        self.text_queue.put(None)  # Signal end of text

        if self.synthesis_thread is None or not self.synthesis_thread.is_alive():
            self.synthesis_thread = threading.Thread(target=self.synthesize_speech)
            self.synthesis_thread.start()

        if self.playback_thread is None or not self.playback_thread.is_alive():
            self.playback_thread = threading.Thread(target=self.play_audio)
            self.playback_thread.start()

    def wait_for_completion(self):
        if self.synthesis_thread:
            self.synthesis_thread.join()
        if self.playback_thread:
            self.playback_thread.join()

    def cleanup(self):
        self.stop_event.set()
        self.wait_for_completion()
        if self.orca:
            self.orca.delete()
            self.orca = None

    def reset(self):
        self.cleanup()
        self.orca = pvorca.create(access_key=self.access_key)
        self.text_queue = Queue()
        self.audio_queue = Queue(maxsize=BUFFER_SIZE)
        self.stop_event.clear()
        self.synthesis_thread = None
        self.playback_thread = None

# Create TTS manager
tts_manager = TTSManager(os.getenv("PICOVOICE_ACCESS_KEY"))

def should_end_conversation(text):
    text = text.translate(str.maketrans('', '', string.punctuation))
    text = text.strip().lower()
    return re.search(r'\b(goodbye|bye)\b$', text) is not None

def generate_text(prompt, store_in_history=True, max_tokens=100):
    try:
        if not conversation_history or conversation_history[0]["role"] != "system":
            conversation_history.insert(0, {"role": "system", "content": SYSTEM_PROMPT})
        
        temp_conversation = conversation_history.copy()
        temp_conversation.append({"role": "user", "content": prompt})
        
        stream = client.chat.completions.create(
            model="llama-3.1-8b-instant",
            messages=temp_conversation,
            max_tokens=max_tokens,
            stream=True
        )

        ai_response = ""
        for chunk in stream:
            if chunk.choices[0].delta.content is not None:
                text_chunk = chunk.choices[0].delta.content
                ai_response += text_chunk
                print(text_chunk, end='', flush=True)

        if store_in_history:
            conversation_history.append({"role": "user", "content": prompt})
            conversation_history.append({"role": "assistant", "content": ai_response})
            if len(conversation_history) > MAX_HISTORY:
                conversation_history.pop(1)
                conversation_history.pop(1)
        
        print("\n")
        return ai_response
    except Exception as e:
        print(f"An error occurred in text generation: {e}")
        return None

def get_query_type(user_query):
    intent = client.chat.completions.create(
        model="gemma2-9b-it",
        messages=[
            {
                "role": "system",
                "content": INTENT_PROMPT
            },
            {
                "role": "user",
                "content": user_query
            }
        ],
        temperature=0,
        max_tokens=80,
        top_p=1,
        stream=False,
        stop=None,
    )

    # Return the assistant's response
    return intent.choices[0].message.content

def answer(prompt, store_in_history=True):
    global microphone
    if microphone:
        microphone.finish()

    generated_text = generate_text(prompt, store_in_history)

    if generated_text:
        tts_manager.speak(generated_text)
        tts_manager.wait_for_completion()

    if microphone:
        microphone.start()



def clear_line():
    columns, _ = shutil.get_terminal_size()
    sys.stdout.write('\r' + ' ' * columns + '\r')
    sys.stdout.flush()

def display_sentence(sentence, end="\n"):
    global displayed_sentence
    clear_line()
    print(f"\rUSER: {sentence}", end=end, flush=True)
    displayed_sentence = sentence

def check_timeout():
    global current_sentence, last_update_time
    while not exit_flag.is_set():
        time.sleep(0.01)
        with processing_lock:
            if current_sentence and time.time() - last_update_time > 2:
                display_sentence(current_sentence)
                process(current_sentence, False)
                current_sentence = ""
                last_update_time = time.time()

def process(sentence, is_final):
    response = get_query_type(sentence)
    print(response)
    answer(sentence)
    if should_end_conversation(sentence):
        exit_flag.set()

def speech2speech():
    global microphone, dg_connection, exit_flag, current_sentence, last_update_time, displayed_sentence
    try:
        config = DeepgramClientOptions(options={"keepalive": "true"})
        deepgram: DeepgramClient = DeepgramClient("", config)

        dg_connection = deepgram.listen.websocket.v("1")

        def on_message(self, result, **kwargs):
            global current_sentence, last_update_time, displayed_sentence
            transcript = result.channel.alternatives[0].transcript
            if len(transcript) == 0:
                return

            with processing_lock:
                if result.is_final:
                    current_sentence += transcript
                    if result.speech_final:
                        display_sentence(current_sentence)
                        process(current_sentence, True)
                        current_sentence = ""
                    else:
                        display_sentence(current_sentence, end="")
                else:
                    temp_sentence = current_sentence + transcript
                    if temp_sentence != displayed_sentence:
                        display_sentence(temp_sentence, end="")

                last_update_time = time.time()

        dg_connection.on(LiveTranscriptionEvents.Transcript, on_message)

        options: LiveOptions = LiveOptions(
            model="nova-2",
            language="en-US",
            punctuate=True,
            encoding="linear16",
            channels=1,
            sample_rate=16000,
            interim_results=True,
            utterance_end_ms="1000",
            vad_events=True,
            endpointing=300,
            no_delay=True,
        )

        if dg_connection.start(options) is False:
            print("Failed to connect to Deepgram")
            return

        timeout_thread = threading.Thread(target=check_timeout, daemon=True)
        timeout_thread.start()

        microphone = Microphone(dg_connection.send)
        microphone.start()
        
        answer("Hey pixie", store_in_history=False)  # Greet the user after microphone is initialized
        print("\n\nStart speaking. Say 'goodbye' or 'bye' to end the conversation.\n")

        exit_flag.clear()
        while not exit_flag.is_set():
            time.sleep(0.1)
        
        shutdown()
        return

    except Exception as e:
        print(f"An error occurred: {e}")
        return
    finally:
        exit_flag.clear()
        current_sentence = ""
        last_update_time = time.time()
        displayed_sentence = ""

def listen_for_wakeword():
    global porcupine, recorder
    print("Pixie is Ready")
    while True:
        try:
            porcupine = pvporcupine.create(access_key=porcupine_access_key, keyword_paths=[wakeword_path], sensitivities=[sensitivity])
            recorder = PvRecorder(device_index=-1, frame_length=porcupine.frame_length)
            recorder.start()

            while True:
                pcm = recorder.read()
                keyword_index = porcupine.process(pcm)
                if keyword_index >= 0:
                    print("Wake word detected!")
                    recorder.stop()
                    porcupine.delete()
                    speech2speech()
                    tts_manager.reset()  # Reset TTS manager after conversation
                    break  # Exit inner loop to reinitialize porcupine and recorder

        except KeyboardInterrupt:
            print("Stopping...")
            break
        except Exception as e:
            print(f"An error occurred: {e}")
        finally:
            if 'recorder' in locals() and recorder is not None:
                recorder.stop()
            if 'porcupine' in locals() and porcupine is not None:
                porcupine.delete()

    shutdown()

def shutdown():
    global microphone, dg_connection, tts_manager
    print("\nShutting down...")
    if microphone:
        microphone.finish()
    if 'dg_connection' in globals():
        dg_connection.finish()
    tts_manager.cleanup()

if __name__ == "__main__":
    listen_for_wakeword()