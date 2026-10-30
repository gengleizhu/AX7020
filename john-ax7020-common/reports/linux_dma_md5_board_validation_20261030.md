# AX7020 Linux DMA 与 MD5-crypt 实板闭环记录（2026-10-30）

## 1. 结论

AX7020 已能从 SD 卡无 JTAG 启动修复版 MD5 bitstream。PetaLinux 2020.1 自动加载通用 DMAengine client，创建 `/dev/john-dma`。一批 96 条 MD5-crypt 任务以及后续 220 批连续任务均完成，MM2S/S2MM 中断计数同步增长，硬件摘要与 Windows 软件参考值逐条一致。

本记录只证明 MD5 修复版的 Linux 实板闭环。bcrypt、descrypt、sha256crypt、sha512crypt 尚未完成相同实板验证。

## 2. 文件位置

VM 工程：

```text
~/ax7020_linux/projects/ax7020_linux
~/ax7020_linux/hardware/hard_1030/john_ax7020_md5crypt8_startup_reset.xsa
~/ax7020_linux/hardware/hard_1030/john_ax7020_md5crypt8_startup_reset.bit
```

PetaLinux 自定义项：

```text
project-spec/meta-user/recipes-modules/john-dma/
project-spec/meta-user/recipes-apps/john-dma-test/
project-spec/meta-user/recipes-bsp/device-tree/files/system-user.dtsi
```

Windows 开发副本和证据：

```text
D:\Documents\ChatGPT\john\linux\john-dma\files\john-dma.c
D:\Documents\ChatGPT\john\linux\john-dma\files\john_dma_uapi.h
D:\Documents\ChatGPT\john\linux\john-dma-test\files\john-dma-test.c
D:\Documents\ChatGPT\john\tools\generate_md5_dma_test.py
D:\Documents\ChatGPT\john\output\ax7020_board_dma_20261030\
D:\Documents\ChatGPT\john\output\petalinux_hard_1030_20261030\ssh_full_transcript.log
```

## 3. 创建 PetaLinux 组件

在 Ubuntu 18.04.4 中执行：

```bash
source ~/petalinux/2020.1/settings.sh
cd ~/ax7020_linux/projects/ax7020_linux

petalinux-create -t modules --name john-dma --enable
petalinux-create -t apps --template c --name john-dma-test --enable
```

把驱动、UAPI 头、Makefile 和 recipe 放入 `recipes-modules/john-dma/`；把测试程序、同一 UAPI 头、Makefile 和 recipe 放入 `recipes-apps/john-dma-test/`。两个 UAPI 头必须保持完全一致。

Linux 5.4 不提供 `dev_err_probe()`。错误路径使用以下兼容形式：

```c
ret = PTR_ERR(channel);
if (ret != -EPROBE_DEFER)
        dev_err(dev, "cannot request DMA channel: %d\n", ret);
return ret;
```

## 4. 设备树 DMA consumer

在保留原板级 `system-user.dtsi` 内容的基础上，于根节点增加：

```dts
john_dma_client: john-dma-client {
        compatible = "john,axi-dma-client-1.0";
        dmas = <&dma 0>, <&dma 1>;
        dma-names = "tx", "rx";
        status = "okay";
};
```

其中 `dma` 必须是当前 XSA 生成的 `dma@40400000` 标签。构建后不要只检查源文件，应展开最终 DTB 核对 phandle：

```bash
cd ~/ax7020_linux/projects/ax7020_linux
DTC=build/tmp/sysroots-components/x86_64/dtc-native/usr/bin/dtc
"$DTC" -I dtb -O dts images/linux/system.dtb |
        sed -n '/john-dma-client/,/};/p'
```

如果修改已写入 `system-user.dtsi`，但最终 DTB 仍是旧内容，清理设备树缓存后重建：

```bash
petalinux-build -c device-tree -x cleansstate
petalinux-build -c device-tree
```

## 5. 构建和打包

```bash
source ~/petalinux/2020.1/settings.sh
cd ~/ax7020_linux/projects/ax7020_linux

petalinux-build -c john-dma
petalinux-build

bit=~/ax7020_linux/hardware/hard_1030/john_ax7020_md5crypt8_startup_reset.bit
petalinux-package --boot \
        --fsbl images/linux/zynq_fsbl.elf \
        --fpga "$bit" \
        --u-boot \
        --dtb images/linux/system.dtb \
        --force

sha256sum images/linux/BOOT.BIN \
        images/linux/image.ub \
        images/linux/system.dtb \
        images/linux/boot.scr
```

`/tftpboot` 不存在只会产生复制警告，不影响本地镜像生成。

核对 initramfs 内容：

```bash
gzip -dc images/linux/rootfs.cpio.gz | cpio -it 2>/dev/null |
        grep -E '(^|/)(john-dma-test|john-dma.ko)$|etc/modules-load.d/john-dma.conf'
```

## 6. SD 更新和回滚

本次先把旧文件备份到：

```text
/media/sd-mmcblk0p1/backup_pre_john_dma_20261030_1512/
```

板上更新过程采用临时文件加同分区重命名，避免直接覆盖到一半：

```sh
sd=/media/sd-mmcblk0p1
backup=$sd/backup_pre_john_dma_20261030_1512
mkdir -p "$backup"

for f in BOOT.BIN image.ub system.dtb boot.scr; do
        cp -p "$sd/$f" "$backup/$f"
done

for f in BOOT.BIN image.ub system.dtb boot.scr; do
        cp "/tmp/$f" "$sd/$f.new"
        sync
        mv "$sd/$f.new" "$sd/$f"
done
sync
sha256sum "$sd"/BOOT.BIN "$sd"/image.ub "$sd"/system.dtb "$sd"/boot.scr
```

需要回滚时，先确认备份哈希，再将备份目录中的四个文件按相同方式复制回第一分区根目录。

## 7. 启动后的检查

```sh
ls -l /dev/john-dma
dmesg | grep -E 'john-dma|Xilinx AXI DMA|xilinx-dma'
grep -E 'xilinx-dma' /proc/interrupts
command -v john-dma-test
test -e /sys/bus/platform/drivers/john-dma/john-dma-client && echo DRIVER_BOUND=YES
```

本次实际输出包括：

```text
john-dma john-dma-client: ready: john-dma, tx=dma1chan0 rx=dma1chan1, max=65600/8256 bytes
/dev/john-dma -> major 10, minor 60
```

板卡 IPv4 未配置时仍可从 Windows 直连网卡通过固定 MAC 派生的 IPv6 链路本地地址访问：

```text
fe80::20a:35ff:fe00:1e53%6
```

`%6` 是本机直连网卡的 interface index，只适用于本次 Windows 主机，换电脑后需重新查看。

## 8. 真实 MD5 批次测试

Windows 生成 96 条包含 0～64 字节口令长度的确定性测试任务：

```powershell
python D:\Documents\ChatGPT\john\tools\generate_md5_dma_test.py generate
```

上传 `md5_request.bin` 后，在板上执行：

```sh
grep -E 'xilinx-dma' /proc/interrupts
john-dma-test /tmp/md5_request.bin /tmp/md5_response.bin 30000
grep -E 'xilinx-dma' /proc/interrupts
```

首批实际结果：

```text
PASS tx=10056 rx=2472 status=0x000603d4 completed=96 total=96 elapsed_cycles=845699
```

下载 `md5_response.bin` 后逐条软件复核：

```powershell
python D:\Documents\ChatGPT\john\tools\generate_md5_dma_test.py verify
```

判定标准：

```json
{
  "pass": true,
  "result_records": 96,
  "failures": []
}
```

## 9. 连续运行结果和性能解释

- 首批后又运行 20 批，全部 PASS。
- 再运行 200 批，共 19,200 条候选，全部 PASS。
- MM2S/S2MM 两路中断计数均累计到 221，未出现单边中断丢失。
- 200 批耗时 3.30 秒，当前一次一进程的端到端测试约 5,818.18 条/秒。
- PL 时钟 100 MHz，约 845,455 周期/批，对应约 8.45 ms/批和约 11,354 条/秒的纯硬件估算上限。

两个吞吐量不能混写：5,818 条/秒包含每批启动进程、打开字符设备、映射寄存器、命令和文件 I/O；11,354 条/秒来自 PL 周期计数。常驻 UDP 节点服务应复用设备与寄存器映射，并测量网络、编解码、DMA 和 PL 各阶段，才能形成最终验收性能。

## 10. 下一步

1. 将当前 DMA client、测试程序和 recipe 正式纳入 Git 基线。
2. 把一次一进程测试改为常驻节点服务，建立任务队列、状态机和异常恢复。
3. 完成 UDP 上位机真实闭环。
4. 对其余四算法逐一完成真实 payload 和软件参考值对照。
5. 验证完整 bitstream 在线切换、驱动恢复和双板任务分片。
