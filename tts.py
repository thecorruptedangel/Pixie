import sounddevice as sd
import numpy as np
import time

from deepgram import (
    DeepgramClient,
    DeepgramClientOptions,
    SpeakWebSocketEvents,
    SpeakOptions,
)

TTS_TEXT = "Hello, this is a text to speech example using Deepgram."

def main():
    try:
        # Create a Deepgram client using the API key from environment variables
        deepgram: DeepgramClient = DeepgramClient()

        # Create a websocket connection to Deepgram
        dg_connection = deepgram.speak.websocket.v("1")

        def on_open(self, open, **kwargs):
            print(f"\n\n{open}\n\n")

        def on_binary_data(self, data, **kwargs):
            print("Received binary data")
            array = np.frombuffer(data, dtype=np.int16)
            sd.play(array, 48000)
            sd.wait()

        def on_close(self, close, **kwargs):
            print(f"\n\n{close}\n\n")

        dg_connection.on(SpeakWebSocketEvents.Open, on_open)
        dg_connection.on(SpeakWebSocketEvents.AudioData, on_binary_data)
        dg_connection.on(SpeakWebSocketEvents.Close, on_close)

        # connect to websocket
        options = SpeakOptions(
            model="aura-asteria-en",
            encoding="linear16",
            sample_rate=48000,
        )

        print("\n\nPress Enter to stop...\n\n")
        if dg_connection.start(options) is False:
            print("Failed to start connection")
            return

        # send the text to Deepgram
        dg_connection.send_text(TTS_TEXT)
        dg_connection.flush()

        # Indicate that we've finished
        time.sleep(5)
        print("\n\nPress Enter to stop...\n\n")
        input()
        dg_connection.finish()

        print("Finished")
        
    except Exception as e:
        print(f"An unexpected error occurred: {e}")


if __name__ == "__main__":
    main()