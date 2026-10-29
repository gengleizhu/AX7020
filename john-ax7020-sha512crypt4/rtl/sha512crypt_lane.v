`timescale 1ns/1ps
// Sixteen independent SHA512-crypt jobs per original John algorithm unit.
module sha512crypt_lane #(
 parameter MIN_ROUNDS=1000
)(
 input aclk,aresetn,input [31:0] s_axis_tdata,input [3:0] s_axis_tkeep,
 input s_axis_tlast,s_axis_tvalid,output s_axis_tready,
 output [31:0] m_axis_tdata,output [3:0] m_axis_tkeep,
 output m_axis_tlast,m_axis_tvalid,input m_axis_tready,output [31:0] status
);
 localparam RX=0,START=1,SEND=2,WAIT_ALL=4,TX=5;
 reg [2:0] state=RX;
 reg [31:0] words[0:25];
 reg [4:0] pos=0;
 reg [6:0] byte_pos=0;
 reg [8:0] txpos=0;
 reg [3:0] tx_record=0; reg [4:0] tx_word=0;
 reg [4:0] jobs=0,received=0;
 reg touched=0,reset_fault=0,protocol_error=0,timeout_error=0;
 reg [31:0] elapsed=0;
 reg [575:0] results[0:15];
 reg [575:0] shift=0;
 reg [8:0] bitpos=0;
 reg [1:0] collect=0;
 wire ready,afull,empty;
 wire [1:0] unit_out;
 wire fault=reset_fault|protocol_error|timeout_error;
 wire unit_wr=aresetn && !fault && !afull &&
       ((state==START && ready) || state==SEND);
 wire [7:0] unit_in=state==SEND?words[byte_pos[6:2]][8*byte_pos[1:0]+:8]:8'b0;
 wire rd=aresetn && !fault && collect==0 && received<16 && !empty;
 sha512unit #(.N_CORES(4),.UNIT_CONF(64'b0)) unit_i(
  // John SHA512's input FIFO consumes the ctrl-marked last DATA byte.
  // A separate footer would leave one byte in its 8-byte assembly register.
  .CLK(aclk),.unit_in(unit_in),.unit_in_ctrl(state==START || (state==SEND && byte_pos==103)),
  .unit_in_wr_en(unit_wr),.unit_in_afull(afull),.unit_in_ready(ready),
  .dout(unit_out),.rd_en(rd),.empty(empty));
 assign s_axis_tready=aresetn && !fault && state==RX;
 assign m_axis_tvalid=aresetn && !fault && state==TX;
 assign m_axis_tlast=txpos==289;
 assign m_axis_tkeep=15;
 assign m_axis_tdata=txpos==0?32'h3453484a:txpos==1?elapsed:
      results[tx_record][32*tx_word+:32];
 assign status={8'h52,15'b0,timeout_error,5'b0,protocol_error,reset_fault,(state!=RX || jobs!=0 || pos!=0)};
 always @(posedge aclk)begin
  if(!aresetn)begin
    if(touched)reset_fault<=1;
    state<=RX;pos<=0;jobs<=0;received<=0;collect<=0;
  end else if(!fault)begin
    if((state!=RX || jobs!=0 || pos!=0) && state!=TX && received<16)begin
      elapsed<=elapsed+1;
      if(elapsed==100000000)timeout_error<=1;
    end
    case(state)
    RX:if(s_axis_tvalid && s_axis_tready)begin
      touched<=1;
      if(jobs==0 && pos==0)elapsed<=0;
      words[pos]<=s_axis_tdata;
      if(s_axis_tkeep!=15 || s_axis_tlast!=(jobs==15 && pos==25) ||
       (pos==0 && (s_axis_tdata<MIN_ROUNDS || s_axis_tdata>999999999)) ||
       (pos==1 && (s_axis_tdata==0 || s_axis_tdata>16)) ||
       (pos==8 && s_axis_tdata>64) || (pos==9 && s_axis_tdata!=0))protocol_error<=1;
      if(pos==25)begin pos<=0;state<=START;end else pos<=pos+1'b1;
    end
    START:if(unit_wr)begin byte_pos<=0;state<=SEND;end
    SEND:if(unit_wr)begin
      if(byte_pos==103)begin
        jobs<=jobs+1'b1;
        if(jobs==15)state<=WAIT_ALL;else state<=RX;
      end else byte_pos<=byte_pos+1'b1;
    end
    WAIT_ALL:if(received==16)begin txpos<=0;tx_record<=0;tx_word<=0;state<=TX;end
    TX:if(m_axis_tready)begin
      if(txpos>=2)begin
        if(tx_word==17)begin tx_word<=0;tx_record<=tx_record+1'b1;end
        else tx_word<=tx_word+1'b1;
      end
      if(txpos==289)begin state<=RX;jobs<=0;received<=0;elapsed<=0;end
      else txpos<=txpos+1'b1;
    end
    endcase
    case(collect)
    0:if(rd)collect<=1;
    1:if(unit_out==3)begin collect<=2;bitpos<=0;end
    2:begin
      shift[2*bitpos+:2]<=unit_out;
      if(bitpos==287)collect<=3;else bitpos<=bitpos+1'b1;
    end
    3:begin
      if(unit_out!=0)protocol_error<=1;
      results[received]<=shift;received<=received+1'b1;collect<=0;
    end
    endcase
  end
 end
endmodule
