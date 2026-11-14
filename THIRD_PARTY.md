# Third-party components and distribution scope

## Project-authored material

The repair scripts, SIS inspection/build orchestration, package description, default configuration, tests and documentation are covered by the project's MIT license. That license grants no additional rights over input SDK components or external tools.

## Symbian EPOC ER5 SDK inputs

The driver is a binary transformation of `EPOC32/Release/MARM/Rel/SLIP.NIF`. The native editor is derived from matching `INTERNET.CTL` and `INTERNET.R01`. Original copyright and license terms remain applicable; these are not original clean-room binaries.

The inspected SDK `LICENCE.TXT` limits redistribution in sections c), d), e) and h). Its listed redistributable directories include WINC and installer-tool paths, not the MARM/Rel input directory used here. This project does not assert permission for public redistribution of the resulting modified MARM binaries or SIS. The source archive therefore omits original and modified SDK binaries. The separate SIS is supplied for the requested device installation test.

SDK source-distribution reference: <https://github.com/static-void/psion_cpp_sdk_linux>. Inspect the license accompanying your own SDK distribution. Do not label the driver, native applet or complete SIS as MIT-licensed solely because the patch scripts are MIT-licensed.

## SIS writer

`xmakesis.pl` is an external sdk2unix tool with copyright notices for Andrew de Quincey (2000) and Knowledge Intelligence AG/Rudolf Koenig (2001). Its source header identifies the GNU Public License. It is not included in this source archive; supply a separately obtained copy when building. `tools/inspect_sis.py` is this project's independent reader for validating its own limited ER5 package format.

## Wodem firmware

The Wodem manufacturer references [martin-ger/esp_slip_router](https://github.com/martin-ger/esp_slip_router), whose repository identifies the MIT license. This project does not bundle or flash that firmware. Hardware revisions and firmware flow-control settings can differ.

## Python tools

Capstone, Keystone and Unicorn are external development/test dependencies. They are installed separately through `requirements.txt` and are not embedded in the Psion driver or SIS. Their upstream licenses apply to their packages.

The 0.4.5 icon comes from the SDK Internet.aif (original EPOC Internet artwork and mask). UID/caption changes do not transfer ownership of this artwork. It is included only in the separately supplied device-test SIS, not the public source archive. SDK/binary redistribution rights remain subject to the applicable license.
