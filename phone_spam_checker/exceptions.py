class DeviceConnectionError(RuntimeError):
    """Raised when an ADB device cannot be reached."""


class JobAlreadyRunningError(RuntimeError):
    """Raised when a job is already in progress."""
