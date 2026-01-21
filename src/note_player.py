"""High-level API for playing notes on 3D printer."""

import time
from typing import Literal

import serial

from .config import FREQUENCY_RANGES
from .gcode_sender import send_gcode_with_retry
from .motion_planner import MotionPlanner
from .position_tracker import AbsolutePositionTracker


Axis = Literal["X", "Y", "Z"]
Volume = Literal["soft", "normal", "loud"]


class NotePlayer:
    """
    Simple API for playing notes on 3D printer motors.

    Usage:
        player = NotePlayer(serial_connection, tracker, planner)
        player.play_note("Y", 440.0, 1.0)  # Play A4 for 1 second
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

    def play_note(
        self,
        axis: Axis,
        frequency: float,
        duration: float,
        debug: bool = False
    ) -> None:
        """
        Play a note by moving motor at specific frequency.

        Blocking call - returns after note completes.

        Args:
            axis: Which axis to use ("X", "Y", or "Z")
            frequency: Frequency in Hz
            duration: Duration in seconds
            debug: Print debug information

        Raises:
            OutOfBoundsError: Note cannot be played within boundaries
        """
        # Validate frequency is in range for axis
        min_freq, max_freq = FREQUENCY_RANGES[axis]
        if not (min_freq <= frequency <= max_freq):
            raise ValueError(
                f"Frequency {frequency} Hz out of range for {axis} axis "
                f"[{min_freq}, {max_freq}]"
            )

        # Get current position
        current_pos = self.tracker.get_position(axis)
        if current_pos is None:
            raise ValueError(f"Unknown position for {axis} axis. Initialize tracker first.")

        # Plan movement
        target, direction = self.planner.plan_note_movement(
            axis, frequency, duration, current_pos
        )

        # Calculate feedrate
        feedrate = self.planner.frequency_to_feedrate(axis, frequency)

        if debug:
            distance = abs(target - current_pos)
            direction_str = "positive" if direction > 0 else "negative"
            print(f"Playing {frequency:.1f} Hz on {axis} for {duration:.2f}s")
            print(f"  Current: {current_pos:.1f}mm -> Target: {target:.1f}mm")
            print(f"  Distance: {distance:.1f}mm, Direction: {direction_str}")
            print(f"  Feedrate: {feedrate:.1f} mm/min")

        # Execute movement (send G-code command)
        self.tracker.move_to(self.ser, axis, target, feedrate, debug=debug)

        # Wait for movement to complete
        # The G-code command returns "ok" immediately, but movement takes time
        time.sleep(duration)

    def pause(self, duration: float) -> None:
        """
        Pause for specified duration.

        Args:
            duration: Pause duration in seconds
        """
        time.sleep(duration)

    def play_note_diagonal(
        self,
        frequency_low: float,
        frequency_high: float,
        duration: float,
        debug: bool = False
    ) -> None:
        """
        Play two notes simultaneously on X and Y axes (diagonal motion).

        Lower frequency plays on Y axis, higher frequency on X axis.
        Moves both axes at the same time, producing two frequencies.

        Args:
            frequency_low: Lower frequency in Hz (will play on Y axis)
            frequency_high: Higher frequency in Hz (will play on X axis)
            duration: Duration in seconds
            debug: Print debug information

        Raises:
            OutOfBoundsError: Movement cannot be completed within boundaries
        """
        # Assign frequencies: lower on Y (closest to user), higher on X
        frequency_y = frequency_low
        frequency_x = frequency_high

        # Validate frequencies
        for axis, freq in [("X", frequency_x), ("Y", frequency_y)]:
            min_freq, max_freq = FREQUENCY_RANGES[axis]
            if not (min_freq <= freq <= max_freq):
                raise ValueError(
                    f"Frequency {freq} Hz out of range for {axis} axis "
                    f"[{min_freq}, {max_freq}]"
                )

        # Get current positions
        current_x = self.tracker.get_position("X")
        current_y = self.tracker.get_position("Y")
        if current_x is None or current_y is None:
            raise ValueError("Unknown position. Initialize tracker first.")

        # Plan movements for both axes
        target_x, dir_x = self.planner.plan_note_movement("X", frequency_x, duration, current_x)
        target_y, dir_y = self.planner.plan_note_movement("Y", frequency_y, duration, current_y)

        # Calculate feedrates
        feedrate_x = self.planner.frequency_to_feedrate("X", frequency_x)
        feedrate_y = self.planner.frequency_to_feedrate("Y", frequency_y)

        # Use the higher feedrate for diagonal move to maintain timing
        feedrate = max(feedrate_x, feedrate_y)

        if debug:
            distance_x = abs(target_x - current_x)
            distance_y = abs(target_y - current_y)
            print(f"Playing diagonal: X={frequency_x:.1f} Hz, Y={frequency_y:.1f} Hz for {duration:.2f}s")
            print(f"  X: {current_x:.1f}mm -> {target_x:.1f}mm (distance: {distance_x:.1f}mm)")
            print(f"  Y: {current_y:.1f}mm -> {target_y:.1f}mm (distance: {distance_y:.1f}mm)")
            print(f"  Feedrate: {feedrate:.1f} mm/min")

        # Send diagonal move command
        command = f"G1 X{target_x:.3f} Y{target_y:.3f} F{feedrate:.1f}"
        send_gcode_with_retry(self.ser, command, debug=debug)

        # Update tracker
        self.tracker.set_position("X", target_x)
        self.tracker.set_position("Y", target_y)

        # Wait for movement to complete
        time.sleep(duration)

    def validate_note(self, axis: Axis, frequency: float, duration: float) -> bool:
        """
        Check if note can be played without exceeding boundaries.

        Args:
            axis: Which axis
            frequency: Frequency in Hz
            duration: Duration in seconds

        Returns:
            True if note is possible, False otherwise
        """
        # Check frequency range
        min_freq, max_freq = FREQUENCY_RANGES[axis]
        if not (min_freq <= frequency <= max_freq):
            return False

        # Check if movement fits in boundaries
        return self.planner.validate_note_possible(axis, frequency, duration)

    def play_note_with_volume(
        self,
        frequency: float,
        duration: float,
        volume: Volume = "normal",
        debug: bool = False
    ) -> None:
        """
        Play a note with volume control using different axes.

        Volume modes:
        - "soft": Uses X axis only (quieter, farther from user)
        - "normal": Uses Y axis only (normal volume, closest to user)
        - "loud": Uses both X and Y axes moving equally (louder, combined sound)

        Args:
            frequency: Frequency in Hz
            duration: Duration in seconds
            volume: Volume mode ("soft", "normal", or "loud")
            debug: Print debug information

        Raises:
            OutOfBoundsError: Movement cannot be completed within boundaries
            ValueError: Invalid frequency or volume mode
        """
        if volume == "soft":
            # Use X axis (farther from user = quieter)
            self.play_note("X", frequency, duration, debug=debug)
        elif volume == "normal":
            # Use Y axis (closest to user = normal volume)
            self.play_note("Y", frequency, duration, debug=debug)
        elif volume == "loud":
            # Use both axes moving equally (combined = louder)
            # Both play the same frequency for maximum volume
            self.play_note_diagonal(frequency, frequency, duration, debug=debug)
        else:
            raise ValueError(f"Invalid volume mode: {volume}. Must be 'soft', 'normal', or 'loud'")
