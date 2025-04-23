# Copyright 2020, feelSpace GmbH, <info@feelspace.de>
import logging
from typing import List, Optional


class GattAttribute:

    def __init__(self, handle):
        """
        Gatt attribute constructor.
        :param Optional(int) handle: Attribute handle.
        """
        self.handle = handle

    def __eq__(self, other):
        return self.handle == other.handle

    def __ne__(self, other):
        return not self.__eq__(other)


class GattCharacteristic:

    def __init__(self, uuid, declaration_attr, value_attr, configuration_attrs=None):
        """
        Gatt characteristic constructor.
        :param str uuid: Characteristic UUID.
        :param GattAttribute declaration_attr: Declaration attribute.
        :param GattAttribute value_attr: Value attribute
        :param List[GattAttribute] configuration_attrs: Configuration attributes.
        """
        if configuration_attrs is None:
            configuration_attrs = []
        self.uuid = uuid
        self.declaration_attr = declaration_attr
        self.value_attr = value_attr
        self.configuration_attrs: List[GattAttribute] = configuration_attrs

    def __eq__(self, other):
        return self.uuid == other.uuid

    def __ne__(self, other):
        return not self.__eq__(other)

    def get_all_handles(self) -> [int]:
        """ Returns the list of all attribute handles covered by this characteristic.
        :return: the list of all attribute handles covered by this characteristic.
        """
        handles = []
        if self.declaration_attr.handle is not None:
            handles.append(self.declaration_attr.handle)
        if self.value_attr.handle is not None:
            handles.append(self.value_attr.handle)
        if self.configuration_attrs is not None:
            for attr in self.configuration_attrs:
                if attr.handle is not None:
                    handles.append(attr.handle)
        return handles


class NaviBeltGattProfile:

    def __init__(self):
        """ Constructor of a NaviBelt GATT profile.
        """

        self.logger = logging.getLogger(__name__)

        self.firmware_info_char = GattCharacteristic(
            "0000fe01-0000-1000-8000-00805f9b34fb", GattAttribute(None), GattAttribute(None))
        self.keep_alive_char = GattCharacteristic(
            "0000fe02-0000-1000-8000-00805f9b34fb", GattAttribute(None), GattAttribute(None), [GattAttribute(None)])
        self.vibration_command_char = GattCharacteristic(
            "0000fe03-0000-1000-8000-00805f9b34fb", GattAttribute(None), GattAttribute(None))
        self.button_press_char = GattCharacteristic(
            "0000fe04-0000-1000-8000-00805f9b34fb", GattAttribute(None), GattAttribute(None), [GattAttribute(None)])
        self.param_request_char = GattCharacteristic(
            "0000fe05-0000-1000-8000-00805f9b34fb", GattAttribute(None), GattAttribute(None))
        self.param_notification_char = GattCharacteristic(
            "0000fe06-0000-1000-8000-00805f9b34fb", GattAttribute(None), GattAttribute(None), [GattAttribute(None)])
        self.buzzer_led_command_char = GattCharacteristic(
            "0000fe07-0000-1000-8000-00805f9b34fb", GattAttribute(None), GattAttribute(None))
        self.battery_status_char = GattCharacteristic(
            "0000fe09-0000-1000-8000-00805f9b34fb", GattAttribute(None), GattAttribute(None), [GattAttribute(None)])
        self.sensor_command_char = GattCharacteristic(
            "0000fe0a-0000-1000-8000-00805f9b34fb", GattAttribute(None), GattAttribute(None))
        self.sensor_notification_char = GattCharacteristic(
            "0000fe0b-0000-1000-8000-00805f9b34fb", GattAttribute(None), GattAttribute(None), [GattAttribute(None)])
        self.orientation_data_char = GattCharacteristic(
            "0000fe0c-0000-1000-8000-00805f9b34fb", GattAttribute(None), GattAttribute(None), [GattAttribute(None)])
        self.debug_input_char = GattCharacteristic(
            "0000fe13-0000-1000-8000-00805f9b34fb", GattAttribute(None), GattAttribute(None))
        self.debug_output_char = GattCharacteristic(
            "0000fe14-0000-1000-8000-00805f9b34fb", GattAttribute(None), GattAttribute(None), [GattAttribute(None)])

        self.characteristics = [
            self.firmware_info_char,
            self.keep_alive_char,
            self.vibration_command_char,
            self.button_press_char,
            self.param_request_char,
            self.param_notification_char,
            self.buzzer_led_command_char,
            self.battery_status_char,
            self.sensor_command_char,
            self.sensor_notification_char,
            self.orientation_data_char,
            self.debug_input_char,
            self.debug_output_char
        ]

        self._handles_dict = {}
        for char in self.characteristics:
            for handle in char.get_all_handles():
                self._handles_dict[handle] = char

        self._char_uuid_dict = {}
        for char in self.characteristics:
            self._char_uuid_dict[char.uuid.lower()] = char

    def set_char_handles(self, char_uuid, declaration_handle, value_handle, configuration_handles=None):
        """ Sets the attributes handles for a characteristic.

        :param char_uuid: The characteristic uuid.
        :param declaration_handle: The declaration attribute handle.
        :param value_handle: The value attribute handle.
        :param configuration_handles: The configuration attribute handles.
        """
        if configuration_handles is None:
            configuration_handles = []
        characteristic = self.get_char_from_uuid(char_uuid)
        if characteristic is None:
            self.logger.error("NaviBeltGattProfile: No characteristic to set handles.")
            return
        if len(characteristic.configuration_attrs) != len(configuration_handles):
            self.logger.error("NaviBeltGattProfile: Non-matching length for configuration handles.")
            return
        # Remove previous handles from dict
        for handle in characteristic.get_all_handles():
            self._handles_dict.pop(handle, None)
        # Set new handles
        characteristic.declaration_attr.handle = declaration_handle
        characteristic.value_attr.handle = value_handle
        for idx, conf_attr in enumerate(characteristic.configuration_attrs):
            conf_attr.handle = configuration_handles[idx]
        # Adds handles to dict
        for handle in characteristic.get_all_handles():
            self._handles_dict[handle] = characteristic

    def get_char_from_handle(self, handle) -> Optional[GattCharacteristic]:
        """ Returns the GATT characteristic that contains the given attribute handle.

        :param int handle: The attribute handle.
        :return: The characteristic that contains the attribute.
        """
        if handle in self._handles_dict:
            return self._handles_dict[handle]
        return None

    def get_char_from_uuid(self, uuid) -> Optional[GattCharacteristic]:
        """ Returns the characteristic from its UUID.

        :param str uuid: The characteristic UUID.
        :return: The characteristic.
        """
        if uuid.lower() in self._char_uuid_dict:
            return self._char_uuid_dict[uuid]
        return None


_usb_gatt_profile = None


def get_usb_gatt_profile() -> NaviBeltGattProfile:
    """
    Returns the GATT profile for a USB connection (no service discovery).
    :return: The GATT profile for a USB connection.
    """
    global _usb_gatt_profile
    if _usb_gatt_profile is None:
        _usb_gatt_profile = NaviBeltGattProfile()
        # Handles initialization
        _usb_gatt_profile.set_char_handles("0000fe01-0000-1000-8000-00805f9b34fb", 30, 31)
        _usb_gatt_profile.set_char_handles("0000fe02-0000-1000-8000-00805f9b34fb", 32, 33, [34])
        _usb_gatt_profile.set_char_handles("0000fe03-0000-1000-8000-00805f9b34fb", 35, 36)
        _usb_gatt_profile.set_char_handles("0000fe04-0000-1000-8000-00805f9b34fb", 37, 38, [39])
        _usb_gatt_profile.set_char_handles("0000fe05-0000-1000-8000-00805f9b34fb", 40, 41)
        _usb_gatt_profile.set_char_handles("0000fe06-0000-1000-8000-00805f9b34fb", 42, 43, [44])
        _usb_gatt_profile.set_char_handles("0000fe07-0000-1000-8000-00805f9b34fb", 45, 46)
        _usb_gatt_profile.set_char_handles("0000fe09-0000-1000-8000-00805f9b34fb", 50, 51, [52])
        _usb_gatt_profile.set_char_handles("0000fe0a-0000-1000-8000-00805f9b34fb", 54, 55)
        _usb_gatt_profile.set_char_handles("0000fe0b-0000-1000-8000-00805f9b34fb", 56, 57, [58])
        _usb_gatt_profile.set_char_handles("0000fe0c-0000-1000-8000-00805f9b34fb", 59, 60, [61])
        _usb_gatt_profile.set_char_handles("0000fe13-0000-1000-8000-00805f9b34fb", 74, 75)
        _usb_gatt_profile.set_char_handles("0000fe14-0000-1000-8000-00805f9b34fb", 76, 77, [78])
    return _usb_gatt_profile
