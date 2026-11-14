"""Build a native ER5 SIS using exact local SDK inputs and xmakesis.pl."""
import argparse
import hashlib
import importlib.util
import json
from pathlib import Path
import shutil
import subprocess
import sys

ROOT=Path(__file__).resolve().parent

def module(name,path):
    spec=importlib.util.spec_from_file_location(name,path);m=importlib.util.module_from_spec(spec);spec.loader.exec_module(m);return m

def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--sdk-root',type=Path,required=True,help='Cpp directory of the exact ER5 SDK')
    parser.add_argument('--makesis',type=Path,required=True,help='Path to sdk2unix xmakesis.pl')
    parser.add_argument('--test',action='store_true',help='Run ARM data-path and initialization checks')
    parser.add_argument('--device-tcpip',type=Path,help='Optional exact private device TCPIP.PRT for native flow-boundary regression tests')
    args=parser.parse_args();sdk=args.sdk_root.resolve();maker=args.makesis.resolve()
    if not maker.is_file():parser.error('SIS builder does not exist')
    driver=module('driver',ROOT/'src/build_driver.py');panel=module('panel',ROOT/'src/build_panel.py')
    paths=sdk/'EPOC32/Release/MARM/Rel'
    source=paths/'SLIP.NIF'
    original,v3,reference=driver.build(source,ROOT/'build/v3-reference',sdk_root=sdk,trace=True)
    no_log=module('disable_log',ROOT/'src/disable_v3_logging.py')
    no_log.patch(v3)  # Guard the v3 functional repair basis.
    _,working,reference=driver.build(source,ROOT/'build/diagnostic-043',sdk_root=sdk,trace=True,ram_trace=True,flow_repair=True)
    disable_diag=module('disable_diag',ROOT/'src/disable_043_diagnostics.py')
    clean,patch_report=disable_diag.patch(working,reference)
    shutil.copytree(ROOT/'build/diagnostic-043',ROOT/'build/driver',dirs_exist_ok=True)
    (ROOT/'build/driver/SLIP.NIF').write_bytes(clean)
    report=reference|{'status':'0.4.4 no-diagnostic candidate; device comparison pending','trace_enabled':False,'trace_mode':'disabled','max_dump_bytes':0,'object_size':disable_diag.ORIGINAL_OBJECT_SIZE,'patched_sha256':patch_report['output_sha256'],'diagnostic_removal':patch_report}
    (ROOT/'build/driver/validation.json').write_text(json.dumps(report,indent=2)+'\n')
    ctl,rsc,panel_report=panel.build((paths/'INTERNET.CTL').read_bytes(),(paths/'INTERNET.R01').read_bytes())
    icon_source=sdk/'EPOC32/Release/WINS/Rel/Z/System/Controls/INTERNET.aif'
    icon,icon_report=panel.build_icon(icon_source.read_bytes())
    panel_report['icon']=icon_report
    payload=ROOT/'payload';payload.mkdir(exist_ok=True)
    for name,data in [('SLIP.NIF',clean),('WodemSLIP.ctl',ctl),('WodemSLIP.rsc',rsc),('WodemSLIP.aif',icon),('TCPIP.INI',(ROOT/'config/TCPIP.INI').read_bytes()),('QUICKSTART.TXT',(ROOT/'docs/QUICKSTART.TXT').read_bytes())]:
        (payload/name).write_bytes(data)
    if args.test:
        driver.build(source,ROOT/'build/baseline-v2',sdk_root=sdk,tx_repair=False)
        for name in ['test_data_path.py','test_initialization.py','test_release_no_diagnostics.py']:
            subprocess.run([sys.executable,str(ROOT/'tests'/name)],cwd=ROOT,check=True)
        if args.device_tcpip:
            driver.build(source,ROOT/'build/diagnostic-042',sdk_root=sdk,trace=True,ram_trace=True)
            subprocess.run([sys.executable,str(ROOT/'tests/test_tcpip_flow.py'),str(args.device_tcpip.resolve())],cwd=ROOT,check=True)
    dist=ROOT/'dist';dist.mkdir(exist_ok=True)
    sis=dist/'WodemSLIP-0.4.5.sis'
    subprocess.run(['perl',str(maker),'installer/WodemSLIP.pkg',str(sis)],cwd=ROOT,check=True)
    inspector=module('sis',ROOT/'tools/inspect_sis.py');package=inspector.inspect(sis)
    if package['uid']!=0x0f574454 or package['version']!=[0,4,5]:raise RuntimeError('Incorrect SIS identity')
    expected={r'C:\System\Libs\SLIP.NIF':clean,r'C:\System\Controls\WodemSLIP.ctl':ctl,r'C:\System\Controls\WodemSLIP.rsc':rsc,r'C:\System\WodemSLIP\QUICKSTART.TXT':(payload/'QUICKSTART.TXT').read_bytes(),r'C:\System\WodemSLIP\TCPIP-template.INI':(payload/'TCPIP.INI').read_bytes(),r'C:\System\Data\TCPIP.INI':(payload/'TCPIP.INI').read_bytes()}
    expected[r'C:\System\Controls\WodemSLIP.aif']=icon
    yes={f['destination']:f['payload'] for f in inspector.selected_files(package,True)}
    no={f['destination']:f['payload'] for f in inspector.selected_files(package,False)}
    if yes!=expected:raise RuntimeError('SIS payload/destination mismatch')
    if no!={k:v for k,v in expected.items() if k!=r'C:\System\Data\TCPIP.INI'}:raise RuntimeError('Config skip must preserve existing TCPIP.INI')
    result={'version':'0.4.5-icon-fix','hardware_status':'Driver byte-identical to 0.4.4; add missing original Internet icon AIF with matching WodemSLIP UID/caption. Control-panel display needs a device check.','trace_enabled':False,'trace_mode':report['trace_mode'],'max_dump_bytes':0,'changes':patch_report,'driver_sha256':hashlib.sha256(clean).hexdigest(),'driver_size':len(clean),'control_panel':panel_report,'sis_sha256':hashlib.sha256(sis.read_bytes()).hexdigest(),'sis_files_verified':len(yes),'skip_config_files_verified':len(no),'tests_requested':args.test,'native_device_tcpip_tests_requested':bool(args.test and args.device_tcpip),'installer_checks':['ER5 UIDs','UID CRC','whole SIS CRC','package version','English language','installation order','optional config skip','all destinations and payload bytes','AIF applet UID/caption and preserved original artwork/mask']}
    (dist/'validation.json').write_text(json.dumps(result,indent=2)+'\n')
    sums=[]
    for p in [sis,dist/'validation.json']:sums.append(f'{hashlib.sha256(p.read_bytes()).hexdigest()}  {p.name}')
    (dist/'SHA256SUMS').write_text('\n'.join(sums)+'\n')
    print(json.dumps({k:v for k,v in result.items() if k!='control_panel'},indent=2))

if __name__=='__main__':main()
