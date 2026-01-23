#!/usr/bin/env python3
"""
MIDI Preview Tool - Quickly preview tracks from MIDI files with audio playback.

Usage:
    python preview_midi.py <midi_file> [duration_seconds]

Controls:
    - Space: Pause/Resume
    - Q: Quit current preview
    - Enter: Skip to next track

Example:
    python preview_midi.py library/song.mid
    python preview_midi.py library/song.mid 20  # 20 second preview
"""

import sys
import mido
import pygame
import time
import threading
from pathlib import Path


class MIDIPreview:
    def __init__(self, midi_path: str, preview_duration: float = 30.0, start_offset: float = 0.0):
        """Initialize MIDI preview player.

        Args:
            midi_path: Path to MIDI file
            preview_duration: Duration of preview in seconds
            start_offset: Where to start the preview (seconds from beginning)
        """
        self.midi_path = midi_path
        self.preview_duration = preview_duration
        self.start_offset = start_offset
        self.mid = mido.MidiFile(midi_path)
        self.paused = False
        self.stopped = False
        self.skip_requested = False

        # Initialize pygame mixer for MIDI playback
        pygame.mixer.init(frequency=22050, size=-16, channels=2, buffer=512)
        pygame.init()

    def get_track_info(self):
        """Extract information about all tracks in the MIDI file."""
        track_info = []

        for i, track in enumerate(self.mid.tracks):
            note_count = sum(1 for msg in track if msg.type == 'note_on' and msg.velocity > 0)
            track_name = None

            # Try to find track name
            for msg in track:
                if msg.type == 'track_name':
                    track_name = msg.name
                    break

            if note_count > 0:  # Only include tracks with notes
                track_info.append({
                    'index': i,
                    'name': track_name or f'Track {i}',
                    'note_count': note_count
                })

        return track_info

    def create_preview_file(self, track_index: int, output_path: str):
        """Create a temporary MIDI file with just one track for the specified duration."""
        new_mid = mido.MidiFile()
        new_mid.ticks_per_beat = self.mid.ticks_per_beat

        # Copy the track
        original_track = self.mid.tracks[track_index]
        new_track = mido.MidiTrack()

        # Calculate time bounds
        start_ticks = mido.second2tick(self.start_offset, self.mid.ticks_per_beat, 500000)
        end_ticks = mido.second2tick(self.start_offset + self.preview_duration,
                                      self.mid.ticks_per_beat, 500000)

        current_tick = 0
        tempo = 500000  # Default tempo

        # Add messages within time range
        for msg in original_track:
            current_tick += msg.time

            # Track tempo changes
            if msg.type == 'set_tempo':
                tempo = msg.tempo
                if current_tick <= end_ticks:
                    new_track.append(msg)
            # Only include messages within preview range
            elif current_tick >= start_ticks and current_tick <= end_ticks:
                # Adjust timing for the first message
                if len(new_track) == 0 or (len(new_track) == 1 and new_track[0].type == 'set_tempo'):
                    adjusted_msg = msg.copy(time=0)
                else:
                    adjusted_msg = msg.copy()
                new_track.append(adjusted_msg)
            elif current_tick > end_ticks:
                break

        # Add end of track
        new_track.append(mido.MetaMessage('end_of_track', time=0))
        new_mid.tracks.append(new_track)
        new_mid.save(output_path)

        return new_mid

    def play_track_preview(self, track_index: int, track_name: str):
        """Play a preview of a specific track."""
        temp_file = '/tmp/midi_preview_temp.mid'

        try:
            # Create preview file
            preview_mid = self.create_preview_file(track_index, temp_file)

            # Load and play
            pygame.mixer.music.load(temp_file)
            pygame.mixer.music.play()

            print(f"\n▶ Playing: {track_name}")
            print(f"   Duration: {self.preview_duration}s | Start: {self.start_offset}s")
            print("\n   Controls: [Space] Pause/Resume | [Q] Stop | [Enter] Next track")

            start_time = time.time()

            while pygame.mixer.music.get_busy() and not self.stopped and not self.skip_requested:
                # Check for elapsed time
                elapsed = time.time() - start_time
                if elapsed >= self.preview_duration:
                    break

                # Progress indicator
                progress = min(elapsed / self.preview_duration * 100, 100)
                bar_length = 40
                filled = int(bar_length * progress / 100)
                bar = '█' * filled + '░' * (bar_length - filled)
                print(f'\r   [{bar}] {progress:.1f}% ({elapsed:.1f}/{self.preview_duration:.1f}s)', end='', flush=True)

                time.sleep(0.1)

            print()  # New line after progress bar
            pygame.mixer.music.stop()

            if self.skip_requested:
                self.skip_requested = False
                return 'skip'
            elif self.stopped:
                return 'stop'
            else:
                return 'complete'

        except Exception as e:
            print(f"\n   ⚠ Error playing track: {e}")
            return 'error'

    def input_listener(self):
        """Listen for keyboard input in a separate thread."""
        import sys
        import tty
        import termios

        fd = sys.stdin.fileno()
        old_settings = termios.tcgetattr(fd)

        try:
            tty.setraw(sys.stdin.fileno())
            while not self.stopped:
                ch = sys.stdin.read(1)

                if ch == ' ':  # Space - pause/resume
                    if pygame.mixer.music.get_busy():
                        if self.paused:
                            pygame.mixer.music.unpause()
                            self.paused = False
                        else:
                            pygame.mixer.music.pause()
                            self.paused = True
                elif ch == 'q' or ch == 'Q':  # Q - quit
                    self.stopped = True
                elif ch == '\r' or ch == '\n':  # Enter - skip
                    self.skip_requested = True
        finally:
            termios.tcsetattr(fd, termios.TCSADRAIN, old_settings)

    def preview_all_tracks(self):
        """Preview all tracks in the MIDI file."""
        print(f"\n{'='*70}")
        print(f"MIDI Preview: {Path(self.midi_path).name}")
        print(f"{'='*70}")

        track_info = self.get_track_info()

        if not track_info:
            print("No tracks with notes found in this MIDI file.")
            return

        print(f"\nFound {len(track_info)} track(s) with notes:")
        for info in track_info:
            print(f"  [{info['index']}] {info['name']} ({info['note_count']} notes)")

        print(f"\nStarting preview ({self.preview_duration}s per track)...")

        # Start input listener thread
        listener_thread = threading.Thread(target=self.input_listener, daemon=True)
        listener_thread.start()

        for info in track_info:
            if self.stopped:
                print("\n⏹ Preview stopped by user")
                break

            result = self.play_track_preview(info['index'], info['name'])

            if result == 'stop':
                print("\n⏹ Preview stopped by user")
                break
            elif result == 'skip':
                print("   ⏭ Skipped to next track")

            # Small pause between tracks
            if not self.stopped and info != track_info[-1]:
                time.sleep(0.5)

        self.stopped = True  # Signal input listener to stop
        pygame.mixer.quit()
        print(f"\n{'='*70}")
        print("Preview complete!")

    def preview_specific_track(self, track_index: int):
        """Preview a specific track."""
        print(f"\n{'='*70}")
        print(f"MIDI Preview: {Path(self.midi_path).name}")
        print(f"{'='*70}")

        track_info = self.get_track_info()

        # Find the track
        track = next((t for t in track_info if t['index'] == track_index), None)

        if not track:
            print(f"Track {track_index} not found or has no notes.")
            return

        # Start input listener thread
        listener_thread = threading.Thread(target=self.input_listener, daemon=True)
        listener_thread.start()

        self.play_track_preview(track['index'], track['name'])

        self.stopped = True
        pygame.mixer.quit()
        print(f"\n{'='*70}")


def main():
    if len(sys.argv) < 2:
        print("Usage: python preview_midi.py <midi_file> [duration_seconds] [track_index]")
        print("\nExamples:")
        print("  python preview_midi.py library/song.mid")
        print("  python preview_midi.py library/song.mid 20              # 20 second preview")
        print("  python preview_midi.py library/song.mid 30 1            # Track 1, 30 seconds")
        print("\nControls during playback:")
        print("  Space: Pause/Resume")
        print("  Q: Quit preview")
        print("  Enter: Skip to next track")
        sys.exit(1)

    midi_path = sys.argv[1]

    # Check if file exists
    if not Path(midi_path).exists():
        print(f"Error: File not found: {midi_path}")
        sys.exit(1)

    # Parse duration argument
    duration = 30.0
    if len(sys.argv) >= 3:
        try:
            duration = float(sys.argv[2])
        except ValueError:
            print(f"Invalid duration: {sys.argv[2]}")
            sys.exit(1)

    # Parse track index (optional)
    track_index = None
    if len(sys.argv) >= 4:
        try:
            track_index = int(sys.argv[3])
        except ValueError:
            print(f"Invalid track index: {sys.argv[3]}")
            sys.exit(1)

    try:
        previewer = MIDIPreview(midi_path, preview_duration=duration)

        if track_index is not None:
            previewer.preview_specific_track(track_index)
        else:
            previewer.preview_all_tracks()

    except KeyboardInterrupt:
        print("\n\n⏹ Preview interrupted by user")
        pygame.mixer.quit()
    except Exception as e:
        print(f"\nError: {e}")
        sys.exit(1)


if __name__ == '__main__':
    main()
