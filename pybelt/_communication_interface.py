# Copyright 2020, feelSpace GmbH, <info@feelspace.de>
import asyncio
import queue
import sys
import threading
import time
import logging

import bleak
import serial
from bleak import BleakScanner, BleakClient
from bleak.backends.device import BLEDevice
from pybelt import belt_scanner

from pybelt._gatt_profile import *

SERIAL_BAUDRATE = 115200
# Baudrate for serial connection

SERIAL_READ_TIMEOUT = 0.50
# Timeout to read data on serial port

THREAD_JOIN_TIMEOUT_SEC = 2.0
# Timeout to wait thread termination

SERIAL_PACKET_TIMEOUT = 2.5
# Timeout to read a complete packet on serial port

SERIAL_FLUSH_INPUT_TIMEOUT = 1.50
# Timeout for flushing serial input

EVENT_LOOP_READY_TIMEOUT = 1.0


# Timeout for initializing the event loop in BLE interface


def decode_ascii(byte_msg) -> str:
    """Decodes a byte array to a string.

    :param Union[bytes, bytearray] byte_msg:
        The bytes to decode.

    :rtype str
        The decoded string.
    """
    if len(byte_msg) == 0:
        return ""
    try:
        for i in range(0, len(byte_msg)):
            if byte_msg[i] < 0 or byte_msg[i] > 255:
                byte_msg[i] = 35
        msg = bytes(byte_msg).decode('ascii', 'replace')
        return msg
    except:
        return "### FORMAT ERROR ###"


class ParseMode:
    """Enumeration of parse mode for connection interfaces."""

    GATT = 0
    TEXT = 1


class BeltCommunicationDelegate:
    """
    Delegate interface for communication interfaces.
    """

    def on_connection_established(self):
        """
        Called when the connection has been established.
        """
        pass

    def on_connection_closed(self, expected=True):
        """
        Called when the connection has been closed.

        :param bool expected: 'True' if the disconnection was expected.
        """
        pass

    def on_gatt_char_notified(self, gatt_char, data):
        """
        Called when a GATT notification has been received or a characteristic has been read.

        :param GattCharacteristic gatt_char: The characteristic that received the data.
        :param bytes data: The data received.
        """
        pass

    def on_raw_text_received(self, data):
        """
        Called when raw text has been received.
        This applies only to the serial interface.

        :param bytes data: The data received.
        """
        pass


class BeltCommunicationInterface:
    """
    Interface for the communication.
    """

    def close(self):
        """
        Closes the connection.
        """
        pass

    def wait_disconnection(self, timeout=1) -> bool:
        """
        Waits until the belt disconnect.

        :param float timeout: The timeout time to stop waiting for disconnection.
        :return: 'True' if the belt disconnected, 'False' if the timeout is reached.
        """
        pass

    def is_connected(self) -> bool:
        """
        Returns the connection state.

        :return: 'True' if the belt is connected.
        """
        pass

    def write_gatt_char(self, gatt_char, data) -> bool:
        """
        Writes a GATT attribute.

        :param GattCharacteristic gatt_char:  The characteristic to write.
        :param bytes data: The data to write.
        :return: 'True' if successful, 'False' if not connected or a problem occurs.
        """
        pass

    def set_gatt_notifications(self, gatt_char, enabled) -> bool:
        """
        Enables or disables the notifications for a characteristic.

        :param GattCharacteristic gatt_char: The characteristic for which notifications has to be enabled or disabled.
        :param bool enabled: 'True' to enable the notifications on the characteristic.
        :return: 'True' if successful, 'False' if not connected or a problem occurs.
        """
        pass

    def read_gatt_char(self, gatt_char) -> bool:
        """
        Request the value of a characteristic.

        :param GattCharacteristic gatt_char: The GATT characteristic to read.
        :return: 'True' if successful, 'False' if not connected or a problem occurs.
        """
        pass

    def get_gatt_profile(self) -> NaviBeltGattProfile:
        """
        Returns the GATT profile with characteristics.
        :return: the GATT profile with characteristics.
        """
        pass


class SerialPortInterface(threading.Thread, BeltCommunicationInterface):
    """Serial port interface.
    """

    # --------------------------------------------------------------- #
    # Public methods

    def __init__(self, delegate):
        """Initializes the serial port interface.

        Parameters
        ----------
        :param BeltCommunicationDelegate delegate:
            The delegate that handles packets and messages received.
        """
        threading.Thread.__init__(self, name="SerialPortListener")
        self._serial_port_name = None
        self._serial_port = None
        self._delegate = delegate

        # Logger
        self.logger = logging.getLogger(__name__)

        # Flag for stopping the thread
        self.stop_flag = False
        self._expect_disconnection = False

        # Parse mode
        self._parse_mode = ParseMode.GATT
        self._pending_parse_mode = None

        # Variable for packet timeout
        self._packet_start_time = time.perf_counter()

        # Output lock
        self._output_lock = threading.RLock()

        # Python version
        self._PY3 = sys.version_info > (3,)

        # GATT profile
        self._gatt_profile = get_usb_gatt_profile()

    def open(self, port, parse_mode=ParseMode.GATT, initial_flush=True):
        """
        Opens a serial connection with a belt.
        :param str port: The port name to use.
        :param int parse_mode: The parse mode.
        :param bool initial_flush: 'True' to flush initial input data when connected.
        """
        # Check connection state
        if self._serial_port is not None:
            self.logger.error("SerialPortInterface: Belt already connected!")
            return

        # Set parameters
        self._parse_mode = parse_mode
        self._pending_parse_mode = None

        # Open port
        self._serial_port_name = port
        self.stop_flag = False
        self._serial_port = serial.Serial(
            self._serial_port_name,
            SERIAL_BAUDRATE,
            timeout=SERIAL_READ_TIMEOUT)

        # Initial flush
        self.write_gatt_char(self._gatt_profile.param_request_char, b'\x01\x01')
        if initial_flush:
            self._flush_input()

        # Start listening
        self.start()

        # Dummy command to start binary communication
        self.write_gatt_char(self._gatt_profile.param_request_char, b'\x01\x01')
        time.sleep(0.5)

        # Inform delegate
        if self._delegate is not None:
            try:
                self._delegate.on_connection_established()
            except:
                pass

    def set_parse_mode(self, parse_mode):
        """Sets the parse mode.

        Parameters
        ----------
        :param int parse_mode:
            The parse mode to set.
        """
        if self.is_alive() and not self.stop_flag and self._parse_mode != parse_mode:
            self._pending_parse_mode = parse_mode

    def get_port(self) -> str:
        """
        Returns the port for the connection.
        :return: the port for the connection.
        """
        return self._serial_port_name

    # --------------------------------------------------------------- #
    # Private methods

    def _flush_input(self):
        """Flushes the input. """
        self.logger.info("SerialPortListener: Flush input.")
        try:
            flush_timeout = time.perf_counter() + SERIAL_FLUSH_INPUT_TIMEOUT
            while time.perf_counter() < flush_timeout:
                self._serial_port.reset_input_buffer()
                time.sleep(0.05)
        except:
            self.logger.warning("SerialPortListener: Unable to flush serial input.")

    # --------------------------------------------------------------- #
    # Implementation of communication interface methods

    def close(self):
        # Stop listener
        self.stop_flag = True
        if self.is_alive() and threading.current_thread() != self:
            self.join(THREAD_JOIN_TIMEOUT_SEC)

    def wait_disconnection(self, timeout=1) -> bool:
        if not self.is_connected():
            # Already disconnected
            return True
        if threading.current_thread() == self:
            self.logger.error("BeltController: Cannot wait disconnection from listener thread.")
            return False
        self._expect_disconnection = True
        self.join(timeout)
        self._expect_disconnection = False
        return self.is_connected()

    def is_connected(self) -> bool:
        return self._serial_port is not None

    def write_gatt_char(self, gatt_char, data) -> bool:
        with self._output_lock:
            try:
                packet = bytes([gatt_char.value_attr.handle]) + bytes([len(data)]) + data
                self._serial_port.write(packet)
            except:
                return False
        return True

    def set_gatt_notifications(self, gatt_char, enabled) -> bool:
        with self._output_lock:
            try:
                if enabled:
                    packet = bytes([gatt_char.configuration_attrs[0].handle, 2, 0x01, 0x00])
                else:
                    packet = bytes([gatt_char.configuration_attrs[0].handle, 2, 0x00, 0x00])
                self._serial_port.write(packet)
            except:
                return False
        return True

    def read_gatt_char(self, gatt_char) -> bool:
        with self._output_lock:
            try:
                packet = bytes([gatt_char.value_attr.handle, 0])
                self._serial_port.write(packet)
            except:
                return False
        return True

    def get_gatt_profile(self) -> NaviBeltGattProfile:
        return self._gatt_profile

    # --------------------------------------------------------------- #
    # Implementation of Thread methods

    def run(self):
        self.stop_flag = False
        self._expect_disconnection = False
        self.logger.debug("SerialPortListener: Start listening belt.")
        packet = None
        while not self.stop_flag:
            try:
                # Blocking until data are received or read timeout
                data_serial = self._serial_port.read(size=1)
                # Convert to list of int
                if len(data_serial) > 0:
                    in_byte = bytes([data_serial[0]])
                else:
                    in_byte = None
            except:
                if not self.stop_flag and not self._expect_disconnection:
                    self.logger.exception("SerialPortListener: Error when reading on serial port.")
                break
            # Check for packet timeout
            if packet is not None and len(packet) > 0:
                if ((time.perf_counter() - self._packet_start_time) >
                        SERIAL_PACKET_TIMEOUT):
                    # Timeout, clear packet
                    self.logger.error("SerialPortListener: Packet timeout. (" + decode_ascii(packet) + ")")
                    packet = None
            # Check parse mode
            if self._pending_parse_mode is not None:
                # Change parse mode
                self._parse_mode = self._pending_parse_mode
                self._pending_parse_mode = None
                # Clear packet
                packet = None
            # Handle received byte (fill packet)
            if in_byte is not None:
                if self._parse_mode == ParseMode.GATT:
                    # Fill packet
                    if packet is None or len(packet) == 0:
                        packet = bytearray()
                        # First byte is attribute handle
                        gatt_char = self._gatt_profile.get_char_from_handle(ord(in_byte))
                        if gatt_char is not None:
                            packet.append(in_byte[0])
                            self._packet_start_time = time.perf_counter()
                        else:
                            self.logger.error("SerialPortListener: Incorrect attribute handle in packet header. (" +
                                              decode_ascii(in_byte) + ")")
                            self._flush_input()
                            # ignore byte
                    elif len(packet) == 1:
                        # Second byte is the data length
                        if ord(in_byte) <= 22:
                            packet.append(in_byte[0])
                        else:
                            gatt_char = self._gatt_profile.get_char_from_handle(packet[0])
                            if gatt_char is not None and gatt_char == self._gatt_profile.sensor_notification_char and \
                                    ord(in_byte) <= 244:
                                # Data length extension supported on sensor notifications
                                packet.append(in_byte[0])
                            else:
                                # Incorrect length, clear received data
                                self.logger.error("SerialPortListener: Incorrect packet length in packet header. (" +
                                                  decode_ascii(in_byte) + ")")
                                self._flush_input()
                                packet = None
                    elif len(packet) >= 2:
                        # Complete packet to the data size
                        packet.append(in_byte[0])
                    # Check for complete packet
                    if packet is not None and (len(packet) >= 2) and (len(packet) == packet[1] + 2):
                        # Notify packet received
                        try:
                            gatt_char = self._gatt_profile.get_char_from_handle(packet[0])
                            self._delegate.on_gatt_char_notified(
                                gatt_char,
                                packet[2:])
                        except:
                            self.logger.exception("SerialPortListener: Error when handling received packet.")
                        packet = None
                elif self._parse_mode == ParseMode.TEXT:
                    if (ord(in_byte) == 0x0D or ord(in_byte) == 0x0A or
                            (32 <= ord(in_byte) <= 127)):
                        if packet is None:
                            packet = bytearray()
                        packet.append(in_byte[0])
                    else:
                        # Ignore byte and clear packet
                        self.logger.error("SerialPortListener: Incorrect text byte. (" +
                                          decode_ascii(in_byte) + ")")
                        packet = None
                    # Check for completed packet (new line)
                    if packet is not None and len(packet) > 0 and packet[-1] == 0x0A:
                        # Handle packet
                        try:
                            self._delegate.on_raw_text_received(packet)
                        except:
                            self.logger.exception("Error when handling received text.")
                        packet = None
        self.logger.debug("SerialPortListener: Stop listening belt.")
        # Close port
        if self._serial_port is not None:
            try:
                self._serial_port.close()
            except:
                self.logger.exception("BeltController: Failed to close serial port.")
        self._serial_port = None
        # Inform delegate
        if self._delegate is not None:
            try:
                self._delegate.on_connection_closed(expected=(self.stop_flag or self._expect_disconnection))
            except:
                pass


def print_packet(packet):
    packet_str = ""
    for b in packet:
        packet_str += hex(b) + " "
    print(packet_str)


class BleInterface(BeltCommunicationInterface, threading.Thread):
    """Serial port interface.
    """

    # --------------------------------------------------------------- #
    # Public methods

    def __init__(self, delegate):
        """Initializes the BLE interface.

        :param BeltCommunicationDelegate delegate:
            The delegate that handles received notifications.
        """
        threading.Thread.__init__(self, name="BleInterfaceThread")
        self._device = None
        self._delegate = delegate
        self._gatt_client = None
        self._event_loop = None
        self._event_loop_ready = threading.Event()
        self._event_notifier = None
        self._is_disconnecting = False
        self._expect_disconnection = False
        # Logger
        self.logger = logging.getLogger(__name__)
        # GATT profile
        self._gatt_profile = get_usb_gatt_profile()

    def open(self, device=None):
        """
        Connects to a belt via BLE.

        :param bleak.backends.device.BLEDevice device: The device to connect to, or 'None' to scan for a device.
        """
        if self._gatt_client is not None:
            # Already connected
            self.logger.error("BleInterface: Belt already connected!")
            return
        # Start event notifier
        self._event_notifier = BleEventNotifier(self._delegate, self)
        self._event_notifier.start()
        # Start thread and loop
        self._event_loop_ready.clear()
        self.start()
        self._event_loop_ready.wait(EVENT_LOOP_READY_TIMEOUT)
        # Retrieve device
        self._device = device
        if self._device is None:
            try:
                # Use belt scanner to find the first belt
                belts = []
                with belt_scanner.create() as scanner:
                    belts = scanner.scan()
                if not belts:
                    self._device = belts[0]
            except:
                self.logger.exception("BleInterface: Error when scanning!")
                self.close()
                raise
        if self._device is None:
            raise Exception("No belt found via BLE.")
        try:
            # Connect to device
            future = asyncio.run_coroutine_threadsafe(self._connect(), self._event_loop)
            connected = future.result()
            if not connected:
                self.close()
                raise Exception("BLE connection failed.")
            # Retrieve profile / Service discovery (automatic)
            self._fill_gatt_profile(self._gatt_client.services)
        except:
            # Disconnect and re-raise exception
            self.logger.exception("BleInterface: Error when scheduling connection!")
            self.close()
            raise
        # Inform delegate
        try:
            self._event_notifier.notify_connection()
        except:
            self.logger.exception("BleInterface: Failed to access event notifier for connection notification!")
            pass

    def get_device(self):
        """
        Returns the connected device.

        :return bleak.backends.device.BLEDevice: The connected device.
        """
        return self._device

    # --------------------------------------------------------------- #
    # Private methods

    async def _scan(self) -> BLEDevice:
        """Scans for a belt.
        """
        self.logger.debug("BleInterface: Scan for belt.")
        try:
            devices = await BleakScanner.discover()
            for d in devices:
                # Check for service UUID
                if 'uuids' in d.metadata:
                    for uuid in d.metadata['uuids']:
                        if isinstance(uuid, str) and "65333333-a115-11e2-9e9a-0800200ca100" in uuid.lower():
                            self.logger.debug("BleInterface: Belt found.")
                            self._device = d
                            return d
            self.logger.debug("BleInterface: No belt found!")
        except:
            self.logger.exception("BleInterface: Error when scanning!")

    async def _connect(self) -> bool:
        """
        Connects the belt.
        :return: 'True' if successful, 'False' otherwise.
        """
        try:
            self.logger.debug("BleInterface: Connect client.")
            self._gatt_client = BleakClient(
                self._device.address,
                loop=self._event_loop,
                disconnected_callback=self._on_device_disconnected)
            await self._gatt_client.connect()
        except:
            self.logger.exception("BleInterface: Error when connecting!")
            return False
        self.logger.debug("BleInterface: Client connected.")
        return True

    async def _disconnect(self) -> bool:
        """
        Disconnects the device.
        :return: 'True' if successful, 'False' otherwise.
        """
        success = True
        try:
            if self._gatt_client is not None:
                connected = await self._gatt_client.is_connected()
                if connected:
                    self.logger.debug("BleInterface: Disconnect client.")
                    success = await self._gatt_client.disconnect()
                else:
                    self.logger.debug("BleInterface: Client already disconnected.")
        except:
            self.logger.exception("BleInterface: Error when disconnecting!")
            success = False
        return success

    async def _write_gatt_char(self, gatt_char, data) -> bool:
        """
        Writes a GATT characteristic.
        :param GattCharacteristic gatt_char: The characteristic to write.
        :param bytes data: The data to write.
        :return: 'True' if successful, 'False' otherwise.
        """
        try:
            if self._gatt_client is None:
                self.logger.warning("BleInterface: No connection to write char!")
                return False
            connected = await self._gatt_client.is_connected()
            if not connected:
                self.logger.warning("BleInterface: No connection to set notifications!")
                return False
            await self._gatt_client.write_gatt_char(gatt_char.uuid, bytearray(data), response=True)
        except:
            self.logger.exception("BleInterface: Error when writing characteristic.")
            return False
        return True

    async def _set_gatt_notifications(self, gatt_char, enabled) -> bool:
        """
        Enables or disables the notifications.
        :param GattCharacteristic gatt_char: The GATT characteristic to configure.
        :param enabled: 'True' to enable notifications, 'False' to disable notifications.
        :return: 'True' if successful, 'False' otherwise.
        """
        try:
            if self._gatt_client is None:
                self.logger.warning("BleInterface: No connection to set notifications!")
                return False
            connected = await self._gatt_client.is_connected()
            if not connected:
                self.logger.warning("BleInterface: No connection to set notifications!")
                return False
            if enabled:
                await self._gatt_client.start_notify(gatt_char.uuid, self._on_notification_received)
            else:
                await self._gatt_client.stop_notify(gatt_char.uuid)
        except:
            self.logger.exception("BleInterface: Error when configuring notifications!")
            return False
        return True

    async def _read_gatt_char(self, gatt_char) -> bool:
        """
        Reads a GATT characteristic.
        :param GattCharacteristic gatt_char: The GATT characteristic to read.
        :return: 'True' if successful, 'False' otherwise.
        """
        try:
            if self._gatt_client is None:
                self.logger.warning("BleInterface: No connection to read char!")
                return False
            connected = await self._gatt_client.is_connected()
            if not connected:
                self.logger.warning("BleInterface: No connection to set notifications!")
                return False
            value = await self._gatt_client.read_gatt_char(gatt_char.uuid)
        except:
            self.logger.exception("BleInterface: Error when reading characteristic.")
            return False
        try:
            self._event_notifier.notify_gatt_notification(gatt_char, bytes(value))
        except:
            self.logger.exception("BleInterface: Error when calling delegate method 'on_gatt_char_notified'.")
        return True

    def _fill_gatt_profile(self, services):
        """ Fills the gatt profile with attribute handles.
        :param BleakGATTServiceCollection services: The list of services.
        """
        for gatt_char in self._gatt_profile.characteristics:
            bleak_gatt_char = services.get_characteristic(gatt_char.uuid)
            if bleak_gatt_char is None:
                self.logger.error("BleInterface: Characteristic not listed for UUID {}".format(gatt_char.uuid))
            # else: TODO Adds handles
        # TODO
        is_new_profile = True
        try:
            adv_uuids = self._device.metadata['uuids']
            for uuid in adv_uuids:
                if "65333333-a115-11e2-9e9a-0800200ca100" in uuid.lower() or \
                        "65333333-a115-11e2-9e9a-0800200ca200" in uuid.lower():
                    is_new_profile = False
                    break
        except:
            pass
        if is_new_profile:
            self._gatt_profile.set_char_handles("0000fe01-0000-1000-8000-00805f9b34fb", 8, 9)
            self._gatt_profile.set_char_handles("0000fe02-0000-1000-8000-00805f9b34fb", 10, 11, [12])
            self._gatt_profile.set_char_handles("0000fe03-0000-1000-8000-00805f9b34fb", 13, 14)
            self._gatt_profile.set_char_handles("0000fe04-0000-1000-8000-00805f9b34fb", 15, 16, [17])
            self._gatt_profile.set_char_handles("0000fe05-0000-1000-8000-00805f9b34fb", 18, 19)
            self._gatt_profile.set_char_handles("0000fe06-0000-1000-8000-00805f9b34fb", 20, 21, [22])
            self._gatt_profile.set_char_handles("0000fe09-0000-1000-8000-00805f9b34fb", 28, 29, [30])
            self._gatt_profile.set_char_handles("0000fe0a-0000-1000-8000-00805f9b34fb", 32, 33)
            self._gatt_profile.set_char_handles("0000fe0b-0000-1000-8000-00805f9b34fb", 34, 35, [36])
            self._gatt_profile.set_char_handles("0000fe0c-0000-1000-8000-00805f9b34fb", 37, 38, [39])
            self._gatt_profile.set_char_handles("0000fe13-0000-1000-8000-00805f9b34fb", 41, 42)
            self._gatt_profile.set_char_handles("0000fe14-0000-1000-8000-00805f9b34fb", 43, 44, [45])
        else:
            self._gatt_profile = get_usb_gatt_profile()
        self.logger.debug("BLE interface, TBC: UUIDs should be used instead of characteristic handles!")

    # --------------------------------------------------------------- #
    # Bleak GATT client callback methods

    def _on_notification_received(self, attr_handle, data):
        """
        Callback for notifications.
        :param int attr_handle: The attribute handle.
        :param bytearray data: The characteristic notified value.
        """
        gatt_char = self._gatt_profile.get_char_from_handle(attr_handle)
        if gatt_char is None:
            self.logger.debug("BleInterface: Notification on unsupported handle!")
            return
        try:
            self._event_notifier.notify_gatt_notification(gatt_char, bytes(data))
        except:
            self.logger.exception("BleInterface: Failed to access event notifier!")

    def _on_device_disconnected(self, gatt_client):
        """
        Callback on disconnection.
        :param gatt_client: The GATT client disconnected.
        """
        self.logger.debug("BleInterface: Client {} disconnected.".format(gatt_client.address))
        if self._gatt_client is None:
            # Connection already closed
            return
        if self._is_disconnecting:
            # Ignore callback when properly disconnecting from 'close()' call
            return

        # TODO TBT
        # try:
        #     # Disconnect
        #     self._gatt_client.disconnect()
        #     # TODO
        #     #future = asyncio.run_coroutine_threadsafe(self._disconnect(), self._event_loop)
        #     #success = future.result()
        #     if not success:
        #         self.logger.error("BleInterface: Failed to disconnect!")
        # except:
        #     self.logger.exception("BleInterface: Error when scheduling disconnection!")

        # Disconnected
        self._gatt_client = None
        # Stop event loop
        try:
            self.logger.debug("BleInterface: Stop event loop.")
            self._event_loop.call_soon_threadsafe(self._event_loop.stop)
        except:
            self.logger.exception("BleInterface: Error when stopping event loop!")
        self._event_loop = None
        # Notify disconnection and stop event notifier
        if self._event_notifier is not None:
            self._event_notifier.notify_disconnection(expected=self._expect_disconnection)

    # --------------------------------------------------------------- #
    # Implementation of communication interface methods

    def close(self):
        if self._gatt_client is None:
            # Already closed
            return
        self.logger.debug("BleInterface: Disconnect and stop event loop.")
        # Flag to ignore '_on_device_disconnected' callback
        self._is_disconnecting = True
        try:
            # Disconnect
            future = asyncio.run_coroutine_threadsafe(self._disconnect(), self._event_loop)
            success = future.result()
            if not success:
                self.logger.error("BleInterface: Failed to disconnect!")
        except:
            self.logger.exception("BleInterface: Error when scheduling disconnection!")
        self._is_disconnecting = False
        self._gatt_client = None
        # Stop event loop
        try:
            self.logger.debug("BleInterface: Stop event loop.")
            self._event_loop.call_soon_threadsafe(self._event_loop.stop)
        except:
            self.logger.exception("BleInterface: Error when stopping event loop!")
        self._event_loop = None
        # Notify disconnection and stop event notifier
        if self._event_notifier is not None:
            self._event_notifier.notify_disconnection()

    def wait_disconnection(self, timeout=1) -> bool:
        if not self.is_connected():
            # Already disconnected
            return True
        if threading.current_thread() == self:
            self.logger.error("BeltController: Cannot wait disconnection from listener thread.")
            return False
        self._expect_disconnection = True
        self._event_notifier.join(timeout)
        self._expect_disconnection = False
        return self.is_connected()

    def is_connected(self) -> bool:
        return self._gatt_client is not None

    def write_gatt_char(self, gatt_char, data) -> bool:
        if self._gatt_client is None:
            self.logger.error("BleInterface: No connection to write char!")
            return False
        try:
            future = asyncio.run_coroutine_threadsafe(self._write_gatt_char(gatt_char, data), self._event_loop)
            success = future.result()
            if not success:
                self.logger.error("BleInterface: Failed to write char!")
                return False
        except:
            self.logger.exception("BleInterface: Error when scheduling write char operation!")
            return False
        return True

    def set_gatt_notifications(self, gatt_char, enabled) -> bool:
        if self._gatt_client is None:
            self.logger.error("BleInterface: No connection to set notifications!")
            return False
        try:
            future = asyncio.run_coroutine_threadsafe(
                self._set_gatt_notifications(gatt_char, enabled), self._event_loop)
            success = future.result()
            if not success:
                self.logger.error("BleInterface: Failed to set notification!")
                return False
        except:
            self.logger.exception("BleInterface: Error when scheduling notification configuration!")
            return False
        return True

    def read_gatt_char(self, gatt_char) -> bool:
        if self._gatt_client is None:
            self.logger.error("BleInterface: No connection to read characteristic!")
            return False
        try:
            future = asyncio.run_coroutine_threadsafe(
                self._read_gatt_char(gatt_char), self._event_loop)
            success = future.result()
            if not success:
                self.logger.error("BleInterface: Failed to read characteristic!")
                return False
        except:
            self.logger.exception("BleInterface: Error when scheduling read char operation!")
            return False
        return True

    def get_gatt_profile(self) -> NaviBeltGattProfile:
        return self._gatt_profile

    # --------------------------------------------------------------- #
    # Implementation of Thread methods

    def run(self):
        try:
            # Create loop
            self._event_loop = asyncio.new_event_loop()
            asyncio.set_event_loop(self._event_loop)
            # Start loop
            self.logger.debug("BleInterface: Event loop started.")
            self._event_loop_ready.set()
            self._event_loop.run_forever()
        except:
            self.logger.exception("BleInterface: Error in event loop.")
            self.close()


class BleEventNotifier(threading.Thread):
    """
    A thread to notify the BLE delegate of events.
    This is necessary to isolate the BLE client that runs in an event loop.
    """

    EVENT_CONNECTION = "EVENT_CONNECTION"
    EVENT_DISCONNECTION = "EVENT_DISCONNECTION"
    EVENT_GATT_NOTIFICATION = "EVENT_GATT_NOTIFICATION"

    def __init__(self, delegate, ble_interface):
        """
        Constructor with a delegate for notifications.
        :param BeltCommunicationDelegate delegate: The delegate that handles notifications.
        :param BleInterface ble_interface: The BLE interface.
        """
        threading.Thread.__init__(self, name="BleDelegateNotifier")
        # Delegate and BLE interface
        self._delegate = delegate
        self._ble_interface = ble_interface
        # Notification queue
        self._notification_queue = queue.Queue()
        # Logger
        self.logger = logging.getLogger(__name__)

    def run(self):
        self.logger.debug("BleDelegateNotifier: Delegate notifier started.")
        while True:
            # Wait for next event
            event = self._notification_queue.get()
            if isinstance(event, tuple) and len(event) > 0:

                if event[0] == self.EVENT_CONNECTION:
                    try:
                        self._delegate.on_connection_established()
                    except:
                        self.logger.exception("BleDelegateNotifier: Unable to notify connection!")

                elif event[0] == self.EVENT_DISCONNECTION:
                    # Clear notifier reference in controller
                    try:
                        self._ble_interface._event_notifier = None
                    except:
                        self.logger.exception("BeltEventNotifier: Unable to clear event notifier reference!")
                    # Notify disconnection
                    try:
                        self._delegate.on_connection_closed(expected=event[1])
                    except:
                        self.logger.exception("BleDelegateNotifier: Unable to notify disconnection!")
                    # Stop thread
                    break

                elif event[0] == self.EVENT_GATT_NOTIFICATION:
                    try:
                        self._delegate.on_gatt_char_notified(event[1], event[2])
                    except:
                        self.logger.exception("BleDelegateNotifier: Unable to notify GATT char notification!")

                else:
                    self.logger.warning("BleDelegateNotifier: Unknown event!")
            else:
                self.logger.warning("BleDelegateNotifier: Unknown event!")

        self.logger.debug("BeltEventNotifier: Event notifier stopped.")

    def notify_gatt_notification(self, gatt_char, data):
        """
        Notifies asynchronously the delegate of a GATT notification.
        :param gatt_char: The GATT characteristic on which the notification has been received.
        :param data: The data received.
        """
        if self.is_alive():
            self._notification_queue.put((self.EVENT_GATT_NOTIFICATION, gatt_char, data))
        else:
            self.logger.warning("BeltEventNotifier: No GATT notification as the notifier thread is stopped!")

    def notify_connection(self):
        """
        Notifies asynchronously the delegate that a connection has been established.
        """
        if self.is_alive():
            self._notification_queue.put((self.EVENT_CONNECTION,))
        else:
            self.logger.warning("BeltEventNotifier: No connection notification as the notifier thread is stopped!")

    def notify_disconnection(self, expected=True, join=True):
        """
        Notifies asynchronously the delegate that the device has been disconnected, and stop the event notification
        thread.
        :param expected: True to notify that the disconnection is expected, False if it is an unexpected disconnection.
        :param join: True to wait the end of the event notification thread.
        """
        if self.is_alive():
            self._notification_queue.put((self.EVENT_DISCONNECTION, expected))
            if join:
                try:
                    self.join(THREAD_JOIN_TIMEOUT_SEC)
                except:
                    pass
        else:
            self.logger.warning("BeltEventNotifier: No disconnection notification as the notifier thread is stopped!")
