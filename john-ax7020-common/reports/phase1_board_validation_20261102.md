# 2026-11-02 AX7020 实板验证

平台：XC7Z020，Vivado 2020.1，Linux 5.4；COM7 115200；板卡169.254.173.138，UDP42000。

| 算法 | 实板结果 |
|---|---|
| bcrypt8 | cost4，32个48字节结果包与参考匹配，公共响应1600字节 |
| descrypt8 | 128候选，8核掩码为1/2/4/8/16/32/64/128，与参考匹配，响应232字节 |
| md5crypt8 | 既有基线96/96参考匹配；最新bit切换返回后的复测失败：PL状态0x00070118，error=6，detail=0，待定位 |
| sha256crypt8 | 1000轮，96/96摘要匹配，响应4008字节 |
| sha512crypt4 | 1000轮，64/64摘要匹配，响应4728字节 |

上述UDP测试覆盖乱序、重复、冲突重复、不完整提交拒绝、DMA和结果重组。DES验证的是原始核的候选比较掩码，不等同于完整摘要输出验证。

## 修复及操作

1. bcrypt原生初始化依赖任务数据，公共壳原先等待原生初始化才接收任务，形成互锁。算法1复位后允许收包；其余算法保留初始化门控。五算法公共壳仿真通过，bcrypt重建WNS=0.956ns，时序通过。
2. 小于单个UDP载荷的bcrypt请求使原测试的“不完整提交”前提不成立；测试改为拆成两个片段。
3. 只停止服务后JTAG重配置会使DMA软件状态与硬件状态不一致。实测PL完成但DMA超时，重新绑定后恢复。可靠测试顺序如下（每步确认成功后继续）：

```sh
/etc/init.d/john-node stop
rmmod john_dma
echo 40400000.dma > /sys/bus/platform/drivers/xilinx-vdma/unbind
# 此处由Windows Vivado通过JTAG加载相应bitstream
echo 40400000.dma > /sys/bus/platform/drivers/xilinx-vdma/bind
modprobe john_dma
/etc/init.d/john-node start
```

服务运行检查应使用 `/etc/init.d/john-node status`；`pidof john-node`不能可靠识别Python解释器进程，此前据此判断服务退出不正确。

## 证据与限制

请求、响应和verification.json：`D:/Documents/ChatGPT/john/output/phase1_board_validation_20261102/`。公共XSA审计：`john-ax7020-common/reports/xsa_common_audit_20261102.json`。生成与核对工具：`john-ax7020-common/scripts/phase1_board_vectors.py`。UART命令工具：`john-ax7020-common/scripts/board_uart_command.ps1`。

测试结束已加载最新MD5 bitstream，初始READY=1，但提交既有md5_request.bin后返回上述错误，当前保留失败现场。未写入新的启动镜像。优先定位最新MD5请求兼容性，不能宣称五份最新bit全部实板通过。随后将切换生命周期纳入Linux加载服务，完成连续多批与不同参数回归、长稳和异常恢复、双节点调度。未宣称Linux FPGA Manager在线加载已完成。本次修改与构建产物尚未提交Git。
