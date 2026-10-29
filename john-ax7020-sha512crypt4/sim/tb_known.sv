`timescale 1ns/1ps
module tb_known;
 reg clk=0; always #5 clk=~clk;
 reg resetn=0,valid=0,last=0,ready=0; reg [31:0] din=0;
 wire ir,ov,ol; wire [31:0] dout,status;
 sha512crypt_lane dut(.aclk(clk),.aresetn(resetn),.s_axis_tdata(din),.s_axis_tkeep(4'hf),
 .s_axis_tlast(last),.s_axis_tvalid(valid),.s_axis_tready(ir),.m_axis_tdata(dout),
 .m_axis_tkeep(),.m_axis_tlast(ol),.m_axis_tvalid(ov),.m_axis_tready(ready),.status(status));
 reg [31:0] input_words[0:415],expected[0:255]; reg [15:0] seen=0;
 integer i,n,part,job_id,cycles=0;
 always @(posedge clk)begin
   cycles=cycles+1;
   if(cycles%100000==0)begin
     $display("KNOWN_PROGRESS cycles=%0d received=%0d",cycles,dut.received);
     $fflush();
   end
   if(cycles>3000000 || status[8:1]!=0)$fatal(1,"Known failure status=%h",status);
 end
 initial begin
   $readmemh("known_input.mem",input_words);$readmemh("known_expected.mem",expected);
   repeat(30)@(negedge clk);resetn=1;
   for(i=0;i<416;i=i+1)begin
     @(negedge clk);din=input_words[i];last=(i==415);valid=1;
     do @(posedge clk);while(!ir);
   end
   @(negedge clk);valid=0;last=0;
   for(n=0;n<290;n=n+1)begin
     wait(ov);@(negedge clk);
     if(ol!==(n==289))$fatal(1,"Known framing");
     if(n==0 && dout!==32'h3453484a)$fatal(1,"Known magic");
     if(n==1)$display("KNOWN_UNIT_CYCLES %0d",dout);
     if(n>=2)begin
       part=(n-2)%18;
       if(part==0)begin job_id=dout;if(job_id>15||seen[job_id])$fatal(1,"Known id");seen[job_id]=1;end
       else if(part==1)begin if(dout!==0)$fatal(1,"ID high");end
       else if(dout!==expected[16*job_id+part-2])$fatal(1,"Known digest job=%0d word=%0d",job_id,part-2);
     end
     ready=1;@(posedge clk);@(negedge clk);ready=0;
   end
   if(seen!==16'hffff)$fatal(1,"Missing IDs");
   $display("KNOWN_TEST_PASS jobs=16 rounds=1000 cycles=%0d",cycles);$finish;
 end
endmodule
