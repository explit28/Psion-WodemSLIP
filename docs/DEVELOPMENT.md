# Development

## Local inputs

Use an ER5 C++ SDK `Cpp` directory containing these exact inputs:

- `EPOC32/Release/MARM/Rel/SLIP.NIF`, 5964 bytes, SHA256 `58ce94961455347d4276297ca42d947ec173e7d5b62660798e375cd7c6b68603`.
- `EPOC32/Release/MARM/Rel/INTERNET.CTL`, 26812 bytes; checked E32 code checksum `0xCEC3DD33`.
- `EPOC32/Release/MARM/Rel/INTERNET.R01`, matching that applet's resources.
- `EPOC32/Release/MARM/Rel/EFSRV.LIB` for diagnostic reference generation.
- `EPOC32/Release/WINS/Rel/Z/System/Controls/INTERNET.aif`, 1600 bytes, SHA256 `02cf66a9257597ee89eac1d37fc5b21374277a8c6545433a221c91233981ef6d`. The original EPOC bitmap/mask pair is portable application-info data; its UID/caption are adapted for WodemSLIP.

The public [psion_cpp_sdk_linux](https://github.com/static-void/psion_cpp_sdk_linux) project was used to locate the SDK/tools during development. Obtain and use SDK inputs under the applicable license. This source archive does not contain them.

For SIS creation, supply the non-Unicode-capable `xmakesis.pl` from sdk2unix (Andrew de Quincey/Rudolf Koenig). In the above source distribution it is at `install/sdk2unix-1.9/bin/xmakesis.pl` after unpacking sdk2unix. It requires Perl and `Compress::Zlib`. The external tool is not relicensed or bundled here.

## Build

Python requirements are pinned to the versions used for verification:

```bash
python3 -m venv .venv
. .venv/bin/activate
python -m pip install -r requirements.txt
python build.py --sdk-root /path/to/Cpp --makesis /path/to/xmakesis.pl --test
```

Outputs:

| Path | Content |
|---|---|
| `dist/WodemSLIP-0.4.5.sis` | Installable ER5 SIS |
| `dist/validation.json` | Driver/SIS hashes and validation summary |
| `dist/SHA256SUMS` | Output checksums |
| `build/driver/` | No-diagnostic driver and detailed repair/test reports |
| `payload/` | Files assembled for the package |

The build reproduces the exact v3 basis and the user-confirmed 0.4.3 diagnostic driver (SHA256 `7d131b4bd6f0654eac93df3e6ffd78faf21b5ab16e5f0f4678ea8ba93d6c721f`). `src/disable_043_diagnostics.py` changes only three diagnostic entry instructions, the object allocation literal and the code checksum. Any other byte difference is rejected. All network repair code and image layout remain unchanged. This preserves inert diagnostic code/imports in the file while making the entry points return without data-memory access. Object allocation returns to 2,244 bytes.

No ARM C++ cross-compiler is required. Exact input mismatches fail the build. `build/diagnostic-043` is the reproducible reference; `build/driver` is the installed derivative. The old `disable_v3_logging.py` and `test_no_log_entry.py` are historical 0.4.1 utilities, not the release patch.

The 0.4.5 packaging change adds WodemSLIP.aif. `build_panel.build_icon` pins the original AIF hash, verifies the UID CRC, preserves both bitmap and mask bytes, and adjusts caption and footer offsets. The installed AIF UID matches the CTL. The driver is byte-identical to 0.4.4; a full network retest is not required for this packaging-only change.

## Verification

The actual ARM driver runs in Unicorn at two load bases. The release suite verifies:

- 116 complete TX/RX loopback cases, 90 receive-boundary cases, 8 factory and 4 destructor cases, and 2048 handshake masks.
- Only five changed words relative to the exact working 0.4.3 image; code checksum and original allocation literal.
- 96 no-op diagnostic-entry cases with all registers/flags preserved and no data-memory access.
- 36 receive-error recovery cases with diagnostics forbidden, including pending output, partial packets and immediate replies.
- Repeated sends and actual Stop/destructor wrapper execution without diagnostic file operations.
- A canary spanning the removed object extension stays untouched in exercised paths.
- Structural/export/relocation checks and independent SIS inspection of UIDs, CRC, version, language, destinations, payloads and optional configuration skip.

The RAM ring-specific test script remains for historical diagnostic builds and is not run on the release. Native OS/protocol APIs are modeled except the selected actual TCPIP routines described below. Physical timing, full kernel/handshake and device installation are not emulated; a final Psion comparison remains necessary.

## Native device TCPIP boundary comparison

The private device TCPIP.PRT input is not included in the public source archive. Its SHA256 must be `730c083b5608addb395eb238147328ea7a5e879dc0f79726fcc3a201d79e0ae9`. With that exact input:

```bash
python build.py --sdk-root /path/to/Cpp --makesis /path/to/xmakesis.pl --test --device-tcpip /private/TCPIP.PRT
```

This also reproduces the 0.4.2 baseline. `test_tcpip_flow.py` executes the actual device Send dispatch at RVA 0xa7a8 and StartSending/manager/state routines (0xb2c8, 0x9100, 0x9134, 0x8274) against old/new ARM NIF code. Lookup, address queries and higher-level notifications are modeled. It confirms old false blocking, 100 corrected single-packet sends without spurious resume, and queue saturation/recovery at two load bases. It does not recreate a complete handshake or prove the device browser is fixed. No device binaries/captures are included in the public ZIP.

## Historical diagnostics

The normal 0.4.4 build produces no diagnostic file. `build/diagnostic-043/SLIP.NIF` is the exact working bounded-RAM reference. Its historical procedure and decoder are described in [DIAGNOSTICS.md](DIAGNOSTICS.md). It is not packaged in the release SIS.

The older synchronous v3-style trace can still be rebuilt explicitly:

```bash
python src/build_driver.py --sdk-root /path/to/Cpp --output build/trace --trace
python tools/decode_trace.py SLIPDBG.BIN
```

That variant appends indefinitely and is a historical comparison tool only.

## Publishing

The source archive excludes `build/`, `payload/`, `dist/`, SDK-derived binaries, diagnostic logs and private captures. It contains scripts, package description, configuration, tests and documentation.

The supplied SIS is a separate device-test artifact. The Symbian SDK license covers its modified driver and applet inputs; public binary redistribution permission is not established by the MIT license on this project's scripts. See [third-party scope](../THIRD_PARTY.md).

Do not claim this is supported on all EPOC devices. Record the actual model, ROM/TCP-IP stack version, driver hash and tested operations in a release report.
