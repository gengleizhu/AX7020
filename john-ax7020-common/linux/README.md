# AX7020 Linux DMA 与常驻 UDP 节点

该目录保存与五算法公共 AXI/Stream ABI 配套的 Linux 组件。当前 MD5-crypt 已在 AX7020 实板完成 DMA、常驻 UDP 服务和软件真值闭环；其他四种算法尚未做 Linux/UDP 实板闭环。

## 组件

- `john-dma/`：算法无关的 DMAengine client，生成 `/dev/john-dma`。
- `include/john_dma_uapi.h`：驱动与用户态共享 ioctl ABI。
- `node/john_node_service.py`：常驻节点服务，启动后只打开一次 DMA 和寄存器映射。
- `node/libjohnhw.so` 源码：以对齐的 C `volatile uint32_t` 安全访问 AXI-Lite，避免 Python 缓冲区写 MMIO。
- `node/john_udp_protocol.py`：节点和上位机共享的 UDP v1 编解码。
- `node/john_health.py`：低频采集 Linux、网口和 XADC 健康数据，不进入 DMA 工作线程。
- `../host/john_udp_client.py`：Windows/Linux 上位机命令行客户端。
- `../software/test_john_udp_integration.py`：实板乱序、重复、冲突片、提前提交、DMA 和结果重组测试。
- `petalinux/`：PetaLinux 2020.1 recipes 和设备树片段。
- `deploy_to_petalinux.sh`：将源码复制到已有 PetaLinux 工程的辅助脚本。

## UDP v1 工作流

每个 UDP 数据报为 64 字节网络序头加不超过 1136 字节载荷，总长度不超过 1200 字节，避免普通以太网 IP 分片。头和载荷分别有 CRC32。

```text
DISCOVER -> CAPS
BEGIN    -> ACK
DATA...  -> ACK（每片确认，重复片必须字节一致）
COMMIT   -> ACK（硬件工作线程异步执行）
STATUS   -> STATUS_REPLY（轮询 QUEUED/RUNNING/DONE/ERROR）
RESULT...-> RESULT_REPLY（分片读取结果）
RESULT_ACK -> ACK（上位机确认后释放结果缓存）
HEARTBEAT -> HEARTBEAT_REPLY（轻量在线、队列和 Bitstream 状态）
HEALTH    -> HEALTH_REPLY（Linux、网络、XADC、DMA 和 Bitstream 健康信息）
```

关键保证：

- `session + task + shard + batch` 唯一标识一次任务。
- `sequence` 唯一标识一次 UDP 请求；客户端超时后原样重发。
- BEGIN、DATA、COMMIT 和 RESULT 都按幂等方式处理，ACK 丢失不会重复启动硬件。
- DATA 的重叠字节只有内容完全相同时才接受，防止重传覆盖不同数据。
- PL 仍一次执行一个任务；PS 默认可缓存 8 个在途任务和 16 个结果，网络接收、健康采样和硬件工作线程分离。
- 结果收到 `RESULT_ACK` 后释放；未确认结果默认保留 600 秒，容量满时暂停启动下一项而不覆盖旧结果。
- 算法 payload 保持原样，服务端只验证 Common request header、bitstream 算法和长度。

头部共 16 个 `uint32`，均为网络字节序：

| 字 | 字段 |
|---:|---|
| 0 | magic `JNP1` |
| 1 | version `0x00010000` |
| 2 | message type |
| 3 | flags |
| 4 | session |
| 5 | sequence |
| 6/7 | task ID low/high |
| 8 | shard ID |
| 9 | batch ID |
| 10 | fragment offset |
| 11 | total length |
| 12 | payload length |
| 13 | payload CRC32 |
| 14 | response/error code |
| 15 | header CRC32（计算时本字段为0） |

## PetaLinux 集成

先在仓库所在 Linux/共享目录执行：

```bash
cd john-ax7020-common/linux
./deploy_to_petalinux.sh ~/ax7020_linux/projects/ax7020_linux
```

把 `petalinux/device-tree/john-dma-client.dtsi` 中的节点合并到工程原有 `system-user.dtsi`，不要覆盖 ALINX 的 USB、PHY、SD 和 UART 配置。然后执行：

```bash
source ~/petalinux/2020.1/settings.sh
cd ~/ax7020_linux/projects/ax7020_linux
petalinux-config -c rootfs
# 选中 user packages -> john-dma、john-node
petalinux-build -c john-dma
petalinux-build -c john-node
petalinux-build
```

启动检查：

```bash
/etc/init.d/john-node status
tail -f /media/sd-mmcblk0p1/john-node/log/john-node.log
```

可在 SD 启动分区创建 `john-node.conf`，配置在重启后保留：

```sh
NODE_ID=ax7020-1
NODE_INTERFACE=eth0
NODE_IP=169.254.173.138/16
NODE_PORT=42000
QUEUE_DEPTH=8
RESULT_DEPTH=16
RESULT_TTL=600
```

日志写入 SD 卡并在启动时进行 1 MiB、4 份轮转；PL 详细错误只进入本地日志，上位机仅接收任务失败分类。

## 上位机

发现节点：

```powershell
python john-ax7020-common\host\john_udp_client.py `
  --host 169.254.173.138 discover

python john-ax7020-common\host\john_udp_client.py `
  --host 169.254.173.138 heartbeat

python john-ax7020-common\host\john_udp_client.py `
  --host 169.254.173.138 health
```

提交一帧已经由算法 codec 构造的 Common request：

```powershell
python john-ax7020-common\host\john_udp_client.py `
  --host 169.254.173.138 run md5_request.bin md5_response.bin
```

客户端负责分片、ACK、超时重发、状态轮询和结果重组；返回的 Common response 仍需交给对应算法 codec 做 job ID、结果条数和摘要真值校验。

## 2026-10-30 实板结果

- 当前 PetaLinux `image.ub` SHA256：`8f78380f43a3564cd2de8966838ca96e1f11b2fb2518c338b5a7557232a05f33`。
- `S95john-node` 随系统自动启动，服务监听 UDP 42000，识别 MD5-crypt、8 个算法单元、每单元 3 Core、100 MHz。
- 单批 96 个口令从 Windows 经 UDP、Linux、AXI DMA 和 FPGA 返回，96/96 摘要与软件参考值一致。
- 100 个连续批次、共 9600 个候选在同一客户端连接对象中完成；末批结果 96/96 正确，节点服务保持运行。
- 故障注入已覆盖乱序分片、相同分片重复、冲突重传、数据不全时 COMMIT；协议按预期接受或拒绝，随后硬件任务仍可正确完成。
- 运行后 MM2S/S2MM Linux 中断计数同步增长，未再出现 Python 直接 mmap 写 AXI-Lite 时发生的 `external abort`。
- 当前逐片 ACK 的参考客户端端到端约 840 candidates/s；这不是 PL 算法核极限，主要受小 UDP 报文逐片往返和 Python 控制开销限制，后续需采用窗口确认/批量流水优化。
- 4客户端并发提交时实测1批运行、3批排队，4批均96/96正确；健康消息、XADC、电压、网口、DMA计数、Bitstream状态和SD持久化日志均已实板验证。

详细证据见 `../reports/linux_udp_node_validation_20261030.md` 和 `../reports/linux_health_queue_validation_20261030.md`。

## 当前限制

- PS 队列已经支持多任务缓存，但 PL 物理上仍串行执行；跨节点调度由上位分发软件负责。
- CANCEL 只能取消尚未开始的任务；运行中的 DMA/算法不能被不安全地强制释放。
- 当前 init 脚本依赖 initramfs 中的 Python 3；最终精简 rootfs 前需核对 Python 子包依赖。
- 当前实板闭环只验证 MD5-crypt；bcrypt、descrypt、sha256crypt、sha512crypt 仍需更换 Bitstream 后逐一验证。
- v1 对每个 DATA 分片逐片 ACK，可靠但吞吐率偏低；窗口确认尚未实现。
- 固定节点 IP 和服务配置已可从 SD 持久化；SSH 主机密钥与认证仍未持久化。
- 心跳采用上位机请求/节点应答方式，不主动广播，避免上位机处理慢时积压无效心跳。
