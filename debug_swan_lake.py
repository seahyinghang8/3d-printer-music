#!/usr/bin/env python3
"""Debug script to check what notes exist in swan-lake.mid"""

from src.midi_parser import parse_midi_file, print_melody_summary

# Parse the file with the same settings as playlist
filename = "library/swan-lake.mid"
track_index = 2
start_seconds = 0
end_seconds = 5
transpose_semitones = 0  # First without transpose

print(f"=== Parsing {filename} ===")
print(f"Track: {track_index}, Start: {start_seconds}s, End: {end_seconds}s")
print()

# Parse without transpose
print("WITHOUT transpose:")
notes, selected_track = parse_midi_file(
    filename,
    track_index=track_index,
    tempo_scale=1.0,
    start_time=start_seconds,
    end_time=end_seconds
)
print(f"Found {len(notes)} notes")
print_melody_summary(notes)

print("\n" + "="*60 + "\n")

# Parse with transpose
print("WITH transpose +16:")
notes_transposed, _ = parse_midi_file(
    filename,
    track_index=track_index,
    tempo_scale=1.0,
    transpose_semitones=16,
    start_time=start_seconds,
    end_time=end_seconds
)
print(f"Found {len(notes_transposed)} notes")
print_melody_summary(notes_transposed)

# Show all notes if there are any
if notes:
    print("\n=== First 10 notes (no transpose) ===")
    for i, note in enumerate(notes[:10]):
        print(f"{i+1}. Start: {note.start_time:.3f}s, Duration: {note.duration:.3f}s, Freq: {note.frequency:.1f}Hz")
