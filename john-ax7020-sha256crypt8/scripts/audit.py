"""Build an evidence summary only after simulation and routed checks pass."""
import hashlib,json,re,xml.etree.ElementTree as ET
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
def read(name): return (ROOT/name).read_text(errors='replace')
sim,invalid,build=(read(name) for name in ('reports/simulation.log','reports/invalid.log','reports/build.log'))
known=read('reports/known.log')
assert re.search(r'KNOWN_TEST_PASS jobs=12 rounds=1000 cycles=\d+',known)
assert re.search(r'SHA256CRYPT8_TEST_PASS units=8 physical_sha256cores_active=24 peak_active_units=8 jobs=96 rounds=10 cycles=\d+',sim)
assert re.search(r'INVALID_TEST_PASS cases=8',invalid)
# Vivado echoes the Tcl guard containing the literal text "Fatal:"; only a
# simulator diagnostic beginning a line is a real failure.
assert not re.search(r'^Fatal:',sim+'\n'+invalid,re.M)
assert re.search(r'SHA256CRYPT_SOC_COMPLETE',build) and not re.search(r'^ERROR:',build,re.M)
timing,util=read('reports/soc/routed_timing.rpt'),read('reports/soc/routed_utilization.rpt')
assert 'All user specified timing constraints are met.' in timing
m=re.search(r'WNS\(ns\).*?\n\s*-+.*?\n\s*([-\d.]+)\s+([-\d.]+)\s+\d+\s+\d+\s+([-\d.]+)',timing,re.S)
assert m
wns,tns,whs=map(float,m.groups()); assert wns>=0 and whs>=0
def resource(label):
    found=re.search(r'\|\s*'+re.escape(label)+r'\*?\s*\|\s*([\d.]+)',util)
    assert found,label
    return float(found.group(1))
status=read('reports/soc/status.txt')
assert 'units=8 sha256cores=24 thread_slots=96 blackboxes=0' in status
hierarchy=read('reports/soc/synth_hierarchy.rpt')
assert len(re.findall(r'^\|\s+unit_i\s+\|\s+sha256unit(?:__\w+)?\s+\|',hierarchy,re.M))==8
assert len(re.findall(r'^\|\s+\\?cores\[\d\]\.core\s+\|\s+sha256core(?:__\w+)?\s+\|',hierarchy,re.M))==24
assert not re.search(r'\|\s*\S+\s*\|\s*Error\s*\|',read('reports/soc/drc.rpt'))
artifacts={}
for name in ('deliverables/john_sha256crypt8.bit','deliverables/john_sha256crypt8.hwh'):
    path=ROOT/name; assert path.stat().st_size>1000
    artifacts[name]={'bytes':path.stat().st_size,'sha256':hashlib.sha256(path.read_bytes()).hexdigest()}
hwh=ET.parse(ROOT/'deliverables/john_sha256crypt8.hwh').getroot()
modules={node.get('INSTANCE'):node for node in hwh.findall('.//MODULE')}
def params(name): return {p.get('NAME'):p.get('VALUE') for p in modules[name].findall('./PARAMETERS/PARAMETER')}
dma=params('dma')
assert dma['C_M_AXIS_MM2S_TDATA_WIDTH']=='32' and dma['C_S_AXIS_S2MM_TDATA_WIDTH']=='32'
assert dma['C_INCLUDE_MM2S_DRE']=='1' and dma['C_INCLUDE_S2MM_DRE']=='1'
assert params('reset')['C_EXT_RESET_HIGH']=='0'
cycles=int(re.search(r'SHA256CRYPT8_TEST_PASS.*cycles=(\d+)',sim).group(1))
standard_compute_cycles=int(re.search(r'KNOWN_UNIT_CYCLES\s+(\d+)',known).group(1))
standard_total_cycles=int(re.search(r'KNOWN_TEST_PASS jobs=12 rounds=1000 cycles=(\d+)',known).group(1))
result={'target':'xc7z020clg400-1','algorithm':'sha256crypt ($5$)','units':8,
 'physical_sha256cores':24,'hardware_thread_slots':96,'verified_jobs':96,
 'parallel_simulation_rounds':10,'single_unit_standard_rounds':1000,
 'default_5000_software_reference_verified':True,
 'clock_mhz':100,'resources_full_soc':{'LUT':resource('Slice LUTs'),'FF':resource('Slice Registers'),
 'BRAM36_equivalent':resource('Block RAM Tile'),'DSP':resource('DSPs')},
 'wns_ns':wns,'whs_ns':whs,'estimated_fmax_from_slack_mhz':1000/(10-wns),
 'parallel_simulation_superbatch_cycles_rounds10':cycles,
 'parallel_simulation_candidates_per_second_at_100mhz_rounds10':96e8/cycles,
 'single_unit_compute_cycles_rounds1000':standard_compute_cycles,
 'single_unit_transaction_cycles_rounds1000':standard_total_cycles,
 'projected_8unit_candidates_per_second_at_100mhz_rounds1000_from_cycle_model':96e8/standard_compute_cycles,
 'board_tested':False,'board_throughput':None,'artifacts':artifacts}
(ROOT/'reports/summary.json').write_text(json.dumps(result,indent=2))
print(json.dumps(result,indent=2))
