# Nix Shell Usage for BLKB

## Prerequisites

- Nix package manager with `nix-shell`
- Bluetooth adapter
- Sudo access (for `rfkill`, `hciconfig`, `bluetoothctl`)

## Quick Start

### 1. Enter the Nix shell

```shell
nix-shell
```

This provides Python 3 with `dbus-python`, `pygobject3`, `bluez`, `dbus`, `glib`, `cairo`, and `gobject-introspection`.

### 2. Configure your Bluetooth adapter MAC and device name

Edit `MY_ADDRESS` and `MY_DEV_NAME` in `btk_server.py`:

```shell
# Find your Bluetooth MAC
hciconfig hci0 | awk '/BD Address: /{print $3}'
```

### 3. Unblock and power on Bluetooth

```shell
sudo rfkill unblock bluetooth
sudo bluetoothctl power on
sudo bluetoothctl discoverable on
sudo bluetoothctl pairable on
```

### 4. Pair with your target device

```shell
bluetoothctl
# Inside bluetoothctl:
scan on
# Wait for your device to appear, note its MAC
pair <DEVICE_MAC>
trust <DEVICE_MAC>
exit
```

### 5. Run the keyboard server

From inside `nix-shell`, run as root (needed for `hciconfig` and Bluetooth):

```shell
sudo -E nix-shell --run "python3 btk_server.py"
```

Or if you're already inside `nix-shell`:

```shell
sudo python3 btk_server.py
```

### 6. Connect from your target device

On your phone/tablet/computer, go to Bluetooth settings and connect to "Raspberry_Keyboard" (or whatever you set `MY_DEV_NAME` to).

## Troubleshooting

- **`hciconfig` not found**: Make sure you're inside `nix-shell` which provides `bluez`.
- **DBus errors**: Ensure `dbus` service is running (`sudo systemctl start dbus`).
- **Permission denied**: Most Bluetooth commands require root. Use `sudo`.
- **Adapter not found**: Check `rfkill list` — if soft-blocked, run `sudo rfkill unblock bluetooth`.
- **`bluetoothctl` not found**: Exit and re-enter nix-shell, or run from outside the shell where your system `bluez` is available.
