# 结果流水修订验证记录

## 修改前的已确认结果

- bcrypt：100 MHz WNS -0.228 ns；结果计数→错误检测→输出控制长路径。
- MD5：100 MHz WNS -0.159 ns；lane BRAM→汇总选择→公共校验→状态机长路径。
- DES：100 MHz WNS +0.325 ns。
- 原生 MD5 回归：MD5CRYPT8_TEST_PASS，192 个 job（两批），24 个物理 Core 活跃。
- 公共接口+真实 MD5：两批均 PASS，最终 AXI_NATIVE_PASS ALG=3。

## 修改

1. bcrypt %48 改成握手驱动 0～11 字计数，RELEASE/复位清零。
2. 五工程加入官方 axis_register_slice:1.1，全寄存 REG_CONFIG=8，32 位数据及 TKEEP/TLAST。
3. 仿真使用同版本同配置的官方 IP，不用行为模型代替流水。
4. 导出前统一检查建立及保持时序；失败停止构建并写入不合格状态。
5. 寄存器布局、软件 ABI、算法核数量及 100 MHz 目标不变。

## 本轮验证

- 2026-10-29 10:53：包含官方 Register Slice 的公共接口仿真 ALG=1..5 全部 PASS，无 Fatal。
- Python 协议单元测试：3 个测试方法全部 PASS。
- 含官方流水的真实 MD5 两批回归已启动：build/native_md5_pipeline.log；尚未取得最终结论。
- 五工程顺序完整构建已重新启动：当前 bcrypt 综合中；本轮 WNS 尚未得到。
- 上板未执行。不能把修改前的综合报告或比特流当作本轮验证结果。

本轮只提交源码和测试记录，不上传上轮未通过时序的 bcrypt 交付文件。
