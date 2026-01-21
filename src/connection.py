"""Printer connection utilities."""

import glob
import time
from typing import Optional

import serial

from .config import BAUD_RATE
from .exceptions import ConnectionError as PrinterConnectionError


def find_printer_port(user_port: Optional[str] = None) -> str:
    """
    Find USB serial port for 3D printer.

    Args:
        user_port: Optional explicit port path

    Returns:
        Path to printer serial port

    Raises:
        PrinterConnectionError: No printer port found
    """
    if user_port:
        return user_port

    # Search for USB serial ports in order of preference
    patterns = [
        "/dev/usb*",      # Generic USB
        "/dev/cu.usb*",   # macOS
        "/dev/ttyUSB*",   # Linux
        "/dev/ttyACM*",   # Linux Arduino-style
    ]

    for pattern in patterns:
        ports = glob.glob(pattern)
        if ports:
            return ports[0]

    raise PrinterConnectionError("No printer port found. Please specify port explicitly.")


def connect_to_printer(port: str, baud_rate: int = BAUD_RATE) -> serial.Serial:
    """
    Open serial connection to printer.

    Args:
        port: Serial port path
        baud_rate: Communication speed (default 115200)

    Returns:
        Open serial connection

    Raises:
        PrinterConnectionError: Failed to open connection
    """
    try:
        ser = serial.Serial(port, baud_rate, timeout=2)
        # Wait for printer to boot/initialize
        time.sleep(2)
        return ser
    except (serial.SerialException, OSError) as e:
        raise PrinterConnectionError(f"Failed to connect to printer on {port}: {e}")
