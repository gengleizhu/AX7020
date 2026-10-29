`timescale 1ns/1ps
`include "config.vh"
module tb_expand;
  reg clk=0;
  always #5 clk=~clk;
  reg [7:0] key[0:72];
  reg [31:0] expected[0:17];
  wire [6:0] addr;
  wire [31:0] dout;
  wire set_empty,empty;
  reg word_empty=1,rd_en=0,bug=0;
  integer v,i,cycles=0;
  bcrypt_expand_key_b dut(.CLK(clk),.din(key[addr]),.rd_addr(addr),
    .word_set_empty(set_empty),.word_empty(word_empty),.sign_extension_bug(bug),
    .dout(dout),.rd_en(rd_en),.empty(empty));
  initial begin #1000000; $fatal(1,"EXPAND_TIMEOUT"); end
  initial begin
    repeat(10) @(negedge clk);
    for(v=0;v<`VECTOR_COUNT;v=v+1) begin
      $readmemh($sformatf("sim/vectors/key_%0d.mem",v),key);
      $readmemh($sformatf("sim/vectors/ek_%0d.mem",v),expected);
      for(i=0;i<18;i=i+1)
        if(^expected[i]===1'bx) $fatal(1,"missing/unknown EK reference");
      bug=(v==4); word_empty=0;
      for(i=0;i<18;i=i+1) begin
        wait(empty===0); @(negedge clk);
        repeat(i%4+1) begin
          if(^dout===1'bx || dout !== expected[i]) $fatal(1,"EK mismatch v=%d word=%d got=%h exp=%h",v,i,dout,expected[i]);
          @(negedge clk);
        end
        rd_en=1; @(negedge clk); rd_en=0;
      end
      wait(set_empty===1); word_empty=1;
      repeat(5) @(negedge clk);
      $display("EXPAND_VECTOR_PASS %0d",v);
    end
    $display("STAGE1_PASS tb_expand"); $finish;
  end
endmodule
