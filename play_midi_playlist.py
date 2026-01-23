#!/usr/bin/env python3
"""
MIDI Playlist Player for 3D Printer.

Usage:
    python play_midi_playlist.py <playlist.yaml>
    python play_midi_playlist.py <playlist.yaml> --shuffle

Features:
- Homes printer once at startup
- Plays MIDI files from a YAML playlist
- Supports time trimming (start/end seconds)
- Auto-selects track and transpose (or uses specified values)
- Ctrl+C to skip to next track
- Dynamically reloads YAML between tracks (allows live editing)
- Shuffle mode persists to YAML
"""

import argparse
import signal
import sys
from typing import Optional

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
from src.playlist_manager import PlaylistManager


# Global flag for interrupt handling
interrupted = False
skip_current_track = False


def signal_handler(signum, frame):
    """Handle Ctrl+C interrupt."""
    global interrupted, skip_current_track

    if not interrupted:
        # First interrupt: skip current track
        print("\n\n⚠ Ctrl+C detected - skipping to next track...")
        skip_current_track = True
        interrupted = True
    else:
        # Second interrupt: exit program
        print("\n\n⚠ Ctrl+C detected again - exiting playlist...")
        sys.exit(0)


def parse_track_value(track_value) -> Optional[int]:
    """
    Parse track value from YAML.

    Args:
        track_value: Either 'auto', an integer, or None

    Returns:
        Integer track index or None for auto-selection
    """
    if track_value is None or (isinstance(track_value, str) and track_value.lower() == 'auto'):
        return None
    return int(track_value)


def parse_transpose_value(transpose_value) -> tuple[bool, int]:
    """
    Parse transpose value from YAML.

    Args:
        transpose_value: Either 'auto', an integer, or None

    Returns:
        Tuple of (auto_transpose, transpose_semitones)
    """
    if transpose_value is None:
        return False, 0
    if isinstance(transpose_value, str) and transpose_value.lower() == 'auto':
        return True, 0
    return False, int(transpose_value)


def play_track(
    player: NotePlayer,
    melody: list,
    track_name: str,
    item_index: int
) -> bool:
    """
    Play a track with interrupt handling.

    Args:
        player: NotePlayer instance
        melody: Melody sequence (list of (frequency, duration, volume) tuples)
        track_name: Name of track for display
        item_index: Index in playlist for display

    Returns:
        True if completed normally, False if interrupted
    """
    global skip_current_track

    print(f"\n=== Playing Track {item_index + 1}: {track_name} ===\n")

    for i, (frequency, duration, volume) in enumerate(melody):
        # Check for interrupt
        if skip_current_track:
            print("\n⚠ Track skipped")
            return False

        if frequency is None:
            # Rest (pause)
            print(f"[{i+1}/{len(melody)}] Rest: {duration:.2f}s")
            player.pause(duration)
        else:
            # Note
            print(f"[{i+1}/{len(melody)}] {frequency:.1f} Hz for {duration:.2f}s (volume: {volume})")
            try:
                player.play_note(frequency, frequency, duration, volume=volume, debug=False)
            except Exception as e:
                print(f"  ⚠ Skipping note: {e}")
                player.pause(duration)

    print("\n✓ Track complete!")
    return True


def main():
    """Main playlist player entry point."""
    global interrupted, skip_current_track

    # Parse command line arguments
    parser = argparse.ArgumentParser(description='Play a MIDI playlist on 3D printer')
    parser.add_argument('playlist', help='Path to playlist YAML file')
    parser.add_argument('--shuffle', action='store_true', help='Shuffle the playlist')
    args = parser.parse_args()

    # Set up interrupt handler
    signal.signal(signal.SIGINT, signal_handler)

    print(f"=== MIDI Playlist Player ===")
    print(f"Playlist: {args.playlist}")
    if args.shuffle:
        print("Mode: Shuffle")
    print()

    # Initialize playlist manager
    try:
        playlist_manager = PlaylistManager(args.playlist)
        playlist_manager.load_playlist()

        # Apply shuffle if requested
        if args.shuffle:
            print("Shuffling playlist...")
            playlist_manager.shuffle()
            print("✓ Playlist items shuffled and saved to YAML\n")

    except FileNotFoundError:
        print(f"Error: Playlist file '{args.playlist}' not found")
        sys.exit(1)
    except Exception as e:
        print(f"Error loading playlist: {e}")
        sys.exit(1)

    # Connect to printer
    print("=== Connecting to Printer ===")
    try:
        port = find_printer_port()
        ser = connect_to_printer(port)
    except Exception as e:
        print(f"Error connecting to printer: {e}")
        sys.exit(1)

    # Initialize printer (home and position) - ONCE
    tracker = AbsolutePositionTracker()
    planner = MotionPlanner(SAFE_LIMITS)
    player = NotePlayer(ser, tracker, planner)

    try:
        print("Initializing printer (homing)...")
        initialize_printer_position(ser, tracker)
        print("✓ Printer ready\n")

        # Main playback loop
        track_count = 0
        while True:
            # Reset interrupt flags for this track
            interrupted = False
            skip_current_track = False

            # Reload playlist from YAML (allows live editing)
            try:
                playlist_manager.load_playlist()
            except Exception as e:
                print(f"Error reloading playlist: {e}")
                break

            # Get next unplayed item
            next_item = playlist_manager.get_next_unplayed_item()
            if next_item is None:
                print("\n✓ All tracks completed!")
                print("Resetting playlist before ending...")
                playlist_manager.reset_played_status()
                continue

            item_index, item = next_item
            track_count += 1

            # Extract item parameters
            filename = item.get('filename')
            if filename is None:
                print(f"Error: Playlist item {item_index + 1} missing 'filename'")
                playlist_manager.mark_as_played(item_index)
                continue
            start_seconds = item.get('start_seconds', 0)
            end_seconds = item.get('end_seconds')
            track_value = item.get('track')
            transpose_value = item.get('transpose')

            print(f"\n{'='*60}")
            print(f"Track {track_count}: {filename}")
            print(f"  Start: {start_seconds}s, End: {end_seconds if end_seconds else 'end of file'}")
            print(f"  Track: {track_value}, Transpose: {transpose_value}")
            print(f"{'='*60}\n")

            # Parse track and transpose settings
            track_index = parse_track_value(track_value)
            auto_transpose, transpose_semitones = parse_transpose_value(transpose_value)

            # Parse MIDI file
            try:
                print(f"Parsing MIDI file: {filename}")

                # First parse without transposition to analyze
                notes_original, selected_track = parse_midi_file(
                    filename,
                    track_index=track_index,
                    tempo_scale=1.0,
                    start_time=start_seconds,
                    end_time=end_seconds
                )

                print(f"Found melody in track {selected_track}")
                print_melody_summary(notes_original)

                # Handle auto-transpose
                if auto_transpose:
                    print("\n=== Auto-Transpose Analysis ===")
                    target_range = FREQUENCY_RANGES["Y"]
                    transposer = Transposer(target_range)
                    suggested_semitones, transposed_notes = transposer.analyze(notes_original)

                    if suggested_semitones != 0:
                        print(f"Auto-applying transpose: {suggested_semitones:+d} semitones")
                        transpose_semitones = suggested_semitones
                    else:
                        print("No transposition needed")

                # Parse again with the chosen transpose
                if transpose_semitones != 0:
                    print(f"\n=== Applying Transpose: {transpose_semitones:+d} semitones ===")
                    notes, _ = parse_midi_file(
                        filename,
                        track_index=selected_track,
                        tempo_scale=1.0,
                        transpose_semitones=transpose_semitones,
                        start_time=start_seconds,
                        end_time=end_seconds
                    )
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
                print("Marking as played and continuing to next track...")
                playlist_manager.mark_as_played(item_index)
                continue

            # Play the track
            try:
                completed = play_track(player, melody, filename, item_index)

                if not completed:
                    print(f"Track was interrupted")

            except Exception as e:
                print(f"Error playing track: {e}")

            # Mark as played regardless of how it ended
            playlist_manager.mark_as_played(item_index)
            print(f"Marked track {item_index + 1} as played")

    finally:
        print("\n=== Cleaning Up ===")
        send_gcode_with_retry(ser, "M84")
        ser.close()
        print("Done!")


if __name__ == "__main__":
    main()
