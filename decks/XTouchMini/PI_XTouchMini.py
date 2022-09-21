if __name__ != "__main__":
    import XPLMPlanes
    import XPLMProcessing
    import XPLMDataAccess
    import XPLMUtilities
    from XPPython3 import xp
    import json
import mido
import os
import time

from typing import List, Tuple, Dict, Any


class PythonInterface:
    def __init__(self) -> None:
        self.__name = "X-TOUCH-MINI - 1.0.0"
        self.__sig = "behringer.xtouch-mini"
        self.__desc = "Plugin for Behringers X-TOUCH MINI"
        self.__input_device_name = ""
        self.__output_device_name = ""
        self.__input_device: mido.BaseInput = None
        self.__output_device: mido.BaseOutput = None
        self.__encoder_cmd_mappings: Dict[str, List[XPLMUtilities.XPLMCommandRef]] = dict()
        self.__button_cmd_mappings: Dict[str, XPLMUtilities.XPLMCommandRef] = dict()
        self.__regular_callback_time: float = 0.0
        self.__input_dataref_mappings: List[Dict[int, int]] = list()
        self.__last_output_states: List[Dict[int, Any]] = list()
        self.__msgs_to_send_after_button_release: List[mido.Message] = list()
        self.__msgs_to_send_after_layer_change: List[mido.Message] = list()
        self.__button_pressed: bool = False
        self.__current_layer: int = 0
        self.__cmd_ref = None
        self.__cmd_refCon = []
        self.__debug_output = False

    def XPluginStart(self) -> Tuple[str, str, str]:
        # register command callback to toggle the layers of the XTouchMini
        self.__cmd_ref = XPLMUtilities.XPLMCreateCommand("behringer/xtouch_mini/toggle_layer", "Toggle the active layer of the X-Touch Mini")
        XPLMUtilities.XPLMRegisterCommandHandler(self.__cmd_ref, self.command_toggle_layer_callback, 1, self.__cmd_refCon)
        return self.__name, self.__sig, self.__desc

    def XPluginStop(self) -> None:
        pass

    def XPluginEnable(self) -> int:
        # register flight loop to load the configuration (plane specific)
        XPLMProcessing.XPLMRegisterFlightLoopCallback(self.InitialFlightLoop_f, -1, [])
        return 1

    def XPluginDisable(self) -> None:
        if self.__input_device:
            self.__input_device.close()
        if self.__output_device:
            self.__output_device.close()
        XPLMUtilities.XPLMUnregisterCommandHandler(self.__cmd_ref, self.command_toggle_layer_callback, 1, self.__cmd_refCon)

    def XPluginReceiveMessage(self, inFromWho, inMessage, inParam) -> None:
        pass

    def command_toggle_layer_callback(self, commandRef, phase, refCon) -> int:
        if ((self.__output_device is not None) and (phase == 0)):
            # toggle the layer in command_begin
            self.__current_layer = (self.__current_layer + 1) % 2
            # activate correct layer
            self.send_mido_message(mido.Message('program_change', channel=0, program=self.__current_layer))
            if (len(self.__msgs_to_send_after_layer_change) > 0):
                for msg in self.__msgs_to_send_after_layer_change:
                    self.send_mido_message(msg)
                self.__msgs_to_send_after_layer_change.clear()
        # no need for XPlane to handle this command -> return 0
        return 0

    def mido_input_callback(self, msg: mido.Message) -> None:
        received = f'{msg.type} channel={msg.channel} control={msg.control}'
        if (self.__debug_output):
            xp.log(f'INFO: Received {str(msg)}')
        if (received in self.__encoder_cmd_mappings):
            # assume down direction
            amount = 64 - msg.value
            cmd_id = self.__encoder_cmd_mappings[received][0]
            # check for up direction
            if (msg.value > 64):
                amount = msg.value - 64
                cmd_id = self.__encoder_cmd_mappings[received][1]
            # register flight callback to actually send the command, otherwise X-Plane will crash!
            XPLMProcessing.XPLMRegisterFlightLoopCallback(self.CommandFlightLoop_f, -1, (cmd_id, amount))
        elif (received in self.__button_cmd_mappings):
            # send key press when button has been pressed, when it is released check for light changes (otherwise the buttons
            # won't light if the key has been pressed too long!)
            if (msg.value != 0):
                self.__button_pressed = True
                amount = 1
                cmd_id = self.__button_cmd_mappings[received]
                # register flight callback to actually send the command, otherwise X-Plane will crash!
                XPLMProcessing.XPLMRegisterFlightLoopCallback(self.CommandFlightLoop_f, -1, (cmd_id, amount))
            else:
                self.__button_pressed = False
                if (len(self.__msgs_to_send_after_button_release) > 0):
                    for msg in self.__msgs_to_send_after_button_release:
                        self.send_mido_message(msg)
                    self.__msgs_to_send_after_button_release.clear()

    def RegularFlightLoop_f(self, sinceLastCAll, sinceLastFlightLoop, counter, refCon) -> float:
        for layer in range(len(self.__input_dataref_mappings)):
            for dataref_id in self.__input_dataref_mappings[layer].keys():
                data_type = XPLMDataAccess.XPLMGetDataRefTypes(dataref_id)
                cur_val: Any = None
                if (data_type & XPLMDataAccess.xplmType_Int):
                    cur_val = XPLMDataAccess.XPLMGetDatai(dataref_id)
                elif (data_type & XPLMDataAccess.xplmType_Float):
                    cur_val = XPLMDataAccess.XPLMGetDataf(dataref_id)
                elif (data_type & XPLMDataAccess.xplmType_Double):
                    cur_val = XPLMDataAccess.XPLMGetDatad(dataref_id)
                else:
                    xp.log(f'WARNING: Datarefs of type {data_type} are not supported!')
                if (cur_val is not None):
                    if (self.__last_output_states[layer][dataref_id] != cur_val):
                        # assume button off
                        velocity = 0
                        if (bool(cur_val)):
                            velocity = 1
                        msg = mido.Message('note_on', note=self.__input_dataref_mappings[layer][dataref_id], velocity=velocity)
                        # check if the button is on the currently active layer, if not save the message for the layer toggling
                        if (self.__current_layer == layer):
                            # do not send the message directly if a button is pressed because the pressed button won't light                            
                            if (self.__button_pressed):
                                self.__msgs_to_send_after_button_release.append(msg)
                            else:
                                self.send_mido_message(msg)
                        else:
                            self.__msgs_to_send_after_layer_change.append(msg)
                        self.__last_output_states[layer][dataref_id] = cur_val
        return self.__regular_callback_time

    def CommandFlightLoop_f(self, sinceLastCall, sinceLastFlightLoop, counter, refCon) -> int:
        (cmd_id, amount) = refCon
        for i in range(amount):
            XPLMUtilities.XPLMCommandOnce(cmd_id)
        # disable flight loop callback again as all button actions have been submitted
        return 0

    def InitialFlightLoop_f(self, sinceLastCall, sinceLastFlightLoop, counter, refCon) -> int:
        (model, path) = XPLMPlanes.XPLMGetNthAircraftModel(0)
        slash_pos = path.rfind("/")
        bslash_pos = path.rfind("\\")
        delim_pos = slash_pos
        if ((slash_pos == -1) or (bslash_pos > slash_pos)):
            delim_pos = bslash_pos
        cfg_file = f'{path[:delim_pos]}/xtouch_config.jsonc'
        if os.path.exists(cfg_file):
            if self.read_config_file_and_find_ids(cfg_file):
                try:
                    self.__input_device = mido.open_input(self.__input_device_name, callback=self.mido_input_callback)
                except Exception as e:
                    xp.log(f'ERROR: Cannot open device "{self.__input_device_name}" as input: {e}')
                try:
                    self.__output_device = mido.open_output(self.__output_device_name)
                except Exception as e:
                    xp.log(f'ERROR: Cannot open device "{self.__output_device_name}" as output: {e}')
                if (self.__input_device and self.__output_device):
                    # switch off all buttons (first layer B, then layer A) - encoder rings will be lighted by the device itself again, so no use switching them off...
                    for layer in range(1, -1, -1):
                        self.send_mido_message(mido.Message('program_change', channel=0, program=layer))
                        for i in range(16):
                            self.send_mido_message(mido.Message('note_off', note=i, velocity=0))
                    # if output device is needed (that means datarefs have been found) register a regular flight loop to enable checking for changed datarefs
                    if (len(self.__input_dataref_mappings) > 0):
                        XPLMProcessing.XPLMRegisterFlightLoopCallback(self.RegularFlightLoop_f, self.__regular_callback_time, [])
        else:
            xp.log('INFO: No config file found -> nothing to do')
        # disable flight loop callback as config file has been parsed and devices have been opened
        return 0

    def read_config_file_and_find_ids(self, config_file: str) -> bool:
        xp.log(f'INFO: Opening "{config_file}"')
        with open(config_file, 'r') as f:
            try:
                configs = json.load(f)
                self.__input_device_name = configs["Devices"]["Input"]
                self.__output_device_name = configs["Devices"]["Output"]
                self.__regular_callback_time = configs["General_Settings"]["Callback_Frequency"]
                self.__debug_output = configs["General_Settings"]["Debug_Output"]
                key = "Encoders"
                if (key in configs.keys()):
                    for input_message in configs[key].keys():
                        cmd_ids: List[XPLMUtilities.XPLMCommandRef] = list()
                        for cmd_ref in configs[key][input_message]:
                            cmd_id = XPLMUtilities.XPLMFindCommand(cmd_ref)
                            if (cmd_id is not None):
                                cmd_ids.append(cmd_id)
                            else:
                                xp.log(f'WARNING: No command "{cmd_ref}" found, please check the name')
                        if (len(cmd_ids) == 2):
                            self.__encoder_cmd_mappings[input_message] = cmd_ids
                keys = ["Encoder_Buttons", "Buttons"]
                for key in keys:
                    if (key in configs.keys()):
                        for input_message in configs[key].keys():
                            cmd_id = XPLMUtilities.XPLMFindCommand(configs[key][input_message])
                            if (cmd_id is not None):
                                self.__button_cmd_mappings[input_message] = cmd_id
                            else:
                                xp.log(f'WARNING: No command "{cmd_ref}" found, please check the name')
                key = "Lights"
                if (key in configs.keys()):
                    layers = ["A", "B"]
                    for layer in layers:
                        if (layer in configs[key].keys()):
                            layer_dict: Dict[int, int] = dict()
                            last_value_dict: Dict[int, int] = dict()
                            for dataref in configs[key][layer]:
                                id = XPLMDataAccess.XPLMFindDataRef(dataref)
                                if (id is not None):
                                    layer_dict[id] = configs[key][layer][dataref]
                                    last_value_dict[id] = 0
                                else:
                                    xp.log(f'WARNING: No dataref "{dataref}" found, please check the name')
                            self.__input_dataref_mappings.append(layer_dict)
                            self.__last_output_states.append(last_value_dict)
                if (self.__debug_output):
                    xp.log(f'INFO: Found {len(self.__encoder_cmd_mappings.keys())} encoder commands')
                    xp.log(f'INFO: Found {len(self.__button_cmd_mappings.keys())} button commands')
                    dataref_cnt = 0
                    for i in range(len(self.__input_dataref_mappings)):
                        dataref_cnt += len(self.__input_dataref_mappings[i].keys())
                    xp.log(f'INFO: Found {dataref_cnt} button datarefs')
                return True
            except (Exception, KeyError) as e:
                xp.log(f'ERROR: Your config file does not have the required format, please check: {e}')
                return False

    def send_mido_message(self, msg: mido.Message) -> None:
        if (self.__debug_output):
            xp.log(f'INFO: Sending "{str(msg)}"')
        self.__output_device.send(msg)


#################################################################################
def find_midi_devices() -> Tuple[str, str]:
    input_names: List[str] = list()
    output_names: List[str] = list()

    i: int = 0
    for name in mido.get_input_names():
        print(f'{i}: {name}')
        input_names.append(name)
        i += 1
    d_i = int(input('Select MIDI device for input: '))

    i = 0
    for name in mido.get_output_names():
        print(f'{i}: {name}')
        output_names.append(name)
        i += 1
    d_o = int(input('Select MIDI device for output: '))
    return (input_names[d_i], output_names[d_o])


def input_test_callback(msg: mido.Message) -> None:
    print(msg)


def run_test_input(name: str) -> None:
    try:
        print(f'Opening MIDI device: "{name}"')
        m = mido.open_input(name, callback=input_test_callback)
        print('Device opened for testing. Use ctrl-c to quit.')
        while True:
            time.sleep(10)
    except Exception as e:
        print(e)
    except KeyboardInterrupt:
        m.close()


def output_test_input_callback(msg: mido.Message, m_output: mido.ports.BaseOutput, button_states: Dict[int, bool]) -> None:
    # called when a button was pressed
    print(msg)
    msg_dict = msg.dict()
    if (msg_dict['type'] == 'control_change'):
        if (msg_dict['value'] == 0):
            button = msg_dict['control']
            if button < len(button_states.keys()):
                velocity = 1
                if button_states[button]:
                    velocity = 0
                out_msg = mido.Message('note_on', note=button, velocity=velocity)
                print(f'Sending {out_msg}')
                m_output.send(out_msg)
                if (velocity == 0):
                    button_states[button] = False
                else:
                    button_states[button] = True


def run_test_output(name_input: str, name_output: str) -> None:
    button_states: Dict[int, bool] = dict()
    # init all buttons to switched off
    for i in range(32):
        button_states[i] = False
    try:
        print(f'Opening MIDI device "{name_output}" for output')
        m_output = mido.open_output(name_output)
        print(f'Opening MIDI device "{name_input}" for input')
        input_callback_lambda = lambda x: output_test_input_callback(x, m_output, button_states)
        m_input = mido.open_input(name_input, callback=input_callback_lambda)
        print('Devices opened. Use ctrl-c to quit.')
        while True:
            time.sleep(10)
    except Exception as e:
        print(e)
    except KeyboardInterrupt:
        m_input.close()


if (__name__ == "__main__"):
    import argparse

    parser = argparse.ArgumentParser(description='Interface to MIDI devices')
    parser.add_argument('-ti', '--test_input',  action="store_true",    dest='test_input',  help='start test mode for input device')
    parser.add_argument('-to', '--test_output', action='store_true',    dest='test_output', help='start test mode for output device')
    parser.add_argument('-mi', '--midi_input',  action='store',         dest='midi_input',  help='ID of midi device to use for input',      required=False, type=str, default='')
    parser.add_argument('-mo', '--midi_output', action='store',         dest='midi_output', help='ID of midi device to use for ooutput',    required=False, type=str, default='')

    args = parser.parse_args()

    name_input = args.midi_input
    name_output = args.midi_output
    if ((args.midi_input == '') or (args.midi_output == '')):
        (name_input, name_output) = find_midi_devices()

    if args.test_input:
        run_test_input(name_input)
    elif args.test_output:
        run_test_output(name_input, name_output)
    else:
        print("Next time select the test to execute by either passing --test_input/-ti or --test_output/-to")
