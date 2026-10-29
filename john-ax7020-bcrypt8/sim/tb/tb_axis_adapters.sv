`timescale 1ns/1ps
module tb_axis_adapters;
 reg clk=0,rst=0;
 always #5 clk=~clk;
 reg [31:0] sd=0;
 reg [3:0] sk=0;
 reg sl=0,sv=0,byte_ready=0;
 wire sr,bv,ie;
 wire [7:0] bd;
 axis_to_john_pktcomm input_dut(clk,rst,sd,sk,sl,sv,sr,bd,bv,byte_ready,ie);
 integer cycle=0,got=0,sent=0,i,j,n;
 reg check_bytes=1;
 always @(posedge clk) begin
   cycle<=cycle+1;
   if(bv && byte_ready && check_bytes) begin
     if(bd !== (got%256)) $fatal(1,"byte lane order got=%d value=%h",got,bd);
     got=got+1;
   end
 end
 always @(negedge clk) byte_ready=(cycle%11)>3;
 task beat(input integer bytes);
 begin
   @(negedge clk); sd=0; sk=0; sl=1; sv=1;
   for(j=0;j<bytes;j=j+1) begin sd[8*j+:8]=(sent+j)%256; sk[j]=1; end
   @(posedge clk); while(!sr) @(posedge clk);
   @(negedge clk); sv=0; sent=sent+bytes;
 end endtask
 wire [15:0] od;
 reg oe=1,orr=0,orst=0;
 wire ord,ov,ol,oerr;
 wire [31:0] data;
 wire [3:0] keep;
 john_pktcomm_to_axis output_dut(clk,orst,od,oe,ord,data,keep,ol,ov,orr,oerr);
 integer inword=0,outbyte=0,outpackets=0;
 function [7:0] expected(input integer x);
   case(x%48)
     0: expected=2;
     1: expected=8'hd3;
     4: expected=30;
     5,6: expected=0;
     default: expected=x%48;
   endcase
 endfunction
 assign od={expected(2*inword+1),expected(2*inword)};
 reg stalled=0;
 reg [37:0] hold_data;
 always @(posedge clk) begin
   if(ord) inword<=inword+1;
   if(stalled && hold_data !== {ov,ol,keep,data}) $fatal(1,"unstable output");
   stalled<=ov && !orr;
   hold_data<={ov,ol,keep,data};
   if(ov && orr) begin
     if(keep!==15) $fatal(1,"keep");
     for(n=0;n<4;n=n+1)
       if(data[8*n+:8]!==expected(outbyte+n)) $fatal(1,"output bytes");
     outbyte=outbyte+4;
     if(ol!==(outbyte%48==0)) $fatal(1,"packet boundary");
     if(ol) outpackets=outpackets+1;
   end
 end
 always @(negedge clk) begin
   orr=(cycle%31)>21;
   oe=inword>=240;
 end
 initial begin
   repeat(10) @(negedge clk); rst=1; orst=1;
   for(i=0;i<64;i=i+1) beat(1+i%4);
   wait(got==sent); @(negedge clk);
   sk=5; sv=1; sl=1;
   @(posedge clk); while(!sr) @(posedge clk);
   @(negedge clk); sv=0;
   repeat(5) @(negedge clk);
   if(!ie || sr || bv) $fatal(1,"bad keep must fail closed");
   rst=0; @(negedge clk); rst=1;
   if(ie) $fatal(1,"adapter startup reset");
   wait(outpackets==10);
   repeat(20) @(negedge clk);
   if(oerr || outbyte!=480) $fatal(1,"output coverage");
   $display("ADAPTERS_PASS input_bytes=%0d output_packets=%0d",got,outpackets);
   $finish;
 end
 initial begin #1000000; $fatal(1,"adapter timeout got=%0d sent=%0d ie=%b i=%0d inword=%0d packets=%0d oerr=%b",got,sent,ie,i,inword,outpackets,oerr); end
endmodule
