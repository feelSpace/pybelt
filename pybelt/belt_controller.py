# Copyright 2020, feelSpace GmbH, <info@feelspace.de>

from pybelt._communication_interface import *
from pybelt._gatt_profile import *
from typing import List

WAIT_ACK_TIMEOUT_SEC = 1  # Default timeout for waiting acknowledgment
DEBUG_MESSAGE_COMPLETION_TIMEOUT = 0.5  # Timeout for waiting the completion of a debug message
WAIT_DISCONNECTION_TIMEOUT_SEC = 10.0  # Timeout for disconnection


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
        self._notifications_handlers = []

        # Connection state
        self._connection_state = BeltConnectionState.DISCONNECTED

        # Connection
        self._communication_interface = None
        self._last_connected_interface = None
        self._disconnection_event = threading.Event()

        # Packet ack
        self._ack_char = None
        self._ack_data = None
        self._ack_event = threading.Event()
        self._ack_rsp = None

        # GATT profile
        self._gatt_profile = None

        # Cache of belt parameters
        self._belt_mode = None
        self._default_intensity = None
        self._firmware_version = None
        self._battery_status = None
        self._belt_orientation = None
        self._heading_offset = None
        self._inaccurate_signal_state = None

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
            self.logger.exception("BeltController: Connection failed.")
            self._close_connection()
            self._set_connection_state(
                BeltConnectionState.DISCONNECTED,
                BeltConnectionError("Connection failed."))
            return
        # Retrieve GATT profile
        self._gatt_profile = self._communication_interface.get_gatt_profile()
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
            self.connect(self._last_connected_interface.get_port())
        except:
            self.logger.exception("BeltController: Error when reconnecting.")

    def disconnect_belt(self, wait=True):
        """Disconnects the belt.

        In case `wait` parameter is `False`, the program should not end before complete disconnection. Disconnection
        is notified to the delegate via `on_connection_state_changed`.

        :param bool wait: 'True' to block until disconnection.
        """
        self._disconnection_event.clear()
        if (self._connection_state == BeltConnectionState.DISCONNECTING or
                self._connection_state == BeltConnectionState.DISCONNECTED):
            return
        self._set_connection_state(BeltConnectionState.DISCONNECTING)
        self._close_connection()
        if wait:
            self._disconnection_event.wait(WAIT_DISCONNECTION_TIMEOUT_SEC)
            if self._connection_state != BeltConnectionState.DISCONNECTED:
                self.logger.warning("BeltController: Disconnection timeout!")

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

    def set_belt_mode(self, mode, wait_ack=False) -> bool:
        """ Sets the mode of the belt.
        This operation is asynchronous except if the parameter ´wait_ack´ is True.
        The delegate will be informed of the mode change via ´on_belt_mode_changed´.

        :param int mode: The mode to be set. See ´BeltMode´ for a list of the modes.
        :param bool wait_ack: True to wait for mode change acknowledgment.
        :return: True if the request has been sent, False if no belt is connected.
        :raise ValueError: If the mode value is not valid.
        :raise TimeoutError: If the acknowledgment is waited and the timeout period is reached.
        """
        if self._connection_state != BeltConnectionState.CONNECTED:
            self.logger.warning("BeltController: Cannot set the belt mode when not connected.")
            return False
        if mode < 0 or mode > 6:
            raise ValueError("Belt mode value out of range.")
        if wait_ack:
            write_result = self.write_gatt(
                self._gatt_profile.param_request_char,
                bytes([0x01, 0x81, mode]),
                self._gatt_profile.param_notification_char,
                b'\x01\x01')
        else:
            write_result = self.write_gatt(
                self._gatt_profile.param_request_char,
                bytes([0x01, 0x81, mode]))
        if write_result == 2:
            raise TimeoutError("Timeout period reached when changing the belt mode.")
        return write_result == 0

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

    def set_default_intensity(self, intensity, vibration_feedback=False, wait_ack=False) -> bool:
        """
        Sets the default intensity for belt signals such as compass.

        Note: The minimum default intensity is 5%. Any request to change the intensity below 5% will result in setting
        this minimum intensity.

        :param int intensity: The default intensity to set in range [0-100].
        :param bool vibration_feedback: True to start a vibration informing about the new intensity, False for no
        vibration feedback.
        :param bool wait_ack: True to wait for mode change acknowledgment.
        :return: 'True' if the request has been sent successfully.
        :raise TimeoutError: If the timeout period is reached when waiting for acknowledgment.
        """
        if self._connection_state != BeltConnectionState.CONNECTED:
            self.logger.warning("BeltController: Cannot set the default intensity when not connected.")
            return False
        if intensity < 0:
            intensity = 0
        if intensity > 100:
            intensity = 100
        if wait_ack:
            write_result = self.write_gatt(
                self._gatt_profile.param_request_char,
                bytes([0x01, 0x82, intensity, 0x00, (0x01 if vibration_feedback else 0x00)]),
                self._gatt_profile.param_notification_char,
                b'\x01\x02')
        else:
            write_result = self.write_gatt(
                self._gatt_profile.param_request_char,
                bytes([0x01, 0x82, intensity, 0x00, (0x01 if vibration_feedback else 0x00)]))
        if write_result == 2:
            raise TimeoutError("Timeout period reached when changing the belt mode.")
        return write_result == 0

    def write_gatt(self, gatt_char, data, ack_char=None, ack_data=None, timeout_sec=WAIT_ACK_TIMEOUT_SEC,
                   with_response=True) -> int:
        """
        Sends data to a GATT characteristic.

        :param GattCharacteristic gatt_char: The characteristic to write.
        :param bytes data: The data to write.
        :param GattCharacteristic ack_char: The characteristic for which an acknowledgment should be waited.
        :param bytes|list ack_data: The acknowledgment pattern.
        :param float timeout_sec: The timeout period in seconds.
        :param bool with_response: 'True' to write with response, 'False' to write without response.
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
            self._ack_rsp = None
            self._ack_event.clear()
        # Send packet
        try:
            self.logger.log(5, "BeltController: " + gatt_char.uuid[4:8] + " -> " + bytes_to_hexstr(data))
        except:
            pass
        try:
            if not self._communication_interface.write_gatt_char(gatt_char, data, with_response=with_response):
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
            self._ack_rsp = None
            self._ack_event.clear()
        return 0

    def request_gatt(self, gatt_char, data, rsp_char, rsp_pattern=None, timeout_sec=WAIT_ACK_TIMEOUT_SEC,
                   with_response=True) -> (int, bytes):
        """
        Sends a command and wait for a response.

        :param GattCharacteristic gatt_char: The characteristic to write.
        :param bytes data: The data to write.
        :param GattCharacteristic rsp_char: The characteristic on which the response is received.
        :param bytes|list rsp_pattern: The response pattern.
        :param float timeout_sec: The timeout period in seconds.
        :param bool with_response: 'True' to write with response, 'False' to write without response.
        :return: Returns a tuple with a response code: '0' if successful, '1' when no connection is available or a
        problem occurs, '2' when the timeout is reached, and the data received.
        """
        if (self._connection_state == BeltConnectionState.DISCONNECTED or
                self._connection_state == BeltConnectionState.DISCONNECTING):
            self.logger.error("BeltController: No connection to send packet.")
            return (1, b'')
        # Set ACK
        self._ack_char = rsp_char
        self._ack_data = rsp_pattern
        self._ack_rsp = None
        self._ack_event.clear()
        # Send packet
        try:
            self.logger.log(5, "BeltController: " + gatt_char.uuid[4:8] + " -> " + bytes_to_hexstr(data))
        except:
            pass
        try:
            if not self._communication_interface.write_gatt_char(gatt_char, data, with_response=with_response):
                self.logger.error("BeltController: Error when sending packet.")
                self._ack_char = None
                self._ack_data = None
                self._ack_event.clear()
                return (1, b'')
        except:
            self.logger.exception("BeltController: Error when sending packet.")
            self._ack_char = None
            self._ack_data = None
            self._ack_event.clear()
            return (1, b'')
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
            return (2, b'')
        # Clear ACK flag
        rsp = self._ack_rsp
        self._ack_char = None
        self._ack_data = None
        self._ack_rsp = None
        self._ack_event.clear()
        return (0, rsp)

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
        self._ack_rsp = None
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

    def add_notifications_handler(self, handler):
        """
        Adds a notifications handler.
        :param BeltNotificationsHandler handler: The notifications handler to add.
        """
        self._notifications_handlers.append(handler)

    def remove_notifications_handler(self, handler):
        """
        Removes a notifications handler.
        :param BeltNotificationsHandler handler: The handler to remove
        """
        self._notifications_handlers.remove(handler)

    def set_orientation_notifications(self, enabled) -> bool:
        """
        Sets the state of orientation notifications.

        IMPORTANT: It is important to note that orientation updates from the belt were not designed for updating a
        system in real-time, just for monitoring and showing on a map the orientation of the belt. In case you need a
        vibration signal on the belt that is dependent on the orientation, you can use the `vibrate_at_magnetic_bearing`
        or `send_pulse_command` (with orientation_type=MAGNETIC_BEARING) to get a vibration relative to magnetic North.

        :param enabled: 'True' to enable orientation notifications, 'False' to disable.
        :return: 'True' if the request has been sent successfully.
        """
        if self._connection_state == BeltConnectionState.DISCONNECTED:
            return False
        return self._communication_interface.set_gatt_notifications(self._gatt_profile.orientation_data_char, enabled)

    def set_power_status_notifications(self, enabled) -> bool:
        """
        Sets the state of power status notifications.

        :param enabled: 'True' to enable power status notifications, 'False' to disable.
        :return: 'True' if the request has been sent successfully.
        """
        if self._connection_state == BeltConnectionState.DISCONNECTED:
            return False
        return self._communication_interface.set_gatt_notifications(self._gatt_profile.battery_status_char, enabled)

    def rename(self, suffix) -> bool:
        """
        Renames the belt with a suffix.
        :param str suffix: The suffix of the belt to set.
        :return: 'True' if the request has been sent successfully.
        """
        # TODO To be moved in diagnostic app
        # TODO Adds parameter wait_ack
        # TODO Raise ValueError If a parameter value is illegal.
        # TODO Reset name if suffix is None
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
                self._gatt_profile.param_request_char,
                bytes([0x01, 0x84]) + encoded_suffix) != 0:
            return False
        self.logger.debug("BeltController: Rename request sent.")
        if isinstance(self._communication_interface, BleInterface):
            self._communication_interface.close()

    def set_pairing_requirement(self, pairing_required, save=True, wait_ack=False) -> bool:
        """
        Sets the pairing requirement of the belt. The pairing requirement determines if the belt requires pairing or not
        for connections. When pairing is disabled, any device can connect to the belt without pairing. When pairing is
        enable, the belt only accept connection from paired devices. To pair a device when pairing is enabled, the
        pairing mode must be started on the belt by pressing the home button for at least 3 seconds, then the device to
        connect must request pairing.

        It is recommended to enable pairing for a general usage of the belt and to disable it only for testing purpose.

        :param bool pairing_required: 'True' to require pairing.
        :param bool save: 'True' to save the setting on the belt, False for a temporary setting.
        :param bool wait_ack: 'True' to wait for acknowledgment.
        :return: 'True' if the request has been sent successfully.
        """
        if self._connection_state != BeltConnectionState.CONNECTED:
            self.logger.warning("BeltController: Cannot set pairing requirement when not connected.")
            return False
        if wait_ack:
            write_result = self.write_gatt(
                self._gatt_profile.param_request_char,
                bytes([
                    0x11,
                    0x25,
                    (0x01 if save else 0x00),
                    (0x01 if pairing_required else 0x00)]),
                self._gatt_profile.param_notification_char,
                b'\x10\x25')
        else:
            write_result = self.write_gatt(
                self._gatt_profile.param_request_char,
                bytes([
                    0x11,
                    0x25,
                    (0x01 if save else 0x00),
                    (0x01 if pairing_required else 0x00)]),
                self._gatt_profile.param_notification_char)
        if write_result == 2:
            raise TimeoutError("Timeout period reached when setting pairing requirement.")
        return write_result == 0

    def set_orientation_notification_period(self, period, start_notification) -> bool:
        """
        Sets the period for orientation notifications.

        Changing the period of orientation notifications is only available from firmware version 52. The minimum
        notification period supported by the belt is 20ms (i.e. 50Hz).

        IMPORTANT: It is important to note that orientation updates from the belt were not designed for updating a
        system in real-time, just for monitoring and showing on a map the orientation of the belt. In case you need a
        vibration signal on the belt that is dependent on the orientation, you can use the `vibrate_at_magnetic_bearing`
        or `send_pulse_command` (with orientation_type=MAGNETIC_BEARING) to get a vibration relative to magnetic North.

        The belt orientation may be inaccurate when used indoor because of magnetic interference. To get a better
        orientation, it is recommended to calibrate the belt in the room where it is used (or outdoor if used outdoor).

        It is not recommended to use short notification period over BLE connection. For short notification
        periods, after disconnection, it may be required to wait a few seconds to reconnect the belt again. If the
        reconnection failed, it may be necessary to restart the belt. In case the belt does not respond anymore, you can
        make a “hard power-off” by pressing the power button of the belt more than 6 seconds and then pressing it again
        to restart the belt.

        :param period: The period in seconds. Minimum value is 20 milliseconds (50Hz).
        :param start_notification: 'True' to start the orientation notification.
        :return: 'True' on success, 'False' otherwise.
        """
        if self.get_connection_state() != BeltConnectionState.CONNECTED:
            self.logger.warning("BeltController: No belt belt connected to set notification period.")
            return False
        if self.get_firmware_version() < 52:
            self.logger.warning("BeltController: Belt firmware version not supported.")
            return False
        if period < 0.02:
            self.logger.warning("BeltController: Notification period not supported.")
            return False
        period_ms = int(period * 1000.0)
        self.set_orientation_notifications(False)
        if self.write_gatt(self._gatt_profile.param_request_char,
                           bytes([
                               0x11,
                               0x0F,
                               0x00,
                               period_ms & 0xFF,
                               (period_ms >> 8) & 0xFF,
                           ]),
                           self._gatt_profile.param_notification_char,
                           b'\x10\x0F') != 0:
            self.logger.warning("BeltController: Failed to write notification period parameter.")
            return False
        return self.set_orientation_notifications(True)

    def vibrate_at_magnetic_bearing(
            self,
            bearing,
            switch_to_app_mode=True,
            channel_index=1,
            intensity=None,
            clear_other_channels=False) -> bool:
        """
        Sends a command to start a continuous vibration in a given direction relative to magnetic North.

        :param int bearing: The direction relative to magnetic North in degrees (positive clockwise).
        :param bool switch_to_app_mode: `True` to switch automatically to app mode.
        :param int channel_index: The channel index to configure. The belt has six channels (index 0 to 5).
        :param int intensity: The intensity of the vibration in range [0, 100] or `None` to use the default intensity.
        :param bool clear_other_channels: `True` to stop and clear other channels when this vibration starts.
        :return: `True` if the command has been sent successfully.
        :raise ValueError: If a parameter value is illegal.
        """
        if self._connection_state != BeltConnectionState.CONNECTED:
            self.logger.warning("BeltController: Cannot send a command when not connected.")
            return False
        if self._belt_mode != BeltMode.APP_MODE and switch_to_app_mode:
            if not self.set_belt_mode(BeltMode.APP_MODE):
                return False
        return self.send_vibration_command(
            channel_index=channel_index,
            pattern=BeltVibrationPattern.CONTINUOUS,
            intensity=intensity,
            orientation_type=BeltOrientationType.MAGNETIC_BEARING,
            orientation=bearing,
            pattern_iterations=None,
            pattern_period=500,
            pattern_start_time=0,
            exclusive_channel=False,
            clear_other_channels=clear_other_channels
        )

    def vibrate_at_angle(
            self,
            angle,
            switch_to_app_mode=True,
            channel_index=1,
            intensity=None,
            clear_other_channels=False) -> bool:
        """
        Sends a command to start a continuous vibration in a given direction relative to user front direction.

        :param int angle: The orientation of the vibration in degrees (positive clockwise), 0 is for front.
        :param bool switch_to_app_mode: `True` to switch automatically to app mode.
        :param int channel_index: The channel index to configure. The belt has six channels (index 0 to 5).
        :param int intensity: The intensity of the vibration in range [0, 100] or `None` to use the default intensity.
        :param bool clear_other_channels: `True` to stop and clear other channels when this vibration starts.
        :return: `True` if the command has been sent successfully.
        :raise ValueError: If a parameter value is illegal.
        """
        if self._connection_state != BeltConnectionState.CONNECTED:
            self.logger.warning("BeltController: Cannot send a command when not connected.")
            return False
        if self._belt_mode != BeltMode.APP_MODE and switch_to_app_mode:
            if not self.set_belt_mode(BeltMode.APP_MODE):
                return False
        return self.send_vibration_command(
            channel_index=channel_index,
            pattern=BeltVibrationPattern.CONTINUOUS,
            intensity=intensity,
            orientation_type=BeltOrientationType.ANGLE,
            orientation=angle,
            pattern_iterations=None,
            pattern_period=500,
            pattern_start_time=0,
            exclusive_channel=False,
            clear_other_channels=clear_other_channels
        )

    def send_vibration_command(
            self,
            channel_index,
            pattern,
            intensity,
            orientation_type,
            orientation,
            pattern_iterations,
            pattern_period,
            pattern_start_time,
            exclusive_channel,
            clear_other_channels) -> bool:
        """
        Sends a command that configures the vibration on a vibration channel.

        :param int channel_index: The channel index to configure. The belt has six channels (index 0 to 5).
        :param int pattern: The vibration pattern to use, see `BeltVibrationPattern`.
        :param Union[int,None] intensity: The intensity of the vibration in range [0, 100] or `None` to use the default
            intensity.
        :param int orientation_type: The type of signal orientation, see `BeltOrientationType`.
        :param int orientation: The value of the vibration orientation.
        :param Union[int,None] pattern_iterations: The number of pattern iterations or `None` to repeat indefinitely the
            pattern. The maximum value is 127 iterations.
        :param int pattern_period: The duration in milliseconds of one pattern iteration. The maximum period is 65535
            milliseconds.
        :param int pattern_start_time: The starting time in milliseconds of the first pattern iteration.
        :param bool exclusive_channel: `True` to suspend other channels as long as this vibration is active.
        :param bool clear_other_channels: `True` to stop and clear other channels when this vibration starts.
        :return: `True` if the command has been sent successfully.
        :raise ValueError: If a parameter value is illegal.
        """
        if channel_index < 0 or channel_index > 5:
            raise ValueError("Channel index value out of range.")
        if pattern < 0 or pattern > 26:
            raise ValueError("Pattern value out of range.")
        if (intensity is not None) and (intensity < 0 or intensity > 100):
            raise ValueError("Intensity value out of range.")
        if orientation_type < 0 or orientation_type > 3:
            raise ValueError("Orientation type value out of range.")
        if (pattern_iterations is not None) and (pattern_iterations < 0 or pattern_iterations > 127):
            raise ValueError("Pattern iterations value out of range.")
        if pattern_period <= 0 or pattern_period > 65535:
            raise ValueError("Pattern period value out of range.")
        if pattern_start_time < 0 or pattern_start_time > 65535:
            raise ValueError("Pattern start time value out of range.")
        if self._connection_state != BeltConnectionState.CONNECTED:
            self.logger.warning("BeltController: Cannot send a command when not connected.")
            return False
        # Adjust values
        if intensity is None:
            intensity = 0xAAAA
        if orientation_type == BeltOrientationType.MAGNETIC_BEARING or orientation_type == BeltOrientationType.ANGLE:
            orientation = orientation % 360
        if orientation_type == BeltOrientationType.MOTOR_INDEX:
            orientation = orientation % 16
        # Send command
        return self.write_gatt(
            self._gatt_profile.vibration_command_char,
            bytes([
                channel_index,
                pattern,
                intensity & 0xFF,
                (intensity >> 8) & 0xFF,
                0x00,
                0x00,
                orientation_type,
                orientation & 0xFF,
                (orientation >> 8) & 0xFF,
                0x00,
                0x00,
                (0x00 if pattern_iterations is None else pattern_iterations),
                pattern_period & 0xFF,
                (pattern_period >> 8) & 0xFF,
                pattern_start_time & 0xFF,
                (pattern_start_time >> 8) & 0xFF,
                (0x01 if exclusive_channel else 0x00),
                (0x01 if clear_other_channels else 0x00)
            ])) == 0

    def send_pulse_command(
            self,
            channel_index,
            orientation_type,
            orientation,
            intensity,
            on_duration_ms,
            pulse_period,
            pulse_iterations,
            series_period,
            series_iterations,
            timer_option,
            exclusive_channel,
            clear_other_channels) -> bool:
        """
        Sends a command that configures vibration pulses on a vibration channel.

        :param int channel_index: The channel index to configure. The belt has six channels (index 0 to 5).
        :param int orientation_type: The type of signal orientation, see `BeltOrientationType`.
        :param int orientation: The value of the vibration orientation.
        :param Union[int,None] intensity: The intensity of the vibration in range [0, 100] or `None` to use the default
            intensity.
        :param int on_duration_ms: The on-duration of a pulse in milliseconds.
        :param int pulse_period: The period of pulses in milliseconds.
        :param int pulse_iterations: The number of pulses in a series.
        :param int series_period: The period of a series of pulses.
        :param Union[int,None] series_iterations: The number of series iterations or `None` to repeat the series of
            pulse indefinitely.
        :param int timer_option: Behavior of the timer for vibration, see `BeltVibrationTimerOption`.
        :param bool exclusive_channel: `True` to suspend other channels as long as this vibration is active.
        :param bool clear_other_channels: `True` to stop and clear other channels when this vibration starts.
        :return: `True` if the command has been sent successfully.
        :raise ValueError: If a parameter value is illegal.
        """
        if channel_index < 0 or channel_index > 5:
            raise ValueError("Channel index value out of range.")
        if orientation_type < 0 or orientation_type > 3:
            raise ValueError("Orientation type value out of range.")
        if (intensity is not None) and (intensity < 0 or intensity > 100):
            raise ValueError("Intensity value out of range.")
        if on_duration_ms <= 0 or on_duration_ms > 65535:
            raise ValueError("On-duration value out of range.")
        if pulse_period <= 0 or pulse_period > 65535:
            raise ValueError("On-duration value out of range.")
        if pulse_iterations <= 0 or pulse_iterations > 255:
            raise ValueError("Pulse iterations value out of range.")
        if series_period <= 0 or series_period > 65535:
            raise ValueError("Series period value out of range.")
        if (series_iterations is not None) and (series_iterations < 0 or series_iterations > 127):
            raise ValueError("Series iterations value out of range.")
        if timer_option < 0 or timer_option > 2:
            raise ValueError("Timer option value out of range.")
        # Adjust values
        if intensity is None:
            intensity = 0xAA
        if orientation_type == BeltOrientationType.MAGNETIC_BEARING or orientation_type == BeltOrientationType.ANGLE:
            orientation = orientation % 360
        if orientation_type == BeltOrientationType.MOTOR_INDEX:
            orientation = orientation % 16
        # Send command
        return self.write_gatt(
            self._gatt_profile.vibration_command_char,
            bytes([
                0x40,
                channel_index,
                orientation_type,
                orientation & 0xFF,
                (orientation >> 8) & 0xFF,
                intensity,
                on_duration_ms & 0xFF,
                (on_duration_ms >> 8) & 0xFF,
                pulse_iterations,
                (0x00 if series_iterations is None else series_iterations),
                pulse_period & 0xFF,
                (pulse_period >> 8) & 0xFF,
                series_period & 0xFF,
                (series_period >> 8) & 0xFF,
                timer_option,
                (0x01 if exclusive_channel else 0x00),
                (0x01 if clear_other_channels else 0x00)
            ])) == 0

    def stop_vibration(
            self,
            channel_index=None) -> bool:
        """
        Stops the vibration on all or one vibration channel in App mode.

        :param int channel_index: The channel index to stop in range [0, 5], or `None` to stop all channels.
        :return: `True` if the command has been sent successfully.
        :raise ValueError: If the channel index value is out of range.
        """
        if (channel_index is not None) and (channel_index < 0 or channel_index > 5):
            raise ValueError("Channel index value out of range.")
        if self._connection_state != BeltConnectionState.CONNECTED:
            self.logger.warning("BeltController: Cannot send a command when not connected.")
            return False
        if channel_index is None:
            return self.write_gatt(
                self._gatt_profile.vibration_command_char,
                bytes([0x30, 0xFF])) == 0
        else:
            return self.write_gatt(
                self._gatt_profile.vibration_command_char,
                bytes([0x30, channel_index & 0xFF])) == 0

    def get_inaccurate_orientation_signal_state(self) -> (bool, bool):
        """ Returns the state (enabled/disabled) of the inaccurate orientation signal.

        :return: A tuple indicating the state of the inaccurate signal. The first value is the state in application
            mode, the second one is the state in compass mode. Returns `None` if the belt is not connected,
        """
        return self._inaccurate_signal_state

    def set_inaccurate_orientation_signal_state(self, enable_in_app, save_on_belt, enable_in_compass=True,
                                                wait_ack=False) -> bool:
        """ Sets the state of the inaccurate orientation signal.

        The inaccurate orientation signal is a vibration signal that indicates a possible inaccuracy in orientation
        relative to magnetic North. The signal consists in three pulses on both sides of the belt. If your application
        does not rely on the compass for the direction of vibrations, you can disable temporarily the inaccurate
        orientation signal for the application mode. You can also disable and save this configuration on the belt if
        you use a belt for an experiment.

        IMPORTANT: If your application is meant for other users than you, you must explicitly inform the user before
        disabling the inaccurate orientation signal. The inaccurate orientation signal is important for a safe usage
        of the belt.

        :param bool enable_in_app: `True` to enable the inaccurate signal in application mode, `False` to disable the
            signal.
        :param bool save_on_belt: `True` to save the inaccurate signal configuration on the belt. If `False` the
            configuration will be reset on power cycle.
        :param bool enable_in_compass:  `True` to enable the inaccurate signal in compass mode, `False` to disable the
            signal.
        :param bool wait_ack: `True` to wait for request acknowledgment.
        :return: `True` if the request has been sent correctly, `False` if no belt is connected or a communication
            problem occurs.
        :raise TimeoutError: If acknowledgment is not received within the timeout period.
        """
        if self._connection_state != BeltConnectionState.CONNECTED:
            self.logger.warning("BeltController: Cannot set inaccurate signal state when not connected.")
            return False
        signal_state = 0
        if enable_in_compass:
            signal_state = signal_state + 1
        if enable_in_app:
            signal_state = signal_state + 2
        if wait_ack:
            write_result = self.write_gatt(
                self._gatt_profile.param_request_char,
                bytes([
                    0x11,
                    0x03,
                    (0x01 if save_on_belt else 0x00),
                    signal_state]),
                self._gatt_profile.param_notification_char,
                b'\x10\x03')
        else:
            write_result = self.write_gatt(
                self._gatt_profile.param_request_char,
                bytes([
                    0x11,
                    0x03,
                    (0x01 if save_on_belt else 0x00),
                    signal_state]),
                self._gatt_profile.param_notification_char)
        if write_result == 2:
            raise TimeoutError("Timeout period reached when setting inaccurate signal state.")
        return write_result == 0

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
        self._inaccurate_signal_state = None

    def _handshake(self):
        """Handshake procedure.

        :return: 'True' if the handshake is successful, 'False' otherwise.
        """
        self.logger.info("BeltController: Start handshake.")
        # Register to keep-alive
        self.logger.debug("BeltController: Register to keep-alive notifications.")
        if not self._communication_interface.set_gatt_notifications(self._gatt_profile.keep_alive_char, True):
            return False

        # Register to parameter notifications
        self.logger.debug("BeltController: Register to parameter notifications.")
        if not self._communication_interface.set_gatt_notifications(self._gatt_profile.param_notification_char, True):
            return False

        # Read belt mode
        self.logger.debug("BeltController: Read belt mode.")
        if (self.write_gatt(self._gatt_profile.param_request_char,
                            b'\x01\x01',
                            self._gatt_profile.param_notification_char,
                            b'\x01\x01') != 0):
            self.logger.error("BeltController: Failed to request belt mode.")
            return False
        if self._belt_mode is None:
            self.logger.error("BeltController: Failed to read belt mode.")
            return False

        # Read default intensity
        self.logger.debug("BeltController: Read default intensity.")
        if (self.write_gatt(self._gatt_profile.param_request_char,
                            b'\x01\x02',
                            self._gatt_profile.param_notification_char,
                            b'\x01\x02') != 0):
            self.logger.error("BeltController: Failed to request default intensity.")
            return False
        if self._default_intensity is None:
            self.logger.error("BeltController: Failed to read default intensity.")
            return False

        # Read firmware version
        self.logger.debug("BeltController: Read firmware version.")
        if self.read_gatt(self._gatt_profile.firmware_info_char) != 0:
            self.logger.error("BeltController: Failed to request firmware version.")
            return False
        if self._firmware_version is None:
            self.logger.error("BeltController: Failed to read firmware version.")
            return False

        # Read heading offset
        self.logger.debug("BeltController: Read heading offset.")
        if (self.write_gatt(self._gatt_profile.param_request_char,
                            b'\x01\x03',
                            self._gatt_profile.param_notification_char,
                            b'\x01\x03') != 0):
            self.logger.error("BeltController: Failed to request default intensity.")
            return False
        if self._heading_offset is None:
            self.logger.error("BeltController: Failed to read default intensity.")
            return False

        # Read compass accuracy signal state
        self.logger.debug("BeltController: Read compass accuracy signal state.")
        if (self.write_gatt(self._gatt_profile.param_request_char,
                            b'\x10\x01\x03',
                            self._gatt_profile.param_notification_char,
                            b'\x10\x03') != 0):
            self.logger.error("BeltController: Failed to request compass accuracy signal state.")
            return False
        if self._inaccurate_signal_state is None:
            self.logger.error("BeltController: Failed to read compass accuracy signal state.")
            return False

        # Register to button press
        self.logger.debug("BeltController: Register to button press events.")
        if not self._communication_interface.set_gatt_notifications(self._gatt_profile.button_press_char, True):
            self.logger.error("BeltController: Failed to register to button press events.")
            return False

        # Register to orientation notifications
        self.logger.debug("BeltController: Register to orientation notifications.")
        if not self._communication_interface.set_gatt_notifications(self._gatt_profile.orientation_data_char, True):
            self.logger.error("BeltController: Failed to register to orientation notifications.")
            return False

        # Register to power status notifications
        self.logger.debug("BeltController: Register to power-status notifications.")
        if not self._communication_interface.set_gatt_notifications(self._gatt_profile.battery_status_char, True):
            self.logger.error("BeltController: Failed to register to power-status notifications.")
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
        if belt_mode < 0 or belt_mode > 10:
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
        enabled_in_compass = (state == 1) or (state == 3)
        enabled_in_app = (state == 2) or (state == 3)
        self._inaccurate_signal_state = (enabled_in_app, enabled_in_compass)
        try:
            self._delegate.on_inaccurate_orientation_signal_state_notified(enabled_in_app, enabled_in_compass)
        except:
            pass

    def _notify_pairing_requirement(self, pairing_required):
        """
        Notifies the delegate of the pairing requirement state.
        :param pairing_required: 'True' if pairing is required.
        """
        if (self._connection_state == BeltConnectionState.DISCONNECTED or
                self._connection_state == BeltConnectionState.DISCONNECTING):
            return
        try:
            self._delegate.on_pairing_requirement_notified(pairing_required)
        except:
            pass

    def _notify_belt_orientation(self, packet):
        """Notifies the belt orientation to the delegate.

        :param bytes packet: The raw orientation data.
        """
        if (self._connection_state == BeltConnectionState.DISCONNECTED or
                self._connection_state == BeltConnectionState.DISCONNECTING):
            return
        sensor_id = int.from_bytes(
            bytes(packet[0:1]),
            byteorder='little',
            signed=False)
        belt_heading = int.from_bytes(
            bytes(packet[1:3]),
            byteorder='little',
            signed=True)
        box_heading = int.from_bytes(
            bytes(packet[3:5]),
            byteorder='little',
            signed=True)
        box_roll = int.from_bytes(
            bytes(packet[5:7]),
            byteorder='little',
            signed=True)
        box_pitch = int.from_bytes(
            bytes(packet[7:9]),
            byteorder='little',
            signed=True)
        accuracy = int.from_bytes(
            bytes(packet[9:11]),
            byteorder='little',
            signed=False)
        mag_stat = int.from_bytes(
            bytes(packet[11:12]),
            byteorder='little',
            signed=True)
        acc_stat = int.from_bytes(
            bytes(packet[12:13]),
            byteorder='little',
            signed=True)
        gyr_stat = int.from_bytes(
            bytes(packet[13:14]),
            byteorder='little',
            signed=True)
        fus_stat = int.from_bytes(
            bytes(packet[14:15]),
            byteorder='little',
            signed=True)
        is_orientation_accurate = (int.from_bytes(
            bytes(packet[15:16]),
            byteorder='little',
            signed=False)) == 0
        try:
            self._delegate.on_belt_orientation_notified(
                belt_heading,
                is_orientation_accurate,
                [sensor_id,
                 belt_heading,
                 box_heading,
                 box_roll,
                 box_pitch,
                 accuracy,
                 mag_stat,
                 acc_stat,
                 gyr_stat,
                 fus_stat,
                 is_orientation_accurate])
        except:
            pass

    def _notify_belt_battery(self, packet):
        """Notifies the belt battery status to the delegate.

        :param bytes packet: The raw battery status data.
        """
        if (self._connection_state == BeltConnectionState.DISCONNECTED or
                self._connection_state == BeltConnectionState.DISCONNECTING):
            return
        bat_stat = int.from_bytes(
            bytes(packet[0:1]),
            byteorder='little',
            signed=False)
        charge_level = float(int.from_bytes(
            bytes(packet[1:3]),
            byteorder='little',
            signed=False)) / 256.0
        if charge_level > 100.0:
            charge_level = 100.0
        ttfe = float(int.from_bytes(
            bytes(packet[3:5]),
            byteorder='little',
            signed=False)) * 5.625
        ma = int.from_bytes(
            bytes(packet[5:7]),
            byteorder='little',
            signed=True)
        mv = int.from_bytes(
            bytes(packet[7:9]),
            byteorder='little',
            signed=False)
        try:
            self._delegate.on_belt_battery_notified(
                charge_level,
                [bat_stat, charge_level, ttfe, ma, mv])
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
        self._disconnection_event.set()
        if expected or self._connection_state == BeltConnectionState.DISCONNECTING:
            self._set_connection_state(BeltConnectionState.DISCONNECTED)
        else:
            self._set_connection_state(
                BeltConnectionState.DISCONNECTED,
                BeltConnectionError("Connection lost."))

    def on_gatt_char_notified(self, gatt_char, data):

        # Check for service discovery completed
        if self._gatt_profile is None:
            self.logger.debug("BeltController: Notification received before service discovery.")
            return

        # Check for power-off notification
        if ((gatt_char == self._gatt_profile.button_press_char and len(data) >= 5 and data[4] == BeltMode.STANDBY) or
                (gatt_char == self._gatt_profile.param_notification_char and len(data) >= 3 and data[0] == 0x01 and
                 data[1] == 0x01 and data[2] == BeltMode.STANDBY)):
            self.logger.info("BeltController: Belt switched off.")
            self._communication_interface.close()

        # Firmware information
        if gatt_char == self._gatt_profile.firmware_info_char:
            # Firmware information received
            if len(data) >= 2:
                try:
                    self._firmware_version = int.from_bytes(
                        bytes(data[:2]), byteorder='little', signed=False)
                except:
                    self.logger.error("Unable to parse firmware version.")

        # Keep alive request
        if gatt_char == self._gatt_profile.keep_alive_char:
            # Retrieve belt mode
            if len(data) >= 2:
                self._set_belt_mode(data[1])
            # Send keep-alive ACK
            self.write_gatt(self._gatt_profile.keep_alive_char, bytes([0x01]))

        # Button press notification
        if gatt_char == self._gatt_profile.button_press_char:
            if len(data) >= 5:
                self._notify_button_pressed(data[0], data[3], data[4])

        # Belt mode change
        if gatt_char == self._gatt_profile.param_notification_char:
            if len(data) >= 3 and data[0] == 0x01 and data[1] == 0x01:
                self._set_belt_mode(data[2])

        # Default intensity
        if gatt_char == self._gatt_profile.param_notification_char:
            if len(data) >= 3 and data[0] == 0x01 and data[1] == 0x02:
                self._notify_default_intensity(data[2])

        # Heading offset
        if gatt_char == self._gatt_profile.param_notification_char:
            if len(data) >= 4 and data[0] == 0x01 and data[1] == 0x03:
                self._notify_heading_offset(int.from_bytes(
                    bytes(data[2:4]), byteorder='little', signed=False))

        # BT name
        if gatt_char == self._gatt_profile.param_notification_char:
            if len(data) >= 2 and data[0] == 0x01 and data[1] == 0x04:
                self._notify_bt_name(bytearray(data[2:]))

        # Advanced parameters
        if gatt_char == self._gatt_profile.param_notification_char:
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
                elif data[1] == 0x25:
                    # Pairing requirement
                    self._notify_pairing_requirement(data[2] != 0)

        # Belt orientation
        if gatt_char == self._gatt_profile.orientation_data_char:
            if len(data) >= 16:
                self._notify_belt_orientation(data)

        # Battery status
        if gatt_char == self._gatt_profile.battery_status_char:
            if len(data) >= 9:
                self._notify_belt_battery(data)

        # Check for ACK
        if (self._ack_data is not None or self._ack_char is not None) and not self._ack_event.is_set():
            if self._is_ack(gatt_char, data):
                self.logger.log(5, "BeltController: Ack data received 0x"+data.hex())
                self._ack_rsp = data
                self._ack_data = None
                self._ack_char = None
                self._ack_event.set()

        # Inform system handlers
        for handler in self._notifications_handlers:
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
            strRep = strRep + "0" + hex(d)[2:]
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
    """Enumeration of belt modes."""

    STANDBY = 0
    WAIT = 1
    COMPASS = 2
    APP_MODE = 3
    PAUSE = 4
    CALIBRATION = 5
    CROSSING = 6



class BeltOrientationType:
    """Enumeration of orientation types."""

    BINARY_MASK = 0
    MOTOR_INDEX = 1
    ANGLE = 2
    MAGNETIC_BEARING = 3


class BeltVibrationPattern:
    """Enumeration of vibration patterns."""

    NO_VIBRATION = 0
    CONTINUOUS = 1
    SINGLE_SHORT = 2
    SINGLE_LONG = 3
    DOUBLE_SHORT = 4
    DOUBLE_LONG = 5


class BeltVibrationTimerOption:
    """Enumeration of timer option for vibration pulses commands."""

    RESET_TIMER = 0
    RESET_ON_DIFFERENT_PERIOD = 1
    KEEP_TIMER = 2


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

    def on_pairing_requirement_notified(self, pairing_required):
        """ Called when the pairing requirement has been changed or notified.

        :param pairing_required: 'True' if the pairing is required.
        """
        pass

    def on_belt_orientation_notified(self, heading, is_orientation_accurate, extra):
        """ Called when the orientation of the belt has been notified.

        :param int heading: The heading of the belt in degrees.
        :param bool is_orientation_accurate: `True` if the orientation is accurate, `False` otherwise.
        :param List extra: A list containing extra information on the orientation notification.
        """
        pass

    def on_belt_battery_notified(self, charge_level, extra):
        """ Called when the battery level of the belt is notified.
        :param float charge_level: Charge level of the belt battery in percent.
        :param List extra: Extra information on the belt battery.
        """
        pass

    def on_inaccurate_orientation_signal_state_notified(self, signal_enabled_in_app_mode,
                                                        signal_enabled_in_compass_mode):
        """ Called when the state of the inaccurate orientation signal has been notified.
        :param bool signal_enabled_in_app_mode: `True` if inaccurate orientation signal is enabled in application mode,
        `False` otherwise.
        :param bool signal_enabled_in_compass_mode: `True` if inaccurate orientation signal is enabled in compass mode,
        `False` otherwise.
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


class BeltNotificationsHandler:
    """
    Handler interface for belt debug and test.
    """

    def on_gatt_char_notified(self, gatt_char, data):
        """
        Called when a GATT notification has been received or a characteristic has been read.

        :param GattCharacteristic gatt_char: The GATT characteristic.
        :param bytes data: The data received.
        """
        pass
