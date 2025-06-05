import pytest

from phone_spam_checker.device_pool import DevicePool


def test_device_released_on_exception():
    pool = DevicePool(["dev1"])
    with pytest.raises(RuntimeError):
        with pool:
            raise RuntimeError("boom")
    assert len(pool) == 1
