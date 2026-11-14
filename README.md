# Wodem SLIP for Psion

A repaired serial SLIP driver and a native Control panel entry for a Psion 5mx Pro running EPOC ER5, used with an ESP8266-based Wodem.

The project provides a native `.sis` installer, a normal selectable Internet profile, and the static TCP/IP configuration required by the SLIP driver. It does not use a launcher EXE to rewrite the connection database.

## Status

**0.4.5 adds the missing Control panel icon; driver unchanged from 0.4.4.** The user confirmed 0.4.3 works with CERN and other tested pages; only neverssl.com failed. This version removes active diagnostics from that exact driver while preserving its functional networking instructions and binary layout.

The three diagnostic entry points (`ram_init`, `logger`, `ram_dump`) return immediately. Object allocation is restored from 35,104 to 2,244 bytes. No RAM trace is recorded and no diagnostic files are created, overwritten or appended. Existing BIN files are left untouched. Diagnostic bodies, call wrappers and native imports remain inert in the image to avoid moving the working networking code. Only three entry instructions, the allocation-size literal and the code-checksum word differ from the user-tested 0.4.3 image.

Queue-based send flow control and serial framing/parity/overrun recovery remain byte-identical to 0.4.3. No artificial delay is added. Tests cover the exact binary difference, no-op entries, unused-buffer guards, send/receive/error paths, Stop/destruction, and selected actual device TCPIP boundary routines. This is not a complete device/kernel/UART simulation; the final no-diagnostic SIS still needs a Psion comparison test.

0.4.5 installs `C:\System\Controls\WodemSLIP.aif`, which was missing and caused the question-mark placeholder. It preserves the original EPOC Internet icon (computer, globe and handheld), adapting its UID and caption to WodemSLIP. The original icon transparency mask is retained. No driver or connection-setting changes accompany this icon fix. The icon display still needs a device check.

## Install on the Psion

1. Back up existing `SLIP.NIF`, WodemSLIP applet files and `C:\System\Data\TCPIP.INI`.
2. Transfer `WodemSLIP-0.4.5.sis` to the Psion, close Internet programs and open the SIS in the System file manager.
3. Answer the configuration question. **Yes replaces `TCPIP.INI`; No preserves it.** Choose No if you already have working settings or other custom interfaces.
4. Close programs and perform a normal soft reset. This is not a hard reset.
5. Create a profile under **Control panel → WodemSLIP**, as described in the [installation guide](docs/INSTALL.md).

A short installed guide is available at `C:\System\WodemSLIP\QUICKSTART.TXT`.

## Default network configuration

| Setting | Default |
|---|---|
| Psion SLIP address | `192.168.240.2` |
| Wodem peer / default gateway | `192.168.240.1` |
| Netmask | `255.255.255.0` |
| DNS | `192.168.178.1` — change for your LAN |
| Wodem management console | TCP port `7777` |
| Serial settings | `115200`, 8 data bits, no parity, 1 stop bit; match the Wodem |

**The active SLIP address comes from `TCPIP.INI`. Setting an address in the Internet profile alone is insufficient for this driver.** The file contains both `[slip]` and `[slip::ecuart]` sections. The original loopback and resolver defaults are retained.

Flow control and the need for a null-modem adapter depend on the actual firmware and wiring. Keep a verified working setup. RTS/CTS requires support and connected handshake lines; do not enable XON/XOFF for this binary SLIP setup.

## Verify the connection

Disable the Psion desktop/remote link before starting SLIP. Connect using the Wodem SLIP profile, then inspect the active interface with a tool such as NetUtils:

- Address should be `192.168.240.2`, not `0.0.0.0`.
- Peer/default gateway should be `192.168.240.1`.
- Ping `192.168.240.1` to check the local SLIP path.
- Use a **TCP/IP Telnet client** with host `192.168.240.1` and port `7777` for the Wodem console. A raw serial terminal cannot replace that client.

The firmware's `show` command displays its configuration and status. If the Wodem responds but the LAN does not, check its WLAN association and the Psion's default route. [Troubleshooting](docs/TROUBLESHOOTING.md) separates these cases.

## Files and removal

The installer copies the repaired driver, the new applet, the short guide and a configuration template. Installing the active `TCPIP.INI` is optional. It does not install Ethernet/IrLAN drivers or modify unrelated connection profiles.

Remove **Wodem SLIP** through **Control panel → Add/remove**. Profiles created in the connection database remain. A `TCPIP.INI` installed by this package is also removed; a configuration skipped during installation is preserved. Previous manually installed files are not automatically restored. Back up custom changes before removal. See [uninstallation](docs/INSTALL.md#uninstall-and-restore).

## Source and rebuilding

This repository contains the repair/build scripts, configuration, package description, tests and documentation. SDK binaries are local inputs and are not included in the public source archive.

```bash
python3 -m venv .venv
. .venv/bin/activate
python -m pip install -r requirements.txt
python build.py --sdk-root /path/to/Cpp --makesis /path/to/xmakesis.pl --test
```

The SIS is written to `dist/WodemSLIP-0.4.5.sis`. Exact input hashes are enforced. See [development](docs/DEVELOPMENT.md) for the SDK/tool requirements and diagnostic builds.

## Documentation

- [Installation and profile setup](docs/INSTALL.md)
- [Troubleshooting](docs/TROUBLESHOOTING.md)
- [Driver and configuration design](docs/DESIGN.md)
- [Build and verification](docs/DEVELOPMENT.md)
- [Third-party components and distribution scope](THIRD_PARTY.md)

Original project scripts and documentation use the [MIT license](LICENSE). That license does not cover Symbian SDK binaries/resources or external build tools. The source archive excludes those binaries; public redistribution rights for a compiled SIS are not established by this project.
