# Psion-WodemSLIP

Connect a Psion running **EPOC ER5** to Wi-Fi through its serial port using a **Wodem** adapter.

**Initial release: 0.4.5** · **Maintainer: [ExPLIT](https://github.com/explit28)**

| Psion Series 5mx | Wodem serial Wi-Fi adapter |
|:---:|:---:|
| [<img src="https://upload.wikimedia.org/wikipedia/commons/4/46/Psion_Series_5MX_%282378635928%29.jpg" width="350" alt="An open Psion Series 5mx handheld running EPOC">](https://commons.wikimedia.org/wiki/File:Psion_Series_5MX_(2378635928).jpg) | [<img src="https://www.amiga-shop.net/images/product_images/popup_images/1304_0.png" width="350" alt="Wodem RS-232 to Wi-Fi adapter from Alinea Computer">](https://www.amiga-shop.net/Amiga-Hardware/Klassische-Amiga-Hardware/Wodem-WLAN-fuer-jeden-Amiga::1304.html) |

*Hardware illustrations: Psion photo by Blake Patterson, [CC BY 2.0](https://creativecommons.org/licenses/by/2.0/), via [Wikimedia Commons](https://commons.wikimedia.org/wiki/File:Psion_Series_5MX_(2378635928).jpg), displayed without image edits. Wodem product image linked from Alinea Computer's Amiga Shop; rights remain with its owner.*

## What it does

WodemSLIP provides a serial SLIP network driver, a native System Control panel applet and a `.sis` installer. The Psion sends IP packets over RS-232 to the Wodem, which connects to your wireless network. Internet applications use the resulting connection through EPOC's TCP/IP stack.

- Native **WodemSLIP** Control panel entry with the EPOC Internet icon.
- Selectable SLIP Internet connection profiles.
- Static IP, gateway and DNS configuration.
- Serial transmit flow control and receive-error recovery.
- No active diagnostic logging or growing BIN files.

The hardware setup used for development is a **Psion 5mx Pro with 32 MB RAM running EPOC ER5**. Other models and ROM versions are not yet verified.

## Hardware and useful links

You need a Psion serial cable, suitable adapters for the Wodem's RS-232 connector, a powered Wodem and a way to transfer the installer to the Psion. A null-modem adapter may be required depending on the cable wiring. The Wodem's WLAN connection must be configured separately.

- **[Wodem product page — Alinea Computer / Amiga Shop](https://www.amiga-shop.net/Amiga-Hardware/Klassische-Amiga-Hardware/Wodem-WLAN-fuer-jeden-Amiga::1304.html)** — hardware, product photographs and power options.
- **[Wodem hardware design](https://gitlab.com/rwahler1/kicad/Amiga_Wodem)** — KiCad project.
- **[ESP SLIP Router firmware](https://github.com/martin-ger/esp_slip_router)** — firmware used by the Wodem.
- **[Wodem enclosure](https://www.thingiverse.com/thing:6257091)** — 3D-printable case.
- **[Psion Series 5 / 5mx overview](https://en.wikipedia.org/wiki/Psion_Series_5)** and **[Psion photo gallery](https://commons.wikimedia.org/wiki/Category:Psion_Series_5)**.

## Installation

Use **`WodemSLIP-0.4.5.sis`** for installation. See [Releases](https://github.com/explit28/Psion-WodemSLIP/releases) for available downloads, or [build from source](#building-from-source).

1. Back up `C:\System\Libs\SLIP.NIF`, any existing WodemSLIP applet files and `C:\System\Data\TCPIP.INI`.
2. Disconnect the network and close Internet applications and the Control panel.
3. Transfer the SIS to the Psion and open it in the System file manager.
4. At the TCP/IP settings question, choose **Yes** to install the supplied defaults, or **No** to preserve an existing working `TCPIP.INI`. A template is installed in either case.
5. Close programs and perform a **normal soft reset** to unload any previously loaded driver.
6. Create a connection under **Control panel → WodemSLIP → New → Standard settings**.

Do not perform a hard reset. The installed quick-start guide is at `C:\System\WodemSLIP\QUICKSTART.TXT`. See the [installation guide](docs/INSTALL.md) for details.

## Connection settings

Create a profile named **Wodem SLIP**, with these settings:

| Profile setting | Value |
|---|---|
| Connection type | Direct |
| Manual login | Off |
| Login script / display window | Off |
| PPP extensions / callback | Off |
| Get IP address from server | Off |
| Local IP address | `192.168.240.2` |
| Automatic DNS | Off; enter the DNS server for your LAN |

**The active SLIP addresses come from `C:\System\Data\TCPIP.INI`. Entering an address in the profile alone is insufficient.** The supplied configuration includes both `[slip]` and `[slip::ecuart]` sections.

| Network setting | Supplied default |
|---|---|
| Psion address | `192.168.240.2` |
| Wodem peer and default gateway | `192.168.240.1` |
| Netmask | `255.255.255.0` |
| DNS server | `192.168.178.1` — change this for your LAN |
| Wodem management console | TCP port `7777` |

The DNS default is from a FritzBox network; it is not universal. Change `ns1` in **both** SLIP sections if your network uses another DNS server. See [the configuration file](config/TCPIP.INI).

### Serial connection

Under **Control panel → Modems**, select the direct cable entry:

- Match the Wodem's baudrate; the development setup uses **115200 baud, 8 data bits, no parity, 1 stop bit**.
- Match hardware flow control to the actual firmware and connected handshake lines. RTS/CTS requires support at both ends.
- Keep **XON/XOFF off** for this binary SLIP connection.
- Disable terminal detection if the cable does not supply the required DSR/DTR signals.

**Switch off the Psion desktop/remote link before starting SLIP.** Close raw serial terminal programs too: they compete for the same serial port.

## Test the connection

1. Connect using the **Wodem SLIP** profile.
2. In an IP utility such as NetUtils, verify that the active SLIP address is `192.168.240.2`, not `0.0.0.0`.
3. Ping `192.168.240.1` to test the local connection to the Wodem.
4. Open this small HTTP page in the Psion browser:

   **[CERN — The World Wide Web project](http://info.cern.ch/hypertext/WWW/TheProject.html)**

For Wodem management, use a **TCP/IP Telnet client** such as Mocha Telnet with host **`192.168.240.1`** and port **`7777`**. At the firmware prompt, `show` displays status and configuration. A raw serial terminal is a different connection type and cannot be used simultaneously with SLIP.

Successful networking does not make a historical Psion browser compatible with modern TLS, JavaScript or large websites. Start with simple HTTP pages. For connection problems, see [Troubleshooting](docs/TROUBLESHOOTING.md).

## Building from source

This repository contains scripts, configuration, tests and documentation. The build requires the exact EPOC ER5 SDK inputs and the external `xmakesis.pl` tool described in [Development](docs/DEVELOPMENT.md). SDK binaries are not bundled in the source repository.

```bash
python3 -m venv .venv
. .venv/bin/activate
python -m pip install -r requirements.txt
python build.py --sdk-root /path/to/Cpp --makesis /path/to/xmakesis.pl --test
```

Output: **`dist/WodemSLIP-0.4.5.sis`**.

## Documentation

- [Installation, profile setup and removal](docs/INSTALL.md)
- [Troubleshooting](docs/TROUBLESHOOTING.md)
- [Driver and configuration design](docs/DESIGN.md)
- [Build requirements and verification](docs/DEVELOPMENT.md)
- [Third-party components](THIRD_PARTY.md)

## Credits and license

Project by **ExPLIT** — GitHub: **[explit28](https://github.com/explit28)**.

Thanks to Alinea Computer for the Wodem hardware, martin-ger for ESP SLIP Router, and the authors of the EPOC SDK and build tools.

Original project scripts and documentation are covered by the [MIT license](LICENSE). Symbian SDK-derived binaries, resources, icons and third-party photographs retain their respective terms. See [THIRD_PARTY.md](THIRD_PARTY.md) for scope and redistribution information.
