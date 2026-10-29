// 原MSB宏中的注释续行不能由Vivado 2018.3正确处理；数值语义保持不变。
`ifndef _LOG2_VH_
`define _LOG2_VH_
`define MSB(x) (((x) < 2) ? 0 : $clog2((x)+1)-1)
`endif
`include "main.vh"
