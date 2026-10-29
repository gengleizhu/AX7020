// 原John输出FIFO接口的可综合同钟实现。wr_clk和rd_clk必须连接同一时钟。
// 不支持原USB output_limit模式；集成顶层固定禁用该模式。
module output_fifo(input wr_clk,input [15:0] din,input wr_en,
 output full,idle,input rd_clk,output [15:0] dout,input rd_en,output empty,
 input mode_limit,reg_output_limit,output [15:0] output_limit,output output_limit_not_done);
 reg [15:0] mem[0:15];
 reg [4:0] wp=0,rp=0;
 assign full=(wp-rp)==16;
 assign empty=wp==rp;
 assign idle=empty;
 assign dout=mem[rp[3:0]];
 assign output_limit=0;
 assign output_limit_not_done=0;
 always @(posedge wr_clk) begin
   if(wr_en && !full) begin mem[wp[3:0]]<=din; wp<=wp+1'b1; end
   if(rd_en && !empty) rp<=rp+1'b1;
 end
endmodule
