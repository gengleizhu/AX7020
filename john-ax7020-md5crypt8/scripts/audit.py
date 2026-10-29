"""Require functional and routed evidence before recording success."""
import argparse,hashlib,json,re
import xml.etree.ElementTree as ET
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
parser=argparse.ArgumentParser()
parser.add_argument('--accept-first-batch',action='store_true',help='Report the verified 96-job batch only; explicitly record incomplete repeated-batch regression')
args=parser.parse_args()
def read(name):return (ROOT/name).read_text(errors='replace')
sim=read('reports/simulation.log');invalid=read('reports/invalid.log');build=read('reports/build.log')
known=read('reports/known.log')
assert re.search(r'^KNOWN_TEST_PASS jobs=12 rounds=1000',known,re.M)
full_pass=bool(re.search(r'^MD5CRYPT8_TEST_PASS units=8 physical_md5cores_active=24 peak_active_units=8 jobs=192 rounds=1000',sim,re.M))
if not full_pass:
    assert args.accept_first_batch,'Full repeated-batch regression not complete'
    assert re.search(r'^SUPERBATCH_CYCLES wave=0 cycles=\d+',sim,re.M)
    assert set(re.findall(r'^UNIT_CYCLES wave=0 unit=(\d+) cycles=\d+',sim,re.M))==set(map(str,range(8)))
assert re.search(r'^INVALID_TEST_PASS cases=8',invalid,re.M)
assert not re.search(r'^Fatal:',sim+'\n'+invalid+'\n'+known,re.M)
assert re.search(r'^MD5CRYPT_SOC_COMPLETE',build,re.M)
assert not re.search(r'^ERROR:',build,re.M)
timing=read('reports/soc/routed_timing.rpt');util=read('reports/soc/routed_utilization.rpt')
assert 'All user specified timing constraints are met.' in timing
m=re.search(r'WNS\(ns\).*?\n\s*-+.*?\n\s*([-\d.]+)\s+([-\d.]+)\s+\d+\s+\d+\s+([-\d.]+)',timing,re.S)
assert m
wns,tns,whs=map(float,m.groups());assert wns>=0 and whs>=0
def resource(name):
    m=re.search(r'\|\s*'+re.escape(name)+r'\*?\s*\|\s*([\d.]+)',util)
    assert m,name
    return float(m[1])
assert 'units=8 md5cores=24 candidate_slots=96 blackboxes=0' in read('reports/soc/status.txt')
hierarchy=read('reports/soc/synth_hierarchy.rpt')
assert len(re.findall(r'^\|\s+unit_i\s+\|\s+md5unit(?:__\w+)?\s+\|',hierarchy,re.M))==8
assert len(re.findall(r'^\|\s+cores\[\d\]\.core\s+\|\s+md5core(?:__\w+)?\s+\|',hierarchy,re.M))==24
assert not re.search(r'\|\s*\S+\s*\|\s*Error\s*\|',read('reports/soc/drc.rpt'))
artifacts={}
for name in ['deliverables/john_md5crypt8.bit','deliverables/john_md5crypt8.hwh']:
    p=ROOT/name;assert p.stat().st_size>1000
    artifacts[name]={'bytes':p.stat().st_size,'sha256':hashlib.sha256(p.read_bytes()).hexdigest()}
hwh=ET.parse(ROOT/'deliverables/john_md5crypt8.hwh').getroot()
modules={m.get('INSTANCE'):m for m in hwh.findall('.//MODULE')}
def params(name):return {p.get('NAME'):p.get('VALUE') for p in modules[name].findall('./PARAMETERS/PARAMETER')}
dma=params('dma')
assert dma['C_M_AXIS_MM2S_TDATA_WIDTH']=='32' and dma['C_S_AXIS_S2MM_TDATA_WIDTH']=='32'
assert dma['C_INCLUDE_MM2S_DRE']=='1' and dma['C_INCLUDE_S2MM_DRE']=='1'
assert params('reset')['C_EXT_RESET_HIGH']=='0'
cycles=[int(x) for x in re.findall(r'^SUPERBATCH_CYCLES wave=\d+ cycles=(\d+)',sim,re.M)]
assert len(cycles)==(2 if full_pass else 1)
sources={}
for folder in ['rtl','vivado','sim','scripts','host','vendor']:
    for p in (ROOT/folder).rglob('*'):
        if p.is_file() and '__pycache__' not in p.parts:
            sources[p.relative_to(ROOT).as_posix()]=hashlib.sha256(p.read_bytes()).hexdigest()
result={'target':'xc7z020clg400-1','units':8,'physical_md5cores':24,'hardware_thread_slots':96,
 'acceptance_scope':'full_repeated_batch' if full_pass else 'verified_first_batch_offline_delivery',
 'verified_mixed_jobs':192 if full_pass else 96,'verified_known_vector_jobs':12,
 'full_repeated_batch_regression_complete':full_pass,'final_dynamic_core_activity_assertion_reached':full_pass,
 'regression_note':None if full_pass else 'Second batch stopped after user accepted existing offline simulation; incomplete second batch is not counted as passed.',
 'clock_mhz':100,'resources_full_soc':{k:resource(v) for k,v in [('LUT','Slice LUTs'),('FF','Slice Registers'),('BRAM36_equivalent','Block RAM Tile'),('DSP','DSPs')]},
 'wns_ns':wns,'whs_ns':whs,'estimated_fmax_from_slack_mhz':1000/(10-wns),
 'simulation_superbatch_cycles':cycles,'simulation_candidates_per_second':[96e8/c for c in cycles],
 'board_tested':False,'board_throughput':None,'artifacts':artifacts,'source_sha256':sources}
(ROOT/'reports/summary.json').write_text(json.dumps(result,indent=2))
print(json.dumps({k:v for k,v in result.items() if k!='source_sha256'},indent=2))
