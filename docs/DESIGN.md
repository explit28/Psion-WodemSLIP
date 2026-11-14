# Design and repairs

## Components

| Component | Responsibility |
|---|---|
| `SLIP.NIF` | EPOC network-interface driver: serial framing, packet ownership and interface callbacks |
| `WodemSLIP.ctl` / `.rsc` | Stock Internet editor adapted to create/list `IfName=slip` profiles |
| `TCPIP.INI` | Static interface addresses, peer, gateway and DNS |
| Native SIS installer | Copies files and offers optional installation of default TCP/IP settings |

The existing ROM socket server, TCP/IP stack, serial framework and connection database are reused. The applet is not a network implementation. There is no connection-launcher EXE.

## Applet icon (0.4.5)

The missing AIF caused EPOC to display the default question-mark icon. The package now installs `WodemSLIP.aif` next to its CTL/RSC. It retains the original 48x48 Internet icon and transparency mask byte-for-byte. UID3 and UID CRC match the new applet identity, while the English caption becomes WodemSLIP; the footer offset is updated for the caption length. Network driver bytes remain unchanged from 0.4.4.

## No-diagnostic derivative (0.4.4)

The exact user-confirmed 0.4.3 image is reproduced and SHA256-guarded before patching. `src/disable_043_diagnostics.py` replaces three entry instructions (`ram_init`, `logger`, `ram_dump`) with `MOV pc,lr`, restores the object allocation literal at RVA 0xe84 from 0x8920 to 0x8c4, then updates the code checksum. These five words are the only allowed changes.

Every functional networking instruction, including queue-based backpressure and receive-error recovery, remains byte-identical. Imports, exports, relocations, image size, call wrappers and code offsets are retained. Diagnostic bodies/imports are unreachable through the disabled entries and remain inert to preserve layout. No trace data is recorded; Stop/destruction do not write a file. No accesses to the removed object extension are permitted by the exercised-path canary tests. Existing log files are not deleted. The absence of instrumentation can still change execution time, so a device comparison remains required.

The following sections describe the retained repairs and the historical diagnostic implementation. RAM tracing below is not active in the 0.4.4 SIS.

## Queue-based transmit flow control (0.4.3)

The prior Send-return bridge set the blocked bit whenever a UART write was active and returned zero via the original bit-4 test. Even a single accepted SYN therefore caused the native TCPIP Send wrapper (device image RVA 0xa7a8) to mark the interface blocked. Completion cleared that state and called StartSending, including native manager/state transitions. This false block/resume has been reproduced against the inspected device TCPIP code; full TCP/browser behavior is not emulated.

The corrected bridge examines queued data mbufs (self+0x49c) against the high-water mark (self+0x4a0), explicitly initialized to 8 during construction. Above the mark it sets blocked bit 2 and returns 0. Otherwise it returns 1 unless a prior block is still awaiting the encoder's capacity notification. UART write-in-progress bit 4 no longer determines the Send result. The existing encoder path clears blocked state and notifies once the count falls to or below the mark; idle completion remains a fallback. Packets are queued/owned exactly once even when returning blocked.

The device trace's retained SYN sequence rises by 64,000 each time, matching the TCPIP sequence allocator increment. This is evidence of regenerated connection requests, not proof of which full-stack call chain produced them. The new build is a focused correction for the confirmed false backpressure, with an on-device comparison still required.

## Bounded RAM diagnostic build

0.4.2 uses the same generator for the v3 functional repairs, but replaces synchronous checkpoint file I/O with an in-object ring of 256 records, each 128 bytes. Object allocation increases from 0x8c4 to 0x8920 bytes. Constructor/start initialization clears and identifies the ring. During ordinary connection events, the logger only touches RAM. Packet checkpoints copy at most 64 IP bytes across mbuf boundaries before ownership is transferred or the incoming packet is processed.

Stop records stage 200, then writes a 32-byte header and the retained ring records through RFile::Replace. Destruction is a fallback; the last successfully dumped event count prevents duplicate writes. The file is bounded at 32,800 bytes, overwrites the previous session and is not appended. Failed file operations return without propagating an error into the network path. The record counter/slot permit chronological decoding after wraparound.

At RVA 0x850, serial read completions -30/-31/-32 formerly applied AND #8 to the flags. This discarded active, serial-open, transmit and flow state, preventing the next read. BIC #8 now clears parser escape state while retaining operational flags. The existing error path discards the damaged partial packet. This defect is reproduced in ARM execution; its occurrence during the current browser hang is not established, particularly because Ping reportedly remains working.

The old minimal no-log patch script remains as a historical comparison utility. It is not the 0.4.2 build path. Binary layout changes for the bounded diagnostic implementation; this release does not claim byte identity with v3 or a confirmed fix for the browser problem.

## Repaired driver behavior

1. Initialize the MComm read/write helpers with `CommConstructL`, protected by CleanupStack; clean them with `CommDelete` while preserving destructor arguments.
2. Clear the original driver's forced DSR/DCD obey/fail handshake bits (`0xf0`), retaining unrelated configured handshake bits.
3. Count outgoing mbufs **before** `RMBufPktQ::Append` transfers ownership and clears the source chain. The stock order can panic with `MBuf 13` in `NumBufs`.
4. Initialize byte cursors for the first transmit mbuf as well as subsequent mbufs.
5. Set the write descriptor length from used bytes, rather than unused capacity.
6. Track a pending SLIP-END delimiter with private state bit `0x20`, avoiding idle repeated writes.
7. Balance queued data-mbuf accounting and wake an IP sender blocked by asynchronous output.
8. Resume receive cursors across serial reads while keeping the original buffer limit.
9. Preserve non-parser connection/write state when the receive parser returns.
10. Finalize and queue a partial receive mbuf using its used length; handle frames ending on an exact mbuf boundary without dereferencing a missing partial buffer.

The repair scripts retain unrelated original code, exports and relocation sites. Existing loader-relocated import references are retargeted when the import table is extended. Branch targets and checksums are validated. These are binary transformations of one exact SDK input, not a clean-room replacement driver.

## Static IP configuration

The original SLIP Control method does not supply `KSoIfConfig`. The inspected TCP/IP stack falls back to `TCPIP.INI`, trying the interface names obtained from the driver. The observed names are `slip` and `slip::ecuart`.

The file supplies `address`, `netmask`, `dstaddr`, `defgate`, `ns1` and `ns2` for both sections. The original `[loop0]` and `[resolver]` settings are retained. This avoids relying on Internet-profile IP fields that were correctly displayed in the editor but not applied to the active SLIP interface.

## Native editor adaptation

The exact SDK Internet applet is patched with a separate experimental UID/resource namespace. Resource 37 changes from `ppp` to `slip`; a precise list query selects visible `DialOutService` records with `IfName='slip'`. The native editor still saves normal connection records.

The `.ISP` export is a limited template and does not preserve all internal SLIP/IP settings. Do not treat it as a complete connection-database backup.

The old IrLAN-derived experimental applet is not used by this implementation.

## Package identity

| Identity | Value |
|---|---|
| SIS component UID | `0x0F574454` |
| Applet UID3 | `0x0F574453` |
| Applet resource base | `0x57445000` |
| Version | `0.4.5` icon fix; driver unchanged from 0.4.4 |

These are experimental, unregistered identifiers; the project does not claim an officially allocated UID.

## Installer configuration choice

The ER5 package uses a text file with `FT,TS` immediately before the active `TCPIP.INI` record. ER5 Install defines No as skipping the next package file while continuing installation. An independent SIS reader checks the reversed storage order, exact payloads and both Yes/No selections.

The SIS does not merge files or back up earlier manual copies automatically. It does not create/delete CommDB profiles or remove unidentified legacy applets.
