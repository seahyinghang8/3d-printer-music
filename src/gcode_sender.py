"""G-code command sending with retry logic."""

import time

import serial

from .exceptions import CommandTimeoutError, GCodeError


def send_gcode(
    ser: serial.Serial,
    command: str,
    wait_for_ok: bool = True,
    timeout: float = 5.0
) -> str:
    """
    Send G-code command and wait for response.

    Args:
        ser: Serial connection
        command: G-code command to send
        wait_for_ok: Whether to wait for "ok" response
        timeout: Max time to wait for response (seconds)

    Returns:
        Response from printer

    Raises:
        CommandTimeoutError: No response within timeout
        GCodeError: Printer returned error
    """
    # Send command
    ser.write(f"{command}\n".encode())

    if not wait_for_ok:
        return ""

    # Wait for response
    start_time = time.time()
    response_lines = []

    while time.time() - start_time < timeout:
        if ser.in_waiting:
            line = ser.readline().decode().strip()
            response_lines.append(line)

            # Check response type
            if "ok" in line.lower():
                return "\n".join(response_lines)

            elif "error" in line.lower():
                raise GCodeError(f"Printer error: {line}")

    # Timeout
    raise CommandTimeoutError(f"Command timed out: {command}")


def send_gcode_with_retry(
    ser: serial.Serial,
    command: str,
    max_retries: int = 50,
    timeout: float = 5.0,
    debug: bool = False
) -> str:
    """
    Send G-code with automatic retry on "busy" response.

    Keeps retrying same command if printer responds "busy: processing".
    Only proceeds when printer responds "ok".

    Args:
        ser: Serial connection
        command: G-code command
        max_retries: Max retry attempts for "busy"
        timeout: Timeout per attempt
        debug: Print debug info (command sent, responses)

    Returns:
        Final response from printer

    Raises:
        CommandTimeoutError: Exceeded retries or timeout
        GCodeError: Printer returned error
    """
    if debug:
        print(f">> {command}")

    for attempt in range(max_retries):
        # Send command only on first attempt
        if attempt == 0:
            ser.write(f"{command}\n".encode())

        # Wait for response
        start_time = time.time()
        response_lines = []
        saw_busy = False

        while time.time() - start_time < timeout:
            if ser.in_waiting:
                line = ser.readline().decode().strip()
                if line:  # Only add non-empty lines
                    response_lines.append(line)
                    if debug:
                        print(f"<< {line}")

                # Check response type
                if "ok" in line.lower():
                    return "\n".join(response_lines)

                elif "busy" in line.lower():
                    # Printer busy, wait and check again
                    saw_busy = True
                    if debug:
                        print("   (Printer busy, waiting for 'ok'...)")
                    time.sleep(0.05)  # Brief pause
                    # Don't break - keep waiting for "ok"

                elif "error" in line.lower():
                    raise GCodeError(f"Printer error: {line}")

        # If we timed out without seeing ok or busy, that's an error
        if not saw_busy:
            raise CommandTimeoutError(f"Command timed out: {command}")

    # Exceeded max retries (kept seeing busy, never got ok)
    raise CommandTimeoutError(f"Command timed out after {max_retries} attempts: {command}")


def initialize_printer(ser: serial.Serial) -> None:
    """
    Initialize printer for music playback.

    - Clears any startup messages
    - Sets absolute positioning mode (G90)
    - Homes all axes (G28)
    - Lifts Z to safe height

    Args:
        ser: Serial connection
    """
    # Clear startup messages
    time.sleep(0.5)
    while ser.in_waiting:
        ser.readline()

    # Set absolute positioning mode
    send_gcode_with_retry(ser, "G90")
