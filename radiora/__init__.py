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
import threading


from serial.threaded import ReaderThread, LineReader

import logging
logger = logging.getLogger(__name__)

STATE_ON = "ON"
STATE_OFF = "OFF"
STATE_TOGGLE = "TOG"  # Only used for set_switch_level
STATE_CHANGE = "CHG"  # Only used feedback commands

# -------------- FEEDBACK COMMAND


class FeedbackCommand:
    COMMAND = None
    REQUIRED_PARAMS = 0

    def __init__(self, raw_command, parsed_args):
        self.raw_command = raw_command
        self.parsed_args = parsed_args
        self.command = parsed_args[0] if len(parsed_args) > 0 else ''

    # Used by derived classes
#    @staticmethod
#    def _parse_bitmap(value) -> []:
#        result = []
#        for char in value:
#            if char == '1':
#                val = True
#            elif char == '0':
#                val = False
#            else:
#                assert char == 'X'
#                val = None
#            result.append(val)
#        return result


class UnknownFeedback(FeedbackCommand):
    def __init__(self, raw_command, parsed_args):
        FeedbackCommand.__init__(self, raw_command, parsed_args)


class Prompt(FeedbackCommand):
    COMMAND = '!'
    REQUIRED_PARAMS = 0

    def __init__(self, raw_command, parsed_args):
        FeedbackCommand.__init__(self, raw_command, parsed_args)


class _SystemFeedback(FeedbackCommand):
    def __init__(self, raw_command, parsed_args, system_arg_index):
        FeedbackCommand.__init__(self, raw_command, parsed_args)
        if len(parsed_args) > system_arg_index:
            assert parsed_args[system_arg_index][0] == 'S'
            self.system = int(parsed_args[system_arg_index][1])
        else:
            self.system = None

    @property
    def system_number(self) -> int:
        return 1 if (not hasattr(self, 'system')) else self.system


class LocalZoneChange(_SystemFeedback):
    COMMAND = "LZC"
    REQUIRED_PARAMS = 2

    def __init__(self, raw_command, parsed_args):
        _SystemFeedback.__init__(self, raw_command, parsed_args, 3)
        self.zone_number = int(parsed_args[1])
        self.state = parsed_args[2]


class _MasterControlFeedback(_SystemFeedback):
    REQUIRED_PARAMS = 1

    def __init__(self, raw_command, parsed_args, system_arg_index=2):
        _SystemFeedback.__init__(self, raw_command, parsed_args, system_arg_index)
        self.master_control_number = int(parsed_args[1])


class _MasterControlButtonFeedback(_MasterControlFeedback):
    REQUIRED_PARAMS = 2

    def __init__(self, raw_command, parsed_args, system_arg_index=3):
        _MasterControlFeedback.__init__(self, raw_command, parsed_args, system_arg_index)
        self.button_number = int(parsed_args[2])


class MasterControlButtonPress(_MasterControlButtonFeedback):
    COMMAND = "MBP"
    REQUIRED_PARAMS = 3

    def __init__(self, raw_command, parsed_args):
        _MasterControlButtonFeedback.__init__(self, raw_command, parsed_args, 4)
        self.state = parsed_args[3]


class RaiseButtonPress(_MasterControlButtonFeedback):
    COMMAND = "RBP"


class RaiseButtonRelease(_MasterControlButtonFeedback):
    COMMAND = "RBR"


class LowerButtonPress(_MasterControlButtonFeedback):
    COMMAND = "LBP"


class LowerButtonRelease(_MasterControlButtonFeedback):
    COMMAND = "LBR"


FEEDBACK_CLASSES = (
    Prompt,
    LocalZoneChange,
    MasterControlButtonPress,
    RaiseButtonPress,
    RaiseButtonRelease,
    LowerButtonPress,
    LowerButtonRelease
)


def create_feedback_command(raw_command) -> FeedbackCommand:
    parsed_args = raw_command.replace(" ", "").split(',')
    if len(parsed_args) > 0:
        command_text = parsed_args[0]
        for feedback_class in FEEDBACK_CLASSES:
            if feedback_class.COMMAND == command_text and feedback_class.REQUIRED_PARAMS <= len(parsed_args):
                return feedback_class(raw_command, parsed_args)
    return UnknownFeedback(raw_command, parsed_args)


# ---------------- MAIN CLASS

class RadioRA:
    class FeedbackQueue:
        def __init__(self, use_thread):
            self._lock = threading.Lock()
            self._check_queue = threading.Event()
            self._queue = []
            self._continue_running = True
            self._feedback_functions = {}
            if use_thread:
                self._thread = threading.Thread(target=lambda: self._thread_process_queue())
                self._thread.start()
            else:
                self._thread = None

        def _thread_process_queue(self):
            while self._process_queue():
                self._check_queue.wait()

        # Returns True if all commands have been processed.  Returns False if the the Stop method has been called
        # and the thread should exit.
        def _process_queue(self):
            self._lock.acquire()
            while self._continue_running and len(self._queue) > 0:
                feedback = self._queue.pop(0)
                feedback_function = None
                if feedback.__class__ in self._feedback_functions:
                    feedback_function = self._feedback_functions[feedback.__class__]
                elif FeedbackCommand in self._feedback_functions:
                    feedback_function = self._feedback_functions[FeedbackCommand]
                if feedback_function is not None:
                    self._lock.release()
                    feedback_function(feedback)
                    self._lock.acquire()
            self._check_queue.clear()
            self._lock.release()
            return self._continue_running

        def report_feedback(self, feedback):
            with self._lock:
                self._queue.append(feedback)
                self._check_queue.set()
            if self._thread is None:
                self._process_queue()

        def set_feedback_observer(self, feedback_class, feedback_function):
            if feedback_class is None:
                feedback_class = FeedbackCommand
            with self._lock:
                self._feedback_functions[feedback_class] = feedback_function

        def stop(self):
            """Shuts down worker thread"""
            assert self._continue_running
            with self._lock:
                self._continue_running = False
                self._queue = []
                self._check_queue.set()
            if self._thread is not None:
                self._thread.join()

    class LineReader(LineReader):
        TERMINATOR = b'\r'

        def __init__(self, feedback_queue):
            self._feedback_queue = feedback_queue
            super(RadioRA.LineReader, self).__init__()

        def handle_line(self, line):
            self._feedback_queue.report_feedback(create_feedback_command(line))

    # NOTE:  Port can either be an open serial port or it can be a string.  If port is an object then baudrate
    # and use_hardware_handshaking are ignored.
    def __init__(self, port, baudrate=9600, use_hardware_handshaking=True, bridged=False, feedback_thread=True):
        self.bridged = bridged
        if isinstance(port, str):
            self._ser = serial.serial_for_url(port,
                                              baudrate=baudrate,
                                              xonxoff=use_hardware_handshaking,
                                              rtscts=use_hardware_handshaking,
                                              dsrdtr=use_hardware_handshaking)
        else:
            self._ser = port
        self._feedback_queue = RadioRA.FeedbackQueue(feedback_thread)
        self._reader_thread = ReaderThread(self._ser, lambda: RadioRA.LineReader(self._feedback_queue))
        self._reader_thread.start()
        transport, self._protocol = self._reader_thread.connect()

    def stop(self):
        self._reader_thread.stop()
        self._reader_thread.join()
        self._feedback_queue.stop()

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

    def set_feedback_observer(self, class_type, feedback_function):
        self._feedback_queue.set_feedback_observer(class_type, feedback_function)

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
