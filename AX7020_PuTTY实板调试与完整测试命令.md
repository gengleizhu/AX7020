# AX7020 PuTTY 实板调试与完整测试命令

更新时间：2026-11-03  
适用系统：AX7020、PetaLinux 2020.1、Linux 5.4、五算法在线切换镜像  
默认板卡地址：169.254.173.138  
上位机直连网口地址：169.254.173.137/16  
节点 UDP 端口：42000

## 1. PuTTY 串口设置

打开 PuTTY，选择 Serial：

| 项目 | 设置 |
|---|---|
| Serial line | COM7，按设备管理器实际端口修改 |
| Speed | 115200 |
| Data bits | 8 |
| Stop bits | 1 |
| Parity | None |
| Flow control | None |

建议在 Session → Logging 中选择 All session output，将日志保存为：

    AX7020_putty_YYYYMMDD_HHMMSS.log

登录信息：

    login: root
    Password: root

命令提示符类似：

    root@ax7020_linux:~#

本文标注“板端”的命令粘贴到 PuTTY。标注“Windows”的命令在 Windows PowerShell 中执行。不要把 PowerShell 命令粘贴到板卡。

## 2. 推荐测试顺序

按以下顺序执行：

1. 启动和镜像检查。
2. Linux、SD 卡和网口检查。
3. DMA、节点服务和日志检查。
4. AXI-Lite 身份寄存器检查。
5. 五份固件及 manifest 校验。
6. Windows 心跳和健康查询。
7. 当前算法真实任务测试。
8. 在线切换其他算法并逐项测试。
9. 切回 MD5，确认最终交付状态。

## 3. 启动与基础 Linux 检查

板端执行：

    date
    uname -a
    uptime
    cat /proc/cmdline
    free -m
    df -h
    mount | grep mmcblk
    cat /proc/loadavg

预期：

- 内核为 Linux 5.4.0-xilinx-v2020.1。
- 根文件系统为 initramfs。
- SD 卡存在 mmcblk0p1，挂载点为 /media/sd-mmcblk0p1。

检查启动镜像：

    ls -lh /media/sd-mmcblk0p1/BOOT.BIN
    ls -lh /media/sd-mmcblk0p1/image.ub
    sha256sum /media/sd-mmcblk0p1/image.ub

当前固化镜像预期 SHA256：

    3ecfa55e239207630c4c92f3d6b5ea4a54aad79d6c98c32494522a1ba83ab57e

旧镜像备份应存在：

    ls -lh /media/sd-mmcblk0p1/image.ub.pre_persist_20261103

## 4. 网口检查

板端执行：

    ip link show eth0
    ip addr show eth0
    cat /sys/class/net/eth0/carrier
    cat /sys/class/net/eth0/operstate
    cat /sys/class/net/eth0/speed
    cat /sys/class/net/eth0/duplex
    cat /sys/class/net/eth0/statistics/rx_errors
    cat /sys/class/net/eth0/statistics/tx_errors
    ping -c 4 169.254.173.137

预期：

- carrier 为 1。
- operstate 为 up。
- speed 为 1000。
- duplex 为 full。
- rx_errors 和 tx_errors 为 0。
- 可以 ping 通 Windows 的 169.254.173.137。

检查持久化网络配置：

    cat /media/sd-mmcblk0p1/john-node.conf

建议内容：

    NODE_ID=ax7020-1
    NODE_INTERFACE=eth0
    NODE_IP=169.254.173.138/16
    NODE_PORT=42000
    QUEUE_DEPTH=8
    RESULT_DEPTH=16
    RESULT_TTL=600

如果板卡没有 169.254.173.138 地址，可临时执行：

    ip addr replace 169.254.173.138/16 dev eth0
    ip link set eth0 up

## 5. DMA 和节点服务检查

板端执行：

    ls -l /dev/john-dma
    lsmod | grep john
    dmesg | grep -Ei 'john|dma|fpga'
    cat /proc/interrupts | grep -Ei 'dma|40400000'
    /etc/init.d/john-node status
    cat /run/john-node.pid
    kill -0 "$(cat /run/john-node.pid)" && echo SERVICE_PROCESS_OK
    netstat -ulnp | grep 42000

预期：

- /dev/john-dma 存在。
- john-dma 模块已经加载。
- 日志中出现 Xilinx AXI DMA Engine Driver Probed。
- 日志中出现 john-dma-client ready。
- john-node is running。
- UDP 42000 正在监听。

查看节点日志：

    tail -n 100 /media/sd-mmcblk0p1/john-node/log/john-node.log

持续观察日志，按 Ctrl+C 退出：

    tail -f /media/sd-mmcblk0p1/john-node/log/john-node.log

手动重启服务：

    /etc/init.d/john-node restart
    sleep 2
    /etc/init.d/john-node status

## 6. PL 和 AXI-Lite 公共寄存器检查

以下命令均为只读，可在节点服务运行时执行：

    devmem 0x43c00000 32
    devmem 0x43c00004 32
    devmem 0x43c00008 32
    devmem 0x43c0000c 32
    devmem 0x43c00020 32
    devmem 0x43c00024 32
    devmem 0x43c00028 32
    devmem 0x43c0002c 32
    devmem 0x43c00084 32
    devmem 0x43c0009c 32
    devmem 0x43c000a0 32

关键预期值：

| 地址 | 含义 | 预期 |
|---|---|---|
| 0x43C00000 | Magic | 0x4A435250 |
| 0x43C00004 | Register ABI | 0x00010001 |
| 0x43C00008 | 地址窗口大小 | 0x00010000 |
| 0x43C0000C | Stream ABI | 0x00010000 |
| 0x43C00020 | Algorithm ID | 1～5 |
| 0x43C00024 | 算法单元数 | 当前工程配置 |
| 0x43C00028 | 每单元 Core 数 | 当前工程配置 |
| 0x43C0002C | 总 Core 数 | 当前工程配置 |
| 0x43C00084 | PL Status | READY、INIT_DONE 应置位 |
| 0x43C0009C | 首个错误码 | 正常为 0 |
| 0x43C000A0 | 错误详情 | 正常为 0 |

Algorithm ID：

| ID | 算法 |
|---:|---|
| 1 | bcrypt8 |
| 2 | descrypt8 |
| 3 | md5crypt8 |
| 4 | sha256crypt8 |
| 5 | sha512crypt4 |

状态寄存器 0x84 的关键位：

- bit0 READY：应为 1。
- bit1 BUSY：计算期间为 1。
- bit3 ERROR：正常为 0。
- bit4 INIT_DONE：应为 1。
- bit5 NEED_RELOAD：正常为 0。
- bit11 SNAPSHOT_VALID：健康采样后可能为 1。

快速判断状态：

    S=$(devmem 0x43c00084 32)
    echo "STATUS=$S"
    [ $((S & 1)) -ne 0 ] && echo READY_OK || echo READY_FAIL
    [ $((S & 16)) -ne 0 ] && echo INIT_OK || echo INIT_FAIL
    [ $((S & 8)) -eq 0 ] && echo ERROR_CLEAR || echo ERROR_SET
    [ $((S & 32)) -eq 0 ] && echo RELOAD_CLEAR || echo NEED_RELOAD

不要在节点服务运行时手工写 0x43C00080、任务描述符或 DMA 寄存器，否则会与服务的寄存器访问发生冲突。

## 7. 五份固件和 manifest 完整性检查

板端执行：

    ls -lh /lib/firmware/john_ax7020_*.bit.bin
    ls -lh /etc/john/bitstreams/john_ax7020_*.json

逐份执行加载前校验，不会切换算法：

    for m in /etc/john/bitstreams/john_ax7020_*.json; do
        echo "CHECK $m"
        python3 /usr/sbin/john-bitstream "$m" --check-only || break
    done

预期五份全部输出 JSON，且没有 firmware SHA256 mismatch 或 unsupported ABI。

固件 SHA256：

    sha256sum /lib/firmware/john_ax7020_*.bit.bin

预期：

    ec6362e907f7fa78c1bc8246dd1c84ce750cf1c9c15e6a729ac7af9b0121300c  john_ax7020_bcrypt8.bit.bin
    d23dc54f8583d4c2eac03e57947f8579bb9372eaa8dca6a7c26e67953a5968f6  john_ax7020_descrypt8.bit.bin
    d9b054fbe0e00280b0f27e4906ebbcd9676a50441110e28b6b1628f077e15e24  john_ax7020_md5crypt8.bit.bin
    3f7016057f1aa561602abdc3342add0610be51ebd33143aca19a48857e808fa1  john_ax7020_sha256crypt8.bit.bin
    cf4e6b8cc6ad18db8d59625327478f8a92d02bf44fa4ed9fb42ef6c47c3dcd6f  john_ax7020_sha512crypt4.bit.bin

## 8. Windows 上位机基础测试

在 Windows PowerShell 中执行：

    Set-Location E:\zhugenglei.work\john
    $BoardIp = '169.254.173.138'
    Test-Connection $BoardIp -Count 4

节点发现：

    py -3 john-ax7020-common\host\john_udp_client.py --host $BoardIp discover

心跳：

    py -3 john-ax7020-common\host\john_udp_client.py --host $BoardIp heartbeat

完整健康状态：

    py -3 john-ax7020-common\host\john_udp_client.py --host $BoardIp health

重点检查：

- algorithm 与当前 Bitstream 一致。
- service.maintenance 为 false。
- 网口 carrier 为 1、speed_mbps 为 1000、duplex 为 full。
- DMA running 为 0；执行任务后 tx/rx completion 应增加。
- 温度和电压字段不是 -1。
- PL error 和 NEED_RELOAD 未置位。

## 9. 五算法在线切换命令

切换前确认没有正在执行或尚未取走结果的任务：

    /etc/init.d/john-node status
    test ! -e /run/john-node.maintenance && echo MAINTENANCE_CLEAR

切换 bcrypt，预期 loaded 为 1：

    python3 /usr/sbin/john-bitstream /etc/john/bitstreams/john_ax7020_bcrypt8.json --drain-seconds 60

切换 DES，预期 loaded 为 2：

    python3 /usr/sbin/john-bitstream /etc/john/bitstreams/john_ax7020_descrypt8.json --drain-seconds 60

切换 MD5，预期 loaded 为 3：

    python3 /usr/sbin/john-bitstream /etc/john/bitstreams/john_ax7020_md5crypt8.json --drain-seconds 60

切换 SHA256，预期 loaded 为 4：

    python3 /usr/sbin/john-bitstream /etc/john/bitstreams/john_ax7020_sha256crypt8.json --drain-seconds 60

切换 SHA512，预期 loaded 为 5：

    python3 /usr/sbin/john-bitstream /etc/john/bitstreams/john_ax7020_sha512crypt4.json --drain-seconds 60

每次切换后执行：

    /etc/init.d/john-node status
    test ! -e /run/john-node.maintenance && echo MAINTENANCE_CLEAR
    cat /sys/class/fpga_manager/fpga0/state
    devmem 0x43c00020 32
    devmem 0x43c00084 32
    devmem 0x43c0009c 32
    devmem 0x43c000a0 32

预期：

- 服务为 running。
- maintenance 不存在。
- FPGA Manager 为 operating。
- Algorithm ID 与目标算法一致。
- ERROR 和 NEED_RELOAD 未置位。

## 10. 五算法真实任务测试

先在 Windows PowerShell 中建立结果目录：

    Set-Location E:\zhugenglei.work\john
    $BoardIp = '169.254.173.138'
    $Out = 'E:\zhugenglei.work\john\outputs\putty_manual_validation'
    New-Item -ItemType Directory -Force -Path $Out | Out-Null

### 10.1 bcrypt

先在 PuTTY 中切换 bcrypt，然后在 Windows 执行：

    py -3 john-ax7020-common\scripts\phase1_board_vectors.py generate 1 "$Out\alg1"
    py -3 john-ax7020-common\software\test_john_udp_integration.py "$Out\alg1\request.bin" "$Out\alg1\response.bin" --host $BoardIp
    py -3 john-ax7020-common\scripts\phase1_board_vectors.py verify 1 "$Out\alg1"

预期：32 条、cost 4、pass 为 true。

### 10.2 DES

先在 PuTTY 中切换 DES，然后在 Windows 执行：

    py -3 john-ax7020-common\scripts\phase1_board_vectors.py generate 2 "$Out\alg2"
    py -3 john-ax7020-common\software\test_john_udp_integration.py "$Out\alg2\request.bin" "$Out\alg2\response.bin" --host $BoardIp
    py -3 john-ax7020-common\scripts\phase1_board_vectors.py verify 2 "$Out\alg2"

预期：128 个候选，8 个单元掩码正确，pass 为 true。

### 10.3 MD5

先在 PuTTY 中切换 MD5，然后在 Windows 执行：

    py -3 john-ax7020-common\scripts\md5_board_vectors.py generate "$Out\alg3"
    py -3 john-ax7020-common\software\test_john_udp_integration.py "$Out\alg3\request.bin" "$Out\alg3\response.bin" --host $BoardIp
    py -3 john-ax7020-common\scripts\md5_board_vectors.py verify "$Out\alg3"

预期：96/96 摘要一致，pass 为 true。

### 10.4 SHA256

先在 PuTTY 中切换 SHA256，然后在 Windows 执行：

    py -3 john-ax7020-common\scripts\phase1_board_vectors.py generate 4 "$Out\alg4"
    py -3 john-ax7020-common\software\test_john_udp_integration.py "$Out\alg4\request.bin" "$Out\alg4\response.bin" --host $BoardIp
    py -3 john-ax7020-common\scripts\phase1_board_vectors.py verify 4 "$Out\alg4"

预期：96 条、1000 轮、pass 为 true。

### 10.5 SHA512

先在 PuTTY 中切换 SHA512，然后在 Windows 执行：

    py -3 john-ax7020-common\scripts\phase1_board_vectors.py generate 5 "$Out\alg5"
    py -3 john-ax7020-common\software\test_john_udp_integration.py "$Out\alg5\request.bin" "$Out\alg5\response.bin" --host $BoardIp
    py -3 john-ax7020-common\scripts\phase1_board_vectors.py verify 5 "$Out\alg5"

预期：64 条、1000 轮、pass 为 true。

test_john_udp_integration.py 还会验证乱序分片、重复分片、冲突重复、不完整提交、DMA 计算和结果重组。

## 11. 队列和连续任务测试

切回 MD5 后，在 Windows 执行 4 个并发任务：

    py -3 john-ax7020-common\software\test_john_udp_queue_integration.py "$Out\alg3\request.bin" "$Out\queue4" --host $BoardIp --count 4

预期：

- 4 个任务均完成。
- 输出 result_0.bin 至 result_3.bin。
- 心跳显示任务排队和结果缓存状态。
- 节点服务保持运行。

连续执行 20 批：

    1..20 | ForEach-Object {
        py -3 john-ax7020-common\host\john_udp_client.py --host $BoardIp run "$Out\alg3\request.bin" "$Out\alg3\loop_$_.bin"
        if ($LASTEXITCODE -ne 0) { throw "第 $_ 批失败" }
    }

完成后在 PuTTY 检查：

    /etc/init.d/john-node status
    tail -n 100 /media/sd-mmcblk0p1/john-node/log/john-node.log
    cat /proc/interrupts | grep -Ei 'dma|40400000'
    devmem 0x43c00084 32
    devmem 0x43c0009c 32

## 12. 在线加载失败后的恢复

如果切换失败，先检查：

    cat /run/john-node.maintenance
    cat /sys/class/fpga_manager/fpga0/state
    /etc/init.d/john-node status
    dmesg | tail -n 100
    tail -n 100 /media/sd-mmcblk0p1/john-node/log/john-node.log

如果 /run/john-node.maintenance 存在，使用已知正确的 MD5 镜像恢复：

    python3 /usr/sbin/john-bitstream /etc/john/bitstreams/john_ax7020_md5crypt8.json --recover

恢复后检查：

    test ! -e /run/john-node.maintenance && echo RECOVERY_REOPENED
    /etc/init.d/john-node status
    cat /sys/class/fpga_manager/fpga0/state
    devmem 0x43c00020 32
    devmem 0x43c00084 32

不要直接删除 maintenance 文件。该文件表示加载流程已在停止服务之后失败，必须先重新加载可信 Bitstream、恢复 DMA 驱动并通过自检。

如果 --recover 也失败，保留串口和日志信息，执行：

    sync
    reboot

重启后 BOOT.BIN 会恢复默认 MD5 PL，固化后的 image.ub 会重新启动节点服务。

## 13. 镜像回滚

仅在新 image.ub 无法正常启动或服务无法恢复时执行。板端：

    cd /media/sd-mmcblk0p1
    cp image.ub image.ub.failed
    cp image.ub.pre_persist_20261103 image.ub
    sha256sum image.ub
    sync
    reboot

回滚前不要删除当前镜像，保留 image.ub.failed 便于定位。

## 14. 最终交付状态检查

建议最终切回 MD5，然后执行：

    python3 /usr/sbin/john-bitstream /etc/john/bitstreams/john_ax7020_md5crypt8.json --drain-seconds 60
    /etc/init.d/john-node status
    test ! -e /run/john-node.maintenance && echo MAINTENANCE_CLEAR
    cat /sys/class/fpga_manager/fpga0/state
    devmem 0x43c00020 32
    devmem 0x43c00084 32
    devmem 0x43c0009c 32
    tail -n 50 /media/sd-mmcblk0p1/john-node/log/john-node.log

最终应满足：

- Algorithm ID 为 3。
- FPGA Manager 为 operating。
- john-node 为 running。
- maintenance 不存在。
- PL ERROR 和 NEED_RELOAD 均未置位。
- Windows discover、heartbeat、health 均有正确响应。
- MD5 真实任务验证为 96/96。
