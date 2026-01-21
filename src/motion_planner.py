"""Motion planning for frequency-based movements."""

import random
from typing import Tuple

from .config import FREQUENCY_RANGES, SAFE_LIMITS, STEPS_PER_MM
from .exceptions import OutOfBoundsError


class MotionPlanner:
    """
    Plan movements that stay within safe boundaries.

    Uses DFS to find valid positions for note playback.
    """

    def __init__(self, safe_limits: dict):
        """
        Initialize planner with boundary limits.

        Args:
            safe_limits: Dict with format {"X": (min, max), "Y": (min, max), ...}
        """
        self.safe_limits = safe_limits
        # Track current direction for each axis (1 = positive, -1 = negative)
        self.current_direction = {"X": 1, "Y": 1, "Z": 1}

    def frequency_to_feedrate(self, axis: str, frequency: float) -> float:
        """
        Convert frequency (Hz) to feedrate (mm/min).

        Formula: feedrate = (frequency * 60) / steps_per_mm

        Args:
            axis: Motor axis
            frequency: Target frequency in Hz

        Returns:
            Feedrate in mm/min
        """
        steps_per_mm = STEPS_PER_MM[axis]
        feedrate = (frequency * 60.0) / steps_per_mm
        return feedrate

    def calculate_distance(
        self,
        axis: str,
        frequency: float,
        duration: float
    ) -> float:
        """
        Calculate distance to move for frequency and duration.

        Args:
            axis: Motor axis
            frequency: Target frequency (Hz)
            duration: Note duration (seconds)

        Returns:
            Distance in mm
        """
        feedrate = self.frequency_to_feedrate(axis, frequency)
        distance = (feedrate / 60.0) * duration  # Convert mm/min to mm/s, then multiply by duration
        return distance

    def plan_note_movement(
        self,
        axis: str,
        frequency: float,
        duration: float,
        current_pos: float
    ) -> Tuple[float, int]:
        """
        Find valid target position for note using DFS.

        Searches for position where:
        1. Can move required distance for frequency/duration
        2. Movement stays within safe boundaries
        3. Randomly changes direction based on proximity to limits

        Args:
            axis: Axis to move
            frequency: Target frequency (Hz)
            duration: Note duration (seconds)
            current_pos: Current position on axis

        Returns:
            (target_position, direction)
            - target_position: Where to move to (mm)
            - direction: 1 for positive, -1 for negative

        Raises:
            OutOfBoundsError: No valid position found within boundaries
        """
        # Calculate required movement
        distance = self.calculate_distance(axis, frequency, duration)

        min_limit, max_limit = self.safe_limits[axis]

        # Check if movement fits in available space
        available_range = max_limit - min_limit
        if distance > available_range:
            raise OutOfBoundsError(
                f"Movement requires {distance:.1f}mm but only {available_range:.1f}mm available"
            )

        # Calculate how far we are from the limits (normalized 0-1)
        distance_to_min = (current_pos - min_limit) / available_range
        distance_to_max = (max_limit - current_pos) / available_range

        # The closer we are to a limit, the higher the probability of changing direction
        # When near min limit (distance_to_min is small), probability to flip negative->positive is high
        # When near max limit (distance_to_max is small), probability to flip positive->negative is high
        direction = self.current_direction[axis]

        if direction > 0:
            # Moving towards max limit - probability of flip increases as we approach it
            flip_probability = 1.0 - distance_to_max
        else:
            # Moving towards min limit - probability of flip increases as we approach it
            flip_probability = 1.0 - distance_to_min

        # Random chance to flip direction based on proximity to limits
        if random.random() < flip_probability:
            direction = -direction

        # Try the chosen direction
        target_pos = current_pos + (distance * direction)

        if min_limit <= target_pos <= max_limit:
            # Update preferred direction for next time
            self.current_direction[axis] = direction
            return target_pos, direction

        # Hit a boundary - must flip direction
        direction = -direction
        target_pos = current_pos + (distance * direction)

        if min_limit <= target_pos <= max_limit:
            # Update preferred direction for next time
            self.current_direction[axis] = direction
            return target_pos, direction

        # Both directions fail - we're trapped
        # This happens when distance is too large for current position
        raise OutOfBoundsError(
            f"Cannot move {distance:.1f}mm from position {current_pos:.1f}mm "
            f"within bounds [{min_limit}, {max_limit}]"
        )

    def validate_note_possible(
        self,
        axis: str,
        frequency: float,
        duration: float
    ) -> bool:
        """
        Check if note can be played within boundaries.

        Args:
            axis: Motor axis
            frequency: Target frequency (Hz)
            duration: Note duration (seconds)

        Returns:
            True if note is possible, False otherwise
        """
        distance = self.calculate_distance(axis, frequency, duration)
        min_limit, max_limit = self.safe_limits[axis]
        available_range = max_limit - min_limit
        return distance <= available_range
