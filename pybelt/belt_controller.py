# Copyright 2020, feelSpace GmbH, <info@feelspace.de>
from pybelt.belt_scanner import BeltScanner
from pybelt._communication_interface import *
from pybelt._gatt_profile import *
from typing import List

WAIT_ACK_TIMEOUT_SEC = 1  # Default timeout for waiting acknowledgment
DEBUG_MESSAGE_COMPLETION_TIMEOUT = 0.5  # Timeout for waiting the completion of a debug message


class BeltController(BeltCommunicationDelegate):
    """Belt connection and control interface.

    The belt controller supports USB and BLE connection.
    """

    # --------------------------------------------------------------- #
    # Public methods

    def __init__(self, delegate=None):
        """Initializes the belt controller.

        Parameters
        ----------
        :param BeltControllerDelegate delegate:
            The delegate that handles belt events.
        """
        # Logger
        self.logger = logging.getLogger(__name__)

        # Delegates
        self._delegate = delegate
        self._system_handlers = []

        # Connection state
        self._connection_state = BeltConnectionState.DISCONNECTED

        # Connection
        self._communication_interface = None
        self._last_connected_interface = None

        # Packet ack
        self._ack_char = None
        self._ack_data = None
        self._ack_event = threading.Event()

        # Cache of belt parameters
        self._belt_mode = None
        self._default_intensity = None
        self._firmware_version = None
        self._battery_status = None
        self._belt_orientation = None
        self._heading_offset = None
        self._compass_accuracy_signal_enabled = None

        # Buffer for debug message
        self._debug_message_buffer = ""
        self._debug_message_last_received = 0

    def connect(self, belt):
        """ Connects a belt via Bluetooth LE or USB.

        :param Union[str, bleak.backends.device.BLEDevice] belt: The interface to use for communicating with the belt.
            For a Bluetooth LE connection a `BLEDevice` must be passed. For USB connection, the name of the serial port
            must passed, e.g. 'COM1' on Windows or '/dev/ttyUSB0' on Linux.
        :raises ValueError: When the type of interface is unsupported.
        """
        # Check belt interface
        if not isinstance(belt, (str, BLEDevice)):
            raise ValueError("Unsupported type for the belt interface.")
        # Close previous connection
        self._close_connection()
        # Set state as CONNECTING
        self._set_connection_state(BeltConnectionState.CONNECTING)
        # Open connection
        try:
            if isinstance(belt, str):
                # USB connection
                self._communication_interface = SerialPortInterface(self)
                self._communication_interface.open(belt)
            else:
                # Bluetooth connection
                self._communication_interface = BleInterface(self)
                self._communication_interface.open(belt)
        except:
            self._close_connection()
            self._set_connection_state(
                BeltConnectionState.DISCONNECTED,
                BeltConnectionError("Connection failed."))
            return
        # Handshake
        if not self._handshake():
            # Handshake failed
            self._close_connection()
            self._set_connection_state(
                BeltConnectionState.DISCONNECTED,
                BeltConnectionError("Handshake failed."))
            return
        # Keep last connected interface
        self._last_connected_interface = belt
        # Set state and inform delegate
        self._set_connection_state(BeltConnectionState.CONNECTED)

# TODO TBR
    # def connect_serial(self, port):
    #     """
    #     Connects a belt via serial port.
    #
    #     :param str port: The serial port to be used, e.g. 'COM1' on Windows or '/dev/ttyUSB0' on Linux.
    #     """
    #     # Close previous connection
    #     self._close_connection()
    #     # Set state as CONNECTING
    #     self._connection_state = BeltConnectionState.CONNECTING
    #     try:
    #         self._delegate.on_connection_state_changed(self._connection_state)
    #     except:
    #         pass
    #     # Open connection
    #     self._communication_interface = SerialPortInterface(self)
    #     try:
    #         self._communication_interface.open(port)
    #     except:
    #         self._close_connection()
    #         self._connection_state = BeltConnectionState.DISCONNECTED
    #         try:
    #             self._delegate.on_connection_state_changed(BeltConnectionState.DISCONNECTED,
    #                                                        BeltConnectionError("Connection failed."))
    #         except:
    #             pass
    #         return
    #
    #     # Handshake
    #     if not self._handshake():
    #         # Handshake failed
    #         self._close_connection()
    #         self._connection_state = BeltConnectionState.DISCONNECTED
    #         try:
    #             self._delegate.on_connection_state_changed(BeltConnectionState.DISCONNECTED,
    #                                                        BeltConnectionError("Handshake failed."))
    #         except:
    #             pass
    #         return
    #
    #     # Set state and inform delegate
    #     self._connection_state = BeltConnectionState.CONNECTED
    #     try:
    #         self._delegate.on_connection_state_changed(self._connection_state)
    #     except:
    #         pass
    #
    # def connect_ble(self, device=None):
    #     """Connects a belt via BLE.
    #
    #     :param bleak.backends.device.BLEDevice device:
    #         The device to connect to, or 'None' to scan for belt.
    #     """
    #     # Close previous connection
    #     self._close_connection()
    #     # Set state as CONNECTING
    #     self._connection_state = BeltConnectionState.CONNECTING
    #     try:
    #         self._delegate.on_connection_state_changed(self._connection_state)
    #     except:
    #         pass
    #     # Open connection
    #     self._communication_interface = BleInterface(self)
    #     try:
    #         self._communication_interface.open(device=device)
    #     except:
    #         self._close_connection()
    #         self._connection_state = BeltConnectionState.DISCONNECTED
    #         try:
    #             self._delegate.on_connection_state_changed(BeltConnectionState.DISCONNECTED,
    #                                                        BeltConnectionError("Connection failed."))
    #         except:
    #             pass
    #         return
    #     # Handshake
    #     if not self._handshake():
    #         # Handshake failed
    #         self._close_connection()
    #         self._connection_state = BeltConnectionState.DISCONNECTED
    #         try:
    #             self._delegate.on_connection_state_changed(BeltConnectionState.DISCONNECTED,
    #                                                        BeltConnectionError("Handshake failed."))
    #         except:
    #             pass
    #         return
    #     # Set state and inform delegate
    #     self._connection_state = BeltConnectionState.CONNECTED
    #     try:
    #         self._delegate.on_connection_state_changed(self._connection_state)
    #     except:
    #         pass

    def reconnect(self):
        """
        Reconnects the last device.
        """
        if self._connection_state != BeltConnectionState.DISCONNECTED:
            self.logger.error("BeltController: Cannot reconnect when not disconnected!")
            return
        if self._last_connected_interface is None:
            self.logger.error("BeltController: No previous connection to reconnect!")
            return
        try:
            if isinstance(self._last_connected_interface, SerialPortInterface):
                self.connect_serial(self._last_connected_interface.get_port())
            elif isinstance(self._last_connected_interface, BleInterface):
                self.connect_ble(self._last_connected_interface.get_device())
            else:
                self.logger.error("BeltController: Unknown interface for the reconnection.")
        except:
            self.logger.exception("BeltController: Error when reconnecting.")

    def disconnect_belt(self):
        """Disconnects the belt.
        """
        if (self._connection_state == BeltConnectionState.DISCONNECTING or
                self._connection_state == BeltConnectionState.DISCONNECTED):
            return
        self._set_connection_state(BeltConnectionState.DISCONNECTING)
        self._close_connection()

    def get_connection_state(self) -> int:
        """Returns the connection state.
        :return: The connection state.
        """
        return self._connection_state

    def get_belt_mode(self) -> int:
        """Returns the belt mode.
        :return: The belt mode, or None if not connected.
        """
        return self._belt_mode

    def get_firmware_version(self) -> int:
        """Returns the firmware version of the connected belt.
        :return: The firmware version of the connected belt, or None if no belt is connected.
        """
        return self._firmware_version

    def get_default_intensity(self) -> int:
        """Returns the default vibration intensity of the connected belt.
        :return: The default vibration intensity of the connected belt, or None if no belt is connected.
        """
        return self._default_intensity

    def write_gatt(self, gatt_char, data, ack_char=None, ack_data=None, timeout_sec=WAIT_ACK_TIMEOUT_SEC) -> int:
        """
        Sends data to a GATT characteristic.

        :param GattCharacteristic gatt_char: The characteristic to write.
        :param bytes data: The data to write.
        :param GattCharacteristic ack_char: The characteristic for which an acknowledgment should be waited.
        :param bytes ack_data: The acknowledgment pattern.
        :param float timeout_sec: The timeout period in seconds.
        :return: Returns '0' if successful, '1' when no connection is available or a problem occurs, '2' when the
        timeout is reached.
        """
        if (self._connection_state == BeltConnectionState.DISCONNECTED or
                self._connection_state == BeltConnectionState.DISCONNECTING):
            self.logger.error("BeltController: No connection to send packet.")
            return 1
        # Set ACK
        if ack_char is not None or ack_data is not None:
            self._ack_char = ack_char
            self._ack_data = ack_data
            self._ack_event.clear()
        # Send packet
        try:
            self.logger.log(5, "BeltController: "+gatt_char.uuid[4:8]+" -> "+bytes_to_hexstr(data))
        except:
            pass
        try:
            if not self._communication_interface.write_gatt_char(gatt_char, data):
                self.logger.error("BeltController: Error when sending packet.")
                self._ack_char = None
                self._ack_data = None
                self._ack_event.clear()
                return 1
        except:
            self.logger.exception("BeltController: Error when sending packet.")
            self._ack_char = None
            self._ack_data = None
            self._ack_event.clear()
            return 1
        # Wait ack
        if ack_char is not None or ack_data is not None:
            if not self._ack_event.is_set():
                # Wait for ACK
                self._ack_event.wait(timeout_sec)
            if not self._ack_event.is_set():
                # Ack not received
                self.logger.error("BeltController: ACK not received.")
                self._ack_char = None
                self._ack_data = None
                self._ack_event.clear()
                return 2
            # Clear ACK flag
            self._ack_char = None
            self._ack_data = None
            self._ack_event.clear()
        return 0

    def read_gatt(self, gatt_char, timeout_sec=WAIT_ACK_TIMEOUT_SEC) -> int:
        """
        Request the value of a GATT characteristic.

        :param GattCharacteristic gatt_char: The characteristic to read.
        :param float timeout_sec: The timeout period in seconds.
        :return: Returns '0' if successful, '1' when no connection is available or a problem occurs, '2' when the
        timeout is reached.
        """
        if (self._connection_state == BeltConnectionState.DISCONNECTED or
                self._connection_state == BeltConnectionState.DISCONNECTING):
            self.logger.error("BeltController: No connection to send packet.")
            return 1
        # Set ACK
        self._ack_char = gatt_char
        self._ack_data = None
        self._ack_event.clear()
        # Request value
        try:
            if not self._communication_interface.read_gatt_char(gatt_char):
                self.logger.error("BeltController: Error when requesting characteristic value.")
                self._ack_char = None
                self._ack_data = None
                self._ack_event.clear()
                return 1
        except:
            self.logger.exception("BeltController: Error when requesting characteristic value.")
            self._ack_char = None
            self._ack_data = None
            self._ack_event.clear()
            return 1
        # Wait ack
        if not self._ack_event.is_set():
            # Wait for ACK
            self._ack_event.wait(timeout_sec)
        if not self._ack_event.is_set():
            # Ack not received
            self.logger.error("BeltController: ACK not received.")
            self._ack_char = None
            self._ack_data = None
            self._ack_event.clear()
            return 2
        # Clear ACK flag
        self._ack_char = None
        self._ack_data = None
        self._ack_event.clear()
        return 0

    def add_system_handler(self, handler):
        """
        Adds a system handler.
        :param BeltSystemHandler handler: The system handler to add.
        """
        self._system_handlers.append(handler)

    def remove_system_handler(self, handler):
        """
        Removes a system handler.
        :param BeltSystemHandler handler: The handler to remove
        """
        self._system_handlers.remove(handler)

    def start_self_test(self, test_mask=0b00000001) -> bool:
        """
        Starts the self-test procedure of the belt.
        :param int test_mask: The test mask. 1: BNO, 2: LSM, 4: Flash, 8: GPS, 16: Barometer.
        :return bool: 'True' if the self-test has been started.
        """
        if self._connection_state != BeltConnectionState.CONNECTED:
            self.logger.error("BeltController: No connection to start self-test.")
            return False
        if test_mask < 0 or test_mask > 0xff:
            self.logger.error("BeltController: Illegal mask value for self-test.")
            return False
        if (self.write_gatt(navibelt_debug_input_char,
                            bytes([0x02, test_mask]),
                            navibelt_debug_output_char,
                            bytes([0x02, 0x01, test_mask])) != 0):
            self.logger.error("BeltController: Failed to start self-test.")

    def set_orientation_notifications(self, enabled) -> bool:
        """
        Sets the state of orientation notifications.

        :param enabled: 'True' to enable orientation notifications, 'False' to disable.
        :return: 'True' if the request has been sent successfully.
        """
        if self._connection_state == BeltConnectionState.DISCONNECTED:
            return False
        return self._communication_interface.set_gatt_notifications(navibelt_orientation_data_char, enabled)

    def set_power_status_notifications(self, enabled) -> bool:
        """
        Sets the state of power status notifications.

        :param enabled: 'True' to enable power status notifications, 'False' to disable.
        :return: 'True' if the request has been sent successfully.
        """
        if self._connection_state == BeltConnectionState.DISCONNECTED:
            return False
        return self._communication_interface.set_gatt_notifications(navibelt_battery_status_char, enabled)

    def set_debug_notifications(self, enabled) -> bool:
        """
        Sets the state of debug notifications.

        :param enabled: 'True' to enable debug notifications, 'False' to disable.
        :return: 'True' if the request has been sent successfully.
        """
        if self._connection_state == BeltConnectionState.DISCONNECTED:
            return False
        return self._communication_interface.set_gatt_notifications(navibelt_debug_output_char, enabled)

    def factory_reset(self, parameters=True, ble=False, sensor=False) -> bool:
        """
        Resets the belt to its factory defaults. The belt will disconnected and an attempt to reconnect will be made.

        :param parameters: 'True' to reset the parameters.
        :param ble: 'True' to reset BLE parameters.
        :param sensor: 'True' to reset the orientations sensor.
        :return: 'True' if the request has been sent successfully.
        """
        if self._connection_state != BeltConnectionState.CONNECTED:
            return False
        if self.write_gatt(
            navibelt_param_request_char,
            bytes([
                0x12,
                (0x01 if parameters else 0x00),
                (0x01 if ble else 0x00),
                (0x01 if sensor else 0x00)])) != 0:
            return False
        self.logger.debug("BeltController: Reset command sent.")
        if isinstance(self._communication_interface, SerialPortInterface):
            self._communication_interface.wait_disconnection(1)
        else:
            self._communication_interface.close()
        time.sleep(1)
        self.logger.debug("BeltController: Reconnection attempt.")
        self.reconnect()
        return True

    def rename(self, suffix) -> bool:
        """
        Renames the belt with a suffix.
        :param str suffix: The suffix of the belt to set.
        :return: 'True' if the request has been sent successfully.
        """
        if self._connection_state != BeltConnectionState.CONNECTED:
            return False
        encoded_suffix = None
        try:
            encoded_suffix = suffix.encode()
        except:
            self.logger.exception("BeltController: Unable to encode the belt suffix.")
            return False
        if len(encoded_suffix) > 18:
            # Do not fit the 20 bytes max packet size
            self.logger.error("BeltController: Suffix is too long.")
            return False
        # Sent rename request
        if self.write_gatt(
                navibelt_param_request_char,
                bytes([0x01, 0x84])+encoded_suffix) != 0:
            return False
        self.logger.debug("BeltController: Rename request sent.")
        if isinstance(self._communication_interface, BleInterface):
            self._communication_interface.close()

    # --------------------------------------------------------------- #
    # Private methods

    def _set_connection_state(self, state, error=None, notify=True):
        """Sets the connection state.
        :param int state: The state to be set.
        :param Exception error: The error to notify if any.
        :param bool notify: `True` to notify the delegate.
        """
        if self._connection_state == state:
            return
        self._connection_state = state
        if notify:
            try:
                self._delegate.on_connection_state_changed(state, error=error)
            except:
                pass

    def _close_connection(self):
        """Closes the connection and clear cached parameter values.
        The connection state is not changed and delegate is not informed.
        """
        if self._communication_interface is not None:
            self._communication_interface.close()
        self._belt_mode = None
        self._default_intensity = None
        self._firmware_version = None
        self._battery_status = None
        self._belt_orientation = None
        self._heading_offset = None
        self._compass_accuracy_signal_enabled = None

    def _handshake(self):
        """Handshake procedure.

        :return: 'True' if the handshake is successful, 'False' otherwise.
        """
        self.logger.info("BeltController: Start handshake.")
        # Register to keep-alive
        self.logger.debug("BeltController: Register to keep-alive notifications.")
        if not self._communication_interface.set_gatt_notifications(navibelt_keep_alive_char, True):
            return False

        # Register to parameter notifications
        self.logger.debug("BeltController: Register to parameter notifications.")
        if not self._communication_interface.set_gatt_notifications(navibelt_param_notification_char, True):
            return False

        # Read belt mode
        self.logger.debug("BeltController: Read belt mode.")
        if (self.write_gatt(navibelt_param_request_char,
                            b'\x01\x01',
                            navibelt_param_notification_char,
                            b'\x01\x01') != 0):
            self.logger.error("BeltController: Failed to request belt mode.")
            return False
        if self._belt_mode is None:
            self.logger.error("BeltController: Failed to read belt mode.")
            return False

        # Read default intensity
        self.logger.debug("BeltController: Read default intensity.")
        if (self.write_gatt(navibelt_param_request_char,
                            b'\x01\x02',
                            navibelt_param_notification_char,
                            b'\x01\x02') != 0):
            self.logger.error("BeltController: Failed to request default intensity.")
            return False
        if self._default_intensity is None:
            self.logger.error("BeltController: Failed to read default intensity.")
            return False

        # Read firmware version
        self.logger.debug("BeltController: Read firmware version.")
        if self.read_gatt(navibelt_firmware_info_char) != 0:
            self.logger.error("BeltController: Failed to request firmware version.")
            return False
        if self._firmware_version is None:
            self.logger.error("BeltController: Failed to read firmware version.")
            return False

        # Read heading offset
        self.logger.debug("BeltController: Read heading offset.")
        if (self.write_gatt(navibelt_param_request_char,
                            b'\x01\x03',
                            navibelt_param_notification_char,
                            b'\x01\x03') != 0):
            self.logger.error("BeltController: Failed to request default intensity.")
            return False
        if self._heading_offset is None:
            self.logger.error("BeltController: Failed to read default intensity.")
            return False

        # Read compass accuracy signal state
        self.logger.debug("BeltController: Read compass accuracy signal state.")
        if (self.write_gatt(navibelt_param_request_char,
                            b'\x10\x01\x03',
                            navibelt_param_notification_char,
                            b'\x10\x03') != 0):
            self.logger.error("BeltController: Failed to request compass accuracy signal state.")
            return False
        if self._compass_accuracy_signal_enabled is None:
            self.logger.error("BeltController: Failed to read compass accuracy signal state.")
            return False

        # Register to button press
        self.logger.debug("BeltController: Register to button press events.")
        if not self._communication_interface.set_gatt_notifications(navibelt_button_press_char, True):
            self.logger.error("BeltController: Failed to register to button press events.")
            return False

        # Register to orientation notifications
        self.logger.debug("BeltController: Register to orientation notifications.")
        if not self._communication_interface.set_gatt_notifications(navibelt_orientation_data_char, True):
            self.logger.error("BeltController: Failed to register to orientation notifications.")
            return False

        # Register to power status notifications
        self.logger.debug("BeltController: Register to power-status notifications.")
        if not self._communication_interface.set_gatt_notifications(navibelt_battery_status_char, True):
            self.logger.error("BeltController: Failed to register to power-status notifications.")
            return False

        # Register to debug output
        self.logger.debug("BeltController: Register to debug output.")
        if not self._communication_interface.set_gatt_notifications(navibelt_debug_output_char, True):
            self.logger.error("BeltController: Failed to register to debug output.")
            return False

        self.logger.info("BeltController: Handshake completed.")
        return True

    def _set_belt_mode(self, belt_mode):
        """Sets the belt mode and informs the delegate.

        :param int belt_mode:
            The belt mode to set.
        """
        if (self._connection_state == BeltConnectionState.DISCONNECTED or
                self._connection_state == BeltConnectionState.DISCONNECTING):
            return
        if belt_mode < 0 or belt_mode > 6:
            self.logger.error("BeltController: Illegal belt mode.")
            return
        if belt_mode == self._belt_mode:
            return
        self._belt_mode = belt_mode
        if self._connection_state == BeltConnectionState.CONNECTING:
            # No delegate notification during handshake
            return
        try:
            self._delegate.on_belt_mode_changed(belt_mode)
        except:
            pass

    def _notify_button_pressed(self, button_id, previous_mode, new_mode):
        """
        Notifies the delegate of a button press event and sets the belt mode.

        :param int button_id:
            The button ID.
        :param int previous_mode:
            The belt mode before the press event.
        :param int new_mode:
            The belt mode after the press event.
        """
        if (self._connection_state == BeltConnectionState.DISCONNECTED or
                self._connection_state == BeltConnectionState.DISCONNECTING):
            return
        if previous_mode < 0 or previous_mode > 6 or new_mode < 0 or new_mode > 6 or button_id < 1 or button_id > 4:
            self.logger.error("BeltController: Illegal button press event argument.")
            return
        self._belt_mode = new_mode
        try:
            self._delegate.on_belt_button_pressed(button_id, previous_mode, new_mode)
        except:
            pass

    def _notify_belt_mode(self, belt_mode):
        """
        Sets the belt mode member variable and notifies the delegate of a belt mode change.

        :param int belt_mode: The belt mode.
        """
        if (self._connection_state == BeltConnectionState.DISCONNECTED or
                self._connection_state == BeltConnectionState.DISCONNECTING):
            return
        if belt_mode < 0 or belt_mode > 6:
            self.logger.error("BeltController: Illegal mode notification argument.")
            return
        self._belt_mode = belt_mode
        try:
            self._delegate.on_belt_mode_changed(belt_mode)
        except:
            pass

    def _notify_default_intensity(self, intensity):
        """
        Sets the default intensity member variable and notifies the delegate.

        :param intensity: The default intensity to set.
        """
        if (self._connection_state == BeltConnectionState.DISCONNECTED or
                self._connection_state == BeltConnectionState.DISCONNECTING):
            return
        if intensity < 0 or intensity > 100:
            self.logger.error("BeltController: Illegal intensity notification argument.")
            return
        self._default_intensity = intensity
        try:
            self._delegate.on_default_intensity_changed(intensity)
        except:
            pass

    def _notify_heading_offset(self, offset):
        """
        Sets the heading offset member variable and notifies the delegate.

        :param int offset: The offset value.
        """
        if (self._connection_state == BeltConnectionState.DISCONNECTED or
                self._connection_state == BeltConnectionState.DISCONNECTING):
            return
        if offset < 0 or offset > 359:
            self.logger.error("BeltController: Illegal offset notification argument.")
            return
        self._heading_offset = offset
        try:
            self._delegate.on_heading_offset_notified(offset)
        except:
            pass

    def _notify_bt_name(self, bt_name):
        """
        Notifies the delegate of the BT name.

        :param bytearray bt_name: The BT name.
        """
        if (self._connection_state == BeltConnectionState.DISCONNECTED or
                self._connection_state == BeltConnectionState.DISCONNECTING):
            return
        bt_name = decode_ascii(bt_name)
        try:
            self._delegate.on_bt_name_notified(bt_name)
        except:
            pass

    def _notify_compass_accuracy_signal_state(self, state):
        """
        Sets the compass accuracy signal state member variable and notifies the delegate.

        :param int state: The signal state.
        """
        if (self._connection_state == BeltConnectionState.DISCONNECTED or
                self._connection_state == BeltConnectionState.DISCONNECTING):
            return
        self._compass_accuracy_signal_enabled = state != 0
        try:
            self._delegate.on_compass_accuracy_signal_state_notified(state != 0)
        except:
            pass

    def _is_ack(self, gatt_char, data) -> bool:
        """
        Checks if the data corresponds to the current acknowledgment.

        :param GattCharacteristic gatt_char: The GATT characteristic of the notification.
        :param bytes data: The data received.
        :return: 'True' if the ACK is verified, 'False' otherwise.
        """
        try:
            if self._ack_char is not None:
                if self._ack_char != gatt_char:
                    return False
            if self._ack_data is not None:
                if len(self._ack_data) > len(data):
                    return False
                for packet_byte, ack_byte in zip(data, self._ack_data):
                    if ack_byte is not None:
                        if ack_byte != packet_byte:
                            return False
            return True
        except:
            self.logger.warning("BeltController: Unable to check ACK.")
        return False

    # --------------------------------------------------------------- #
    # Implementation of communication interface delegate methods

    def on_connection_established(self):
        # Save last connection for reconnection
        self._last_connected_interface = self._communication_interface
        self.logger.debug("BeltController: Connection established.")
        pass

    def on_connection_closed(self, expected=True):
        self.logger.debug("BeltController: Connection closed.")
        if expected or self._connection_state == BeltConnectionState.DISCONNECTING:
            self._set_connection_state(BeltConnectionState.DISCONNECTED)
        else:
            self._set_connection_state(
                BeltConnectionState.DISCONNECTED,
                BeltConnectionError("Connection lost."))

    def on_gatt_char_notified(self, gatt_char, data):

        # Process packet
        try:
            self.logger.log(5, "BeltController: "+gatt_char.uuid[4:8]+" <- "+bytes_to_hexstr(data))
        except:
            pass

        # Check for power-off notification
        if ((gatt_char == navibelt_button_press_char and len(data) >= 5 and data[4] == BeltMode.STANDBY) or
            (gatt_char == navibelt_param_notification_char and len(data) >= 3 and data[0] == 0x01 and
             data[1] == 0x01 and data[2] == BeltMode.STANDBY)):
            self.logger.info("BeltController: Belt switched off.")
            self._communication_interface.close()

        # Firmware information
        if gatt_char == navibelt_firmware_info_char:
            # Firmware information received
            if len(data) >= 2:
                try:
                    self._firmware_version = int.from_bytes(
                        bytes(data[:2]), byteorder='little', signed=False)
                except:
                    self.logger.error("Unable to parse firmware version.")

        # Keep alive request
        if gatt_char == navibelt_keep_alive_char:
            # Retrieve belt mode
            if len(data) >= 2:
                self._set_belt_mode(data[1])
            # Send keep-alive ACK
            self.write_gatt(navibelt_keep_alive_char, bytes([0x01]))

        # Button press notification
        if gatt_char == navibelt_button_press_char:
            if len(data) >= 5:
                self._notify_button_pressed(data[0], data[3], data[4])

        # Belt mode change
        if gatt_char == navibelt_param_notification_char:
            if len(data) >= 3 and data[0] == 0x01 and data[1] == 0x01:
                self._notify_belt_mode(data[2])

        # Default intensity
        if gatt_char == navibelt_param_notification_char:
            if len(data) >= 3 and data[0] == 0x01 and data[1] == 0x02:
                self._notify_default_intensity(data[2])

        # Heading offset
        if gatt_char == navibelt_param_notification_char:
            if len(data) >= 4 and data[0] == 0x01 and data[1] == 0x03:
                self._notify_heading_offset(int.from_bytes(
                        bytes(data[2:4]), byteorder='little', signed=False))

        # BT name
        if gatt_char == navibelt_param_notification_char:
            if len(data) >= 2 and data[0] == 0x01 and data[1] == 0x04:
                self._notify_bt_name(bytearray(data[2:]))

        # Advanced parameters
        if gatt_char == navibelt_param_notification_char:
            if len(data) >= 2 and data[0] == 0x10:
                if data[1] == 0x00:
                    # Default intensity
                    self._notify_default_intensity(data[2])
                elif data[1] == 0x01:
                    # Heading offset
                    self._notify_heading_offset(int.from_bytes(
                        bytes(data[2:4]), byteorder='little', signed=False))
                elif data[1] == 0x03:
                    # Compass accuracy signal state
                    self._notify_compass_accuracy_signal_state(data[2])

        # Self-test state notification
        if gatt_char == navibelt_debug_output_char:
            if len(data) >= 4 and data[0] == 0x02:
                if data[1] != 0x00:
                    # Self-test started
                    self.logger.info("BeltController: Belt self-test started.")
                else:
                    # Self-test completed
                    if data[3] == 0:
                        self.logger.info("BeltController: Belt self-test completed with no error.")
                    else:
                        self.logger.error("BeltController: Belt self-test completed with " +
                                          repr(data[3]) + " error(s)!")

        # Error notification
        if gatt_char == navibelt_debug_output_char:
            if len(data) >= 5 and data[0] == 0xA0:
                error_id = int.from_bytes(bytes(data[1:5]), byteorder='little', signed=False)
                self.logger.error("BeltController: Belt error " + hex(error_id) + " !")

        # Debug message
        if len(self._debug_message_buffer) > 0 and \
                time.perf_counter()-self._debug_message_last_received > DEBUG_MESSAGE_COMPLETION_TIMEOUT:
            # Output incomplete debug message
            self.logger.debug("Belt debug message: " + self._debug_message_buffer)
            self._debug_message_buffer = ""
        if gatt_char == navibelt_debug_output_char:
            if len(data) > 1 and data[0] == 0x01:
                self._debug_message_buffer += decode_ascii(data[1:])
                self._debug_message_last_received = time.perf_counter()
        # Output message ending with '\n'
        eol = self._debug_message_buffer.find('\n')
        while eol >= 0:
            line = self._debug_message_buffer[:eol]
            self._debug_message_buffer = self._debug_message_buffer[eol+1:]
            self.logger.debug("Belt debug message: " + line)
            eol = self._debug_message_buffer.find('\n')

        # TODO Other notifications

        # Check for ACK
        if (self._ack_data is not None or self._ack_char is not None) and not self._ack_event.is_set():
            if self._is_ack(gatt_char, data):
                self._ack_data = None
                self._ack_char = None
                self._ack_event.set()

        # Inform system handlers
        for handler in self._system_handlers:
            try:
                handler.on_gatt_char_notified(gatt_char, data)
            except:
                pass


def bytes_to_hexstr(data) -> str:
    """
    Returns a string representation of bytes.
    :param bytes data: The data to convert.
    :return: A string representation of the data.
    """
    if len(data) == 0:
        return "[]"
    strRep = "0x"
    for d in data:
        if d < 16:
            strRep = strRep+"0"+hex(d)[2:]
        else:
            strRep = strRep + hex(d)[2:]
    return strRep


class BeltConnectionState:
    """Enumeration of connection state."""

    DISCONNECTED = 0
    CONNECTING = 1
    CONNECTED = 2
    DISCONNECTING = 3


class BeltMode:
    """Enumeration of the belt modes."""

    STANDBY = 0
    WAIT = 1
    COMPASS = 2
    APP_MODE = 3
    PAUSE = 4
    CALIBRATION = 5
    CROSSING = 6


class BeltControllerDelegate:
    """Delegate interface for the belt controller.
    """

    def on_connection_state_changed(self, state, error=None):
        """Called when the connection state changed.

        Parameters
        ----------
        :param int state:
            The connection state.
        :param Exception error:
            Error if the state change is unexpected.
        """
        pass

    def on_belt_mode_changed(self, belt_mode):
        """Called when the belt mode changed.

        :param int belt_mode:
            The belt mode.
        """
        pass

    def on_belt_button_pressed(self, button_id, previous_mode, new_mode):
        """Called when a button on the belt has been pressed.

        :param int button_id:
            The button ID.
        :param int previous_mode:
            The belt mode before the button press event.
        :param int new_mode:
            The belt mode after the button press event.
        """
        pass

    def on_default_intensity_changed(self, intensity):
        """Called when the default intensity has been changed or notified.

        :param int intensity:
            The default vibration intensity of the belt.
        """
        pass

    def on_heading_offset_notified(self, offset):
        """Called when the heading offset of the belt has been changed or notified.

        :param int offset:
            The heading offset of the belt.
        """
        pass

    def on_bt_name_notified(self, bt_name):
        """Called when the BT name of the belt has been changed or notified.

        :param str bt_name:
            The BT name of the belt.
        """
        pass

    def on_compass_accuracy_signal_state_notified(self, enabled):
        """
        Called when the state of the compass accuracy signal has been changed or notified.

        :param bool enabled:
            'True' if the signal is enabled, 'False' otherwise.
        """
        pass


class BeltConnectionError(Exception):
    """Exception raised for belt connection problems.
    """

    def __init__(self, message):
        """Constructor.

        Parameters
        ----------
        :param str message:
            The error message.
        """
        super().__init__(message)


class BeltSystemHandler:
    """
    Handler interface for belt debug and test.
    """

    def on_gatt_char_notified(self, gatt_char, data):
        """
        Called when a GATT notification has been received or a characteristic has been read.

        :param GattCharacteristic gatt_char:
        :param bytes data: The data received.
        """
        pass
