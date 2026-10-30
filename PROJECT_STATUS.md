# AX7020 双节点 John FPGA 算法加速项目状态

## 2026-10-30 10:04 启动诊断实证（覆盖此前启动推断）

重新放入启动文件后，串口已确认SD首分区找到boot.scr并加载11558416字节image.ub，FIT中内核/initramfs/DTB哈希通过，Linux5.4进入驱动初始化，但尚未出现登录界面。不能再称“SD中没有启动文件”，也不能称“Linux已完整启动”。

本会话经用户授权通过COM7自动中断U-Boot倒计时，fatload镜像，临时设置initcall_debug ignore_loglevel loglevel=8并bootm，未saveenv、未写Flash或SD。证据日志：D:/Documents/ChatGPT/john/output/ax7020_initcall_20261030_100134.log。

详细日志显示zynq_pinctrl_driver_init返回0（8973usecs）；bgpio_driver_init也返回0；随后calling xilinx_gpio_driver_init，没有返回记录。这将停顿范围缩小到Xilinx GPIO驱动初始化，尚不能确诊具体寄存器访问或硬件根因。优先检查PL配置、GPIO的AXI时钟/复位和硬件地址匹配，避免盲目读不可达PL地址。日志随后出现第二次U-Boot启动（是否人工重新上电待确认），第二次采用原bootargs，表明临时参数未持久化。

## 2026-10-30 增量进展（优先于下文 2026-10-29 快照）

用户提供的新构建记录确认：PetaLinux 2020.1 工程已完成配置，采用 MD5 XSA；Linux 5.4 与 initramfs 已构建，设备树和 SD 启动镜像已生成。用户随后明确确认 AX7020 板卡已正常启动。当前尚未由本会话获取板卡启动日志或登录验证；Linux DMA/中断/算法闭环及 UDP 节点服务仍未验证。下文“Linux 未构建/尚未启动”均为历史状态，不代表当前进展。

### 环境、产物及证据
- Ubuntu VM：zgl@10.10.10.107；用户报告 nproc=4。该地址不是已确认的板卡地址。
- VM 工程：/home/zgl/ax7020_linux/projects/ax7020_linux；工具：/home/zgl/petalinux/2020.1。
- 用户报告构建 2926 tasks 全部成功、device-tree 成功；TFTP /tftpboot 不存在警告未阻断镜像生成。
- 本会话已实际读取 D:/Downloads/ax7020_file/ax7020_sd_boot_20261029.zip，四个文件的 SHA256 均与用户提供值一致：
  - BOOT.BIN，4908080字节：4e593fe421c51ab0a4c3a0658b857f89911e82b52ab756bcbfce99b277f5d413
  - image.ub，11558416字节：07849e557953a083455970b3ad062482d7d9d0c3fbb480334518c4fad4de7dae
  - system.dtb，21102字节：6f38fe4ba38503c1836ee9d370f23fe28247d1112672d494b1758e0ff1cdb48e
  - boot.scr，2010字节：1628b69752247215cf8687de082d420367ec8048d301c118427e57ee2942d8fc
- 用户报告 BOOT.BIN 包含 FSBL/U-Boot/MD5 bit/DTB，image.ub 包含内核/initramfs/DTB；本轮仅验证文件哈希，尚未重新解析内部打包顺序或启动脚本。
- 用户报告设备树：DMA@40400000，interrupts=<0 29 4>,<0 30 4>，对应mm2s_introut/s2mm_introut；unified@43c00000窗口0x10000；GPIO@41200000；gem0的PHY地址1。中断三元组中的29/30不是 Linux 动态 IRQ 编号。
- UART 实际控制台用户记录为 console=ttyPS0,115200；其“UART1”说法需根据板级连线/别名核对，不能直接把硬件 UART 编号与 ttyPS 编号等同。

### 构建问题与未提交配置
用户报告已解决：XSA目录导入、menuconfig终端尺寸、plnx_workspace初始化；tcf-agent改GitLab，FSBL/U-Boot用GitCode对应commit，gcc/Linux下载用清华镜像，临时关闭远程sstate。
这些改动在VM中，尚未提交至AX7020仓库；本会话尚未审阅bbappend/配置具体内容。后续必须保存配方覆盖、commit及下载校验，不删除build或下载缓存来“修复”。
initramfs不持久保存运行时改动；后续可用独立可写SD数据分区或EXT4根文件系统持久化服务配置/日志，并非必须更换根文件系统才能持久化。

### 当前调试入口与下一步
- 已开始本机只读准备及交付包校验，未改RTL/驱动/VM配置、未操作SD分区或板上寄存器。
- 本机ARP无法唯一识别板卡；未扫描或猜测其他局域网主机。等待用户提供板卡IP、SSH用户名及登录方式，或串口ip addr输出。
- 对已知VM的只读SSH连接因缺少已验证主机密钥而停止，未绕过主机校验，未登录VM。
- P0：连接正确板卡，采集uname、完整dmesg、网络/路由、设备树、驱动绑定、/proc/interrupts，确认运行镜像。
- P0：确认PL确已配置且时钟/地址有效，再只读magic/ABI/algorithm/READY；不要在PL状态未知时直接访问MMIO。
- P0：确认DMA驱动和缓冲区方案后再做MM2S/S2MM、中断与缓存一致性测试，然后运行真实MD5一批及连续批次。
- P1：UDP/Python单节点闭环、安全算法切换、第二节点调度及掉线恢复。
- 板卡已启动，不再把“首次编译Linux”作为下一步；启动成功也不等于网络、DMA、五算法均验收通过。



更新时间：2026-10-29 16:31（本机时间）。本文件用于聊天恢复、开发交接和后续工作定位。

**当前结论：五算法 DMA 中断版完整构建及新 XSA 公共接口复核均已通过。下一阶段是 AX7020 公共 PetaLinux 平台、Linux DMA 访问和单算法网络闭环。尚未完成当前版本上板、Linux 驱动及双节点系统验收。**

本文记录既有工作，不修改工程功能。不要把综合、时序、仿真、硬件描述一致性与实板系统验收混为一谈。

## 1. 最终目标与范围

- 两块 ARM+FPGA 开发板作为独立计算节点，上位机进行任务分片、能力匹配、任务分发和结果汇总。
- PS 运行 Linux，负责网络通信、输入校验、任务缓存、算法加载、AXI/DMA 控制、状态采集和结果回传。
- PL 执行 John 口令算法计算，提供公共控制接口与结果通道。
- Python 接口对接高层平台；平台管理字典、目标、任务、节点、告警、结果展示/查询/导出与历史记录。
- 最终支持启动介质启动 Linux、节点服务自动运行、异常恢复和维护升级；裸机/JTAG 仅为辅助调试，不是最终交付方式。
- 当前算法范围为 **5 种**：bcrypt、descrypt、md5crypt、sha256crypt、sha512crypt。早期计划中的“4 种”应统一修正。
- 当前目标板卡为 **ALINX AX7020，XC7Z020-2CLG400I**。PYNQ-Z2 是早期目标；ZU5EV/AXU15EG 是此前预调试平台，不是当前交付工程目标。
- 面向已授权口令安全测试。总体需求包含 TCP/UDP 网络能力，当前节点服务按 UDP 方向推进；最终验收应明确是否要求两种协议都实现。

## 2. 环境与目录边界

| 项目 | 当前状态 |
|---|---|
| Windows 工具 | Vivado/Vitis 2020.1 已安装 |
| 虚拟机环境 | 用户已确认 Ubuntu 18.04.4、PetaLinux 2020.1 安装成功 |
| PL 目标时钟 | 100 MHz |
| 实际 FPGA 源码/工程仓库 | `E:/zhugenglei.work/john` |
| 当前聊天工作区/文档目录 | `D:/Documents/ChatGPT/john` |
| Vivado 入口 | `E:/Xilinx/Vivado/2020.1/bin/vivado.bat` |
| Git 远端（用户指定） | `https://github.com/gengleizhu/AX7020.git` |
| 当前 Git 分支 | `feature/axi-registers-v1.1` |
| 当前 HEAD | `19a6e3b`，结果通道流水及布线时序门限提交 |

**D 盘工作区不是 E 盘 Git 工程仓库。** 本次归档以 E 盘工程根目录的 `PROJECT_STATUS.md` 为交接入口，D 盘保留同内容副本；文档写入不代表提交或上传远端。

最近 DMA 中断源码修改及生成物仍需整理提交；不能把 HEAD 当作包含最新中断改动的完整版本。本次未执行提交/推送，已有未提交变更应保留。

## 3. 整体架构

```text
高层管理平台
    ↕ Python 接口 / 任务分发与结果汇总
    ├─ 网络 → 节点 A：ARM Linux + FPGA
    └─ 网络 → 节点 B：ARM Linux + FPGA

单节点控制：ARM PS GP0 → AXI control 互联
                              ├─ AXI DMA 寄存器
                              ├─ status GPIO
                              └─ unified 公共寄存器

任务数据：PS DDR → HP0/内存互联 → DMA MM2S → unified
          → 原始算法适配顶层 → 多算法单元/计算核

结果数据：算法核 → 单元结果缓存 → 汇聚 → result_slice
          → unified 结果 RAM/公共响应 → DMA S2MM → HP0 → PS DDR

中断：DMA MM2S → IRQ_F2P[0]；DMA S2MM → IRQ_F2P[1]
      IRQ_F2P[15:2] 接零
```

上位机网络/调度与 PS Linux 服务在上图中表示目标架构，并非全部已实现。

### 3.1 PS/PL 硬件平台

- `ps7_0`：PS、DDR/MIO 配置、FCLK0 100 MHz；GP0 控制、HP0 访问 DDR。
- `control`：AXI 控制互联，连接 DMA、GPIO、公共外壳。
- `memory`：DMA 读写主接口到 PS HP0 的内存互联，不是算法内部 RAM。
- `dma`：AXI DMA 7.1，Simple 模式（SG=0），双向各一通道；32 bit 内存/流宽度、DRE 开启、Burst=16、长度字段 23 bit。
- `reset`：统一外设/互联复位；`one/zero` 提供常量。
- `status`：原始算法状态 GPIO；不是温度/电压监测模块。
- `unified`：`john_axi_shell_bd.v` 包装 `john_axi_shell.sv`。
- `result_slice`：官方 AXIS Register Slice，切断结果路径组合逻辑。
- 新增 `dma_irq_concat/dma_irq_zero`：两路 DMA 中断与剩余零位拼接到 PS，DIRECT 模式。
- `john_soc_top`：连接 BD 包装和算法 RTL 顶层；算法阵列位于 BD 外。

### 3.2 公共接口

| 项目 | 定义 |
|---|---|
| DMA 基地址 | `0x40400000` |
| 状态 GPIO 基地址 | `0x41200000` |
| 公共寄存器基地址 | `0x43C00000`，64 KiB 窗口 |
| Common 页偏移 | `0x0000-0x0FFF` |
| 各算法页 | 算法编号 1..5 对应 `0x1000..0x5000` |
| 单元 u 窗口 | `0x8000 + u*0x1000` |
| 单元内 CU c 窗口 | 单元基址 + `0x100 + c*0x100` |
| 公共协议 | 64 字节请求/响应头；原始算法 payload 保留 |
| 命令 | ARM=1、RELEASE=2、SNAPSHOT=4、CLEAR_DIAG=8 |
| 并发模型 | 一个有限批次在途，软件可排队 |
| 结果缓存 | 2048×32 bit = 8 KiB |

AXI-Lite 地址与写数据独立锁存，背压时保持响应；非整字写/未对齐写等返回错误。窗口存在不意味着每个偏移都有有效功能。

`irq_status` 是公共软件事件寄存器，不是独立 PL IRQ 输出。此次连接 PS 的中断来自 AXI DMA。

### 3.3 算法配置

| 算法 | ALGORITHM | 单元/核组织 | 物理核 | 槽位 |
|---|---:|---|---:|---:|
| bcrypt | 1 | 8 个逻辑核，经原始 proxy | 8 | 受批次/结果容量限制 |
| descrypt | 2 | 8×1 | 8 | 128 |
| md5crypt | 3 | 8×3 | 24 | 96 |
| sha256crypt | 4 | 8×3 | 24 | 96 |
| sha512crypt | 5 | 4×4 | 16 | 64 |

算法单元、物理计算核、线程槽位不是同一个概念。MD5/SHA 保留 John 微程序 CPU 和算法内部调度，不是 ARM 执行压缩运算。当前自建 AXI/DMA 外层协议，不是原版 USB/ZTEX 插件即插即用。

## 4. 已完成工作与证据

### 4.1 工程与功能

- 五套 AX7020 Vivado 工程及统一板级配置。
- 公共寄存器/任务头、输入检查、批次控制、状态快照、错误记录、结果缓存及 DMA 数据通道。
- 原始 John 算法单元与并行组织接入。
- AXIS 结果流水、部分长组合逻辑优化和布线时序检查门限。
- Python 公共协议、寄存器辅助代码及测试基础。
- Git 基线和此前源码检查点；架构、模块讲解及项目状态资料。
- 五算法 DMA 两路中断统一接线，五次 Vivado `validate_bd_design` 通过。

### 4.2 最新 DMA 中断版完整构建

2026-10-29 16:05:34 最后一个工程完成；后台串行构建已结束。

| 工程 | 导出完成时间 | WNS ns | WHS ns | 新 BIT/HWH/XSA |
|---|---|---:|---:|---|
| bcrypt8 | 15:09:56 | +0.934 | +0.036 | 已导出 |
| descrypt8 | 15:19:42 | +0.326 | +0.036 | 已导出 |
| md5crypt8 | 15:34:46 | +0.506 | +0.036 | 已导出 |
| sha256crypt8 | 15:52:29 | +0.441 | +0.019 | 已导出 |
| sha512crypt4 | 16:05:34 | +0.617 | +0.009 | 已导出 |

均为 100 MHz 下建立/保持时序通过。WNS 裕量换算不等于已验证 Fmax，更不是板上吞吐量。

### 4.3 新 XSA 离线复核

- 直接检查五份 XSA ZIP 完整性、HWH、PS 初始化及配套导出物。
- MM2S/S2MM 分别接 concat In0/In1，输出连接 PS IRQ_F2P，剩余 14 位接零。
- 五份 HWH 忽略时间戳与算法编号后完全一致；新版五份 `ps7_init.c` 哈希一致。
- 相对旧基线，PS 参数只改变 Fabric Interrupt 使能和中断输入数量（1→16）。
- DMA 参数、地址映射及公共模块未发生意外变化。
- 每份 XSA 内 BIT/HWH 与同目录独立文件逐字节一致。
- 结论：可继续按一套公共 Linux 平台维护，不需要因五算法而生成五种内核。

### 4.4 验证边界

- 此前五算法公共接口仿真通过；结果流水修改后真实 MD5 连续两批端到端仿真通过。
- 新增中断后完成的是 BD 校验、完整实现与 XSA 复核；不要将其表述为新中断已通过 Linux/实板验证。
- 五算法同等深度的真实运算回归尚未全部完成。
- 当前 AX7020 版本尚未上板验收，未获得实测吞吐/功耗或 CPU/FPGA 加速比。
- 尚无完整 Vitis 平台/应用工程、PetaLinux 项目交付或 Linux UDP 节点服务。

## 5. 关键设计决策

1. **最终采用 Linux**：裸机/JTAG 只辅助诊断，交付需自动启动和可维护部署。
2. **先单板单算法闭环，再双节点**：先用 MD5 打通真实任务，不扩展新算法/板卡分散主线。
3. **统一硬件接口、一套 Linux**：公共驱动/服务读取能力与版本；算法数据打包和结果校验仍需各自适配。
4. **MD5 XSA 是平台输入而非软件绑定**：选择它因此前真实回归较充分；五份公共接口等价，不是 PetaLinux 必须用 MD5。
5. **全量 Bitstream 切换**：不是局部重配置，也不是五算法同时驻留；DMA 和寄存器也会重配置，必须先停止访问并管理驱动生命周期。
6. **保留原始微程序 CPU**：负责算法步骤与线程状态，ARM 管理系统；不能只保留压缩核而删除算法控制层。
7. **显式区分状态有效性**：预留字段不得冒充实测遥测；单批完成统计不是逐候选实时进度。
8. **保留旧基线**：无中断 `baseline_v1` 仅作追溯；后续 Linux 使用新版 MD5 deliverables 中 XSA。

## 6. 尚未完成的任务与已知问题

### 6.1 Linux/PS（优先）

- 从新 XSA 建立公共 PetaLinux 工程，生成并核对设备树、启动镜像及板级配置。
- 核对中断 parent、编号、触发类型；不能硬编码 Linux 动态 IRQ 号。
- 确认 PetaLinux 2020.1 DMA 驱动与 Simple DMA 的兼容性，选择 DMAengine 客户端/访问方案。
- 实现 DMA 缓冲区分配/映射、缓存一致性、收发顺序、完成通知、错误与超时。
- 实现公共寄存器访问、任务/结果解析、Bitstream 加载、安全切换和恢复。
- 完成 UDP 节点服务、心跳、启动自检、日志、配置维护和开机自启。

### 6.2 PL 与验证

- 补齐五算法真实运算连续批次、非法输入、结果背压、超时和恢复回归。
- 原核依赖配置初始化，不能把 AXI 复位/RELEASE 当作安全取消全部计算；严重异常需重新加载。
- 公共外壳单批在途；任务/结果队列与批量效率仍需系统验证。
- 逐 CU 完成数/活跃周期、FIFO 细分状态、参数镜像和传感器采集未完整实现。
- MD5 原单元内部 err 未全部向上连接；现有外部错误并非完整原核诊断。
- MD5 lane 固定 1000 万周期超时；SHA lane 存在固定超时。公共超时设为 0 不会关闭原生 lane 限制。
- descrypt 的原始候选匹配仍需软件完整复核；不能把短位匹配直接当最终解算结果。

### 6.3 上位机与双节点

- 固化网络协议，完成分片、能力匹配、分发、汇总、完整性检查及重复结果处理。
- UDP 分包/丢包/重复包/超时重传策略未完成；节点掉线后需重新分配任务。
- 完成 Python 接口与高层软件联调、节点管理、告警追溯、结果历史查询/导出。
- 测量单板/双板收益，分别记录纯计算与端到端加速比，测试断网、断电、重启和长期稳定性。

### 6.4 工程与工具问题

- 存在普通综合/实现警告，不宣称零告警。SHA512 本轮综合有 829 条普通警告、0 错误和0严重警告，仍需分类审阅。
- 日志出现 protobuf `ReportMetaData` 解析错误；未阻断本轮五工程导出，但不能说该工具问题已修复。
- Vivado 校验有旧 PS IP socket portmap 警告（BD 41-176）；未阻断校验。
- 部分 README 仍有 PYNQ-Z2/2018.3/旧仿真描述，需要后续清理；当前实际脚本与新报告优先。
- 最新中断代码/产物尚未整理成新的 Git 提交或冻结 v2 副本；避免把源代码 HEAD、旧基线和新生成物混用。

## 7. 重要文件路径

### 7.1 五工程入口

| 算法 | XPR |
|---|---|
| bcrypt | `E:/zhugenglei.work/john/john-ax7020-bcrypt8/build/soc8/john_ax7020_bcrypt8.xpr` |
| descrypt | `E:/zhugenglei.work/john/john-ax7020-descrypt8/build/soc/john_ax7020_descrypt8.xpr` |
| MD5 | `E:/zhugenglei.work/john/john-ax7020-md5crypt8/build/soc/john_ax7020_md5crypt8.xpr` |
| SHA256 | `E:/zhugenglei.work/john/john-ax7020-sha256crypt8/build/soc/john_ax7020_sha256crypt8.xpr` |
| SHA512 | `E:/zhugenglei.work/john/john-ax7020-sha512crypt4/build/soc/john_ax7020_sha512crypt4.xpr` |

新版平台输入：
`E:/zhugenglei.work/john/john-ax7020-md5crypt8/deliverables/john_ax7020_md5crypt8.xsa`

其他交付物位于对应算法 `deliverables`；bcrypt 多一层 `deliverables/soc8`。报告位于 `reports/soc`；bcrypt 为 `reports/stage4/soc8`，重点看 `status.txt`、`routed_timing.rpt`、`routed_utilization.rpt`。

### 7.2 核心源码与工具

- `E:/zhugenglei.work/john/john-ax7020-common/rtl/john_axi_shell.sv`
- `E:/zhugenglei.work/john/john-ax7020-common/rtl/john_axi_shell_bd.v`
- `E:/zhugenglei.work/john/john-ax7020-common/vivado/integrate_axi_shell.tcl`
- `E:/zhugenglei.work/john/john-ax7020-common/vivado/integrate_dma_irq.tcl`
- `E:/zhugenglei.work/john/john-ax7020-common/software/axi_protocol.py`
- `E:/zhugenglei.work/john/john-ax7020-common/build_ax7020.ps1`
- `E:/zhugenglei.work/john/john-ax7020-md5crypt8/vivado/create_soc.tcl`
- `E:/zhugenglei.work/john/john-ax7020-md5crypt8/rtl/md5crypt8_axis_top.v`
- `E:/zhugenglei.work/john/john-ax7020-md5crypt8/rtl/md5crypt_lane.v`
- `E:/zhugenglei.work/john/john-ax7020-md5crypt8/rtl/cpu_vivado.v`
- `E:/zhugenglei.work/john/john-ax7020-md5crypt8/vendor/fpga-md5crypt/md5crypt/`

### 7.3 核对证据、备份和说明

- 新 XSA 复核：`D:/Documents/ChatGPT/john/output/xsa_audit/irq_v2/复核结论.md`
- 新 XSA 哈希/参数证据：`D:/Documents/ChatGPT/john/output/xsa_audit/irq_v2/comparison.json`
- 复核脚本：`D:/Documents/ChatGPT/john/tmp/audit_irq_xsa.py`
- 中断说明：`D:/Documents/ChatGPT/john/output/xsa_audit/DMA中断接入说明.md`
- 构建日志：`D:/Documents/ChatGPT/john/output/xsa_audit/build_irq_all.stdout.log` 及 `.stderr.log`
- 旧交付物备份：`D:/Documents/ChatGPT/john/output/xsa_audit/pre_irq_deliverables_20261029-150248/`
- 旧无中断基线：`D:/Documents/ChatGPT/john/output/xsa_audit/baseline_v1/ax7020_common_platform_v1.xsa`
- 架构 PDF：`D:/Documents/ChatGPT/john/output/pdf/AX7020_PS_PL架构与工程入口.pdf`（较早快照，中断状态以本文件为准）
- MD5 模块说明：`D:/Documents/ChatGPT/john/output/pdf/AX7020_MD5工程模块功能与工作原理.pdf`（编写时重建尚未全部完成）
- 目标/待办记录：`D:/Documents/ChatGPT/john/output/pdf/AX7020项目目标_当前进展与待办补充记录.pdf`
- 工程菜单：`D:/Documents/ChatGPT/john/output/pdf/open_ax7020.cmd`

## 8. 下一步开发计划与验收点

| 顺序 | 工作 | 完成条件 |
|---|---|---|
| 1 | 整理中断版源码/产物版本和哈希；冻结新平台输入 | 可追溯源码、XSA 与报告对应，不覆盖旧基线 |
| 2 | 用新版 MD5 XSA 建立公共 PetaLinux 工程 | 设备树、中断和板级配置审阅通过；生成启动镜像 |
| 3 | 单板 Linux 启动与基础外设验证 | DDR、网口、启动介质、日志/串口诊断正常 |
| 4 | Linux 寄存器与 DMA 访问 | 正确读能力；MM2S/S2MM 中断与缓存一致性验证通过 |
| 5 | MD5 真实计算闭环 | 一批及连续多批结果与软件参考一致，错误/超时可控 |
| 6 | UDP + Python 全链路 | 上位机提交、状态采集、结果返回、完整性检查通过 |
| 7 | 推广其余算法与安全切换 | 一套服务支持五算法，版本识别及重配置恢复可靠 |
| 8 | 第二节点与高层联调 | 不同分片并行执行、汇总和掉线重分配通过 |
| 9 | 性能、稳定性与交付 | 实测报告、开机自启、部署/维护说明和版本归档齐全 |

第一系统里程碑：**上位机 Python → PS Linux → DMA → MD5 PL → DMA → PS → 上位机，真实任务与软件参考一致。**

## 9. 常用操作命令（仅供复现，本次未执行构建）

```powershell
# 打开 MD5 工程
& 'E:/Xilinx/Vivado/2020.1/bin/vivado.bat' 'E:/zhugenglei.work/john/john-ax7020-md5crypt8/build/soc/john_ax7020_md5crypt8.xpr'

# 重新完整构建：会更新生成目录及产物，执行前先确认备份与版本
& 'E:/zhugenglei.work/john/john-ax7020-common/build_ax7020.ps1' -Project all -Mode full -PythonExe 'C:/Users/Administrator/.cache/codex-runtimes/codex-primary-runtime/dependencies/python/python.exe'

# 复核五份新 XSA（更新 D 盘比较报告，不改工程实现）
& 'C:/Users/Administrator/.cache/codex-runtimes/codex-primary-runtime/dependencies/python/python.exe' 'D:/Documents/ChatGPT/john/tmp/audit_irq_xsa.py'
# 上述脚本使用相对输出路径，应在 D:/Documents/ChatGPT/john 下运行。
```

## 10. 聊天历史异常与交接安全

本任务界面/历史读取曾停留在旧消息，但原始会话文件仍含后续内容。根因未定位，不应删除任务、清缓存或直接修改应用数据库。

已保存快照：`D:/Documents/ChatGPT/john/backups/chat-01a15732-20261029-143416/conversation.jsonl`，11517 行 JSON 均可解析；该快照不含 14:34 之后的新消息，不能视为完整最新聊天备份。备份含工程信息，不要公开上传。

当前工程代码和交付文件保留；本次操作只更新状态文档。后续接手时优先核实文件与日志，不依靠旧聊天摘要推断已完成的实板工作。

## 11. 本次深入核查与目录导航

本节是 2026-10-29 在实际源码上补充的交接核查。已搜索 D/E 工程目录及父目录，未发现适用的 `AGENTS.md`。新对话仍应重新检查，以防后续新增约束。历史 README 和验证记录含“中断未接入”“构建中”等旧状态；硬件中断现已接线，Linux 中断处理仍未验证，不能混为一谈。

```text
E:/zhugenglei.work/john/                实际 Git 工程根目录
├─ john-ax7020-common/
│  ├─ board/ps_config_alinx_2023_1.tcl  板级 PS 配置来源，文件名不代表当前工具版本
│  ├─ rtl/                            公共壳与 BD 包装
│  ├─ software/                       公共 Python 编解码/寄存器回调及测试
│  ├─ sim/                            公共壳模拟端、真实算法联合测试平台
│  ├─ vivado/                         集成、中断、仿真、综合及时序检查
│  └─ reports/                        公共平台/接口验证历史记录
├─ john-ax7020-bcrypt8/                8 核；原始代码来源在 third_party/john
├─ john-ax7020-descrypt8/              8 单元
├─ john-ax7020-md5crypt8/              8 单元，24 物理核
├─ john-ax7020-sha256crypt8/           8 单元，24 物理核
├─ john-ax7020-sha512crypt4/           4 单元，16 物理核
├─ outputs/axi-registers-20261028/     分层寄存器设计稿，不是 RTL 全实现清单
├─ BASELINE.md                        基线说明
├─ AX7020_迁移与操作命令.md            迁移命令记录
├─ AX7020_迁移结果_2020.1.md           迁移结果记录
└─ verilog-ethernet/等                其他/历史资源，不能据此认定 AX7020 UDP 已交付

各算法目录：rtl 是适配器；vendor/或 third_party 是原始计算代码；
vivado 是生成/实现入口；host、sim、scripts 是主机辅助/测试；
build 是生成工程；deliverables 是导出物；reports 是验证报告。
其中 MD5 的上述目录已逐项核对，其他算法具体层级以实际文件为准。

D:/Documents/ChatGPT/john/             当前会话工作区，非上述 Git 根目录
├─ output/xsa_audit/                  五 XSA 比较、IRQ 构建记录及旧导出物备份
├─ output/pdf/                        架构、MD5 模块、目标和工程打开入口
├─ tmp/audit_irq_xsa.py               XSA 复核脚本
├─ backups/                          聊天快照
└─ axu15eg-projects、axu5ev-projects、dual_fpga 等：历史预调试资料
```

### 11.1 模块职责与握手关系

| 模块/层 | 实际职责 | 上下游关系与边界 |
|---|---|---|
| PS7 + GP0/HP0 | ARM/DDR、控制主口、DMA 存储通路、时钟复位源 | 软件未部署不等于该硬件平台不存在 |
| AXI-Lite 公共壳 | 身份、描述符、命令确认、快照、首错记录 | 单次独立 AW/W 锁存，B/R 响应等待 ready；不是 Xilinx 成品寄存器 IP |
| 公共壳流状态机 | INIT→IDLE→ARMED→RX→RUN→DRAIN→DONE/ERROR | 请求 16 字头逐字与描述符核对，再转发原生 payload；异常可要求重加载 |
| 结果 BRAM | 原生结果完整收集后输出公共响应头与载荷 | 8 KiB；同步读加输出保持；不是无限结果队列 |
| 原生 axis_top | 固定格式解析、任务分派、单元结果汇聚 | TDATA/TKEEP/TLAST/TVALID/TREADY 背压；bcrypt 使用原始协议解析链 |
| lane | 将任务送入对应原始算法单元并收集结果、执行本地超时 | MD5/SHA 单元内再由微程序 CPU、控制器、计算核协作 |
| 原始 CPU/控制器 | 调度算法循环、线程与消息块，控制算法引擎 | 不承担 Linux/UDP，不是 Zynq ARM；不可当作无关软核删除 |
| result_slice | 原生结果与公共壳间增加官方全寄存流水 | 32 bit，保留 keep/last；减少长组合时序路径 |
| AXI DMA | DDR↔AXIS 双向搬运 | 控制寄存器与任务数据分离；DMA 完成不自动等于算法结果语义正确 |
| Python Registers/Batch | 回调式读写寄存器、描述符/公共包构造和结果校验 | 不分配物理 DMA 内存，不提供缓存一致性，不是完整 PS 节点服务 |

任务输入是流式转发到原生适配器和其内部缓存，公共壳没有对等的整批输入 RAM 队列。结果在公共壳另有整批 RAM。不能泛称“输入/输出均已实现多批 FIFO+RAM”。

## 12. 寄存器实际实现明细（以 john_axi_shell.sv 为准）

全部地址为相对 `0x43C00000` 的偏移，32 bit 小端、4 字节对齐。对齐但未实现的读通常返回 0/OKAY；未对齐读返回 SLVERR。非法写返回 SLVERR 并记错误偏移/总线错误次数。**读到 0 不代表该功能存在。**

### 12.1 Common 身份、控制、描述符和快照

| 偏移 | 实际读值/功能 | 访问和注意事项 |
|---|---|---|
| 000/004/008/00C | magic=4A435250、寄存器 ABI=00010001、窗口=65536、流 ABI=00010000 | RO |
| 010；014–01C | BUILD_DATE；后三项为 0 | BUILD_ID 未注入，不是可追溯 Git 指纹 |
| 020/024/028/02C | 算法 ID/单元数/每单元核数/总核数 | RO，核数与候选槽数不同 |
| 030/034/038 | capabilities、原生格式 ID=0x100+算法 ID、固定槽位数 | bcrypt 槽位数报告 0，按有限批次处理 |
| 03C–068 | 口令/盐/摘要大小、原生输入输出长度/上限、时钟、计时频率及 rounds 边界等常量 | 能力声明不是 PS 参数校验已经完成的证据 |
| 06C/070/074/078/07C | 32、实时 native_status、1、1、0x10000 | 原值按源码解释，不能擅自扩展语义 |
| 080 | 命令 ARM=1、RELEASE=2、SNAPSHOT=4、CLEAR_DIAG=8 | WO，读返回 0；不支持逐 CU 启停 |
| 084 | 全局状态及状态机编码 | RO，位定义见下 |
| 088/08C/090 | 命令序号/确认序号/命令返回码 | 088 RW，其余 RO；软件串行化访问 |
| 094/098 | 软件事件状态/事件使能 | 094 W1C；098 目前始终 0 且写被拒绝；无壳 IRQ 输出 |
| 09C/0A0/0A4/0A8 | 首错/详细信息/常量FFFFFFFF/警告 | 0A8 W1C，不能把 0A4 当真实故障 CU 索引 |
| 0AC/0B0 | 快照序号/有效性 | SNAPSHOT 后读取；0B0 bit1 表示有效 |
| 0B4/0B8 | 整批超时/无握手看门狗，单位微秒 | 仅 IDLE 可写，0 关闭本层限制，不关闭原生 lane 超时 |
| 0BC/0C0/0C4 | 初始化标志/0/1 | 未实现的控制不要依设计稿写入 |
| 0C8/0CC/0D0/0D4 | 单元 busy/error/done/有效掩码 | bcrypt 返回 0；done 是整批结果已收齐后的保守位图 |
| 0D8/0DC | DONE 批号/输入、计算、输出完成及错误标记 | 完成阶段区分读取 |
| 0E0–0FC | 算法位图、当前算法页、单元起址/步长、CU 起址/步长等布局常量 | 只报告当前 bitstream 能力 |
| 100–144 | 18 字任务描述符 | 仅 IDLE 可写，ARM 时校验 |
| 180–1FC | 32 字批次快照 | 低/高字锁存在同一次 SNAPSHOT，未赋值项为 0 |
| 200–23C | 16 字诊断快照 | 当前前 10 字未采集，不能解释为温度/FIFO 实测 |
| 240/244/248 | scratch/最近非法写偏移/快照总线错误数 | scratch RW，其余 RO |
| 400+u×20h | Common 内单元摘要 | 每项 32 字节，存在/忙/完成/错误及错误码；bcrypt 无有效状态 |

STATUS(084) 位：0 READY、1 BUSY、2 DONE、3 ERROR、4 INIT_DONE、5 NEED_RELOAD、6 INPUT_COMPLETE、7 COMPUTE_DONE、8 OUTPUT_COMPLETE、9 成功输出、10 WARNING、11 SNAPSHOT_VALID；[19:16] 是状态机编码 0..7。其余位当前为 0。

描述符按偏移顺序：100/104 task_id 低/高；108 shard_id；10C batch_id；110 algorithm；114 format_id；118 原生输入字节数；11C 接收容量（含64字头）；120 有效候选数；124 物理槽位数；128 原生输出字节数；12C last_batch（0/1）；130 保留0；134 仅 bcrypt 允许非零但公共壳未消费其语义；138–144 保留0。不得把这些保留项当作已生效的 CU 参数。

快照 180 起：0/1 输入候选数，2/3 完成候选数，4/5 结果记录数，6/7 输入字节，8/9 输出字节，10/11 elapsed 周期，12/13 至少一单元 busy 的周期，14/15 输入饥饿周期，16/17 输出背压周期，18/19 uptime 微秒，20/21 首错时刻微秒；22 实际输出总字节，23 batch，24/25 task，26 shard，27 status，28 有效候选总数，29 单元完成位图。30/31 未使用。bcrypt 无逐核 busy，因此 active 不能作为其真实计算利用率。

诊断 200 起：字10/11/12 为拒绝/成功/失败批次计数；字13 为原生输入已收字数；字14 为状态机；字15 固定8。其余为0。SNAPSHOT 不会清计数。

### 12.2 五算法独立页与载荷

| 算法 | 独立页实际地址 | 固定原生输入/输出字节 | 配置方式 |
|---|---|---|---|
| bcrypt ID1 | 0x43C01000–0x43C01FFF | 可变输入≤65536；每候选输出48，最多170 | John 原始 packet 携带配置/候选 |
| descrypt ID2 | 0x43C02000–0x43C02FFF | 1160 / 168；128槽 | 原生固定格式载荷，25轮、35位初筛 |
| md5crypt ID3 | 0x43C03000–0x43C03FFF | 9992 / 2408；96槽 | 原生载荷，1000轮 |
| sha256crypt ID4 | 0x43C04000–0x43C04FFF | 9992 / 3944；96槽 | 原生载荷；高 rounds 受 lane 超时约束 |
| sha512crypt ID5 | 0x43C05000–0x43C05FFF | 6664 / 4664；64槽 | 原生载荷；高 rounds 受 lane 超时约束 |

输入/输出表中均未加公共头64字节。**同一 bitstream 只实现自己的算法页，其他算法页读0；五页不是五种算法同时驻留。** 所有算法页当前只读，写入被拒绝。页内 +00=存在1、+04=版本10000h、+08=算法编号、+0C=4、+10=快照有效时2否则0、+18=原生状态快照。参数区当前是常量而非可写参数镜像：+20 DES25；+24 MD5/SHA1000；+28 DES35/MD5 1000/SHA999999999；+2C bcrypt1/DES16；+30 bcrypt2/MD5与SHA256为12/SHA512为16；+34 MD5为1/SHA256为5/SHA512为6。其他读0。

盐、目标摘要、候选口令、rounds/cost 的实际下发依各算法原生 payload；公共描述符主要管理任务身份、长度及数量。寄存器页里有轮数常量不代表可通过写该地址改变 rounds，也不代表上限已通过运行测试。

### 12.3 单元与 CU 窗口（已实现的是观察骨架）

单元 u 基址：`0x43C08000 + u×0x1000`。u 从0开始；8单元到0x43C0F000，SHA512只有u=0..3。
CU c 基址：单元基址 + `0x100+c×0x100`。MD5/SHA256 c=0..2，SHA512 c=0..3，bcrypt/DES c=0。

| 窗口内偏移 | 单元窗口 | CU 窗口 |
|---|---|---|
| 00 | 存在=1 | 存在=1 |
| 04 | 非bcrypt有效=1；bcrypt=0 | 有效=0，尚未接 CU 遥测 |
| 08 | 快照 bit0 busy/bit1 done/bit2 error/bit3 initialized | 0 |
| 0C | 单元错误时10，否则0 | 0 |
| 38 | 每单元核数 | CU 编号 |
| 3C | 公共快照序号 | 同左 |
| 其余 | 0 | 0 |

这两类窗口均不能写。未实现逐 CU 参数寄存器、独立任务、独立启动/复位、逐 CU 完成数/周期和真实错误定位。以后若扩展，应同步版本/能力位、RTL、软件和测试，不以地址预留代替实现。

### 12.4 错误与结果处理

ARM 返回码当前包含：1 状态不允许，2 非法/保留字段，4 算法不匹配，5 长度/数量非法，6 格式不匹配，8 非bcrypt使用保留参数。运行首错：6 公共头不符，9 原生输入帧异常，10 原生状态报错，11 整批超时，15 原生结果帧异常，16 无握手看门狗。命令返回码与运行首错不可混用。

响应头16字：magic3152544Ah、流ABI、头长64、总长、算法、格式、task低/高、shard、batch、错误码、完成候选数、payload字节数、记录数、flags、保留0。flags bit0 为DES待完整复核，bit1为含填充槽位。错误响应通常仅头64字节；输出途中超时不得撤回已保持的 AXIS 帧，此时警告/NEED_RELOAD 也必须检查。软件还需验证原生 job/unit ID、剔除填充结果，并对DES完整校验。

## 13. Linux / UDP / DMA / 动态切换的实现边界

| 层次 | 已有内容 | 尚缺内容 |
|---|---|---|
| ARM Linux | 用户确认开发环境已安装；统一 PS 硬件描述已生成 | 当前板启动镜像、设备树、驱动绑定、实板启动证据 |
| UDP | 历史 bcrypt 主机模拟传输与 RTL demo 文件 | 当前 Linux PS 节点服务、可靠分包、重传、重复抑制、实际网络闭环 |
| AXI-Lite | 硬件从接口及 Python 回调封装 | Linux 安全映射/驱动、并发访问管理 |
| AXI-DMA | 硬件双向 Simple DMA、两路 IRQ | Linux 缓冲区/缓存同步、IRQ 收发/超时恢复、板上压力测试 |
| 算法切换 | 五套独立 BIT 与相同公共接口 | Linux FPGA加载链、驱动停止/恢复、任务取消/重试和切换回归 |

建议软件执行顺序（方案，尚未完成实现）：加载匹配 bitstream→读取 ABI/算法/能力并等 READY→校验并编码任务→写描述符和ARM→准备并启动S2MM→启动MM2S→收集 DMA 完成和壳状态→同步缓存并解析结果→确认DMA停止后RELEASE。Linux 用户态普通 Python 缓冲区不能直接当DMA物理内存。

安全全量切换方案：停止接单/标记未完成批次→等待或受控中止传输→停DMA及访问者/处理IRQ与驱动绑定→加载完整bitstream→按需要恢复设备树与驱动→重新初始化DMA和寄存器→验证ABI、算法和READY→恢复接单。不是单纯写“算法编号”寄存器，不是局部重配置；Linux对加载格式、FPGA Manager及设备树的具体支持还需在2020.1平台确认。

## 14. 关键问题、修复与剩余风险

- 已定位并修复：bcrypt旧WNS -0.228 ns（结果计数/校验长路径），MD5旧WNS -0.159 ns（lane BRAM至汇聚/公共校验路径）。bcrypt模48变为按握手递增的0..11计数；五工程加入官方全寄存AXIS Slice；导出前强制setup/hold门限。新构建结果见第4节。未整体替换AXI-Lite译码。
- 已补齐硬件中断：统一集成脚本接MM2S/S2MM至PS，五份XSA复核一致；尚未实现Linux服务/驱动中断闭环。
- 未解决：原生CPU初始化依赖配置，不能安全随意取消；NEED_RELOAD后需系统恢复。高rounds与固定lane超时冲突、每CU/传感器遥测缺失、BUILD_ID未注入。
- 性能风险：单批在途、输出RAM同步读吞吐、PS编解码/UDP补包及缓存管理均可能限制端到端收益；不能仅按核数量宣称加速倍数。
- 文档风险：v1.1 XLSX是设计稿，部分字段超前；README/早期PDF状态陈旧。实际RTL、最新status.txt和XSA审计优先，本次不改这些历史文档。
- 部署风险：未做当前AX7020镜像启动/双板测试；预调试ZU5EV的网口/JTAG结果不能替代。不要使用无IRQ旧XSA建立新平台。

## 15. 精确源码与验证入口补充

下列路径已通过本机文件清单核对（除了第7节文件外）：

- `E:/zhugenglei.work/john/john-ax7020-common/board/ps_config_alinx_2023_1.tcl`
- `E:/zhugenglei.work/john/john-ax7020-common/vivado/check_routed_timing.tcl`
- `E:/zhugenglei.work/john/john-ax7020-common/vivado/test_axi_shell.tcl`
- `E:/zhugenglei.work/john/john-ax7020-common/vivado/test_axi_native.tcl`
- `E:/zhugenglei.work/john/john-ax7020-common/sim/tb_axi_shell.sv`
- `E:/zhugenglei.work/john/john-ax7020-common/sim/tb_axi_native.sv`
- `E:/zhugenglei.work/john/john-ax7020-common/software/test_axi_protocol.py`
- `E:/zhugenglei.work/john/john-ax7020-common/reports/axi_validation_20261029.md`
- `E:/zhugenglei.work/john/john-ax7020-common/reports/pipeline_validation_20261029.md`
- `E:/zhugenglei.work/john/john-ax7020-bcrypt8/rtl/top/john_axis_top.v`
- `E:/zhugenglei.work/john/john-ax7020-descrypt8/rtl/descrypt8_axis_top.v`
- `E:/zhugenglei.work/john/john-ax7020-sha256crypt8/rtl/sha256crypt8_axis_top.v`
- `E:/zhugenglei.work/john/john-ax7020-sha256crypt8/rtl/sha256crypt_lane.v`
- `E:/zhugenglei.work/john/john-ax7020-sha512crypt4/rtl/sha512crypt4_axis_top.v`
- `E:/zhugenglei.work/john/john-ax7020-sha512crypt4/rtl/sha512crypt_lane.v`
- `E:/zhugenglei.work/john/john-ax7020-bcrypt8/host/sim_udp_transport.py`（模拟传输，非部署服务）
- `E:/zhugenglei.work/john/john-ax7020-bcrypt8/host/rtl_udp_demo.py`（历史演示，非已验收Linux节点）
- `E:/zhugenglei.work/john/outputs/axi-registers-20261028/AX7020_五算法分层AXI寄存器地址表_v1.1_设计稿.xlsx`

### 15.1 未提交状态（归档前快照）

HEAD完整值：`19a6e3bb8c49f2ab9e3e23299955a8a5adcc7832`；origin fetch/push均为 `https://github.com/gengleizhu/AX7020.git`。本次未联网验证远端最新提交。

Git显示61个已跟踪文件修改、1个未跟踪文件：

- 已修改源码：`john-ax7020-common/vivado/integrate_axi_shell.tcl`（新增调用中断集成脚本）。
- 未跟踪源码：`john-ax7020-common/vivado/integrate_dma_irq.tcl`。
- 五算法每套12项已修改产物/报告，共60项：BIT/HWH/XSA，以及drc、methodology、route_status、routed_timing、routed_utilization、status、synth_hierarchy、synth_utilization、system_rebuild。目录见第7节，文件扩展名分别为.rpt、status.txt、system_rebuild.tcl。
- 原状态均为工作区未暂存修改；本次没有stage、commit、push、覆盖源码或清理。新增根目录状态文档不包含在上述61+1快照中：现有 .gitignore 第2行的 /* 规则将其忽略，所以普通 git status 不显示它。文件已实际写入，但未受Git跟踪；后续若需纳入版本管理应经授权调整忽略规则或显式添加，本次不修改 .gitignore。
- 部分报告存在LF/CRLF提示；记录该提示，不擅自批量转换。build等被忽略目录不包含在上述计数，不代表其不存在。

## 16. 新对话恢复开发的优先级清单

1. **P0：确认版本边界。** 阅读本文件、检查新AGENTS.md、Git差异和最新构建报告；保留所有未提交内容。核对新MD5 XSA与审计hash；经用户授权后再做版本提交/冻结v2，不在归档任务内自行提交。
2. **P0：公共Linux平台。** 在用户虚拟机中定位已安装PetaLinux2020.1，确认AX7020准确硬件配置和启动介质；用带IRQ的MD5 XSA建立工程，审阅设备树/时钟/中断。先能可靠启动Linux和网口。
3. **P0：DMA与MD5闭环。** 确定驱动/缓冲区方案；先读身份与状态，再验证双向搬运、中断、缓存和错误恢复，完成一批及多批真实MD5对照测试。
4. **P1：UDP节点服务与Python接口。** 明确任务/分包ID、长度、校验、重传、重复抑制、状态/结果消息，完成真实网络链路而非仿真代理；服务开机自启与日志。
5. **P1：算法回归和切换。** 对其余四算法补齐原生编解码/真实运算/非法输入/背压/超时测试；验证完整bitstream切换、驱动恢复和NEED_RELOAD路径。高rounds先确定支持范围。
6. **P1：双节点与高层平台。** 两板不同分片并行；能力匹配、结果汇总/去重、掉线重新分配和任务完整性检查。
7. **P2：观测与交付。** 按验收要求补细化进度、CU遥测/传感器、版本指纹；测纯计算/端到端性能、长稳/断电断网，完成部署维护文档。未接入字段保持有效位0。

当前没有需要继续等待的五工程构建；“正在开发”指Linux系统集成阶段的待推进工作，不表示已有后台Linux构建或已编写完成的驱动。恢复后不要从头重建已通过的全部PL工程，先核实产物与版本，再推进第一真实系统闭环。

## 17. 2026-10-30 AX7020 实板启动与 AXI 复位故障闭环

### 17.1 已完成的实板验证

- AX7020 已从 PetaLinux 2020.1 的 SD 镜像启动，串口为 COM7（115200 8N1），PS 千兆网口链路正常。
- 已确认原始镜像不是卡在 pinctrl：`zynq_pinctrl_driver_init` 正常返回；实际先后卡在 `xilinx_gpio_driver_init` 与 `xilinx_vdma_driver_init`。
- U-Boot、Linux `devmem` 和 JTAG/DAP 复核均表明：旧 bit 的第一次 PS→PL AXI 访问得不到响应，会锁住 AXI/DAP；不是算法计算错误或网口故障。
- 极简 PS+AXI GPIO 工程排除了算法核、DMA、自定义寄存器壳和复杂互连。只有在配置后直接产生可靠低有效复位脉冲时，`0x41200000` 才能正常返回。

### 17.2 根因与修复

Vivado 实际参数显示 `proc_sys_reset/C_AUX_RESET_HIGH=0`。因此 AUX 输入是低有效。最初送入高有效脉冲时极性相反，完整工程仍会挂起；改为低有效 `resetn` 后故障消失。

公共修复文件：

- `E:/zhugenglei.work/john/john-ax7020-common/rtl/john_startup_reset.v`
- `E:/zhugenglei.work/john/john-ax7020-common/vivado/integrate_axi_shell.tcl`

`john_startup_reset` 在每次 PL 配置后保持 `resetn=0` 共 256 个 FCLK 周期，再同步释放；集成脚本把该信号接入低有效 AUX 复位输入。修复位于公共集成层，五算法后续重建均可继承，但截至本节记录时只完成了 MD5 完整工程实板验证，不能把其余四算法写成已验证。

### 17.3 MD5 修复版结果

修复版仍包含 8 个 `md5unit` 和 24 个真实 `md5core`，综合、布局布线和 bitstream/XSA 生成成功；100 MHz 路由时序通过。诊断产物：

- `D:/Documents/ChatGPT/john/output/diagnostics/md5crypt8_startup_reset/john_ax7020_md5crypt8_startup_reset.bit`
- `D:/Documents/ChatGPT/john/output/diagnostics/md5crypt8_startup_reset/john_ax7020_md5crypt8_startup_reset.xsa`
- `D:/Documents/ChatGPT/john/output/diagnostics/md5crypt8_startup_reset/timing.rpt`
- `D:/Documents/ChatGPT/john/output/diagnostics/md5crypt8_startup_reset/utilization.rpt`

正常 Linux 启动（未屏蔽 PL 驱动）结果：

- `xilinx_gpio_driver_init` 返回 0；
- `xilinx_vdma_driver_init` 返回 0；
- 系统进入 `ax7020_linux login:`；
- `0x41200000 = 0xA8000000`；
- `0x43C00000 = 0x4A435250`（公共 magic）；
- `0x40400000 = 0x00010002`；
- 三次 `devmem` 返回码均为 0；
- 临时地址 `169.254.173.138/16` 下，Windows 连续 4 次 ping 全部成功、时延小于 1 ms。

关键证据日志：

- `D:/Documents/ChatGPT/john/output/ax7020_normal_fixed_20261030_123745.log`
- `D:/Documents/ChatGPT/john/output/ax7020_pl_diag_20261030_123653.log`
- `D:/Documents/ChatGPT/john/output/ax7020_pl_diag_20261030_123934.log`

### 17.4 当前边界与下一步

- 当前 SD 卡上的旧 `BOOT.BIN` 仍包含未修复 bit。本次正常启动是在 U-Boot 暂停期间通过 JTAG 临时加载修复版后完成；断电后不会保留。
- 需在 PetaLinux VM 可用后，用修复版 bit、原 FSBL、U-Boot 和 DTB 重新打包 `BOOT.BIN`，复制到 SD 卡并执行一次无 JTAG 冷启动验证。
- 然后依次完成 DMA 两路 IRQ、缓存一致性、真实 MD5 任务闭环及 UDP 节点服务；其余四算法需重建并分别进行寄存器/驱动启动回归。
- 公共复位源码和当前工作区修改均未提交、未推送；不要清理现有未提交文件。

## 18. 2026-10-30 PetaLinux DMA 驱动与 MD5 实板闭环（最新状态）

本节后于 17.4，取代其中“SD 卡仍是旧 BOOT.BIN”“DMA 尚未闭环”等陈述。其余四算法仍未做本节级别的 Linux 实板验证，不能据此写成五算法均已完成。

### 18.1 PetaLinux 镜像与设备树

- 基于 `~/ax7020_linux/hardware/hard_1030/john_ax7020_md5crypt8_startup_reset.xsa/.bit` 重构 PetaLinux 2020.1，完整构建和 `petalinux-package --boot` 均成功。
- 新设备树增加根节点 `john-dma-client`，`compatible = "john,axi-dma-client-1.0"`，`dmas = <&dma 0>, <&dma 1>`，名称为 `tx`、`rx`。
- `system.dtb` 展开后确认 DMA 控制器 `0x40400000` 的 phandle 为该 client 引用，MM2S/S2MM 中断仍为 GIC 61/62（Linux IRQ 46/47）。
- initramfs 已包含 `lib/modules/5.4.0-xilinx-v2020.1/extra/john-dma.ko`、`/usr/bin/john-dma-test` 和 `/etc/modules-load.d/john-dma.conf`。
- SD 卡启动文件已更新；旧文件保存在第一分区 `backup_pre_john_dma_20261030_1512/`，可直接回滚。

新启动文件 SHA256：

| 文件 | SHA256 |
|---|---|
| `BOOT.BIN` | `a2e681f6a67717f08075dc6881e82151410e294a6831f3809310f44b991efc76` |
| `image.ub` | `b273508d9cf23b7a6ee63a59dfc132cfe17b865afe7ec35017bd57088762a12b` |
| `system.dtb` | `4dce530f93e70436a8e7b0957a1e1b1d8a13f9141376132b485aa44788077254` |
| `boot.scr` | `1628b69752247215cf8687de082d420367ec8048d301c118427e57ee2942d8fc` |

### 18.2 Linux DMA client 的实际实现

- 外部内核模块通过 DMAengine 的设备树 consumer 接口申请 `tx=dma1chan0`、`rx=dma1chan1`，而不是用户态直接写 DMA 物理地址。
- 驱动使用 32 位 coherent DMA 缓冲区；暴露独占字符设备 `/dev/john-dma`，限制发送 65,600 字节、接收 8,256 字节。
- 用户态先写一帧完整 Common request，再用 ioctl 传入 TX/RX 长度和超时；驱动严格先提交并启动 S2MM，再启动 MM2S，分别等待完成中断，失败时同步终止双通道。
- `john-dma-test` 负责校验 Common ABI、写 18 字任务描述符、ARM、执行 DMA、读取响应、SNAPSHOT，确认 DMA 已停止后 RELEASE。
- 驱动与测试工具只处理公共 ABI，不内置具体算法编码，因此后续可以复用到其余四个 bitstream；各算法 payload codec 仍由用户态/节点服务负责。
- Linux 5.4 不支持较新内核的 `dev_err_probe()`；已改为 `dev_err()` 加显式错误返回后，模块编译通过。这是版本兼容修复，不改变 DMA 数据通路。

开发副本与日志：

- `D:/Documents/ChatGPT/john/linux/john-dma/files/john-dma.c`
- `D:/Documents/ChatGPT/john/linux/john-dma/files/john_dma_uapi.h`
- `D:/Documents/ChatGPT/john/linux/john-dma-test/files/john-dma-test.c`
- `D:/Documents/ChatGPT/john/linux/john-dma-test/files/Makefile`
- `D:/Documents/ChatGPT/john/output/petalinux_hard_1030_20261030/ssh_full_transcript.log`
- `D:/Documents/ChatGPT/john/output/ax7020_board_dma_20261030/board_ssh_full_transcript.log`
- `D:/Documents/ChatGPT/john/output/ax7020_board_dma_20261030/board_ipv6_ssh_full_transcript.log`
- VM 实际 recipe 位于 `~/ax7020_linux/projects/ax7020_linux/project-spec/meta-user/recipes-modules/john-dma/` 与 `recipes-apps/john-dma-test/`；设备树覆盖位于 `recipes-bsp/device-tree/files/system-user.dtsi`。

### 18.3 MD5-crypt 真实闭环结果

- 无 JTAG 冷启动后，内核自动创建 `/dev/john-dma`；日志为 `ready: john-dma, tx=dma1chan0 rx=dma1chan1, max=65600/8256 bytes`。
- 测试帧为公共头 64 字节加 MD5 原生输入 9,992 字节，总 TX 10,056 字节；RX 为公共头 64 字节加原生结果 2,408 字节，总 2,472 字节。
- 首批 96 条候选真实运行通过：Common 状态完成数 96/96，MM2S/S2MM 中断各增加 1，Windows 软件参考逐条比较结果为 96/96 正确。
- 首批公共快照报告 `elapsed_cycles=845699`；八个算法单元的原生周期为 293595、540719、568447、582802、829931、828484、458094、540832。
- 随后连续运行 20 批全部通过；再运行 200 批（19,200 条候选）全部通过，两路中断计数同步累计到 221，无 DMA 超时、PL ERROR 或 NEED_RELOAD。
- 200 批单进程反复启动测试耗时 3.30 秒，当前测试工具端到端约 60.61 批/秒、5,818.18 条/秒。该数字包含每批进程创建、设备打开、`/dev/mem` 映射和命令往返开销，不等于常驻服务最终吞吐。
- 以 100 MHz 和最后一批约 845,455 周期估算，PL 批处理时间约 8.45 ms，纯硬件约 118.28 批/秒、11,354 条/秒；不同批次和最慢单元会有小幅波动，正式性能值应由常驻节点服务批量测试确认。
- 测试生成/校验脚本：`D:/Documents/ChatGPT/john/tools/generate_md5_dma_test.py`；证据文件位于 `D:/Documents/ChatGPT/john/output/ax7020_board_dma_20261030/`，其中 `md5_verification.json` 的 `pass=true`、`result_records=96`、`failures=[]`。

### 18.4 当前剩余工作（按优先级）

当前板上 `169.254.173.138/16` 是本次启动后临时恢复的开发地址，initramfs 仍按 DHCP 配置；开发 SSH 公钥同样只存在于当前 RAM 根文件系统。断电后可先通过固定 IPv6 链路本地地址恢复访问，但正式交付必须把网络、主机密钥/认证和节点服务以安全方式持久化。启动日志曾提示 SD 两个 FAT 分区未正常卸载；现有启动文件哈希已核对，后续应使用有序关机并安排离线文件系统检查，避免继续直接断电。

1. **P0：把 DMA client、测试程序、recipe、设备树覆盖及操作文档纳入 AX7020 Git 基线。** 当前真实运行副本在 Windows 工作目录和 VM PetaLinux 工程中；尚未擅自提交或推送。
2. **P0：开发常驻 Linux 节点服务。** 统一管理寄存器和 `/dev/john-dma`，提供任务队列、批量流水、超时/NEED_RELOAD 恢复、状态与进度采集，避免每批重新启动进程。
3. **P0：完成 UDP 协议及 Windows Python 客户端真实闭环。** 包含任务/分片 ID、长度与校验、重复抑制、应答、重传、结果完整性和心跳。
4. **P1：其余四算法实板回归。** 先用公共接口识别 bitstream，再分别运行真实 codec 对照；bcrypt 可变长度、DES 二次完整校验、SHA 高 rounds/超时边界需单独覆盖。
5. **P1：动态完整 bitstream 切换与恢复。** 停接单和 DMA、加载 bit、重新绑定/初始化、校验 ABI/算法/READY 后恢复；完成切换中断电、错误和未完成任务重试测试。
6. **P1：双板节点分片、掉线重分配与结果汇总。** 单板闭环通过不等于双节点上位机调度已完成。
7. **P2：性能与长稳。** 用常驻服务测纯 PL、DMA、编解码、UDP 和整链路吞吐，完成长时间循环、断网、重启和 SD 文件系统一致性测试。
