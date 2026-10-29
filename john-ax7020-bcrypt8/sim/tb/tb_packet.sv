`timescale 1ns/1ps
`include "config.vh"
module tb_packet;
  reg clk=0;
  always #5 clk=~clk;
  reg [15:0] din=0;
  reg wr_en=0,rd_en=0;
  wire almost_full,empty,idle,error_r;
  wire [15:0] dout;
  wire [7:0] app_status,pkt_status,core_din;
  wire [1:0] ctrl;
  wire cw,ci,cc,cr,ce,cd;
  bcrypt #(.NUM_CORES(1),.SIMULATION(0)) dut(
    .CORE_CLK(clk),.IFCLK(clk),.hs_input_din(din),.hs_input_wr_en(wr_en),
    .hs_input_almost_full(almost_full),.hs_input_prog_full(),
    .output_dout(dout),.output_rd_en(rd_en),.output_empty(empty),
    .output_limit(),.output_limit_not_done(),.output_mode_limit(1'b0),.reg_output_limit(1'b0),
    .idle(idle),.error_r(error_r),.app_mode(8'h40),
    .app_status(app_status),.pkt_comm_status(pkt_status),.debug2(),.debug3(),
    .mode_cmp(1'b0),.core_din(core_din),.core_ctrl(ctrl),.core_wr_en(cw),
    .core_init_ready(ci),.core_crypt_ready(cc),.core_rd_en(cr),.core_empty(ce),.core_dout(cd));
  bcrypt_wrapper #(.NUM_PROXIES(1),.PROXY_CONF(32'h00000101)) wrapper(
    .CLK(clk),.mode_cmp(1'b0),.din(core_din),.ctrl(ctrl),.wr_en(cw),
    .init_ready(ci),.crypt_ready(cc),.rd_en(cr),.empty(ce),.dout(cd));
  reg [7:0] stimulus[0:`INPUT_BYTES-1];
  reg [31:0] job_ends[0:`JOB_COUNT-1],job_counts[0:`JOB_COUNT-1];
  integer pos=0,v,i,fd,cycles=0,out_words=0;
  reg held_full=0;
  always @(posedge clk) begin
    cycles<=cycles+1;
    if(cycles>30 && (app_status!==0 || pkt_status!==0 || error_r!==0))
      $fatal(1,"PACKET_STATUS app=%h packet=%h",app_status,pkt_status);
    if(dut.full) held_full<=1;
    if(rd_en && !empty) begin
      if(^dout===1'bx) $fatal(1,"unknown packet output");
      $fdisplay(fd,"%02x\n%02x",dout[7:0],dout[15:8]);
      out_words<=out_words+1;
    end
  end
  // 周期性暂停读出，覆盖FIFO积压/反压。
  always @(negedge clk) rd_en=(cycles%1024)>700;
  initial begin #300000000; $fatal(1,"PACKET_TIMEOUT count=%d",out_words); end
  initial begin
    fd=$fopen("packet_output.hex","w");
    $readmemh("sim/vectors/packets.mem",stimulus);
    $readmemh("sim/vectors/job_ends.mem",job_ends);
    $readmemh("sim/vectors/job_counts.mem",job_counts);
    repeat(20) @(negedge clk);
    // 每个批次等结果完整返回，再允许更换salt；同批次可在Busy期间缓存。
    for(v=0;v<`JOB_COUNT;v=v+1) begin
      for(i=0;i<3;i=i+1) begin: send_packet
        integer length,j;
        length=stimulus[pos+4]+256*stimulus[pos+5]+18;
        // 原始流允许奇数长度；跨包16bit拼接由整个流的发送任务处理。
        for(j=0;j<length;j=j+1) begin
          if(pos%2==0) begin
            @(negedge clk);
            while(almost_full) @(negedge clk);
            din={stimulus[pos],stimulus[pos+1]}; wr_en=1;
            @(negedge clk); wr_en=0;
          end
          pos=pos+1;
        end
      end
      if(pos!=job_ends[v]) $fatal(1,"input packet boundary mismatch");
      wait(out_words>=job_counts[v]*24);
      repeat(100) @(negedge clk);
      $display("PACKET_VECTOR_PASS %0d",v);
    end
    repeat(2000) @(negedge clk);
    if(out_words!=`RESULT_COUNT*24) $fatal(1,"unexpected output count");
    if(!held_full) $fatal(1,"backpressure not exercised");
    $fclose(fd); $display("STAGE1_PASS tb_packet"); $finish;
  end
endmodule
