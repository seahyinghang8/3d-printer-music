"""Absolute position tracking for 3D printer."""

import time
from typing import Optional

import serial

from .config import MUSIC_Z_HEIGHT, SAFE_LIMITS
from .exceptions import OutOfBoundsError
from .gcode_sender import send_gcode_with_retry


class AbsolutePositionTracker:
    """
    Track printer head position in absolute coordinates.

    Uses G90 (absolute positioning) mode.
    """

    def __init__(self):
        """Initialize with unknown position."""
        self.position = {"X": None, "Y": None, "Z": None}

    def set_position(self, axis: str, position: float) -> None:
        """Update known position for axis."""
        self.position[axis] = position

    def get_position(self, axis: str) -> Optional[float]:
        """Get current position for axis (None if unknown)."""
        return self.position.get(axis)

    def move_to(
        self,
        ser: serial.Serial,
        axis: str,
        target: float,
        feedrate: float,
        debug: bool = False
    ) -> None:
        """
        Move to absolute position and update tracker.

        Sends: G1 {axis}{target} F{feedrate}

        Args:
            ser: Serial connection
            axis: Axis to move ("X", "Y", or "Z")
            target: Target position in mm
            feedrate: Movement speed in mm/min
            debug: Print debug info

        Raises:
            OutOfBoundsError: Target position exceeds safe boundaries
        """
        # Validate boundary
        if axis in SAFE_LIMITS:
            min_limit, max_limit = SAFE_LIMITS[axis]
            if not (min_limit <= target <= max_limit):
                raise OutOfBoundsError(
                    f"{axis} target {target:.1f}mm outside safe range "
                    f"[{min_limit}, {max_limit}]"
                )

        # Send absolute move command
        command = f"G1 {axis}{target:.3f} F{feedrate:.1f}"
        send_gcode_with_retry(ser, command, debug=debug)

        # Update tracked position
        self.position[axis] = target

    def reset(self) -> None:
        """Reset position to unknown (call after homing)."""
        self.position = {"X": None, "Y": None, "Z": None}


def initialize_printer_position(
    ser: serial.Serial,
    tracker: AbsolutePositionTracker,
    debug: bool = False
) -> None:
    """
    Home printer and set up for music playback.

    - Homes all axes (G28)
    - Sets absolute positioning mode (G90)
    - Moves X, Y to center of safe zone
    - Moves Z to safe music height
    - Updates tracker with known positions

    Args:
        ser: Serial connection
        tracker: Position tracker to update
        debug: Print debug info
    """
    # Home all axes
    send_gcode_with_retry(ser, "G28", debug=debug)

    # Set absolute positioning mode
    send_gcode_with_retry(ser, "G90", debug=debug)

    # Reset tracker (position is now at home)
    tracker.reset()
    tracker.set_position("X", 0.0)
    tracker.set_position("Y", 0.0)
    tracker.set_position("Z", 0.0)

    # Lift Z first to avoid dragging nozzle across bed
    tracker.move_to(ser, "Z", MUSIC_Z_HEIGHT, 1000, debug=debug)

    # Move X and Y to a position just inside the safe zone edge
    # (Home position 0,0 is outside safe limits of 10-225mm)
    # Start about 20% in from the minimum edge to give room for movement in both directions
    x_min, x_max = SAFE_LIMITS["X"]
    y_min, y_max = SAFE_LIMITS["Y"]

    x_start = x_min + (x_max - x_min) * 0.2  # 20% in from min edge
    y_start = y_min + (y_max - y_min) * 0.2  # 20% in from min edge

    # Send single G-code command to move both X and Y together
    command = f"G1 X{x_start:.3f} Y{y_start:.3f} F3000"
    send_gcode_with_retry(ser, command, debug=debug)
    tracker.set_position("X", x_start)
    tracker.set_position("Y", y_start)

    # Wait for movement to complete and printer to settle
    print(f"\n✓ Printer positioned at: X={x_start:.1f}mm, Y={y_start:.1f}mm, Z={MUSIC_Z_HEIGHT:.1f}mm")
    print("Press Enter when ready to start playing...")
    input()
