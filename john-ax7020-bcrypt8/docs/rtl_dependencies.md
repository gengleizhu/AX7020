# RTL依赖与模块中文说明

完整原文件清单及哈希见`reports/source_manifest.json`。
每个测试实际编译文件与顺序由Vivado输出至`reports/stage1/tb_*_compile_order.txt`。
原目录中非编译资源（ISE工程、UCF、分区xml、说明图等）同样留在快照中，不套用到XC7Z020。

## 真实层次与数据流

```text
tb_core → bcrypt_core
              ├─ fsm → MC（微码ROM）
              ├─ PN_wr_addr_reg / PN_addr_reg / PD_addr_reg / S_wr_addr_reg
              └─ unit
                  ├─ P_2x32（PN/PD）
                  ├─ S（四组256×32）
                  └─ S_rd_collision_detector

tb_packet → bcrypt
              ├─ input_fifo（仿真模型）→ inpkt_header
              ├─ template_list_b → word_storage
              ├─ word_gen_b → word_gen_ram / word_storage
              ├─ bcrypt_cmp_config
              ├─ bcrypt_expand_key_b → bcrypt_data
              ├─ bcrypt_arbiter ↔ bcrypt_wrapper
              │                      └─ bcrypt_proxy → bcrypt_core（1个）
              ├─ comparator → asymm_bram_min_wr / ff32
              └─ outpkt_bcrypt → outpkt_checksum → output_fifo（仿真模型）
```

`delay`、`sync_sig`供空闲检测、输出扫描和代理延时使用；同钟协议仿真不证明sync_sig在真实跨域中的充分性。

## 文件与功能

| 文件 | 根据接口/逻辑确认的功能 |
|---|---|
| bcrypt_core.v | 8bit输入、四相byte_wr_en、start握手；init_ready/crypt_ready/empty；1bit串行输出 |
| fsm.v | 96槽微码ROM和指令指针、一级返回地址、S读写冲突异常分支 |
| unit.v | L/R/Ltmp、P/S运算组合及串行位选择；含S读写碰撞检测 |
| P_2x32.v | 32字PN和32字PD存储、迭代递减与ZF；PN为可变状态，PD为任务数据 |
| S.v | 四组256×32存储，同步读，F函数为S3+(S2 XOR (S1+S0)) |
| addr_regs.v | P/S写地址、P读地址、Salt/EK/ID读地址的微操作 |
| bcrypt_data.v | 输出1054字初始化流和31字任务流，装入迭代次数、Salt、两个32位ID |
| bcrypt_expand_key_b.v | 密码循环扩展为18字，支持x版本符号扩展 |
| bcrypt_cmp_config.v | 16字节Salt、subtype、迭代数、hash_count、比较数据、CC终止符解析 |
| bcrypt_arbiter.v | 按代理ready选择任务、初始化广播、串行结果收集、比较及结果封包调度 |
| bcrypt_wrapper.v | 代理边界1/2级寄存器，PROXY_CONF分配代理所带Core数 |
| bcrypt_proxy.v | 选择crypt_ready的物理Core；init_ready广播；扫描结果并锁定串行输出 |
| comparator.v | 片上比较，mode_cmp=0时不使用其筛选结果，但保留模块 |
| inpkt_header.v | v2头、长度、类型、ID、累加取反校验，错误粘滞 |
| template_list_b.v | WORD_LIST/TEMPLATE_LIST写入word_storage，生成word_id和列表结束标记 |
| word_gen_b.v | 直通或按范围生成候选，给出pkt_id/gen_id；本阶段直通路径验收 |
| word_storage.v | 字节索引候选缓存，full/empty握手 |
| outpkt_bcrypt.v | 活跃bcrypt输出路径，形成D2/D3/D4头及数据，连接outpkt_checksum |
| outpkt_checksum.v | 16bit输出端插入Header/Payload校验，遵守读出反压 |
| outpkt_v3.v | 同仓库备用通用输出模块；当前bcrypt.v没有实例化，不当成活跃数据路径 |
| S_data.txt | 1024×32位常量，经CPU BF_common.c常量逐项核对 |
| main.vh / bcrypt.vh | Packet、长度、比较器参数与微码/控制编码 |
| util/log2.vh | 原MSB宏，由全局兼容头的同名guard替代 |
| util/asymm_bram.v | 比较器字节写入/字读取；只在协议行为仿真中使用原模板 |
| util/fifo_sync.v | 同步FIFO辅助模块，保留供原模块依赖；编译顺序清单决定实际使用情况 |

## ISE专属依赖处置

原input_fifo引用`fifo_16_sync_8kb`和`fifo_16in_8out_2k`等FIFO Generator v9.3 IP，
源码快照未提供可直接重建的完整IP交付。原顶层还使用Spartan-6时钟、USB接口和ISE分区壳。
阶段1仿真在input_fifo/output_fifo边界替换为行为模型；单Core综合完全不依赖这些IP。
原UCF、NGC黑盒接口、dummy分区模块不用于PYNQ综合。

## 信号时序约束

- 初始化或任务传输开始后，Core输入必须连续，byte_wr_en按0001/0010/0100/1000轮转。
- init_ready只表示可接收P/MW/S初始化；初始化完成后crypt_ready表示可接收任务。
- empty变0表示结果可读。rd_en脉冲仅启动输出，随后257bit不能暂停。
- 完成结果传输后Core重新要求初始化，不能省略后续P/S重装。
- Proxy数量与物理Core数量分开：阶段1为1 wrapper、1 proxy、1物理Core。
- 原Core没有reset端口，配置初始化值和重新初始化数据流具有不同作用。
