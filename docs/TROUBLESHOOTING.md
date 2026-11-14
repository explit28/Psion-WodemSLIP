# Troubleshooting

Change one setting at a time and keep the cable arrangement that has already worked.

| Symptom | Check |
|---|---|
| Access denied opening serial port | Disable the Psion desktop/remote link and close raw serial terminal programs. |
| Connected, but SLIP address is `0.0.0.0` | Active `C:\System\Data\TCPIP.INI`, exact section names and file spelling. Profile fields alone do not configure this driver. |
| Wodem Ping works, LAN does not | Default gateway, Wodem WLAN association and LAN address; numerical Ping does not use DNS. |
| Telnet fails but Ping works | Use TCP/IP and port `7777`, not default Telnet port `23`; record the exact refusal/timeout. |
| Numerical addresses work, names do not | `ns1`/`ns2` settings and reachability of that DNS server. |
| Only one tester data LED blinks | LEDs alone do not establish direction; inspect actual writes/reads or test the wiring. |
| Framing error / `KErrCommsFrame` (-30) | Matching rate, data bits, parity, stop bits and electrical wiring; unplugging during a connection can also produce errors. |
| `KErrCommsLineFail` (-29) | Modem signal detection and handshake requirements. The repaired driver no longer forces DSR/DCD obey/fail bits. |
| `MBuf 13` | Empty packet chain; verify the repaired driver was loaded after a soft reset. The original send order uses the chain after queue ownership transfer. |
| `KERN-EXEC 3` | This is an exception, not a normal network timeout. Record the exact timing, ROM/version, installed driver hash and a diagnostic trace. |

## Avoid ambiguous tests

- Keep the desktop link off while SLIP is using the port.
- Check the active interface address before investigating WLAN or DNS.
- Configure the Psion's local address as `.2`, not the Wodem's `.1`.
- Match the baudrate at both ends; changing it only on the Psion will break communication.
- Retain a known working null-modem/cable arrangement. Another crossed adapter can undo the required data-line crossing.
- Confirm whether a test is PPP or SLIP. A PPP profile showing Connected does not prove communication with a SLIP-only peer.

## Diagnostic driver

0.4.4 has no active diagnostics. Keep the user-tested 0.4.3 diagnostic driver as a fallback if a regression needs investigation. That historical build retains bounded RAM diagnostics. Follow [the reproduction procedure](DIAGNOSTICS.md). While connecting/transferring it makes no diagnostic file calls. Explicit Stop saves `C:\WODEMDIAG.BIN` once; destruction is a fallback. Copy the file before the next session replaces it.

The file contains register/state snapshots and up to 64 bytes of selected IP packets. Addresses, ports and possibly a short application-data prefix are retained. The decoder reports headers, not raw application bytes:

```bash
python tools/decode_ram_diagnostics.py WODEMDIAG.BIN
```

The last checkpoint is observed progress, not an exception address. No successful read completion does not prove no electrical bytes reached the UART; successful write completion does not prove the Wodem received or interpreted data. The older `decode_trace.py` reads the former unbounded v3 `SLIPDBG.BIN` format only.

## Web access

Working SLIP/TCP/IP can be used by network applications. Historical Psion browsers may still fail on current HTTPS/TLS, certificates, JavaScript or page size. Test a simple HTTP service separately from modern website compatibility.
