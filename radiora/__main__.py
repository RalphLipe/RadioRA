#
# Console test harness.
#
# Copyright (C) 2017 Ralph Lipe <ralph@lipe.ws>
#
# SPDX-License-Identifier:    MIT
"""\
Console interface for testing and getting status of system.
"""


from radiora import RadioRA, FeedbackCommand, MasterControlButtonPress
import argparse
from radiora.serialstub import SerialStub

import logging
logger = logging.getLogger(__name__)


def generic_feedback(feedback: FeedbackCommand):
    print("Generic feedback: {0}".format(feedback.raw_command))
    logger.info(feedback.raw_command)


def master_control_button_press(feedback: MasterControlButtonPress):
    print("Master control {0} button {1} pressed".format(feedback.master_control_number, feedback.button_number))


if __name__ == "__main__":
    parser = argparse.ArgumentParser(
        description="Control RadioRA Chronos interface via command line")
    parser.add_argument("port", type=str, help="url for serial port")
    parser.epilog = 'For a list of ports use "python3 -m serial.tools.list_ports"'
    args = parser.parse_args()

    logging.basicConfig(level=logging.DEBUG)

    port = args.port
    if port == 'TEST':
        port = SerialStub()
        logger.info("Using test port")

    with RadioRA(port) as rr:
        rr.set_feedback_observer(None, generic_feedback)
        rr.set_feedback_observer(MasterControlButtonPress, master_control_button_press)
        continue_running = True

        while continue_running:
            print("Enter command:")
            print("button_press:         b button_number ON/OFF")
            print("set_grafik_eye_scene: g zone_number scene")
            print("set_dimmer_level:     d zone_number dimmer_level [fade_time]")
            print("set_switch_level:     s zone_number ON/OFF")
            print('q - quit')
            command = input("Command? ")
            cp = command.upper().split()
            if len(cp) > 0:
                c = cp[0]
                if c == 'Q':
                    continue_running = False
                elif len(cp) < 3:
                    print("Not enough parameters")
                elif c == 'B':
                    rr.phantom_button_press(cp[1], cp[2])
                elif c == 'S':
                    rr.set_switch_level(cp[1], cp[2])
                elif c == 'G':
                    rr.set_grafik_eye_scene(cp[1], cp[2])
                elif c == 'D':
                    if len(cp) > 3:
                        rr.set_dimmer_level(cp[1], int(cp[2]), cp[3])
                    else:
                        rr.set_dimmer_level(cp[1], int(cp[2]))
                else:
                    print("Unrecognized command")
            print()
