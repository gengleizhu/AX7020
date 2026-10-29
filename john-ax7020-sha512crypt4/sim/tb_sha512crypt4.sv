`timescale 1ns/1ps
module tb_sha512crypt4;
 reg clk=0; always #5 clk=~clk;
 reg resetn=0,iv=0,il=0,ready=0;
 reg [31:0] din=0;
 wire ir,ov,ol;
 wire [31:0] dout,status;
 wire [3:0] keep;
 sha512crypt4_axis_top #(.MIN_ROUNDS(1)) dut(clk,resetn,din,4'hf,il,iv,ir,dout,keep,ol,ov,ready,status);
 reg [31:0] input_words[0:1665],expected[0:1023];
 reg [63:0] seen=0;
 integer cycles=0,peak=0,count,k;
 wire [3:0] active;
 wire [15:0] core_start;
 reg [15:0] core_seen=0;
 genvar u,c;
 generate for(u=0;u<4;u=u+1)begin: probes
   assign active[u]=dut.workers[u].lane.jobs!=0 && dut.workers[u].lane.received<16;
   for(c=0;c<4;c=c+1)begin: core_probes
     assign core_start[4*u+c]=dut.workers[u].lane.unit_i.cores[c].genblk1.core.start_eqn;
   end
 end endgenerate
 always @(posedge clk)begin
   cycles=cycles+1;count=0;core_seen=core_seen|core_start;
   if(cycles%250000==0)$display("PROGRESS cycles=%0d status=%h received0=%0d received3=%0d",cycles,status,dut.workers[0].lane.received,dut.workers[3].lane.received);
   for(k=0;k<4;k=k+1)count=count+active[k];
   if(count>peak)peak=count;
   if(cycles>200000)$fatal(1,"TIMEOUT status=%h",status);
   if(status[23:16]!=0 || status[2:1]!=0)$fatal(1,"Fault status=%h",status);
 end
 task send(input [31:0] word,input bit last);
 begin
   @(negedge clk);din=word;il=last;iv=1;
   do @(posedge clk);while(!ir);
 end endtask
 integer i,j,unit_num,field,record_part,job_id,start_cycle;
 reg [31:0] held;
 initial begin
   $readmemh("input.mem",input_words);$readmemh("expected.mem",expected);
   repeat(30)@(negedge clk);resetn=1;start_cycle=cycles;
   for(i=0;i<1666;i=i+1)send(input_words[i],i==1665);
   @(negedge clk);iv=0;il=0;
   for(j=0;j<1166;j=j+1)begin
     wait(ov);@(negedge clk);held=dout;
     repeat(j%3)begin @(posedge clk);if(!ov || dout!==held)$fatal(1,"Backpressure");end
     if(keep!==15 || ol!==(j==1165))$fatal(1,"Framing j=%d",j);
     if(j==0 && dout!==32'h34524853)$fatal(1,"Magic");
     if(j==1 && dout!==32'h12345678)$fatal(1,"Tag");
     if(j>=2)begin
       unit_num=(j-2)/291;field=(j-2)%291;
       if(field==0 && dout!==unit_num)$fatal(1,"Unit ID");
       if(field==1 && dout!==32'h3453484a)$fatal(1,"Unit header");
       if(field==2)$display("UNIT_CYCLES unit=%0d cycles=%0d",unit_num,dout);
       if(field>=3)begin
         record_part=(field-3)%18;
         if(record_part==0)begin
           job_id=dout;
           if(job_id<unit_num*16 || job_id>=unit_num*16+16 || seen[job_id])$fatal(1,"Job ID %d",job_id);
           seen[job_id]=1;
         end else if(record_part==1)begin if(dout!==0)$fatal(1,"ID high");end
         else if(dout!==expected[16*job_id+record_part-2])
           $fatal(1,"Digest mismatch job=%0d word=%0d got=%h expected=%h",job_id,record_part-2,dout,expected[16*job_id+record_part-2]);
       end
     end
     @(negedge clk);ready=1;@(posedge clk);@(negedge clk);ready=0;
   end
   if(seen!=={64{1'b1}})$fatal(1,"Missing outputs");
   if(peak!=4 || core_seen!==16'hffff)$fatal(1,"Parallel activity peak=%d cores=%h",peak,core_seen);
   $display("SHA512CRYPT4_TEST_PASS units=4 physical_sha512cores_active=16 peak_active_units=4 jobs=64 rounds=10 cycles=%0d",cycles-start_cycle);
   $finish;
 end
endmodule
