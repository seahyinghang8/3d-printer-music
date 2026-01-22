#!/usr/bin/env python3
"""Test the fixed playlist settings"""

from src.midi_parser import parse_midi_file, print_melody_summary

# Parse the file with TRACK 4 (OBOE) instead of track 2
filename = "library/swan-lake.mid"
track_index = 4  # Changed from 2 to 4
start_seconds = 0
end_seconds = 5
transpose_semitones = 16

print(f"=== Testing Track {track_index} (OBOE) ===")
print(f"Time range: {start_seconds}s - {end_seconds}s")
print(f"Transpose: +{transpose_semitones} semitones")
print()

notes, selected_track = parse_midi_file(
    filename,
    track_index=track_index,
    tempo_scale=1.0,
    transpose_semitones=transpose_semitones,
    start_time=start_seconds,
    end_time=end_seconds
)

print(f"Found {len(notes)} notes")
print_melody_summary(notes)

if notes:
    print("\n=== All notes ===")
    for i, note in enumerate(notes):
        print(f"{i+1}. Start: {note.start_time:.3f}s, Duration: {note.duration:.3f}s, Freq: {note.frequency:.1f}Hz, Vel: {note.velocity}")
