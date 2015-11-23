import mido
from threading import Thread, Lock
import time
import math
import re
import numpy
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
    for _ in range(2*int(randint(3, 6)/3.0)):
        time_used = 0.0
        for i, chord in enumerate(progression):
            all_tones = generate_scale(key, 2, major)
            chord_tones = get_chord(chord, note_value(key+'2'))
            chord_tones.extend([x+12 for x in chord_tones])
            non_chord_tones = list(set(all_tones[:-1]) - set(chord_tones))
            non_chord_tones.extend([x+12 for x in non_chord_tones])
            last_played = None

            while time_used < i + 1:
                note_vals = [(0.125, 2), (0.25, 4), (0.375, 2), (0.5, 2), (0.75, 1), (1.0, 1), (1.25, 0.5), (1.5, 0.25)]
                possible_note_vals = [x for x, p in note_vals if time_used + x <= len(progression)]
                note_vals_prob = [p for x, p in note_vals if time_used + x <= len(progression)]
                note_vals_prob = [x*1.0/sum(note_vals_prob) for x in note_vals_prob]
                note_val = numpy.random.choice(possible_note_vals, p=note_vals_prob)
                select_from = non_chord_tones if int(randint(0, 10)/10.0) else chord_tones
                select_from_probabilities = [ (36 - int(math.fabs(last_played - x)))**1.5 if last_played else 1 for x in select_from ]
                select_from_probabilities = [ x * 1.0 / sum(select_from_probabilities) for x in select_from_probabilities ]
                out.append((numpy.random.choice(select_from, p=select_from_probabilities), 80, note_val))
                last_played = out[-1][0]
                out.extend([None for x in range(int(note_val/0.125)-1)])
                time_used += note_val
    if len(out) == 2*len(progression)*8:
        out.extend(out)
    print len(out)
    return out

if __name__ == '__main__':
    tempo = randint(100, 200)
    seconds_per_beat = 60.0/tempo
    # major = bool(randint(0, 1))
    major = True
    key = keys_in_octave[randint(0, len(keys_in_octave)-1)]
    swing = bool(randint(0, 1))

    verse_progression = generate_progression(4, major=major)
    verse_chords = []
    for _ in range(4):
        for chord in verse_progression:
            verse_chords.append((get_chord(chord, note_value(key+'2')), 80, 1.0))
            verse_chords.extend([None for x in range(7)])
    verse_rhythm_chords = []
    for _ in range(4):
        for chord in verse_progression:
            verse_rhythm_chords.extend([(get_chord(chord, note_value(key+'2')), 80, 0.125),
                                        (get_chord(chord, note_value(key+'2')), 60, 0.125)]*4)
    verse_arp = []
    for _ in range(4):
        for chord in verse_progression:
            notes_ = get_chord(chord, note_value(key+'2'))
            for note in (notes_ + [notes_[1]] if len(notes_) == 3 else notes_):
                verse_arp.append((note, 80, 0.25))
                verse_arp.append(None)
    # Prevent ghost notes from getting too messy at high tempos
    # ghost_note_penalty = int((tempo/80.0)**2)
    ghost_note_penalty = 1
    snare = [ randint(20, 50) if int(randint(0, ghost_note_penalty)*1.0/ghost_note_penalty) else 0 for _ in range(8) ]
    snare[2] = 80
    snare[6] = 80
    bass = [ randint(30, 80) if int(randint(0, 2*ghost_note_penalty)/(2.0*ghost_note_penalty)) and i not in (2, 6) else 0 for i in range(8) ]
    verse_snare = [ (note_value('G1'), x, 0.03) if x else None for x in snare ] * 16
    verse_bass = [ (note_value('C1'), x, 0.03) if x else None for x in bass ] * 16
    verse_hihat = [(note_value('C#2'), 70, 0.03), (note_value('C#2'), 40, 0.03)]*64 if randint(0, 1) else [None for x in range(128)]
    verse_melody = generate_melody(key, verse_progression, major)

    chorus_progression = generate_progression(4, major=major, seed=verse_progression[-1])
    chorus_chords = []
    for _ in range(4):
        for chord in chorus_progression:
            chorus_chords.append((get_chord(chord, note_value(key+'2')), 80, 1.0))
            chorus_chords.extend([None for x in range(7)])
    chorus_arp = []
    for _ in range(4):
        for chord in chorus_progression:
            notes_ = get_chord(chord, note_value(key+'2'))
            for note in (notes_ + [notes_[1]] if len(notes_) == 3 else notes_):
                chorus_arp.append((note, 80, 0.25))
                chorus_arp.append(None)
    snare = [ randint(20, 50) if int(randint(0, ghost_note_penalty)*1.0/ghost_note_penalty) else 0 for _ in range(8) ]
    snare[2] = 80
    snare[6] = 80
    bass = [ randint(30, 80) if int(randint(0, 2*ghost_note_penalty)/(2.0*ghost_note_penalty)) and i not in (2, 6) else 0 for i in range(8) ]
    chorus_snare = [ (note_value('G1'), x, 0.03) if x else None for x in snare ] * 16
    chorus_bass = [ (note_value('C1'), x, 0.03) if x else None for x in bass ] * 16
    chorus_hihat = [(note_value('C#2'), 70, 0.03), (note_value('C#2'), 40, 0.03)]*64 if randint(0, 1) else [None for x in range(128)]
    chorus_melody = generate_melody(key, verse_progression, major)

    instruments = [(4, 0), (5, 0), (6, 0), (7, 0), (8, 0)]
    # Only use violin/cello for slower tempos (the sample packs are slow to respond)
    if tempo <= 140:
        instruments.extend([(9, -12), (10, 12)])

    bass_arp_instrument = [3, 11][randint(0, 1)]
    drum_instrument = [2, 12, 13, 14][randint(0, 3)]

    verse_instrument = instruments[randint(0, len(instruments)-1)]
    chorus_instrument = instruments[randint(0, len(instruments)-1)]

    print 'starting playback {}bpm'.format(tempo)
    for i in range(128):
        for note in verse_chords[i][0] if verse_chords[i] else []:
            play(note, verse_chords[i][1], verse_chords[i][2]*seconds_per_beat*4, channel=0)
        for note in verse_rhythm_chords[i][0] if verse_rhythm_chords[i] else []:
            play(note, verse_rhythm_chords[i][1], ((0.167 if i%2 == 0 else 0.083) if swing else 0.125)*seconds_per_beat*4, channel=1)
        for event in [(verse_arp[i], 1),
                      ((verse_arp[i][0]-12, verse_arp[i][1], verse_arp[i][2]) if verse_arp[i] else None, bass_arp_instrument),
                      (verse_snare[i], drum_instrument),
                      (verse_bass[i], drum_instrument),
                      (verse_hihat[i], drum_instrument),
                      ((verse_melody[i][0]+verse_instrument[1], verse_melody[i][1], verse_melody[i][2]) if verse_melody[i] else None, verse_instrument[0])]:
            if event[0]:
                if swing and event[0][2] == 0.125:
                    duration = 0.167 if i%2 == 0 else 0.083
                else:
                    duration = event[0][2]
                play(event[0][0], event[0][1], duration*seconds_per_beat*4, channel=event[1])
        time.sleep(((0.667 if i%2==0 else 0.333) if swing else 0.5)*seconds_per_beat)
    for i in range(128):
        for note in chorus_chords[i][0] if chorus_chords[i] else []:
            play(note, chorus_chords[i][1], chorus_chords[i][2]*seconds_per_beat*4, channel=0)
        for event in [(chorus_arp[i], 1),
                      ((chorus_arp[i][0]-12, chorus_arp[i][1], chorus_arp[i][2]) if chorus_arp[i] else None, bass_arp_instrument),
                      (chorus_snare[i], drum_instrument),
                      (chorus_bass[i], drum_instrument),
                      (chorus_hihat[i], drum_instrument),
                      ((chorus_melody[i][0]+chorus_instrument[1], chorus_melody[i][1], chorus_melody[i][2]) if chorus_melody[i] else None, chorus_instrument[0])]:
            if event[0]:
                if swing and event[0][2] == 0.125:
                    duration = 0.167 if i%2 == 0 else 0.083
                else:
                    duration = event[0][2]
                play(event[0][0], event[0][1], duration*seconds_per_beat*4, channel=event[1])
        time.sleep(((0.667 if i%2==0 else 0.333) if swing else 0.5)*seconds_per_beat)
    for i in range(128):
        for note in verse_chords[i][0] if verse_chords[i] else []:
            play(note, verse_chords[i][1], verse_chords[i][2]*seconds_per_beat*4, channel=0)
        for event in [(verse_arp[i], 1),
                      ((verse_arp[i][0]-12, verse_arp[i][1], verse_arp[i][2]) if verse_arp[i] else None, bass_arp_instrument),
                      (verse_snare[i], drum_instrument),
                      (verse_bass[i], drum_instrument),
                      (verse_hihat[i], drum_instrument),
                      ((verse_melody[i][0]+verse_instrument[1], verse_melody[i][1], verse_melody[i][2]) if verse_melody[i] else None, verse_instrument[0])]:
            if event[0]:
                if swing and event[0][2] == 0.125:
                    duration = 0.167 if i%2 == 0 else 0.083
                else:
                    duration = event[0][2]
                play(event[0][0], event[0][1], duration*seconds_per_beat*4, channel=event[1])
        time.sleep(((0.667 if i%2==0 else 0.333) if swing else 0.5)*seconds_per_beat)
    for note in verse_chords[0][0]:
        play(note, verse_chords[0][1], verse_chords[0][2]*seconds_per_beat*4, channel=0)
    for event in [(verse_arp[0], 1),
                  ((verse_arp[0][0]-12, verse_arp[0][1], verse_arp[0][2]) if verse_arp[0] else None, bass_arp_instrument),
                  (verse_snare[0], drum_instrument),
                  (verse_bass[0], drum_instrument),
                  (verse_hihat[0], drum_instrument),
                  ((note_value('D3'), 90, 0.1), drum_instrument),
                  ((verse_arp[0][0]+verse_instrument[1], verse_melody[0][1], verse_melody[0][2]) if verse_melody[0] else None, verse_instrument[0])]:
        if event[0]:
            play(event[0][0], event[0][1], seconds_per_beat*4, channel=event[1])
    # enable_hihat = randint(0, 1)
    # for _ in range(4):
    #     for chord in verse:
    #         notes_ = get_chord(chord, note_value(key+'2'))
    #         for note in get_chord(chord, note_value(key+'2')):
    #             play(note, 80, 1, channel=0)
    #         for i, note in enumerate(notes_ + [notes_[1]] if len(notes_) == 3 else notes_):
    #             mutex.acquire()
    #             output.send(mido.Message('control_change', control=64, value=127, channel=1))
    #             mutex.release()
    #             play(note, 80, 0.5*seconds_per_beat, channel=1)
    #             play(note-12, 100+randint(0, 20)-10, 0.5*seconds_per_beat, channel=3)
    #             play(melody[verse.index(chord)*4+i], 80, 0.5*seconds_per_beat, channel=4)
    #             pause = 0.333 if swing else 0.25
    #             print verse.index(chord)*4+i
    #             if enable_hihat:
    #                 play(note_value('C#2'), 70, pause*seconds_per_beat, channel=2)
    #             if snare[i*2]:
    #                 play(note_value('G1'), snare[i*2], pause*seconds_per_beat, channel=2)
    #             if bass[i*2]:
    #                 play(note_value('C1'), bass[i*2], pause*seconds_per_beat, channel=2)
    #             time.sleep(pause*seconds_per_beat)
    #             pause = 0.167 if swing else 0.25
    #             if enable_hihat and tempo <= 110:
    #                 play(note_value('C#2'), 40, pause*seconds_per_beat, channel=2)
    #             if snare[i*2+1]:
    #                 play(note_value('G1'), snare[i*2+1], pause*seconds_per_beat, channel=2)
    #             if bass[i*2+1]:
    #                 play(note_value('C1'), bass[i*2+1], pause*seconds_per_beat, channel=2)
    #             time.sleep(pause*seconds_per_beat)
    #         mutex.acquire()
    #         output.send(mido.Message('control_change', control=64, value=0, channel=1))
    #         mutex.release()
    # # Mix it up!
    # snare = [ randint(20, 50) if int(randint(0, ghost_note_penalty)*1.0/ghost_note_penalty) else 0 for _ in range(8) ]
    # snare[2] = 80
    # snare[6] = 80
    # bass = [ randint(30, 80) if int(randint(0, 2*ghost_note_penalty)/(2.0*ghost_note_penalty)) and i not in (2, 6) else 0 for i in range(8) ]
    # enable_hihat = randint(0, 1)
    # for _ in range(4):
    #     for chord in chorus:
    #         notes_ = get_chord(chord, note_value(key+'2'))
    #         for note in get_chord(chord, note_value(key+'2')):
    #             play(note, 80, 1, channel=0)
    #         for i, note in enumerate(notes_ + [notes_[1]] if len(notes_) == 3 else notes_):
    #             mutex.acquire()
    #             output.send(mido.Message('control_change', control=64, value=127, channel=1))
    #             mutex.release()
    #             play(note, 80, 0.5*seconds_per_beat, channel=1)
    #             play(note-12, 100+randint(0, 20)-10, 0.5*seconds_per_beat, channel=3)
    #             pause = 0.333 if swing else 0.25
    #             if enable_hihat:
    #                 play(note_value('C#2'), 70, pause*seconds_per_beat, channel=2)
    #             if snare[i*2]:
    #                 play(note_value('G1'), snare[i*2], pause*seconds_per_beat, channel=2)
    #             if bass[i*2]:
    #                 play(note_value('C1'), bass[i*2], pause*seconds_per_beat, channel=2)
    #             time.sleep(pause*seconds_per_beat)
    #             pause = 0.167 if swing else pause
    #             if enable_hihat and tempo <= 110:
    #                 play(note_value('C#2'), 40, pause*seconds_per_beat, channel=2)
    #             if snare[i*2+1]:
    #                 play(note_value('G1'), snare[i*2+1], pause*seconds_per_beat, channel=2)
    #             if bass[i*2+1]:
    #                 play(note_value('C1'), bass[i*2+1], pause*seconds_per_beat, channel=2)
    #             time.sleep(pause*seconds_per_beat)
    #         mutex.acquire()
    #         output.send(mido.Message('control_change', control=64, value=0, channel=1))
    #         mutex.release()
