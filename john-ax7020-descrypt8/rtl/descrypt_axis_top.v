`timescale 1ns/1ps
// Fixed 16-candidate batch adapter around the unchanged John pipeline/comparator.
// Input: magic, salt, target[31:0], target[34:32], 16 little-endian ASCII[8].
// Output: magic, 16-bit provisional-match mask, compute cycles, status.
module descrypt_axis_top(
 input aclk, aresetn,
 input [31:0] s_axis_tdata, input [3:0] s_axis_tkeep,
 input s_axis_tlast, s_axis_tvalid, output s_axis_tready,
 output reg [31:0] m_axis_tdata, output [3:0] m_axis_tkeep,
 output m_axis_tlast, m_axis_tvalid, input m_axis_tready,
 output [31:0] status
);
 localparam RX=0, CONFIG=1, HASH=2, GAP=3, KEYS=4, META=5, WAIT_RESULT=6, TX=7;
 reg [3:0] state=RX;
 reg [31:0] words[0:35];
 reg [5:0] pos=0;
 reg [3:0] key_idx=0;
 reg [1:0] tx_idx=0;
 reg touched=0, reset_fault=0, protocol_error=0, timeout_error=0;
 reg [15:0] matches=0;
 reg [31:0] cycles=0;
 reg [2:0] parse=0;
 reg final_match=0;
 wire core_ready, core_idle, core_error, cmp_error;
 wire [3:0] nibble;
 reg [56:0] core_din;
 reg [2:0] core_addr;
 reg core_wr;
 wire [63:0] ascii_word={words[5+2*key_idx],words[4+2*key_idx]};
 wire [55:0] ascii7;
 genvar k;
 generate for(k=0;k<8;k=k+1) begin: pack7
   assign ascii7[7*k+:7]=ascii_word[8*k+:7];
 end endgenerate
 wire [63:0] key_bits;
 wire [55:0] key_pc1;
 crypt3_ascii2bin convert(ascii7,key_bits);
 pc1 permute(key_bits,key_pc1);
 wire fault=reset_fault|protocol_error|timeout_error|core_error|cmp_error;
 assign status={8'hDC,15'b0,timeout_error,3'b0,cmp_error,core_error,protocol_error,reset_fault,(state!=RX)};
 assign s_axis_tready=aresetn && !fault && state==RX;
 assign m_axis_tvalid=aresetn && !fault && state==TX;
 assign m_axis_tlast=tx_idx==3;
 assign m_axis_tkeep=4'hf;
 always @* begin
   case(tx_idx)
   0:m_axis_tdata=32'h31524344;
   1:m_axis_tdata={16'b0,matches};
   2:m_axis_tdata=cycles;
   default:m_axis_tdata=status;
   endcase
 end
 always @* begin
   core_wr=0; core_addr=0; core_din=0;
   if(aresetn && !fault) case(state)
   CONFIG:begin core_wr=1;core_addr=2;core_din={47'b0,words[1][9:0]};end
   HASH:begin core_wr=1;core_addr=1;core_din={21'b0,1'b1,words[3][2:0],words[2]};end
   KEYS:begin core_wr=1;core_addr=4;core_din={1'b1,key_pc1};end
   META:begin core_wr=1;core_addr=6;core_din=0;end
   default:begin end
   endcase
 end
 descrypt_core #(.ASYNC(0)) core(
   .CORE_CLK(aclk),.CMP_CLK(aclk),.din(core_din),.addr_in(core_addr),.wr_en(core_wr),
   .global_salt(words[1][11:10]),.crypt_ready(core_ready),.core_idle(core_idle),
   .core_error(core_error),.cmp_error(cmp_error),.dout_ready(1'b1),.dout(nibble));
 always @(posedge aclk) begin
   // Original core has configuration-time initialization, not runtime reset.
   if(!aresetn) begin
     if(touched) reset_fault<=1;
     state<=RX;pos<=0;tx_idx<=0;
   end else if(!fault) begin
     case(state)
     RX:if(s_axis_tvalid && s_axis_tready) begin
       touched<=1;
       words[pos]<=s_axis_tdata;
       if(s_axis_tkeep!=15 || s_axis_tlast!=(pos==35) ||
          (pos==0 && s_axis_tdata!=32'h31534344) ||
          (pos==1 && s_axis_tdata[31:12]!=0) ||
          (pos==3 && s_axis_tdata[31:3]!=0) ||
          (pos>=4 && (s_axis_tdata & 32'h80808080)!=0)) protocol_error<=1;
       if(pos==35) begin state<=CONFIG;pos<=0;matches<=0;cycles<=0;parse<=0;end
       else pos<=pos+1'b1;
     end
     CONFIG:state<=HASH;
     HASH:state<=GAP;
     GAP:if(core_ready && core_idle) begin key_idx<=0;state<=KEYS;end
     KEYS:begin cycles<=cycles+1; if(key_idx==15) state<=META;else key_idx<=key_idx+1'b1;end
     META:begin cycles<=cycles+1;state<=WAIT_RESULT;end
     WAIT_RESULT:begin
       cycles<=cycles+1;
       if(cycles==100000) timeout_error<=1;
       case(parse)
       0:if(nibble[0]) parse<=1;
       1:begin
         final_match<=nibble[0];
         if(nibble[1]) parse<=2;
         else if(nibble[0]) begin state<=TX;tx_idx<=0;parse<=0;end
         else protocol_error<=1;
       end
       2:begin matches[nibble]<=1;parse<=3;end
       3:parse<=4;
       4:parse<=5;
       5:begin parse<=0;if(final_match) begin state<=TX;tx_idx<=0;end end
       default:protocol_error<=1;
       endcase
     end
     TX:if(m_axis_tready) begin
       if(tx_idx==3) begin state<=RX;pos<=0;tx_idx<=0;end
       else tx_idx<=tx_idx+1'b1;
     end
     default:protocol_error<=1;
     endcase
   end
 end
endmodule
