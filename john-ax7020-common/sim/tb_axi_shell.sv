`timescale 1ns/1ps
module tb_axi_shell;
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
 wire native_tx_tlast,native_tx_tvalid;reg native_tx_tready=1;
 reg [31:0] native_rx_tdata=0;reg [3:0] native_rx_tkeep=15;reg native_rx_tlast=0,native_rx_tvalid=0;
 wire native_rx_tready;reg [31:0] native_status=0;reg native_initialized=0;
 john_axi_shell #(.ALGORITHM(ALG)) dut(.*);
 integer nc=0,rc=0;reg checking=0;integer tick=0;
 reg [31:0] last_data;reg last_stalled=0;
 always @(posedge aclk)begin
  tick<=tick+1;
  if(native_tx_tvalid && native_tx_tready)begin
   if(native_tx_tlast!=(nc==IB/4-1))$fatal(1,"Native TLAST");
   if(native_tx_tdata!=(nc==0&&ALG!=1?IM:nc==1&&ALG!=1?123:32'h12340000+nc))$fatal(1,"Native data");
   nc<=nc+1;
  end
  if(last_stalled && (!m_axis_tvalid || m_axis_tdata!==last_data))$fatal(1,"Output changed under backpressure");
  last_stalled<=m_axis_tvalid && !m_axis_tready;last_data<=m_axis_tdata;
  if(checking && m_axis_tvalid && m_axis_tready)begin
   if(m_axis_tkeep!=15 || m_axis_tlast!=(rc==(64+OB)/4-1))$fatal(1,"Outer framing");
   if(rc==0 && m_axis_tdata!=32'h3152544a)$fatal(1,"Response magic");
   if(rc==3 && m_axis_tdata!=64+OB)$fatal(1,"Response length");
   if(rc==10 && m_axis_tdata!=0)$fatal(1,"Unexpected task error %h",m_axis_tdata);
   if(rc==11 && m_axis_tdata!=N)$fatal(1,"Completed count");
   if(rc>=16 && m_axis_tdata!=(rc==16&&ALG!=1?OM:rc==17&&ALG!=1?123:32'h56780000+rc-16))$fatal(1,"Response payload at %d",rc);
   rc<=rc+1;
  end
 end
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
 task reply(input [31:0] d,input bit last);
 begin
  @(negedge aclk);native_rx_tdata=d;native_rx_tlast=last;native_rx_tvalid=1;
  do @(posedge aclk);while(!native_rx_tready);
  @(negedge aclk);native_rx_tvalid=0;
 end endtask
 integer j;reg [31:0] h[0:15];
 initial begin
  #2000000;$fatal(1,"Test timeout ALG=%0d",ALG);
 end
 initial begin
  repeat(5)@(negedge aclk);aresetn=1;
  rd('h84,0,1);native_initialized=1;repeat(3)@(negedge aclk);
  rd('h00,32'h4a435250,-1);rd('h04,32'h10001,-1);rd('h08,65536,-1);rd('h20,ALG,-1);
  rd('he4,ALG*4096,-1);rd(ALG*4096,1,-1);rd(ALG==1?'h2000:'h1000,0,-1);
  rd('h8000,1,-1);rd('h8100,1,-1);rd('h8f00,0,-1);
  wr('h240,32'h5aa5a55a,1,0);rd('h240,32'h5aa5a55a,-1);
  wr('h000,123,0,2);wr('h241,12,1,2);
  s_axi_wstrb=3;wr('h240,0,1,2);s_axi_wstrb=15;rd('h240,32'h5aa5a55a,-1);
  wr('h100,42,0,0);wr('h104,0,1,0);wr('h108,77,0,0);wr('h10c,123,1,0);
  wr('h110,ALG,0,0);wr('h114,256+ALG,1,0);wr('h118,IB,0,0);wr('h11c,64+OB,1,0);
  wr('h120,N,0,0);wr('h124,N,1,0);wr('h128,OB,0,0);
  wr('h88,1,0,0);wr('h80,1,1,0);rd('h90,0,-1);rd('h8c,1,-1);
  h[0]=32'h3151544a;h[1]='h10000;h[2]=64;h[3]=64+IB;h[4]=ALG;h[5]=256+ALG;
  h[6]=42;h[7]=0;h[8]=77;h[9]=123;h[10]=N;h[11]=N;h[12]=OB;h[13]=0;h[14]=0;h[15]=0;
  for(j=0;j<16;j=j+1)send(h[j],0);
  for(j=0;j<IB/4;j=j+1)send(j==0&&ALG!=1?IM:j==1&&ALG!=1?123:32'h12340000+j,j==IB/4-1);
  for(j=0;j<OB/4;j=j+1)reply(j==0&&ALG!=1?OM:j==1&&ALG!=1?123:32'h56780000+j,ALG==1?j%12==11:j==OB/4-1);
  checking=1;
  while(rc<(64+OB)/4)begin @(negedge aclk);m_axis_tready=tick%5!=0;end
  @(negedge aclk);checking=0;m_axis_tready=0;
  rd('h84,4,12);wr('h80,4,1,0);rd('h188,N,-1);rd('h1d8,64+OB,-1);
  wr('h80,2,0,0);rd('h84,1,1);
  // Snapshot must survive RELEASE unchanged until explicitly refreshed.
  rd('h188,N,-1);rd('h1d8,64+OB,-1);
  // Wrong header must be rejected before any native input is accepted.
  wr('h80,1,0,0);send(32'hdeadbeef,0);repeat(5)@(negedge aclk);rd('h9c,6,-1);
  if(nc!=IB/4)$fatal(1,"Header failure leaked to native core");
  // Error response remains a complete 64-byte frame, then permits RELEASE
  // because no native input was accepted for this failed batch.
  for(j=0;j<16;j=j+1)begin
   wait(m_axis_tvalid);@(negedge aclk);
   if(m_axis_tlast!=(j==15))$fatal(1,"Error response TLAST");
   if(j==3 && m_axis_tdata!=64)$fatal(1,"Error response size");
   if(j==10 && m_axis_tdata!=6)$fatal(1,"Error response code");
   if(j>=11 && j<=13 && m_axis_tdata!=0)$fatal(1,"Error response counters");
   m_axis_tready=1;@(posedge aclk);@(negedge aclk);m_axis_tready=0;
  end
  rd('h84,8,12);wr('h80,2,0,0);rd('h84,1,1);
  // Watchdog before any native byte: recoverable error, not a fake success.
  wr('hb8,2,0,0);wr('h80,1,0,0);
  repeat(400)@(negedge aclk);
  rd('h9c,16,-1);rd('h84,0,32);
  wr('h80,1,0,0);rd('h90,1,-1);
  $display("AXI_SHELL_PASS ALG=%0d",ALG);$finish;
 end
endmodule
