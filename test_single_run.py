import subprocess
import sys
import unittest

import single_run
from megaexplorer_plugin import CommandError

# A second process that claims the mutex, says so, and holds it until stdin closes.
HOLDER = (
    "import sys, single_run\n"
    "single_run.claim()\n"
    "print('held', flush=True)\n"
    "sys.stdin.read()\n"
)


class SingleRunTest(unittest.TestCase):
    def test_a_second_process_is_refused_while_the_first_runs(self):
        holder = subprocess.Popen([sys.executable, "-c", HOLDER],
                                  stdin=subprocess.PIPE, stdout=subprocess.PIPE, text=True)
        try:
            self.assertEqual(holder.stdout.readline().strip(), "held")
            with self.assertRaises(CommandError) as raised:
                single_run.claim()
            self.assertEqual(str(raised.exception), single_run.ALREADY_RUNNING)
        finally:
            holder.stdin.close()
            holder.wait(timeout=10)
            holder.stdout.close()

    def test_the_mutex_is_free_again_once_the_holder_is_killed(self):
        holder = subprocess.Popen([sys.executable, "-c", HOLDER],
                                  stdin=subprocess.PIPE, stdout=subprocess.PIPE, text=True)
        self.assertEqual(holder.stdout.readline().strip(), "held")
        # The tree, not just holder: a venv's python.exe runs the real interpreter as
        # its child, which is what holds the mutex. The app kills the tree too.
        subprocess.run(["taskkill", "/T", "/F", "/PID", str(holder.pid)], capture_output=True)
        holder.wait(timeout=10)
        holder.stdout.close()
        holder.stdin.close()

        single_run.claim()  # does not raise
        single_run.claim()  # nor does claiming again in the same process


if __name__ == "__main__":
    unittest.main()
