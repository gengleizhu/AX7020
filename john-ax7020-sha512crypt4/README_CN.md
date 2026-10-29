# PYNQ-Z2 John SHA512crypt 四算法单元工程

目标为 PYNQ-Z2 / XC7Z020CLG400-1，工具为 Vivado 2018.3。工程使用 John 原始 SHA512crypt 算法单元，外接 PS、AXI DMA 和状态 GPIO。4 个算法单元各含 1 个 John 专用软 CPU、4 个物理 SHA-512 压缩核及 16 个线程槽，总计 4 个软 CPU、16 个计算核、64 个任务槽。

## 工程入口与结果

- Vivado 工程：`build/soc/john_sha512crypt4.xpr`。
- 可重建脚本：`vivado/create_soc.tcl`、`scripts/build.ps1`。
- PYNQ overlay：`deliverables/john_sha512crypt4.bit` 与同名 `.hwh`。
- Windows 示例请求：`deliverables/example_request.bin`，对应 `sim/example_jobs.json` 中的 64 个 1000-round 任务。
- 最终验证结果：`reports/summary.json`；仅在全部必要仿真、层级和实现检查通过后生成。

完整 PS + DMA + PL 布局布线结果：

| 项目 | 数值 | XC7Z020 占用 |
|---|---:|---:|
| LUT | 26,948 | 50.65% |
| FF | 32,928 | 30.95% |
| BRAM36 等效块 | 110 | 78.57% |
| DSP | 0 | 0% |
| 目标时钟 | 100 MHz | — |
| WNS | +0.421 ns | — |
| WHS | +0.013 ns | — |
| 基于建立时间余量估算的 Fmax | 104.40 MHz | 非扫频实测 |

4 单元已经完成布局布线。全部 59,147 条可布线网络完成布线；设计无算法黑盒，DRC 无 Error。报告保留 1 项无负载网络 Warning 和 2 项 DMA FIFO RAM 写模式 Advisory，详情见 `reports/soc/drc.rpt`。PS 配置使用已有的 PYNQ-Z2 参考配置；其 DDR 参数和板上行为仍需实物验证。

## 架构与模块

PS DDR → AXI DMA MM2S → `sha512crypt4_axis_top` → 4×`sha512crypt_lane` → 4×原始 `sha512unit`。

各单元独立执行输入任务，返回 ID64 和完整 digest512。适配层及时收走原始单元的 2 位输出，避免输出缓冲区堵塞；外层按单元顺序汇聚，经过 AXI DMA S2MM 写回 DDR。

输入适配遵循原始 `arbiter_tx.v` 的约定：包头独占一字节，结束控制标记与第 104 个有效数据字节同时发送。SHA512 的 FIFO 会收下带结束标记的该字节；额外发送尾字节会破坏后续任务的 64 位拼接边界。当前实现已针对这一点修正。

- `rtl/sha512crypt4_axis_top.v`：请求头解析、四路分发、有序输出、AXI 帧检查及汇总状态。
- `rtl/sha512crypt_lane.v`：16 任务装载、原始字节协议转换、576 位结果收集、输入范围校验、周期计数和超时保护。
- `vendor/fpga-sha512crypt/sha512crypt/unit/sha512unit.v`：原始算法单元；保留软 CPU、微码、控制器、引擎及 4 个 SHA-512 核。
- `rtl/cpu_vivado.v`：原始软 CPU 的 Vivado 兼容副本。
- `rtl/asymm_bram.v`：以 XPM 实现原始非对称 BRAM 接口；同步读取延迟为一周期。
- `host/codec.py`：独立 hashlib 算法参考、crypt-base64 编码、请求与结果编解码。
- `host/pynq_demo.py`：PYNQ 2.4 下的 DMA 驱动及结果校验示例，尚未上板。

原始 John CPU 的 `iop_sets_cf` 时序赋值由阻塞改为非阻塞，避免 XSim 的跨过程竞态；其余 CPU 内容与原始文件相同。原始 SHA-512 计算逻辑和微码均未修改。编译定义 `SIMULATION` 是原始 John 工程选择可综合 RTL 实现的开关，包含在综合流程中，用来代替 ISE 黑盒声明；`UNIT_CONF=0` 选择真实核。

源码来源：[用户指定的 John SHA512crypt 目录](https://github.com/gengleizhu/john/tree/bleeding-jumbo/src/ztex/fpga-sha512crypt)。本地缓存的算法子树 Git SHA 与该目录查询值一致：`5ea292372b9796a31b10d9a848cbe0d0013fd4b4`。79 个原始文件已逐个核对 Git blob，记录于 `reports/source_provenance.json`，版权声明保留。

## 输入边界与协议

算法为 `$6$` SHA512crypt，默认 5000 rounds。主机接口允许口令 0～64 字节、盐 1～16 字节，禁止 NUL，盐禁止 `$`；长度按字节计算。硬件检查 rounds 范围、长度字段、保留字段及 AXI 帧，字符内容检查由主机完成。

综合默认 `MIN_ROUNDS=1000`，最大合法 rounds 字段为 999,999,999。每单元另有 100,000,000 周期安全超时，因此超大 rounds 字段虽然格式合法，任务仍可能触发超时。协议故障、超时或任务开始后的外部复位会锁定接口，需要重新加载 overlay；复位不能清除原始 John 核的内部执行状态。

所有外部字均为小端 32 位；摘要输出字节与独立软件返回的 64 字节原始摘要一致（以仿真逐字比对为准）。外层请求和响应魔数分别为 `0x34534853`、`0x34524853`，单元响应魔数为 `0x3453484A`。

| 层级 | 格式 | 字数 |
|---|---|---:|
| 单任务输入 | rounds32、salt_len32、salt128、ID64、key_len32、reserved32、key512 | 26 |
| 单单元请求 | 16 个任务 | 416 |
| 完整请求 | magic、事务 ID、4 个单元请求 | 1666（6664 字节） |
| 单单元结果 | magic、cycles、16×(ID64+digest512) | 290 |
| 完整响应 | magic、事务 ID、4×(unit_id+单单元结果) | 1166（4664 字节） |

每批必须恰好 64 个不同任务 ID，由主机校验唯一性。`cycles` 从单元接收首个输入字开始计数，到全部 16 个结果收集完毕为止，包含装载及内部输出开销，不是单次 SHA-512 压缩所需周期。

GPIO 状态：bits[31:24] 固定为 `0xA5`；bits[19:16] 为四单元错误位；bits[11:8] 为忙碌位；bit2 为外层协议错误；bit1 为复位错误；bit0 为事务进行中。健康空闲值为 `0xA5000000`。

本工程沿用原始算法单元的内部输入协议，外部为本工程的 DMA 协议；原始 ZTEX USB 通信顶层和 John CPU 插件未接入该 overlay。

## 验证与重建

```powershell
python -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
.\scripts\build.ps1
```

工程已带独立虚拟环境。首次运行需可用 Python；默认 Vivado 路径为 `C:\Xilinx\Vivado\2018.3\bin\vivado.bat`，可通过 `build.ps1 -Vivado ...` 调整。

验证分为：

1. 独立 hashlib 参考与 Passlib 交叉检查，包括默认 5000-round 向量及 16 个 1000-round 样本。
2. `tb_known.sv`：单原始单元，16 个标准 1000-round 任务，覆盖 0～64 字节口令和 1～16 字节盐，比较全部 512 位摘要。
3. `tb_sha512crypt4.sv`：四单元共 64 任务，使用仿真专用 10 rounds，检查全部 16 个核活动、四单元并行、输出 ID、完整摘要、末字标记和输出反压。仅该测试实例设 `MIN_ROUNDS=1`，交付 bitstream 保持 1000。
4. `tb_invalid.sv`：8 类非法输入检查；主机测试覆盖格式、摘要、结果解码、DMA 顺序及失败锁定行为。
5. 完整 SoC 综合、实际层级核数量检查、布局布线、建立/保持时间、DRC 和 bit/hwh 核对。

```powershell
.\.venv\Scripts\python.exe host/cli.py encode sim/example_jobs.json deliverables/example_request.bin
.\.venv\Scripts\python.exe scripts/audit.py
```

### 本次实际验证结果

- 四单元并行测试通过：64 个任务、每任务 10 rounds、59,099 周期；确认 4 个单元同时活动、全部 16 个物理 SHA-512 核活动，全部摘要一致。
- 标准轮数测试通过：单单元 16 个任务、每任务 1000 rounds，全部摘要一致；单元收齐结果耗时 750,135 周期，完整测试事务耗时 750,747 周期。
- 8 类非法输入测试通过；5 项主机单元测试通过；独立参考与 Passlib 的 16 个标准轮数样本及默认 5000-round 向量交叉检查通过。
- 最终审计 `AUDIT_PASS`；布局布线、时序及生成的 bit/hwh 文件已核对。原始 79 个源码文件的来源校验通过。

四单元 1000-round 全批次 RTL 仿真尚未运行；本次覆盖是“四单元低轮数并行”与“单单元标准轮数”两部分，不能混称为四单元标准轮数实测。5000 rounds 仅完成软件参考交叉验证。

按标准测试的任务组合，假设四单元批次延迟相同，100 MHz 下模型为 `4 × 16 × 100,000,000 / 750,135 ≈ 8,532 次候选校验/秒`。这不是板上吞吐，也不是默认 5000 rounds 的吞吐或相对 CPU 的加速倍数。

目前没有板卡。仿真使用真实 RTL，但不覆盖 ARM 执行、真实 DMA/DDR、物理温度功耗或网络集群。上述吞吐模型未计 PS 和 DMA 开销；板上吞吐字段保持空值。拿到板卡后应先验证 overlay 加载和 DMA/DDR，再用相同输入与轮数测量端到端耗时并与 CPU 基线比较。
