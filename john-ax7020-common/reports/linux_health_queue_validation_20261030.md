# AX7020 健康监控、任务队列和结果缓存实板验证（2026-10-30）

## 结论

当前 MD5-crypt 节点已经在 AX7020 实板完成任务状态、请求式心跳、独立健康消息、Bitstream 状态、SD 持久化日志、8 深度任务队列和 16 深度结果缓存验证。PL 详细错误保留在 Linux 日志，上位机只接收任务状态和简化失败类型。

## 镜像

- 最终 `image.ub` SHA256：`8f78380f43a3564cd2de8966838ca96e1f11b2fb2518c338b5a7557232a05f33`
- 最终更新前镜像备份：`/media/sd-mmcblk0p1/backup_pre_health_queue_v4_idempotent_20261030_085259/image.ub`
- Windows 副本：`D:/Documents/ChatGPT/john/output/ax7020_board_dma_20261030/boot_health_queue_v4/image.ub`

## 实测健康信息

- 节点：`ax7020-1`，固定地址 `169.254.173.138/16` 随服务启动脚本恢复。
- 网络：carrier=1、1000 Mbps、full duplex，RX/TX error 和 drop 均为 0。
- XADC：温度约 55℃；VCCINT约0.972 V、VCCAUX约1.785 V、VCCBRAM约0.973 V。
- Bitstream：algorithm=3、8 单元、每单元3 Core、100 MHz、build_date=20261029、load_state=READY。
- DMA：驱动独立记录 MM2S/S2MM completion 计数；5批实测后均为5，Linux IRQ也均为5。

## 队列与结果验证

4个Windows客户端线程并发上传相同的真实MD5任务。心跳在提交后观察到：

```text
service_state=RUNNING
queued=3
results_cached=0
```

说明PS在PL执行第1批时已经缓存其余3批。随后4批全部返回2472字节结果，每批96/96摘要与软件参考值一致。客户端发送 `RESULT_ACK` 后，`results_cached=0`、`tasks_tracked=0`，证明结果缓存被显式释放而不是覆盖。

最终镜像重新启动后又执行1批真实任务，96/96真值正确，心跳和健康查询均正常；重复发送 `RESULT_ACK` 仍返回成功，结果释放具备幂等性。最终镜像同时将正常任务流水日志从INFO降为DEBUG，以减少SD写入。

## 日志

持久化日志路径：

```text
/media/sd-mmcblk0p1/john-node/log/john-node.log
```

默认INFO级别记录服务启动、过期结果和硬件/协议异常；任务排队、开始、完成、最终数量、PL周期、结果长度和结果释放在DEBUG级别可用，避免高吞吐运行时频繁写SD卡。单文件达到1 MiB后保留4份轮转文件。硬件异常时C库返回的PL错误码和详情由 `logging.exception` 写入本地日志，不放入健康消息。

## 当前边界

- 心跳为请求/应答，不是无目的UDP广播。
- 只验证MD5-crypt Bitstream，其他四算法仍需逐一实板验证。
- 逐片ACK限制网络吞吐；任务队列消除了上位机提交间隙，但不能提高单个PL核的计算速度。
- 结果缓存位于RAM，掉电后由上位调度器根据未确认任务重新下发。
- SSH主机密钥仍由initramfs每次启动生成，尚未做持久化。
