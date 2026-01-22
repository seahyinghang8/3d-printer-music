#!/usr/bin/env python3
"""Debug script to explore swan-lake.mid tracks and timing"""

import mido

filename = "library/swan-lake.mid"
midi_file = mido.MidiFile(filename)

print(f"=== MIDI File: {filename} ===")
print(f"Number of tracks: {len(midi_file.tracks)}")
print(f"Ticks per beat: {midi_file.ticks_per_beat}")
print()

# Analyze each track
for track_idx, track in enumerate(midi_file.tracks):
    print(f"\n=== Track {track_idx} ===")
    print(f"Track name: {track.name if hasattr(track, 'name') else 'N/A'}")

    # Count note events
    note_ons = []
    current_time = 0.0
    microseconds_per_beat = 500000

    for msg in track:
        delta_seconds = mido.tick2second(
            msg.time,
            midi_file.ticks_per_beat,
            microseconds_per_beat
        )
        current_time += delta_seconds

        if msg.type == 'set_tempo':
            microseconds_per_beat = msg.tempo

        if msg.type == 'note_on' and msg.velocity > 0:
            note_ons.append((current_time, msg.note, msg.velocity))

    print(f"Total note_on events: {len(note_ons)}")

    if note_ons:
        # Show timing info
        first_note_time = note_ons[0][0]
        last_note_time = note_ons[-1][0]
        print(f"First note at: {first_note_time:.2f}s")
        print(f"Last note at: {last_note_time:.2f}s")
        print(f"Duration: {last_note_time - first_note_time:.2f}s")

        # Show first 5 notes
        print(f"\nFirst 5 notes:")
        for i, (time, note, vel) in enumerate(note_ons[:5]):
            print(f"  {i+1}. Time: {time:.3f}s, Note: {note}, Velocity: {vel}")

        # Show notes in 0-5s range
        notes_in_range = [(t, n, v) for t, n, v in note_ons if 0 <= t <= 5]
        print(f"\nNotes starting between 0-5s: {len(notes_in_range)}")
        if notes_in_range:
            for i, (time, note, vel) in enumerate(notes_in_range[:10]):
                print(f"  {i+1}. Time: {time:.3f}s, Note: {note}, Velocity: {vel}")
