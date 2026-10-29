# John descrypt 八核 / PYNQ-Z2

独立目录，不修改 john-pynq-descrypt 单核基线或 bcrypt 工程。
目标 Vivado 2018.3、XC7Z020CLG400-1、100 MHz。

## 本次验收结果（2026-10-21）

完整 SoC 已完成综合、布局布线、bit/hwh 生成及离线审计；没有上板。

| 指标 | 布线后结果 |
|---|---:|
| 真实 descrypt Core | 8 |
| 候选槽位 | 128 |
| LUT | 23,195（43.60%） |
| FF | 29,821（28.03%） |
| BRAM36 等效 | 18（12.86%） |
| DSP | 0 |
| 约束时钟 | 100 MHz |
| WNS / WHS | +0.362 ns / +0.020 ns |
| 未解析黑盒 / 布线错误 | 0 / 0 |
| 时序余量外推 Fmax（非实测） | 103.756 MHz |

bit 文件 4,045,672 字节，hwh 文件 330,512 字节；SHA-256 见 reports/summary.json。
仿真证明 peak_calculating=8，每个核各完成三批；功能并行成立，但未测 CPU 加速比。
DRC 无 Error，保留 RTSTAT-10 无可布线负载警告和两项 REQP-181 write-first 提示；
方法学报告有三项 AXI 协议转换 IP 的 LUTAR-1 异步复位警告。
原始 John vendor 文件及 worker 适配 RTL 与单核工程逐文件哈希一致。

## 八核含义和架构

PS/DDR → AXI DMA → 八路任务分发 → 8 × descrypt_axis_top → 按核编号汇集 → DMA。
每个 worker 内是未修改的原 John descrypt_core：16 级循环流水线及 35 位比较器。
8 个真实核心合计 128 个候选槽，不把流水线的 16 个槽位当作 16 个独立核心。
原始 RTL 和单核适配模块均从已验证的基线复制，源文件保留版权说明。

- 一次输入 128 个候选：8 组，每组 16 个，每核一组。
- 每组可有独立盐值和目标，也可八组使用同一目标。
- 每个 worker 有独立输入缓存、原核和结果保持寄存器；计算彼此重叠。
- 输出包含事务编号、核心编号、临时匹配位图、计算/比较周期和核心状态。
- 使用固定分组分发、按编号汇集，不宣称实现了动态负载均衡或跨批次流水队列。
- 一次只接受一个 superbatch；全部结果回传后才能开始下一个。慢核会影响整批完成时间。
- 35 位部分匹配必须由主机完整哈希复核，不能直接报告口令命中。
- 每个候选仅支持 0..8 字节 ASCII，不支持 BSDI extended DES crypt。

## 工程入口

- build/soc/john_descrypt8.xpr：PS+DDR+AXI DMA+八核完整工程。
- build/sim8/descrypt8_test.xpr：八核自校验仿真。
- build/sim/descrypt_test.xpr：单 worker 回归和非法输入测试。
- deliverables/john_descrypt8.bit、john_descrypt8.hwh：成功实现后的板级文件。
- reports/summary.json：实际离线验收数据。
- reports/soc/routed_utilization.rpt、routed_timing.rpt：布线后资源与时序。
- rtl/descrypt8_axis_top.v：分发、汇集、事务编号、整体故障状态。
- rtl/descrypt_axis_top.v：保持单核版本不变的 worker 适配器。
- host/codec8.py：八核编解码、编号检查、完整哈希复核。
- host/pynq_demo.py：八核 PYNQ 2.4 DMA helper，仅通过 Mock，未上板。

## DMA 接口

全部使用小端 32 位字。输入 **290 字 / 1160 字节**：

| 位置 | 内容 |
|---|---|
| 字 0 | 0x38534344（DCS8） |
| 字 1 | 主机提供的 32 位事务编号 |
| 后续 8×36 字 | 按 core 0..7 顺序，每段为一个单核输入帧 |

每个内层帧：0x31534344、12 位盐、目标低 32 位、目标高 3 位、16 个零填充 8 字节候选。
内部目标哈希比特序与 crypt 文本表示不同，使用 codec 编码，不手工截取字符串。
外层 TKEEP 全 F，只有第 290 字 TLAST=1。分发器为各 worker 产生各自的 TLAST。

输出 **42 字 / 168 字节**：0x38524344、事务编号，然后八条 5 字记录。
每条：core ID、0x31524344、16 位临时匹配掩码、计算/比较周期、worker 状态。
只有最后一字 TLAST=1，允许接收端反压。主机检查事务编号和八个核心编号。

顶层状态：高 8 位 D8；[23:16] worker 错误位图；[15:8] worker 忙位图；
[2] 外层协议故障；[1] 复位故障；[0] 整体忙。
worker 状态：高 8 位 DC；[8] 超时；[4] 比较器错；[3] 原核错；
[2] 内层协议错；[1] 复位故障；[0] 忙。

畸形帧可能在此前 worker 已启动后才被发现，不保证整批原子撤销。
任一错误锁存后停止整个会话；部分输入中断没有 FPGA 输入超时，主机须设定超时。
原核无完整运行时 reset，接受过数据后的复位必须重新加载 overlay 才能恢复。
不得在 DMA 仍可能访问时释放物理缓冲；异常后保留设备对象直到停机/重配置。

## 验证与重建

```powershell
python -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
powershell -ExecutionPolicy Bypass -File scripts/build.ps1
```

重建会更新本目录 build/reports 的生成文件。生成器采用固定随机种子的 Passlib 独立参考。
八核测试覆盖三次连续事务、384 次候选计算、8 种盐、跨核轮换目标、输入连续传输、
输出反压、编号和掩码核对、非法头和复位保护。明确检查 peak_calculating=8，
每个核的实际启动次数均为 3；不是只检查输出总数量。
另有 192 候选 worker 回归、6 类非法内层输入、9 项主机编解码测试及 3 项 DMA Mock 测试。

八核测试每次事务为 759 个仿真时钟（包含测试中的输出暂停，起止以测试代码为准）。
这不是实板 DMA 吞吐量，不能由此宣称 CPU 加速比或精确八倍提速。
Fmax 若列出，为固定 100 MHz 布线余量外推，不是扫频验证。

## 未验证和未包含

没有板卡测试、PS/Linux 执行验证、DDR/DMA 实测、千兆网络实测、双板任务调度、
温度/电压采集或长时间稳定性测试。未运行布局布线后门级仿真。
此接口不是原 John USB 协议，也没有接入原片上模板生成器和完整多目标表装载。
当前性能优化重点仍包括跨 superbatch 队列、片上候选生成、减少软件/DMA 事务开销。
官方 PYNQ PS 配置中的 DDR DQS 负偏移警告保留，上板前核对实际板卡和镜像。
工具警告完整保存在报告，不通过降低严重级别或忽略时序路径掩盖失败。
