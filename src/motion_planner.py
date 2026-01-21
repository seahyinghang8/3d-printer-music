"""Motion planning for frequency-based movements."""

import random
from typing import List

from .config import STEPS_PER_MM


class MotionPlanner:
    """
    Plan movements that stay within safe boundaries.

    Uses boundary-aware direction selection and multi-segment movements
    to ensure all movements stay within limits without raising errors.
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
        current_pos: float,
        flip_direction: bool = False
    ) -> List[float]:
        """
        Plan one or more movements to play a note within safe boundaries.

        The function determines initial direction based on proximity to boundaries:
        - Closer to min limit: more likely to move towards max (positive direction)
        - Closer to max limit: more likely to move towards min (negative direction)

        If the required distance exceeds the available space in the chosen direction,
        the function automatically splits the movement into multiple segments,
        bouncing between boundaries until the total distance is covered.

        Args:
            axis: Axis to move
            frequency: Target frequency (Hz)
            duration: Note duration (seconds)
            current_pos: Current position on axis
            flip_direction: If True, flip the direction from what would normally be chosen.
                Useful for making consecutive notes with the same frequency sound more distinct.
                Default is False (use normal boundary-based direction selection).

        Returns:
            List of target positions (in mm). Each position represents where to move next.
            Returns a list with one or more positions. Multiple positions occur
            when the total distance requires bouncing between boundaries.

        Example:
            Single movement (fits within bounds):
            [150.0]  # Move to 150mm

            Multi-segment movement (exceeds bounds):
            [10.0, 200.0, 150.0]  # Bounce between boundaries
        """
        # Calculate total required movement distance
        total_distance = self.calculate_distance(axis, frequency, duration)
        min_limit, max_limit = self.safe_limits[axis]

        # Determine initial direction
        if flip_direction:
            # Flip from current direction
            direction = -self.current_direction[axis]
        else:
            # Choose direction based on proximity to max limit
            # Closer to max = more likely to go negative, closer to min = more likely to go positive
            distance_to_max_ratio = (max_limit - current_pos) / (max_limit - min_limit)
            direction = 1 if random.random() < distance_to_max_ratio else -1

        # Plan movements, potentially splitting across multiple segments
        positions: List[float] = []

        incoming_boundary = max_limit if direction == 1 else min_limit
        distance_to_boundary = abs(incoming_boundary - current_pos)
        if distance_to_boundary >= total_distance:
            # Single movement fits within bounds
            target_pos = current_pos + direction * total_distance
            positions.append(target_pos)
            self.current_direction[axis] = direction
        else:
            # Multiple segments needed
            remaining_distance = total_distance - distance_to_boundary
            # First move to boundary
            positions.append(incoming_boundary)
            direction *= -1  # Bounce off boundary
            # Bounce between boundaries
            full_range = max_limit - min_limit
            num_bounces = int(remaining_distance // full_range)
            for _ in range(num_bounces):
                # Alternate direction each bounce
                target_pos = max_limit if direction == 1 else min_limit
                positions.append(target_pos)
                direction *= -1
            # Final segment
            final_segment = remaining_distance % full_range
            if final_segment > 0:
                target_pos = (min_limit + final_segment) if direction == 1 else (max_limit - final_segment)
                positions.append(target_pos)
            self.current_direction[axis] = direction
        return positions
