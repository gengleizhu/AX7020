"""Fail closed unless real simulation, hierarchy, routing and timing evidence pass."""
import hashlib,json,re,xml.etree.ElementTree as ET
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
def read(name):return (ROOT/name).read_text(errors='replace')
def match(pattern,text):
    found=re.search(pattern,text,re.M)
    assert found,pattern
    return found
sim,known,invalid,build=[read('reports/'+x+'.log') for x in ('simulation','known','invalid','build')]
parallel_cycles=int(match(r'^SHA512CRYPT4_TEST_PASS units=4 physical_sha512cores_active=16 peak_active_units=4 jobs=64 rounds=10 cycles=(\d+)',sim)[1])
standard_total=int(match(r'^KNOWN_TEST_PASS jobs=16 rounds=1000 cycles=(\d+)',known)[1])
standard_cycles=int(match(r'^KNOWN_UNIT_CYCLES (\d+)',known)[1])
match(r'^INVALID_TEST_PASS cases=8',invalid)
match(r'^SHA512CRYPT_SOC_COMPLETE wns_ns=',build)
assert not re.search(r'^(?:Fatal:|ERROR:)',sim+'\n'+known+'\n'+invalid+'\n'+build,re.M)
timing=read('reports/soc/routed_timing.rpt')
assert 'All user specified timing constraints are met.' in timing
m=match(r'WNS\(ns\)[\s\S]*?\n\s*-+[^\n]*\n\s*([-\d.]+)\s+([-\d.]+)\s+\d+\s+\d+\s+([-\d.]+)',timing)
wns,tns,whs=map(float,m.groups());assert wns>=0 and tns==0 and whs>=0
hierarchy=read('reports/soc/synth_hierarchy.rpt')
assert len(re.findall(r'^\|\s+unit_i\s+\|\s+sha512unit(?:__\w+)?\s+\|',hierarchy,re.M))==4
assert len(re.findall(r'^\|\s+\\?cores\[\d\]\.core\s+\|\s+core(?:__\w+)?\s+\|',hierarchy,re.M))==16
assert len(re.findall(r'^\|\s+cpu\s+\|\s+cpu(?:__\w+)?\s+\|',hierarchy,re.M))==4
assert 'units=4 sha512cores=16 thread_slots=64 blackboxes=0' in read('reports/soc/status.txt')
route=read('reports/soc/route_status.rpt')
assert int(match(r'# of nets with routing errors\.*\s*:\s*(\d+)',route)[1])==0
routable=int(match(r'# of routable nets\.*\s*:\s*(\d+)',route)[1])
assert int(match(r'# of fully routed nets\.*\s*:\s*(\d+)',route)[1])==routable
assert not re.search(r'\|\s*\S+\s*\|\s*Error\s*\|',read('reports/soc/drc.rpt'))
util=read('reports/soc/routed_utilization.rpt')
def resource(label):return float(match(r'\|\s*'+re.escape(label)+r'\*?\s*\|\s*([\d.]+)',util)[1])
source=json.loads(read('reports/source_provenance.json'))
for name,info in source['files'].items():
    data=(ROOT/'vendor/fpga-sha512crypt'/name).read_bytes()
    assert hashlib.sha256(data).hexdigest()==info['sha256'],name
original=read('vendor/fpga-sha512crypt/sha512crypt/cpu/cpu.v')
assert read('rtl/cpu_vivado.v')==original.replace('iop_sets_cf = `OP_TYPE_SETS_CF(op_code);','iop_sets_cf <= `OP_TYPE_SETS_CF(op_code);')
reference=json.loads(read('reports/reference.json'))
assert reference['passlib_crosschecks']==16 and reference['default_5000_verified']
artifacts={}
for name in ('deliverables/john_sha512crypt4.bit','deliverables/john_sha512crypt4.hwh'):
    data=(ROOT/name).read_bytes();assert len(data)>1000
    artifacts[name]=dict(bytes=len(data),sha256=hashlib.sha256(data).hexdigest())
modules={m.get('INSTANCE'):m for m in ET.parse(ROOT/'deliverables/john_sha512crypt4.hwh').getroot().findall('.//MODULE')}
def params(name):return {p.get('NAME'):p.get('VALUE') for p in modules[name].findall('./PARAMETERS/PARAMETER')}
dma=params('dma')
assert dma['C_M_AXIS_MM2S_TDATA_WIDTH']=='32' and dma['C_S_AXIS_S2MM_TDATA_WIDTH']=='32'
assert dma['C_INCLUDE_MM2S_DRE']=='1' and dma['C_INCLUDE_S2MM_DRE']=='1'
assert params('reset')['C_EXT_RESET_HIGH']=='0'
result=dict(target='xc7z020clg400-1',algorithm='sha512crypt ($6$)',units=4,john_soft_cpus=4,
    physical_sha512cores=16,hardware_thread_slots=64,blackboxes=0,clock_mhz=100,
    resources_full_soc=dict(LUT=resource('Slice LUTs'),FF=resource('Slice Registers'),BRAM36_equivalent=resource('Block RAM Tile'),DSP=resource('DSPs')),
    wns_ns=wns,whs_ns=whs,estimated_fmax_from_slack_mhz=1000/(10-wns),
    parallel_simulation=dict(jobs=64,rounds=10,cycles=parallel_cycles,peak_active_units=4,physical_cores_active=16),
    standard_unit_simulation=dict(jobs=16,rounds=1000,cycles_until_all_results_collected=standard_cycles,transaction_cycles=standard_total),
    default_5000_software_reference_verified=True,
    throughput_model_note='Only a projection for the tested 1000-round job mix; assumes four units with the same batch latency, ignores PS and DMA overhead.',
    projected_4unit_candidates_per_second_at_100mhz_rounds1000=64e8/standard_cycles,
    board_tested=False,board_throughput=None,source_files_verified=source['files_checked'],artifacts=artifacts)
(ROOT/'reports/summary.json').write_text(json.dumps(result,indent=2))
print('AUDIT_PASS\n'+json.dumps(result,indent=2))
