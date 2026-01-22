"""High-level API for playing notes on 3D printer."""

import time
from typing import Tuple

import serial

from .config import FREQUENCY_RANGES
from .gcode_sender import send_gcode_with_retry
from .motion_planner import MotionPlanner
from .position_tracker import AbsolutePositionTracker

class NotePlayer:
    """
    Simple API for playing notes on 3D printer motors.

    All notes are played using diagonal movement (X and Y together).
    Single notes play the same frequency on both axes.

    Usage:
        player = NotePlayer(serial_connection, tracker, planner)
        player.play_note(440.0, 880.0, 1.0)  # Play two frequencies for 1 second
        player.pause(0.5)  # Pause for 0.5 seconds
    """

    def __init__(
        self,
        ser: serial.Serial,
        tracker: AbsolutePositionTracker,
        planner: MotionPlanner
    ):
        """
        Initialize note player.

        Args:
            ser: Serial connection to printer
            tracker: Position tracker
            planner: Motion planner
        """
        self.ser = ser
        self.tracker = tracker
        self.planner = planner
        # Track last note frequency for each axis
        self.last_note_x: float | None = None
        self.last_note_y: float | None = None
        # Track last direction for each axis
        self.last_dir_x: int = -1
        self.last_dir_y: int = -1

    def play_note(
        self,
        freq_1: float,
        freq_2: float,
        duration: float,
        volume: str = "normal",
        debug: bool = False
    ) -> None:
        """
        Play one or two frequencies simultaneously using diagonal movement.

        For a single note, pass the same frequency twice.
        For a chord, pass two different frequencies.

        Volume controls which axes are used for single notes (freq_1 == freq_2):
        - "loud": Both X and Y axes (diagonal movement)
        - "normal": Y axis only
        - "soft": X axis only
        For chords (freq_1 != freq_2), volume is ignored and both axes are used.

        The motion planner automatically assigns higher frequency to X axis
        and lower frequency to Y axis when both are used.

        Blocking call - returns after note completes.

        Args:
            freq_1: First frequency in Hz
            freq_2: Second frequency in Hz
            duration: Duration in seconds
            volume: Volume level ("loud", "normal", or "soft"), only used for single notes
            debug: Print debug information

        Raises:
            ValueError: Invalid frequency or unknown position
        """
        # Validate frequencies are in range
        for freq in [freq_1, freq_2]:
            # Use X axis range since we assign higher freq to X
            min_freq, max_freq = FREQUENCY_RANGES["X"]
            if not (min_freq <= freq <= max_freq):
                raise ValueError(
                    f"Frequency {freq} Hz out of range [{min_freq}, {max_freq}]"
                )

        # Get current positions
        x0 = self.tracker.get_position("X")
        y0 = self.tracker.get_position("Y")
        if x0 is None or y0 is None:
            raise ValueError("Unknown position. Initialize tracker first.")

        # Check if this is a single note or a chord
        is_single_note = abs(freq_1 - freq_2) < 1e-6

        # Determine which axes to use based on volume (only for single notes)
        if is_single_note:
            # loud: both axes (diagonal), normal: Y only, soft: X only
            use_x_axis = volume in ["loud", "soft"]
            use_y_axis = volume in ["loud", "normal"]
        else:
            # For chords, always use both axes
            use_x_axis = True
            use_y_axis = True

        # Determine frequencies for each axis
        # Motion planner assigns higher freq to X, lower to Y
        freq_x = max(freq_1, freq_2) if use_x_axis else None
        freq_y = min(freq_1, freq_2) if use_y_axis else None

        # Determine override directions based on whether frequencies match previous notes
        override_dir_x = None
        override_dir_y = None

        # If X frequency is same as last time, flip X direction
        if freq_x is not None and self.last_note_x is not None and abs(freq_x - self.last_note_x) < 1e-6:
            override_dir_x = -self.last_dir_x

        # If Y frequency is same as last time, flip Y direction
        if freq_y is not None and self.last_note_y is not None and abs(freq_y - self.last_note_y) < 1e-6:
            override_dir_y = -self.last_dir_y

        # Plan movement
        waypoints, feedrate, dir_x, dir_y = self.planner.plan_movement(
            freq_x, freq_y, duration, x0, y0,
            override_dir_x=override_dir_x, override_dir_y=override_dir_y
        )

        # Store the frequencies and directions that were used
        self.last_note_x = freq_x
        self.last_note_y = freq_y
        if dir_x is not None:
            self.last_dir_x = dir_x
        if dir_y is not None:
            self.last_dir_y = dir_y

        if debug:
            # Calculate total distance
            total_distance = 0.0
            x_prev, y_prev = x0, y0
            for x, y in waypoints:
                dx = x - x_prev
                dy = y - y_prev
                total_distance += (dx * dx + dy * dy) ** 0.5
                x_prev, y_prev = x, y

            freq_x = max(freq_1, freq_2)
            freq_y = min(freq_1, freq_2)
            print(f"Playing: X={freq_x:.1f} Hz, Y={freq_y:.1f} Hz for {duration:.2f}s")
            print(f"  Total distance: {total_distance:.1f}mm across {len(waypoints)} waypoint(s)")
            print(f"  Feedrate: {feedrate:.1f} mm/min")

        # Execute all movements
        segment_start_time = time.time()

        for i, (target_x, target_y) in enumerate(waypoints):
            current_x = self.tracker.get_position("X")
            current_y = self.tracker.get_position("Y")
            if current_x is None or current_y is None:
                raise ValueError("Lost position tracking during movement.")

            dx = target_x - current_x
            dy = target_y - current_y
            distance = (dx * dx + dy * dy) ** 0.5

            if debug:
                print(f"  Waypoint {i+1}/{len(waypoints)}: "
                      f"({current_x:.1f}, {current_y:.1f}) -> ({target_x:.1f}, {target_y:.1f}) "
                      f"[{distance:.1f}mm]")

            # Execute diagonal movement
            command = f"G1 X{target_x:.3f} Y{target_y:.3f} F{feedrate:.1f}"
            send_gcode_with_retry(self.ser, command, debug=debug)

            # Update tracker
            self.tracker.set_position("X", target_x)
            self.tracker.set_position("Y", target_y)

            # Calculate segment duration based on distance and feedrate
            segment_duration = distance / (feedrate / 60.0)
            time.sleep(segment_duration)

        # Calculate any remaining time (due to rounding or small discrepancies)
        elapsed = time.time() - segment_start_time
        remaining = duration - elapsed
        if remaining > 0.001:
            time.sleep(remaining)

    def pause(self, duration: float) -> None:
        """
        Pause for specified duration.

        Args:
            duration: Pause duration in seconds
        """
        time.sleep(duration)
