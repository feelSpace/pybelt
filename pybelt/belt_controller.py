# Copyright 2020, feelSpace GmbH, <info@feelspace.de>

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

        # TODO To be moved in diagnostic app
        # # Buffer for debug message
        # self._debug_message_buffer = ""
        # self._debug_message_last_received = 0

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
                navibelt_param_request_char,
                bytes([0x01, 0x81, mode]),
                navibelt_param_notification_char,
                b'\x01\x01')
        else:
            write_result = self.write_gatt(
                navibelt_param_request_char,
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
            self.logger.log(5, "BeltController: " + gatt_char.uuid[4:8] + " -> " + bytes_to_hexstr(data))
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

    # TODO To be moved in diagnosis app
    # def set_debug_notifications(self, enabled) -> bool:
    #     """
    #     Sets the state of debug notifications.
    #
    #     :param enabled: 'True' to enable debug notifications, 'False' to disable.
    #     :return: 'True' if the request has been sent successfully.
    #     """
    #     if self._connection_state == BeltConnectionState.DISCONNECTED:
    #         return False
    #     return self._communication_interface.set_gatt_notifications(navibelt_debug_output_char, enabled)

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
                bytes([0x01, 0x84]) + encoded_suffix) != 0:
            return False
        self.logger.debug("BeltController: Rename request sent.")
        if isinstance(self._communication_interface, BleInterface):
            self._communication_interface.close()

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
            pattern. The maximum value is 255 iterations.
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
        if (pattern_iterations is not None) and (pattern_iterations < 0 or pattern_iterations > 0xFF):
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
            navibelt_vibration_command_char,
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
                pattern_iterations,
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
        pass

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
                navibelt_vibration_command_char,
                bytes([0x30, 0xFF])) == 0
        else:
            return self.write_gatt(
                navibelt_vibration_command_char,
                bytes([0x30, channel_index & 0xFF])) == 0

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

        # TODO To be moved in diagnosis app
        # # Register to debug output
        # self.logger.debug("BeltController: Register to debug output.")
        # if not self._communication_interface.set_gatt_notifications(navibelt_debug_output_char, True):
        #     self.logger.error("BeltController: Failed to register to debug output.")
        #     return False

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

    # TODO To be removed
    # def _notify_belt_mode(self, belt_mode):
    #     """
    #     Sets the belt mode member variable and notifies the delegate of a belt mode change.
    #
    #     :param int belt_mode: The belt mode.
    #     """
    #     if (self._connection_state == BeltConnectionState.DISCONNECTED or
    #             self._connection_state == BeltConnectionState.DISCONNECTING):
    #         return
    #     if belt_mode < 0 or belt_mode > 6:
    #         self.logger.error("BeltController: Illegal mode notification argument.")
    #         return
    #     self._belt_mode = belt_mode
    #     try:
    #         self._delegate.on_belt_mode_changed(belt_mode)
    #     except:
    #         pass

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
            signed=False)
        box_heading = int.from_bytes(
            bytes(packet[3:5]),
            byteorder='little',
            signed=False)
        box_roll = int.from_bytes(
            bytes(packet[5:7]),
            byteorder='little',
            signed=False)
        box_pitch = int.from_bytes(
            bytes(packet[7:9]),
            byteorder='little',
            signed=False)
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
        if expected or self._connection_state == BeltConnectionState.DISCONNECTING:
            self._set_connection_state(BeltConnectionState.DISCONNECTED)
        else:
            self._set_connection_state(
                BeltConnectionState.DISCONNECTED,
                BeltConnectionError("Connection lost."))

    def on_gatt_char_notified(self, gatt_char, data):

        # TODO To be moved in diagnosis app using system handler
        # Process packet
        # try:
        #     self.logger.log(5, "BeltController: "+gatt_char.uuid[4:8]+" <- "+bytes_to_hexstr(data))
        # except:
        #     pass

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
                self._set_belt_mode(data[2])

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

        # Belt orientation
        if gatt_char == navibelt_orientation_data_char:
            if len(data) >= 16:
                self._notify_belt_orientation(data)

        # Battery status
        if gatt_char == navibelt_battery_status_char:
            if len(data) >= 9:
                self._notify_belt_battery(data)

        # TODO To be moved in diagnosis app using system handler
        # # Error notification
        # if gatt_char == navibelt_debug_output_char:
        #     if len(data) >= 5 and data[0] == 0xA0:
        #         error_id = int.from_bytes(bytes(data[1:5]), byteorder='little', signed=False)
        #         self.logger.error("BeltController: Belt error " + hex(error_id) + " !")

        # TODO To be moved in diagnosis app using system handler
        # # Debug message
        # if len(self._debug_message_buffer) > 0 and \
        #         time.perf_counter()-self._debug_message_last_received > DEBUG_MESSAGE_COMPLETION_TIMEOUT:
        #     # Output incomplete debug message
        #     self.logger.debug("Belt debug message: " + self._debug_message_buffer)
        #     self._debug_message_buffer = ""
        # if gatt_char == navibelt_debug_output_char:
        #     if len(data) > 1 and data[0] == 0x01:
        #         self._debug_message_buffer += decode_ascii(data[1:])
        #         self._debug_message_last_received = time.perf_counter()
        # # Output message ending with '\n'
        # eol = self._debug_message_buffer.find('\n')
        # while eol >= 0:
        #     line = self._debug_message_buffer[:eol]
        #     self._debug_message_buffer = self._debug_message_buffer[eol+1:]
        #     self.logger.debug("Belt debug message: " + line)
        #     eol = self._debug_message_buffer.find('\n')

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
