# 3D Printer Music

Turn a Creality Ender 3 3D printer into a musical instrument using the movement of the stepper motors to play musical notes.

## Hardware

- **Printer**: Creality Ender 3
- **Connection**: USB serial (115200 baud)

## Motor Frequency Ranges

We achieve the various frequency by making the motor move at a certain speed.

- **X Motor**: 130.81 Hz - 12543.85 Hz (steps/mm: 80)
  - Furthest from table, low frequencies hard to hear
- **Y Motor**: 130.81 Hz - 12543.85 Hz (steps/mm: 80)
- **Z Motor**: 123.47 Hz - 1864.66 Hz (steps/mm: 400)
  - **Best for low frequencies** - easiest to hear bass notes

By moving the motor at a certain speed, it produces a note.

X and Y axis can be moved at the same time through a diagonal motion. Otherwise, only one axis can move at a time.

## Features

- **Volume Control**: Uses different axes to control perceived volume
  - Soft: X axis only (quieter, farther from user)
  - Normal: Y axis only (normal volume, closest to user)
  - Loud: Both X and Y axes moving equally (louder, combined sound)
  - Auto-loud: If MIDI file has no velocity variation, all notes play at loud volume

- **MIDI Playback**: Parse and play MIDI files with automatic volume mapping
  - MIDI velocity mapped to volume modes
  - Supports melody extraction with rests
  - See [play_jingle_bells.py](play_jingle_bells.py) for example

- **Transpose Control**: Shift notes to higher frequencies for better audibility
  - Manual transpose: Specify semitones to shift (e.g., +12 = up one octave)
  - Auto-analyze mode: Analyzes frequency range and suggests optimal transpose
  - Printers are louder at higher frequencies (1-12kHz range)

- **Smart Motion**: Boundary-aware movement planning ensures all notes can play
  - Direction selection based on proximity to boundaries
  - Closer to boundary = more likely to move toward opposite side
  - Automatic multi-segment movements when distance exceeds available space
  - Bounces between boundaries seamlessly to maintain correct frequency
  - Never raises out-of-bounds errors - always finds a valid movement path

We use uv for this project.

## Quick Examples

### Play Built-in Examples

Play a simple melody:
```bash
uv run python example_chord.py
```

Play Jingle Bells from MIDI:
```bash
uv run python play_jingle_bells.py
```

### Work with MIDI Files

**1. Interactive preview** - explore tracks, play audio, save for printer:
```bash
uv run python preview_midi.py library/jingle_bells_simple.mid
```

Interactive commands:
- `[number]` - View track details
- `p[number]` - Play track audio (requires pygame)
- `s[number]` - Save track as JSON for printer
- `q` - Quit

**2. Play any MIDI track** directly on printer:
```bash
uv run python play_midi.py <midi_file> <track_number> [transpose_semitones]
```

Examples:
```bash
# Play without transposition
uv run python play_midi.py library/jingle_bells_simple.mid 1

# Transpose up one octave (12 semitones) for louder playback
uv run python play_midi.py library/jingle_bells_simple.mid 1 12

# Auto-analyze and suggest optimal transpose
uv run python play_midi.py library/jingle_bells_simple.mid 1 auto
```

The auto-transpose mode analyzes your MIDI file and suggests the best transposition to shift notes into the 1-12kHz range where the printer is loudest, while staying within the printer's frequency capabilities.

**3. Play a playlist** - queue multiple songs with settings:
```bash
uv run python play_midi_playlist.py playlist.yaml
```

Playlist features:
- Play multiple songs in sequence
- Trim songs with start/end time (skip long intros/outros)
- Auto-transpose and auto-track selection per song
- Shuffle mode: `--shuffle` flag
- Live editing: modify YAML between tracks
- Ctrl+C to skip current track
- Progress tracking: resumes from where you left off
- Auto-loop: when all tracks complete, playlist resets and plays again

Example [playlist.yaml](playlist.yaml):
```yaml
items:
  - filename: library/jingle-bells.mid
    start_seconds: 0
    end_seconds: 20
    transpose: auto
    track: auto
    played: false
  - filename: library/habanera.mid
    start_seconds: 0
    transpose: 12
    track: 1
    played: false
```
