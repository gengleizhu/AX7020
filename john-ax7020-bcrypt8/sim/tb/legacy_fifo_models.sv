`timescale 1ns/1ps
// 仅用于阶段1同钟仿真，替代缺失的ISE FIFO IP。
// 不可用于综合/CDC验证；所有算法、Packet模块仍为John原文件。
module input_fifo(input wr_clk,input [15:0] din,input wr_en,
  output full,almost_full,prog_full,input rd_clk,input rd_en,
  output [7:0] dout,output almost_empty,empty);
  reg [7:0] mem[0:8191];
  integer wp=0,rp=0;
  assign full=wp-rp>=8190;
  assign almost_full=wp-rp>=8188;
  assign prog_full=wp-rp>=2048;
  assign empty=wp==rp;
  assign almost_empty=wp-rp<=1;
  assign dout=mem[rp%8192];
  always @(posedge wr_clk) begin
    if(wr_en) begin
      if(full) $fatal(1,"input FIFO overflow");
      mem[wp%8192]<=din[15:8];
      mem[(wp+1)%8192]<=din[7:0];
      wp<=wp+2;
    end
  end
  always @(posedge rd_clk) if(rd_en) begin
    if(empty) $fatal(1,"input FIFO underflow");
    rp<=rp+1;
  end
endmodule

module output_fifo(input wr_clk,input [15:0] din,input wr_en,
  output full,idle,input rd_clk,output [15:0] dout,input rd_en,output empty,
  input mode_limit,reg_output_limit,output [15:0] output_limit,output output_limit_not_done);
  // 小FIFO用于强制产生反压，验证原Packet输出在暂停后保持正确。
  reg [15:0] mem[0:15];
  integer wp=0,rp=0;
  assign full=wp-rp>=16;
  assign empty=wp==rp;
  assign idle=empty;
  assign dout=mem[rp%16];
  assign output_limit=0;
  assign output_limit_not_done=0;
  always @(posedge wr_clk) if(wr_en) begin
    if(full) $fatal(1,"output FIFO overflow");
    mem[wp%16]<=din; wp<=wp+1;
  end
  always @(posedge rd_clk) if(rd_en && !empty) rp<=rp+1;
endmodule
