"""MIDI transposition utilities for optimizing playback frequency ranges."""

from typing import List, Tuple, Optional
from .midi_parser import Note


class Transposer:
    """Handles transposition of MIDI notes to optimize for hardware frequency ranges."""

    def __init__(self, target_freq_range: Tuple[float, float] = (1000.0, 12000.0)):
        """
        Initialize transposer with target frequency range.

        Args:
            target_freq_range: (min, max) frequency range to target (default: 1-12kHz)
        """
        self.target_freq_range = target_freq_range

    def analyze(self, notes: List[Note]) -> Tuple[int, List[Note]]:
        """
        Analyze melody and suggest optimal transposition into the target frequency range.

        Aims to get the melody into the target range without going too high.
        Strategy: Move up by the minimum number of semitones until the lowest
        note is playable, or until 99% of notes sit inside the playable range.

        Args:
            notes: List of Note objects

        Returns:
            (suggested_semitones, transposed_notes)
            - suggested_semitones: Number of semitones to transpose up (0 if no transpose needed)
            - transposed_notes: Notes with the suggested transposition applied
        """
        if not notes:
            return 0, notes

        target_min, target_max = self.target_freq_range
        coverage_target = 0.99

        best_coverage = -1.0
        best_coverage_semitones = 0
        selected_semitones: Optional[int] = None

        for semitones in range(0, 25):  # Try from 0 up to 2 octaves
            factor = 2.0 ** (semitones / 12.0)
            transposed_freqs = [n.frequency * factor for n in notes]
            transposed_min = min(transposed_freqs)
            in_range_ratio = self._in_range_ratio(transposed_freqs)

            if (
                in_range_ratio > best_coverage
                or (abs(in_range_ratio - best_coverage) < 1e-9 and semitones < best_coverage_semitones)
            ):
                best_coverage = in_range_ratio
                best_coverage_semitones = semitones

            if transposed_min >= target_min or in_range_ratio >= coverage_target:
                selected_semitones = semitones
                break

        if selected_semitones is None:
            selected_semitones = best_coverage_semitones

        if selected_semitones == 0:
            return 0, notes

        transposed_notes = self._apply_transposition(notes, selected_semitones)
        return selected_semitones, transposed_notes

    def _apply_transposition(self, notes: List[Note], semitones: int) -> List[Note]:
        """
        Apply transposition to a list of notes.

        Args:
            notes: List of Note objects
            semitones: Number of semitones to transpose (positive = up, negative = down)

        Returns:
            List of transposed Note objects
        """
        transposed_notes = []
        for note in notes:
            new_freq = note.frequency * (2.0 ** (semitones / 12.0))
            transposed_notes.append(Note(
                frequency=new_freq,
                duration=note.duration,
                velocity=note.velocity,
                start_time=note.start_time
            ))
        return transposed_notes

    def get_frequency_info(self, notes: List[Note]) -> dict:
        """
        Get frequency range information for a list of notes.

        Args:
            notes: List of Note objects

        Returns:
            Dictionary with min_freq, max_freq, and in_range status
        """
        if not notes:
            return {"min_freq": 0.0, "max_freq": 0.0, "in_range": False}

        min_freq = min(n.frequency for n in notes)
        max_freq = max(n.frequency for n in notes)
        target_min, target_max = self.target_freq_range

        return {
            "min_freq": min_freq,
            "max_freq": max_freq,
            "in_range": min_freq >= target_min and max_freq <= target_max
        }

    def prompt_user_for_transposition(
        self,
        original_notes: List[Note],
        suggested_semitones: int,
        transposed_notes: List[Note]
    ) -> int:
        """
        Interactive prompt asking user to approve suggested transposition.

        Args:
            original_notes: Original notes before transposition
            suggested_semitones: Suggested number of semitones to transpose
            transposed_notes: Notes with suggested transposition applied

        Returns:
            Number of semitones to apply (0 if user declines)
        """
        if suggested_semitones <= 0:
            print("No transposition needed - frequencies already in optimal range")
            return 0

        octaves = suggested_semitones / 12
        print(f"Suggested transpose: +{suggested_semitones} semitones ({octaves:.1f} octaves)")

        orig_info = self.get_frequency_info(original_notes)
        trans_info = self.get_frequency_info(transposed_notes)
        orig_coverage = self._in_range_ratio([n.frequency for n in original_notes])
        trans_coverage = self._in_range_ratio([n.frequency for n in transposed_notes])

        print(f"Original range: {orig_info['min_freq']:.1f} - {orig_info['max_freq']:.1f} Hz")
        print(f"Transposed range: {trans_info['min_freq']:.1f} - {trans_info['max_freq']:.1f} Hz")
        print(f"In-range coverage: {orig_coverage * 100:.1f}% -> {trans_coverage * 100:.1f}%")

        response = input("\nApply this transposition? (y/n): ").strip().lower()
        if response == 'y':
            print(f"✓ Applying +{suggested_semitones} semitones transpose")
            return suggested_semitones
        else:
            print("✓ Playing without transpose")
            return 0

    def _in_range_ratio(self, freqs: List[float]) -> float:
        """
        Calculate percentage of frequencies that fall inside the target range.

        Args:
            freqs: Frequencies to evaluate

        Returns:
            Ratio of frequencies inside the target range (0.0 - 1.0)
        """
        if not freqs:
            return 0.0

        target_min, target_max = self.target_freq_range
        in_range = sum(1 for f in freqs if target_min <= f <= target_max)
        return in_range / len(freqs)


def create_transposer(target_freq_range: Optional[Tuple[float, float]] = None) -> Transposer:
    """
    Factory function to create a Transposer instance.

    Args:
        target_freq_range: Optional (min, max) frequency range to target

    Returns:
        Transposer instance
    """
    if target_freq_range is None:
        return Transposer()
    return Transposer(target_freq_range)
