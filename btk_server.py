#!/usr/bin/python3

from __future__ import absolute_import, print_function
import os
import sys
import dbus
import dbus.service
import dbus.mainloop.glib
import time
import socket
import struct
import errno
from gi.repository import GLib
from dbus import DBusException
from dbus.mainloop.glib import DBusGMainLoop
import logging
from logging import info, warning, error

import keymap

logging.basicConfig(level=logging.DEBUG)

BUS = None
SDP_RECORD_PATH = sys.path[0] + "/sdp_record.xml"
HID_UUID = "00001124-0000-1000-8000-00805f9b34fb"
MY_DEV_NAME = "Logitech_K380"
MY_ADDRESS = "A0:80:69:D1:B1:35"
SOCKET_PATH = "/tmp/blkb.sock"

HID_PSM_CONTROL = 17
HID_PSM_INTERRUPT = 19

HANDSHAKE_SUCCESS = bytes([0xF0])
HANDSHAKE_ERR_UNSUPPORTED = bytes([0xF3])

HID_CONTROL_NOP = 0x00
HID_CONTROL_HARD_RESET = 0x01
HID_CONTROL_SOFT_RESET = 0x02
HID_CONTROL_SUSPEND = 0x03
HID_CONTROL_EXIT_SUSPEND = 0x04
HID_CONTROL_VIRTUAL_CABLE_UNPLUG = 0x05

MODIFIER_MAP = {
    "CTRL": 0x01,
    "SHIFT": 0x02,
    "ALT": 0x04,
    "GUI": 0x08,
    "WIN": 0x08,
}

SPECIAL_KEYS = {
    "enter": "KEY_ENTER",
    "tab": "KEY_TAB",
    "backspace": "KEY_BACKSPACE",
    "space": "KEY_SPACE",
    "escape": "KEY_ESC",
    "esc": "KEY_ESC",
    "up": "KEY_UP",
    "down": "KEY_DOWN",
    "left": "KEY_LEFT",
    "right": "KEY_RIGHT",
    "home": "KEY_HOME",
    "end": "KEY_END",
    "pageup": "KEY_PAGEUP",
    "pagedown": "KEY_PAGEDOWN",
    "delete": "KEY_DELETE",
    "insert": "KEY_INSERT",
    "f1": "KEY_F1", "f2": "KEY_F2", "f3": "KEY_F3",
    "f4": "KEY_F4", "f5": "KEY_F5", "f6": "KEY_F6",
    "f7": "KEY_F7", "f8": "KEY_F8", "f9": "KEY_F9",
    "f10": "KEY_F10", "f11": "KEY_F11", "f12": "KEY_F12",
    "capslock": "KEY_CAPSLOCK",
    "numlock": "KEY_NUMLOCK",
    "scrolllock": "KEY_SCROLLLOCK",
    "pause": "KEY_PAUSE",
    "printscreen": "KEY_SYSRQ",
    "menu": "KEY_COMPOSE",
}

SHIFT_SYMBOLS = {
    '!': '1', '@': '2', '#': '3', '$': '4', '%': '5',
    '^': '6', '&': '7', '*': '8', '(': '9', ')': '0',
    '_': 'MINUS', '+': 'EQUAL', '{': 'LEFTBRACE', '}': 'RIGHTBRACE',
    '|': 'BACKSLASH', ':': 'SEMICOLON', '"': 'APOSTROPHE',
    '<': 'COMMA', '>': 'DOT', '?': 'SLASH', '~': 'GRAVE',
}

DIRECT_SYMBOLS = {
    '0': '0', '1': '1', '2': '2', '3': '3', '4': '4',
    '5': '5', '6': '6', '7': '7', '8': '8', '9': '9',
    '-': 'MINUS', '=': 'EQUAL',
    '[': 'LEFTBRACE', ']': 'RIGHTBRACE',
    '\\': 'BACKSLASH', ';': 'SEMICOLON', "'": 'APOSTROPHE',
    ',': 'COMMA', '.': 'DOT', '/': 'SLASH', '`': 'GRAVE',
    ' ': 'SPACE',
}


def char_to_key(c):
    if 'a' <= c <= 'z':
        return (0, 'KEY_' + c.upper())
    if 'A' <= c <= 'Z':
        return (0x02, 'KEY_' + c.upper())
    if c in SHIFT_SYMBOLS:
        return (0x02, 'KEY_' + SHIFT_SYMBOLS[c])
    if c in DIRECT_SYMBOLS:
        return (0, 'KEY_' + DIRECT_SYMBOLS[c])
    if c == '\n':
        return (0, 'KEY_ENTER')
    if c == '\r':
        return (0, 'KEY_ENTER')
    if c == '\t':
        return (0, 'KEY_TAB')
    return None


class AutoConfirmAgent(dbus.service.Object):
    AGENT_IFACE = "org.bluez.Agent1"

    def __init__(self, bus, path):
        dbus.service.Object.__init__(self, bus, path)
        self._bus = bus
        info("Agent object created")

    @dbus.service.method(AGENT_IFACE, in_signature="o", out_signature="s")
    def RequestPinCode(self, device):
        info(f"Agent: RequestPinCode from {device}")
        return "0000"

    @dbus.service.method(AGENT_IFACE, in_signature="o", out_signature="u")
    def RequestPasskey(self, device):
        info(f"Agent: RequestPasskey from {device}")
        return dbus.UInt32(0)

    @dbus.service.method(AGENT_IFACE, in_signature="ou", out_signature="")
    def RequestConfirmation(self, device, passkey):
        info(f"Agent: RequestConfirmation from {device} passkey={passkey}")

    @dbus.service.method(AGENT_IFACE, in_signature="ou", out_signature="")
    def DisplayPasskey(self, device, passkey):
        info(f"Agent: DisplayPasskey from {device} passkey={passkey}")

    @dbus.service.method(AGENT_IFACE, in_signature="os", out_signature="")
    def AuthorizeService(self, device, uuid):
        info(f"Agent: AuthorizeService from {device} uuid={uuid}")

    @dbus.service.method(AGENT_IFACE, in_signature="o", out_signature="")
    def RequestAuthorization(self, device):
        info(f"Agent: RequestAuthorization from {device}")

    @dbus.service.method(AGENT_IFACE, in_signature="", out_signature="")
    def Cancel(self):
        info("Agent: Cancel")

    @dbus.service.method(AGENT_IFACE, in_signature="", out_signature="")
    def Release(self):
        info("Agent: Release")


def register_agent(bus):
    info("Registering auto-confirm agent")
    agent_path = "/org/bluez/blkb_agent"
    agent = AutoConfirmAgent(bus, agent_path)
    manager = dbus.Interface(
        bus.get_object("org.bluez", "/org/bluez"),
        "org.bluez.AgentManager1"
    )
    try:
        manager.UnregisterAgent(agent_path)
    except:
        pass
    manager.RegisterAgent(agent_path, "DisplayOnly")
    manager.RequestDefaultAgent(agent_path)
    info("Agent registered as default with DisplayOnly")


class HIDDevice:
    def __init__(self):
        self.ccontrol = None
        self.cinterrupt = None
        self.errorCount = 0
        self.paired = False
        self.scancodes = {
            " ": "KEY_SPACE",
            "\u2192": "KEY_RIGHT",
            "\u21b5": "KEY_ENTER"
        }
        self.interimstate = [
            0xA1, 0x01,
            [0x01, 0, 0, 0, 0, 0, 0, 0],
            0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00
        ]

    def on_control_data(self, source, condition):
        try:
            data = source.recv(1024, socket.MSG_DONTWAIT)
            if not data:
                info("Control channel closed")
                return False
            msg_type = data[0] & 0xF0
            msg_param = data[0] & 0x0F
            info(f"HIDP msg: type=0x{msg_type:02x} param=0x{msg_param:02x}")
            if msg_type == 0x10:
                if msg_param == HID_CONTROL_VIRTUAL_CABLE_UNPLUG:
                    info("VIRTUAL_CABLE_UNPLUG")
                    return False
            elif msg_type == 0x40:
                info("GET_PROTOCOL -> Report Protocol (1)")
                source.send(bytes([0x80 | msg_param, 0x01]))
            elif msg_type == 0x50:
                info(f"SET_PROTOCOL ({data[1]})")
                source.send(bytes([0xF0, 0x00]))
            elif msg_type == 0x20:
                info("GET_REPORT -> unsupported")
                source.send(bytes([0xF0, 0x03]))
            elif msg_type == 0x30:
                info("SET_REPORT -> OK")
                source.send(bytes([0xF0, 0x00]))
            elif msg_type == 0x60:
                info("GET_IDLE -> 0")
                source.send(bytes([0x80 | msg_param, 0x00]))
            elif msg_type == 0x70:
                info("SET_IDLE -> OK")
                source.send(bytes([0xF0, 0x00]))
            elif msg_type == 0x80:
                info("HIDP DATA (input report from host)")
            else:
                info(f"unknown 0x{data[0]:02x}")
                source.send(bytes([0xF0, 0x00]))
        except socket.timeout:
            pass
        except BlockingIOError:
            pass
        except Exception as e:
            error(f"control error: {e}")
            return False
        return True

    def on_control_accept(self, listen_sock, condition):
        try:
            conn, addr = listen_sock.accept()
            info(f"Control channel accepted from {addr}")
            self.ccontrol = conn
            self.ccontrol.setblocking(False)
            GLib.io_add_watch(self.ccontrol, GLib.IO_IN, self.on_control_data)
            self.maybe_start()
        except Exception as e:
            error(f"accept control: {e}")
        return True

    def on_interrupt_accept(self, listen_sock, condition):
        try:
            conn, addr = listen_sock.accept()
            info(f"Interrupt channel accepted from {addr}")
            self.cinterrupt = conn
            self.maybe_start()
        except Exception as e:
            error(f"accept interrupt: {e}")
        return True

    def maybe_start(self):
        if self.ccontrol and self.cinterrupt:
            info("Both HID channels connected")

    def send_hid_report(self, data):
        if not self.cinterrupt:
            return
        try:
            self.cinterrupt.send(bytes(data))
            self.errorCount = 0
        except OSError as err:
            error(f"send error: {err}")
            self.errorCount += 1
            if self.errorCount > 50:
                sys.exit()

    def send_key_state(self):
        bin_str = ""
        for bit in self.interimstate[2]:
            bin_str += str(bit)
        modifier = int(bin_str, 2)
        keys = self.interimstate[4:10]
        state = [0xA1, 1, modifier, 0, 0, 0, 0, 0, 0, 0]
        for i, k in enumerate(keys):
            if i < 6:
                state[4 + i] = k
        self.send_hid_report(state)

    def send_key_down(self, modifier, scancode):
        self.interimstate[2] = [modifier, 0, 0, 0, 0, 0, 0, 0]
        self.interimstate[4] = scancode
        self.send_key_state()

    def send_key_up(self):
        self.interimstate[2] = [0, 0, 0, 0, 0, 0, 0, 0]
        self.interimstate[4] = 0
        self.send_key_state()


class CommandServer:
    def __init__(self, hid):
        self.hid = hid
        self.client = None
        self.buffer = ""
        self.queue = []
        self.busy = False
        self.typing_pos = 0
        self.typing_text = ""
        self.typing_mod = 0

    def start(self):
        if os.path.exists(SOCKET_PATH):
            os.unlink(SOCKET_PATH)
        sock = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
        sock.bind(SOCKET_PATH)
        sock.listen(1)
        sock.setblocking(False)
        GLib.io_add_watch(sock, GLib.IO_IN, self.on_accept)
        info(f"Command socket at {SOCKET_PATH}")

    def on_accept(self, listen_sock, condition):
        conn, addr = listen_sock.accept()
        info("Client connected")
        if self.client:
            self.client.close()
        self.client = conn
        self.client.setblocking(False)
        self.buffer = ""
        GLib.io_add_watch(self.client, GLib.IO_IN, self.on_data)
        return True

    def on_data(self, source, condition):
        try:
            data = source.recv(4096).decode('utf-8')
            if not data:
                self.cleanup()
                return False
            self.buffer += data
            while '\n' in self.buffer:
                line, self.buffer = self.buffer.split('\n', 1)
                line = line.strip()
                if line:
                    self.queue.append(line)
                    if not self.busy:
                        self.busy = True
                        GLib.idle_add(self.process_next)
        except:
            self.cleanup()
            return False
        return True

    def process_next(self):
        if not self.queue:
            self.busy = False
            return False
        cmd = self.queue.pop(0)
        self.execute(cmd)
        return False

    def execute(self, cmd):
        parts = cmd.split(' ', 1)
        action = parts[0]
        args = parts[1] if len(parts) > 1 else ""
        if action == "type":
            self.typing_text = args
            self.typing_pos = 0
            GLib.timeout_add(10, self.type_next)
        elif action == "key":
            key_name = args.lower()
            if key_name in SPECIAL_KEYS:
                scancode = keymap.keytable.get(SPECIAL_KEYS[key_name], 0)
                if scancode:
                    self.hid.send_key_down(0, scancode)
                    GLib.timeout_add(10, self.key_up_and_ok)
                else:
                    self.send_err(f"unknown_key:{key_name}")
                    GLib.idle_add(self.process_next)
            else:
                self.send_err(f"unknown_key:{key_name}")
                GLib.idle_add(self.process_next)
        elif action == "mod":
            sub = args.split(' ', 1)
            if len(sub) == 2:
                mod_val = MODIFIER_MAP.get(sub[0].upper(), 0)
                key_name = sub[1].lower()
                if key_name in SPECIAL_KEYS:
                    scancode = keymap.keytable.get(SPECIAL_KEYS[key_name], 0)
                else:
                    scancode = keymap.keytable.get("KEY_" + sub[1].upper(), 0)
                if scancode:
                    self.hid.send_key_down(mod_val, scancode)
                    GLib.timeout_add(10, self.key_up_and_ok)
                else:
                    self.send_err(f"unknown_key:{key_name}")
                    GLib.idle_add(self.process_next)
            else:
                self.send_err("bad_mod")
                GLib.idle_add(self.process_next)
        elif action == "delay":
            try:
                ms = int(args)
                GLib.timeout_add(ms, self.delay_done)
            except ValueError:
                self.send_err("bad_delay")
                GLib.idle_add(self.process_next)
        elif action == "bye":
            self.send_ok()
            self.cleanup()
        else:
            self.send_err(f"unknown:{action}")
            GLib.idle_add(self.process_next)

    def key_up_and_ok(self):
        self.hid.send_key_up()
        self.send_ok()
        GLib.idle_add(self.process_next)
        return False

    def type_next(self):
        if self.typing_pos >= len(self.typing_text):
            self.send_ok()
            GLib.idle_add(self.process_next)
            return False
        c = self.typing_text[self.typing_pos]
        result = char_to_key(c)
        if result is None:
            self.typing_pos += 1
            return True
        mod, key_name = result
        scancode = keymap.keytable.get(key_name, 0)
        if scancode == 0:
            self.typing_pos += 1
            return True
        self.hid.send_key_down(mod, scancode)
        GLib.timeout_add(10, self.type_up)
        self.typing_pos += 1
        return False

    def type_up(self):
        self.hid.send_key_up()
        GLib.timeout_add(10, self.type_next)
        return False

    def delay_done(self):
        self.send_ok()
        GLib.idle_add(self.process_next)
        return False

    def send_ok(self):
        if self.client:
            try:
                self.client.send(b"OK\n")
            except:
                pass

    def send_err(self, msg):
        if self.client:
            try:
                self.client.send(f"ERR:{msg}\n".encode())
            except:
                pass

    def cleanup(self):
        if self.client:
            try:
                self.client.close()
            except:
                pass
            self.client = None
        self.buffer = ""
        self.queue = []
        self.busy = False


def read_sdp_record():
    try:
        with open(SDP_RECORD_PATH, "r") as fh:
            return fh.read()
    except:
        sys.exit("Could not open the sdp record. Exiting...")


def setup_bt_device():
    info("Setting up BT device")
    bus = dbus.SystemBus()
    adapter = dbus.Interface(
        bus.get_object("org.bluez", "/org/bluez/hci0"),
        "org.freedesktop.DBus.Properties"
    )
    try:
        adapter.Set("org.bluez.Adapter1", "Alias", MY_DEV_NAME)
        adapter.Set("org.bluez.Adapter1", "Powered", dbus.Boolean(1))
        adapter.Set("org.bluez.Adapter1", "Discoverable", dbus.Boolean(1))
        adapter.Set("org.bluez.Adapter1", "Pairable", dbus.Boolean(1))
        info("Configured via D-Bus")
    except Exception as e:
        warning(f"D-Bus config failed: {e}")
        os.system("hciconfig hci0 up")
        os.system("hciconfig hci0 name " + MY_DEV_NAME)
        os.system("hciconfig hci0 piscan")
    try:
        dev_iface = dbus.Interface(
            bus.get_object("org.bluez", "/org/bluez"),
            "org.freedesktop.DBus.ObjectManager"
        )
        objects = dev_iface.GetManagedObjects()
        for path, ifaces in objects.items():
            if "org.bluez.Device1" in ifaces:
                dev = dbus.Interface(
                    bus.get_object("org.bluez", path),
                    "org.bluez.Device1"
                )
                try:
                    dev.Disconnect()
                except:
                    pass
                try:
                    adapter_iface = dbus.Interface(
                        bus.get_object("org.bluez", "/org/bluez/hci0"),
                        "org.bluez.Adapter1"
                    )
                    adapter_iface.RemoveDevice(dbus.ObjectPath(path))
                    info(f"Removed stale device: {path}")
                except:
                    pass
    except:
        pass
    info("BT device ready")


def register_sdp_record(bus):
    info("Registering HID SDP record (no AutoConnect)")
    service_record = read_sdp_record()
    opts = {
        "ServiceRecord": service_record,
        "Role": "server",
        "RequireAuthentication": False,
        "RequireAuthorization": False,
    }
    manager = dbus.Interface(
        bus.get_object("org.bluez", "/org/bluez"),
        "org.bluez.ProfileManager1"
    )
    dummy_path = "/org/bluez/blkb_sdp"
    try:
        manager.UnregisterProfile(dummy_path)
    except:
        pass
    manager.RegisterProfile(dummy_path, HID_UUID, opts)
    info("SDP record registered")


def main():
    DBusGMainLoop(set_as_default=True)
    bus = dbus.SystemBus()

    setup_bt_device()
    register_agent(bus)
    register_sdp_record(bus)

    info("Setting device class to keyboard")
    os.system("hciconfig hci0 class 0x0025C0 2>/dev/null")
    os.system("hciconfig hci0 class 2>/dev/null")

    hid = HIDDevice()

    control_listen = socket.socket(socket.AF_BLUETOOTH, socket.SOCK_SEQPACKET, socket.BTPROTO_L2CAP)
    control_listen.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    control_listen.bind((MY_ADDRESS, HID_PSM_CONTROL))
    control_listen.listen(1)
    GLib.io_add_watch(control_listen, GLib.IO_IN, hid.on_control_accept)
    info("Listening on HID Control PSM 17")

    interrupt_listen = socket.socket(socket.AF_BLUETOOTH, socket.SOCK_SEQPACKET, socket.BTPROTO_L2CAP)
    interrupt_listen.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    interrupt_listen.bind((MY_ADDRESS, HID_PSM_INTERRUPT))
    interrupt_listen.listen(1)
    GLib.io_add_watch(interrupt_listen, GLib.IO_IN, hid.on_interrupt_accept)
    info("Listening on HID Interrupt PSM 19")

    cmd_server = CommandServer(hid)
    cmd_server.start()

    info("Waiting for HID connection from host...")

    loop = GLib.MainLoop()
    try:
        loop.run()
    except KeyboardInterrupt:
        if os.path.exists(SOCKET_PATH):
            os.unlink(SOCKET_PATH)
        sys.exit()


if __name__ == "__main__":
    main()
