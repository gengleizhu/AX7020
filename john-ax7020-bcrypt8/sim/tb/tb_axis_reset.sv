`timescale 1ns/1ps
module tb_axis_reset;
 reg clk=0,rst=0,valid=0;
 always #5 clk=~clk;
 wire ready,mvalid;
 wire [31:0] status;
 john_axis_top #(.CORES(8)) dut(
  .aclk(clk),.aresetn(rst),.s_axis_tdata(32'h00000302),.s_axis_tkeep(4'hf),
  .s_axis_tlast(1'b1),.s_axis_tvalid(valid),.s_axis_tready(ready),
  .m_axis_tdata(),.m_axis_tkeep(),.m_axis_tlast(),.m_axis_tvalid(mvalid),
  .m_axis_tready(1'b1),.status(status));
 initial begin
  repeat(10) @(negedge clk);
  rst=1;
  repeat(10) @(negedge clk);
  if(!ready || status[23:0]!==0) $fatal(1,"startup reset failed");
  valid=1;
  @(posedge clk); while(!ready) @(posedge clk);
  @(negedge clk); valid=0;
  repeat(3) @(negedge clk);
  rst=0;
  repeat(3) @(negedge clk);
  rst=1; valid=1;
  repeat(30) @(negedge clk);
  if(status[19]!==1 || ready!==0 || mvalid!==0) $fatal(1,"mid-session reset did not fail closed");
  $display("RESET_GUARD_PASS");
  $finish;
 end
 initial begin #100000; $fatal(1,"reset test timeout"); end
endmodule
