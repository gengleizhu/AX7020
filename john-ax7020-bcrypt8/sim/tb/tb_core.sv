`timescale 1ns/1ps
`include "config.vh"
// 直接驱动原始Core；不使用软件模型替换任何计算模块。
module tb_core;
  reg clk=0;
  always #5 clk=~clk;
  reg [7:0] din=0;
  reg [3:0] byte_wr_en=0;
  reg start=0, rd_en=0;
  wire init_ready, crypt_ready, empty, dout;
  bcrypt_core dut(.CLK(clk),.mode_cmp(1'b0),.din(din),.byte_wr_en(byte_wr_en),
    .start(start),.rd_en(rd_en),.init_ready(init_ready),.crypt_ready(crypt_ready),
    .empty(empty),.dout(dout));
  reg [31:0] init_data[0:1053], data[0:30], expected[0:7], got[0:7];
  integer v,w,b,k,n,cycles=0,begin_cycle,loop_count=0,frame_bits=0,fd;
  integer observed_loops;
  reg counting=0;
  always @(posedge clk) begin
    cycles <= cycles+1;
    if(counting && dut.fsm.IP==25) loop_count <= loop_count+1;
  end
  initial begin
    #300000000;
    $fatal(1,"CORE_TIMEOUT IP=%d",dut.fsm.IP);
  end
  task send_word(input [31:0] word_value,input first);
    integer j;
    begin
      for(j=0;j<4;j=j+1) begin
        @(negedge clk);
        byte_wr_en=4'b0001<<j; din=word_value[j*8+:8];
        start=first && j==0;
      end
    end
  endtask
  task end_input;
    begin @(negedge clk); byte_wr_en=0; start=0; din=0; end
  endtask
  initial begin
    fd=$fopen("core_results.txt","w");
    $readmemh("sim/vectors/init.mem",init_data);
    repeat(20) @(negedge clk);
    for(v=0;v<`VECTOR_COUNT;v=v+1) begin
      $readmemh($sformatf("sim/vectors/data_%0d.mem",v),data);
      $readmemh($sformatf("sim/vectors/result_%0d.mem",v),expected);
      wait(init_ready===1);
      for(w=0;w<1054;w=w+1) send_word(init_data[w],w==0);
      end_input();
      wait(crypt_ready===1);
      repeat(8) @(negedge clk);
      for(w=0;w<30;w=w+1)
        if(dut.unit.P.PN[w] !== init_data[w]) $fatal(1,"PN init mismatch %d",w);
      for(w=0;w<256;w=w+1) begin
        if(dut.unit.S.S0[w] !== init_data[30+w]) $fatal(1,"S0 init mismatch");
        if(dut.unit.S.S1[w] !== init_data[286+w]) $fatal(1,"S1 init mismatch");
        if(dut.unit.S.S2[w] !== init_data[542+w]) $fatal(1,"S2 init mismatch");
        if(dut.unit.S.S3[w] !== init_data[798+w]) $fatal(1,"S3 init mismatch");
      end
      begin_cycle=cycles; loop_count=0; counting=1;
      for(w=0;w<31;w=w+1) send_word(data[w],w==0);
      end_input();
      repeat(8) @(negedge clk);
      for(w=0;w<31;w=w+1)
        if(dut.unit.P.PD[w] !== data[w]) $fatal(1,"PD mismatch %d got=%h expected=%h",w,dut.unit.P.PD[w],data[w]);
      if(crypt_ready!==0) $fatal(1,"Core did not enter BUSY");
      wait(empty===0);
      observed_loops=loop_count; counting=0;
      if(observed_loops!=data[19]) $fatal(1,"Cost loop mismatch %d expected %d",observed_loops,data[19]);
      // 延迟读取：结果必须保留；rd_en只启动一次，不能逐bit反压。
      repeat(31) begin @(negedge clk); if(empty!==0) $fatal(1,"result lost"); end
      rd_en=1; @(negedge clk); rd_en=0;
      n=0;
      while(dout!==1 && n<32) begin @(negedge clk); n=n+1; end
      if(dout!==1) $fatal(1,"missing serial header");
      frame_bits=1;
      for(w=0;w<8;w=w+1) begin
        got[w]=0;
        for(b=0;b<32;b=b+1) begin
          @(negedge clk);
          if(dout!==0 && dout!==1) $fatal(1,"unknown serial bit");
          got[w][b]=dout; frame_bits=frame_bits+1;
        end
        if(got[w] !== expected[w]) $fatal(1,"v=%d word=%d got=%h expected=%h",v,w,got[w],expected[w]);
      end
      @(negedge clk);
      if(frame_bits!=257 || dout!==0) $fatal(1,"serial frame length");
      wait(init_ready===1);
      $display("CORE_VECTOR_PASS vector=%0d cycles=%0d loops=%0d bits=%0d",v,cycles-begin_cycle,observed_loops,frame_bits);
      $fdisplay(fd,"%0d %0d %0d %0d",v,cycles-begin_cycle,observed_loops,frame_bits);
      repeat(20) @(negedge clk);
    end
    $fclose(fd);
    $display("STAGE1_PASS tb_core"); $finish;
  end
endmodule
