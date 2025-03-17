import os
import pvporcupine
from pvrecorder import PvRecorder
from dotenv import load_dotenv
load_dotenv()
access_key = os.getenv('PICOVOICE_ACCESS_KEY')
if not access_key:
    print("Error: Porcupine access key not found in .env file.")
wakeword_path = "pixy_windows.ppn"  # Replace with your .ppn file path
sensitivity = 1

# Initialize Porcupine
porcupine = pvporcupine.create(access_key=access_key, keyword_paths=[wakeword_path], sensitivities=[sensitivity])

# Initialize PvRecorder
recorder = PvRecorder(device_index=-1, frame_length=porcupine.frame_length)
recorder.start()


def listen_for_wakeword():
    print("Pixie is Ready")
    try:
        while True:
            pcm = recorder.read()
            keyword_index = porcupine.process(pcm)
            if keyword_index >= 0:
                print("detected")
    except KeyboardInterrupt:
        print("Stopping...")
    finally:
        recorder.stop()
        porcupine.delete()

if __name__ == "__main__":
    listen_for_wakeword()