#!/usr/bin/env python3
"""Test different track/time options for swan-lake.mid"""

from src.midi_parser import parse_midi_file, print_melody_summary

filename = "library/swan-lake.mid"
transpose_semitones = 16

print("=" * 70)
print("OPTION 1: Track 4 (OBOE), 0-5 seconds")
print("=" * 70)
notes1, _ = parse_midi_file(filename, track_index=4, transpose_semitones=transpose_semitones, start_time=0, end_time=5)
print(f"Found {len(notes1)} notes")
print_melody_summary(notes1)

print("\n" + "=" * 70)
print("OPTION 2: Track 4 (OBOE), 4-10 seconds (more notes)")
print("=" * 70)
notes2, _ = parse_midi_file(filename, track_index=4, transpose_semitones=transpose_semitones, start_time=4, end_time=10)
print(f"Found {len(notes2)} notes")
print_melody_summary(notes2)

print("\n" + "=" * 70)
print("OPTION 3: Track 1 (HARP), 0-5 seconds (more notes)")
print("=" * 70)
notes3, _ = parse_midi_file(filename, track_index=1, transpose_semitones=transpose_semitones, start_time=0, end_time=5)
print(f"Found {len(notes3)} notes")
print_melody_summary(notes3)

print("\n" + "=" * 70)
print("OPTION 4: Track 1 (HARP), 2-7 seconds (even more notes)")
print("=" * 70)
notes4, _ = parse_midi_file(filename, track_index=1, transpose_semitones=transpose_semitones, start_time=2, end_time=7)
print(f"Found {len(notes4)} notes")
print_melody_summary(notes4)

print("\n" + "=" * 70)
print("OPTION 5: Auto-select track (let it pick the best), 0-5 seconds")
print("=" * 70)
notes5, track5 = parse_midi_file(filename, track_index=None, transpose_semitones=transpose_semitones, start_time=0, end_time=5)
print(f"Selected track: {track5}")
print(f"Found {len(notes5)} notes")
print_melody_summary(notes5)
