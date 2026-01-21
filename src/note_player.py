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

        If the required movement distance exceeds available space, the function
        automatically executes multiple back-and-forth movements to maintain
        the correct frequency throughout the entire duration.

        Blocking call - returns after note completes.

        Args:
            axis: Which axis to use ("X", "Y", or "Z")
            frequency: Frequency in Hz
            duration: Duration in seconds
            debug: Print debug information

        Raises:
            ValueError: Invalid frequency or unknown position
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

        # Plan movement(s) - may return multiple segments if distance is large
        positions = self.planner.plan_note_movement(
            axis, frequency, duration, current_pos
        )

        # Calculate feedrate for the frequency
        feedrate = self.planner.frequency_to_feedrate(axis, frequency)

        if debug:
            # Calculate total distance across all segments
            pos = current_pos
            total_distance = 0.0
            for target_pos in positions:
                total_distance += abs(target_pos - pos)
                pos = target_pos
            print(f"Playing {frequency:.1f} Hz on {axis} for {duration:.2f}s")
            print(f"  Total distance: {total_distance:.1f}mm across {len(positions)} segment(s)")
            print(f"  Feedrate: {feedrate:.1f} mm/min")

        # Execute all movements
        segment_start_time = time.time()
        for i, target_pos in enumerate(positions):
            current = self.tracker.get_position(axis)
            if current is None:
                raise ValueError(f"Lost position tracking for {axis} axis during movement.")

            distance = abs(target_pos - current)
            direction_str = "positive" if target_pos > current else "negative"

            if debug:
                print(f"  Segment {i+1}/{len(positions)}: {current:.1f}mm -> {target_pos:.1f}mm "
                      f"({distance:.1f}mm {direction_str})")

            # Execute movement
            self.tracker.move_to(self.ser, axis, target_pos, feedrate, debug=debug)

            # Calculate time for this segment based on distance and feedrate
            segment_duration = (distance / (feedrate / 60.0))
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

        If either axis requires multiple segments due to boundary constraints,
        the movements are synchronized to maintain both frequencies throughout
        the entire duration. Both axes will execute their movements in parallel,
        bouncing off boundaries as needed.

        Args:
            frequency_low: Lower frequency in Hz (will play on Y axis)
            frequency_high: Higher frequency in Hz (will play on X axis)
            duration: Duration in seconds
            debug: Print debug information

        Raises:
            ValueError: Invalid frequency or unknown position
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

        # Plan movements for both axes (may return multiple segments)
        positions_x = self.planner.plan_note_movement("X", frequency_x, duration, current_x)
        positions_y = self.planner.plan_note_movement("Y", frequency_y, duration, current_y)

        # Calculate feedrates for each axis
        feedrate_x = self.planner.frequency_to_feedrate("X", frequency_x)
        feedrate_y = self.planner.frequency_to_feedrate("Y", frequency_y)

        if debug:
            # Calculate total distances
            temp_pos_x = current_x
            total_distance_x = 0.0
            for target_pos in positions_x:
                total_distance_x += abs(target_pos - temp_pos_x)
                temp_pos_x = target_pos

            temp_pos_y = current_y
            total_distance_y = 0.0
            for target_pos in positions_y:
                total_distance_y += abs(target_pos - temp_pos_y)
                temp_pos_y = target_pos

            print(f"Playing diagonal: X={frequency_x:.1f} Hz, Y={frequency_y:.1f} Hz for {duration:.2f}s")
            print(f"  X: {len(positions_x)} segment(s), total distance: {total_distance_x:.1f}mm")
            print(f"  Y: {len(positions_y)} segment(s), total distance: {total_distance_y:.1f}mm")
            print(f"  Feedrates: X={feedrate_x:.1f}, Y={feedrate_y:.1f} mm/min")

        # Execute movements - need to interleave both axes' segments
        # We'll process both position lists simultaneously
        segment_start_time = time.time()

        idx_x = 0
        idx_y = 0

        while idx_x < len(positions_x) or idx_y < len(positions_y):
            # Get next target for each axis (or stay at current position if done)
            if idx_x < len(positions_x):
                target_x = positions_x[idx_x]
                current_x_pos = self.tracker.get_position("X")
                if current_x_pos is None:
                    raise ValueError("Lost position tracking for X axis during movement.")
                distance_x = abs(target_x - current_x_pos)
                idx_x += 1
            else:
                # X is done, stay at current position
                current_x_pos = self.tracker.get_position("X")
                if current_x_pos is None:
                    raise ValueError("Lost position tracking for X axis during movement.")
                target_x = current_x_pos
                distance_x = 0.0

            if idx_y < len(positions_y):
                target_y = positions_y[idx_y]
                current_y_pos = self.tracker.get_position("Y")
                if current_y_pos is None:
                    raise ValueError("Lost position tracking for Y axis during movement.")
                distance_y = abs(target_y - current_y_pos)
                idx_y += 1
            else:
                # Y is done, stay at current position
                current_y_pos = self.tracker.get_position("Y")
                if current_y_pos is None:
                    raise ValueError("Lost position tracking for Y axis during movement.")
                target_y = current_y_pos
                distance_y = 0.0

            if debug:
                print(f"  Segment: X {current_x_pos:.1f}->{target_x:.1f}mm, Y {current_y_pos:.1f}->{target_y:.1f}mm")

            # Execute diagonal movement using the appropriate feedrate
            # Use the higher feedrate to maintain timing
            feedrate = max(feedrate_x, feedrate_y)
            command = f"G1 X{target_x:.3f} Y{target_y:.3f} F{feedrate:.1f}"
            send_gcode_with_retry(self.ser, command, debug=debug)

            # Update tracker
            self.tracker.set_position("X", target_x)
            self.tracker.set_position("Y", target_y)

            # Calculate segment duration based on the longer movement
            # Time = distance / (feedrate / 60) for each axis
            if distance_x > 0:
                duration_x = distance_x / (feedrate_x / 60.0)
            else:
                duration_x = 0.0

            if distance_y > 0:
                duration_y = distance_y / (feedrate_y / 60.0)
            else:
                duration_y = 0.0

            segment_duration = max(duration_x, duration_y)
            time.sleep(segment_duration)

        # Calculate any remaining time
        elapsed = time.time() - segment_start_time
        remaining = duration - elapsed
        if remaining > 0.001:
            time.sleep(remaining)

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

        If movements require bouncing between boundaries, this is handled
        automatically by the underlying play_note methods.

        Args:
            frequency: Frequency in Hz
            duration: Duration in seconds
            volume: Volume mode ("soft", "normal", or "loud")
            debug: Print debug information

        Raises:
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
