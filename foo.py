import mido
import thread
import time
import math
import re

# Standard notes in an octave
keys_in_octave = ['C', 'C#', 'D', 'D#', 'E', 'F', 'F#', 'G', 'G#', 'A', 'A#', 'B']
# For remapping certain note values to more standard note names:
note_remap = {
    'Db': 'C#',
    'Eb': 'D#',
    'E#': 'F',
    'Fb': 'E',
    'Gb': 'F#',
    'Ab': 'G#',
    'Bb': 'A#',
    'B#': 'C',
    'Cb': 'B'
}

# Relative positions of notes in major/minor scales:
major_scale_progression = [0, 2, 4, 5, 7, 9, 11, 12]
minor_scale_progression = [0, 2, 3, 5, 7, 8, 10, 12]

output = mido.open_output()

def _play(note, vel, duration):
    output.send(mido.Message('note_on', note=note, velocity=vel))
    time.sleep(duration)
    output.send(mido.Message('note_off', note=note, velocity=vel))

def play(note, vel, duration):
    thread.start_new_thread(_play, (note, vel, duration))

# major_scales = ['Cb', 'Gb', 'Db', 'Ab', 'Eb', 'Bb', 'F', 'C', 'G', 'D', 'A', 'E', 'B', 'F#', 'C#']
# minor_scales = ['Ab', 'Eb', 'Bb', 'F', 'C', 'G', 'D', 'A', 'E', 'B', 'F#', 'C#', 'G#', 'D#', 'A#']
# def minor_to_major(scale):
#     return major_scales[minor_scales.index(scale)]

# Returns the MIDI note value for a note name (e.g. "C#4")
def note_value(note):
    try:
        note, octave = re.match(r'^([A-Z][b#]?)(\d+)$', note[0].upper()+note[1:]).groups()
    except AttributeError:
        raise Exception('Bad note input to note_value %r' % note)

    if note in note_remap.keys():
        note = note_remap[note]

    position_in_octave = keys_in_octave.index(note)

    return int(octave)*12 + position_in_octave

# Generates a sequence of MIDI note values for a scale. `name` specifies the
# base note, `octave` specifies in which octave the scale should be, and
# `major` designates whether the produced scale should be major or minor
def generate_scale(name, octave, major=True):
    scale = major_scale_progression if major else minor_scale_progression
    base_note = note_value(name+str(octave))
    return [ base_note + x for x in scale ]

transitions_major = {
  'I': ['I', 'ii', 'iii', 'IV', 'V', 'vi', 'vii0'],
  'ii': ['V', 'vii0'],
  'iii': ['IV', 'vi'],
  'IV': ['I', 'ii', 'V', 'vii0'],
  'V': ['I', 'vi'],
  'vi': ['ii', 'IV', 'V'],
  'vii0': ['I']
}

transitions_minor = {
  'i': ['i', 'ii0', 'III', 'iv', 'V', 'VI', 'VII', 'vii0'],
  'ii0': ['V', 'vii0'],
  'III': ['iv', 'VI'],
  'iv': ['i', 'ii0', 'V', 'vii0'],
  'V': ['i', 'VI'],
  'VI': ['ii0', 'iv', 'V'],
  'VII': ['III'],
  'vii0': ['i', 'V']
}

notes = {
  'I': [0, 4, 7],
  'II': [2, 6, 9],
  'III': [4, 8, 11],
  'IV': [5, 9, 12],
  'V': [7, 11, 14],
  'VI': [0, 9, 13],
  # 'VI': [9, 13, 16],
  'VII': [2, 11, 15],
  # 'VII': [11, 15, 18],
  'i': major_chord_to_minor('I'),
  'ii': major_chord_to_minor('II'),
  'iii': major_chord_to_minor('III'),
  'iv': major_chord_to_minor('IV'),
  'v': major_chord_to_minor('V'),
  'vi': major_chord_to_minor('VI'),
  'vii': major_chord_to_minor('VII'),
  'ii0': [1, 4, 7, 9],
  'vii0': [0, 4, 7, 10]
}

def major_chord_to_minor(symbol):
  minor = notes[symbol]
  minor[1] -= 1
  return minor

def get_chord(symbol, base_note):
  return [notes[symbol] + base_note for i in range(len(notes[symbol]))]
