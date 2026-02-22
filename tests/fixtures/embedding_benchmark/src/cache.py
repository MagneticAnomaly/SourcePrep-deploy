"""Caching module — LRU cache implementation and memoize decorator."""

import functools
import threading
from collections import OrderedDict
from typing import Any, Callable, Optional, TypeVar

F = TypeVar("F", bound=Callable[..., Any])


class LRUCache:
    """A thread-safe Least Recently Used (LRU) cache.

    Stores key-value pairs up to a maximum capacity. When the cache
    is full and a new item is added, the least recently accessed item
    is evicted.

    Usage:
        cache = LRUCache(capacity=100)
        cache.put("key", "value")
        result = cache.get("key")  # returns "value"
    """

    def __init__(self, capacity: int = 128):
        self.capacity = capacity
        self._store: OrderedDict[str, Any] = OrderedDict()
        self._lock = threading.Lock()
        self._hits = 0
        self._misses = 0

    def get(self, key: str) -> Optional[Any]:
        """Retrieve a value by key. Returns None if not found.

        Accessing a key moves it to the most-recently-used position.
        """
        with self._lock:
            if key in self._store:
                self._store.move_to_end(key)
                self._hits += 1
                return self._store[key]
            self._misses += 1
            return None

    def put(self, key: str, value: Any) -> None:
        """Store a key-value pair. Evicts LRU item if at capacity."""
        with self._lock:
            if key in self._store:
                self._store.move_to_end(key)
                self._store[key] = value
            else:
                if len(self._store) >= self.capacity:
                    self._store.popitem(last=False)
                self._store[key] = value

    def delete(self, key: str) -> bool:
        """Remove a key from the cache. Returns True if the key existed."""
        with self._lock:
            if key in self._store:
                del self._store[key]
                return True
            return False

    def clear(self) -> None:
        """Remove all items from the cache."""
        with self._lock:
            self._store.clear()
            self._hits = 0
            self._misses = 0

    @property
    def size(self) -> int:
        """Current number of items in the cache."""
        return len(self._store)

    @property
    def hit_rate(self) -> float:
        """Cache hit rate as a fraction (0.0 to 1.0)."""
        total = self._hits + self._misses
        return self._hits / total if total > 0 else 0.0


def memoize(max_size: int = 256) -> Callable[[F], F]:
    """A decorator that memoizes function results using an LRU cache.

    Caches the return value of a function based on its arguments.
    Uses string representation of args as cache keys.

    Args:
        max_size: Maximum number of cached results.

    Usage:
        @memoize(max_size=100)
        def expensive_computation(x, y):
            return x ** y
    """
    cache = LRUCache(capacity=max_size)

    def decorator(func: F) -> F:
        @functools.wraps(func)
        def wrapper(*args: Any, **kwargs: Any) -> Any:
            key = f"{func.__name__}:{args}:{sorted(kwargs.items())}"
            result = cache.get(key)
            if result is not None:
                return result
            result = func(*args, **kwargs)
            cache.put(key, result)
            return result

        wrapper.cache = cache  # type: ignore[attr-defined]
        return wrapper  # type: ignore[return-value]

    return decorator
