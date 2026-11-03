# 五算法在线切换与失败恢复实板记录（2026-11-02）

## 结论与范围

AX7020、PetaLinux 2020.1/Linux 5.4 已验证本地 root 命令驱动的全量 PL 在线重配置，不重启 Linux、不使用 JTAG。不是部分重配置，也没有新增远程 UDP 下载 bitstream 接口。失败恢复由管理员明确指定已知正确 manifest 并执行 `--recover`；不是自动回滚。

流程：SHA256/ABI预检查 → maintenance拒绝新BEGIN → 排空任务及未确认结果 → 停服务并等待退出 → 卸载john_dma → 解绑xilinx-vdma → FPGA Manager加载 → magic/ABI/算法/READY自检 → 重新绑定DMA及加载客户端 → 启动节点并校验健康信息 → 取消maintenance。

加载前排空失败恢复接单；停服务之后失败保持maintenance，不能直接删除标记继续接单。恢复流程重新加载可信固件，并完成同样的驱动恢复和自检。恢复命令也受进程锁保护。

## 实板结果

Linux在线切换先执行 MD5→bcrypt→DES→SHA256→SHA512 自检，再执行 SHA512→bcrypt→DES→SHA256→SHA512→MD5，并逐项执行UDP/DMA真实计算验证。全过程未重启Linux。

| 算法 | 实际计算验证 |
|---|---|
| bcrypt8 | 32条，cost4，软件参考值一致 |
| descrypt8 | 128候选，8单元命中掩码1/2/4/8/16/32/64/128正确 |
| md5crypt8 | 96条，摘要逐条一致 |
| sha256crypt8 | 96条，1000轮，软件参考值一致 |
| sha512crypt4 | 64条，1000轮，软件参考值一致 |

故障注入：

1. 用有效MD5固件但manifest声明算法2：配置成功，自检报 `identity mismatch at offset 0x20`，保留maintenance、不启动服务。执行MD5 `--recover` 后恢复服务，96/96摘要正确。
2. 用SHA256校验正确但内容无效的测试固件：FPGA Manager报 `Invalid bitstream, could not find a sync word`、状态 `write init error`；保留maintenance。执行MD5 `--recover` 后恢复为 `operating`，96/96摘要正确。
3. 恢复后额外连续3批MD5 UDP/DMA集成测试均通过（每批返回2472字节）；集成测试包含乱序、重复、冲突重复、不完整提交及结果重组。
4. 加载器7项单元测试、队列4项单元测试通过。排空超时/停止失败等为单元测试覆盖，未将其写成实板故障覆盖。

结果文件：`D:/Documents/ChatGPT/john/output/phase1_board_validation_20261102/alg1/response.bin`、`alg2/response.bin`、`alg4/response.bin`、`alg5/response.bin`；MD5结果位于该目录下 `md5/recovery_identity.bin`、`recovery_invalid.bin`、`recovery_batch_1.bin` 至 `recovery_batch_3.bin`。前两份恢复结果已逐摘要核对96/96。

## 操作命令（板端root）

```sh
# 正常切换：替换文件名即可选择五种算法。
python3 /usr/sbin/john-bitstream /media/sd-mmcblk0p1/phase2_20261102/john_ax7020_sha256crypt8.json --drain-seconds 60

# 失败后恢复至MD5；要求已有失败的maintenance标记。
python3 /usr/sbin/john-bitstream /media/sd-mmcblk0p1/phase2_20261102/john_ax7020_md5crypt8.json --recover

# 仅校验文件，不停服务、不加载。
python3 /usr/sbin/john-bitstream /media/sd-mmcblk0p1/phase2_20261102/john_ax7020_md5crypt8.json --check-only
cat /sys/class/fpga_manager/fpga0/state
```

manifest文件名分别为 `john_ax7020_bcrypt8.json`、`john_ax7020_descrypt8.json`、`john_ax7020_md5crypt8.json`、`john_ax7020_sha256crypt8.json`、`john_ax7020_sha512crypt4.json`。对应固件必须在 `/lib/firmware`。

## 文件与持久化

工程根目录：`E:/zhugenglei.work/john`。

- 加载器：`john-ax7020-common/linux/node/john_bitstream.py`
- 节点维护模式：`john-ax7020-common/linux/node/john_node_service.py`
- 服务退出等待：`john-ax7020-common/linux/node/S95john-node`
- 打包脚本：`john-ax7020-common/scripts/build_linux_firmware.py`
- 本机固件及manifest：`john-ax7020-common/build/linux_firmware/`
- 测试：`john-ax7020-common/software/test_bitstream_switch.py`
- PetaLinux集成：`john-ax7020-common/linux/deploy_to_petalinux.sh` 及 `linux/petalinux/recipes-apps/john-node/john-node.bb`

板端当前运行MD5，服务正常、maintenance不存在。最新加载器、节点服务、启动脚本及五份固件已备份到SD `/media/sd-mmcblk0p1/phase2_20261102/`，文件分别为 `john-bitstream`、`john-node.current`、`init.current`、`john_ax7020_*.bit.bin`。

当前运行部署仍在RAM rootfs，尚未重新构建image.ub，掉电后不会自动恢复本次更新。SD备份保存了文件，但不是开机部署机制。下一步通过现有PetaLinux部署入口重建镜像并验证冷启动持久化。

## 未完成的验收边界

- 尚未实现上位机远程切换控制命令及自动选择回退版本；当前是本地管理命令。
- 尚未进行长时间压力测试、全部20种有向算法组合遍历、在途DMA故障/断电注入、双节点切换调度。
- 之前JTAG连续切换后的首拍错误6未在本次有序Linux切换中复现，其底层残留状态根因仍未完全证明。
- 当前修改未提交；保留已有未提交源码、构建产物，不擅自清理。
