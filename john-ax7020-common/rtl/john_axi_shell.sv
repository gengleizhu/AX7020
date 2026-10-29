// Common AXI ABI 1.1. One finite batch in flight. Native cores are never reset
// by a command: original John initialization requires FPGA reconfiguration.
module john_axi_shell #(
 parameter integer ALGORITHM=3,
 parameter integer CLOCK_HZ=100000000,
 parameter integer BUILD_DATE=20261029,
 parameter integer RESULT_WORDS=2048
)(
 (* X_INTERFACE_PARAMETER="ASSOCIATED_BUSIF S_AXI:S_AXIS:M_AXIS:NATIVE_TX:NATIVE_RX, ASSOCIATED_RESET aresetn, FREQ_HZ 100000000" *)
 (* X_INTERFACE_INFO="xilinx.com:signal:clock:1.0 aclk CLK" *) input wire aclk,
 (* X_INTERFACE_INFO="xilinx.com:signal:reset:1.0 aresetn RST" *) input wire aresetn,
 (* X_INTERFACE_INFO="xilinx.com:interface:aximm:1.0 S_AXI AWADDR", X_INTERFACE_PARAMETER="PROTOCOL AXI4LITE, ADDR_WIDTH 16, DATA_WIDTH 32" *) input wire [15:0] s_axi_awaddr,
 (* X_INTERFACE_INFO="xilinx.com:interface:aximm:1.0 S_AXI AWPROT" *) input wire [2:0] s_axi_awprot,
 (* X_INTERFACE_INFO="xilinx.com:interface:aximm:1.0 S_AXI AWVALID" *) input wire s_axi_awvalid,
 (* X_INTERFACE_INFO="xilinx.com:interface:aximm:1.0 S_AXI AWREADY" *) output wire s_axi_awready,
 (* X_INTERFACE_INFO="xilinx.com:interface:aximm:1.0 S_AXI WDATA" *) input wire [31:0] s_axi_wdata,
 (* X_INTERFACE_INFO="xilinx.com:interface:aximm:1.0 S_AXI WSTRB" *) input wire [3:0] s_axi_wstrb,
 (* X_INTERFACE_INFO="xilinx.com:interface:aximm:1.0 S_AXI WVALID" *) input wire s_axi_wvalid,
 (* X_INTERFACE_INFO="xilinx.com:interface:aximm:1.0 S_AXI WREADY" *) output wire s_axi_wready,
 (* X_INTERFACE_INFO="xilinx.com:interface:aximm:1.0 S_AXI BRESP" *) output reg [1:0] s_axi_bresp,
 (* X_INTERFACE_INFO="xilinx.com:interface:aximm:1.0 S_AXI BVALID" *) output reg s_axi_bvalid,
 (* X_INTERFACE_INFO="xilinx.com:interface:aximm:1.0 S_AXI BREADY" *) input wire s_axi_bready,
 (* X_INTERFACE_INFO="xilinx.com:interface:aximm:1.0 S_AXI ARADDR" *) input wire [15:0] s_axi_araddr,
 (* X_INTERFACE_INFO="xilinx.com:interface:aximm:1.0 S_AXI ARPROT" *) input wire [2:0] s_axi_arprot,
 (* X_INTERFACE_INFO="xilinx.com:interface:aximm:1.0 S_AXI ARVALID" *) input wire s_axi_arvalid,
 (* X_INTERFACE_INFO="xilinx.com:interface:aximm:1.0 S_AXI ARREADY" *) output wire s_axi_arready,
 (* X_INTERFACE_INFO="xilinx.com:interface:aximm:1.0 S_AXI RDATA" *) output reg [31:0] s_axi_rdata,
 (* X_INTERFACE_INFO="xilinx.com:interface:aximm:1.0 S_AXI RRESP" *) output reg [1:0] s_axi_rresp,
 (* X_INTERFACE_INFO="xilinx.com:interface:aximm:1.0 S_AXI RVALID" *) output reg s_axi_rvalid,
 (* X_INTERFACE_INFO="xilinx.com:interface:aximm:1.0 S_AXI RREADY" *) input wire s_axi_rready,
 (* X_INTERFACE_INFO="xilinx.com:interface:axis:1.0 S_AXIS TDATA" *) input wire [31:0] s_axis_tdata,
 (* X_INTERFACE_INFO="xilinx.com:interface:axis:1.0 S_AXIS TKEEP" *) input wire [3:0] s_axis_tkeep,
 (* X_INTERFACE_INFO="xilinx.com:interface:axis:1.0 S_AXIS TLAST" *) input wire s_axis_tlast,
 (* X_INTERFACE_INFO="xilinx.com:interface:axis:1.0 S_AXIS TVALID" *) input wire s_axis_tvalid,
 (* X_INTERFACE_INFO="xilinx.com:interface:axis:1.0 S_AXIS TREADY" *) output wire s_axis_tready,
 (* X_INTERFACE_INFO="xilinx.com:interface:axis:1.0 M_AXIS TDATA" *) output wire [31:0] m_axis_tdata,
 (* X_INTERFACE_INFO="xilinx.com:interface:axis:1.0 M_AXIS TKEEP" *) output wire [3:0] m_axis_tkeep,
 (* X_INTERFACE_INFO="xilinx.com:interface:axis:1.0 M_AXIS TLAST" *) output wire m_axis_tlast,
 (* X_INTERFACE_INFO="xilinx.com:interface:axis:1.0 M_AXIS TVALID" *) output wire m_axis_tvalid,
 (* X_INTERFACE_INFO="xilinx.com:interface:axis:1.0 M_AXIS TREADY" *) input wire m_axis_tready,
 (* X_INTERFACE_INFO="xilinx.com:interface:axis:1.0 NATIVE_TX TDATA" *) output wire [31:0] native_tx_tdata,
 (* X_INTERFACE_INFO="xilinx.com:interface:axis:1.0 NATIVE_TX TKEEP" *) output wire [3:0] native_tx_tkeep,
 (* X_INTERFACE_INFO="xilinx.com:interface:axis:1.0 NATIVE_TX TLAST" *) output wire native_tx_tlast,
 (* X_INTERFACE_INFO="xilinx.com:interface:axis:1.0 NATIVE_TX TVALID" *) output wire native_tx_tvalid,
 (* X_INTERFACE_INFO="xilinx.com:interface:axis:1.0 NATIVE_TX TREADY" *) input wire native_tx_tready,
 (* X_INTERFACE_INFO="xilinx.com:interface:axis:1.0 NATIVE_RX TDATA" *) input wire [31:0] native_rx_tdata,
 (* X_INTERFACE_INFO="xilinx.com:interface:axis:1.0 NATIVE_RX TKEEP" *) input wire [3:0] native_rx_tkeep,
 (* X_INTERFACE_INFO="xilinx.com:interface:axis:1.0 NATIVE_RX TLAST" *) input wire native_rx_tlast,
 (* X_INTERFACE_INFO="xilinx.com:interface:axis:1.0 NATIVE_RX TVALID" *) input wire native_rx_tvalid,
 (* X_INTERFACE_INFO="xilinx.com:interface:axis:1.0 NATIVE_RX TREADY" *) output wire native_rx_tready,
 input wire [31:0] native_status,
 input wire native_initialized
);
 localparam integer UNITS=ALGORITHM==5?4:8;
 localparam integer CORES=ALGORITHM==3||ALGORITHM==4?3:ALGORITHM==5?4:1;
 localparam integer SLOTS=ALGORITHM==1?0:ALGORITHM==2?128:ALGORITHM==5?64:96;
 localparam integer IN_BYTES=ALGORITHM==1?0:ALGORITHM==2?1160:ALGORITHM==5?6664:9992;
 localparam integer OUT_BYTES=ALGORITHM==1?0:ALGORITHM==2?168:ALGORITHM==3?2408:ALGORITHM==4?3944:4664;
 localparam [31:0] IN_MAGIC=ALGORITHM==2?32'h38534344:ALGORITHM==3?32'h38534d44:ALGORITHM==4?32'h38534853:32'h34534853;
 localparam [31:0] OUT_MAGIC=ALGORITHM==2?32'h38524344:ALGORITHM==3?32'h38524d44:ALGORITHM==4?32'h38524853:32'h34524853;
 localparam [3:0] INIT=0,IDLE=1,ARMED=2,RX=3,RUN=4,DRAIN=5,DONE=6,ERROR=7;
 reg [3:0] state;
 reg [31:0] desc[0:17];
 reg [31:0] cmd_seq,ack_seq,cmd_result,timeout_us,watchdog_us,scratch;
 reg [31:0] first_error,error_detail,bad_offset,bus_errors,rejected,successes,failures;
 reg [31:0] snap_seq,irq_status,irq_enable,warnings;
 reg [31:0] snap[0:31];
 reg [31:0] snap_unit[0:7];
 reg [31:0] snap_diag[0:15];
 reg [31:0] snap_bus_errors,snap_native;
 reg drain_timeout;
 reg snapshot_valid,reload,initialized,input_complete,compute_done,output_complete;
 reg [4:0] header_pos;
 reg [31:0] input_count,result_count,tx_count;
 reg [31:0] batch_us,quiet_us;
 reg [31:0] micro_div;
 reg [63:0] uptime,elapsed,input_bytes,output_bytes,starve,stall,active,error_time;
 reg [31:0] result_read;
 reg [31:0] out_word;
 reg out_valid,ram_wait;
 (* ram_style="block" *) reg [31:0] results[0:RESULT_WORDS-1];
 reg have_aw,have_w;
 reg [15:0] aw;
 reg [31:0] wd;
 reg [3:0] ws;
 wire busy=state>=ARMED && state<=DRAIN;
 wire native_fault=ALGORITHM==1 ? |native_status[19:8] || |native_status[7:0] : |native_status[23:16] || |native_status[2:1];
 wire [31:0] unit_busy=ALGORITHM==1?0:({24'b0,native_status[15:8]} & ((1<<UNITS)-1));
 wire [31:0] status_word={12'b0,state,4'b0,snapshot_valid,(|warnings),
       (output_complete && first_error==0),output_complete,compute_done,input_complete,reload,initialized,
       (state==ERROR),(state==DONE),busy,(state==IDLE && initialized)};
 wire [31:0] output_payload=first_error==0?desc[10]:0;
 wire [31:0] completed=compute_done?desc[8]:0;
 wire [31:0] unit_done=(compute_done && ALGORITHM!=1)?((1<<UNITS)-1):0;
 wire [31:0] capabilities=32'h00000003 | (ALGORITHM==1?32'h400:0) | (ALGORITHM==2?32'h800:0);
 wire micro_tick=micro_div==CLOCK_HZ/1000000-1;
 wire rx_fire=s_axis_tvalid && s_axis_tready;
 wire nr_fire=native_rx_tvalid && native_rx_tready;
 wire tx_fire=m_axis_tvalid && m_axis_tready;
 wire in_end=input_count+4>=desc[6];
 wire [3:0] expected_keep=in_end?(desc[6][1:0]==0?15:desc[6][1:0]==1?1:desc[6][1:0]==2?3:7):15;
 wire native_input_bad=s_axis_tkeep!=expected_keep || s_axis_tlast!=in_end ||
       (ALGORITHM!=1 && ((input_count==0 && s_axis_tdata!=IN_MAGIC) || (input_count==4 && s_axis_tdata!=desc[3])));
 assign s_axi_awready=aresetn && !have_aw && !s_axi_bvalid;
 assign s_axi_wready=aresetn && !have_w && !s_axi_bvalid;
 assign s_axi_arready=aresetn && !s_axi_rvalid;
 assign s_axis_tready=aresetn && ((state==ARMED) || (state==RX && native_tx_tready));
 assign native_tx_tdata=s_axis_tdata;
 assign native_tx_tkeep=s_axis_tkeep;
 assign native_tx_tlast=s_axis_tlast;
 assign native_tx_tvalid=aresetn && state==RX && s_axis_tvalid && !native_input_bad;
 assign native_rx_tready=aresetn && (state==RX || state==RUN) && result_count<desc[10] && result_count<RESULT_WORDS*4;
 assign m_axis_tkeep=15;
 assign m_axis_tvalid=aresetn && state==DRAIN && (tx_count<64 || out_valid);
 assign m_axis_tlast=tx_count+4==64+output_payload;
 assign m_axis_tdata=tx_count<64?response_word(tx_count[5:2]):out_word;

 function automatic [31:0] request_word(input integer p);
 begin case(p)
  0:request_word=32'h3151544a;1:request_word=32'h10000;2:request_word=64;
  3:request_word=64+desc[6];4:request_word=ALGORITHM;5:request_word=256+ALGORITHM;
  6:request_word=desc[0];7:request_word=desc[1];8:request_word=desc[2];9:request_word=desc[3];
  10:request_word=desc[8];11:request_word=desc[9];12:request_word=desc[10];
  13:request_word=desc[11];14:request_word=0;default:request_word=0;
 endcase end endfunction
 function automatic [31:0] response_word(input integer p);
 begin case(p)
  0:response_word=32'h3152544a;1:response_word=32'h10000;2:response_word=64;
  3:response_word=64+output_payload;4:response_word=ALGORITHM;5:response_word=256+ALGORITHM;
  6:response_word=desc[0];7:response_word=desc[1];8:response_word=desc[2];9:response_word=desc[3];
  10:response_word=first_error;11:response_word=completed;12:response_word=output_payload;
  13:response_word=first_error?0:ALGORITHM==2?8:desc[9];
  14:response_word=(ALGORITHM==2?1:0)|(desc[8]<desc[9]?2:0);default:response_word=0;
 endcase end endfunction
 function automatic [31:0] arm_error;
 begin
  if(state!=IDLE || !initialized)arm_error=1;
  else if(desc[4]!=ALGORITHM)arm_error=4;
  else if(desc[5]!=256+ALGORITHM)arm_error=6;
  else if(desc[11]>1 || desc[12]!=0 || desc[14]!=0 || desc[15]!=0 || desc[16]!=0 || desc[17]!=0)arm_error=2;
  else if(ALGORITHM!=1 && desc[13]!=0)arm_error=8;
  else if(!desc[6] || desc[6]>65536 || !desc[8] || desc[8]>desc[9] ||
     !desc[10] || desc[10]>RESULT_WORDS*4 || desc[7]<64+desc[10])arm_error=5;
  else if(ALGORITHM!=1 && (desc[6]!=IN_BYTES || desc[9]!=SLOTS || desc[10]!=OUT_BYTES))arm_error=5;
  else if(ALGORITHM==1 && (desc[9]>RESULT_WORDS*4/48 || desc[9]!=desc[8] || desc[10]!=desc[9]*48))arm_error=5;
  else arm_error=0;
 end endfunction
 function automatic [31:0] read_reg(input [15:0] addr);
 integer u,c,o;reg [31:0] n;
 begin
 n=0;u=0;c=0;o=0;
 case(addr)
  'h000:n=32'h4a435250;'h004:n=32'h10001;'h008:n=65536;'h00c:n=32'h10000;
  'h010:n=BUILD_DATE;'h014:n=0;'h018:n=0;'h01c:n=0;
  'h020:n=ALGORITHM;'h024:n=UNITS;'h028:n=CORES;'h02c:n=UNITS*CORES;
  'h030:n=capabilities;'h034:n=256+ALGORITHM;'h038:n=SLOTS;
  'h03c:n=ALGORITHM==1?72:ALGORITHM==2?8:ALGORITHM==4?32:64;
  'h040:n=ALGORITHM==2?2:ALGORITHM==3?8:16;'h044:n=ALGORITHM==2?2:1;
  'h048:n=ALGORITHM==1?24:ALGORITHM==2?0:ALGORITHM==3?16:ALGORITHM==4?32:64;
  'h04c:n=IN_BYTES;'h050:n=OUT_BYTES;'h054:n=ALGORITHM==1?65536:IN_BYTES;
  'h058:n=ALGORITHM==1?RESULT_WORDS*4:OUT_BYTES;'h05c:n=CLOCK_HZ;'h060:n=1000000;
  'h064:n=ALGORITHM==1?0:ALGORITHM==2?25:1000;
  'h068:n=ALGORITHM==1?0:ALGORITHM==2?25:ALGORITHM==3?1000:999999999;
  'h06c:n=32;'h070:n=native_status;'h074:n=1;'h078:n=1;'h07c:n=32'h10000;
  'h084:n=status_word;'h088:n=cmd_seq;'h08c:n=ack_seq;'h090:n=cmd_result;
  'h094:n=irq_status;'h098:n=irq_enable;'h09c:n=first_error;'h0a0:n=error_detail;
  'h0a4:n=32'hffffffff;'h0a8:n=warnings;'h0ac:n=snap_seq;'h0b0:n={30'b0,snapshot_valid,1'b0};
  'h0b4:n=timeout_us;'h0b8:n=watchdog_us;'h0bc:n={30'b0,initialized,1'b1};
  'h0c0:n=0;'h0c4:n=1;'h0c8:n=unit_busy;'h0cc:n=ALGORITHM==1?0:(native_status>>16)&((1<<UNITS)-1);
  'h0d0:n=unit_done;'h0d4:n=ALGORITHM==1?0:(1<<UNITS)-1;
  'h0d8:n=(state==DONE)?desc[3]:0;
  'h0dc:n={28'b0,(output_complete && first_error!=0),output_complete,compute_done,input_complete};
  'h0e0:n=1<<(ALGORITHM-1);'h0e4:n=ALGORITHM*4096;'h0e8:n=32768;'h0ec:n=4096;
  'h0f0:n=256;'h0f4:n=256;'h0f8:n=8;'h0fc:n=15;
  'h240:n=scratch;'h244:n=bad_offset;'h248:n=snap_bus_errors;
  default:begin
   if(addr>='h100 && addr<='h144)n=desc[(addr-'h100)>>2];
   else if(addr>='h180 && addr<'h200)n=snap[(addr-'h180)>>2];
   else if(addr>='h200 && addr<'h240)n=snap_diag[(addr-'h200)>>2];
   else if(addr>='h400 && addr<'h800)begin
    u=(addr-'h400)>>5;o=addr&31;
    if(u<UNITS)case(o)
     0:n=ALGORITHM==1?0:{28'b0,snap_unit[u][2],snap_unit[u][1],snap_unit[u][0],1'b1};
     4:n=snap_unit[u][2]?10:0;8:n=0;
     default:n=0;
    endcase
   end else if(addr>='h1000 && addr<'h6000 && (addr>>12)==ALGORITHM)begin
    case(addr&4095)
     0:n=1;4:n=32'h10000;8:n=ALGORITHM;12:n=4;
     16:n=snapshot_valid?2:0;24:n=snap_native;
     32:n=ALGORITHM==2?25:0;40:n=ALGORITHM==2?35:ALGORITHM==3?1000:ALGORITHM>=4?999999999:0;
     36:n=ALGORITHM>=3?1000:0;
     44:n=ALGORITHM==1?1:ALGORITHM==2?16:0;
     48:n=ALGORITHM==1?2:ALGORITHM>=3?(ALGORITHM==5?16:12):0;
     52:n=ALGORITHM>=3?(ALGORITHM==3?1:ALGORITHM==4?5:6):0;
     default:n=0;
    endcase
   end else if(addr>='h8000)begin
    u=(addr-'h8000)>>12;c=((addr&4095)>>8)-1;o=addr&255;
    if(u<UNITS && (c<0 || c<CORES))case(o)
     0:n=1;4:n=(c<0 && ALGORITHM!=1)?1:0;
     8:n=c<0?snap_unit[u]:0;
     12:n=(c<0 && snap_unit[u][2])?10:0;
     56:n=c<0?CORES:c;60:n=snap_seq;default:n=0;
    endcase
   end
  end
 endcase
 read_reg=n;
 end endfunction

 task automatic fail(input [31:0] code,input [31:0] detail);
 begin
  if(first_error==0)begin
   first_error<=code;error_detail<=detail;error_time<=uptime;
   failures<=failures+1;reload<=input_count!=0;irq_status[1]<=1;
   state<=DRAIN;tx_count<=0;out_valid<=0;ram_wait<=0;
  end
 end endtask
 integer i;
 always @(posedge aclk)begin
  if(!aresetn)begin
   state<=INIT;initialized<=0;reload<=0;have_aw<=0;have_w<=0;
   s_axi_bvalid<=0;s_axi_rvalid<=0;s_axi_rdata<=0;s_axi_rresp<=0;s_axi_bresp<=0;
   cmd_seq<=0;ack_seq<=0;cmd_result<=0;timeout_us<=0;watchdog_us<=0;scratch<=0;
   first_error<=0;error_detail<=0;bad_offset<=0;bus_errors<=0;rejected<=0;successes<=0;failures<=0;
   snap_seq<=0;snapshot_valid<=0;irq_status<=0;irq_enable<=0;warnings<=0;
   input_complete<=0;compute_done<=0;output_complete<=0;header_pos<=0;
   input_count<=0;result_count<=0;tx_count<=0;batch_us<=0;quiet_us<=0;micro_div<=0;
   uptime<=0;elapsed<=0;input_bytes<=0;output_bytes<=0;starve<=0;stall<=0;active<=0;error_time<=0;
   out_valid<=0;ram_wait<=0;out_word<=0;result_read<=0;
   for(i=0;i<18;i=i+1)desc[i]<=0;
   for(i=0;i<32;i=i+1)snap[i]<=0;
   for(i=0;i<8;i=i+1)snap_unit[i]<=0;
   for(i=0;i<16;i=i+1)snap_diag[i]<=0;
   snap_bus_errors<=0;snap_native<=0;drain_timeout<=0;
  end else begin
   if(native_initialized)begin initialized<=1;if(state==INIT)state<=IDLE;end
   if(micro_tick)begin micro_div<=0;uptime<=uptime+1;end else micro_div<=micro_div+1;
   if(s_axi_awvalid && s_axi_awready)begin have_aw<=1;aw<=s_axi_awaddr;end
   if(s_axi_wvalid && s_axi_wready)begin have_w<=1;wd<=s_axi_wdata;ws<=s_axi_wstrb;end
   if(s_axi_bvalid && s_axi_bready)s_axi_bvalid<=0;
   if(s_axi_rvalid && s_axi_rready)s_axi_rvalid<=0;
   if(s_axi_arvalid && s_axi_arready)begin
    s_axi_rvalid<=1;s_axi_rdata<=read_reg(s_axi_araddr);s_axi_rresp<=s_axi_araddr[1:0]?2:0;
   end
   if(have_aw && have_w && !s_axi_bvalid)begin
    have_aw<=0;have_w<=0;s_axi_bvalid<=1;s_axi_bresp<=0;
    if(ws!=15 || aw[1:0]!=0)begin s_axi_bresp<=2;bad_offset<=aw;bus_errors<=bus_errors+1;end
    else if(aw=='h088)cmd_seq<=wd;
    else if(aw=='h240)scratch<=wd;
    else if(aw=='h094)irq_status<=irq_status & ~wd;
    else if(aw=='h0a8)warnings<=warnings & ~wd;
    else if(aw=='h0b4 && state==IDLE)timeout_us<=wd;
    else if(aw=='h0b8 && state==IDLE)watchdog_us<=wd;
    else if(aw>='h100 && aw<='h144 && state==IDLE)desc[(aw-'h100)>>2]<=wd;
    else if(aw=='h080)begin
     ack_seq<=cmd_seq;cmd_result<=0;
     case(wd)
     1:begin
      cmd_result<=arm_error();
      if(arm_error()==0)begin state<=ARMED;header_pos<=0;end
      else begin rejected<=rejected+1;irq_status[3]<=1;end
     end
     2:if((state==DONE || state==ERROR) && !reload)begin
      state<=IDLE;first_error<=0;error_detail<=0;input_complete<=0;compute_done<=0;output_complete<=0;
      input_count<=0;result_count<=0;tx_count<=0;batch_us<=0;quiet_us<=0;
      elapsed<=0;input_bytes<=0;output_bytes<=0;starve<=0;stall<=0;active<=0;drain_timeout<=0;
     end else begin cmd_result<=1;rejected<=rejected+1;end
     4:begin
      snap_seq<=snap_seq+1;snapshot_valid<=1;
      snap[0]<=input_complete?desc[8]:0;snap[1]<=0;snap[2]<=completed;snap[3]<=0;
      snap[4]<=compute_done?(ALGORITHM==2?8:desc[9]):0;snap[5]<=0;
      snap[6]<=input_bytes[31:0];snap[7]<=input_bytes[63:32];snap[8]<=output_bytes[31:0];snap[9]<=output_bytes[63:32];
      snap[10]<=elapsed[31:0];snap[11]<=elapsed[63:32];snap[12]<=active[31:0];snap[13]<=active[63:32];
      snap[14]<=starve[31:0];snap[15]<=starve[63:32];snap[16]<=stall[31:0];snap[17]<=stall[63:32];
      snap[18]<=uptime[31:0];snap[19]<=uptime[63:32];snap[20]<=error_time[31:0];snap[21]<=error_time[63:32];
      snap[22]<=output_complete?64+output_payload:0;snap[23]<=desc[3];snap[24]<=desc[0];snap[25]<=desc[1];
      snap[26]<=desc[2];snap[27]<=status_word;snap[28]<=desc[8];snap[29]<=unit_done;
      for(i=0;i<8;i=i+1)snap_unit[i]<=ALGORITHM==1?0:{28'b0,initialized,((native_status>>(16+i))&1)!=0,unit_done[i],unit_busy[i]};
      snap_native<=native_status;snap_bus_errors<=bus_errors;
      snap_diag[10]<=rejected;snap_diag[11]<=successes;snap_diag[12]<=failures;
      snap_diag[13]<=input_count>>2;snap_diag[14]<={28'b0,state};snap_diag[15]<=8;
     end
     8:if(state==IDLE)begin rejected<=0;successes<=0;failures<=0;bus_errors<=0;bad_offset<=0;end
       else begin cmd_result<=1;rejected<=rejected+1;end
     default:begin cmd_result<=2;rejected<=rejected+1;end
     endcase
    end else begin s_axi_bresp<=2;bad_offset<=aw;bus_errors<=bus_errors+1;end
   end
   if(busy)begin
    elapsed<=elapsed+1;
    if(|unit_busy)active<=active+1;
    if(state==RX && native_tx_tready && !s_axis_tvalid)starve<=starve+1;
    if(m_axis_tvalid && !m_axis_tready)stall<=stall+1;
    if(micro_tick)begin batch_us<=batch_us+1;quiet_us<=quiet_us+1;end
    if(rx_fire || nr_fire || tx_fire)quiet_us<=0;
   end
   if(rx_fire)begin
    input_bytes<=input_bytes+s_axis_tkeep[0]+s_axis_tkeep[1]+s_axis_tkeep[2]+s_axis_tkeep[3];
    if(state==ARMED)begin
     if(s_axis_tdata!=request_word(header_pos) || s_axis_tkeep!=15 || s_axis_tlast)fail(6,header_pos*4);
     else if(header_pos==15)begin state<=RX;header_pos<=0;end else header_pos<=header_pos+1;
    end else if(state==RX)begin
     if(native_input_bad)fail(9,input_count>>2);
     else begin
      input_count<=input_count+s_axis_tkeep[0]+s_axis_tkeep[1]+s_axis_tkeep[2]+s_axis_tkeep[3];
      if(in_end)begin input_complete<=1;state<=RUN;end
     end
    end
   end
   if(nr_fire)begin
    results[result_count>>2]<=native_rx_tdata;result_count<=result_count+4;
    if(native_rx_tkeep!=15 || (ALGORITHM==1?(native_rx_tlast!=((result_count%48)==44)):
       (native_rx_tlast!=(result_count+4==desc[10]))) ||
       (ALGORITHM!=1 && ((result_count==0 && native_rx_tdata!=OUT_MAGIC) || (result_count==4 && native_rx_tdata!=desc[3]))))fail(15,result_count>>2);
   end
   if(state==RUN && result_count==desc[10] && first_error==0)begin compute_done<=1;state<=DRAIN;tx_count<=0;end
   // Synchronous BRAM read, one entry buffered through arbitrary backpressure.
   if(state==DRAIN && tx_count>=64 && !out_valid && !ram_wait)begin result_read<=results[(tx_count-64)>>2];ram_wait<=1;end
   if(ram_wait)begin out_word<=result_read;out_valid<=1;ram_wait<=0;end
   if(tx_fire)begin
    output_bytes<=output_bytes+4;tx_count<=tx_count+4;
    if(tx_count>=64)out_valid<=0;
    if(m_axis_tlast)begin
     output_complete<=1;state<=(first_error || drain_timeout)?ERROR:DONE;irq_status[0]<=1;
     if(drain_timeout)begin first_error<=11;failures<=failures+1;irq_status[1]<=1;end
     else if(!first_error)successes<=successes+1;
    end
   end
   if((state==RX || state==RUN) && native_fault)fail(10,native_status);
   if(busy && first_error==0 && ((timeout_us!=0 && batch_us>=timeout_us) || (watchdog_us!=0 && quiet_us>=watchdog_us)))begin
    if(state!=DRAIN)fail(timeout_us!=0 && batch_us>=timeout_us?11:16,0);
    // AXIS cannot revoke a stalled beat. Keep the entire frame immutable;
    // PS detects warning/NEED_RELOAD and must quiesce/reset DMA before reload.
    else if(!drain_timeout)begin drain_timeout<=1;warnings[0]<=1;error_time<=uptime;reload<=1;end
   end
  end
 end
endmodule
