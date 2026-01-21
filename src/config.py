"""Configuration constants for 3D printer music."""

# Serial communication
BAUD_RATE = 115200

# Motor specifications
STEPS_PER_MM = {
    "X": 80,
    "Y": 80,
    "Z": 400,
}

# Frequency ranges (Hz) for each axis
FREQUENCY_RANGES = {
    "X": (130.81, 12543.85),
    "Y": (130.81, 12543.85),
    "Z": (123.47, 1864.66),
}

# Safe boundaries (mm) - 10mm margin on X/Y
SAFE_LIMITS = {
    "X": (10.0, 225.0),
    "Y": (10.0, 225.0),
    "Z": (3.0, 200.0),
}

# Z height for music playback (lift nozzle safely)
MUSIC_Z_HEIGHT = 3.0
