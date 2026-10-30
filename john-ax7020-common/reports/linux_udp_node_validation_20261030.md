# AX7020 Linux 常驻 UDP 节点实板验证（2026-10-30）

## 结论

MD5-crypt 单节点链路已在 AX7020 实板形成真实闭环：Windows UDP 客户端完成任务分片和可靠传输，PetaLinux 常驻服务通过 `/dev/john-dma` 与 FPGA 交互，最终 96/96 个结果与软件参考值一致。连续批次和协议故障注入均通过。该结果不能外推为其他四种算法或双节点已经验收。

## 镜像与运行环境

| 项目 | 实测值 |
|---|---|
| 板卡 | ALINX AX7020 / XC7Z020 |
| Linux | 5.4.0-xilinx-v2020.1, ARMv7 |
| Bitstream | MD5-crypt，8 算法单元 × 3 Core |
| PL 时钟 | 100 MHz |
| UDP 地址 | `169.254.173.138:42000`（本次临时配置） |
| image.ub SHA256 | `533a6c12f149e0863a423436e3f8f99a42cb4fc5a4859de075ca05224959dcef` |
| 服务 | `/usr/bin/python3 /usr/sbin/john-node --bind 0.0.0.0 --port 42000` |
| 原生硬件库 | `/usr/lib/libjohnhw.so` |

SD 卡更新前的镜像已备份到：

```text
/media/sd-mmcblk0p1/backup_pre_udp_node_v3_20261030_080059/image.ub
```

旧镜像 SHA256 为 `3325695de9fdb39513f7068ea33259cc38bbf8268406ffd25b5796e1e46e5139`。

## 已验证功能

1. SysV init 自启动：`/etc/rc5.d/S95john-node` 正确启动服务。
2. DISCOVER/CAPS：返回寄存器 ABI、流 ABI、算法编号、单元数、Core 数、时钟、能力和 PL 状态。
3. BEGIN/DATA/COMMIT：10,056 字节 Common request 分片上传并异步启动硬件。
4. STATUS：完成后报告 2,472 字节结果、96 个完成项和约 845k PL 周期。
5. RESULT：结果分片读取、重组与 Common response 解析成功。
6. 真值：96 个 MD5-crypt 摘要全部与软件参考实现一致。
7. DMA：首批执行后两个 `xilinx-dma-controller` 中断均从 0 增加到 1；连续执行时两路计数同步增长。
8. 稳定性：100 个连续批次，共 9,600 个候选，末批仍为 96/96 正确，服务未退出。
9. 故障注入：接受乱序片和内容相同的重复片；拒绝内容冲突的重复片；拒绝数据不完整时的 COMMIT；补齐后可正常计算并返回正确结果。

## 性能解释

100 个连续批次通过当前参考客户端耗时 11.429 秒，端到端约 839.96 candidates/s。这个数值包含 Windows Python、UDP 每片 ACK、状态轮询、结果逐片读取和文件外的控制开销，不代表 PL 核的极限吞吐。单批 PL 计算约 845,256 周期，在 100 MHz 下约 8.45 ms；后续应通过滑动窗口/累计 ACK、请求流水和批次队列降低网络往返占比。

## 已解决问题

旧版 Python 服务直接通过 `mmap` 缓冲区写 AXI-Lite 描述符，在偏移 `0x100` 处触发 ARM `external abort on non-linefetch`。新版改为常驻 C 共享库，以对齐的 `volatile uint32_t` 访问寄存器，并在同一进程中持久保持 `/dev/mem` 映射和 `/dev/john-dma` 文件描述符。截至本次检查，两路 DMA 中断计数均为 142，新版运行中未再出现该异常。

## 尚未验证

- bcrypt、descrypt、sha256crypt、sha512crypt 的 Linux/UDP 实板闭环。
- 固定 IP、SSH 主机密钥、认证配置和日志的跨重启持久化。
- 双板注册、能力调度、分片并行、掉线重分配和结果汇总。
- UDP 高吞吐窗口协议、多任务排队、运行中安全取消。
- UDP v1 目前只有 CRC 和任务身份字段，没有认证与加密；部署到非隔离网络前需增加消息认证或使用受控专网。
- 长时间压力、断电恢复、异常 Bitstream 和 DMA 超时恢复。

## 复测入口

```powershell
python john-ax7020-common\host\john_udp_client.py --host 169.254.173.138 discover
python john-ax7020-common\host\john_udp_client.py --host 169.254.173.138 run md5_request.bin md5_response.bin
python john-ax7020-common\software\test_john_udp_integration.py md5_request.bin md5_response_fault.bin --host 169.254.173.138
```
