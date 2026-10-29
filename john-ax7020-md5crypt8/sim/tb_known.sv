`timescale 1ns/1ps
module tb_known;
 reg clk=0;always #5 clk=~clk;
 reg resetn=0,valid=0,last=0,ready=0;
 reg [31:0] din=0;
 wire ir,ov,ol;
 wire [31:0] dout,status;
 md5crypt_lane dut(.aclk(clk),.aresetn(resetn),.s_axis_tdata(din),.s_axis_tkeep(4'hf),
 .s_axis_tlast(last),.s_axis_tvalid(valid),.s_axis_tready(ir),.m_axis_tdata(dout),
 .m_axis_tkeep(),.m_axis_tlast(ol),.m_axis_tvalid(ov),.m_axis_tready(ready),.status(status));
 integer j,p,n,cycles=0;
 reg [11:0] seen=0;
 reg [31:0] expected[0:3];
 always @(posedge clk)begin
   cycles=cycles+1;
   if(cycles%10000==0 && $test$plusargs("PROBE"))begin
     $display("TRACE cycle=%0d jobs=%0d received=%0d collect=%0d err=%h core_ready=%h round0=%h saltlen0=%h keylen0=%h",cycles,dut.jobs,dut.received,dut.collect,dut.unit_i.genblk2.ctrl.err,dut.unit_i.core_ready,dut.unit_i.genblk2.ctrl.cpu.registers.reg_mem[14],dut.unit_i.genblk2.ctrl.cpu.registers.reg_mem[12],dut.unit_i.genblk2.ctrl.cpu.registers.reg_mem[13]);
     for(j=0;j<12;j=j+1)$display("THREAD %0d state=%h IP=%h rounds=%h R0=%h flags=%h",j,dut.unit_i.genblk2.ctrl.engine.thread_state.mem[j],dut.unit_i.genblk2.ctrl.cpu.instruction.IP_mem[j],dut.unit_i.genblk2.ctrl.cpu.registers.reg_mem[16*j+14],dut.unit_i.genblk2.ctrl.cpu.registers.reg_mem[16*j],dut.unit_i.genblk2.ctrl.cpu.cpu_flags.flags_mem[j]);
     $display("ROM19=%h ROM20=%h ROM21=%h ROM22=%h",dut.unit_i.genblk2.ctrl.cpu.instruction.instr_mem[19],dut.unit_i.genblk2.ctrl.cpu.instruction.instr_mem[20],dut.unit_i.genblk2.ctrl.cpu.instruction.instr_mem[21],dut.unit_i.genblk2.ctrl.cpu.instruction.instr_mem[22]);
     $display("CORE starts=%d %d %d %d inputs=%d %d %d %d ready=%b input_ready=%b cnt=%d %d ctx=%b",dut.unit_i.cores[0].genblk1.core.X_START[0],dut.unit_i.cores[0].genblk1.core.X_START[1],dut.unit_i.cores[0].genblk1.core.X_START[2],dut.unit_i.cores[0].genblk1.core.X_START[3],dut.unit_i.cores[0].genblk1.core.X_SET_INPUT_READY[0],dut.unit_i.cores[0].genblk1.core.X_SET_INPUT_READY[1],dut.unit_i.cores[0].genblk1.core.X_SET_INPUT_READY[2],dut.unit_i.cores[0].genblk1.core.X_SET_INPUT_READY[3],dut.unit_i.cores[0].genblk1.core.ready,dut.unit_i.cores[0].genblk1.core.input_ready,dut.unit_i.cores[0].genblk1.core.cnt0,dut.unit_i.cores[0].genblk1.core.cnt1,dut.unit_i.core_ctx_num);
     if($test$plusargs("PROBE"))$finish;
   end
   if(status[8:1]!=0 || cycles>2000000)$fatal(1,"Known test failure status=%h",status);
 end
 initial begin
   expected[0]=32'hc9631d40;expected[1]=32'h15f8d1a4;
   expected[2]=32'hda88b604;expected[3]=32'h05032f52;
   repeat(30)@(negedge clk);resetn=1;
   for(j=0;j<12;j=j+1)for(p=0;p<26;p=p+1)begin
     @(negedge clk);valid=1;last=(j==11&&p==25);
     case(p)
     0:din=1000;1:din=8;2:din=32'h34333231;3:din=32'h38373635;
     6:din=j;8:din=3;10:din=32'h00636261;default:din=0;
     endcase
     do @(posedge clk);while(!ir);
   end
   @(negedge clk);valid=0;last=0;
   wait(ov);
   for(n=0;n<74;n=n+1)begin
     @(negedge clk);
     if(!ov || ol!==(n==73))$fatal(1,"Known framing");
     if(n==0 && dout!==32'h38524d4a)$fatal(1,"Known header");
     if(n==1)$display("KNOWN_UNIT_CYCLES %0d",dout);
     if(n>=2)begin
       p=(n-2)%6;
       if(p==0)begin
         if(dout>11 || seen[dout])$fatal(1,"Known ID");seen[dout]=1;
       end else if(p==1)begin if(dout!==0)$fatal(1,"Known ID high");end
       else if(dout!==expected[p-2])$fatal(1,"Known digest word=%d got=%h expected=%h",p-2,dout,expected[p-2]);
     end
     ready=1;@(posedge clk);@(negedge clk);ready=0;
   end
   if(seen!==12'hfff)$fatal(1,"Known missing IDs");
   $display("KNOWN_TEST_PASS jobs=12 rounds=1000");$finish;
 end
endmodule

