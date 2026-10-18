import mido

print("=== AKAI MIDI CC MONITOR ===")
ports = [p for p in mido.get_input_names() if "mpk" in p.lower()]
if not ports:
    print("No MPK found")
    exit(1)

print(f"Listening on {ports[0]}... (Press CC button on Akai and tap pads)")
with mido.open_input(ports[0]) as inport:
    for msg in inport:
        if msg.type == "control_change":
            print(f"Incoming CC: Control={msg.control}, Value={msg.value}, Channel={msg.channel + 1}")
