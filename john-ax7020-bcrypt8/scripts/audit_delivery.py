"""核对可交付bit/hwh与设计接口的离线一致性，不操作板卡。"""
import hashlib
import json
from pathlib import Path
import xml.etree.ElementTree as ET

ROOT=Path(__file__).resolve().parents[1]
folder=ROOT/"deliverables/soc8"
tree=ET.parse(folder/"john_soc8.hwh")
modules={m.get("INSTANCE"):m for m in tree.findall(".//MODULE")}


def params(name):
    return {p.get("NAME").upper():p.get("VALUE") for p in modules[name].findall("./PARAMETERS/PARAMETER")}


dma=params("dma")
checks={"C_INCLUDE_SG":"0","C_INCLUDE_MM2S_DRE":"1","C_INCLUDE_S2MM_DRE":"1",
        "C_M_AXIS_MM2S_TDATA_WIDTH":"32","C_S_AXIS_S2MM_TDATA_WIDTH":"32","C_SG_LENGTH_WIDTH":"23"}
for key,value in checks.items():
    assert dma[key]==value,(key,dma.get(key))
assert params("reset")["C_EXT_RESET_HIGH"]=="0"
assert params("status")["C_GPIO_WIDTH"]=="32"
assert params("status")["C_ALL_INPUTS"]=="1"
ps=params("ps7_0")
assert ps["PCW_USE_S_AXI_HP0"]=="1"
assert ps["PCW_ENET0_PERIPHERAL_ENABLE"]=="1"
assert float(ps["PCW_FPGA0_PERIPHERAL_FREQMHZ"])==100
log=(ROOT/"build/soc8/john_soc8.runs/synth_1/runme.log").read_text()
assert "$readmem data file 'bcrypt/S_data.txt' is read successfully" in log
assert "cannot be opened" not in log
sha=hashlib.sha256((ROOT/"third_party/pynq_reference/base_v2_4.tcl").read_bytes()).hexdigest()
assert sha=="56efc009575551efdd0963f3f6608f0d61a1499e4ace3a4f38164d84537f8897"
manifest={"board_tested":False,"part":"xc7z020clg400-1","cores":8,"clock_mhz":100,
          "dma_checked":checks,"files":{}}
for name in ("john_soc8.bit","john_soc8.hwh"):
    raw=(folder/name).read_bytes()
    manifest["files"][name]={"bytes":len(raw),"sha256":hashlib.sha256(raw).hexdigest()}
(folder/"manifest.json").write_text(json.dumps(manifest,indent=2))
print("DELIVERY_AUDIT_PASS: bit/hwh, DMA widths/DRE, reset polarity, PS Ethernet/clock, ROM initialization")
