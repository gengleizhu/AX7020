`timescale 1ns/1ps
module tb_axis_multicore;
 parameter CORES=1;
 parameter INPUT_BYTES=400;
 reg clk=0,resetn=0;
 always #5 clk=~clk;
 reg [31:0] sdata=0;
 reg [3:0] skeep=0;
 reg slast=0,svalid=0,mready=0;
 wire sready,mvalid,mlast;
 wire [31:0] mdata,status;
 wire [3:0] mkeep;
 john_axis_top #(.CORES(CORES)) dut(clk,resetn,sdata,skeep,slast,svalid,sready,
   mdata,mkeep,mlast,mvalid,mready,status);
 reg [7:0] input_bytes[0:INPUT_BYTES-1];
 integer cycle=0,fd,metrics,received=0,bytes_out=0,peak=0,busy_count=0;
 integer first_input=-1,last_output=0;
 reg [CORES-1:0] busy=0,used=0;
 genvar g;
 generate for(g=0;g<CORES;g=g+1) begin: monitor
   wire ready=dut.wrapper.proxies[0].proxy.cores[g].init_ready_in === 1'b0 &&
              dut.wrapper.proxies[0].proxy.cores[g].crypt_ready_in === 1'b1;
   wire empty=dut.wrapper.proxies[0].proxy.cores[g].empty_in;
   reg old_ready=0;
   integer start_cycle=0,completed=0;
   always @(posedge clk) begin
     old_ready<=ready;
     if(old_ready && !ready) begin
       busy[g]<=1; used[g]<=1; start_cycle=cycle;
     end
     if(busy[g] && !empty) begin
       busy[g]<=0; completed=completed+1;
       $fdisplay(metrics,"CORE core=%0d cycles=%0d completed=%0d",g,cycle-start_cycle,completed);
     end
   end
 end endgenerate
 reg stalled=0;
 reg [37:0] held;
 integer k;
 always @(posedge clk) begin
   cycle<=cycle+1;
   busy_count=0;
   for(k=0;k<CORES;k=k+1) busy_count=busy_count+busy[k];
   if(busy_count>peak) peak=busy_count;
   if(resetn && status[23:0]!==0) $fatal(1,"STATUS %h",status);
   if(stalled && {mvalid,mlast,mkeep,mdata} !== held) $fatal(1,"AXIS changed while stalled");
   stalled<=mvalid && !mready;
   held<={mvalid,mlast,mkeep,mdata};
   if(svalid && sready && first_input<0) first_input=cycle;
   if(mvalid && mready) begin
     if(mkeep!==15 || ^mdata===1'bx) $fatal(1,"invalid output beat");
     $fdisplay(fd,"%02x\n%02x\n%02x\n%02x",mdata[7:0],mdata[15:8],mdata[23:16],mdata[31:24]);
     bytes_out=bytes_out+4;
     if(mlast) begin
       if(bytes_out!=48) $fatal(1,"TLAST boundary %d",bytes_out);
       received=received+1; bytes_out=0; last_output=cycle;
     end
   end
 end
 // 第一个结果到达后暂停2048周期，确定覆盖实际输出FIFO满/背压。
 integer stall_left=0;
 reg injected=0,full_seen=0;
 always @(posedge clk) if(dut.engine.full) full_seen<=1;
 always @(negedge clk) begin
   if(mvalid && !injected) begin injected=1; stall_left=2048; end
   if(stall_left>0) begin mready=0; stall_left=stall_left-1; end
   else mready=(cycle%17)>5;
 end
 integer pos=0,j,n,segment_left=0;
 initial begin
   fd=$fopen("axis_output.hex","w");
   metrics=$fopen("metrics.txt","w");
   $readmemh("input.mem",input_bytes);
   repeat(20) @(negedge clk);
   resetn=1;
   // 模拟13字节DMA事务，使TLAST穿过John头/载荷边界，并覆盖1/2/3字节尾拍。
   while(pos<INPUT_BYTES) begin
     segment_left=((pos/13)%3==0)?13:(((pos/13)%3==1)?14:15);
     if(segment_left>INPUT_BYTES-pos) segment_left=INPUT_BYTES-pos;
     while(segment_left>0) begin
       @(negedge clk);
       sdata=0; skeep=0;
       n=segment_left<4?segment_left:4;
       for(j=0;j<n;j=j+1) begin sdata[j*8+:8]=input_bytes[pos+j]; skeep[j]=1; end
       slast=segment_left==n; svalid=1;
       @(posedge clk); while(!sready) @(posedge clk);
       @(negedge clk); svalid=0;
       pos=pos+n; segment_left=segment_left-n;
       repeat(pos%3) @(negedge clk);
     end
   end
   wait(received==32);
   repeat(3000) @(negedge clk);
   if(received!=32 || peak!=CORES || used!={CORES{1'b1}}) $fatal(1,"parallel coverage peak=%d used=%h",peak,used);
   // 单核在暂停窗口内只有一个48字节包，未必填满16深FIFO；多核必须覆盖满。
   if(CORES>1 && !full_seen) $fatal(1,"missing FIFO backpressure");
   $fdisplay(metrics,"SUMMARY cores=%0d results=%0d peak_busy=%0d batch_cycles=%0d full_seen=%0d",
     CORES,received,peak,last_output-first_input+1,full_seen);
   $fclose(fd); $fclose(metrics);
   $display("INTEGRATION_PASS cores=%0d results=%0d peak_busy=%0d",CORES,received,peak);
   $finish;
 end
 initial begin #500000000; $fatal(1,"TIMEOUT results=%d",received); end
endmodule
