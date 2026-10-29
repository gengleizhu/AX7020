# PYNQ-Z2 John SHA256crypt 八算法单元工程

本工程将 John the Ripper 原始 `sha256unit` 接入 PYNQ-Z2（XC7Z020）的 PS + AXI DMA 数据通道。设计包含 8 个完整算法单元；每个单元内部是 3 个 SHA-256 压缩核与 12 个硬件线程槽，因此整机是 24 个物理 SHA-256 核、96 个并发任务槽。它不是把一个核复制成 8 个接口，也没有使用行为级摘要替身。

## 功能边界

- 算法：SHA256crypt，哈希标识 `$5$`。
- 口令：0～32 字节，不允许 NUL。
- 盐：1～16 字节，不允许 NUL 或 `$`；原始核支持示例中的 `=` 等字符。
- rounds 字段按 SHA256crypt 规范校验为 1000～999999999，默认值 5000。PL 另有 100,000,000 周期安全超时；超高 rounds 任务会报告超时，不能理解为保证完成整个规范上限。
- 每次 DMA 请求必须包含 96 个唯一任务 ID，并确定性分给 8 个单元。
- 输出含任务 ID、256 位原始摘要和每单元计算周期；DMA 字节流与常见的 32 字节 SHA 摘要顺序一致。
- 输入长度、字段范围、AXI `keep/last`、超时和不安全复位均有硬件状态位。

## 架构

PS DDR → AXI DMA MM2S → `sha256crypt8_axis_top` → 8×`sha256crypt_lane` → 8×原始 John `sha256unit`。结果按单元顺序汇聚，经 DMA S2MM 回到 DDR。AXI-Lite GPIO 暴露计算状态。

请求为 2498 个 32 位字：请求魔数、事务 ID，以及 8×12 个 26 字任务。响应为 986 个 32 位字：响应魔数、事务 ID，以及 8 组“单元号 + 单元头 + 周期 + 12×(ID64 + digest256)”。

## 源码与兼容修改

`vendor/fpga-sha256crypt` 保存原始 John 源码。`rtl/cpu_vivado.v` 是唯一的算法侧兼容副本：把时钟过程中的一个阻塞赋值改成非阻塞赋值，消除 Vivado/XSim 的跨过程竞态；微码和 SHA256crypt 算法没有改动。

主要文件：

- `rtl/sha256crypt_lane.v`：12 任务装载、原始 2 位输出采集、校验与状态。
- `rtl/sha256crypt8_axis_top.v`：8 单元分发与有序汇聚。
- `host/codec.py`：独立软件参考、DMA 编解码和端序归一化。
- `host/pynq_demo.py`：PYNQ 2.4 DMA 示例（尚未上板）。
- `vivado/create_soc.tcl`：创建 PS、DMA、状态 GPIO 并完成综合、布局布线和 bitstream。

## 离线验证

在 PowerShell 中执行：

```powershell
.\scripts\build.ps1
```

验证包括 Passlib 交叉验证、默认 5000 rounds 官方已知向量、单算法单元 12 个任务的标准 1000 rounds 逐字验证、96 个任务的 10 rounds 八单元并行/分发/汇聚验证、24 个物理核活动断言、反压/帧检查、非法输入检查，以及完整 PS + DMA + PL 的布局布线与时序审计。10 rounds 仅由仿真顶层参数放宽，综合/bitstream 保持默认 `MIN_ROUNDS=1000`。

最终实测数字见 `reports/summary.json`、`reports/soc/routed_utilization.rpt` 和 `reports/soc/routed_timing.rpt`。没有板卡，因此 `board_tested=false`，仿真吞吐不能冒充板上吞吐。

## XC7Z020 实现结果

8 个算法单元已完成完整 PS + DMA + PL 的布局布线，不需要降为 4 单元。布线后资源为 27,428 LUT（51.56%）、29,957 FF（28.16%）、106 BRAM36 等效块（75.71%）、0 DSP；100 MHz 约束下 WNS 为 +0.713 ns、WHS 为 +0.020 ns，按建立时间余量折算的理论时钟上限约为 107.68 MHz。实现检查结果为 0 个算法黑盒、0 条未布通网络。

并行功能仿真覆盖 8 单元、24 个物理 SHA-256 核和全部 96 个任务槽。为控制 XSim 时间，该项使用 10 rounds，只用于验证并行分发、核活动、结果汇聚和 AXI 反压；另由单个原始算法单元以标准下限 1000 rounds 对 12 个任务逐字校验，算法计算耗时 599,582 周期，含接口收发共 599,858 周期。按 8 个单元等速并行的周期模型折算，100 MHz、1000 rounds 时约为 16,011 candidate/s；这是仿真周期推算值，不是板上实测。默认 5000 rounds 的标准向量由独立软件参考验证。
