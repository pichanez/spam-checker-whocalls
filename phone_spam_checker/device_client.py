import logging

logger = logging.getLogger(__name__)


class AndroidDeviceClient:
    """Wrapper around uiautomator2 providing common operations."""

    def __init__(self, device_id: str) -> None:
        import uiautomator2 as u2

        logger.info("Connecting to device %s", device_id)
        self.d = u2.connect(device_id)
        for fn in ("screen_on", "unlock"):
            try:
                getattr(self.d, fn)()
            except Exception:
                pass

    def start_app(self, package: str, activity: str) -> bool:
        """Launch application and handle permission dialogs."""
        try:
            self.d.app_start(package, activity=activity)
        except Exception as e:
            logger.error("Failed to launch %s: %s", package, e)
            return False
        self.handle_permissions()
        return True

    def stop_app(self, package: str) -> None:
        logger.info("Stopping %s", package)
        self.d.app_stop(package)

    def handle_permissions(self) -> None:
        """Tap common permission dialog buttons if present."""
        for text in ("ALLOW", "Allow", "ALLOW ALL THE TIME"):
            if self.d(text=text).exists(timeout=2):
                logger.info("Confirming permission dialog: %s", text)
                self.d(text=text).click()
