import fs from 'node:fs/promises';
import {Workbook, SpreadsheetFile, FileBlob} from '@oai/artifact-tool';

const dir='E:/zhugenglei.work/john/outputs/axi-registers-20261028';
const wb=Workbook.create();
const specs=[];
const hex=(n,w=4)=>'0x'+n.toString(16).toUpperCase().padStart(w,'0');
const cols=n=>{let s='';while(n){n--;s=String.fromCharCode(65+n%26)+s;n=Math.floor(n/26);}return s;};
function sheet(name,title,headers,rows,widths){
  const s=wb.worksheets.add(name), end=rows.length+5, last=cols(headers.length);
  s.showGridLines=false;
  s.getRange(`A1:${last}${end}`).format.font={name:'Microsoft YaHei',size:10,color:'#243247'};
  s.getRange('A2').values=[[title]];s.getRange('A2').format.font={size:15,bold:true,color:'#17365D'};
  s.getRange(`A5:${last}5`).values=[headers];
  if(rows.length)s.getRange(`A6:${last}${end}`).values=rows;
  rows.forEach((r,i)=>r.forEach((v,j)=>{if(typeof v==='string' && /^0x[0-9a-f]+$/i.test(v))s.getCell(i+5,j).setNumberFormat(`"${v}"`);}));
  const body=s.getRange(`A5:${last}${end}`);body.format.wrapText=true;body.format.verticalAlignment='top';
  widths.forEach((v,i)=>s.getRange(`${cols(i+1)}5:${cols(i+1)}${end}`).format.columnWidth=v);
  s.getRange(`A5:${last}5`).format={fill:'#24476A',font:{name:'Microsoft YaHei',size:10,bold:true,color:'#FFFFFF'},rowHeight:30,wrapText:true,verticalAlignment:'center'};
  for(let i=0;i<rows.length;i++){
    const r=i+6;
    let lines=1;
    rows[i].forEach((v,j)=>{const text=String(v??'');const width=widths[j]*0.9; const count=text.split('\n').reduce((a,l)=>a+Math.max(1,Math.ceil([...l].reduce((n,c)=>n+(c.charCodeAt(0)>255?1.9:1),0)/width)),0);lines=Math.max(lines,count);});
    s.getRange(`A${r}:${last}${r}`).format.rowHeight=Math.max(34,lines*15+10);
    if(i%2===1)s.getRange(`A${r}:${last}${r}`).format.fill='#F1F5F9';
  }
  s.freezePanes.freezeRows(5);
  const table=s.tables.add(`A5:${last}${end}`,true,'Table'+specs.length);
  table.style='TableStyleMedium2';table.showFilterButton=true;
  specs.push({name,end,last,rows:rows.length});
  return s;
}

const reg=[];
function R(off,name,access,reset,bits,desc,impl='新增统一外壳',group='公共'){
  reg.push([hex(off),name,32,access,reset,bits,desc,impl,group]);
}
function pair(off,name,desc,group='进度',impl='新增计数器'){
  R(off,name+'_LO','RO-S','0','[31:0] 低32位',desc+'；从同一次快照读取LO/HI。',impl,group);
  R(off+4,name+'_HI','RO-S','0','[31:0] 高32位',desc+'；与前一地址组成uint64，单位同LO。',impl,group);
}
R(0,'IP_MAGIC','RO','0x4A435250','[31:0] 固定签名','识别本统一控制接口；旧GPIO状态不具有本签名。');
R(4,'ABI_VERSION','RO','0x00010001','[31:16] major=1；[15:0] minor=1','拟议ABI v1.1；保留v1.0公共字段和紧凑单元窗口，追加算法及CU窗口；major不兼容则拒绝运行。');
R(8,'REGMAP_BYTES','RO','0x00010000','有效寄存器窗口字节数','统一控制IP占64 KiB；Common占前4 KiB；设备树映射长度须随本版更新。');
R(12,'HW_VERSION','RO','构建注入','[31:24] major；[23:16] minor；[15:0] patch','逻辑功能版本；不要使用编译日期代替ABI版本。');
R(16,'BUILD_DATE','RO','构建注入','uint32十进制YYYYMMDD','例如20261028；由构建脚本注入，非BCD。');
R(20,'BUILD_TIME','RO','构建注入','uint32十进制HHMMSS','例如161500；构建时间采用Asia/Shanghai。');
R(24,'BUILD_ID_LO','RO','构建注入','构建标识低32位','与HI组成64位构建ID；关联PS侧清单中的完整源码版本与Bitstream SHA-256。');
R(28,'BUILD_ID_HI','RO','构建注入','构建标识高32位','仅用于追溯，不是Bitstream完整性或认证校验。');
R(32,'ALGORITHM_ID','RO','随算法','1 bcrypt；2 descrypt；3 md5crypt；4 sha256crypt；5 sha512crypt','沿用用户原表编号；读取当前Bitstream算法，写寄存器不能切换算法。');
R(36,'UNIT_COUNT','RO','8/8/8/8/4','uint32逻辑计算单元数','bcrypt按8个可调度Core记8个逻辑单元，内部仍是1个proxy。');
R(40,'CORES_PER_UNIT','RO','1/1/3/3/4','uint32每逻辑单元底层Core数','统一计数口径；与原表C_AL_CORE_NUM对应，但明确是每单元数量。');
R(44,'TOTAL_CORE_COUNT','RO','8/8/24/24/16','uint32总Core数','UNIT_COUNT × CORES_PER_UNIT；Core数量不等于同时完成的候选数。');
R(48,'CAPABILITIES','RO','按实现置位','位定义见位域表','未实现能力必须为0；禁止根据地址存在推断支持。');
R(52,'PAYLOAD_FORMAT','RO','0x101～0x105','见算法适配表','v1统一外层包头，内层保留算法原始协议；PS预装5种编解码适配器。');
R(56,'BATCH_SLOTS','RO','可变/128/96/96/64','固定算法返回物理槽数；可变返回0','尾批需填充，并另传VALID_COUNT；bcrypt使用软件显式展开后的候选数量。');
R(60,'MAX_PASSWORD_BYTES','RO','72/8/64/32/64','uint32字节数','这是当前移植核/协议限制，不是所有软件算法实现的理论上限。');
R(64,'MAX_SALT_BYTES','RO','16/2/8/16/16','uint32字节数','DES为2个crypt字符表示12位Salt；bcrypt另有subtype字段。');
R(68,'RESULT_KIND','RO','1/2/1/1/1','1摘要记录；2候选匹配位图','DES是35位比较产生的初筛位图；不得当作最终口令命中。');
R(72,'DIGEST_BYTES','RO','24/0/16/32/64','uint32原始摘要字节数','bcrypt返回24字节内部结果，须按John规范转换比较；DES不返回完整摘要，填0。');
R(76,'FIXED_INPUT_BYTES','RO','0/1160/9992/9992/6664','内层Payload字节数，不含统一64字节头','0表示可变长；不等于AXI DMA本次传输总长度。');
R(80,'FIXED_OUTPUT_BYTES','RO','0/168/2408/3944/4664','成功时内层Payload字节数','bcrypt为48×PHYSICAL_COUNT；错误包可以只含64字节统一头。');
R(84,'MAX_INPUT_BYTES','RO','构建注入','单次允许的Payload上限，字节','bcrypt需按封装缓存与验证结果确定；不得把原始单包上限直接当整批上限。');
R(88,'MAX_OUTPUT_BYTES','RO','构建注入','单次输出Payload上限，字节','PS同时检查64+Payload <= DMA长度上限及接收缓冲区容量。');
R(92,'CLOCK_HZ','RO','100000000','统一外壳计数时钟Hz','原有工程PL接口100MHz；若核异频，单元周期须按各自时钟解释。');
R(96,'TIMEBASE_HZ','RO','1000000','超时与时间戳时基Hz','建议内部1MHz使能计数；不是额外时钟域。');
R(100,'PARAM_LIMIT_MIN','RO','见算法表','bcrypt cost最小值；其他rounds最小值','bcrypt原核接受范围需实测后写入构建清单；不能直接宣称4～31全验证。');
R(104,'PARAM_LIMIT_MAX','RO','见算法表','bcrypt cost最大值；其他rounds最大值','MD5固定1000；DES固定25；SHA256/SHA512 999999999，但实际受超时策略限制。');
R(108,'UNIT_WINDOW_STRIDE','RO','0x20','每逻辑单元状态窗口步长','单元i地址=0x400+i×0x20；最多32个逻辑单元。');
R(112,'NATIVE_STATUS','RO','原始值','保留现有顶层32位status','直接映射用于旧状态诊断，不能用统一字段解释其位含义。','映射现有status');
R(116,'PROGRESS_MODE','RO','按实现','0不可用；1整批完成；2单元批完成；3逐候选完成','只能发布实际实现粒度；不能把忙位比例当计算百分比。');
R(120,'MAX_INFLIGHT_BATCHES','RO','1','本接口同时在途批次数','v1串行批调度，DDR可双缓冲；PL不宣称支持多批并发队列。');
R(124,'STREAM_ABI_VERSION','RO','0x00010000','[31:16] major；[15:0] minor','统一DMA包头版本，与寄存器ABI独立校验。');

R(128,'COMMAND','WO-P','0','bit0 ARM；1 RELEASE；2 SNAPSHOT；3 CLEAR_DIAG；4 SOFT_RESET','单次只允许1个命令位；读回0。SOFT_RESET仅能力支持且IDLE可用。');
R(132,'STATUS','RO','初始化中','见位域表','实时状态；ARM只进入接收准备，不代表任务已经计算。');
R(136,'CMD_SEQ','RW','0','PS写入递增命令序号','写COMMAND前写序号；PS单线程/互斥锁管理全部寄存器访问。');
R(140,'CMD_ACK_SEQ','RO','0','最近处理的命令序号','成功或拒绝均更新，先更新CMD_RESULT再发布ACK；回卷按uint32处理。');
R(144,'CMD_RESULT','RO','0','0成功；其他统一错误码','命令接受结果，不代表任务计算完成；非法命令不污染正在运行的任务结果。');
R(148,'IRQ_STATUS','RW1C','0','bit0完成；1任务错；2告警；3命令拒绝','可选中断锁存状态；写1清除，硬件同周期置位优先。');
R(152,'IRQ_ENABLE','RW','0','bit0～3使能对应事件','可选。irq = OR(IRQ_STATUS & IRQ_ENABLE)；现有BD尚未接PL中断。','新增且需修改BD');
R(156,'FIRST_ERROR_CODE','RO','0','统一错误码','本批首个致命错误保持至RELEASE；读不清零。');
R(160,'FIRST_ERROR_DETAIL','RO','0','由错误类型解释','例如字节位置、字段偏移或原始状态；语义见错误码表。');
R(164,'FIRST_ERROR_UNIT','RO','0xFFFFFFFF','逻辑单元ID；FFFFFFFF表示全局或未知','禁止将未知单元记为Core0。');
R(168,'WARNING_STATUS','RW1C','0','bit0输入等待超时预警；1输出背压；2温度告警；3诊断计数饱和','可选字段必须由有效能力提供；告警上报与任务致命错误分开。');
R(172,'SNAPSHOT_SEQ','RO','0','快照序号，每完成一次SNAPSHOT递增','忙时拒绝重叠请求；完整影子数据就绪后再递增。');
R(176,'SNAPSHOT_STATUS','RO','0','bit0 BUSY；bit1 VALID','RO-S字段来自同一次影子快照；无VALID不得作为有效数据上报。');
R(180,'TIMEOUT_US','RW','0','0禁用；否则本批总超时微秒','仅IDLE可写。ARM开始到最终输出握手完成，含输入等待和输出背压；PS另有DMA看门狗。');
R(184,'WATCHDOG_US','RW','0','0禁用；否则无进展超时微秒','可选。进展事件=有效输入/输出握手或计算完成事件，慢算法需按cost/rounds设置。');
R(188,'INIT_STATUS','RO','0','bit0接口就绪；1算法初始化完成；2初始化错误','必须接原核真实init/ready信号，不可用固定延时虚报完成。');
R(192,'SELFTEST_STATUS','RO','0','0未执行；1进行中；2通过；3失败','可选PL自检。若使用PS下发已知答案测试，结果只在PS软件上报，不写成PL自检通过。');
R(196,'LAST_RESET_CAUSE','RO','构建复位','bit0上电/配置；1支持的软复位；2异常复位','PL重配置后无法保留旧PL历史；跨重配置原因由PS日志维护。');
R(200,'UNIT_BUSY_MASK','RO','0','bit i为逻辑单元i忙','仅当UNIT_STATUS_VALID对应位有效才可解释。');
R(204,'UNIT_ERROR_MASK','RO','0','bit i为逻辑单元i错误','映射各算法内部错误；bcrypt需新增逐Core观测信号。');
R(208,'UNIT_DONE_MASK','RO','0','bit i为本批单元已完成计算','本批锁存，到RELEASE清除；与输出已传输状态分开。');
R(212,'UNIT_STATUS_VALID','RO','按实现','bit i表示该单元忙/错/完成观测均可靠','未实现逐单元信息时对应位0；不根据UNIT_COUNT伪造全1。');
R(216,'LAST_COMPLETED_BATCH','RO','0','最近一次进入DONE的BATCH_ID','与当前TASK_ID、SHARD_ID一起识别；重配置后历史归PS管理。');
R(220,'TRANSFER_STATUS','RO','0','bit0输入全部接受；1计算完成；2输出TLAST握手；3错误头成功输出','PL只能确认流端握手，不能确认DDR写回完成；PS还必须检查S2MM完成。');
R(224,'ALGORITHM_REGION_MASK','RO','1/2/4/8/16','bit0～4对应算法ID1～5','当前Bitstream只有对应算法区域有效；不是节点存储的可加载镜像清单。');
R(228,'ACTIVE_ALGORITHM_BASE','RO','0x1000～0x5000','当前算法专属区相对基址','算法ID×0x1000；未知算法必须由能力和ABI协商，不硬套旧公式。');
R(232,'UNIT_REGION_BASE','RO','0x00008000','详细单元窗口起始相对地址','与0x0400处v1.0紧凑只读窗口并存，映射同一份快照数据。');
R(236,'UNIT_REGION_STRIDE','RO','0x00001000','每单元窗口字节步长','单元u地址=UNIT_REGION_BASE+u×UNIT_REGION_STRIDE。');
R(240,'CU_REGION_OFFSET','RO','0x00000100','单元内部第一个CU窗口偏移','CU c地址=单元基址+CU_REGION_OFFSET+c×CU_REGION_STRIDE。');
R(244,'CU_REGION_STRIDE','RO','0x00000100','每CU窗口字节步长','每单元最多15个CU窗口；当前五算法最多使用CU0～CU3。');
R(248,'MAX_UNIT_WINDOWS','RO','8','预留单元窗口总数','可访问u=0～7；真正存在数量读UNIT_COUNT，未实例化窗口读0。');
R(252,'MAX_CU_WINDOWS_PER_UNIT','RO','15','每单元预留CU窗口数','可访问c=0～14；Core不是候选槽，12/16候选槽不能当12/16个CU。');

R(256,'TASK_ID_LO','RW','0','64位Task ID低32位','本块0x100～0x144是影子描述符；仅IDLE写，ARM原子锁存。','新增任务描述符','任务');
R(260,'TASK_ID_HI','RW','0','64位Task ID高32位','禁止在ARM后修改；任务ID由上位机分配。','新增任务描述符','任务');
R(264,'SHARD_ID','RW','0','uint32分片ID','跨节点重新分配时保持业务分片ID，并由PS维护重试代次。','新增任务描述符','任务');
R(268,'BATCH_ID','RW','0','uint32批次ID','统一映射到四种固定算法原始Transaction ID；bcrypt由适配层映射Packet/Word/Gen ID。','新增任务描述符','任务');
R(272,'EXPECTED_ALGORITHM','RW','0','期望算法编号1～5','ARM时必须等于只读ALGORITHM_ID。','新增校验','任务');
R(276,'EXPECTED_PAYLOAD_FORMAT','RW','0','期望Payload格式','必须等于PAYLOAD_FORMAT；不同算法内部Payload不可互换。','新增校验','任务');
R(280,'INPUT_PAYLOAD_BYTES','RW','0','本批输入Payload字节数','DMA MM2S长度=64+本值；与DMA头逐项比对。','新增校验','任务');
R(284,'OUTPUT_CAPACITY_BYTES','RW','0','本批S2MM接收容量，包含64字节头','配置容量不小于成功输出最大长度；寄存器不持有DDR物理地址。','新增校验','任务');
R(288,'VALID_COUNT','RW','0','本批真实候选数','必须1～PHYSICAL_COUNT；v1仅支持前VALID_COUNT个槽有效，其余是填充。','新增有效计数','任务');
R(292,'PHYSICAL_COUNT','RW','0','实际下发候选槽总数','固定算法必须等于BATCH_SLOTS；bcrypt为显式字典展开后有限候选数。','新增校验','任务');
R(296,'EXPECTED_RESULT_PAYLOAD_BYTES','RW','0','成功输出Payload长度','固定算法等于FIXED_OUTPUT_BYTES；bcrypt为48×PHYSICAL_COUNT，须防32位乘法溢出。','新增校验','任务');
R(300,'TASK_FLAGS','RW','0','bit0 LAST_BATCH；bit1 PAYLOAD_CRC_VALID；其余0','LAST_BATCH仅供上层追溯；PL不汇总整个任务。CRC能力未实现时bit1必须0。','新增任务描述符','任务');
R(304,'PAYLOAD_CRC32','RW','0','输入Payload CRC-32/ISO-HDLC','反射多项式EDB88320，初值/异或FFFFFFFF；范围仅原始Payload字节，非UDP报文。','可选新增CRC','任务');
R(308,'BCRYPT_SUBTYPE','RW','0','bcrypt ASCII a/b/x/y；其他算法0','作为描述符诊断镜像，必须与John配置包一致；实际支持子类型需已知答案测试。','新增适配校验','任务');
R(312,'PARAM_MODE','RW','0','0参数随Payload；1统一批参数检查','v1只要求模式0；模式1仅CAP_BATCH_PARAM=1可用。','扩展保留','任务');
R(316,'ROUNDS_OR_COST','RW','0','模式0填0；模式1依算法解释','bcrypt是log2 cost，不能当作rounds；MD5/SHA为迭代轮数。','扩展保留','任务');
R(320,'SALT_LENGTH','RW','0','模式0填0；模式1单位字节','模式1时用于比对Payload参数，不能静默覆盖Payload。','扩展保留','任务');
R(324,'TARGET_COUNT','RW','0','模式0填0；模式1目标数量','当前统一方案保留原算法目标处理方式，不宣称全算法硬件目标比较。','扩展保留','任务');

pair(384,'ACCEPTED_COUNT','本批已解析接受的有效候选数，剔除尾批填充');
pair(392,'COMPLETED_COUNT','本批完成有效候选计算数，剔除填充；进度粒度见PROGRESS_MODE');
pair(400,'RESULT_RECORD_COUNT','本批已形成的物理结果记录数；DES为单元位图记录数，不能作候选进度');
pair(408,'INPUT_BYTES','MM2S到统一外壳已握手总字节数，包含统一包头');
pair(416,'OUTPUT_BYTES','统一外壳到S2MM已握手总字节数，包含统一包头');
pair(424,'ELAPSED_CYCLES','从ARM接受至完成输出或错误锁存的外壳时钟周期数');
pair(432,'COMPUTE_ACTIVE_CYCLES','任一算法单元忙时累计的墙钟周期，非各Core周期之和');
pair(440,'INPUT_STARVE_CYCLES','本批正在等待所需输入且TREADY=1/TVALID=0的周期数');
pair(448,'OUTPUT_STALL_CYCLES','输出TVALID=1且TREADY=0的周期数');
pair(456,'UPTIME_US','本次PL配置以来微秒计数','维测');
pair(464,'FIRST_ERROR_TIME_US','首个致命错误时刻，相对本次PL配置微秒','维测');
R(472,'RESULT_VALID_BYTES','RO-S','0','本批最终输出总字节数','输出成功结束后有效；错误包可能64字节，未输出TLAST时不得作为完整结果。','新增统计','结果');
R(476,'SNAPSHOT_BATCH_ID','RO-S','0','快照所属BATCH_ID','SNAPSHOT同时锁存上下文，避免PS跨批混读。','新增快照','进度');
R(480,'SNAPSHOT_TASK_LO','RO-S','0','任务低32位','与快照高32位组合。','新增快照','进度');
R(484,'SNAPSHOT_TASK_HI','RO-S','0','任务高32位','与快照低32位组合。','新增快照','进度');
R(488,'SNAPSHOT_SHARD_ID','RO-S','0','分片ID','快照必须与PS当前任务上下文匹配。','新增快照','进度');
R(492,'SNAPSHOT_STATUS_WORD','RO-S','0','STATUS快照','提供与计数器同时刻的状态。','新增快照','进度');
R(496,'SNAPSHOT_VALID_COUNT','RO-S','0','有效候选总数快照','PS计算进度=COMPLETED_COUNT/本值；本值0时上报未知。','新增快照','进度');
R(500,'SNAPSHOT_UNIT_DONE_MASK','RO-S','0','单元完成位图快照','其有效性仍受UNIT_STATUS_VALID限制。','新增快照','进度');

const diag=[
['TASK_FIFO_LEVEL','当前任务FIFO占用，单位32位Word'],['TASK_FIFO_DEPTH','任务FIFO深度，单位32位Word'],
['TASK_FIFO_HIGH_WATER','任务FIFO占用峰值，单位32位Word'],['RESULT_FIFO_LEVEL','当前结果FIFO占用，单位32位Word'],
['RESULT_FIFO_DEPTH','结果FIFO深度，单位32位Word'],['RESULT_FIFO_HIGH_WATER','结果FIFO占用峰值，单位32位Word'],
['FIFO_OVERFLOW_COUNT','FIFO溢出次数，饱和计数'],['FIFO_UNDERFLOW_COUNT','FIFO非法空读次数，饱和计数'],
['PROTOCOL_ERROR_COUNT','协议错误次数，饱和计数'],['TIMEOUT_COUNT','任务超时次数，饱和计数'],
['REJECTED_COMMAND_COUNT','拒绝命令次数，饱和计数'],['SUCCESS_BATCH_COUNT','本配置周期成功批次数，饱和计数'],
['FAILED_BATCH_COUNT','本配置周期失败批次数，饱和计数'],['LAST_INPUT_WORD_INDEX','最近解析的输入32位Word索引'],
['FSM_DEBUG','[7:0]外壳状态；[15:8]适配器状态；其余保留'],['DIAG_VALID','bit0 FIFO观测有效；bit1协议计数有效；bit2周期计数有效；bit3调试状态有效']];
diag.forEach((d,i)=>R(0x200+4*i,d[0],'RO-S','0或构建值','uint32',d[1]+'；只统计当前PL配置周期，CLEAR_DIAG按规则清除。','新增，需观测点','维测'));
R(0x240,'SCRATCH','RW','0','32位回读测试','仅接口连通测试；无算法副作用。PS可写A5A55A5A后回读，再恢复0。','新增','维测');
R(0x244,'LAST_BAD_OFFSET','RO','0','最近非法寄存器访问偏移','对齐错误、只读写入或空洞写入记录；不当作算法失败。','新增','维测');
R(0x248,'BUS_ERROR_COUNT','RO-S','0','uint32饱和计数','非法MMIO访问次数；AXI读写返回规定错误响应。','新增','维测');
R(0x280,'SENSOR_VALID','RO-S','0','bit0温度；1 VCCINT；2 VCCAUX；3 VCCBRAM','可选PL传感器代理；第一版建议PS通过Linux IIO/XADC采集，CAP_SENSOR=0。','可选，默认不实现','传感器');
R(0x284,'TEMPERATURE_MC','RO-S','0','int32，毫摄氏度','仅SENSOR_VALID.bit0=1有效；不可把无传感器的0当作0℃。','可选','传感器');
R(0x288,'VCCINT_UV','RO-S','0','uint32，微伏','只在SENSOR_VALID.bit1=1有效。','可选','传感器');
R(0x28C,'VCCAUX_UV','RO-S','0','uint32，微伏','只在SENSOR_VALID.bit2=1有效。','可选','传感器');
R(0x290,'VCCBRAM_UV','RO-S','0','uint32，微伏','只在SENSOR_VALID.bit3=1有效。','可选','传感器');
R(0x294,'SENSOR_AGE_US','RO-S','0','距离最近有效采样的微秒数','超过PS配置的新鲜度阈值则上报过期；板卡功耗/风扇转速无硬件传感器时不提供。','可选','传感器');

const seen=new Set();for(const r of reg){const n=Number(r[0]);if(n%4||seen.has(n)||n>=0x400)throw Error('register collision '+r[0]);seen.add(n);}
const s0=sheet('AXI寄存器地址表','Common公共寄存器地址表 · 分层设计稿 v1.1',
['偏移（字节）','寄存器名称','位宽','访问','复位/常量值','位域或类型','用途与访问约束','实现状态','分组'],reg,[15,32,7,9,20,42,70,23,10]);
s0.getRange('A3').values=[['拟议控制基址0x43C00000；总窗口64 KiB，Common前4 KiB；32位小端、4字节对齐。尚未实现于RTL。']];s0.tabColor='#24476A';

const regions=[
['0x0000','0x0FFF','Common公共区','0x43C00000','0x43C00FFF','所有算法','原公共地址保留；身份、控制、进度、DMA描述、维测；0x0400紧凑单元窗口保留为兼容别名。'],
...['bcrypt','descrypt','md5crypt','sha256crypt','sha512crypt'].map((a,i)=>[hex((i+1)*4096),hex((i+2)*4096-1),a+'专属区',hex(0x43C00000+(i+1)*4096,8),hex(0x43C00000+(i+2)*4096-1,8),'仅ALGORITHM_ID='+String(i+1),'未加载算法区域全部读0，写SLVERR；读取区域存在标识后才解释字段。']),
['0x6000','0x7FFF','算法扩展预留','0x43C06000','0x43C07FFF','预留','读0，写SLVERR；未来新增算法按能力表声明，不改变已有区域含义。'],
['0x8000','0xFFFF','8个单元及内部CU区','0x43C08000','0x43C0FFFF','当前算法拓扑','单元步长0x1000，CU步长0x100；该区域属于当前算法，不是五种算法并发实例。']
];
sheet('分层地址总览','64 KiB分层地址空间',['起始偏移','结束偏移','区域','示例物理起址','示例物理终址','有效条件','用途与兼容约束'],regions,[16,16,29,22,22,30,85]);

const ar=[];const aa=['bcrypt','descrypt','md5crypt','sha256crypt','sha512crypt'];
function AR(i,o,n,a,v,b,d){ar.push([aa[i-1],hex(i*4096+o),hex(o),n,a,v,b,d,'新增；尚未实现']);}
for(let i=1;i<=5;i++){
 AR(i,0,'REGION_PRESENT','RO','1','当前区域有效时1','整个非当前算法区域读0；不是五种算法同时存在。');
 AR(i,4,'REGION_ABI','RO','0x00010000','算法专属区版本1.0','与Common ABI和DMA包头版本独立；major不匹配不解释专属字段。');
 AR(i,8,'REGION_ALGORITHM_ID','RO',i,'算法编号','有效时与Common ALGORITHM_ID相同。');
 AR(i,12,'REGION_CAPABILITIES','RO','按实现','bit0参数镜像；1微程序标识；2原始诊断','未实现对应能力必须0；[31:3]保留。');
 AR(i,16,'PARAM_VALID','RO-S','0','bit0统一参数有效；bit1原始诊断有效','快照值。批内参数不一致时bit0=0，不能取第一个job代表整批。');
 AR(i,20,'MICROCODE_BUILD_ID','RO','构建注入或0','微程序版本标识','REGION_CAPABILITIES.bit1=1才有效；无微程序的设计返回0。');
 AR(i,24,'ALGORITHM_NATIVE_STATUS','RO-S','0','原始算法诊断状态','PARAM_VALID.bit1=1才解释；位定义遵循对应原核，不跨算法复用解释。');
 AR(i,28,'PARAM_SCOPE','RO-S','0','0无参数；1整批一致；2批内混合','数据来源是已接受的Payload解析结果；混合参数通过任务清单逐job查询，不凭镜像推断。');
}
AR(1,0x20,'BCRYPT_COST_LOG2','RO-S','0','cost指数','PARAM_VALID.bit0=1有效；从实际接受的John配置转换，不能与迭代次数混用。');
AR(1,0x24,'BCRYPT_SUBTYPE_ACTIVE','RO-S','0','ASCII a/b/x/y','当前生效子类型；支持范围需已知答案测试。');
AR(1,0x28,'BCRYPT_ITERATION_COUNT','RO-S','0','原始配置中的32位迭代计数','与COST含义分别记录；转换遵循原John核。');
AR(1,0x2C,'BCRYPT_PROXY_COUNT','RO','1','物理proxy数','当前1 proxy带8 Core；逻辑单元按8个Core展开。');
AR(1,0x30,'BCRYPT_PACKET_VERSION','RO','2','原生John协议版本','不是统一DMA包头版本。');
AR(1,0x34,'BCRYPT_PACKET_STATUS','RO-S','0','原生包解析诊断','需接解析器真实状态；可用于定位checksum/type/length错误。');
AR(2,0x20,'DES_ITERATIONS','RO','25','固定DES加密次数','算法固定能力常量。');
AR(2,0x24,'DES_SALT12_ACTIVE','RO-S','0','[11:0] Salt；高20位0','仅整批目标/Salt一致且PARAM_VALID.bit0=1有效；否则值置0且标混合。');
AR(2,0x28,'DES_COMPARE_BITS','RO','35','硬件目标初筛位数','不是完整64位目标验证；PS必须完整复核。');
AR(2,0x2C,'DES_CANDIDATES_PER_UNIT','RO','16','每单元候选槽数','单元内1个Core；候选槽不属于CU地址层级。');
AR(2,0x30,'DES_COMPARATOR_STATUS','RO-S','0','比较器汇总诊断','真实观测点新增后有效；每单元错误在单元窗口读取。');
for(const i of [3,4,5]){
 const prefix=i===3?'MD5':i===4?'SHA256':'SHA512';
 AR(i,0x20,prefix+'_ROUNDS_ACTIVE','RO-S','0','整批一致时的实际rounds','PARAM_VALID.bit0=1有效；参数直接来自DMA载荷，不另设可写第二来源。');
 AR(i,0x24,prefix+'_ROUNDS_MIN','RO',1000,'最小轮数','当前移植协议支持范围。');
 AR(i,0x28,prefix+'_ROUNDS_MAX','RO',i===3?1000:999999999,'最大轮数','数值合法不代表可在指定超时时间内完成。');
 AR(i,0x2C,prefix+'_SALT_LENGTH_ACTIVE','RO-S','0','整批一致时的Salt字节数','任一候选Salt内容/长度或轮数不同即按混合参数处理，bit0=0。');
 AR(i,0x30,prefix+'_SLOTS_PER_UNIT','RO',i===5?16:12,'每单元任务槽数','与CORES_PER_UNIT不同，不能用于CU窗口索引。');
 AR(i,0x34,prefix+'_VARIANT_ID','RO',i===3?1:i===4?5:6,'crypt格式编号','分别对应$1$、$5$、$6$；MD5不含APR1。');
}
ar.sort((a,b)=>Number(a[1])-Number(b[1]));
sheet('算法专属寄存器','五个算法专属区 · 参数镜像与诊断',['算法','全局偏移','区内偏移','名称','访问','复位/常量','位域/单位','语义与有效条件','实现状态'],ar,[17,15,15,35,10,22,46,85,23]);

const windows=[];
for(let u=0;u<8;u++){
 const ub=0x8000+u*0x1000;
 windows.push([u,'单元公共',hex(ub),hex(ub+255),hex(0x43C00000+ub,8),'前4算法均存在；SHA512仅u<4','+0x000～0x0FF，模板见单元CU字段定义']);
 for(let c=0;c<15;c++){
  const cb=ub+0x100+c*0x100;
  const active=c===0?(u<4?'全部5算法':'bcrypt/DES/MD5/SHA256'):c<3?(u<4?'MD5/SHA256/SHA512':'MD5/SHA256'):c===3&&u<4?'SHA512':'当前五算法不实例化';
  windows.push([u,'CU'+c,hex(cb),hex(cb+255),hex(0x43C00000+cb,8),active,'只读观测。未实例化返回0；已存在但未接观测点则VALID=0。']);
 }
}
sheet('单元CU地址展开','8个单元与每单元15个预留CU窗口',['单元u','层级','起始偏移','结束偏移','示例物理基址','当前拓扑存在条件','访问约束'],windows,[10,15,16,16,24,42,83]);

const uf=[];
function UF(level,o,name,access,bits,desc){uf.push([level,hex(o),name,access,bits,desc,'新增观测；未验证前有效位为0']);}
for(const level of ['单元公共','CU']){
 UF(level,0,'PRESENT','RO','0不存在；1实际实例化','存在性与可观测性分开；即使尚未接统计信号，存在的硬件仍可PRESENT=1。');
 UF(level,4,'OBS_VALID','RO-S','bit0状态；1完成计数；2活跃周期；3等待周期；4任务上下文；5原生状态','未实现能力对应位0；禁止将不可观测值当作0进度/空闲。');
 UF(level,8,'STATE','RO-S','bit0 busy；1 done；2 error；3 init_done','done本批锁存；由Common RELEASE统一清除；仅OBS_VALID.bit0=1有效。');
 UF(level,12,'ERROR_CODE','RO-S','统一错误码；0无错误','需要有效状态；错误详情保存原生状态，首个错误汇总至Common。');
 UF(level,16,'COMPLETED_LO','RO-S','已完成有效候选数低32位','不计填充；CU需要真实候选归属才能累加。不提供CU观测时保留单元级统计。');
 UF(level,20,'COMPLETED_HI','RO-S','已完成有效候选数高32位','同一次Common SNAPSHOT，先确认OBS_VALID.bit1。');
 UF(level,24,'ACTIVE_CYCLES_LO','RO-S','活跃周期低32位','同CLOCK_HZ时间基准；单元取任意CU活跃的墙钟周期，不将并行CU周期相加。');
 UF(level,28,'ACTIVE_CYCLES_HI','RO-S','活跃周期高32位','与LO共享快照；OBS_VALID.bit2=1有效。');
 UF(level,32,'WAIT_CYCLES_LO','RO-S','等待周期低32位','有待执行任务且等待输入/调度/结果接收的周期；未分配任务的空闲不计入。');
 UF(level,36,'WAIT_CYCLES_HI','RO-S','等待周期高32位','等待与活跃事件须定义为互斥；OBS_VALID.bit3=1有效。');
 UF(level,40,'TASK_ID_LO','RO-S','当前任务ID低32位','与高32位、BATCH_ID及Common快照对应；OBS_VALID.bit4=1有效。');
 UF(level,44,'TASK_ID_HI','RO-S','当前任务ID高32位','候选slot/job_id不是任务ID；v1单批在途，分片上下文取Common。');
 UF(level,48,'BATCH_ID','RO-S','当前批次ID','批内多个候选共享该ID，不能作为CU候选ID。');
 UF(level,52,'NATIVE_STATUS','RO-S','原生诊断位','仅OBS_VALID.bit5=1有效；各算法解释可能不同。');
 UF(level,56,level==='单元公共'?'CU_COUNT':'CU_INDEX','RO',level==='单元公共'?'当前单元物理Core数量':'当前CU索引c','按实际硬件拓扑编译常量；不存在窗口整页读0。');
 UF(level,60,'SNAPSHOT_SEQ','RO-S','该窗口的快照序号','和Common SNAPSHOT_SEQ一致；不能通过逐窗口自行抓取导致时间不同步。');
}
UF('两级共有',64,'RESERVED_040_0FF','RO','+0x040～+0x0FF保留','读0，写SLVERR。v1.1不开放逐CU启动/复位/下发；共享John调度器由Common控制。');
sheet('单元CU字段定义','单元公共块与CU块字段模板',['层级','块内偏移','寄存器','访问','位域/单位','含义与一致性要求','实现状态'],uf,[19,16,27,10,55,92,30]);

const rules=[
['地址空间','统一控制IP','0x43C00000～0x43C0FFFF（拟议64 KiB）','五个BD显式固定同一基址和64 KiB译码范围；设备树reg长度改为0x10000。最终以XSA核对，无冲突后冻结。'],
['地址空间','现有AXI DMA','0x40400000～0x4040FFFF','保留AMD DMA自身寄存器；DDR地址和DMA长度由Linux DMA驱动管理，不重复映射进自定义控制IP。'],
['地址空间','现有AXI GPIO','0x41200000～0x4120FFFF','当前为原生32位status；过渡期保留，统一外壳NATIVE_STATUS镜像它。'],
['分区','0x000～0x07F','只读身份与能力','算法ID、ABI、构建版本、Core数、数据大小、格式。'],
['分区','0x080～0x0FF','命令、状态与区域发现','0x0E0～0x0FF新增算法有效位图、当前算法基址、单元/CU基址与步长。'],
['分区','0x100～0x17F','任务影子描述符','0x148～0x17F暂保留；ARM时校验并锁存。'],
['分区','0x180～0x1FF','进度、结果、快照','0x1F8～0x1FF暂保留。'],
['分区','0x200～0x27F','维测与FIFO','0x24C～0x27F暂保留；统计值需要DIAG_VALID。'],
['分区','0x280～0x2FF','可选传感器','0x298～0x3FF暂保留。'],
['分区','0x400～0x7FF','原32个紧凑单元窗口，兼容保留','步长0x20；复用新单元窗口快照观测，u>=8读0；0x800～0xFFF仍保留。'],
['分区','0x1000～0x5FFF','5个算法专属区域','每算法4 KiB，仅当前算法区有效；未加载区读0、写SLVERR。'],
['分区','0x6000～0x7FFF','扩展预留','读0、写SLVERR；未来算法不可复用已分配编号和地址语义。'],
['分区','0x8000～0xFFFF','8个单元及内部CU窗口','单元步长0x1000，单元公共块256B，CU0～CU14每个256B；CU=底层Core，不是候选槽。'],
['总线规则','宽度/字节序','32位小端，地址为字节偏移','每个寄存器4字节对齐；8/16位字段放在32位字中。ARM与PL统一uint32访问。'],
['总线规则','WSTRB','所有写操作要求WSTRB=0xF','部分写/非对齐访问返回SLVERR且不产生副作用；这是本IP的设计约定，需在RTL实现。'],
['总线规则','RO / RW / WO-P / RW1C','只读 / 读写 / 写1命令脉冲 / 写1清位','WO-P读0；写RO或空洞返回SLVERR；保留地址读0，保留位写1拒绝。越出窗口由互连DECERR。'],
['总线规则','RO-S','快照只读','读操作无清除副作用。SNAPSHOT完成前数据无效；计数器不得通过两次实时32位读拼64位。'],
['命令','ARM=0x01','只允许IDLE且INIT_DONE且无待释放结果','校验影子描述符/能力/长度，成功后锁存并置ARMED，开始总超时计时；失败保持IDLE。'],
['命令','RELEASE=0x02','只允许DONE或可恢复ERROR，且PS确认DMA已静止','清当前批上下文/本批计数/本批错误，回IDLE；不清累计诊断。NEED_RELOAD=1时拒绝。'],
['命令','SNAPSHOT=0x04','任意非重配置状态，前一快照完成后','锁存RO-S和上下文；跨时钟用请求/应答握手，完成再改SEQ/VALID。'],
['命令','CLEAR_DIAG=0x08','仅IDLE','清累计错误/成功失败/总线错误计数与FIFO峰值；不改变身份、时基、FIFO深度、有效能力或当前传感器。'],
['命令','SOFT_RESET=0x10','仅IDLE且CAP_SOFT_RESET=1','第一版原John核不保证可复位，默认能力0。不可将清状态位当作恢复计算核。'],
['命令','互斥与ACK','单进程驱动所有MMIO写入','依次写CMD_SEQ、内存屏障、COMMAND；等ACK_SEQ一致后检查CMD_RESULT；ACK与任务DONE不同。'],
['STATUS','bit0 READY','可接受ARM','仅STATE=IDLE、初始化成功且没有未释放结果时为1。'],
['STATUS','bit1 BUSY','当前批占用','ARMED/RECEIVING/RUNNING/DRAINING=1；DONE/ERROR=0，但仍不能直接ARM。'],
['STATUS','bit2 DONE / bit3 ERROR','成功终态锁存 / 错误终态锁存','DONE只表示PL最终输出TLAST已握手；PS仍须等待S2MM完成并验证结果。'],
['STATUS','bit4 INIT_DONE / bit5 NEED_RELOAD','初始化已完成 / 必须重载','原核内部锁死或有未排空计算时，NEED_RELOAD置1，禁止仅RELEASE恢复。'],
['STATUS','bit6 INPUT_COMPLETE / bit7 COMPUTE_DONE','输入字节接收完成 / 所有物理槽计算完成','两者都不等于DDR结果可读。失败时不能宣布计算完成。'],
['STATUS','bit8 OUTPUT_COMPLETE / bit9 RESULT_VALID','流输出结束 / 完整成功结果已输出','RESULT_VALID仅成功批为1；错误头另由TRANSFER_STATUS表示。'],
['STATUS','bit10 WARNING / bit11 SNAP_VALID','存在告警 / 存在有效快照','[15:12]=0；[19:16]=STATE；[31:20]=0。'],
['STATE','0 INIT；1 IDLE；2 ARMED；3 RECEIVING','4 RUNNING；5 DRAINING；6 DONE；7 ERROR','输入和计算可重叠；接收阶段优先标RECEIVING。收到完整输入后标RUNNING，计算结束再DRAINING。'],
['CAPABILITIES','bit0统一流包头；1完成计数；2逐单元状态','bit3 IRQ；4 FIFO观测；5传感器代理','这6项按实际实现置位。v1交付要求bit0/1=1；不支持的状态字段必须伴随无效指示。'],
['CAPABILITIES','bit6安全软复位；7输入CRC32；8 PL自检','bit9统一批参数校验；10可变批；11部分目标比较','bcrypt为可变批；DES为部分目标比较。[31:12]保留0。'],
['快照','读取顺序','发SNAPSHOT→等待ACK成功→BUSY=0且SEQ更新→读RO-S→复读SEQ','SEQ应保持一致，否则重读。READ的64位LO/HI共享影子快照。逐单元窗口也包含在同一次快照。'],
['计数','进度定义','COMPLETED_COUNT / VALID_COUNT','排除填充候选；若只做整批完成观测，则中途显示粗粒度/未知剩余时间，不能按耗时猜完成数。'],
['计数','64位与饱和','64位时间/候选/字节计数按uint64；32位诊断计数饱和','饱和后不回卷且WARNING.bit3=1。吞吐率由PS对两次快照差分计算，单位候选/秒。'],
['结果','计算完成与任务完成','PL算完→流输出结束→S2MM完成→PS校验→UDP可靠确认','上位机确认接收前PS保留结果副本；网络重传不能再次执行同一个批次。'],
['重配置','PL全量Bitstream切换','暂停调度、排空/取消、停DMA、屏蔽中断、隔离PL访问、加载、重建驱动、校验、自检','当前不属于动态部分重配置。Linux在PS继续运行，但PL寄存器/DMA/计数会丢失。'],
['兼容','只更换Bitstream的前提','固定PS配置、时钟、DMA参数、地址、IRQ与设备树接口','五个新Bitstream实现同一外壳；PS预装五种Payload编解码后无需改程序，只切换格式/配置。'],
['兼容','v1.0到v1.1','公共地址和含义保留，minor升为1','REGMAP_BYTES扩大到64 KiB；旧软件仅访问Common仍可兼容，新软件必须更新映射长度后使用扩展区。两版均为未实现的设计稿。'],
['兼容','旧紧凑窗口与详细窗口','共用一份观测快照，按原位定义转换','旧UNIT_STATE的valid/busy/done/error按旧布局组合，不是对新STATE直接逐字节别名；不得重复计数。'],
['计数','CU统计有效性','先建立候选归属及完成事件再发布CU计数','若底层Core协作处理同一候选，不可相加当候选完成数；以单元适配器去重后的完成数为权威。'],
['参数','专属区默认只读','运行参数由DMA任务Payload提供','算法专属区显示实际生效参数镜像；批内不同参数则PARAM_SCOPE=2、PARAM_VALID.bit0=0，参数镜像值置0。'],
['能力','存在与可观测','PRESENT与OBS_VALID分开','不存在窗口全0；存在但无观测接线的窗口PRESENT=1、OBS_VALID=0；不能用0状态推断空闲。'],
['兼容','原生格式差异','统一寄存器不能自动统一算法输入输出','本版统一64字节外层头，保留内层John/固定批格式。完全无算法分支需要后续PL统一候选记录转换。'],
['可选单元窗口','0x400+i×0x20，i=0～31','+0x00 UNIT_STATE；+0x04 UNIT_ERROR；+0x08 DONE_COUNT_LO；+0x0C HI','UNIT_STATE bit0 valid；bit1 busy；bit2 done；bit3 error；其余0。DONE_COUNT为该单元有效候选完成数。'],
['可选单元窗口','后16字节','+0x10 ACTIVE_CYCLES_LO；+0x14 HI；+0x18 NATIVE_STATUS；+0x1C保留','均RO-S；不存在的单元全部读0、valid=0；写返回SLVERR。完整窗口需CAP_UNIT_STATUS。'],
];
sheet('位域与访问规则','位域、状态机与兼容规则',['分类','对象','定义','实施说明'],rules,[17,37,62,85]);

const alg=[
['bcrypt',1,8,1,8,'1个原John proxy管理8个Core；逻辑单元按Core计',72,'16字节二进制salt + subtype','cost指数；原配置载荷使用迭代计数，转换需核对John定义','可变，限定显式展开字典；v1不开放未知数量的掩码生成','0x101','John v2，输入type1/2/3/4，单包payload+18字节','48 × PHYSICAL_COUNT','每条D3：10字节头+4校验+word_id16+gen_id32+结果24字节+4校验','当前每条D3有TLAST；新增聚合后整批仅最后一拍TLAST。需连接真实idle/init/完成事件。','24字节内部结果须用现有John规则还原并与目标校验，不能直接当标准字符串。'],
['descrypt',2,8,1,8,'8个DES Core，每Core16候选',8,'2个crypt字符，解析为12位Salt','固定25次DES加密','128槽/批，每单元16槽','0x102','DCS8+tag+8×DCS1单元任务；1160字节','168字节','DCR8+tag；每单元ID + DCR1 + 16位初筛mask + cycles + status','只比较目标的35位。PS按批次/单元/槽位回查候选，并做完整DEScrypt验证。','有效候选前缀外的填充命中必须丢弃；不能将mask置位数作为完成数。'],
['md5crypt',3,8,3,24,'8个md5unit，每单元3个MD5 Core、12个任务',64,'1～8个crypt字符，当前不支持空Salt','固定1000','96槽/批，每单元12槽','0x103','DMS8+tag+96×104字节job；9992字节','2408字节','DMR8+tag；每单元ID + JMR8 + cycles + 12×(job_id64+digest16)','job含rounds、salt长度/16B缓冲、job_id、口令长度、保留0、口令64B。','只覆盖$1$ md5crypt；不能宣称覆盖APR1或其他MD5变体。'],
['sha256crypt',4,8,3,24,'8个sha256unit，每单元3个SHA256 Core、12个任务',32,'1～16字节；禁止NUL与$','1000～999999999；默认5000','96槽/批，每单元12槽','0x104','SHS8+tag+96×104字节job；9992字节','3944字节','SHR8+tag；每单元ID + JHS8 + cycles + 12×(job_id64+digest32)','口令上限按当前RTL/codec为32字节，虽然输入保留了64字节缓冲区。','PS按$5$编码规则进行目标比较；返回摘要不等于完整crypt字符串。'],
['sha512crypt',5,4,4,16,'4个sha512unit，每单元4个SHA512 Core、16个任务',64,'1～16字节；禁止NUL与$','1000～999999999；默认5000','64槽/批，每单元16槽','0x105','SHS4+tag+64×104字节job；6664字节','4664字节','SHR4+tag；每单元ID + JHS4 + cycles + 16×(job_id64+digest64)','单元数4，不是4个底层Core。高rounds下PS与PL超时参数必须同步配置。','PS按$6$编码规则进行目标比较。']
];
const algLabels=['算法','算法ID','单元数','每单元Core','总Core','内部结构','最大口令B','Salt约束','迭代参数','物理批规模','格式ID（拟议）','现有输入Payload','成功输出Payload','现有结果内容','需要处理的差异','结果验证'];
sheet('五算法适配','算法能力及现有Payload映射',['对比字段',...alg.map(x=>x[0])],algLabels.slice(1).map((label,i)=>[label,...alg.map(x=>x[i+1])]),[23,44,44,44,44,44]);

const stream=[];
function P(kind,off,name,type,meaning){stream.push([kind,off,name,type,meaning]);}
const inFields=[
['MAGIC','0x3151544A（小端字节JTQ1）','统一请求签名'],['STREAM_ABI','0x00010000','major16/minor16'],['HEADER_BYTES','64','v1固定64字节'],['TOTAL_BYTES','uint32','64+INPUT_PAYLOAD_BYTES'],
['ALGORITHM_ID','uint32','与描述符EXPECTED_ALGORITHM和只读能力一致'],['PAYLOAD_FORMAT','uint32','0x101～0x105'],['TASK_ID_LO','uint32','任务ID低32位'],['TASK_ID_HI','uint32','任务ID高32位'],
['SHARD_ID','uint32','分片ID'],['BATCH_ID','uint32','批次ID，原生tag应相同'],['VALID_COUNT','uint32','前缀有效候选数'],['PHYSICAL_COUNT','uint32','包括填充的实际槽数'],
['EXPECTED_RESULT_PAYLOAD_BYTES','uint32','成功输出Payload长度，不含统一头'],['TASK_FLAGS','uint32','bit0最后批；bit1Payload CRC有效；其余0'],['PAYLOAD_CRC32','uint32','未启用时必须0'],['RESERVED','0','必须0']];
inFields.forEach((v,i)=>P('请求头',hex(i*4),v[0],v[1],v[2]+'；PL校验后才接受对应任务。'));
const outFields=[
['MAGIC','0x3152544A（小端字节JTR1）','统一结果签名'],['STREAM_ABI','0x00010000','major16/minor16'],['HEADER_BYTES','64','v1固定64'],['TOTAL_BYTES','uint32','本包总字节数，成功64+原生结果长度，错误可为64'],
['ALGORITHM_ID','uint32','实际计算算法'],['PAYLOAD_FORMAT','uint32','原生结果格式'],['TASK_ID_LO','uint32','原任务低32位'],['TASK_ID_HI','uint32','原任务高32位'],
['SHARD_ID','uint32','原分片ID'],['BATCH_ID','uint32','原批次ID'],['STATUS_CODE','uint32','0成功，其余见错误码表'],['VALID_COMPLETED_COUNT','uint32','成功时等于VALID_COUNT；失败时仅表示已完成数，不可当整批成功'],
['PAYLOAD_BYTES','uint32','本包实际原生Payload字节数'],['PHYSICAL_RESULT_RECORDS','uint32','bcrypt=N；DES=8个位图记录；MD5/SHA256=96；SHA512=64；错误头为0'],['RESULT_FLAGS','uint32','bit0仅初筛（DES）；bit1存在填充槽；其余0'],['RESERVED','0','必须0']];
outFields.forEach((v,i)=>P('结果头',hex(i*4),v[0],v[1],v[2]));
[
['流规则','—','数据宽度','32位AXI Stream','小端。有效字节由TKEEP表示，计数仅在TVALID && TREADY时增加。'],
['流规则','—','TLAST','一批一个外层包','请求总长度最后一拍TLAST；中途不允许TLAST。结果只有整批统一包末尾TLAST。'],
['流规则','—','TKEEP','非末拍0xF','末拍仅允许0x1/0x3/0x7/0xF，且与TOTAL_BYTES模4匹配；不支持稀疏byte lane。'],
['流规则','0x40起','Payload','原生算法协议','统一外壳剥头后把Payload交给对应适配器；原John校验和继续保留，不被CRC取代。'],
['流规则','—','尾批','前VALID_COUNT有效','固定批不足时PS用合法候选填满，job_id仍唯一，并保留有效槽映射；上报结果与进度剔除填充。'],
['bcrypt适配','—','有限批','物理候选数N','v1由PS显式展开候选并映射Word/Gen/Packet ID；禁用无法准确预知结果数的生成任务。'],
['bcrypt适配','—','结果聚合','N×48字节','消费内部每条D3的TLAST，验证ID和长度后缓存/聚合。N条全部完成才输出一个外层包；与DMA简单模式兼容。'],
['结果策略','—','推荐先缓存再发','BRAM或受限批大小','先完成整批再发送统一结果头可确定错误码与长度；会增加存储资源，需重新综合评估MAX_INPUT/OUTPUT。'],
['结果策略','—','失败','任务完整性','若输出尚未开始且输出通道可用，发送64字节错误头；输出中途失败可能无完整包，由PS超时和寄存器诊断处理。'],
['一致性','—','校验不回滚','批次失败即整体作废','CRC在末尾才知结果，流式喂核可能已开始计算；错误时不发布成功结果，必要时重载PL。'],
['长度示例','—','DES / MD5','请求1224 / 10056字节','含64字节头；成功输出232 / 2472字节。'],
['长度示例','—','SHA256 / SHA512','请求10056 / 6728字节','含64字节头；成功输出4008 / 4728字节。'],
['长度示例','—','bcrypt','请求64+原生包流长度','成功输出64+48×N；原生单包Payload上限1048558不代表整批缓存上限。'],
['PS标准结果','—','面向Python的平台记录','软件层结构','task_id、shard_id、batch_id、candidate_id、algorithm_id、result_kind、digest或provisional_match、verified_match、error_code。'],
['PS标准结果','—','目标校验对象','PS保留完整目标','MD5/SHA/bcrypt由PS比较；DES初筛结果必须完整复核。标准记录不直接暴露算法内部字节序给高层平台。'],
].forEach(r=>stream.push(r));
sheet('DMA任务与结果','统一DMA包头与批量数据约定',['方向/分类','字节偏移','字段','值/类型','定义与约束'],stream,[19,14,38,39,98]);

const errs=[
['0x00000000','OK','成功','命令或任务成功','按所在字段区分ARM成功与计算成功'],
['0x00000001','BAD_STATE','命令','状态不允许执行命令','CMD_RESULT报错，DETAIL记录STATE；不打断正在运行的任务'],
['0x00000002','UNSUPPORTED','命令','命令、参数模式或能力未支持','检查CAPABILITIES，禁止反复尝试软复位'],
['0x00000003','ABI_MISMATCH','协议','包头或寄存器ABI不兼容','DETAIL记录收到的版本；拒绝本批'],
['0x00000004','ALGORITHM_MISMATCH','协议','任务算法与当前Bitstream不符','DETAIL记录请求算法ID；PS先调度正确算法镜像'],
['0x00000005','LENGTH_ERROR','协议','字节数/槽数/结果容量不符','DETAIL记录出错字段的包头或寄存器偏移'],
['0x00000006','HEADER_ERROR','协议','魔数、保留位或格式ID不符','DETAIL记录字段偏移'],
['0x00000007','CHECKSUM_ERROR','协议','John校验或可选CRC不符','DETAIL 1=John头；2=John载荷；3=外层Payload CRC'],
['0x00000008','INVALID_PARAMETER','参数','口令/Salt/rounds/cost/subtype不支持','DETAIL记录Payload字节偏移；拒绝本批'],
['0x00000009','STREAM_FRAMING','协议','TLAST/TKEEP错误','DETAIL记录当前输入Word索引'],
['0x0000000A','CORE_FAULT','计算','算法核或内部仲裁器故障','DETAIL保留原始状态，UNIT给单元ID；通常需重载'],
['0x0000000B','COMPUTE_TIMEOUT','超时','超过TIMEOUT_US','保存快照、停DMA、排除网络因素后重载；错误不等于无匹配'],
['0x0000000C','FIFO_FAULT','数据通道','FIFO溢出或非法空读','DETAIL bit0输入溢出；1输入空读；2输出溢出；3输出空读'],
['0x0000000D','INIT_FAILURE','初始化','原核初始化未完成/失败','禁止READY；检查时钟、复位、ROM初始化'],
['0x0000000E','UNEXPECTED_RESET','复位','任务期间复位导致会话无效','NEED_RELOAD=1；重配置并从PS日志恢复未提交批'],
['0x0000000F','RESULT_INTEGRITY','结果','结果长度/ID/数量重复或缺失','DETAIL记录结果索引；整批作废，不返回部分成功'],
['0x00000010','WATCHDOG_TIMEOUT','超时','无进展看门狗超时','与总超时区分；慢算法需合理阈值'],
['0x00010001','PS_DMA_ERROR','PS软件','DMA硬件/驱动错误','不写进PL FIRST_ERROR；软件告警包含DMA状态与任务ID'],
['0x00010002','PS_DMA_TIMEOUT','PS软件','收发DMA未按期完成','检查PL状态、TLAST、背压和中断；不只看PL DONE'],
['0x00010003','PS_LOAD_FAILURE','PS软件','Bitstream加载/身份校验失败','节点停止接任务，保留上一个成功构建信息'],
['0x00010004','PS_NETWORK_TIMEOUT','PS软件','UDP重传仍未确认','仅重发缓存结果；不自动重复计算已提交批'],
['0x00010005','PS_RESULT_INVALID','PS软件','结果ID、校验或完整性不符','保存原始帧以定位，拒绝提交到平台'],
['0x00010006','PS_SELFTEST_FAILED','PS软件','已知答案测试失败','节点不注册为可用，不宣称PL自检通过'],
];
sheet('错误码','统一错误码与恢复处理',['错误码','名称','归属','含义','处理及DETAIL语义'],errs,[17,31,17,48,88]);

const ops=[
['方案评估','通信链路','高层平台→Python接口→UDP→PS Linux节点服务→AXI-Lite/DMA→PL','可行。Python负责协议适配和平台接口，PS负责节点执行及可靠传输，PL负责计算。'],
['首次接入','硬件平台','统一PS/DDR/时钟/地址/IRQ/DMA参数并生成新XSA','当前统一寄存器尚未在RTL实现；五个旧Bitstream不具备本表ABI。'],
['首次接入','Linux驱动','通过设备树描述固定控制IP和DMA；使用受支持DMA内核接口管理缓冲区','HP0路径必须处理缓存一致性和DMA映射；普通Python bytearray不能直接当DMA物理缓冲区。'],
['首次接入','网络配置','固定节点ID、MAC/IP及端口由PS管理','网络地址、节点在线状态属于软件，不需要搬进PL寄存器。'],
['算法切换1','暂停与保存','节点标记SWITCHING，停止新批次，完成或取消当前批，保存已收到结果','上位机能看到切换状态；未完成分片由任务管理器重新调度。'],
['算法切换2','停DMA和隔离','等待/终止DMA，屏蔽IRQ，停止MMIO轮询，使用平台支持的隔离与重配置流程','禁止在PL重配置期间访问其AXI从设备；全量重配置后DMA驱动需协调复位/解绑重绑。'],
['算法切换3','加载与核验','Linux FPGA Manager加载适配的镜像；恢复设备访问，读MAGIC/ABI/算法/构建ID/能力','Bitstream文件格式、设备树与驱动以PetaLinux2020.1实际支持验证；仅有.bit文件不保证可直接使用。'],
['算法切换4','初始化与自检','等待真实INIT_DONE；执行每算法已知答案测试；通过后节点READY','将构建ID、软件版本、可用算法能力上报Python。'],
['任务提交1','UDP接收','校验session_id、node_id、task/shard/batch、分片序号、长度、应用校验','UDP会丢包、重复和乱序；PS先完整重组/去重再提交，不能按收到多少报文就算多少任务。'],
['任务提交2','参数与批处理','验证完整目标与算法约束；拆固定批，合法填充，保留candidate_id映射','尾批只统计VALID_COUNT；参数仍通过Payload传递，寄存器是控制和诊断描述。'],
['任务提交3','准备缓冲','分配/映射DMA缓冲，编码64字节头和原生Payload；准备输出容量','请求总长度与头/TLAST一致；接收长度至少能放成功结果。'],
['任务提交4','ARM','读READY，填写0x100描述符及超时；写CMD_SEQ、COMMAND.ARM并检查ACK','ARM成功后外壳等输入；未成功不得启动MM2S。'],
['任务提交5','DMA启动','先准备S2MM接收，再启动MM2S发送','避免结果早到导致长期背压。DMA内核驱动统一拥有DMA寄存器，用户态不可并发修改。'],
['执行监控','定时快照','建议100～500ms快照一次；读取STATUS、完成数、吞吐、FIFO/背压、错误','频率为建议可配置；长rounds任务可降低频率，错误/完成立即上报。'],
['执行监控','进度表达','本批计算进度=completed/valid；分片进度由PS累计已提交成功批与当前有效完成数','计算进度100%仍可处于结果传输；平台任务完成要等待结果完整性验证和确认。'],
['结果接收1','完成条件','等待S2MM完成、取得实际接收字节数，再校验统一头、ID、长度和原生结果','PL DONE或COMPUTE_DONE不能单独作为DDR数据可用条件；错误流可能需超时退出。'],
['结果接收2','验证与持久化','解析对应Payload，过滤填充，DES完整复核，形成标准candidate记录','按session+task+shard+batch去重；PS在释放DMA缓冲前拷贝/持久化待确认结果。'],
['结果接收3','释放与回传','DMA静止后发RELEASE；UDP分片回传，重传直至Python确认','PS可以先释放PL开始下一批，但必须保留上一批结果缓存；缓存满时反压调度。'],
['异常恢复','PL故障','采集首错/原生状态/快照；若NEED_RELOAD则停DMA并重载同算法','现有原John核复位后可能锁死，不能仅清GPIO或DMA复位后声称恢复。'],
['异常恢复','掉电/重启','PS持久化已确认批次与待重试批；启动创建新session_id','旧会话报文不接受；PL计数不是跨重启持久化进度。'],
['UDP上报','身份与能力','node_id、session_id、algorithm_id、ABI、build_id、unit/core数量、payload_format','读取只读能力并附PS软件版本；算法可用列表从镜像清单来，不等于当前加载算法。'],
['UDP上报','运行状态','task_id、shard_id、batch_id、node_state、PL状态、valid/accepted/completed、progress_mode','同次快照数据必须标snapshot_seq与PS时间戳；没有有效值时用null及valid=false。'],
['UDP上报','性能与维测','elapsed_us、候选/秒、输入等待/输出背压、FIFO峰值、错误计数、丢包/重传','速率由PS差分；UDP丢包/重传来自PS软件，不能伪装PL寄存器数据。'],
['UDP上报','物理状态','温度、VCCINT/VCCAUX/VCCBRAM及采样时刻/有效性','推荐PS Linux IIO/XADC统一采集；无传感器时功耗/风扇转速上报不可用。'],
['UDP上报','结果与告警','result_seq、条数、摘要/初筛/已验证命中、first_error/detail/unit、处理记录','UDP协议另设版本、长度、分片号/总片数、ACK、超时、去重；网络封包与AXI包头独立。'],
['UDP上报','MTU与吞吐','按实际路径MTU拆应用分片；MTU1500/IPv4无选项时UDP载荷上限1472B','建议约1200～1400B并扣除应用头；大任务批量DMA，避免每候选一次寄存器/网络往返。'],
['落地顺序','第一步','统一控制IP+身份+ARM/状态/快照+原生状态，接入一个算法验证','验收MMIO对齐、非法访问、计数快照、任务ID与DMA结束条件。'],
['落地顺序','第二步','五算法适配外壳、有限批、bcrypt结果聚合、尾批过滤','验证已知答案、并行完成计数、错误停机与结果完整性；新增资源后重新综合/布局布线。'],
['落地顺序','第三步','PS统一驱动/节点服务+Python SDK+可靠UDP+算法切换','验收丢包/乱序/重复、断线、重配置、无结果超时；不能只做顺畅路径。'],
['落地顺序','第四步','双板分片、重分配、吞吐与稳定性','记录纯PL计算吞吐及端到端吞吐，统计PS/网络等待占比；确认全软件链路完成。'],
];
sheet('PS操作与上报','PS运行流程、网络上报与实施顺序',['阶段','项目','操作/字段','边界与验收'],ops,[20,24,89,83]);

const source=[
['原表','C_VER_0，0x0000，16位，2026','BUILD_DATE 0x0010','将年/月日合并十进制YYYYMMDD，保留原意；地址按4字节重新划分。'],
['原表','C_VER_1，0x0002，16位，1028','BUILD_DATE 0x0010','原值表达10月28日；另新增ABI_VERSION与HW_VERSION，日期不作为兼容版本。'],
['原表','C_VER_2，0x0004，16位，1615','BUILD_TIME 0x0014','改为HHMMSS，示例161500，秒可置0。'],
['原表','C_VER_INF，0x0006，16位','ALGORITHM_ID 0x0020','保留1～5算法编号；改只读32位寄存器，按Bitstream编译常量。'],
['原表','C_AL_UNIT_NUM，0x0008，8位','UNIT_COUNT 0x0024','8/8/8/8/4；扩展到32位便于统一访问。'],
['原表','C_AL_CORE_NUM，0x000A，8位','CORES_PER_UNIT 0x0028及TOTAL_CORE_COUNT 0x002C','明确每单元/总数，防止把算法单元数量误认为底层Core总数。'],
['来源','用户初稿','寄存器划分.xlsx，Sheet1!D6:I13','2026-10-28读取；原文件保持不变。其后为空白预留行。'],
['源码','bcrypt8','john-ax7020-bcrypt8/rtl/top/john_axis_top.v；rtl/adapters/john_pktcomm_to_axis.v；host/john_packet_codec.py','原始协议、status、48B D3及逐包TLAST；main.vh定义72字节口令。'],
['源码','descrypt8','john-ax7020-descrypt8/rtl/descrypt8_axis_top.v；host/codec.py、codec8.py','固定批格式、35位目标初筛和PS完整验证。'],
['源码','md5crypt8','john-ax7020-md5crypt8/rtl/md5crypt8_axis_top.v；host/codec.py；vivado/create_soc.tcl','8单元/24Core、96槽、1000轮；现有DMA/GPIO架构。'],
['源码','sha256crypt8','john-ax7020-sha256crypt8/rtl/sha256crypt8_axis_top.v；host/codec.py','96槽、32字节口令上限、输出3944B。'],
['源码','sha512crypt4','john-ax7020-sha512crypt4/rtl/sha512crypt4_axis_top.v；host/codec.py','64槽、64字节口令上限、输出4664B。'],
['构建证据','五工程system_rebuild.tcl','各项目reports/soc或bcrypt reports/stage4/soc8','当前DMA基址40400000，GPIO基址41200000；create_soc.tcl使用自动assign_bd_address，新版必须显式固定。'],
['官方资料','AMD AXI DMA PG021','https://www.amd.com/content/dam/xilinx/support/documents/ip_documentation/axi_dma/v7_1/pg021_axi_dma.pdf','用于DMA收发长度/TLAST/缓冲区语义；实际实现须匹配Vivado2020.1生成的IP参数。'],
['官方资料','Linux FPGA Manager','https://cdn.kernel.org/doc/html/latest/driver-api/fpga/intro.html','用于管理器/桥接隔离架构参考；具体内核API以PetaLinux2020.1内核为准。'],
['交付边界','此次成果','统一寄存器与协议设计稿','未修改RTL、未生成新Bitstream、未证明新增逻辑资源/时序可满足；下一步按本表实现并验证。'],
['修订记录','v1.1分层地址设计','64 KiB，Common+5算法区+8单元/CU区','保持旧Common及紧凑单元窗口；新增地址发现、算法参数镜像、CU存在性/观测有效性，不新增独立CU控制。'],
];
sheet('原表对照与依据','原表字段映射及设计依据',['分类','原字段/来源','新定义/定位','说明'],source,[16,40,90,85]);

wb.recalculate();
console.log((await wb.inspect({kind:'table',range:'AXI寄存器地址表!A5:I12',include:'values,formulas',tableMaxRows:8,tableMaxCols:9,maxChars:3000})).ndjson);
console.log((await wb.inspect({kind:'match',searchTerm:'#REF!|#DIV/0!|#VALUE!|#NAME\\?|#NUM!|#SPILL!',options:{useRegex:true,maxResults:20},summary:'error scan'})).ndjson);
for(const s of specs){
 const preview=await wb.render({sheetName:s.name,range:`A1:${s.last}${Math.min(s.end,10)}`,scale:1,format:'png'});
 await fs.writeFile(`${dir}/${s.name}.png`,new Uint8Array(await preview.arrayBuffer()));
}
for(const [name,range] of [['五算法适配','A11:F20'],['AXI寄存器地址表','A120:I134']]){
 const preview=await wb.render({sheetName:name,range,scale:1,format:'png'});
 await fs.writeFile(`${dir}/${name}_detail.png`,new Uint8Array(await preview.arrayBuffer()));
}
const outfile=dir+'/AX7020_五算法分层AXI寄存器地址表_v1.1_设计稿.xlsx';
await (await SpreadsheetFile.exportXlsx(wb)).save(outfile);
console.log(JSON.stringify({outfile,registers:reg.length,sheets:specs},null,2));
