# 后续集成接口与风险记录

## 从阶段1转入阶段2

阶段2首先建立PS Ethernet → PS UDP → DDR → AXI DMA → PL Loopback → DMA → UDP通道。
采用PYNQ-Z2已有PS千兆以太网，不在PL重新实现MAC/IP/UDP。
同钟仿真FIFO模型不能复用于板级设计，需重新实现并验证AXI-Stream和跨时钟域接口。
阶段1报告通过不代表这些通道已有实现。

## 算法接口

输入适配保留John字节流顺序，核对旧input_fifo的16bit高字节先出约定，
不把AXI的字节lane顺序直接等同于旧USB端口数值。
输出通过包Header中的长度加18字节恢复包边界，并包含完整Payload Checksum；
TLAST只在最后一个有效AXI字产生，不能使用Core empty作为包结束。
接收DMA应先准备再启动输入，队列满必须形成反压，禁止默默丢弃结果。

## 初始化/算法加载

Core的init_ready表示需要P/MW/S数据，不是bitstream校验通过标志。
后续AXI-Lite控制应另设算法ID、构建版本、Core数、初始化状态、错误原因和运行状态。
加载bitstream时先停止接收任务，等待或明确取消旧任务，再清理DMA/会话，
加载可信镜像后重新建立算法ID检查和已知答案检查。
原Core没有显式reset，软复位设计必须覆盖微码、地址、缓存、代理和仲裁器。

## 进度

mode_cmp=0没有D2和原num_processed统计，主机应依据去重后的D3结果计数。
已发送/已接收/已进入Core/已返回结果需要分别记录；不得将UDP ACK等同于计算完成。
批次按Salt/subtype/Cost分组；更换配置前等待前批次已接收的工作全部完成或清理。

## 多核/多节点

每块板目标8个物理Core。必须统计实际综合网表的Core实例，并验证多个Core同时Busy。
初始可用一个Proxy带8Core，但原arbiter中TOTAL_IN_PROCESSING等计数基于Proxy参数，
后续特别检查mode_cmp切换时的在途统计和初始化广播，不认为改参数即完成8Core。
节点独立Session、任务代次及结果去重用于断线重派；某一节点断线不应阻塞另一节点。

## 物理状态

温度、片上电源电压、时钟/复位状态应来自PS/XADC及实际硬件寄存器。
需要区分芯片内部电压监测与整板供电/功率，不能以XADC读数冒充整板功耗。
本阶段未读取实物传感器，不提供模拟的硬件监测数据。

## 输入有效性

原PL错误标志是粘滞的。PS在向PL送数前完成包重组、Checksum和业务语义校验。
主机验证标准bcrypt字符串、合法subtype、Salt/哈希Base64、Cost、字典编码与72字节语义。
不能仅依赖PL检查来阻止零迭代数、过大任务或错误目标。
