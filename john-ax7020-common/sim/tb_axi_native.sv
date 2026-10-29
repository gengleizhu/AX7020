`timescale 1ns/1ps
module tb_axi_native;
 parameter integer ALG=3;
 localparam IB=ALG==1?16:ALG==2?1160:ALG==5?6664:9992;
 localparam OB=ALG==1?96:ALG==2?168:ALG==3?2408:ALG==4?3944:4664;
 localparam N=ALG==1?2:ALG==2?128:ALG==5?64:96;
 localparam IM=ALG==2?32'h38534344:ALG==3?32'h38534d44:ALG==4?32'h38534853:32'h34534853;
 localparam OM=ALG==2?32'h38524344:ALG==3?32'h38524d44:ALG==4?32'h38524853:32'h34524853;
 reg aclk=0;always #5 aclk=~aclk;
 reg aresetn=0;
 reg [15:0] s_axi_awaddr=0,s_axi_araddr=0;
 reg [2:0] s_axi_awprot=0,s_axi_arprot=0;
 reg s_axi_awvalid=0,s_axi_wvalid=0,s_axi_bready=0,s_axi_arvalid=0,s_axi_rready=0;
 wire s_axi_awready,s_axi_wready,s_axi_bvalid,s_axi_arready,s_axi_rvalid;
 reg [31:0] s_axi_wdata=0;reg [3:0] s_axi_wstrb=15;
 wire [31:0] s_axi_rdata;wire [1:0] s_axi_bresp,s_axi_rresp;
 reg [31:0] s_axis_tdata=0;reg [3:0] s_axis_tkeep=15;reg s_axis_tlast=0,s_axis_tvalid=0;
 wire s_axis_tready;wire [31:0] m_axis_tdata;wire [3:0] m_axis_tkeep;wire m_axis_tlast,m_axis_tvalid;
 reg m_axis_tready=0;wire [31:0] native_tx_tdata;wire [3:0] native_tx_tkeep;
 wire native_tx_tlast,native_tx_tvalid;wire native_tx_tready;
 wire [31:0] native_rx_tdata;wire [3:0] native_rx_tkeep;wire native_rx_tlast,native_rx_tvalid;
 wire native_rx_tready;wire [31:0] native_status;wire native_initialized;
 john_axi_shell #(.ALGORITHM(ALG)) dut(.*);
 task wr(input [15:0] a,input [31:0] d,input bit reverse_order,input [1:0] expected);
 begin
  @(negedge aclk);s_axi_awaddr=a;s_axi_wdata=d;
  if(reverse_order)begin
   s_axi_wvalid=1;do @(posedge aclk);while(!s_axi_wready);
   @(negedge aclk);s_axi_wvalid=0;repeat(3)@(negedge aclk);s_axi_awvalid=1;
   do @(posedge aclk);while(!s_axi_awready);@(negedge aclk);s_axi_awvalid=0;
  end else begin
   s_axi_awvalid=1;do @(posedge aclk);while(!s_axi_awready);
   @(negedge aclk);s_axi_awvalid=0;repeat(2)@(negedge aclk);s_axi_wvalid=1;
   do @(posedge aclk);while(!s_axi_wready);@(negedge aclk);s_axi_wvalid=0;
  end
  wait(s_axi_bvalid);if(s_axi_bresp!=expected)$fatal(1,"BRESP %h",a);
  repeat(2)@(negedge aclk);s_axi_bready=1;@(negedge aclk);s_axi_bready=0;
 end endtask
 task rd(input [15:0] a,input [31:0] expected,input [31:0] mask);
 begin
  @(negedge aclk);s_axi_araddr=a;s_axi_arvalid=1;
  do @(posedge aclk);while(!s_axi_arready);
  @(negedge aclk);s_axi_arvalid=0;wait(s_axi_rvalid);
  if((s_axi_rdata&mask)!=(expected&mask))$fatal(1,"Read %h got %h expected %h",a,s_axi_rdata,expected);
  repeat(2)@(negedge aclk);s_axi_rready=1;@(negedge aclk);s_axi_rready=0;
 end endtask
 task send(input [31:0] d,input bit last);
 begin
  @(negedge aclk);s_axis_tdata=d;s_axis_tlast=last;s_axis_tvalid=1;
  do @(posedge aclk);while(!s_axis_tready);
  @(negedge aclk);s_axis_tvalid=0;
 end endtask

 generate
 if(ALG==3)begin: md5
 md5crypt8_axis_top core(.aclk(aclk),.aresetn(aresetn),.s_axis_tdata(native_tx_tdata),.s_axis_tkeep(native_tx_tkeep),.s_axis_tlast(native_tx_tlast),.s_axis_tvalid(native_tx_tvalid),.s_axis_tready(native_tx_tready),.m_axis_tdata(native_rx_tdata),.m_axis_tkeep(native_rx_tkeep),.m_axis_tlast(native_rx_tlast),.m_axis_tvalid(native_rx_tvalid),.m_axis_tready(native_rx_tready),.status(native_status),.initialized(native_initialized));
 end else if(ALG==4)begin: sha256
 sha256crypt8_axis_top core(.aclk(aclk),.aresetn(aresetn),.s_axis_tdata(native_tx_tdata),.s_axis_tkeep(native_tx_tkeep),.s_axis_tlast(native_tx_tlast),.s_axis_tvalid(native_tx_tvalid),.s_axis_tready(native_tx_tready),.m_axis_tdata(native_rx_tdata),.m_axis_tkeep(native_rx_tkeep),.m_axis_tlast(native_rx_tlast),.m_axis_tvalid(native_rx_tvalid),.m_axis_tready(native_rx_tready),.status(native_status),.initialized(native_initialized));
 end else begin: sha512
 sha512crypt4_axis_top core(.aclk(aclk),.aresetn(aresetn),.s_axis_tdata(native_tx_tdata),.s_axis_tkeep(native_tx_tkeep),.s_axis_tlast(native_tx_tlast),.s_axis_tvalid(native_tx_tvalid),.s_axis_tready(native_tx_tready),.m_axis_tdata(native_rx_tdata),.m_axis_tkeep(native_rx_tkeep),.m_axis_tlast(native_rx_tlast),.m_axis_tvalid(native_rx_tvalid),.m_axis_tready(native_rx_tready),.status(native_status),.initialized(native_initialized));
 end
 endgenerate
 localparam DW=ALG==3?4:ALG==4?8:16;
 localparam UNITS=ALG==5?4:8;
 localparam PER=N/UNITS;
 localparam UW=3+PER*(DW+2);
 reg [31:0] inputs[0:IB/4-1],expected[0:N*DW-1];
 reg [N-1:0] seen;
 integer j,k,wave,p,u,field,id,part;
 reg [31:0] h[0:15],held;
 integer cycles=0;
 always @(posedge aclk)begin
  cycles<=cycles+1;
  if(cycles>20000000)$fatal(1,"Native integration timeout ALG=%0d",ALG);
 end
 initial begin
  $readmemh("input.mem",inputs);$readmemh("expected.mem",expected);
  repeat(30)@(negedge aclk);aresetn=1;
  wait(native_initialized);repeat(3)@(negedge aclk);
  for(wave=0;wave<2;wave=wave+1)begin
   seen=0;id=0;
   wr('h100,42,0,0);wr('h104,0,1,0);wr('h108,77,0,0);wr('h10c,inputs[1]+wave,1,0);
   wr('h110,ALG,0,0);wr('h114,256+ALG,1,0);wr('h118,IB,0,0);wr('h11c,64+OB,1,0);
   wr('h120,N,0,0);wr('h124,N,1,0);wr('h128,OB,0,0);
   wr('h80,1,1,0);rd('h90,0,-1);
   h[0]=32'h3151544a;h[1]='h10000;h[2]=64;h[3]=64+IB;h[4]=ALG;h[5]=256+ALG;
   h[6]=42;h[7]=0;h[8]=77;h[9]=inputs[1]+wave;h[10]=N;h[11]=N;h[12]=OB;h[13]=0;h[14]=0;h[15]=0;
   for(j=0;j<16;j=j+1)send(h[j],0);
   for(j=0;j<IB/4;j=j+1)send(j==1?inputs[j]+wave:inputs[j],j==IB/4-1);
   for(j=0;j<(64+OB)/4;j=j+1)begin
    wait(m_axis_tvalid);@(negedge aclk);held=m_axis_tdata;
    repeat(j%4)begin
     @(posedge aclk);
     if(!m_axis_tvalid || m_axis_tdata!==held)$fatal(1,"Native response backpressure");
    end
    @(negedge aclk);
    if(m_axis_tkeep!=15 || m_axis_tlast!=(j==(64+OB)/4-1))$fatal(1,"Native outer framing %d",j);
    if(j==0 && held!==32'h3152544a)$fatal(1,"Outer magic");
    if(j==10 && held!==0)$fatal(1,"Native task failed code=%h",held);
    if(j==11 && held!==N)$fatal(1,"Completed count");
    if(j==16 && held!==OM)$fatal(1,"Native magic");
    if(j==17 && held!==inputs[1]+wave)$fatal(1,"Native tag");
    if(j>=18)begin
     p=j-18;u=p/UW;field=p%UW;
     if(field==0 && held!==u)$fatal(1,"Unit ID");
     if(field>=3)begin
      part=(field-3)%(DW+2);
      if(part==0)begin
       id=held;
       if(id<u*PER || id>=(u+1)*PER || seen[id])$fatal(1,"Candidate ID");
       seen[id]=1;
      end else if(part==1)begin if(held!==0)$fatal(1,"Candidate ID high");end
      else if(held!==expected[id*DW+part-2])$fatal(1,"Digest mismatch ALG=%d job=%d word=%d",ALG,id,part-2);
     end
    end
    m_axis_tready=1;@(posedge aclk);@(negedge aclk);m_axis_tready=0;
   end
   if(!(&seen))$fatal(1,"Missing native results");
   wr('h80,4,0,0);rd('h188,N,-1);rd('h84,4,12);
   wr('h80,2,0,0);rd('h84,1,1);
   $display("AXI_NATIVE_BATCH_PASS ALG=%0d wave=%0d cycles=%0d",ALG,wave,cycles);
  end
  $display("AXI_NATIVE_PASS ALG=%0d",ALG);$finish;
 end
endmodule

