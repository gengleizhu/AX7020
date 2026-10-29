# AX7020 统一寄存器开发分支

目标：XC7Z020-2CLG400I，Vivado/Vitis 2020.1。
基线：`baseline-ax7020-before-axi-v1.1`（56d9f7b）。
当前为开发版本，不能把基线 BIT/XSA 的报告视为新增寄存器版本的验证结果。

## 接口与使用顺序

- DMA 控制：0x40400000；兼容状态 GPIO：0x41200000。
- 统一 AXI-Lite：0x43C00000，64 KiB，32 位小端、4 字节对齐。
- Common：0x0000–0x0FFF；算法区：0x1000–0x5FFF。
- 当前算法的单元区：0x8000 + 单元编号 × 0x1000。
- CU：单元基址 + 0x100 + CU 编号 × 0x100。
- 五算法 ID：bcrypt=1、descrypt=2、md5crypt=3、sha256crypt=4、sha512crypt=5。
- 逻辑单元/CU：8×1、8×1、8×3、8×3、4×4；候选槽数不是 CU 数。

1. Linux 加载与目标板匹配的 Bitstream，等待 INIT_DONE/READY；读取 ABI、算法和能力位。
2. PS 校验目标、Salt、rounds/cost、字典和候选 ID，调用相应算法编码器。
3. 写任务描述寄存器 0x100–0x144，发 ARM=1；核对 ACK_SEQ/CMD_RESULT。
4. 准备 DMA 一致性缓冲，先启动 S2MM，再发送 MM2S（64 字节公共头 + 原生算法载荷）。
5. 轮询状态，发 SNAPSHOT=4 后读取同一快照的任务、进度、计数。当前进度是整批完成计数，不是逐轮进度。
6. 等待 DMA 完成并同步 CPU 缓存，验证公共结果头、原生单元/job ID、结果数量，去掉填充候选。
7. DES 仅硬件 35 位初筛，PS 必须完整复核；不得把初筛命中当作最终结果。
8. 确认 DMA 静止后 RELEASE=2。NEED_RELOAD=1 时禁止继续提交，停止/复位 DMA 后重新配置 PL。

一次仅允许一个有限批次在途；队列、UDP 重传、任务重分配在 PS/上位机完成。
ARM/RELEASE 不复位 John 原核，不支持逐 CU 独立启动/复位。
背压期间不得撤销 AXIS VALID；输出超时时保持帧稳定，同时置 warning/NEED_RELOAD，PS 应废弃该批并协调恢复。

## 已有实现与明确限制

已实现源码：统一身份/拓扑、任务描述、ARM/RELEASE/SNAPSHOT/CLEAR_DIAG、
AXI 地址与写掩码校验、输入公共头检查、原生数据转接、结果 BRAM 缓冲、
公共结果头、首错/超时/背压处理、单元与 CU 存在性、共同软件封装。
详细定义来源于 outputs/axi-registers-20261028 中的 v1.1 设计稿。

以下不可视为已经完成：

- 算法参数镜像、逐 CU 完成数/周期观测尚未接入，对应能力或有效位为 0。
- 固定批次算法的单元忙/错可观测；单元 done 是完整结果收集后的保守完成状态。
- bcrypt 无逐 Core 状态观测；其单元状态有效位为 0。
- FIFO 细分计数和传感器未接入；不能把读出的 0 当作真实空 FIFO 或 0℃。
- 中断未接入，PS 使用轮询；BUILD_ID 尚未注入。
- 固定算法载荷格式、Salt/口令校验由原适配器及 PS 编码器承担；公共壳不替代算法编码器。
- 原生 lane 仍有固定超时（MD5 10,000,000 周期，SHA 100,000,000 周期）；
  Common TIMEOUT_US=0 不能取消原生超时。高 rounds 的支持仍需调整与回归。
- `software/axi_protocol.py` 是公共协议和寄存器接口，不是 Linux DMA 驱动或完整 UDP 节点服务。
- 五个新工程已生成；公共壳五种参数的协议仿真通过，独立综合通过。
  完整 PS+DMA+PL 新版布局布线、真实算法与公共壳端到端回归、板上验证尚待完成。

## 可复现命令（PowerShell，仓库根目录）

```powershell
./john-ax7020-common/build_ax7020.ps1 -Project all -Mode project -PythonExe <python.exe绝对路径>
./john-ax7020-common/build_ax7020.ps1 -Project all -Mode full -PythonExe <python.exe绝对路径>
& E:/Xilinx/Vivado/2020.1/bin/vivado.bat -mode batch -source john-ax7020-common/vivado/test_axi_shell.tcl
& E:/Xilinx/Vivado/2020.1/bin/vivado.bat -mode batch -source john-ax7020-common/vivado/synth_axi_shell.tcl
python -m unittest discover -s john-ax7020-common/software -v
& E:/Xilinx/Vivado/2020.1/bin/vivado.bat -mode batch -source john-ax7020-common/vivado/test_axi_native.tcl -tclargs 3
```

`test_axi_shell.tcl` 使用模拟原生计算端验证总线/帧处理，不是密码算法正确性测试。
`test_axi_native.tcl` 参数 3/4/5 分别连接 MD5/SHA256/SHA512 真实算法与公共壳，比较参考摘要；新增测试尚待完整执行通过。
`synth_axi_shell.tcl` 的资源/时序仅属于默认 MD5 参数的公共模块独立综合，非整机布线结果。
完整工程在各算法目录 `build/soc/*.xpr`，bcrypt 为 `build/soc8/*.xpr`。
打开工程可查看 Block Design 的 unified 模块；顶层源码连接原生算法和 initialized/status。
