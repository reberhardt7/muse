import mido
import time
output = mido.open_output()

def play(note, vel):
    output.send(mido.Message('note_on', note=note, velocity=vel))
    time.sleep(0.5)
    output.send(mido.Message('note_off', note=note, velocity=vel))
