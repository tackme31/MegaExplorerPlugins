"""Overlaps the network-bound stages of tagging with the GPU-bound one."""

from collections import deque
from concurrent.futures import ThreadPoolExecutor

_END = object()


def pipeline(items, fetch, compute, store, workers):
    """Runs fetch(item) and then store(item, job) on `workers` threads each, and
    job = compute(item, fetched) on the calling thread in between; compute
    returns None to drop the item before store.

    Yields (item, stored) as each item finishes, stored being None for a dropped
    item. At most 2 * workers items wait in each threaded stage, so a long list
    is not fetched far ahead of the model. An exception from any stage ends the
    run: queued calls are dropped and running ones are waited for. Close the
    generator (contextlib.closing) so that also happens when the caller stops."""
    window = 2 * workers
    fetchers = ThreadPoolExecutor(workers, thread_name_prefix="fetch")
    storers = ThreadPoolExecutor(workers, thread_name_prefix="store")
    fetching = deque()
    storing = deque()
    pending = iter(items)
    try:
        while True:
            while len(fetching) < window:
                item = next(pending, _END)
                if item is _END:
                    break
                fetching.append((item, fetchers.submit(fetch, item)))
            if fetching and len(storing) < window:
                item, future = fetching.popleft()
                job = compute(item, future.result())
                if job is None:
                    yield item, None
                else:
                    storing.append((item, storers.submit(store, item, job)))
            elif storing:
                item, future = storing.popleft()
                yield item, future.result()
            else:
                return
    finally:
        fetchers.shutdown(cancel_futures=True)
        storers.shutdown(cancel_futures=True)
