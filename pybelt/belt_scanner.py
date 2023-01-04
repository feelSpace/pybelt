# Copyright 2020, feelSpace GmbH, <info@feelspace.de>

import asyncio
import logging
import threading
from typing import List
from bleak.backends.device import BLEDevice
from bleak import BleakScanner
from contextlib import contextmanager


@contextmanager
def create():
    scanner = None
    try:
        scanner = BeltScanner()
        yield scanner
    finally:
        if scanner is not None:
            scanner.close()


class BeltScanner:
    """Utility class for scanning belts.
    """

    def __init__(self, event_loop=None):
        """Initializes the belt scanner.
        :param event_loop: Optional AsyncIO event loop.
        """
        self._logger = logging.getLogger(__name__)
        if event_loop is None:
            # Start scanner own event loop
            self._event_loop = asyncio.new_event_loop()
            self._event_loop_thread = _EventLoopThread(self._event_loop)
            self._event_loop_thread.start()
        else:
            self._event_loop = event_loop
            self._event_loop_thread = None

    def __del__(self):
        if self._event_loop_thread is not None:
            # Stop event loop if scanner own it
            self._event_loop.call_soon_threadsafe(self._event_loop.stop)
            self._event_loop_thread.join()
            self._event_loop.close()

    def close(self):
        if self._event_loop_thread is not None:
            # Stop event loop if scanner own it
            try:
                self._event_loop.call_soon_threadsafe(self._event_loop.stop)
                self._event_loop_thread.join()
                self._event_loop.close()
                self._event_loop_thread = None
            except:
                pass

    def scan(self) -> List[BLEDevice]:
        """Scans for advertising belts.

        :return: The available belts.
        """
        future = asyncio.run_coroutine_threadsafe(self._scan(), self._event_loop)
        return future.result()

    async def _scan(self) -> List[BLEDevice]:
        """Scans for advertising belts (asynchronous).
        """
        self._logger.debug("BeltScanner: Start async scan.")
        belts = []
        devices = await BleakScanner.discover()
        for d in devices:
            self._logger.debug("BeltScanner: Device found.")
            # Check for service UUID
            if 'uuids' in d.metadata:
                for uuid in d.metadata['uuids']:
                    self._logger.debug("BeltScanner: Advertised UUID {}.".format(uuid))
                    if isinstance(uuid, str) and ("65333333-a115-11e2-9e9a-0800200ca100" in uuid.lower()
                                                  or "0000fe51-0000-1000-8000-00805f9b34fb" in uuid.lower()):
                        belts.append(d)
        self._logger.debug("BeltScanner: End async scan.")
        return belts


class _EventLoopThread(threading.Thread):
    """Thread for the event loop.
    """

    def __init__(self, event_loop):
        """Initializes the thread for the event loop.
        :param event_loop: The event loop.
        """
        self._logger = logging.getLogger(__name__)
        threading.Thread.__init__(self, name="_EventLoopThread")
        self._event_loop = event_loop

    def run(self) -> None:
        self._logger.debug("BeltScanner: Start scan event loop.")
        self._event_loop.run_forever()
        self._logger.debug("BeltScanner: End scan event loop.")
