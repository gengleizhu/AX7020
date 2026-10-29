"""从实际日志生成报告；缺失PASS或来源不一致时拒绝生成成功报告。"""
from pathlib import Path
import datetime
import hashlib
import json
import re

ROOT = Path(__file__).resolve().parents[1]
report = ROOT / "reports/stage1"
def read_log(path):
    data = path.read_bytes()
    return data.decode("utf-16" if data[:2] in (b"\xff\xfe",b"\xfe\xff") else "utf-8",errors="replace")

manifest = json.loads((ROOT / "reports/source_manifest.json").read_text())
for name, digest in manifest["sha256"].items():
    assert hashlib.sha256((ROOT / "rtl/john_original" / name).read_bytes()).hexdigest() == digest, name
tests = ["tb_expand", "tb_core", "tb_invalid", "tb_packet"]
for test in tests:
    log = (report / f"{test}.log").read_text(errors="replace")
    assert f"STAGE1_PASS {test}" in log and "Fatal:" not in log and "cannot be opened" not in log, test
assert "STAGE1_PACKET_BYTES_PASS" in read_log(ROOT / "logs/stage1/packet_compare.log")
assert "OK" in read_log(ROOT / "logs/stage1/codec.log")

def count(text, label):
    return float(re.search(r"\|\s*" + re.escape(label) + r"\s*\|\s*(\d+(?:\.\d+)?)", text).group(1))

rows = []
for p in ("10.000", "8.000", "6.667"):
    status = (report / f"synthesis/core_{p}_status.txt").read_text()
    assert "blackboxes=0 real_core=1" in status
    wns = float(re.search(r"wns_ns=([-\d.]+)", status).group(1))
    util = (report / f"synthesis/core_{p}_utilization.rpt").read_text()
    rows.append(dict(period_ns=float(p),frequency_mhz=round(1000/float(p),3),
                     LUT=int(count(util,"Slice LUTs*")),FF=int(count(util,"Slice Registers")),
                     BRAM36=count(util,"Block RAM Tile"),DSP=int(count(util,"DSPs")),WNS=wns))
assert rows[0]["WNS"] >= 0
results = json.loads((ROOT / "sim/vectors/vectors.json").read_text())
lines = [
    "# 阶段1实际验证报告",
    "",
    f"生成时间：{datetime.datetime.now().isoformat(timespec='seconds')}。",
    f"John提交：`{manifest['commit']}`；Vivado 2018.3；器件 `xc7z020clg400-1`。",
    "",
    "## 结论",
    "",
    "阶段1自检仿真和100 MHz单Core OOC综合通过。没有执行布局布线、bitstream生成或开发板运行。",
    "算法Core六个源文件保持原样；协议链使用原John模块，仅补充word_gen_b遗漏的寄存器声明。",
    "",
    "## 验证记录",
    "",
    "| 项目 | 实际验证 |",
    "|---|---|",
    "| 参考模型 | 9个已知答案；标准字符串含23字节哈希，参考模型提供完整24字节 |",
    "| tb_expand | 9组18×32bit Expanded Key，含符号扩展差异、消费端暂停 |",
    "| tb_core | 9组P/S初始化、PD装载、Cost循环计数、64bit ID、257bit结果帧 |",
    "| tb_invalid | 5个Header/Checksum负例、1个有效对照、3个Config负例 |",
    "| tb_packet | 10批次、11条RESULT；含连续双候选、Word ID 0/1、奇偶包长度、输出反压 |",
    "| C/Python | 原pkt_comm.c生成65条不同长度报文与Python编码逐字节一致 |",
    "| Python解码 | 1字节等多种分段、连续包、逐字节损坏、非零reserved字段 |",
    "| 综合 | 真实fsm/unit/P/S存在，0 Blackbox，100/125/150 MHz三档 |",
    "",
    "## 单Core综合资源与内部时序",
    "",
    "| 目标MHz | LUT | FF | BRAM36等效 | DSP | WNS(ns) |",
    "|---:|---:|---:|---:|---:|---:|",
]
for row in rows:
    lines.append(f"| {row['frequency_mhz']} | {row['LUT']} | {row['FF']} | {row['BRAM36']} | {row['DSP']} | {row['WNS']:+.3f} |")
lines += [
    "",
    "这些是综合后的内部寄存器路径估算，没有接口输入/输出延时、布线延时或板级Fmax承诺。",
    "方法学报告保留TIMING-18（OOC接口无延时）及SYNTH-6（BRAM输出未合并寄存器）警告。",
    "mode_cmp在原Core未被使用，因此未连接端口警告属已知事实；比较位于外围arbiter/comparator。",
    "100 MHz使用4个RAMB18；更紧约束下工具把部分S盒映射为LUT RAM，LUT用量随之变化。",
    "",
    "## 实际Core测试周期",
    "",
    "周期从首个任务数据字节之前开始，包含31字装载、计算、31周期延后读取、串行输出；不含1054字初始化。",
    "这是仿真计数，不能当作整板吞吐量。",
    "",
    "| 向量 | Cost | 循环次数 | 周期 | 串行帧bits |",
    "|---|---:|---:|---:|---:|",
]
for line in (report / "core_results.txt").read_text().splitlines():
    idx,cycles,loops,bits=map(int,line.split())
    v=results[idx]
    lines.append(f"| {v['name']} | {v['cost']} | {loops} | {cycles} | {bits} |")
lines += [
    "",
    "## 验证边界与后续事项",
    "",
    "- 协议链的input_fifo/output_fifo是仅限同钟仿真的行为模型，不是后续AXI或异步FIFO实现。",
    "- mask/TEMPLATE_LIST的实际字符展开、比较模式D2/D4、8Core和双板未在本阶段验收。",
    "- 在mode_cmp=0时原arbiter不发D2、不累计num_processed；后续应按唯一D3结果统计进度。",
    "- 原Core没有显式reset。重新配置可恢复初态；中途任务取消/软复位仍需单独设计。",
    "- Cost=0仅用于原开发向量，不是生产bcrypt输入范围。后续主机须校验格式、范围及2的幂迭代数。",
    "- 只校验传输CRC或Checksum不能认证bitstream控制操作；板端鉴权留给后续阶段。",
    "- 标准bcrypt字符串省略原始结果最后一字节。原ztex_bcrypt.c将小端binary[20]清零用于cmp_exact；本阶段保留完整原始结果。",
    "",
    "日志见本目录的四个tb_*.log、packet_output.hex、core_results.txt；完整工具日志在logs/stage1。",
]
(report / "validation.md").write_text("\n".join(lines)+"\n",encoding="utf-8")
(report / "summary.json").write_text(json.dumps(dict(
    status="stage1_pass",commit=manifest["commit"],core_vectors=len(results),
    packet_results=11,synthesis=rows,board_tested=False,bitstream_generated=False),
    indent=2),encoding="utf-8")
print("REPORT_PASS reports/stage1/validation.md")
