# PYNQ-Z2 John bcrypt

## 阶段3/4：单核集成与直接8核

按最新要求直接实现8核，不再要求2/4核逐档验收。离线工作覆盖Windows UDP→XSim真实RTL结果回传、
8核并行验证，以及完整PS/DMA/PL系统的实现流程；**没有板卡，不声称板级验收完成**。

- [阶段3/4实际报告](reports/stage34/validation.md)
- [中文接口与设计说明](docs/stage34_design.md)
- 完整系统工程：`build/soc8/john_soc8.xpr`
- 比特流与硬件描述（生成成功后）：`deliverables/soc8/john_soc8.bit`、`john_soc8.hwh`

```powershell
cd E:\zhugenglei.work\john\john-pynq-bcrypt
powershell -ExecutionPolicy Bypass -File scripts\run_stage34.ps1
```

此入口默认重新验证单核阶段3和8核Cost4/5，不运行2/4核。UDP仿真每次使用新目录；报告会核对实际结果、
真实核数量、黑盒、布线错误与setup/hold时序。Fmax和吞吐量的估算口径见报告，板级实测值不伪造。

## 阶段1（保留基线）

本工程实现John原始bcrypt单Core功能基线，支持Vivado 2018.3重建、自检仿真和XC7Z020单Core综合。
实际结果以 [验证报告](reports/stage1/validation.md) 为准。阶段1本身没有bitstream或板级程序。

## 运行

本机已找到 `C:\Xilinx\Vivado\2018.3`。需要Python 3.10以上和Git；C测试使用Vivado自带MinGW GCC。

```powershell
cd E:\zhugenglei.work\john\john-pynq-bcrypt
powershell -ExecutionPolicy Bypass -File scripts\run_stage1.ps1
```

其它安装路径：

```powershell
powershell -ExecutionPolicy Bypass -File scripts\run_stage1.ps1 -VivadoRoot C:\Xilinx\Vivado\2018.3 -Python python
```

成功结束标记为 `STAGE1_ALL_PASS`。任何缺少PASS、结果不匹配、源码变化或100MHz内部综合时序失败均会退出失败。
每次运行会重新生成本工程build目录和报告；请不要将个人源文件放在build中。

## 打开工程

工程文件：`build/project/john_bcrypt_stage1.xpr`。
综合顶层是原始 `bcrypt_core`；仿真顶层可选 `tb_core`、`tb_expand`、`tb_invalid`、`tb_packet`。
通过脚本运行会为XSIM准备S_data和测试向量。GUI首次运行前请先运行一次脚本。

只重建工程：

```powershell
python scripts\prepare.py
& C:\Xilinx\Vivado\2018.3\bin\vivado.bat -mode batch -source vivado/create_project.tcl
```

仅运行指定测试：

```powershell
& C:\Xilinx\Vivado\2018.3\bin\vivado.bat -mode batch -source vivado/run_sim.tcl -tclargs tb_core
```

## 文件

| 位置 | 用途 |
|---|---|
| third_party/john | 固定提交的完整John仓库 |
| rtl/john_original | 原始bcrypt目录与许可证，SHA-256可核查 |
| rtl/stage1 | Vivado兼容宏、遗漏声明补丁；不重写算法 |
| sim/tb | 四组自检和旧FIFO的同钟行为模型 |
| sim/vectors | 已知答案、完整24字节参考结果、原始John输入包 |
| host/john_packet_codec.py | 可独立复用的v2协议编解码 |
| tests | 直接链接原C的校验器、Python回归 |
| vivado | 创建工程、仿真、综合Tcl |
| scripts/run_stage1.ps1 | 一键重建、验证、报告入口 |
| reports/stage1 | 仿真结果、实际输出、资源及时序报告 |
| docs | 中文模块说明、协议与移植事项 |

## 阶段1验证范围

单Core计算、Key扩展、常量初始化、Cost循环、257bit原始输出与完整John结果包均纳入自检。
CPU参考仅生成预期答案，RTL仿真输出来自原始计算逻辑。
协议测试的FIFO行为模型不属于可烧录设计，尚未验证PS/DDR/DMA/UDP、跨时钟域、8Core、双板或FPGA物理监测。
