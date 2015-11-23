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

# Relative positions of notes in major/minor scales (e.g. any major scale goes
# base note, whole step, whole step, half step, whole step, whole step, whole
# step, half step)
major_scale_progression = [0, 2, 4, 5, 7, 9, 11, 12]
minor_scale_progression = [0, 2, 3, 5, 7, 8, 10, 12]

# Valid chords that can be transitioned to from some given diatonic triad.
# Taken from http://www.angelfire.com/music/HarpOn/theory2.html
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

# Produces the MIDI numbers (in relation to the base note) for a minor
# diatonic triad given the major chord symbol (e.g. major_chord_to_minor('I')
# gives the minor sequence [0, 3, 7])
def major_chord_to_minor(symbol):
    minor = list(triad_notes[symbol])
    minor[1] -= 1
    return minor

# Defines the MIDI numbers (in relation to the base note) for diatonic triads.
# These can be combined with the base note to produce chords with MIDI. For
# example, the I chord with base note middle C (60) could be produced with the
# MIDI note numbers [60+0, 60+4, 60+7]
triad_notes = {
    'I': [0, 4, 7],
    'II': [2, 6, 9],
    'III': [4, 8, 11],
    'IV': [5, 9, 12],
    'V': [7, 11, 14],
    'VI': [9, 13, 16],
    'VII': [11, 15, 18],
    'ii0': [1, 4, 7, 9],
    'vii0': [0, 4, 7, 10]
}
triad_notes['i'] = major_chord_to_minor('I')
triad_notes['ii'] = major_chord_to_minor('II')
triad_notes['iii'] = major_chord_to_minor('III')
triad_notes['iv'] = major_chord_to_minor('IV')
triad_notes['v'] = major_chord_to_minor('V')
triad_notes['vi'] = major_chord_to_minor('VI')
triad_notes['vii'] = major_chord_to_minor('VII')

# Open MIDI virtual output device
output = mido.open_output()

# Calling mido is not thread-safe. We segfault if we're trying to play a bunch
# of notes using different threads
mido_mutex = Lock()

# We play each note in its own thread. This is inefficient, but it lets us
# deal with note lengths much more easily. Instead of trying to track which
# notes are playing and need to be stopped when, we just start a thread that
# will send the note_off message at the appropriate time. Not the ideal
# solution but it's the easiest to implement
def _play(note, vel, duration, channel=1):
    mido_mutex.acquire()
    try:
        msg = mido.Message('note_on', note=note, velocity=vel, channel=channel)
        msg.channel = channel
        output.send(msg)
    finally:
        mido_mutex.release()
    time.sleep(duration)
    mido_mutex.acquire()
    try:
        msg = mido.Message('note_off', note=note, velocity=vel, channel=channel)
        msg.channel = channel
        output.send(msg)
    finally:
        mido_mutex.release()

def play(note, vel, duration, channel=1):
    """
    Plays a note (specified as an integer, e.g. 60 for middle C) at a given
    velocity for a given duration (in seconds) over a given MIDI channel.
    """
    Thread(target=_play, args=(note, vel, duration, channel)).start()

# major_scales = ['Cb', 'Gb', 'Db', 'Ab', 'Eb', 'Bb', 'F', 'C', 'G', 'D', 'A', 'E', 'B', 'F#', 'C#']
# minor_scales = ['Ab', 'Eb', 'Bb', 'F', 'C', 'G', 'D', 'A', 'E', 'B', 'F#', 'C#', 'G#', 'D#', 'A#']
# def minor_to_major(scale):
#     return major_scales[minor_scales.index(scale)]

def note_number(note):
    """
    Returns the MIDI note number for a given note name (e.g. "C#4")
    """
    try:
        note, octave = re.match(r'^([A-Z][b#]?)(\d+)$', note[0].upper()+note[1:]).groups()
    except AttributeError:
        raise Exception('Bad note input to note_number %r' % note)

    if note in note_remap.keys():
        note = note_remap[note]

    position_in_octave = keys_in_octave.index(note)

    return (int(octave)+2)*12 + position_in_octave

def generate_scale(name, octave, major=True):
    """
    Generates a sequence of MIDI note numbers for a scale (do re mi fa sol la
    si do). `name` specifies the base note, `octave` specifies in which octave
    the scale should be, and `major` designates whether the produced scale
    should be major or minor.
    """
    scale = major_scale_progression if major else minor_scale_progression
    base_note = note_number(name+str(octave))
    return [ base_note + x for x in scale ]

def get_chord(symbol, base_note):
    """
    Generates a list of MIDI note numbers representing a diatonic triad chord
    given the roman numeral symbol and a base note (e.g. get_chord('I', 60)
    will return [60, 64, 67] which is the first diatonic triad in C major
    starting at middle C).
    """
    return [triad_notes[symbol][i] + base_note for i in range(len(triad_notes[symbol]))]

def play_progression(*args):
    """
    Plays a chord progression in C major given a series of diatonic triads in
    roman numeral form (e.g. play_progression('iii', 'vi', 'ii', 'V'))
    """
    for x in args:
        for note in get_chord(x, note_number('C5')):
            play(note, 80, 1)
        time.sleep(1)

def pick_next_chord(seed, transitions):
    """
    Given a current chord and a graph with valid transitions (see
    transitions_major or transitions_minor), picks the next chord in a
    progression
    """
    return transitions[seed][randint(0, len(transitions[seed])-1)]

def generate_progression(bars, major=True, seed=None):
    """
    Generates an n-bar chord progression. Returns a list of roman numerals
    representing the chords (for any key). `major` specifies whether a major
    key is being used. If `seed` is provided, the progression will be
    generated such that `seed` transitions to the first chord of the
    progression; otherwise, a random first chord will be chosen.
    """
    transitions = transitions_major if major else transitions_minor
    progression = [ pick_next_chord(seed, transitions) if seed else transitions.keys()[randint(0, len(transitions.keys())-1)] ]
    for _ in range(bars - 1):
        progression.append(pick_next_chord(progression[-1], transitions))
    return progression

def generate_melody(key, progression, progression_repeats, major=True):
    """
    Generates a {len(progression)*progression_repeats}-bar melody given a key,
    chord progression, and whether or not the key is a major key.
    """
    out = []
    for _ in range(progression_repeats):
        time_used = 0.0     # Number of measures that have been generated so far
        for i, chord in enumerate(progression):
            all_tones = generate_scale(key, 2, major)
            chord_tones = get_chord(chord, note_number(key+'2'))
            chord_tones.extend([x+12 for x in chord_tones])
            non_chord_tones = list(set(all_tones[:-1]) - set(chord_tones))
            non_chord_tones.extend([x+12 for x in non_chord_tones])
            last_played = None

            # Generate a sequence of notes to fill a measure for this chord
            while time_used < i + 1:
                note_vals = [(0.125, 2), (0.25, 4), (0.375, 2), (0.5, 2), (0.75, 1), (1.0, 1), (1.25, 0.5), (1.5, 0.25)]
                # Only allow note lengths that will fit into the len(progression)
                # measures for this chord progression (i.e. don't allow spill
                # of notes into different repetitions of the progression)
                possible_note_vals = [x for x, p in note_vals if time_used + x <= len(progression)]
                note_vals_prob = [p for x, p in note_vals if time_used + x <= len(progression)]
                note_vals_prob = [x*1.0/sum(note_vals_prob) for x in note_vals_prob]
                # Choose a note length
                note_val = numpy.random.choice(possible_note_vals, p=note_vals_prob)
                # Choose the set of note numbers we could pick from (either
                # the chord tones or non-chord tones)
                select_from = non_chord_tones if int(randint(0, 10)/10.0) else chord_tones
                # Incentivize choosing notes that are close to the previously
                # played note so that we aren't just jumping all over the
                # place and sounding terribly random
                NEARBY_INCENTIVE = 2.0
                select_from_probabilities = [ (36 - int(math.fabs(last_played - x)))**NEARBY_INCENTIVE if last_played else 1 for x in select_from ]
                select_from_probabilities = [ x * 1.0 / sum(select_from_probabilities) for x in select_from_probabilities ]
                out.append((numpy.random.choice(select_from, p=select_from_probabilities), 80, note_val))
                last_played = out[-1][0]
                out.extend([None for x in range(int(note_val/0.125)-1)])
                time_used += note_val
    assert len(out) == 8 * len(progression) * progression_repeats
    return out

if __name__ == '__main__':
    # Choose tempo, key, and whether or not we have a swing feel
    tempo = randint(100, 200)
    print "Tempo: {}bpm".format(tempo)
    seconds_per_beat = 60.0/tempo
    # major = bool(randint(0, 1))
    major = True
    key = keys_in_octave[randint(0, len(keys_in_octave)-1)]
    print "Key: {} major".format(key)
    swing = bool(randint(0, 1))
    print "Swing feel: {}".format(swing)

    verse_progression = generate_progression(4, major=major)
    print "Verse progression: {}".format(verse_progression)
    verse_chords = []
    for _ in range(4):
        for chord in verse_progression:
            verse_chords.append((get_chord(chord, note_number(key+'2')), 80, 1.0))
            verse_chords.extend([None for x in range(7)])
    verse_rhythm_chords = []
    for _ in range(4):
        for chord in verse_progression:
            verse_rhythm_chords.extend([(get_chord(chord, note_number(key+'2')), 80, 0.125),
                                        (get_chord(chord, note_number(key+'2')), 60, 0.125)]*4)
    verse_arp = []
    for _ in range(4):
        for chord in verse_progression:
            notes_ = get_chord(chord, note_number(key+'2'))
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
    verse_snare = [ (note_number('G1'), x, 0.03) if x else None for x in snare ] * 16
    verse_bass = [ (note_number('C1'), x, 0.03) if x else None for x in bass ] * 16
    verse_hihat = [(note_number('C#2'), 70, 0.03), (note_number('C#2'), 40, 0.03)]*64 if randint(0, 1) else [None for x in range(128)]
    melody_repeats = 2*int(randint(3, 6)/3.0)   # Either 2 or 4
    verse_melody = generate_melody(key, verse_progression, melody_repeats, major)
    if melody_repeats == 2:
        verse_melody = verse_melody * 2

    chorus_progression = generate_progression(4, major=major, seed=verse_progression[-1])
    print "Chorus progression: {}".format(chorus_progression)
    chorus_chords = []
    for _ in range(4):
        for chord in chorus_progression:
            chorus_chords.append((get_chord(chord, note_number(key+'2')), 80, 1.0))
            chorus_chords.extend([None for x in range(7)])
    chorus_arp = []
    for _ in range(4):
        for chord in chorus_progression:
            notes_ = get_chord(chord, note_number(key+'2'))
            for note in (notes_ + [notes_[1]] if len(notes_) == 3 else notes_):
                chorus_arp.append((note, 80, 0.25))
                chorus_arp.append(None)
    snare = [ randint(20, 50) if int(randint(0, ghost_note_penalty)*1.0/ghost_note_penalty) else 0 for _ in range(8) ]
    snare[2] = 80
    snare[6] = 80
    bass = [ randint(30, 80) if int(randint(0, 2*ghost_note_penalty)/(2.0*ghost_note_penalty)) and i not in (2, 6) else 0 for i in range(8) ]
    chorus_snare = [ (note_number('G1'), x, 0.03) if x else None for x in snare ] * 16
    chorus_bass = [ (note_number('C1'), x, 0.03) if x else None for x in bass ] * 16
    chorus_hihat = [(note_number('C#2'), 70, 0.03), (note_number('C#2'), 40, 0.03)]*64 if randint(0, 1) else [None for x in range(128)]
    melody_repeats = 2*int(randint(3, 6)/3.0)
    chorus_melody = generate_melody(key, verse_progression, melody_repeats, major)
    if melody_repeats == 2:
        chorus_melody = chorus_melody * 2

    instruments = [(4, 0), (5, 0), (6, 0), (7, 0), (8, 0)]
    # Only use violin/cello for slower tempos (the sample packs are slow to respond)
    if tempo <= 140:
        instruments.extend([(9, -12), (10, 12)])

    bass_arp_instrument = [3, 11][randint(0, 1)]
    drum_instrument = [2, 12, 13, 14][randint(0, 3)]

    verse_instrument = instruments[randint(0, len(instruments)-1)]
    chorus_instrument = instruments[randint(0, len(instruments)-1)]

    print 'starting playback'
    # Play verse
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
    # Play chorus
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
    # Play verse
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
    # End the song playing the first chord of the verse
    for note in verse_chords[0][0]:
        play(note, verse_chords[0][1], verse_chords[0][2]*seconds_per_beat*4, channel=0)
    for event in [(verse_arp[0], 1),
                  ((verse_arp[0][0]-12, verse_arp[0][1], verse_arp[0][2]) if verse_arp[0] else None, bass_arp_instrument),
                  (verse_snare[0], drum_instrument),
                  (verse_bass[0], drum_instrument),
                  (verse_hihat[0], drum_instrument),
                  ((note_number('D3'), 90, 0.1), drum_instrument),
                  ((verse_arp[0][0]+verse_instrument[1], verse_melody[0][1], verse_melody[0][2]) if verse_melody[0] else None, verse_instrument[0])]:
        if event[0]:
            play(event[0][0], event[0][1], seconds_per_beat*4, channel=event[1])
