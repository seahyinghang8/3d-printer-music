# 3D Printer Music - Production Primitives

from .config import BAUD_RATE, FREQUENCY_RANGES, MUSIC_Z_HEIGHT, SAFE_LIMITS, STEPS_PER_MM
from .connection import connect_to_printer, find_printer_port
from .exceptions import (
    CommandTimeoutError,
    ConnectionError,
    GCodeError,
    OutOfBoundsError,
    PrinterMusicError,
)
from .gcode_sender import initialize_printer, send_gcode_with_retry
from .motion_planner import MotionPlanner
from .note_player import NotePlayer
from .position_tracker import AbsolutePositionTracker, initialize_printer_position

__all__ = [
    # Connection
    "find_printer_port",
    "connect_to_printer",
    # G-code
    "send_gcode_with_retry",
    "initialize_printer",
    # Position tracking
    "AbsolutePositionTracker",
    "initialize_printer_position",
    # Planning
    "MotionPlanner",
    # Note playing
    "NotePlayer",
    # Exceptions
    "PrinterMusicError",
    "GCodeError",
    "OutOfBoundsError",
    "ConnectionError",
    "CommandTimeoutError",
    # Config
    "SAFE_LIMITS",
    "FREQUENCY_RANGES",
    "STEPS_PER_MM",
    "MUSIC_Z_HEIGHT",
    "BAUD_RATE",
]
