import pytest


class FakeRedis:
    def __init__(self):
        self.values = {}
        self.sorted_sets = {}

    async def set(self, key, value, ex=None, nx=False):
        if nx and key in self.values:
            return False
        self.values[key] = value
        return True

    async def get(self, key):
        return self.values.get(key)

    async def delete(self, key):
        existed = key in self.values
        self.values.pop(key, None)
        return int(existed)

    async def zadd(self, name, mapping):
        self.sorted_sets.setdefault(name, {}).update(mapping)
        return len(mapping)

    async def zrangebyscore(self, name, min_score, max_score, start=0, num=None):
        items = [
            member
            for member, score in self.sorted_sets.get(name, {}).items()
            if float(min_score) <= score <= float(max_score)
        ]
        items.sort(key=lambda member: self.sorted_sets[name][member])
        if num is None:
            return items[start:]
        return items[start : start + num]

    async def zrem(self, name, *members):
        count = 0
        for member in members:
            if member in self.sorted_sets.get(name, {}):
                del self.sorted_sets[name][member]
                count += 1
        return count


@pytest.fixture
def fake_redis():
    return FakeRedis()
