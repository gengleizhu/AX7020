"""将Vivado生成的PS/DMA wrapper与原John集成顶层连接；仅DDR/FIXED_IO成为管脚。"""
import re
import sys
from pathlib import Path

source, target = map(Path, sys.argv[1:])
text = source.read_text()
ports = re.findall(r"^\s*(input|output|inout)\s+(\[[^]]+\]\s*)?(\w+)\s*;", text, re.M)
assert ports, "wrapper ports not found"
external = [(d,w,n) for d,w,n in ports if n.startswith(("DDR", "FIXED_IO"))]
internal = [(d,w,n) for d,w,n in ports if not n.startswith(("DDR", "FIXED_IO"))]
assert len(external) >= 20
result = "// Generated PS/DMA + eight original John SHA512crypt units (24 cores, 96 slots).\n"
result += "module john_soc_top(\n" + ",\n".join(f" {d} {w or ''}{n}" for d,w,n in external) + "\n);\n"
result += "".join(f"wire {w or ''}{n};\n" for _,w,n in internal)
result += "system_wrapper system_i(\n" + ",\n".join(f" .{n}({n})" for _,_,n in ports) + "\n);\n"
result += """sha512crypt4_axis_top compute(
 .aclk(clk100),.aresetn(resetn),
 .s_axis_tdata(to_pl_tdata),.s_axis_tkeep(to_pl_tkeep),.s_axis_tlast(to_pl_tlast),
 .s_axis_tvalid(to_pl_tvalid),.s_axis_tready(to_pl_tready),
 .m_axis_tdata(from_pl_tdata),.m_axis_tkeep(from_pl_tkeep),.m_axis_tlast(from_pl_tlast),
 .m_axis_tvalid(from_pl_tvalid),.m_axis_tready(from_pl_tready),.status(compute_status),.initialized(compute_initialized));
endmodule
"""
names = {n for _,_,n in internal}
assert names == {"clk100", "resetn", "compute_status", "compute_initialized"} | {
    p+"_"+s for p in ("to_pl","from_pl") for s in ("tdata","tkeep","tlast","tvalid","tready")
}, names
target.write_text(result)
print(f"SOC_WRAPPER_GENERATED {target}")
