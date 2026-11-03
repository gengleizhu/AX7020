# PetaLinux 启动镜像固化与冷启动验证（2026-11-03）

## 结论

最新 Linux 节点服务、DMA 驱动、在线 Bitstream 加载及失败恢复工具、五种算法固件和 manifest 已固化到 PetaLinux 2020.1 的 image.ub。新镜像已经写入 AX7020 SD 卡并完成重启验证。板卡当前运行 MD5，FPGA Manager 状态为 operating，节点服务正常，maintenance 标记不存在。

本次只更新 image.ub。开机默认 PL 仍由原 BOOT.BIN 中已验证的 MD5 Bitstream 配置，所以未重新打包或替换 BOOT.BIN。

## 固化内容

- /usr/sbin/john-node
- /usr/sbin/john-bitstream
- /etc/init.d/john-node 及自动启动链接
- john-dma.ko
- /lib/firmware/john_ax7020_{bcrypt8,descrypt8,md5crypt8,sha256crypt8,sha512crypt4}.bit.bin
- /etc/john/bitstreams/john_ax7020_{bcrypt8,descrypt8,md5crypt8,sha256crypt8,sha512crypt4}.json

新增 PetaLinux 包为 john-firmware，源文件位于 john-ax7020-common/linux/petalinux/recipes-apps/john-firmware/。部署脚本会把该包登记到 project-spec/meta-user/conf/user-rootfsconfig，避免重新执行 rootfs 配置时丢失。

## 构建结果

虚拟机工程：/home/zgl/ax7020_linux/projects/ax7020_linux

构建命令：

    source ~/petalinux/2020.1/settings.sh
    cd ~/ax7020_linux/projects/ax7020_linux
    petalinux-config -c rootfs --silentconfig
    petalinux-build -c john-node -x cleansstate
    petalinux-build -c john-firmware -x cleansstate
    petalinux-build

结果为 3593 个任务全部成功。唯一警告仍是没有 /tftpboot，不影响 SD 启动镜像。

新镜像：

- 大小：26351568 bytes
- SHA256：3ecfa55e239207630c4c92f3d6b5ea4a54aad79d6c98c32494522a1ba83ab57e
- Windows 交付路径：E:/zhugenglei.work/john/outputs/petalinux_persist_20261103/image.ub

镜像中的 rootfs.manifest 已确认包含 john-dma、john-node、john-firmware；解包检查确认上述程序、五份固件和五份 manifest 均存在。

## SD 更新和回滚

板卡 SD 第一分区中的新镜像：

    /media/sd-mmcblk0p1/image.ub

旧镜像备份：

    /media/sd-mmcblk0p1/image.ub.pre_persist_20261103

如需回滚，可在板端执行：

    cd /media/sd-mmcblk0p1
    cp image.ub image.ub.failed
    cp image.ub.pre_persist_20261103 image.ub
    sync
    reboot

## 实板冷启动验证

重启时 U-Boot 从 SD 读取 26351568 字节的新 image.ub，FIT 中 kernel、ramdisk、设备树 SHA256 校验均通过。Linux 5.4 正常启动，DMA 驱动探测成功，john-node 自动启动。

验证结果：

1. 五份固件、五份 manifest、加载器、节点程序和启动脚本均存在。
2. 五份 manifest 全部通过 john-bitstream --check-only 的 SHA256 和 ABI 检查。
3. 默认 MD5：冷启动后 UDP/DMA 集成测试通过，96/96 摘要匹配。
4. 使用镜像内 manifest 在线切换到 SHA256：加载、自检及 UDP/DMA 计算通过，96 条、1000 轮参考结果一致。
5. 在线切回 MD5：加载、自检及 UDP/DMA 测试通过，96/96 摘要匹配。
6. 最终状态：算法编号 3（MD5），FPGA Manager 为 operating，服务进程存活，无 maintenance 标记。

启动日志：

    E:/zhugenglei.work/john/outputs/petalinux_persist_20261103/board_boot_persist_20261103.log

验证结果：

    E:/zhugenglei.work/john/outputs/petalinux_persist_20261103/md5_cold_boot_response.bin
    E:/zhugenglei.work/john/outputs/petalinux_persist_20261103/sha256_persist_switch_response.bin
    E:/zhugenglei.work/john/outputs/petalinux_persist_20261103/md5_after_persist_switch_response.bin

## 已知事项

启动日志提示 FAT 分区此前未正常卸载。此次更新前后均执行了 sync，镜像哈希及启动校验均通过；后续维护窗口可将 SD 卡接入主机执行 FAT 文件系统检查。

当前修改及构建产物尚未提交 Git，不把未提交状态写成已提交。

