#
# Library for controlling Lutron RadioRA Chronos System Bridge
#
# Copyright (C) 2017 Ralph Lipe <ralph@lipe.ws>
#
# SPDX-License-Identifier:    MIT
"""\
Library for controlling Lutron RadioRA Chronos System Bridge
"""
import serial


from serial.threaded import ReaderThread, LineReader

import logging
logger = logging.getLogger(__name__)

STATE_ON = "ON"
STATE_OFF = "OFF"
STATE_TOGGLE = "TOG"  # Only used for set_switch_level
STATE_CHANGE = "CHG"  # Only used feedback commands

# -------------- FEEDBACK COMMAND


LOCAL_ZONE_CHANGE = "LZC"
MASTER_CONTROL_BUTTON_PRESS = "MBP"
RAISE_BUTTON_PRESS = "RBP"
RAISE_BUTTON_RELEASE = "RBR"
LOWER_BUTTON_PRESS = "LBP"
LOWER_BUTTON_RELEASE = "LBR"
CORDLESS_WAKING_UP = "CWU"
CORDLESS_GOING_TO_SLEEP = "CGS"
LED_MAP = "LMP"
ZONE_MAP = "ZMP"
RADIORA_SYSTEM_MODE = "RSM"
COMMAND_UNKNOWN = "UNKNOWN"
COMMAND_PROMPT = "!"


class FeedbackCommand:
    # Any entry for attributes that starts with an _ specifies a method to call to convert the string value.  Any
    # entry that does not start with an _ but does end with '_number' will be converted to an integer.
    _PARSE_TABLE = (
        ({COMMAND_PROMPT},
            ()),
        ({LOCAL_ZONE_CHANGE},
            ('zone_number', 'state', '_set_system')),
        ({MASTER_CONTROL_BUTTON_PRESS},
            ('master_control_number', 'button_number', 'state', '_set_system')),
        ({LED_MAP},
            ('_set_led_states',)),
        ({ZONE_MAP},
            ('_set_zone_states', '_system')),
        ({RAISE_BUTTON_PRESS, RAISE_BUTTON_RELEASE, LOWER_BUTTON_PRESS, LOWER_BUTTON_RELEASE},
            ('master_control_number', 'button_number', '_set_system')),
        ({CORDLESS_WAKING_UP, CORDLESS_GOING_TO_SLEEP},
            ('master_control_number', '_set_system')),
        ({RADIORA_SYSTEM_MODE},
            ('system_mode', 'event', '_set_system'))
    )

    def __init__(self, raw_command):
        self.raw_command = raw_command
        self.parsed_args = raw_command.replace(" ", "").split(',')
        if len(self.parsed_args) > 0:
            self.command = self.parsed_args[0]
            for parse_table_item in self._PARSE_TABLE:
                if self.command in parse_table_item[0]:
                    attributes = parse_table_item[1]
                    i = 0
                    # Loop until the parsed parameters run out
                    while i+1 < len(self.parsed_args):
                        attr_name = attributes[i]
                        value = self.parsed_args[i+1]
                        if attr_name.startswith('_'):
                            f = getattr(self, attr_name)
                            f(value)
                        else:
                            if attr_name.endswith('_number'):
                                value = int(value)
                            setattr(self, attr_name, value)
                        i = i + 1
                    return
        self.command = COMMAND_UNKNOWN

    def _set_system(self, value):
        assert value[0] == 'S'
        self.system = int(value[1])

    @staticmethod
    def _parse_bitmap(value):
        result = []
        for char in value:
            if char == '1':
                val = True
            elif char == '0':
                val = False
            else:
                assert char == 'X'
                val = None
            result.append(val)
        return result

    def _set_led_states(self, value):
        self.led_states = FeedbackCommand._parse_bitmap(value)

    def _set_zone_states(self, value):
        self.zone_states = FeedbackCommand._parse_bitmap(value)


# ---------------- MAIN CLASS


class RadioRA:
    class LineReader(LineReader):
        TERMINATOR = b'\r'

        def __init__(self, notify):
            self._notify = notify
            super(RadioRA.LineReader, self).__init__()

        def handle_line(self, line):
            if self._notify:
                self._notify(FeedbackCommand(line))

    # NOTE:  Port can either be an open serial port or it can be a string.  If port is an object then baudrate
    # and use_hardware_handshaking are ignored.
    def __init__(self, port, baudrate=9600, use_hardware_handshaking=True,
                 bridged=False, notify=None):
        self.bridged = bridged
        if isinstance(port, str):
            self._ser = serial.serial_for_url(port,
                                              baudrate=baudrate,
                                              xonxoff=use_hardware_handshaking,
                                              rtscts=use_hardware_handshaking,
                                              dsrdtr=use_hardware_handshaking)
        else:
            self._ser = port
        self._thread = ReaderThread(self._ser, lambda: RadioRA.LineReader(notify))
        self._thread.start()
        transport, self._protocol = self._thread.connect()

    def stop(self):
        self._thread.stop()
        self._thread.join()

    def __enter__(self):
        """Performs no function.  Returns original SomfyRTS object (self)."""
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        """Closes the serial port and terminates the background thread if there is one."""
        self.stop()

    def _send_command(self, command, system=None):
        if system:
            assert system in (1, 2)
            command += ",S{0}".format(system)
        logger.info("Sending command: {0}".format(command))
        self._protocol.write_line(command)

    def phantom_button_press(self, button_number, state, fade_time=None, delay_switch=False, system=None):
        cmd = "BP,{0},{1}".format(button_number, state)
        if fade_time is not None:
            cmd += ",{0}".format(fade_time)
        if delay_switch:
            cmd += ",DS"
        self._send_command(cmd, system)

    def set_dimmer_level(self, zone_number, dimmer_level=100, fade_time=None, system=None):
        cmd = "SDL,{0},{1}".format(zone_number, dimmer_level)
        if fade_time is not None:
            cmd += ",{0}".format(fade_time)
        self._send_command(cmd, system)

    def set_switch_level(self, zone_number, state, delay_time=None, system=None):
        cmd = "SSL,{0},{1}".format(zone_number, state)
        if delay_time is not None:
            cmd += ",{0}".format(delay_time)
        self._send_command(cmd, system)

    def set_grafik_eye_scene(self, zone_number, scene, system=None):
        cmd = "SGS,{0},{1}".format(zone_number, scene)
        self._send_command(cmd, system)

    def security_flash_mode(self, button_number, state):
        assert state == STATE_ON or state == STATE_OFF
        cmd = "SFM,{0},{1}".format(button_number, state)
        self._send_command(cmd)

    def version_inquiry(self):
        self._send_command("VERI")

    def local_zone_change_monitoring(self, enable):
        self._send_command("LZCMON" if enable else "SZCMOFF")

    def master_control_button_press_monitoring(self, enable):
        self._send_command("MBPMON" if enable else "MBPMOFF")
