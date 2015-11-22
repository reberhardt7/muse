import mido
from threading import Thread, Lock
import time
import math
import re
from random import randint

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

mutex = Lock()
def _play(note, vel, duration, channel=1):
    mutex.acquire()
    try:
        msg = mido.Message('note_on', note=note, velocity=vel, channel=channel)
        msg.channel = channel
        output.send(msg)
    finally:
        mutex.release()
    time.sleep(duration)
    mutex.acquire()
    try:
        msg = mido.Message('note_off', note=note, velocity=vel, channel=channel)
        msg.channel = channel
        output.send(msg)
    finally:
        mutex.release()

def play(note, vel, duration, channel=1):
    Thread(target=_play, args=(note, vel, duration, channel)).start()

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

    return (int(octave)+2)*12 + position_in_octave

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
    # 'VI': [0, 9, 13],
    'VI': [9, 13, 16],
    # 'VII': [2, 11, 15],
    'VII': [11, 15, 18],
    'ii0': [1, 4, 7, 9],
    'vii0': [0, 4, 7, 10]
}

def major_chord_to_minor(symbol):
    minor = list(notes[symbol])
    minor[1] -= 1
    return minor

notes['i'] = major_chord_to_minor('I')
notes['ii'] = major_chord_to_minor('II')
notes['iii'] = major_chord_to_minor('III')
notes['iv'] = major_chord_to_minor('IV')
notes['v'] = major_chord_to_minor('V')
notes['vi'] = major_chord_to_minor('VI')
notes['vii'] = major_chord_to_minor('VII')

def get_chord(symbol, base_note):
    return [notes[symbol][i] + base_note for i in range(len(notes[symbol]))]

def play_progression(*args):
    for x in args:
        for note in get_chord(x, note_value('C5')):
            play(note, 80, 1)
        time.sleep(1)

def pick_next_chord(seed, transitions):
    return transitions[seed][randint(0, len(transitions[seed])-1)]

def generate_progression(bars, major=True, seed=None):
    transitions = transitions_major if major else transitions_minor
    progression = [ pick_next_chord(seed, transitions) if seed else transitions.keys()[randint(0, len(transitions.keys())-1)] ]
    for _ in range(bars - 1):
        progression.append(pick_next_chord(progression[-1], transitions))
    return progression

def generate_melody(key, progression, major=True):
    out = []
    for chord in progression:
        print chord
        all_tones = generate_scale(key, 2, major)
        chord_tones = get_chord(chord, note_value(key+'2'))
        chord_tones.extend([x+12 for x in chord_tones])
        non_chord_tones = list(set(all_tones[:-1]) - set(chord_tones))
        non_chord_tones.extend([x+12 for x in non_chord_tones])
        print chord_tones

        for _ in range(4):
            select_from = non_chord_tones if int(randint(0, 8)/8.0) else chord_tones
            print select_from
            out.append(select_from[randint(0, len(select_from)-1)])
    return out

if __name__ == '__main__':
    tempo = randint(80, 120)
    seconds_per_beat = 60.0/tempo
    # major = bool(randint(0, 1))
    major = True
    key = keys_in_octave[randint(0, len(keys_in_octave)-1)]
    swing = bool(randint(0, 1))

    verse = generate_progression(4, major=major)
    chorus = generate_progression(4, major=major, seed=verse[-1])
    # Prevent ghost notes from getting too messy at high tempos
    # ghost_note_penalty = int((tempo/80.0)**2)
    # print ghost_note_penalty
    ghost_note_penalty = 1
    snare = [ randint(20, 50) if int(randint(0, ghost_note_penalty)*1.0/ghost_note_penalty) else 0 for _ in range(8) ]
    snare[2] = 80
    snare[6] = 80
    bass = [ randint(30, 80) if int(randint(0, 2*ghost_note_penalty)/(2.0*ghost_note_penalty)) and i not in (2, 6) else 0 for i in range(8) ]

    melody = generate_melody(key, verse, major)
    print melody

    enable_hihat = randint(0, 1)
    for _ in range(4):
        for chord in verse:
            notes_ = get_chord(chord, note_value(key+'2'))
            for note in get_chord(chord, note_value(key+'2')):
                play(note, 80, 1, channel=0)
            for i, note in enumerate(notes_ + [notes_[1]] if len(notes_) == 3 else notes_):
                mutex.acquire()
                output.send(mido.Message('control_change', control=64, value=127, channel=1))
                mutex.release()
                play(note, 80, 0.5*seconds_per_beat, channel=1)
                play(note-12, 100+randint(0, 20)-10, 0.5*seconds_per_beat, channel=3)
                play(melody[verse.index(chord)*4+i], 80, 0.5*seconds_per_beat, channel=4)
                pause = 0.333 if swing else 0.25
                print verse.index(chord)*4+i
                if enable_hihat:
                    play(note_value('C#2'), 70, pause*seconds_per_beat, channel=2)
                if snare[i*2]:
                    play(note_value('G1'), snare[i*2], pause*seconds_per_beat, channel=2)
                if bass[i*2]:
                    play(note_value('C1'), bass[i*2], pause*seconds_per_beat, channel=2)
                time.sleep(pause*seconds_per_beat)
                pause = 0.167 if swing else 0.25
                if enable_hihat and tempo <= 110:
                    play(note_value('C#2'), 40, pause*seconds_per_beat, channel=2)
                if snare[i*2+1]:
                    play(note_value('G1'), snare[i*2+1], pause*seconds_per_beat, channel=2)
                if bass[i*2+1]:
                    play(note_value('C1'), bass[i*2+1], pause*seconds_per_beat, channel=2)
                time.sleep(pause*seconds_per_beat)
            mutex.acquire()
            output.send(mido.Message('control_change', control=64, value=0, channel=1))
            mutex.release()
    # Mix it up!
    snare = [ randint(20, 50) if int(randint(0, ghost_note_penalty)*1.0/ghost_note_penalty) else 0 for _ in range(8) ]
    snare[2] = 80
    snare[6] = 80
    bass = [ randint(30, 80) if int(randint(0, 2*ghost_note_penalty)/(2.0*ghost_note_penalty)) and i not in (2, 6) else 0 for i in range(8) ]
    enable_hihat = randint(0, 1)
    for _ in range(4):
        for chord in chorus:
            notes_ = get_chord(chord, note_value(key+'2'))
            for note in get_chord(chord, note_value(key+'2')):
                play(note, 80, 1, channel=0)
            for i, note in enumerate(notes_ + [notes_[1]] if len(notes_) == 3 else notes_):
                mutex.acquire()
                output.send(mido.Message('control_change', control=64, value=127, channel=1))
                mutex.release()
                play(note, 80, 0.5*seconds_per_beat, channel=1)
                play(note-12, 100+randint(0, 20)-10, 0.5*seconds_per_beat, channel=3)
                pause = 0.333 if swing else 0.25
                if enable_hihat:
                    play(note_value('C#2'), 70, pause*seconds_per_beat, channel=2)
                if snare[i*2]:
                    play(note_value('G1'), snare[i*2], pause*seconds_per_beat, channel=2)
                if bass[i*2]:
                    play(note_value('C1'), bass[i*2], pause*seconds_per_beat, channel=2)
                time.sleep(pause*seconds_per_beat)
                pause = 0.167 if swing else pause
                if enable_hihat and tempo <= 110:
                    play(note_value('C#2'), 40, pause*seconds_per_beat, channel=2)
                if snare[i*2+1]:
                    play(note_value('G1'), snare[i*2+1], pause*seconds_per_beat, channel=2)
                if bass[i*2+1]:
                    play(note_value('C1'), bass[i*2+1], pause*seconds_per_beat, channel=2)
                time.sleep(pause*seconds_per_beat)
            mutex.acquire()
            output.send(mido.Message('control_change', control=64, value=0, channel=1))
            mutex.release()
