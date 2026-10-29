"""报告只汇总实际工具输出；板级性能永远为null，不能以仿真吞吐替代。"""
import argparse
import hashlib
import json
from pathlib import Path
import re

ROOT=Path(__file__).resolve().parents[1]


def resource(path):
    text=path.read_text()
    out={}
    for key,name in (("LUT","Slice LUTs"),("FF","Slice Registers"),("BRAM36","Block RAM Tile"),("DSP","DSPs")):
        match=re.search(r"\|\s*"+re.escape(name)+r"\*?\s*\|\s*([\d.]+)\s*\|",text)
        if not match: raise ValueError("missing resource "+name)
        out[key]=float(match[1])
    return out


def timing(folder):
    text=(folder/"routed_timing.rpt").read_text()
    line=text.split("WNS(ns)",1)[1].splitlines()[2]
    values=line.split()
    out={"WNS_ns":float(values[0]),"WHS_ns":float(values[4]),"WPWS_ns":float(values[8]),
         "timing_met":"All user specified timing constraints are met." in text}
    route=(folder/"route_status.rpt").read_text()
    assert re.search(r"nets with routing errors\.+\s*:\s*0\s*:",route)
    assert out["timing_met"] and min(out["WNS_ns"],out["WHS_ns"],out["WPWS_ns"])>=0
    return out


def simulation(folder,cores,cost):
    audit=json.loads((folder/"udp_audit.json").read_text())
    assert audit["status"]=="pass" and audit["cores"]==cores and audit["cost"]==cost
    text=(folder/"simulate.log").read_text()
    assert "INTEGRATION_PASS" in text and "Fatal:" not in text and "cannot be opened" not in text
    metrics=(folder/"metrics.txt").read_text()
    summary=dict(re.findall(r"(\w+)=(\d+)",metrics.split("SUMMARY")[-1]))
    assert int(summary["peak_busy"])==cores and int(summary["results"])==32
    cycles=[int(x) for x in re.findall(r"CORE core=\d+ cycles=(\d+)",metrics)]
    core_ids={int(x) for x in re.findall(r"CORE core=(\d+)",metrics)}
    assert len(cycles)==32 and core_ids==set(range(cores))
    import sys
    sys.path.insert(0,str(ROOT/"host"))
    from john_packet_codec import Decoder
    raw=(folder/"windows_received.bin").read_bytes()
    assert hashlib.sha256(raw).hexdigest()==audit["output_sha256"]
    assert hashlib.sha256((folder/"received_input.bin").read_bytes()).hexdigest()==audit["input_sha256"]
    decoder=Decoder()
    actual=[p.encode().hex() for p in decoder.feed(raw)]
    expected=json.loads((ROOT/f"sim/integration/cost{cost}/expected.json").read_text())
    assert not decoder.buffer and sorted(actual)==sorted(expected)
    return {"cores":cores,"cost":cost,"results":32,"peak_busy":cores,
            "core_cycles_min":min(cycles),"core_cycles_max":max(cycles),
            "batch_cycles":int(summary["batch_cycles"]),
            "PL_simulated_hashes_per_second_at_100MHz":32*100e6/int(summary["batch_cycles"]),
            "hardware_measured_hashes_per_second":None,"evidence":str(folder.relative_to(ROOT))}


def main():
    p=argparse.ArgumentParser()
    p.add_argument("--single",type=Path,default=ROOT/"reports/stage3/udp_1_cost4")
    p.add_argument("--eight4",type=Path,default=ROOT/"reports/stage4/udp_8_cost4")
    p.add_argument("--eight5",type=Path,default=ROOT/"reports/stage4/udp_8_cost5")
    args=p.parse_args()
    original=json.loads((ROOT/"reports/source_manifest.json").read_text())
    for name,sha in original["sha256"].items():
        assert hashlib.sha256((ROOT/"rtl/john_original"/name).read_bytes()).hexdigest()==sha,name
    sim=[simulation(args.single.resolve(),1,4),simulation(args.eight4.resolve(),8,4),simulation(args.eight5.resolve(),8,5)]
    adapter=(ROOT/"reports/stage3/adapters/simulate.log").read_text()
    assert "ADAPTERS_PASS" in adapter and "Fatal:" not in adapter
    reset=(ROOT/"reports/stage3/reset/simulate.log").read_text()
    assert "RESET_GUARD_PASS" in reset and "Fatal:" not in reset
    pl=ROOT/"reports/stage4/cores8"
    status=(pl/"status.txt").read_text()
    assert "physical_cores=8 blackboxes=0" in status and "implementation=pass" in status
    pl_data={**resource(pl/"routed_utilization.rpt"),**timing(pl)}
    pl_data["estimated_internal_Fmax_MHz"]=float(re.search(r"estimated_internal_fmax_mhz=(\S+)",status)[1])
    soc=ROOT/"reports/stage4/soc8"
    soc_status=(soc/"status.txt").read_text()
    assert "physical_cores=8 blackboxes=0" in soc_status and "bitstream_generated=true" in soc_status
    soc_data={**resource(soc/"routed_utilization.rpt"),**timing(soc)}
    soc_data["estimated_Fmax_MHz"]=float(re.search(r"estimated_fmax_mhz=(\S+)",soc_status)[1])
    for ext in ("bit","hwh"):
        assert (ROOT/f"deliverables/soc8/john_soc8.{ext}").stat().st_size>1000
    result={"status":"offline_stage3_stage4_pass","board_tested":False,
            "physical_cores":8,"PL_OOC":pl_data,"full_SoC":soc_data,"simulations":sim,
            "notes":["Fmax为固定布局布线网表的时序外推，不是扫频或板测极限。",
                     "吞吐为32任务批次RTL周期换算，不包含真实网络、PS、DMA或DDR开销。",
                     "PS DDR负DQS skew警告继承官方PYNQ v2.4配置，实板验收前必须核对。"]}
    out=ROOT/"reports/stage34"
    out.mkdir(parents=True,exist_ok=True)
    (out/"summary.json").write_text(json.dumps(result,indent=2,ensure_ascii=False),encoding="utf-8")
    lines=["# 阶段3/4：单核集成及直接8核离线验收","",
           "结果：离线验收通过。实际板卡测试未执行。用户调整后不再要求2/4核逐档验收。","",
           "## 真实实现资源及布线后时序","",
           "| 范围 | LUT | FF | BRAM36等效 | DSP | WNS(ns) | WHS(ns) | Fmax估算(MHz) |",
           "|---|---:|---:|---:|---:|---:|---:|---:|"]
    for name,data,fkey in (("8核完整PL（OOC）",pl_data,"estimated_internal_Fmax_MHz"),
                           ("PS+DMA+8核完整系统",soc_data,"estimated_Fmax_MHz")):
        lines.append(f"| {name} | {data['LUT']:g} | {data['FF']:g} | {data['BRAM36']:g} | {data['DSP']:g} | {data['WNS_ns']:+.3f} | {data['WHS_ns']:+.3f} | {data[fkey]:.3f} |")
    lines += ["","100MHz目标；检查8个真实bcrypt_core和0黑盒。布线无错误，setup/hold/pulse约束通过。",
              "Fmax=1000/(10-WNS)，只作固定网表估算，未承诺可在该频率重新实现或实板稳定。",
              "OOC接口预算2ns且时钟位置未约束；应以含PS真实时钟树的完整系统报告为主要依据。","",
              "## 运算周期及吞吐量","",
              "| 核数 | Cost | 结果数 | 同时Busy峰值 | 每Core计算周期范围 | 批次周期 | 100MHz PL仿真吞吐(hash/s) |",
              "|---:|---:|---:|---:|---:|---:|---:|"]
    for r in sim:
        lines.append(f"| {r['cores']} | {r['cost']} | {r['results']} | {r['peak_busy']} | {r['core_cycles_min']}–{r['core_cycles_max']} | {r['batch_cycles']} | {r['PL_simulated_hashes_per_second_at_100MHz']:.2f} |")
    lines += ["","Core周期从crypt_ready下降到结果empty下降，包含任务装载后的运算，不含初始P/S广播和串行结果读出。",
              "批次周期从首个AXIS输入握手到最后一个输出TLAST握手，含初始化、排队、封包及测试注入反压。",
              "单板硬件吞吐、网络吞吐和DMA开销：未测，不以仿真或Windows墙钟时间代替。","",
              "## 验证证据","",
              "- Windows UDP真实socket发送John包；本机桥重组后启动XSim，RTL输出再通过UDP返回。",
              "- 乱序、重复、缺片补发、重复COMMIT均覆盖；返回包checksum及Packet/Word/Generation ID逐字节验证。",
              "- Cost4/5各32任务，8核各完成4个候选；输出FIFO满、AXIS反压和非整字输入均覆盖。",
              "- 独立适配器测试：160个输入字节、10个输出包、非法TKEEP故障停机；另验证8核会话中途复位锁定。",
              "- 板端DMA调度仅完成Mock单元测试；没有运行ARM、物理DDR、真实以太网或板上DMA。","",
              "## 尚需实板确认与限制","",
              "- 官方PYNQ v2.4 PS预设存在DDR DQS skew -0.009/-0.033警告，本工程没有擅自修改物理参数。",
              "- 保留原校验和DSP输入流水、原Core BRAM输出寄存器、AXI协议转换IP内部异步复位等方法学警告；完整系统DRC无Error。",
              "- 原Core无软复位，任务开始后的复位会锁定会话；故障恢复须重新加载可信overlay。",
              "- 集成输出只支持mode_cmp=0的D3包；D2/D4比较模式尚未验收。",
              "- Windows仿真桥仅监听127.0.0.1，不是生产PS网络服务；无远程bitstream加载功能。",
              "- 未执行布线后带延时门级功能仿真；当前为RTL功能仿真+实现后静态时序分析。",
              "- 8核当前未出现资源/时序失败；若后续加监测、多代理等出现失败，需重新测量，不沿用本报告。","",
              "## 主要文件","",
              "- 工程：build/soc8/john_soc8.xpr",
              "- 完整系统实现报告：reports/stage4/soc8/",
              "- PL实现报告：reports/stage4/cores8/",
              "- 比特流/硬件描述：deliverables/soc8/john_soc8.bit、john_soc8.hwh",
              "- 一键重建：scripts/run_stage34.ps1",
              "- 设计说明：docs/stage34_design.md"]
    (out/"validation.md").write_text("\n".join(lines)+"\n",encoding="utf-8")
    sources={}
    for folder in ("rtl","host","board","vivado","scripts","tests","sim/tb","third_party/pynq_reference"):
        for file in (ROOT/folder).rglob("*"):
            if file.is_file() and "__pycache__" not in str(file) and file.suffix not in (".pyc",):
                sources[str(file.relative_to(ROOT))]=hashlib.sha256(file.read_bytes()).hexdigest()
    (out/"delivery_source_hashes.json").write_text(json.dumps(sources,indent=2))
    print("OFFLINE_STAGE34_REPORT_PASS")


if __name__=="__main__":
    main()
