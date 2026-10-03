"""Drives MegaDirStatPlugin.exe over stdio the way MEGA Explorer does.

Run through ctest (which sets MEGADIRSTAT_PLUGIN_EXE, PATH and the offscreen
platform), or by hand:
    set MEGADIRSTAT_PLUGIN_EXE=...\\bin\\MegaDirStatPlugin.exe
    python -m unittest -v test_protocol
"""
import json
import os
import queue
import subprocess
import threading
import unittest

EXE = os.environ.get("MEGADIRSTAT_PLUGIN_EXE", "")
TIMEOUT = 10


class Host:
    """The app's side of one run: writes requests, collects what the plugin sends."""

    def __init__(self):
        env = dict(os.environ)
        env.setdefault("QT_QPA_PLATFORM", "offscreen")
        self.proc = subprocess.Popen([EXE], stdin=subprocess.PIPE, stdout=subprocess.PIPE,
                                     stderr=subprocess.PIPE, env=env)
        self.messages = queue.Queue()
        self.stderr = []
        threading.Thread(target=self._read_stdout, daemon=True).start()
        threading.Thread(target=self._read_stderr, daemon=True).start()

    def _read_stdout(self):
        for line in self.proc.stdout:
            self.messages.put(json.loads(line))

    def _read_stderr(self):
        for line in self.proc.stderr:
            self.stderr.append(line.decode("utf-8", "replace").rstrip())

    def send(self, message):
        message["jsonrpc"] = "2.0"
        self.proc.stdin.write((json.dumps(message) + "\n").encode("utf-8"))
        self.proc.stdin.flush()

    def request(self, id, method, params=None):
        self.send({"id": id, "method": method, "params": params or {}})

    def reply(self, request, result):
        self.send({"id": request["id"], "result": result})

    def reply_error(self, request, code, message):
        self.send({"id": request["id"], "error": {"code": code, "message": message}})

    def next(self, timeout=TIMEOUT):
        return self.messages.get(timeout=timeout)

    def expect_quiet(self, seconds=0.5):
        try:
            message = self.messages.get(timeout=seconds)
        except queue.Empty:
            return
        raise AssertionError(f"unexpected message: {message}")

    def initialize(self):
        self.request(1, "initialize", {"apiVersion": 1})
        return self.next()

    def execute(self, items):
        self.request(2, "command.execute", {
            "invocationId": 1, "commandId": "show",
            "context": {"site": "selection", "items": items}})

    def shutdown(self):
        self.request(3, "shutdown")
        response = self.next()
        self.proc.stdin.close()
        return response, self.proc.wait(timeout=TIMEOUT)

    def close(self):
        if self.proc.poll() is None:
            self.proc.kill()
            self.proc.wait()


def folder(handle, name):
    return {"handle": handle, "name": name, "type": "folder"}


def tree(root, count):
    """count files under one subfolder of root, in items.descendants' pre-order."""
    sub = root + "-sub"
    items = [{"handle": sub, "name": "sub", "type": "folder", "parent": root, "size": 0, "mtime": 0}]
    items += [{"handle": f"{root}-{i}", "name": f"f{i}.jpg", "type": "file", "parent": sub,
               "size": i + 1, "mtime": 1700000000} for i in range(count)]
    return items


@unittest.skipUnless(os.path.isfile(EXE), "MEGADIRSTAT_PLUGIN_EXE does not name the plugin")
class ProtocolTest(unittest.TestCase):
    def setUp(self):
        self.host = Host()
        self.addCleanup(self.host.close)

    def test_initialize_then_shutdown_exits_cleanly(self):
        self.assertEqual(self.host.initialize()["result"], {"apiVersion": 1})
        response, code = self.host.shutdown()
        self.assertEqual(response, {"jsonrpc": "2.0", "id": 3, "result": {}})
        self.assertEqual(code, 0)

    def test_exits_when_stdin_closes(self):
        self.host.initialize()
        self.host.proc.stdin.close()
        self.assertEqual(self.host.proc.wait(timeout=TIMEOUT), 0)

    def test_unknown_method_is_rejected(self):
        self.host.request(7, "no.such.method")
        self.assertEqual(self.host.next()["error"]["code"], -32601)

    def test_selection_without_a_folder_fails_the_command(self):
        self.host.initialize()
        self.host.execute([{"handle": "F1", "name": "a.jpg", "type": "file"}])
        response = self.host.next()
        self.assertEqual(response["id"], 2)
        self.assertEqual(response["error"]["code"], -32000)
        self.assertEqual(self.host.shutdown()[1], 0)

    def test_reads_every_page_of_every_selected_folder(self):
        trees = {"R1": tree("R1", 1500), "R2": tree("R2", 10)}
        self.host.initialize()
        self.host.execute([folder("R1", "one"), folder("R2", "two")])

        get = self.host.next()
        self.assertEqual(get["method"], "items.get")
        self.assertEqual(get["params"]["handles"], ["R1", "R2"])
        self.assertIn("parent", get["params"]["fields"])
        self.host.reply(get, {"items": [{"handle": "R1", "name": "one", "parent": "X"},
                                        {"handle": "R2", "name": "two", "parent": "X"}]})

        pages = []
        while True:
            try:
                call = self.host.next(timeout=1)
            except queue.Empty:
                break
            self.assertEqual(call["method"], "items.descendants")
            params = call["params"]
            pages.append((params["handle"], params.get("cursor")))
            self.assertEqual(set(params["fields"]), {"name", "type", "parent", "size", "mtime"})
            items = trees[params["handle"]]
            offset = int(params.get("cursor") or 0)
            page = items[offset:offset + params["limit"]]
            end = offset + len(page)
            self.host.reply(call, {"items": page,
                                   "nextCursor": str(end) if end < len(items) else None})

        self.assertEqual(pages, [("R1", None), ("R1", "1000"), ("R2", None)])
        # The command stays open while the window is; the app's way out is closing stdin.
        self.host.proc.stdin.close()
        self.assertEqual(self.host.proc.wait(timeout=TIMEOUT), 0)
        # Only the plugin's own categories: the offscreen platform warns on its own.
        self.assertFalse([line for line in self.host.stderr if "[dirstat." in line])

    def test_load_error_stops_reading(self):
        self.host.initialize()
        self.host.execute([folder("R1", "gone")])
        get = self.host.next()
        self.host.reply_error(get, -32002, "No such item: R1")
        self.host.expect_quiet()


if __name__ == "__main__":
    unittest.main()
