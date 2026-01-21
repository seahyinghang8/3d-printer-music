"""Custom exceptions for 3D printer music."""


class PrinterMusicError(Exception):
    """Base exception for printer music errors."""
    pass


class GCodeError(PrinterMusicError):
    """G-code command failed or returned error."""
    pass


class OutOfBoundsError(PrinterMusicError):
    """Movement would exceed safe boundaries."""
    pass


class ConnectionError(PrinterMusicError):
    """Failed to connect to printer."""
    pass


class CommandTimeoutError(PrinterMusicError):
    """Command did not receive response in time."""
    pass
