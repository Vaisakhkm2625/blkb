#!/usr/bin/python3

import sys
import socket
import time
import random
import os
import argparse

SOCKET_PATH = "/tmp/blkb.sock"


def escape_text(text):
    return text.replace('\\', '\\\\').replace('\n', '\\n')


class Client:
    def __init__(self, socket_path):
        self.sock = None
        self.socket_path = socket_path

    def connect(self):
        self.sock = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
        self.sock.connect(self.socket_path)

    def close(self):
        if self.sock:
            try:
                self.sock.close()
            except:
                pass
            self.sock = None

    def send_cmd(self, cmd):
        self.sock.sendall((cmd + "\n").encode())
        resp = self.sock.recv(4096).decode().strip()
        if resp.startswith("ERR:"):
            print(f"Error: {resp[4:]}")
            return False
        return True


def cmd_type(text, socket_path):
    c = Client(socket_path)
    try:
        c.connect()
        c.send_cmd(f"type {escape_text(text)}")
    except KeyboardInterrupt:
        pass
    finally:
        c.close()


def cmd_key(keyname, socket_path):
    c = Client(socket_path)
    try:
        c.connect()
        c.send_cmd(f"key {keyname}")
    except KeyboardInterrupt:
        pass
    finally:
        c.close()


def cmd_mod(mod, key, socket_path):
    c = Client(socket_path)
    try:
        c.connect()
        c.send_cmd(f"mod {mod} {key}")
    except KeyboardInterrupt:
        pass
    finally:
        c.close()


def cmd_file(path, delay_min, delay_max, chunk_size, socket_path):
    with open(path) as f:
        text = f.read()
    c = Client(socket_path)
    c.connect()
    try:
        total = len(text)
        for i in range(0, total, chunk_size):
            chunk = text[i:i+chunk_size]
            progress = f"[{i}/{total}]"
            print(f"  {progress} sending chunk...")
            if not c.send_cmd(f"type {escape_text(chunk)}"):
                break
            if i + chunk_size < total:
                delay_ms = random.randint(delay_min * 1000, delay_max * 1000)
                print(f"  {progress} waiting {delay_ms/1000:.1f}s...")
                if not c.send_cmd(f"delay {delay_ms}"):
                    break
        print("  Done")
    except KeyboardInterrupt:
        print("\n  Stopped")
    finally:
        c.close()


def cmd_direct(socket_path):
    print("Direct mode. Type text and press Enter to send.")
    print("  /key <name>  - send special key (enter, tab, f5, etc.)")
    print("  /mod <m> <k> - send modifier+key (ctrl r, alt f4, etc.)")
    print("  /delay <ms>  - wait")
    print("  Ctrl-C to exit")
    c = Client(socket_path)
    c.connect()
    try:
        while True:
            line = input("> ")
            if line.startswith("/"):
                parts = line[1:].strip().split(None, 2)
                if not parts:
                    continue
                sub_cmd = parts[0].lower()
                if sub_cmd == "bye" or sub_cmd == "exit":
                    break
                elif sub_cmd == "key":
                    if len(parts) >= 2:
                        c.send_cmd(f"key {parts[1]}")
                elif sub_cmd == "mod":
                    if len(parts) >= 3:
                        c.send_cmd(f"mod {parts[1]} {parts[2]}")
                elif sub_cmd == "delay":
                    if len(parts) >= 2:
                        c.send_cmd(f"delay {parts[1]}")
                else:
                    print(f"  unknown: /{sub_cmd}")
            else:
                c.send_cmd(f"type {escape_text(line)}")
    except (KeyboardInterrupt, EOFError):
        print()
    finally:
        c.close()


def main():
    parser = argparse.ArgumentParser(description="BLKB Client - send keystrokes to Bluetooth HID keyboard")
    parser.add_argument("-s", "--socket", default=SOCKET_PATH, help="Unix socket path")

    sub = parser.add_subparsers(dest="command")

    p_type = sub.add_parser("type", help="Send text as keystrokes")
    p_type.add_argument("text", help="Text to type")

    p_key = sub.add_parser("key", help="Send a special key")
    p_key.add_argument("keyname", help="Key name (enter, tab, f5, right, etc.)")

    p_mod = sub.add_parser("mod", help="Send modifier + key")
    p_mod.add_argument("mod", help="Modifier (ctrl, shift, alt, win)")
    p_mod.add_argument("key", help="Key name")

    p_file = sub.add_parser("file", help="Type a file with random delays between chunks (blocking)")
    p_file.add_argument("path", help="File path")
    p_file.add_argument("--delay-min", type=int, default=30, help="Min delay between chunks in seconds (default: 30)")
    p_file.add_argument("--delay-max", type=int, default=180, help="Max delay between chunks in seconds (default: 180)")
    p_file.add_argument("--chunk-size", type=int, default=5, help="Characters per chunk (default: 5)")

    p_direct = sub.add_parser("direct", help="Interactive mode - type text or use / commands")

    args = parser.parse_args()

    if args.command == "type":
        cmd_type(args.text, args.socket)
    elif args.command == "key":
        cmd_key(args.keyname, args.socket)
    elif args.command == "mod":
        cmd_mod(args.mod, args.key, args.socket)
    elif args.command == "file":
        cmd_file(args.path, args.delay_min, args.delay_max, args.chunk_size, args.socket)
    elif args.command == "direct":
        cmd_direct(args.socket)
    else:
        parser.print_help()


if __name__ == "__main__":
    main()
