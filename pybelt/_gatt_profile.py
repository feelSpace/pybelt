# Copyright 2020, feelSpace GmbH, <info@feelspace.de>
from typing import List


class GattCharacteristic:

    def __init__(self, uuid, declaration_attr, value_attr, configuration_attrs=None):
        """
        Gatt characteristic constructor.
        :param str uuid: Characteristic UUID.
        :param GattAttribute declaration_attr: Declaration attribute.
        :param GattAttribute value_attr: Value attribute
        :param List[GattAttribute] configuration_attrs: Configuration attributes.
        """
        self.uuid = uuid
        self.declaration_attr = declaration_attr
        self.value_attr = value_attr
        self.configuration_attrs: List[GattAttribute] = configuration_attrs

    def __eq__(self, other):
        return self.uuid == other.uuid

    def __ne__(self, other):
        return not self.__eq__(other)


class GattAttribute:

    def __init__(self, handle):
        """
        Gatt attribute constructor.
        :param int handle: Attribute handle.
        """
        # TODO Change to ble_handle AND usb_handle
        self.handle = handle

    def __eq__(self, other):
        return self.handle == other.handle

    def __ne__(self, other):
        return not self.__eq__(other)


navibelt_firmware_info_char = GattCharacteristic(
    "0000fe01-0000-1000-8000-00805f9b34fb", GattAttribute(30), GattAttribute(31))
navibelt_keep_alive_char = GattCharacteristic(
    "0000fe02-0000-1000-8000-00805f9b34fb", GattAttribute(32), GattAttribute(33), [GattAttribute(34)])
navibelt_vibration_command_char = GattCharacteristic(
    "0000fe03-0000-1000-8000-00805f9b34fb", GattAttribute(35), GattAttribute(36))
navibelt_button_press_char = GattCharacteristic(
    "0000fe04-0000-1000-8000-00805f9b34fb", GattAttribute(37), GattAttribute(38), [GattAttribute(39)])
navibelt_param_request_char = GattCharacteristic(
    "0000fe05-0000-1000-8000-00805f9b34fb", GattAttribute(40), GattAttribute(41))
navibelt_param_notification_char = GattCharacteristic(
    "0000fe06-0000-1000-8000-00805f9b34fb", GattAttribute(42), GattAttribute(43), [GattAttribute(44)])
navibelt_battery_status_char = GattCharacteristic(
    "0000fe09-0000-1000-8000-00805f9b34fb", GattAttribute(50), GattAttribute(51), [GattAttribute(52)])
navibelt_orientation_data_char = GattCharacteristic(
    "0000fe0c-0000-1000-8000-00805f9b34fb", GattAttribute(59), GattAttribute(60), [GattAttribute(61)])
navibelt_debug_input_char = GattCharacteristic(
    "0000fe13-0000-1000-8000-00805f9b34fb", GattAttribute(74), GattAttribute(75))
navibelt_debug_output_char = GattCharacteristic(
    "0000fe14-0000-1000-8000-00805f9b34fb", GattAttribute(76), GattAttribute(77), [GattAttribute(78)])

navibelt_char_uuid_dict = {
    navibelt_firmware_info_char.uuid: navibelt_firmware_info_char,
    navibelt_keep_alive_char.uuid: navibelt_keep_alive_char,
    navibelt_vibration_command_char.uuid: navibelt_vibration_command_char,
    navibelt_button_press_char.uuid: navibelt_button_press_char,
    navibelt_param_request_char.uuid: navibelt_param_request_char,
    navibelt_param_notification_char.uuid: navibelt_param_notification_char,
    navibelt_battery_status_char.uuid: navibelt_battery_status_char,
    navibelt_orientation_data_char.uuid: navibelt_orientation_data_char,
    navibelt_debug_input_char.uuid: navibelt_debug_input_char,
    navibelt_debug_output_char.uuid: navibelt_debug_output_char
}

navibelt_attr_handle_dict = {
    navibelt_firmware_info_char.declaration_attr.handle: navibelt_firmware_info_char,
    navibelt_firmware_info_char.value_attr.handle: navibelt_firmware_info_char,
    navibelt_keep_alive_char.declaration_attr.handle: navibelt_keep_alive_char,
    navibelt_keep_alive_char.value_attr.handle: navibelt_keep_alive_char,
    navibelt_keep_alive_char.configuration_attrs[0].handle: navibelt_keep_alive_char,
    navibelt_vibration_command_char.declaration_attr.handle: navibelt_vibration_command_char,
    navibelt_vibration_command_char.value_attr.handle: navibelt_vibration_command_char,
    navibelt_button_press_char.declaration_attr.handle: navibelt_button_press_char,
    navibelt_button_press_char.value_attr.handle: navibelt_button_press_char,
    navibelt_button_press_char.configuration_attrs[0].handle: navibelt_button_press_char,
    navibelt_param_request_char.declaration_attr.handle: navibelt_param_request_char,
    navibelt_param_request_char.value_attr.handle: navibelt_param_request_char,
    navibelt_param_notification_char.declaration_attr.handle: navibelt_param_notification_char,
    navibelt_param_notification_char.value_attr.handle: navibelt_param_notification_char,
    navibelt_param_notification_char.configuration_attrs[0].handle: navibelt_param_notification_char,
    navibelt_battery_status_char.declaration_attr.handle: navibelt_battery_status_char,
    navibelt_battery_status_char.value_attr.handle: navibelt_battery_status_char,
    navibelt_battery_status_char.configuration_attrs[0].handle: navibelt_battery_status_char,
    navibelt_orientation_data_char.declaration_attr.handle: navibelt_orientation_data_char,
    navibelt_orientation_data_char.value_attr.handle: navibelt_orientation_data_char,
    navibelt_orientation_data_char.configuration_attrs[0].handle: navibelt_orientation_data_char,
    navibelt_debug_input_char.declaration_attr.handle: navibelt_debug_input_char,
    navibelt_debug_input_char.value_attr.handle: navibelt_debug_input_char,
    navibelt_debug_output_char.declaration_attr.handle: navibelt_debug_output_char,
    navibelt_debug_output_char.value_attr.handle: navibelt_debug_output_char,
    navibelt_debug_output_char.configuration_attrs[0].handle: navibelt_debug_output_char
}
