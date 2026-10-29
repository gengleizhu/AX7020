"""Evidence-based delivery summary; never interprets tool exit alone as PASS."""
import hashlib
import json
import re
import xml.etree.ElementTree as ET
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]
def read(path):return (ROOT/path).read_text(errors='replace')
sim=read('reports/simulation.log')
sim8=read('reports/simulation8.log')
build=read('reports/build.log')
assert re.search(r'^DESCRYPT_TEST_PASS',sim,re.M) and not re.search(r'^Fatal:',sim,re.M)
assert re.search(r'^DESCRYPT8_TEST_PASS cores=8 peak_calculating=8 batches_per_core=3 candidates=384 salts=8',sim8,re.M)
assert not re.search(r'^Fatal:',sim8,re.M)
assert re.search(r'^DESCRYPT_SOC_COMPLETE',build,re.M)
assert not re.search(r'^ERROR:',build,re.M)
timing=read('reports/soc/routed_timing.rpt')
util=read('reports/soc/routed_utilization.rpt')
assert 'All user specified timing constraints are met.' in timing
timing_rows=re.search(r'WNS\(ns\).*?\n\s*-+.*?\n\s*([-\d.]+)\s+([-\d.]+)\s+\d+\s+\d+\s+([-\d.]+)',timing,re.S)
assert timing_rows,'Missing timing summary'
wns,tns,whs=map(float,timing_rows.groups())
assert wns>=0 and whs>=0
def resource(name):
    match=re.search(r'\|\s*'+re.escape(name)+r'\*?\s*\|\s*([\d.]+)',util)
    assert match,name
    return float(match[1])
resources={k:resource(label) for k,label in [('LUT','Slice LUTs'),('FF','Slice Registers'),('BRAM36_equivalent','Block RAM Tile'),('DSP','DSPs')]}
state=read('reports/soc/status.txt')
assert 'cores=8 candidate_slots=128 blackboxes=0' in state
hierarchy=read('reports/soc/synth_hierarchy.rpt')
assert len(re.findall(r'^\|\s+core\s+\|\s+descrypt_core(?:__\d+)?\s+\|',hierarchy,re.M))==8,'Eight physical core instances not found'
for path in ['deliverables/john_descrypt8.bit','deliverables/john_descrypt8.hwh']:
    assert (ROOT/path).stat().st_size>1000,path
hwh=ET.parse(ROOT/'deliverables/john_descrypt8.hwh').getroot()
modules={m.get('INSTANCE'):m for m in hwh.findall('.//MODULE')}
def params(name):return {p.get('NAME'):p.get('VALUE') for p in modules[name].findall('./PARAMETERS/PARAMETER')}
dma=params('dma')
assert dma['C_M_AXIS_MM2S_TDATA_WIDTH']=='32' and dma['C_S_AXIS_S2MM_TDATA_WIDTH']=='32'
assert dma['C_INCLUDE_MM2S_DRE']=='1' and dma['C_INCLUDE_S2MM_DRE']=='1'
assert params('reset')['C_EXT_RESET_HIGH']=='0'
assert not re.search(r'\|\s*\S+\s*\|\s*Error\s*\|',read('reports/soc/drc.rpt'))
sources={}
for folder in ['rtl','vivado','sim','scripts','host','vendor']:
    for path in (ROOT/folder).rglob('*'):
        if path.is_file() and '__pycache__' not in path.parts:
            sources[path.relative_to(ROOT).as_posix()]=hashlib.sha256(path.read_bytes()).hexdigest()
summary={'target':'xc7z020clg400-1','tool':'Vivado 2018.3','cores':8,'candidate_slots':128,
         'clock_mhz':100,'resources_full_soc':resources,'wns_ns':wns,'whs_ns':whs,
         'estimated_fmax_mhz':1000/(10-wns),'estimated_fmax_is_sweep':False,
         'rtl_superbatches':3,'rtl_eight_core_candidates':384,'rtl_salts':8,
         'peak_simultaneous_calculating_cores':8,'batches_per_core':3,
         'lane_regression_candidates':192,'negative_lane_protocol_cases':6,
         'host_codec_tests':9,'dma_mock_tests':3,
         'superbatch_cycles_with_test_backpressure':[int(x) for x in re.findall(r'cycles_with_test_backpressure=(\d+)',sim8)],
         'board_tested':False,'network_tested':False,'john_usb_protocol_compatible':False,
         'bit_sha256':hashlib.sha256((ROOT/'deliverables/john_descrypt8.bit').read_bytes()).hexdigest(),
         'hwh_sha256':hashlib.sha256((ROOT/'deliverables/john_descrypt8.hwh').read_bytes()).hexdigest()}
(ROOT/'reports/source_hashes.json').write_text(json.dumps(sources,indent=2))
(ROOT/'reports/summary.json').write_text(json.dumps(summary,indent=2))
print(json.dumps(summary,indent=2))
print('DESCRYPT_OFFLINE_AUDIT_PASS; NOT BOARD TESTED')
