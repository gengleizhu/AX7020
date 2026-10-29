# 阶段3/4：无板卡单核集成与直接8核实现

## 验收口径

用户最新要求为直接8核，不再执行2/4核逐档验收。单核保留为阶段3通信集成基线。
最终数字以 `reports/stage34/validation.md` 及其原始日志为准，不能仅以脚本存在判定通过。
没有板卡，所以真实PS/Linux、DDR、以太网、DMA运行及物理传感器未验收。

本次包含两个相互独立的证据链：

1. Windows真实UDP socket → 本机仿真桥 → AXI接口测试驱动 → 原John解析/仲裁/Proxy/算法核 → AXI输出 → UDP返回。
2. PS+DDR接口+AXI互连+AXI DMA+原John八核的完整XC7Z020设计，执行综合、布局布线、静态时序分析及bitstream生成。

第1条验证应用协议和RTL功能，但不模拟ARM执行Linux，也不把localhost流量当作千兆网卡测试。
第2条验证工具能否把完整设计实现到器件上，但不代表板级正确运行。

## RTL层次

```text
john_axis_top（同钟100MHz）
  axis_to_john_pktcomm：32位AXIS → 8位原始John流
  john_stream_engine：原bcrypt.v真实实现的接口移植副本
    inpkt_header / template_list_b / word_gen_b
    bcrypt_expand_key_b / bcrypt_cmp_config / bcrypt_data
    bcrypt_arbiter（NUM_CORES=1，含义是1个Proxy）
    outpkt_bcrypt / outpkt_checksum / 可综合output_fifo
  bcrypt_wrapper（NUM_PROXIES=1）
    bcrypt_proxy（NUM_CORES=8）
      bcrypt_core × 8（每核保留fsm/unit/P/S）
  john_pktcomm_to_axis：16位结果流 → 32位AXIS与TLAST
```

`SIMULATION`预处理宏启用原John真实RTL，**不是**用假结果替代算法。
`john_stream_engine.SIMULATION`参数保持0，报文校验不会被禁用。
`PROXY_CONF=0x108`：1级寄存器、8个Core、非Dummy。
原始文件保留在 `rtl/john_original`，移植副本及补丁在 `rtl/integration`，生成器在 `scripts/prepare_integration.py`。
六个原始算法文件没有改动。沿用阶段1已记录的word_gen_b遗漏声明补丁。

### 为什么改变输入FIFO边界

原USB接口是16位输入、高字节先出，而AXI DMA按lane0先出，最后一拍还可能只有1/2/3个有效字节。
如果只交换字节再补零，奇数长度John流可能被插入不存在的数据，破坏下一包报文头。
因此移植副本只替换原输入FIFO边界：AXI串行器保持单字节，原解析器以原`rd_en`条件消费。
原解析器、字典处理、算法、任务ID和校验和编码不变。

## AXI接口约定

- 全部计算、AXIS、FIFO使用PS FCLK0的同一个100MHz时钟；不存在自制异步FIFO。
- 输入32位、低字节lane0最先发送；合法TKEEP为1/3/7/F，非TLAST拍必须为F。
- 输入TLAST是一次DMA传输边界，不是John包边界。允许一个John包跨多个DMA事务，也允许一次DMA包含多个John包。
- 输出从John头读取Payload长度，输出TLAST绝不来自Core empty。
- 当前只接收mode_cmp=0产生的D3：30字节Payload，加18字节包头/校验，总长48字节、12个32位拍。
- 输出遇到非D3或非30字节Payload会停止并报错；未来支持D2/D4时须扩展适配器及测试。
- 输出FIFO16个16位字，计数器有界、可综合；满时反压一直传回John输出仲裁链。
- TVALID且TREADY=0时，TDATA/TKEEP/TLAST保持不变。

### 初始化与复位

原Core依靠配置初始化的寄存器启动，每个候选结束后仍按原机制重新请求P/S初始化。
适配器支持启动复位，但原Core并无完整运行时reset。
顶层一旦接收过AXIS数据，再拉低resetn会置reset_fault，禁止重新接受输入。恢复方式是重加载可信overlay。
这是一项明确的故障保护限制，不声称已经实现任意时刻软复位/任务取消。

状态字由AXI GPIO只读输入映射到PS：

| 位 | 含义 |
|---|---|
| 31:24 | 固定签名0xBC |
| 23:20 | 保留 |
| 19 | reset_fault |
| 18 | 输出格式错误 |
| 17 | 输入AXIS错误 |
| 16 | 原John error_r |
| 15:8 | 原John app_status |
| 7:0 | 原John pkt_comm_status |

签名不是密码学认证，也不是算法自检通过标志。上板首次使用仍须运行已知答案检查。

## Windows UDP仿真桥

入口：`host/rtl_udp_demo.py`。默认8核；可选单核用于阶段3基线。

外层协议含版本、Session、请求ID、分片号/总数、总长度、Payload长度和CRC32。
外层CRC32与John累加取反Checksum是不同层次，不能混用。
最大UDP Payload1200字节；当前测试特意用73字节分片，覆盖跨包头/载荷的重组。
测试注入倒序、重复、缺片；COMMIT发现缺片后请求补发，重复COMMIT不会重复启动计算。
结果由客户端轮询状态后分片拉取。每条请求有有限重试和总超时。

该桥只绑定127.0.0.1；一次进程只接收一个会话，只用于离线验收，不是生产板端服务。
输入先完整重组并验证原John包及本测试支持的字典业务参数，才创建新的XSim运行目录。
服务端不读取expected.json、不执行CPU bcrypt，也不会在仿真失败时返回参考答案。
客户端收到实际输出后再检查完整包、Checksum、Packet/Word/Generation ID和预期结果。
并行结果允许乱序，以ID匹配，不以返回位置匹配。
目前该入口限32个以NUL结尾的候选，每个不超过71字节；阶段1另有原Core 72字节边界验证。

复现示例（输出目录必须不存在，避免旧数据混入）：

```powershell
python host/rtl_udp_demo.py --cores 8 --cost 4 --output reports/my_new_8core_run
```

## 完整SoC工程

`vivado/create_soc.tcl`使用：

- ZYNQ7 PS：保留PYNQ-Z2官方DDR/MIO/PS以太网配置；
- GP0 → AXI控制互连 → DMA控制寄存器与状态GPIO；
- DMA MM2S/S2MM → AXI内存互连 → HP0 → DDR；
- DMA流接口 → 原John八核PL；
- proc_sys_reset同步释放计算域复位；
- 同钟100MHz，DMA Simple模式，无SG，启用DRE以支持字节长度。

PS配置取自[Xilinx PYNQ v2.4的PYNQ-Z2 base.tcl](https://github.com/Xilinx/PYNQ/blob/v2.4/boards/Pynq-Z2/base/base.tcl)，其脚本标明Vivado 2018.3。
下载原文与版权保存在 `third_party/pynq_reference/base_v2_4.tcl`，重建无需联网。
只提取PS配置块，未引入原base overlay的HDMI、MicroBlaze等无关模块。
完整系统的PL核在BD外的HDL顶层连接，BD保留PS和DMA；自动生成顶层脚本会严格检查接口集合。

官方PS预设触发DDR DQS skew负值警告（lane2 -0.009、lane3 -0.033）。
这些板级参数未为了消除警告而随意改写；上板前须核对实际镜像PS初始化及硬件版本。
项目未安装或修改系统级Vivado板卡库，也未修改用户其它工程。

## 板端程序准备

`board/dma_benchmark.py`按照[PYNQ v2.4 DMA源码](https://github.com/Xilinx/PYNQ/blob/v2.4/pynq/lib/dma.py)的接口准备，
采用Xlnk连续内存及DMA寄存器，兼容Python3.6；原John codec也做了无dataclasses依赖的兼容调整，并重跑原C兼容测试。

- 先准备S2MM，再启动MM2S；
- 每个D3包有一个TLAST，所以每次接收48字节，并为后续结果重新启动接收；
- 不先阻塞等待全部MM2S完成，避免字典输入阻塞与输出积压形成死锁；
- 发送前flush、接收后invalidate，检查DMA错误、超时、PL状态和结果ID；
- 超时后不释放可能仍被DMA访问的连续内存，标记会话不可重用；管理员重新配置后再恢复。

该程序当前只通过Mock调度测试，不能声称实板DMA已通过。它没有网络bitstream加载接口。
远程认证、生产UDP服务和双板任务管理属于后续阶段，不随本阶段仿真桥自动获得。

## 性能计数与限制

Core周期：crypt_ready从1变0至结果empty从1变0。
批次周期：首个输入AXIS握手至最后一个D3输出TLAST握手。
批次吞吐量：32×100000000/批次周期。包含本测试的初始化、排队、输出反压和填充/排空开销。
每批32项由两个不同长度的口令交替构成；输入可重复，但Word ID逐项唯一，验证的是32次独立任务而非32个不同口令。
不同口令长度可能使微码执行周期略有差别，因此报告最小/最大值。

Fmax为固定布局布线网表根据关键路径余量外推的估算；只在100MHz约束下完成实现。
实际板上时钟上限、PS/DMA端到端吞吐量和长时间稳定性必须等板卡测试，报告保留“未测”。

实现报告保留工具警告：原校验和DSP未加输入流水，原S盒BRAM输出未加寄存器，
以及AXI协议转换IP内部的LUT驱动异步复位警告。没有通过忽略时序路径来消除这些警告。
完整系统DRC无Error，但“无Error”不等同于所有方法学警告已消除。

## 如果后续8核实现出现失败

当前是否成功由报告与原始工具日志决定。资源或时序失败必须保留失败阶段和最差路径，不能只降低验收标准：

1. 资源不足：查看真实核心与外围资源分解，优先调整缓存深度及S盒BRAM/LUT RAM映射；不得将真实Core换成Dummy。
2. 核心内部路径超时：根据路径报告评估降低目标频率，或修改微码配合存储输出流水；后者须完整重跑算法回归。
3. Proxy/仲裁扇出拥塞：评估2个Proxy×4核、寄存器级数及布置区域；重新验证初始化广播和结果ID。
4. DMA/互连路径超时：增加AXI寄存器切片，并验证TLAST、背压和延迟变化。
5. 任何调整均重新生成完整系统布线报告，不以单Core数字乘8代替。
