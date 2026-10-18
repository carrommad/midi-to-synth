import time
import mido

for p in mido.get_input_names():
    if "mpk" in p.lower():
        print("Connected to:", p)
        with mido.open_input(p) as inport:
            for msg in inport:
                if msg.type == "note_on" and msg.velocity > 0:
                    print(f"Note On: {msg.note} (Ch {msg.channel + 1}, Vel {msg.velocity})")
                elif msg.type == "note_off" or (msg.type == "note_on" and msg.velocity == 0):
                    print(f"Note Off: {msg.note}")
