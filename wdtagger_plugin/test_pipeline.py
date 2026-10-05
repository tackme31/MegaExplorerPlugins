import threading
import time
import unittest
from contextlib import closing

from pipeline import pipeline


class PipelineTest(unittest.TestCase):
    def test_every_item_comes_out_once_with_its_stored_result(self):
        results = dict(pipeline(range(20), lambda i: i * 10, lambda i, f: f + 1,
                                lambda i, job: (i, job), workers=3))
        self.assertEqual(results, {i: (i, i * 10 + 1) for i in range(20)})

    def test_a_dropped_item_comes_out_as_none_and_is_not_stored(self):
        stored = []

        def store(item, job):
            stored.append(item)
            return job

        results = dict(pipeline(range(6), lambda i: i,
                                lambda i, f: None if i % 2 else f, store, workers=2))
        self.assertEqual(results, {0: 0, 1: None, 2: 2, 3: None, 4: 4, 5: None})
        self.assertEqual(sorted(stored), [0, 2, 4])

    def test_compute_runs_on_the_calling_thread_and_the_others_do_not(self):
        caller = threading.get_ident()
        seen = {"fetch": set(), "compute": set(), "store": set()}

        def record(stage, value):
            seen[stage].add(threading.get_ident())
            return value

        list(pipeline(range(8), lambda i: record("fetch", i),
                      lambda i, f: record("compute", f),
                      lambda i, job: record("store", job), workers=2))
        self.assertEqual(seen["compute"], {caller})
        self.assertNotIn(caller, seen["fetch"])
        self.assertNotIn(caller, seen["store"])

    def test_no_more_than_workers_calls_of_a_stage_run_at_once(self):
        lock = threading.Lock()
        running = {"fetch": 0, "store": 0}
        peak = {"fetch": 0, "store": 0}

        def slow(stage):
            def call(*args):
                with lock:
                    running[stage] += 1
                    peak[stage] = max(peak[stage], running[stage])
                time.sleep(0.01)
                with lock:
                    running[stage] -= 1
                return args[-1]
            return call

        list(pipeline(range(30), slow("fetch"), lambda i, f: f, slow("store"), workers=3))
        self.assertEqual(peak, {"fetch": 3, "store": 3})

    def test_items_are_not_fetched_far_ahead_of_compute(self):
        fetched = []

        def fetch(i):
            fetched.append(i)
            return i

        run = pipeline(range(100), fetch, lambda i, f: f, lambda i, job: job, workers=2)
        with closing(run):
            next(run)
            time.sleep(0.05)
            # One window waiting for compute, one already handed on to store.
            self.assertLessEqual(len(fetched), 2 * (2 * 2))

    def test_an_error_in_a_stage_ends_the_run(self):
        def fetch(i):
            if i == 3:
                raise ValueError("boom")
            return i

        with self.assertRaises(ValueError):
            list(pipeline(range(10), fetch, lambda i, f: f, lambda i, job: job, workers=2))

    def test_stopping_early_drops_the_queued_work(self):
        stored = []

        def store(item, job):
            stored.append(item)
            return job

        with closing(pipeline(range(100), lambda i: i, lambda i, f: f, store, workers=2)) as run:
            next(run)
        self.assertLess(len(stored), 100)


if __name__ == "__main__":
    unittest.main()
