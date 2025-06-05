import asyncio
import pytest

from phone_spam_checker.distributed_pool import RedisDevicePool, RedisJobQueue


class FakeRedis:
    def __init__(self):
        self.data = {}

    def exists(self, key):
        return key in self.data

    def rpush(self, key, *values):
        self.data.setdefault(key, []).extend(values)

    def blpop(self, key, timeout=0):
        lst = self.data.get(key, [])
        if not lst:
            return None
        return (key, lst.pop(0))

    def llen(self, key):
        return len(self.data.get(key, []))


def test_redis_device_pool():
    client = FakeRedis()
    pool = RedisDevicePool("pool:test", ["dev1"], client)
    with pool as dev:
        assert dev == "dev1"
        assert len(pool) == 0
    assert len(pool) == 1


@pytest.mark.asyncio
async def test_redis_job_queue():
    client = FakeRedis()
    q = RedisJobQueue("jobs", client)
    await q.put(("job", ["1"], "svc"))
    job_id, nums, svc = await q.get()
    assert job_id == "job"
    assert nums == ["1"]
    assert svc == "svc"
    q.task_done()
    await q.join()

