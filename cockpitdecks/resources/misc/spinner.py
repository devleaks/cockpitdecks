"""
https://stackoverflow.com/questions/4995733/how-to-create-a-spinning-command-line-cursor
usage:

with Spinner():
  # ... some long-running operations

"""
import sys
import time
import threading

class Spinner:

    @staticmethod
    def spinning_cursor():
        while True:
            for cursor in '|/-\\': yield cursor

    def __init__(self, delay=None):
        self.thread = None
        self.exit = None
        self.delay = 0.1
        self.spinner_generator = Spinner.spinning_cursor()
        if delay and float(delay): self.delay = delay

    def spinner_task(self):
        while not self.exit.is_set():
            sys.stdout.write(next(self.spinner_generator))
            sys.stdout.flush()
            self.exit.wait(self.delay)
            sys.stdout.write('\b')
            sys.stdout.flush()

    def __enter__(self):
        self.exit = threading.Event()
        self.thread = threading.Thread(target=self.spinner_task)
        self.thread.start()

    def __exit__(self, exception, value, tb):
        self.exit.set()
        self.thread.join(timeout=self.delay)
        # if self.thread.is_alive():
        #     print(f"anim_stop: ..thread may hang..")
        self.exit = None
        if exception is not None:
            return False
