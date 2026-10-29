// 单时钟32位AXIS -> 原John字节流，lane0最先发送；跨TLAST不插入填充字节。
module axis_to_john_pktcomm(
 input clk, input resetn,
 input [31:0] s_axis_tdata,input [3:0] s_axis_tkeep,
 input s_axis_tlast,input s_axis_tvalid,output s_axis_tready,
 output [7:0] data,output valid,input ready,output reg error=0);
 reg [31:0] buffer=0;
 reg [2:0] count=0;
 assign s_axis_tready=resetn && count==0 && !error;
 assign data=buffer[7:0];
 assign valid=resetn && count!=0 && !error;
 always @(posedge clk) begin
   if(!resetn) begin count<=0; error<=0; end
   else begin
     if(s_axis_tvalid && s_axis_tready) begin
       buffer<=s_axis_tdata;
       case(s_axis_tkeep)
         4'b0001: count<=1;
         4'b0011: count<=2;
         4'b0111: count<=3;
         4'b1111: count<=4;
         default: error<=1;
       endcase
       // 非最后一拍不允许部分字；DMA每次发送可包含任意数量原John包。
       if(!s_axis_tlast && s_axis_tkeep!=4'b1111) error<=1;
     end
     if(valid && ready) begin buffer<=buffer>>8; count<=count-1'b1; end
   end
 end
endmodule
