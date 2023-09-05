# Copyright 2023, feelSpace GmbH, <info@feelspace.de>

""" This file contains tests for serial communication via USB.
"""
import time
import unittest

import serial
from pybelt.belt_controller import BeltController, BeltConnectionState, BeltOrientationType, BeltVibrationTimerOption, \
    BeltMode

from serial.tools import list_ports


class TestSerialCommunication(unittest.TestCase):

    def setUp(self) -> None:
        self.belt_controller = BeltController()
        # Connect via USB
        ports = serial.tools.list_ports.comports()
        if ports is None or len(ports) == 0:
            raise Exception("No serial port found to connect a belt.")
        self.belt_controller = BeltController()
        for port in ports:
            try:
                print("Try to connect to {}".format(port[0]))
                self.belt_controller.connect(port[0])
            except:
                pass
            if self.belt_controller.get_connection_state() == BeltConnectionState.CONNECTED:
                break
        if self.belt_controller.get_connection_state() != BeltConnectionState.CONNECTED:
            raise Exception("No serial port found to connect a belt.")

    def tearDown(self) -> None:
        # Disconnect belt
        if self.belt_controller is not None and self.belt_controller.get_connection_state() != BeltConnectionState.DISCONNECTED:
            self.belt_controller.disconnect_belt()

    def test_quick_vibration_command(self):
        """ Tests that no packets are lost when a lot of commands are sent in a short time.
        """
        # Send multiple vibration commands and check via intensity command
        # Test 101 times
        for i in range(1, 20):
            # Change mode
            try:
                self.belt_controller.set_belt_mode(BeltMode.APP_MODE, True)
            except:
                self.assertTrue(False, "Mode change failed.")
                return
            for j in range(1, 51):
                    # Send 50 vibration command
                    self.belt_controller.send_pulse_command(
                        1, # Channel index
                        BeltOrientationType.MOTOR_INDEX, # Orientation type
                        i%16, # Motor index
                        j, # Intensity
                        1000, # On duration
                        1000, # Pulse period
                        1, # Pulse iterations
                        1000, # Series period
                        1, # Series iterations
                        BeltVibrationTimerOption.RESET_TIMER, # Timer option
                        False, # Exclusive channel
                        False # Clear other channel
                    )
            try:
                self.belt_controller.set_belt_mode(BeltMode.PAUSE, True)
            except:
                self.assertTrue(False, "Mode change packet lost!")
                return
            self.assertEqual(self.belt_controller.get_belt_mode(), BeltMode.PAUSE, "Mode change failed.")

