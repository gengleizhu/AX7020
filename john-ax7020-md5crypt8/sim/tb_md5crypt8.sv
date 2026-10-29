`timescale 1ns/1ps
module tb_md5crypt8;
 reg clk=0;always #5 clk=~clk;
 reg resetn=0,iv=0,il=0,ready=0;
 reg [31:0] din=0;
 wire ir,ov,ol;
 wire [31:0] dout,status;
 wire [3:0] keep;
 md5crypt8_axis_top dut(clk,resetn,din,4'hf,il,iv,ir,dout,keep,ol,ov,ready,status);
 reg [31:0] input_words[0:2497],expected[0:383];
 reg [95:0] seen=0;
 integer cycles=0,peak=0,count,k;
 wire [7:0] active;
 wire [23:0] core_start;
 reg [23:0] core_seen=0;
 genvar u,c;
 generate for(u=0;u<8;u=u+1)begin: probes
   assign active[u]=dut.workers[u].lane.jobs!=0 && dut.workers[u].lane.received<12;
   for(c=0;c<3;c=c+1)begin: core_probes
     assign core_start[3*u+c]=dut.workers[u].lane.unit_i.cores[c].genblk1.core.start_eqn;
   end
 end endgenerate
 always @(posedge clk)begin
   cycles=cycles+1;count=0;core_seen=core_seen|core_start;
   if(cycles%100000==0)$display("PROGRESS cycles=%0d status=%h received0=%0d received7=%0d",cycles,status,dut.workers[0].lane.received,dut.workers[7].lane.received);
   for(k=0;k<8;k=k+1)count=count+active[k];
   if(count>peak)peak=count;
   if(cycles>4000000)$fatal(1,"TIMEOUT status=%h",status);
   if(status[23:16]!=0 || status[2:1]!=0)$fatal(1,"Fault status=%h",status);
 end
 task send(input [31:0] word,input bit last);
 begin
   @(negedge clk);din=word;il=last;iv=1;
   do @(posedge clk);while(!ir);
 end endtask
 integer wave,i,j,unit_num,field,record_part,job_id,start_cycle;
 reg [31:0] held;
 initial begin
   $readmemh("input.mem",input_words);$readmemh("expected.mem",expected);
   repeat(30)@(negedge clk);resetn=1;
   for(wave=0;wave<2;wave=wave+1)begin
     seen=0;start_cycle=cycles;
     for(i=0;i<2498;i=i+1)send(i==1?input_words[i]+wave:input_words[i],i==2497);
     @(negedge clk);iv=0;il=0;
     for(j=0;j<602;j=j+1)begin
       wait(ov);@(negedge clk);held=dout;
       repeat(j%3)begin @(posedge clk);if(!ov || dout!==held)$fatal(1,"Backpressure");end
       if(keep!==15 || ol!==(j==601))$fatal(1,"Framing j=%d",j);
       if(j==0 && dout!==32'h38524d44)$fatal(1,"Magic");
       if(j==1 && dout!==(32'h12345678+wave))$fatal(1,"Tag");
       if(j>=2)begin
         unit_num=(j-2)/75;field=(j-2)%75;
         if(field==0 && dout!==unit_num)$fatal(1,"Unit ID");
         if(field==1 && dout!==32'h38524d4a)$fatal(1,"Unit header");
         if(field==2)$display("UNIT_CYCLES wave=%0d unit=%0d cycles=%0d",wave,unit_num,dout);
         if(field>=3)begin
           record_part=(field-3)%6;
           if(record_part==0)begin
             job_id=dout;
             if(job_id<unit_num*12 || job_id>=unit_num*12+12 || seen[job_id])$fatal(1,"Job ID %d",job_id);
             seen[job_id]=1;
           end else if(record_part==1)begin if(dout!==0)$fatal(1,"ID high");end
           else if(dout!==expected[4*job_id+record_part-2])
             $fatal(1,"Digest mismatch job=%0d word=%0d got=%h expected=%h",job_id,record_part-2,dout,expected[4*job_id+record_part-2]);
         end
       end
       @(negedge clk);ready=1;@(posedge clk);@(negedge clk);ready=0;
     end
     if(seen!=={96{1'b1}})$fatal(1,"Missing outputs");
     $display("SUPERBATCH_CYCLES wave=%0d cycles=%0d",wave,cycles-start_cycle);
   end
   if(peak!=8 || core_seen!==24'hffffff)$fatal(1,"Parallel activity peak=%d cores=%h",peak,core_seen);
   $display("MD5CRYPT8_TEST_PASS units=8 physical_md5cores_active=24 peak_active_units=8 jobs=192 rounds=1000");
   $finish;
 end
endmodule
