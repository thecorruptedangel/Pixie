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
import threading

load_dotenv()

current_sentence = ""
displayed_sentence = ""
last_update_time = time.time()
processing_lock = threading.Lock()

def process(sentence, is_final):
    status = "Final" if is_final else "Interim"
    print(f"\nProcessed ({status}): {sentence}")

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
    while True:
        time.sleep(0.01)  # Check every 100ms
        with processing_lock:
            if current_sentence and time.time() - last_update_time > 2:
                display_sentence(current_sentence)
                process(current_sentence, False)
                current_sentence = ""
                last_update_time = time.time()

def main():
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

        def on_close(self, close, **kwargs):
            print("\nConnection Closed")

        def on_error(self, error, **kwargs):
            print(f"\nHandled Error: {error}")

        dg_connection.on(LiveTranscriptionEvents.Transcript, on_message)
        dg_connection.on(LiveTranscriptionEvents.Close, on_close)
        dg_connection.on(LiveTranscriptionEvents.Error, on_error)

        options: LiveOptions = LiveOptions(
            model="nova-2",
            language="en-US",
            smart_format=True,
            encoding="linear16",
            channels=1,
            sample_rate=16000,
            interim_results=True,
            utterance_end_ms="1000",
            vad_events=True,
            endpointing=300,
            no_delay=True,
        )

        print("\n\nPress Enter to stop recording...\n")
        if dg_connection.start(options) is False:
            print("Failed to connect to Deepgram")
            return

        # Start the timeout checking thread
        timeout_thread = threading.Thread(target=check_timeout, daemon=True)
        timeout_thread.start()

        microphone = Microphone(dg_connection.send)
        microphone.start()
        input()
        microphone.finish()
        dg_connection.finish()

        print("\nFinished")

    except Exception as e:
        print(f"Could not open socket: {e}")
        return

if __name__ == "__main__":
    main()