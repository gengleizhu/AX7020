`timescale 1ns/1ps
module tb_descrypt8;
 reg clk=0;always #5 clk=~clk;
 reg resetn=0,iv=0,il=0,ready=0;
 reg [31:0] din=0;
 wire ir,ov,ol;
 wire [31:0] dout,status;
 wire [3:0] keep;
 descrypt8_axis_top dut(clk,resetn,din,4'hf,il,iv,ir,dout,keep,ol,ov,ready,status);
 reg [31:0] vectors[0:295];
 wire [7:0] calculating;
 integer cycles=0,peak=0,k,count;
 integer launched[0:7];
 genvar g;
 generate for(g=0;g<8;g=g+1)begin: monitor
   assign calculating[g]=(dut.workers[g].lane.state==4 || dut.workers[g].lane.state==5 || dut.workers[g].lane.state==6);
   always @(posedge clk)if(dut.workers[g].lane.state==4 && dut.workers[g].lane.key_idx==0)launched[g]=launched[g]+1;
 end endgenerate
 always @(posedge clk)begin
   cycles=cycles+1;count=0;
   for(k=0;k<8;k=k+1)count=count+calculating[k];
   if(count>peak)peak=count;
   if(cycles>20000)$fatal(1,"TIMEOUT status=%h",status);
 end
 task send(input [31:0] word,input bit last);
 begin
   @(negedge clk);din=word;il=last;iv=1;
   do @(posedge clk);while(!ir);
 end endtask
 integer wave,i,j,c,record,field,start_cycle;
 reg [31:0] held;
 reg held_last;
 initial begin
   for(i=0;i<8;i=i+1)launched[i]=0;
   $readmemh("vectors.mem",vectors);
   repeat(5)@(negedge clk);resetn=1;
   for(wave=0;wave<3;wave=wave+1)begin
     start_cycle=cycles;
     send(32'h38534344,0);send(32'h100+wave,0);
     for(i=0;i<8;i=i+1)begin
       c=(i+wave)%8;
       for(j=0;j<36;j=j+1)send(vectors[37*c+j],i==7 && j==35);
     end
     @(negedge clk);iv=0;il=0;
     for(j=0;j<42;j=j+1)begin
       wait(ov);@(negedge clk);held=dout;held_last=ol;
       repeat((j%5)+1)begin
         @(posedge clk);
         if(!ov || dout!==held || ol!==held_last)$fatal(1,"Unstable output");
       end
       if(keep!==15 || ol!==(j==41))$fatal(1,"Framing");
       if(j==0 && dout!==32'h38524344)$fatal(1,"Magic");
       if(j==1 && dout!==(32'h100+wave))$fatal(1,"Transaction ID");
       if(j>=2)begin
         record=(j-2)/5;field=(j-2)%5;c=(record+wave)%8;
         case(field)
         0:if(dout!==record)$fatal(1,"Core ID");
         1:if(dout!==32'h31524344)$fatal(1,"Worker magic");
         2:if(dout!==vectors[37*c+36])$fatal(1,"Match wave=%d core=%d got=%h expected=%h",wave,record,dout,vectors[37*c+36]);
         3:if(dout<400 || dout>2000)$fatal(1,"Cycles");
         4:if(dout[8:1]!==0)$fatal(1,"Worker error");
         endcase
       end
       @(negedge clk);ready=1;@(posedge clk);@(negedge clk);ready=0;
     end
     $display("SUPERBATCH wave=%0d cycles_with_test_backpressure=%0d",wave,cycles-start_cycle);
     if(status[23:16]!=0 || status[2:0]!=0)$fatal(1,"Aggregate status=%h",status);
   end
   if(peak!=8)$fatal(1,"Only %d cores simultaneously calculating",peak);
   for(i=0;i<8;i=i+1)if(launched[i]!=3)$fatal(1,"Core %d launches=%d",i,launched[i]);
   send(32'hdeadbeef,0);@(negedge clk);iv=0;repeat(3)@(negedge clk);
   if(!status[2] || ir || ov)$fatal(1,"Bad header accepted");
   resetn=0;repeat(3)@(negedge clk);resetn=1;repeat(3)@(negedge clk);
   if(!status[1] || ir)$fatal(1,"Reset guard");
   $display("DESCRYPT8_TEST_PASS cores=8 peak_calculating=8 batches_per_core=3 candidates=384 salts=8");
   $finish;
 end
endmodule
