# 第二阶段：Linux算法加载和恢复

范围：停接单、任务排空、DMA停止、Linux FPGA Manager完整加载、驱动恢复、自检、连续多批及异常恢复。

## 当前实现（尚未部署）

- john_node_service.py检测/run/john-node.maintenance，拒绝新BEGIN，保留已有任务上传/执行/结果读取。HEALTH返回maintenance。
- john_bitstream.py提供本地root入口，校验/lib/firmware下.bin的SHA256及manifest ABI；等待tasks_tracked为0且DMA不运行，再停止服务、卸载john_dma、解绑xilinx-vdma、经FPGA Manager加载完整固件，检查operating及magic/ABI/algorithm/READY，然后绑定DMA并重启服务。
- 排空失败恢复接单；停机后的失败保持维护标记，禁止新任务，不自动反复重载未知硬件。
- PetaLinux部署脚本和recipe已加入工具。队列单元测试4项通过，含维护模式拒绝新任务而保留已上传任务。加载器仅完成语法检查，尚无失败路径测试，尚未实板运行。

板上已确认：FPGA Manager firmware/flags/state接口存在，state=operating，fpgautil存在，configfs已挂载。

## 待完成

1. 加载工具失败路径/排空/哈希/自检测试；验证关闭文件描述符与停机超时。
2. 五份bit经对应工具转为FPGA Manager支持的.bin，生成哈希manifest；不能直接将.bit改后缀。
3. 备份并部署服务，先用MD5执行Linux加载和真值测试。
4. 五算法切换与连续多批回归，故障固件/不兼容ABI/排空超时/加载失败测试。
5. 深入定位之前连续JTAG切换后的首拍错误；Linux加载流程通过前不宣称此问题已解决。

Manifest字段：firmware（纯文件名.bin）、sha256、algorithm（1..5）、register_abi（65537）、stream_abi（65536）。工具入口安装后为/usr/sbin/john-bitstream，可先用--check-only检查文件。无网络端固件上传/切换命令；此阶段先从Linux本地受控执行。

当前板卡仍使用已通过96/96结果核对的最新MD5基线，本阶段源码尚未上板，未提交Git。
