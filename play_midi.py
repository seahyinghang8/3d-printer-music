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
    Transposer,
)
from src.midi_parser import parse_midi_file, extract_melody_with_rests, print_melody_summary

if len(sys.argv) < 2:
    print("Usage: python play_midi.py <midi_file> [track_index] [transpose_semitones]")
    print("\nExample:")
    print("  python play_midi.py library/song.mid              # auto-select best track")
    print("  python play_midi.py library/song.mid 1            # use specific track")
    print("  python play_midi.py library/song.mid 1 12         # transpose up 1 octave")
    print("  python play_midi.py library/song.mid auto auto    # auto-select track and transpose")
    print("\nTo preview tracks first, run:")
    print("  python preview_midi.py <midi_file>")
    sys.exit(1)

midi_path = sys.argv[1]

# Parse track_index argument (optional)
track_index = None
if len(sys.argv) >= 3 and sys.argv[2].lower() != "auto":
    track_index = int(sys.argv[2])

# Parse transpose argument
transpose_semitones = 0
auto_transpose = False
if len(sys.argv) >= 4:
    if sys.argv[3].lower() == "auto":
        auto_transpose = True
    else:
        transpose_semitones = int(sys.argv[3])
elif len(sys.argv) >= 3 and sys.argv[2].lower() == "auto":
    # Handle "python play_midi.py file.mid auto"
    auto_transpose = True

track_display = f"Track {track_index}" if track_index is not None else "Auto-select"
print(f"=== MIDI Playback: {midi_path} ({track_display}) ===\n")

# Parse MIDI file
print("Parsing MIDI file...")
try:
    # First parse without transposition to analyze
    notes_original, selected_track = parse_midi_file(midi_path, track_index=track_index, tempo_scale=1.0)

    print(f"Found melody in track {selected_track}")
    print_melody_summary(notes_original)

    # Handle auto-transpose
    if auto_transpose:
        print("\n=== Auto-Transpose Analysis ===")
        # Use Y axis frequency range as the target (it's the loudest axis)
        target_range = FREQUENCY_RANGES["Y"]
        transposer = Transposer(target_range)
        suggested_semitones, transposed_notes = transposer.analyze(notes_original)

        # Prompt user to apply the suggested transposition
        transpose_semitones = transposer.prompt_user_for_transposition(
            notes_original,
            suggested_semitones,
            transposed_notes
        )

    # Parse again with the chosen transpose
    if transpose_semitones != 0:
        print(f"\n=== Applying Transpose: {transpose_semitones:+d} semitones ===")
        notes, _ = parse_midi_file(midi_path, track_index=selected_track, tempo_scale=1.0, transpose_semitones=transpose_semitones)
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
    print(f"=== Playing Track {selected_track} ===\n")

    for i, (frequency, duration, volume) in enumerate(melody):
        if frequency is None:
            # Rest (pause)
            print(f"[{i+1}/{len(melody)}] Rest: {duration:.2f}s")
            player.pause(duration)
        else:
            # Note - all notes now play diagonally
            # For single note, pass same frequency twice
            print(f"[{i+1}/{len(melody)}] {frequency:.1f} Hz for {duration:.2f}s (volume: {volume})")
            try:
                # Play as diagonal movement (same frequency on both axes for single note)
                player.play_note(frequency, frequency, duration, volume=volume, debug=False)
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
