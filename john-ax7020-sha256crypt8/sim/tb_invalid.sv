`timescale 1ns/1ps
module tb_invalid;
 reg clk=0; always #5 clk=~clk;
 reg resetn=0,valid=0; integer pos=0;
 wire [31:0] status[0:7]; wire [7:0] ready,ov;
 genvar i;
 generate for(i=0;i<8;i=i+1)begin: cases
   wire [31:0] data = pos==0?(i==0?999:i==1?1000000000:1000):
     pos==1?(i==2?0:i==3?17:1):pos==8?(i==6?33:0):pos==9?(i==7?1:0):0;
   sha256crypt_lane lane(.aclk(clk),.aresetn(resetn),.s_axis_tdata(data),
     .s_axis_tkeep(i==4?4'h7:4'hf),.s_axis_tlast(i==5),
     .s_axis_tvalid(valid),.s_axis_tready(ready[i]),.m_axis_tdata(),
     .m_axis_tkeep(),.m_axis_tlast(),.m_axis_tvalid(ov[i]),.m_axis_tready(1'b1),.status(status[i]));
 end endgenerate
 integer k;
 initial begin
   repeat(20)@(negedge clk);resetn=1;valid=1;
   for(pos=0;pos<10;pos=pos+1)@(negedge clk);
   valid=0;repeat(5)@(negedge clk);
   for(k=0;k<8;k=k+1)if(!status[k][2] || ready[k] || ov[k])$fatal(1,"Invalid accepted case=%d",k);
   $display("INVALID_TEST_PASS cases=8");$finish;
 end
endmodule
