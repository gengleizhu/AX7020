# John协议与软件任务链

依据固定版本的ztex_bcrypt.c、device_format.c、task.c、jtr_device.c、device.c、
inouttraffic.c、ztex.c与pkt_comm目录接口/调用点核查；当前没有移植整个John主机调度器。

## 主机链路

ztex_bcrypt.crypt_all准备17字节Salt/subtype及迭代次数，device_format执行任务生命周期。
task_list_create按设备划分候选；task_assign分配设备和16位递增任务ID（回绕跳过0）。
task_create_output_pkt_comm依次排队CMP_CONFIG、WORD_GEN、WORD_LIST或TEMPLATE_LIST。
任务ID写入WORD_GEN。不能误以为结果的Packet ID只来自WORD_LIST头。

pkt_comm创建Header和Checksum，device/inouttraffic执行设备收发，ztex通过libusb访问Cypress。
接收后inpkt解析D3/D4/D2，jtr_device用“设备+Packet ID”查任务，再校验Word ID和Generation ID。
task_result_new从原候选缓存恢复口令；mask路径通过Generation ID重建实际候选。
节点掉线时原task_deassign清除旧结果并将任务置为未分配。
后续UDP需要另加Session/重试代次，防止旧任务ID回绕后串入新任务。

## 字节格式

| 偏移 | 长度 | 内容 |
|---:|---:|---|
| 0 | 1 | version=2 |
| 1 | 1 | type |
| 2 | 2 | reserved，可非零 |
| 4 | 3 | Payload长度，小端 |
| 7 | 1 | reserved |
| 8 | 2 | Packet ID，小端 |
| 10 | 4 | Header checksum |
| 14 | N | Payload |
| 14+N | 4 | Payload checksum |

Checksum按4字节小端字累加，末尾不足4字节高位补0，模2^32后逐位取反；不是CRC32。
Python编码器将reserved默认置0；解码器保留字段，不能拒绝原RTL输出的reserved=0x35b9。
原C pkt_create_header不会写reserved，C测试调用方显式清零缓冲区以得到确定结果。

类型：01 WORD_LIST、02 WORD_GEN、03 CMP_CONFIG、04 TEMPLATE_LIST、D2 PROCESSING_DONE、
D3 RESULT、D4 CMP_RESULT。D3 Payload是Word ID(2)+Generation ID(4)+原始结果(24)，整包48字节。

## bcrypt配置与端序

CMP_CONFIG为Salt16字节、ASCII subtype一字节、迭代次数4字节、hash_count2字节、
比较哈希列表、CC结束字节。mode_cmp=0时本工程使用hash_count=0。
迭代次数传2^Cost，不是Cost本身。Salt将标准Base64解码后的大端32位值按小端序列化；
结果也按六个32位数小端序列化。标准字符串编码只使用前23个网络序字节，
但FPGA返回完整24字节，验证时不能无条件丢弃原始第24字节。

WORD_LIST使用零终止字串，恰好72字节的候选不追加零。上位机超过72字节的语义必须明确，
不得把多余字节误解释成下一条候选。零范围WORD_GEN的Payload为00 00 00 00 00 BB。

## 已发现的行为边界

mode_cmp=0时arbiter在发出D3后直接继续扫描，源码明确不做num_processed累计、不发D2。
后续进度按唯一(Session,任务,Word ID,Generation ID)结果计数，不能等待D2作为完成条件。

原配置解析器只检查迭代数高位等有限条件，不保证拒绝0或所有非2的幂值。
阶段1负例实际验证的是第20位越界、非法subtype、错误CC以及头/校验错误。
后续主机/PS需要严格校验标准bcrypt格式、Cost范围、目标长度、资源限制。
原解析器会在Payload最终Checksum验证前向下游流式传递内容，因此PS应先验证完整包再送PL；
PL原校验保留为第二道检测，不能把它当作事务回滚机制。
