# Installation

## Target and requirements

- Psion 5mx Pro, EPOC ER5. The tested device has 32 MB RAM. Other devices/ROMs are unconfirmed.
- A powered Wodem with compatible SLIP firmware and matching serial settings.
- Appropriate serial cable/adapters. Their exact pin mapping determines whether another null-modem adapter is needed.
- A way to transfer a SIS file to the Psion.
- For verification: an IP diagnostic utility and a TCP/IP Telnet client supporting a custom port. These applications are not bundled.

The TCP/IP stack, Nifman and serial framework already present on the Psion are used. No Ethernet/IrLAN package is required. Do not replace ROM components such as `Nifman.dll` or `TCPIP.PRT` with SDK versions.

## Before installation

Back up any manually installed files that the package will replace:

| Path | Purpose |
|---|---|
| `C:\System\Libs\SLIP.NIF` | Existing serial SLIP driver |
| `C:\System\Controls\WodemSLIP.ctl` | Existing new-style SLIP applet |
| `C:\System\Controls\WodemSLIP.rsc` | Its resources |
| `C:\System\Data\TCPIP.INI` | Existing active TCP/IP configuration, if present |

The earlier IrLAN-derived experimental applet has not been assigned an unambiguous legacy filename in this project. The installer therefore does not delete it automatically. Remove only positively identified legacy applet files, keeping backups and original Ethernet/IrLAN components.

## Run the installer

1. Copy `WodemSLIP-0.4.5.sis` to the Psion.
2. Close Web, email, Telnet, NetUtils and other Internet programs. Close the Control panel before installation.
3. Open the SIS in the System file manager and follow EPOC Install.
4. At **Install standard Wodem SLIP TCP/IP settings?**, choose:
   - **Yes:** install the supplied `C:\System\Data\TCPIP.INI`, replacing an existing copy.
   - **No:** keep the existing active file. The repaired driver and applet are still installed.
5. Close programs and perform a **normal soft reset**, so a previously loaded driver is released. Do not perform a hard reset or format the device.

There is no startup EXE or background setup process. Add/remove manages the SIS component.

## Installed files

| Destination | Installed |
|---|---|
| `C:\System\Libs\SLIP.NIF` | Always |
| `C:\System\Controls\WodemSLIP.ctl` | Always |
| `C:\System\Controls\WodemSLIP.rsc` | Always |
| `C:\System\Controls\WodemSLIP.aif` | Always; icon and caption |
| `C:\System\WodemSLIP\QUICKSTART.TXT` | Always |
| `C:\System\WodemSLIP\TCPIP-template.INI` | Always |
| `C:\System\Data\TCPIP.INI` | Only if Yes is selected |

The 0.4.5 package uses the unchanged 0.4.4 driver, **8572 bytes**. Its exact SHA256 and SIS checks are generated in `dist/validation.json` and `dist/SHA256SUMS` during the build.

Networking code is retained byte-for-byte from the user-tested 0.4.3. Diagnostic entry points return immediately, and allocation returns to 2,244 bytes. No trace buffer is used and no diagnostic files are written. Existing `SLIPDBG.BIN` and `WODEMDIAG.BIN` are left untouched. Keep working configuration and compare with the same CERN URL after a normal soft reset.

## Preserve or customize an existing TCPIP.INI

If you chose No, keep your existing loopback, resolver and other interface sections. Add or update the two SLIP sections using `config/TCPIP.INI` in the source or the installed template.

```ini
[slip]
address= 192.168.240.2
netmask= 255.255.255.0
dstaddr= 192.168.240.1
defgate= 192.168.240.1
ns1= 192.168.178.1
ns2= 0.0.0.0

[slip::ecuart]
address= 192.168.240.2
netmask= 255.255.255.0
dstaddr= 192.168.240.1
defgate= 192.168.240.1
ns1= 192.168.178.1
ns2= 0.0.0.0
```

`192.168.178.1` is the DNS address from the tested FritzBox LAN, not a universal Wodem default. Change both `ns1` values for another network. If the Wodem uses a different SLIP address, adjust the Psion address, destination and gateway accordingly. `slip::ecuart` is the observed interface name; verify the name on other systems rather than assuming it is identical.

The installer supplies a complete default file and does not merge an existing file automatically.

## Create a normal Internet profile

1. Open **Control panel → WodemSLIP**.
2. Choose **New → Based upon: Standard settings**. Do not import an old `.ISP` template for the first setup.
3. Name: **Wodem SLIP**. Connection type: **Direct**.
4. Account: disable **Manual login**. If the editor requires a username, use a placeholder such as `wodem`; this is not the WLAN password.
5. Addresses: disable **Get IP address from server** and enter `192.168.240.2`. Disable automatic DNS; enter your DNS address. The active driver configuration still comes from `TCPIP.INI`.
6. Login: disable **Use login script** and **Display window**.
7. Advanced: disable **PPP extensions** and **Use call back**.
8. Save with **Done**, then **OK**. Reopen WodemSLIP and verify the profile remains in its filtered list.

The profile is a standard CommDB Internet-service record with internal interface name `slip`. It should be selectable in normal Internet applications. The installer does not create the record automatically.

## Serial setup

Under **Control panel → Modems**, use the direct cable entry:

- Rate: match the Wodem; the tested setup used `115200`.
- 8 data bits, no parity, 1 stop bit.
- Flow control: match the actual firmware and connected handshake lines. RTS/CTS is not supported by every firmware build/cable. XON/XOFF should be off for this binary SLIP setup.
- Disable terminal detection if the connection does not provide the required DSR/DTR signals.

Do not infer which direction is active solely from an inline tester's TD/RD labels: adapter placement and crossed wiring affect their meaning.

For data transfer to the desktop, the Psion remote link may be on. **Switch it off before SLIP**, because both use the same serial port. A raw serial terminal must also be closed. Mocha/newTELnet must be used in TCP/IP mode, not as a second raw serial application.

## First verification

Inspect `ifconfig` in your diagnostic application after connecting:

| Value | Expected default |
|---|---|
| SLIP interface | Up |
| Address | `192.168.240.2` |
| Netmask | `255.255.255.0` |
| Destination/default gateway | `192.168.240.1` |
| DNS 1 | Your configured DNS |

Then ping the Wodem and connect a TCP/IP Telnet client to **host `192.168.240.1`, port `7777`**. On the firmware console, `show` reads the configuration/status. Do not post a WLAN password if the output includes it.

Ping to the Wodem checks the local link. Access to the LAN/Internet also needs Wodem WLAN association and the Psion's route. A successful Ping alone does not prove TCP or DNS is configured correctly.

## Uninstall and restore

1. Disconnect and close Internet programs.
2. Back up `TCPIP.INI` if it has been customized.
3. Remove **Wodem SLIP** in **Control panel → Add/remove**.
4. Close programs and perform a normal soft reset.

The package removes files it installed. If Yes was selected for the active configuration, it also removes that `TCPIP.INI`; if No was selected, the existing file is not part of this installation. Removal does not restore previous manually installed driver/configuration copies. Restore your backups if needed.

Internet profiles created in CommDB remain. Delete only the intended Wodem SLIP profile manually if it is no longer required. Do not delete the whole connection database or unrelated profiles.
