"""Motion planning for diagonal frequency-based movements."""

import math
import random
from typing import List, Tuple

from .config import STEPS_PER_MM


class MotionPlanner:
    """
    Plan diagonal movements that produce two frequencies simultaneously.

    All movements are diagonal (X and Y together), maintaining precise
    velocity ratios to produce correct frequencies on both axes.
    """

    def __init__(self, safe_limits: dict):
        """
        Initialize planner with boundary limits.

        Args:
            safe_limits: Dict with format {"X": (min, max), "Y": (min, max)}
        """
        self.x_min, self.x_max = safe_limits["X"]
        self.y_min, self.y_max = safe_limits["Y"]

    def frequency_to_velocity(self, axis: str, frequency: float) -> float:
        """
        Convert frequency (Hz) to velocity (mm/s).

        Formula: velocity = frequency / steps_per_mm

        Args:
            axis: Motor axis ("X" or "Y")
            frequency: Target frequency in Hz

        Returns:
            Velocity in mm/s
        """
        steps_per_mm = STEPS_PER_MM[axis]
        velocity = frequency / steps_per_mm
        return velocity

    def _choose_direction_probabilistic(
        self,
        current_pos: float,
        min_bound: float,
        max_bound: float,
        steepness: float = 10.0
    ) -> int:
        """
        Choose movement direction using logistic function probability.

        The probability of moving towards max increases as the position
        approaches min, and vice versa. The logistic function creates
        smooth S-curve transitions with tunable boundary repulsion.

        Args:
            current_pos: Current position along the axis
            min_bound: Minimum boundary
            max_bound: Maximum boundary
            steepness: Controls how sharply probability changes near boundaries.
                      Higher values = stronger boundary repulsion (default: 10.0)

        Returns:
            Direction: 1 (towards max) or -1 (towards min)
        """
        # Normalize position to [0, 1] range
        normalized_pos = (current_pos - min_bound) / (max_bound - min_bound)

        # Apply logistic function centered at 0.5
        # When normalized_pos = 0 (at min), sigmoid ≈ 1 → high prob to move positive
        # When normalized_pos = 1 (at max), sigmoid ≈ 0 → high prob to move negative
        # When normalized_pos = 0.5 (center), sigmoid = 0.5 → 50/50
        x = steepness * (normalized_pos - 0.5)
        probability_move_positive = 1.0 / (1.0 + math.exp(x))

        # Sample direction based on probability
        return 1 if random.random() < probability_move_positive else -1

    def plan_movement(
        self,
        freq_x: float | None,
        freq_y: float | None,
        duration: float,
        x0: float,
        y0: float,
        override_dir_x: int | None = None,
        override_dir_y: int | None = None
    ) -> Tuple[List[Tuple[float, float]], float, int | None, int | None]:
        """
        Plan movement to produce one or two frequencies.

        Supports diagonal movement (both axes), or single-axis movement.

        Args:
            freq_x: X-axis frequency in Hz (None to skip X axis)
            freq_y: Y-axis frequency in Hz (None to skip Y axis)
            duration: Note duration in seconds
            x0: Starting X position in mm
            y0: Starting Y position in mm
            override_dir_x: If provided, use this direction for X axis instead of calculating
            override_dir_y: If provided, use this direction for Y axis instead of calculating

        Returns:
            Tuple of (waypoints, feedrate, dir_x, dir_y):
                - waypoints: List of (x, y) positions to move through
                - feedrate: Feedrate in mm/min for the movement
                - dir_x: Direction used for X axis (1, -1, or None if not used)
                - dir_y: Direction used for Y axis (1, -1, or None if not used)
        """
        # Calculate velocity components
        vx = self.frequency_to_velocity("X", freq_x) if freq_x is not None else 0.0
        vy = self.frequency_to_velocity("Y", freq_y) if freq_y is not None else 0.0

        # Calculate total velocity
        v_total = math.sqrt(vx * vx + vy * vy)

        # Calculate total distance needed
        total_distance = v_total * duration

        # Determine initial directions for active axes
        dir_x = None
        dir_y = None

        if freq_x is not None:
            dir_x = override_dir_x if override_dir_x is not None else self._choose_direction_probabilistic(x0, self.x_min, self.x_max)
        if freq_y is not None:
            dir_y = override_dir_y if override_dir_y is not None else self._choose_direction_probabilistic(y0, self.y_min, self.y_max)

        # Use ray marching to find all waypoints
        signed_vx = vx * dir_x if dir_x is not None else 0.0
        signed_vy = vy * dir_y if dir_y is not None else 0.0
        waypoints = self._ray_march(x0, y0, signed_vx, signed_vy, total_distance)

        # Calculate feedrate (convert mm/s to mm/min)
        feedrate = v_total * 60.0

        return waypoints, feedrate, dir_x, dir_y

    def plan_diagonal_movement(
        self,
        freq_x: float,
        freq_y: float,
        duration: float,
        x0: float,
        y0: float,
        override_dir_x: int | None = None,
        override_dir_y: int | None = None
    ) -> Tuple[List[Tuple[float, float]], float, int, int]:
        """
        Plan diagonal movement to produce two frequencies simultaneously.

        Uses parametric ray marching to calculate all boundary bounces while
        maintaining exact velocity ratios for correct frequencies.

        Args:
            freq_x: X-axis frequency in Hz
            freq_y: Y-axis frequency in Hz
            duration: Note duration in seconds
            x0: Starting X position in mm
            y0: Starting Y position in mm
            override_dir_x: If provided, use this direction for X axis instead of calculating
            override_dir_y: If provided, use this direction for Y axis instead of calculating

        Returns:
            Tuple of (waypoints, feedrate, dir_x, dir_y):
                - waypoints: List of (x, y) positions to move through
                - feedrate: Feedrate in mm/min for the diagonal movement
                - dir_x: Direction used for X axis (1 or -1)
                - dir_y: Direction used for Y axis (1 or -1)
        """
        waypoints, feedrate, dir_x, dir_y = self.plan_movement(
            freq_x, freq_y, duration, x0, y0, override_dir_x, override_dir_y
        )
        # plan_diagonal_movement guarantees non-None directions
        assert dir_x is not None and dir_y is not None
        return waypoints, feedrate, dir_x, dir_y

    def _ray_march(
        self,
        x: float,
        y: float,
        vx: float,
        vy: float,
        remaining_distance: float
    ) -> List[Tuple[float, float]]:
        """
        Ray march through the workspace, bouncing off boundaries.

        Args:
            x: Current X position
            y: Current Y position
            vx: X velocity component (signed)
            vy: Y velocity component (signed)
            remaining_distance: Diagonal distance left to cover

        Returns:
            List of (x, y) waypoints
        """
        waypoints = []
        epsilon = 1e-6  # Small value for floating point comparisons

        while remaining_distance > epsilon:
            # Calculate time to reach each boundary
            if abs(vx) > epsilon:
                if vx > 0:
                    t_x = (self.x_max - x) / vx
                else:
                    t_x = (self.x_min - x) / vx
            else:
                t_x = float('inf')

            if abs(vy) > epsilon:
                if vy > 0:
                    t_y = (self.y_max - y) / vy
                else:
                    t_y = (self.y_min - y) / vy
            else:
                t_y = float('inf')

            # Take the minimum time (next bounce)
            t_bounce = min(t_x, t_y)

            # Calculate position at bounce
            x_next = x + vx * t_bounce
            y_next = y + vy * t_bounce

            # Calculate distance traveled
            dx = x_next - x
            dy = y_next - y
            segment_distance = math.sqrt(dx * dx + dy * dy)

            # Check if this is the final segment
            if segment_distance >= remaining_distance:
                # Final position - move exactly remaining_distance
                t_final = remaining_distance / math.sqrt(vx * vx + vy * vy)
                x_final = x + vx * t_final
                y_final = y + vy * t_final
                waypoints.append((x_final, y_final))
                break
            else:
                # Add waypoint at boundary
                waypoints.append((x_next, y_next))
                remaining_distance -= segment_distance

                # Update position
                x = x_next
                y = y_next

                # Flip velocity component(s) based on which boundary was hit
                # Use epsilon for floating point comparison
                if abs(t_x - t_y) < epsilon:
                    # Hit corner - flip both
                    vx = -vx
                    vy = -vy
                elif t_x < t_y:
                    # Hit X boundary
                    vx = -vx
                else:
                    # Hit Y boundary
                    vy = -vy

        return waypoints
