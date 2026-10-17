"""Pseudo-terminal fixture running the real firmware parser and mode state machine.

No GPIO/PWM: simulates centering delay only, not actual servo dynamics.
"""
import importlib.util
import json
import os
from pathlib import Path
import select
import threading
import time
import tty
import types


class SerialBoard:
    def __init__(self):
        path = Path(__file__).resolve().parents[1] / 'firmware/remote.py'
        spec = importlib.util.spec_from_file_location('board_remote', path)
        self.remote = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(self.remote)
        self.remote.time = types.SimpleNamespace(ticks_diff=lambda a, b: a-b)
        self.control = self.remote.ModeController()
        self.lines = self.remote.LineBuffer()
        self.master, self.slave = os.openpty()
        tty.setraw(self.slave)
        self.path = os.ttyname(self.slave)
        os.set_blocking(self.master, False)
        self.inputs = dict(touch=False, left=False, right=False)
        self.stop = threading.Event()
        self.error = None
        self.thread = threading.Thread(target=self.run, daemon=True)
        self.thread.start()

    def run(self):
        centering_at = None
        last_report = 0
        try:
            while not self.stop.wait(0.005):
                now = time.monotonic()
                if select.select([self.master], [], [], 0)[0]:
                    chunk = os.read(self.master, 4096).decode('ascii', errors='replace')
                    for line in self.lines.feed(chunk):
                        self.control.receive(line, int(now*1000))
                if self.control.mode == 'centering' and centering_at is None:
                    centering_at = now
                centered = centering_at is not None and now-centering_at >= 0.1
                mode = self.control.update(int(now*1000), centered)
                if mode != 'centering':
                    centering_at = None
                if now-last_report >= 0.1:
                    data = dict(v=1, mode=mode, **self.inputs)
                    os.write(self.master, ('@'+json.dumps(data)+'\n').encode())
                    last_report = now
        except Exception as error:
            self.error = error

    def close(self):
        self.stop.set()
        self.thread.join(timeout=2)
        os.close(self.master)
        os.close(self.slave)
        if self.error is not None:
            raise self.error
