`timescale 1ns/1ps
module tb_descrypt;
 reg clk=0; always #5 clk=~clk;
 reg resetn=0,valid=0,last=0,ready=0;
 reg [3:0] keep=15;
 reg [31:0] din=0;
 wire inready,outvalid,outlast;
 wire [31:0] dout,status;
 wire [3:0] outkeep;
 descrypt_axis_top dut(clk,resetn,din,keep,last,valid,inready,dout,outkeep,outlast,outvalid,ready,status);
 integer cycles=0;
 reg [31:0] vectors[0:295];
 integer v,n,r;
 wire [5:0] reject_done;
 genvar e;
 generate for(e=0;e<6;e=e+1)begin: negative_cases
   reject_case #(.CASE_ID(e)) check(clk,reject_done[e]);
 end endgenerate
 always @(posedge clk) begin cycles<=cycles+1;if(cycles>20000)$fatal(1,"TIMEOUT");end
 task send(input [31:0] value,input bit final_word);
 begin
   @(negedge clk);din=value;last=final_word;valid=1;
   do @(posedge clk);while(!inready);
   @(negedge clk);valid=0;last=0;
 end endtask
 task batch(input [34:0] target,input [15:0] expected,input integer pattern);
 integer i,j; reg [63:0] word_ascii; reg [31:0] held;
 begin
   send(32'h31534344,0);send(12'h1c7,0);
   send(target[31:0],0);send({29'b0,target[34:32]},0);
   for(i=0;i<16;i=i+1)begin
     if(pattern==0) word_ascii=(i%2==0)?64'h333231647770796d:64'h393939647770796d;
     else word_ascii=64'h333231647770796d;
     send(word_ascii[31:0],0);send(word_ascii[63:32],i==15);
   end
   for(j=0;j<4;j=j+1)begin
     wait(outvalid);@(negedge clk);held=dout;
     repeat(7)begin @(posedge clk);if(!outvalid || dout!==held || outlast!==(j==3))$fatal(1,"Backpressure stability");end
     if(outkeep!==15)$fatal(1,"KEEP");
     if(j==0 && dout!==32'h31524344)$fatal(1,"Magic");
     if(j==1 && dout!=={16'b0,expected})$fatal(1,"Matches got=%h expected=%h",dout,expected);
     if(j==2)begin if(dout<400 || dout>2000)$fatal(1,"Cycle count %d",dout);$display("COMPUTE_CYCLES=%0d",dout);end
     @(negedge clk);ready=1;@(posedge clk);@(negedge clk);ready=0;
   end
   if(status[7:1]!=0)$fatal(1,"Status=%h",status);
 end endtask
 initial begin
   repeat(5)@(negedge clk);resetn=1;
   // Independent expected low 35-bit hashes from upstream descrypt_test.v.
   batch(35'h3cc8731ad,16'h5555,0);
   batch(35'h7080068cb,16'haaaa,0);
   batch(35'h3cc8731ad,16'hffff,1);
   batch(35'h000000000,16'h0000,1);
   $readmemh("vectors.mem",vectors);
   for(v=0;v<8;v=v+1)begin
     for(n=0;n<36;n=n+1)send(vectors[v*37+n],n==35);
     for(r=0;r<4;r=r+1)begin
       wait(outvalid);@(negedge clk);
       if(r==1 && dout!==vectors[v*37+36])$fatal(1,"Reference mismatch case=%d got=%h exp=%h",v,dout,vectors[v*37+36]);
       if(outlast!==(r==3))$fatal(1,"Reference TLAST");
       ready=1;@(posedge clk);@(negedge clk);ready=0;
     end
     if(status[7:1]!=0)$fatal(1,"Reference status");
   end
   // Malformed frame must latch error and never launch more computation.
   send(32'h31534344,1);repeat(4)@(negedge clk);
   if(!status[2] || inready || outvalid)$fatal(1,"Malformed frame accepted");
   resetn=0;repeat(3)@(negedge clk);resetn=1;repeat(3)@(negedge clk);
   if(!status[1] || inready)$fatal(1,"Reset guard failed");
   if(reject_done!==6'b111111)$fatal(1,"Negative protocol cases incomplete");
   $display("DESCRYPT_TEST_PASS batches=12 candidates=192 salts=8 backpressure=PASS malformed=PASS reset_guard=PASS");
   $finish;
 end
endmodule

module reject_case #(parameter CASE_ID=0)(input clk,output reg done=0);
 reg resetn=0,valid=0,last=0;
 reg [3:0] keep=15;
 reg [31:0] data=0;
 wire ready,ov;
 wire [31:0] status;
 descrypt_axis_top dut(.aclk(clk),.aresetn(resetn),.s_axis_tdata(data),
 .s_axis_tkeep(keep),.s_axis_tlast(last),.s_axis_tvalid(valid),.s_axis_tready(ready),
 .m_axis_tdata(),.m_axis_tkeep(),.m_axis_tlast(),.m_axis_tvalid(ov),.m_axis_tready(1'b1),.status(status));
 integer i,stop_word;
 initial begin
   stop_word=(CASE_ID==2)?1:(CASE_ID==3)?3:(CASE_ID==4)?4:(CASE_ID==5)?35:0;
   repeat(5)@(negedge clk);resetn=1;
   for(i=0;i<=stop_word;i=i+1)begin
     @(negedge clk);valid=1;data=(i==0)?32'h31534344:0;last=0;keep=15;
     if(i==stop_word)case(CASE_ID)
     0:data=32'hdeadbeef;
     1:keep=3;
     2:data=32'h1000;
     3:data=32'h8;
     4:data=32'h80;
     5:last=0; // Missing final TLAST.
     endcase
     @(posedge clk);if(!ready)$fatal(1,"Negative test not ready");
     @(negedge clk);valid=0;
   end
   repeat(5)@(negedge clk);
   if(!status[2] || ready || ov || dut.core.state!==0)$fatal(1,"Invalid frame reached core case=%d",CASE_ID);
   done=1;
 end
endmodule
