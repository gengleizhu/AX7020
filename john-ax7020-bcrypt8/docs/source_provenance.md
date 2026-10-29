# 源码与修改来源

2026-10-20核查：gengleizhu/john及openwall/john的bleeding-jumbo分支均为
`5184bc0b8c105f8c5978b112e723d65b2de3e63e`。本次完整克隆用户仓库并锁定该提交。
本地旧资源评估快照声明相同提交，但未携带Git元数据，本工程使用完整克隆作为来源。

`scripts/prepare.py`核验HEAD及Git工作区无修改，再复制fpga-bcrypt目录。
文件SHA-256见`reports/source_manifest.json`；算法六个Core文件未修改。
仓库LICENSE和各RTL文件中的Denis Burykin版权许可原样保留。

## 兼容变化

1. `rtl/stage1/globals.vh`：用常量表达式实现非负范围内与原`MSB`一致的宏，避免原注释续行被Vivado错误预处理。
2. `rtl/stage1/word_gen_b.v`：增加遗漏的8位`cur_range_count_max`寄存器声明。原代码在五处引用它，却没有声明；对应md5crypt/sha256crypt/sha512crypt同源文件有明确8位声明。差异见同目录`word_gen_b.patch`。
3. `sim/tb/legacy_fifo_models.sv`：仅用于同钟仿真的旧FIFO接口行为模型，源文件只放在sim_1，不进入综合。
4. 原`SIMULATION`预处理宏在两个文件集中均定义，以选中真实计算RTL。原`bcrypt`模块的`SIMULATION`参数设为0，校验和始终启用。
5. Vivado 2018.3切换仿真顶层时增量编译可能漏掉缓存的全局宏，工程关闭增量仿真编译。
   全量编译会清理XSIM目录，因此脚本先编译/展开，再复制初始化数据，最后启动仿真。
   日志出现无法读取数据文件即判失败；Expanded Key测试同时拒绝未知值，避免两个X被误认为相等。

## 原测试平台的差异

原bcrypt_test只展示波形，输出未检查且没有结束条件，checksum填0并以参数关闭校验。
其注释中的`abcde/Cost00`与实际发送的iteration_count=32不相符。
本工程使用该注释中的完整标准哈希作为独立Cost0开发向量，并用CPU参考确认；
正式Cost4/5向量来自ztex_bcrypt.c。没有把原平台注释当成已经通过的测试。

原注释列出的`0c874c66...`为每个32位字的小端排列；标准哈希解码后的网络顺序是`664c870c...`。
本工程分别记录网络24字节、Core的32位字、协议小端结果，防止整串或逐字节错误反转。
