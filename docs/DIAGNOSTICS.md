# Historical diagnostic builds

**0.4.4 has no active diagnostics and does not generate WODEMDIAG.BIN.** The procedure below applies only to the retained 0.4.3 diagnostic reference. That build was user-confirmed to load CERN and other pages; neverssl.com remained unavailable. Do not expect the release build to produce this file.

# 0.4.3 diagnostic test

This build corrects false transmit backpressure while retaining serial receive-error recovery and the bounded RAM ring. It is not yet a confirmed fix for the browser connection failure. Use the same working profile, cable, baudrate and test page for the comparison.

## One reproduction

1. Keep a copy of the working v3 driver. Disconnect SLIP and close network applications and the Control panel.
2. Install `WodemSLIP-0.4.3-Diagnostic.sis` over the existing package. At the TCPIP.INI question choose **No** to retain working configuration. Keep the existing profile, cable arrangement and baudrate.
3. Close programs and perform a normal soft reset so the old driver is unloaded. Do not perform a hard reset.
4. Disable the desktop link and connect SLIP. Ping `192.168.240.1`.
5. Open `http://info.cern.ch/hypertext/WWW/TheProject.html`. If the browser stays at Connecting, wait about 20 seconds. Confirm whether Ping still replies.
6. **Explicitly disconnect the network connection** using NetUtils/the connection utility. Closing the browser alone may leave the connection active and does not guarantee a dump.
7. Copy `C:\WODEMDIAG.BIN` to the PC and provide it for analysis, with the Ping and browser result. Copy it before another connection test replaces it.

If the file is missing, report that rather than repeatedly reinstalling. File creation failures are contained so they do not themselves terminate networking. If the Psion crashes before Stop/destruction, the RAM diagnostics may not be saved.

## What is collected

The ring retains the last 256 checkpoints. Each 128-byte record contains sequence/stage, registers and driver state. Send-entry and IP-delivery checkpoints copy up to 64 bytes of a packet across mbuf boundaries. This permits inspection of IPv4/TCP headers, including SYN/ACK flags, sequence and acknowledgement numbers. An RX checkpoint is before the IP protocol callback; a following stage 190 shows that callback returned. Neither checkpoint proves the complete TCP/application operation succeeded.

During connection activity, diagnostics make no file calls. Stop writes at most **32,800 bytes**, replacing the previous file; destruction retries only if the current event count has not been successfully flushed. Ring initialization adds about 32 KB to the driver's object storage. Capturing RAM still consumes CPU time, so it does not reproduce the exact timing of a completely uninstrumented driver.

The file contains IP addresses and packet prefixes, which may include a short application-data prefix. The decoder displays header information without printing raw application payload bytes:

```bash
python tools/decode_ram_diagnostics.py WODEMDIAG.BIN
```

## Binary format

All scalar fields are little-endian uint32. The 32-byte header is: magic `WDR1`, format version 1, record size 128, capacity 256, total event count, next ring slot, previously flushed count, reserved. The saved header can contain the preceding flushed count because it is updated in RAM only after successful Write/Flush.

Record words 0..15 are: magic, stage, sequence, flags, saved r0, r1, r2, r3, r5, r6, lr, queued mbuf count, partial RX byte count, RX descriptor word, captured packet-byte count, self pointer. The remaining 64 bytes hold the packet prefix (zero-padded). Before wrap, the file includes only initialized records; after wrap, sequence numbers recover order. The decoder rejects inconsistent headers, lengths or sequence ranges.

Stages 120/180 capture TX/RX packet prefixes; 160/170 capture signed write/read completion status in saved r1; 200 marks Stop completion and triggers the dump. Other stages retain the v3 stage numbering described by `src/build_driver.py`.

## Interpretation limits

Framing/parity/overrun recovery has been reproduced and tested in ARM emulation. It is not known whether those errors occur in the current browser failure. Continued Ping responses during the hang make a complete reception stop an insufficient explanation on its own. The trace is intended to distinguish missing TCP responses from responses delivered to the protocol callback without the expected next transmission.
