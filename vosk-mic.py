import queue
import sys
import sounddevice as sd
import json
import os
from vosk import Model, KaldiRecognizer
import time

import serial

SERIAL_PORT = "/dev/ttyS1"
BAUD_RATE = 9600


MODEL = "vosk-model-small-en-us-0.15"
#MODEL = "vosk-model-en-us-0.22-lgraph"
# MODEL = "vosk-model-en-us-0.22"
model_path = "model/" + MODEL 
SAMPLE_RATE = 16000
buf_time = 0.0

COMMAND = [
    'payload', 'camera', 'switch'
    ]

last_time = 0
current_time = 0


grammar_json = json.dumps(COMMAND  + ["[unk]"]) 

if not os.path.exists(model_path):
    print(f"Model not found at {model_path}. Please download and extract.")
    sys.exit()

model = Model(model_path)
rec = KaldiRecognizer(model, SAMPLE_RATE, grammar_json)

q = queue.Queue()



def audio_callback(indata, frames, time, status):
    if status:
        print(status, file=sys.stderr)
    q.put(bytes(indata))


def serial_setup():
   ser = serial.Serial(SERIAL_PORT, BAUD_RATE, timeout=1)
   time.sleep(2)
   print(f"serial {ser}")
   return ser

def send_serial(ser, command):
    try:
        cmd_id = COMMAND.index(command)

        header = 0xAA
        checksum = (cmd_id) & 0xFF

        packet = bytearray([header, cmd_id, checksum])
        ser.write(packet)
        print(f"cmd {cmd_id}  - {checksum}")
    except:
        print("error")

def run():
    ser = serial.Serial(SERIAL_PORT, BAUD_RATE, timeout=1)
    time.sleep(2)
    print(f"serial {ser}")
    
    last_time = 0 

    with sd.RawInputStream(samplerate=SAMPLE_RATE, blocksize=4000, dtype='int16',
                           channels=1, callback=audio_callback):
        
        print("Listening for commands (X Y)...")
        
        while True:
            data = q.get()
            if rec.AcceptWaveform(data):
                res_json = json.loads(rec.Result())
                current_text = res_json.get("text", "")
            else:
                partial_json = json.loads(rec.PartialResult())
                current_text = partial_json.get("partial", "")

            if not current_text:
                continue

            words = current_text.split()
            
            if not words:
                continue

            if words[0] in COMMAND:
                now = time.time()

                if (now - last_time) > 1.0:
                    cmd = words[0]
                    print(f"\n[!] EXECUTE: {cmd.upper()} ")
                    
                    send_serial(ser, cmd)
                    
                    rec.Reset() 
                    with q.mutex:
                        q.queue.clear()
                    
                    last_time = now 
                    print("Ready for next command...")
                else:
                    print(f"\r[~] Cooldown active... ({int(now - last_time)}s)", end="")

if __name__ == "__main__":
    try:
        run()
    except KeyboardInterrupt:
        print("\nExiting...")
