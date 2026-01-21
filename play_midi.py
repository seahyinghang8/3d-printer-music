#!/usr/bin/env python3
"""
Generic MIDI playback script for 3D printer.

Usage:
    python play_midi.py <midi_file> <track_index> [transpose_semitones]

Example:
    python play_midi.py library/song.mid 1
    python play_midi.py library/song.mid 1 12  # transpose up one octave
    python play_midi.py library/song.mid 1 auto  # auto-analyze and suggest transpose
"""

import sys
from typing import cast, Literal
from src import (
    find_printer_port,
    connect_to_printer,
    AbsolutePositionTracker,
    MotionPlanner,
    NotePlayer,
    initialize_printer_position,
    send_gcode_with_retry,
    SAFE_LIMITS,
    FREQUENCY_RANGES,
)
from src.midi_parser import parse_midi_file, extract_melody_with_rests, print_melody_summary, analyze_transposition

if len(sys.argv) < 3:
    print("Usage: python play_midi.py <midi_file> <track_index> [transpose_semitones]")
    print("\nExample:")
    print("  python play_midi.py library/song.mid 1")
    print("  python play_midi.py library/song.mid 1 12  # transpose up 1 octave")
    print("  python play_midi.py library/song.mid 1 auto  # auto-analyze")
    print("\nTo preview tracks first, run:")
    print("  python preview_midi.py <midi_file>")
    sys.exit(1)

midi_path = sys.argv[1]
track_index = int(sys.argv[2])

# Parse transpose argument
transpose_semitones = 0
auto_transpose = False
if len(sys.argv) >= 4:
    if sys.argv[3].lower() == "auto":
        auto_transpose = True
    else:
        transpose_semitones = int(sys.argv[3])

print(f"=== MIDI Playback: {midi_path} (Track {track_index}) ===\n")

# Parse MIDI file
print("Parsing MIDI file...")
try:
    # First parse without transposition to analyze
    notes_original = parse_midi_file(midi_path, track_index=track_index, tempo_scale=1.0)

    print(f"Found melody in track {track_index}")
    print_melody_summary(notes_original)

    # Handle auto-transpose
    if auto_transpose:
        print("\n=== Auto-Transpose Analysis ===")
        # Use Y axis frequency range as the target (it's the loudest axis)
        target_range = FREQUENCY_RANGES["Y"]
        suggested_semitones, transposed_notes = analyze_transposition(notes_original, target_range)

        if suggested_semitones > 0:
            octaves = suggested_semitones / 12
            print(f"Suggested transpose: +{suggested_semitones} semitones ({octaves:.1f} octaves)")
            print(f"Original range: {min(n.frequency for n in notes_original):.1f} - {max(n.frequency for n in notes_original):.1f} Hz")
            print(f"Transposed range: {min(n.frequency for n in transposed_notes):.1f} - {max(n.frequency for n in transposed_notes):.1f} Hz")

            # Ask user if they want to apply it
            response = input("\nApply this transposition? (y/n): ").strip().lower()
            if response == 'y':
                transpose_semitones = suggested_semitones
                print(f"✓ Applying +{transpose_semitones} semitones transpose")
            else:
                print("✓ Playing without transpose")
        else:
            print("No transposition needed - frequencies already in optimal range")

    # Parse again with the chosen transpose
    if transpose_semitones != 0:
        print(f"\n=== Applying Transpose: {transpose_semitones:+d} semitones ===")
        notes = parse_midi_file(midi_path, track_index=track_index, tempo_scale=1.0, transpose_semitones=transpose_semitones)
        print_melody_summary(notes)
    else:
        notes = notes_original

    # Extract melody with rests
    melody = extract_melody_with_rests(notes)
    print(f"\nMelody sequence: {len(melody)} events (notes + rests)")

    # Skip long rests at the beginning (>5 seconds)
    print("Skipping intro rests...")
    while melody and melody[0][0] is None and melody[0][1] > 5.0:
        print(f"  Skipping {melody[0][1]:.1f}s rest")
        melody.pop(0)

    print(f"Playing {len(melody)} events")

except Exception as e:
    print(f"Error parsing MIDI file: {e}")
    sys.exit(1)

# Connect to printer
print("\n=== Connecting to Printer ===")
port = find_printer_port()
ser = connect_to_printer(port)

# Initialize
tracker = AbsolutePositionTracker()
planner = MotionPlanner(SAFE_LIMITS)
player = NotePlayer(ser, tracker, planner)

try:
    # Initialize printer
    print("Initializing printer...")
    initialize_printer_position(ser, tracker)
    print("✓ Ready to play\n")

    # Play the melody
    print(f"=== Playing Track {track_index} ===\n")

    for i, (frequency, duration, volume) in enumerate(melody):
        if frequency is None:
            # Rest (pause)
            print(f"[{i+1}/{len(melody)}] Rest: {duration:.2f}s")
            player.pause(duration)
        else:
            # Note
            print(f"[{i+1}/{len(melody)}] {frequency:.1f} Hz for {duration:.2f}s (volume: {volume})")
            try:
                # Cast volume to satisfy type checker - we know it's one of the valid literal values
                volume_typed = cast(Literal["soft", "normal", "loud"], volume)
                player.play_note_with_volume(frequency, duration, volume_typed, debug=False)
            except Exception as e:
                print(f"  ⚠ Skipping note: {e}")
                # Skip notes that can't be played
                player.pause(duration)

    print("\n✓ Playback complete!")

finally:
    print("\nCleaning up...")
    send_gcode_with_retry(ser, "M84")
    ser.close()
    print("Done!")
