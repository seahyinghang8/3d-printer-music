"""MIDI file parsing for 3D printer music."""

from typing import List, Tuple, Optional
import mido


class Note:
    """Represents a musical note with timing and dynamics."""

    def __init__(
        self,
        frequency: float,
        duration: float,
        velocity: int = 64,
        start_time: float = 0.0
    ):
        """
        Initialize a note.

        Args:
            frequency: Frequency in Hz
            duration: Duration in seconds
            velocity: MIDI velocity (0-127), used for volume mapping
            start_time: Start time in seconds from beginning
        """
        self.frequency = frequency
        self.duration = duration
        self.velocity = velocity
        self.start_time = start_time

    def get_volume(self) -> str:
        """
        Map MIDI velocity to volume mode.

        Velocity ranges:
        - 0-42: soft (pp, p)
        - 43-84: normal (mp, mf)
        - 85-127: loud (f, ff, fff)

        Returns:
            "soft", "normal", or "loud"
        """
        if self.velocity < 43:
            return "soft"
        elif self.velocity < 85:
            return "normal"
        else:
            return "loud"

    def __repr__(self) -> str:
        return f"Note(freq={self.frequency:.1f}Hz, dur={self.duration:.2f}s, vel={self.velocity}, vol={self.get_volume()})"


def midi_note_to_frequency(midi_note: int) -> float:
    """
    Convert MIDI note number to frequency in Hz.

    MIDI note 69 (A4) = 440 Hz
    Formula: freq = 440 * 2^((note - 69) / 12)

    Args:
        midi_note: MIDI note number (0-127)

    Returns:
        Frequency in Hz
    """
    result: float = 440.0 * (2.0 ** ((midi_note - 69) / 12.0))
    return result


def parse_midi_file(
    midi_path: str,
    track_index: Optional[int] = None,
    tempo_scale: float = 1.0,
    transpose_semitones: int = 0,
    start_time: float = 0.0,
    end_time: Optional[float] = None
) -> Tuple[List[Note], int]:
    """
    Parse a MIDI file and extract notes with timing.

    Args:
        midi_path: Path to MIDI file
        track_index: Which track to extract (default: None = auto-select track with highest notes)
        tempo_scale: Scale tempo (1.0 = original, 0.5 = half speed, 2.0 = double speed)
        transpose_semitones: Number of semitones to transpose (positive = up, negative = down)
        start_time: Start time in seconds (notes before this are filtered out)
        end_time: End time in seconds (notes after this are filtered out, None = no limit)

    Returns:
        Tuple of (notes, selected_track_index)
        - notes: List of Note objects with timing information
        - selected_track_index: The track that was used (useful when auto-selecting)
    """
    try:
        midi_file = mido.MidiFile(midi_path)
    except ValueError as e:
        if "attribute must be in range" in str(e):
            raise ValueError(
                f"MIDI file has corrupted metadata: {e}\n"
                f"Try opening the file in GarageBand or another MIDI editor and re-exporting it."
            )
        raise

    # Auto-select track if not specified
    if track_index is None:
        track_index = _find_best_track(midi_file)
        print(f"Auto-selected track {track_index} (highest average frequency)")

    # Get the track
    if track_index >= len(midi_file.tracks):
        raise ValueError(f"Track {track_index} not found. File has {len(midi_file.tracks)} tracks.")

    track = midi_file.tracks[track_index]

    # Extract notes
    notes = []
    current_time = 0.0  # Current time in seconds
    active_notes = {}  # Map MIDI note number to start time and velocity

    # Default tempo (500000 microseconds per beat = 120 BPM)
    microseconds_per_beat = 500000

    for msg in track:
        # Convert delta time to seconds
        delta_seconds = mido.tick2second(
            msg.time,
            midi_file.ticks_per_beat,
            microseconds_per_beat
        )
        current_time += delta_seconds / tempo_scale

        if msg.type == 'set_tempo':
            # Update tempo
            microseconds_per_beat = msg.tempo

        elif msg.type == 'note_on' and msg.velocity > 0:
            # Note starts
            active_notes[msg.note] = (current_time, msg.velocity)

        elif msg.type == 'note_off' or (msg.type == 'note_on' and msg.velocity == 0):
            # Note ends
            if msg.note in active_notes:
                note_start_time, velocity = active_notes.pop(msg.note)
                duration = current_time - note_start_time

                # Apply transposition
                transposed_note = msg.note + transpose_semitones

                # Convert MIDI note to frequency
                frequency = midi_note_to_frequency(transposed_note)

                # Create note object
                note = Note(
                    frequency=frequency,
                    duration=duration,
                    velocity=velocity,
                    start_time=note_start_time
                )
                notes.append(note)

    # Sort by start time
    notes.sort(key=lambda n: n.start_time)

    # Filter notes by time window if specified
    if start_time > 0 or end_time is not None:
        filtered_notes = []
        for note in notes:
            note_end = note.start_time + note.duration

            # Skip notes that end before or at start_time
            if note_end <= start_time:
                continue

            # Skip notes that start at or after end_time
            if end_time is not None and note.start_time >= end_time:
                continue

            # Trim notes that overlap the boundaries
            adjusted_note = Note(
                frequency=note.frequency,
                duration=note.duration,
                velocity=note.velocity,
                start_time=note.start_time
            )

            # Trim start if note begins before start_time
            if note.start_time < start_time:
                # Adjust duration and start time
                overlap = start_time - note.start_time
                adjusted_note.duration = note.duration - overlap
                adjusted_note.start_time = start_time

            # Trim end if note extends past end_time
            if end_time is not None:
                note_end_adjusted = adjusted_note.start_time + adjusted_note.duration
                if note_end_adjusted > end_time:
                    adjusted_note.duration = end_time - adjusted_note.start_time

            filtered_notes.append(adjusted_note)

        notes = filtered_notes

        # Adjust all note start times to be relative to start_time
        for note in notes:
            note.start_time -= start_time

    return notes, track_index


def _find_best_track(midi_file: mido.MidiFile) -> int:
    """
    Find the track with the highest average frequency (likely the melody).

    The melody is typically in a higher register than bass or accompaniment parts.

    Args:
        midi_file: Loaded MIDI file

    Returns:
        Index of the best track to use
    """
    best_track_index = 0
    highest_avg_freq = 0.0

    for track_idx, track in enumerate(midi_file.tracks):
        # Collect all note values from this track
        note_values = []
        for msg in track:
            if msg.type == 'note_on' and msg.velocity > 0:
                note_values.append(msg.note)

        # Calculate average frequency if track has notes
        if note_values:
            avg_note = sum(note_values) / len(note_values)
            avg_freq = midi_note_to_frequency(int(avg_note))

            # Track with highest average frequency is usually the melody
            if avg_freq > highest_avg_freq:
                highest_avg_freq = avg_freq
                best_track_index = track_idx

    return best_track_index


def extract_melody_with_rests(notes: List[Note]) -> List[Tuple[Optional[float], float, str]]:
    """
    Extract melody as sequence of (frequency, duration, volume) with rests.

    Converts absolute timing to relative timing with rests between notes.

    When multiple notes start at the same time (chords):
    - Takes the highest frequency note (melody note)
    - Ignores lower harmony notes

    This is because the printer can only play one note at a time on a single axis.

    Args:
        notes: List of Note objects (sorted by start_time)

    Returns:
        List of (frequency, duration, volume) tuples
        - frequency is None for rests
        - duration in seconds
        - volume is "soft", "normal", or "loud"
    """
    if not notes:
        return []

    # Check if there's any velocity variation - if not, default to loud
    velocities = [n.velocity for n in notes]
    has_variation = len(set(velocities)) > 1
    default_volume = "normal" if has_variation else "loud"

    melody: List[Tuple[Optional[float], float, str]] = []
    current_time = 0.0
    i = 0

    while i < len(notes):
        note = notes[i]

        # Add rest if needed
        if note.start_time > current_time:
            rest_duration = note.start_time - current_time
            melody.append((None, rest_duration, default_volume))
            current_time = note.start_time

        # Check for chord (multiple notes starting at same time)
        # Take the highest frequency note (usually the melody)
        chord_notes = [note]
        j = i + 1
        while j < len(notes) and abs(notes[j].start_time - note.start_time) < 0.01:  # Within 10ms
            chord_notes.append(notes[j])
            j += 1

        if len(chord_notes) > 1:
            # Chord detected - take highest frequency (melody note)
            melody_note = max(chord_notes, key=lambda n: n.frequency)
            volume = melody_note.get_volume() if has_variation else default_volume
            melody.append((melody_note.frequency, melody_note.duration, volume))
            current_time = melody_note.start_time + melody_note.duration
            i = j  # Skip all chord notes
        else:
            # Single note
            volume = note.get_volume() if has_variation else default_volume
            melody.append((note.frequency, note.duration, volume))
            current_time = note.start_time + note.duration
            i += 1

    return melody


def analyze_transposition(
    notes: List[Note],
    target_freq_range: Tuple[float, float] = (1000.0, 12000.0)
) -> Tuple[int, List[Note]]:
    """
    Analyze melody and suggest optimal transposition to higher frequencies.

    The printer is louder at higher frequencies, so we try to transpose up
    as much as possible while staying within the target range.

    Args:
        notes: List of Note objects
        target_freq_range: (min, max) frequency range to target (default: 1-12kHz)

    Returns:
        (suggested_semitones, transposed_notes)
        - suggested_semitones: Number of semitones to transpose up (0 if no transpose needed)
        - transposed_notes: Notes with the suggested transposition applied
    """
    if not notes:
        return 0, notes

    min_freq = min(n.frequency for n in notes)
    max_freq = max(n.frequency for n in notes)
    target_min, target_max = target_freq_range

    # If already in good range, no need to transpose
    if min_freq >= target_min:
        return 0, notes

    # Calculate how many semitones we can safely transpose up
    # Each semitone multiplies frequency by 2^(1/12) ≈ 1.059463
    best_transpose = 0

    for semitones in range(1, 25):  # Try up to 2 octaves
        transposed_max = max_freq * (2.0 ** (semitones / 12.0))
        transposed_min = min_freq * (2.0 ** (semitones / 12.0))

        # Check if this transpose keeps us within range
        if transposed_max <= target_max and transposed_min >= target_min:
            best_transpose = semitones
        elif transposed_min >= target_min and transposed_max > target_max:
            # We've gone too high, stick with previous
            break

    # Apply the best transposition
    if best_transpose > 0:
        transposed_notes = []
        for note in notes:
            new_freq = note.frequency * (2.0 ** (best_transpose / 12.0))
            transposed_notes.append(Note(
                frequency=new_freq,
                duration=note.duration,
                velocity=note.velocity,
                start_time=note.start_time
            ))
        return best_transpose, transposed_notes
    else:
        return 0, notes


def print_melody_summary(notes: List[Note]) -> None:
    """
    Print a summary of the melody.

    Args:
        notes: List of Note objects
    """
    if not notes:
        print("No notes found!")
        return

    print(f"Total notes: {len(notes)}")
    print(f"Duration: {notes[-1].start_time + notes[-1].duration:.1f}s")
    print(f"Frequency range: {min(n.frequency for n in notes):.1f} - {max(n.frequency for n in notes):.1f} Hz")
    print(f"Velocity range: {min(n.velocity for n in notes)} - {max(n.velocity for n in notes)}")

    # Count volume distribution
    soft_count = sum(1 for n in notes if n.get_volume() == "soft")
    normal_count = sum(1 for n in notes if n.get_volume() == "normal")
    loud_count = sum(1 for n in notes if n.get_volume() == "loud")

    print("\nVolume distribution:")
    print(f"  Soft: {soft_count} notes ({soft_count/len(notes)*100:.1f}%)")
    print(f"  Normal: {normal_count} notes ({normal_count/len(notes)*100:.1f}%)")
    print(f"  Loud: {loud_count} notes ({loud_count/len(notes)*100:.1f}%)")

    # Show first few notes
    print("\nFirst 5 notes:")
    for i, note in enumerate(notes[:5]):
        print(f"  {i+1}. {note}")
