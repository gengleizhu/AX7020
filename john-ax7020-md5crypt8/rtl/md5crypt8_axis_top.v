`timescale 1ns/1ps
// One DMA superbatch: magic DMS8, transaction ID, eight 312-word unit frames.
// One response: magic DMR8, transaction ID, eight (unit ID + 74 result words).
// Deterministic dispatch and ordered gather. Each worker buffers its own results.
module md5crypt8_axis_top(
 input aclk,aresetn,input [31:0] s_axis_tdata,input [3:0] s_axis_tkeep,
 input s_axis_tlast,s_axis_tvalid,output s_axis_tready,
 output reg [31:0] m_axis_tdata,output [3:0] m_axis_tkeep,
 output m_axis_tlast,output reg m_axis_tvalid,input m_axis_tready,
 output [31:0] status
);
 localparam HEADER=0,TAG=1,FEED=2,OUT_HEADER=3,OUT_TAG=4,OUT_ID=5,GATHER=6;
 reg [2:0] state=HEADER,worker=0;
 reg [8:0] pos=0;
 reg [6:0] outpos=0;
 reg [31:0] tag=0;
 reg protocol_error=0,reset_fault=0,touched=0;
 wire [7:0] ir,ov,ol;
 wire [31:0] od[0:7],ws[0:7];
 wire [7:0] errors,busy;
 wire fault=protocol_error|reset_fault|(|errors);
 genvar i;
 generate for(i=0;i<8;i=i+1) begin: workers
   assign errors[i]=|ws[i][8:1];
   assign busy[i]=ws[i][0];
   md5crypt_lane lane(
    .aclk(aclk),.aresetn(aresetn),.s_axis_tdata(s_axis_tdata),.s_axis_tkeep(s_axis_tkeep),
    .s_axis_tlast(pos==311),.s_axis_tvalid(s_axis_tvalid && state==FEED && worker==i && !fault),
    .s_axis_tready(ir[i]),.m_axis_tdata(od[i]),.m_axis_tkeep(),.m_axis_tlast(ol[i]),
    .m_axis_tvalid(ov[i]),.m_axis_tready(m_axis_tready && state==GATHER && worker==i && !fault),
    .status(ws[i]));
 end endgenerate
 assign status={8'hA8,errors,busy,5'b0,protocol_error,reset_fault,(state!=HEADER)};
 assign s_axis_tready=aresetn && !fault && ((state==HEADER || state==TAG) || (state==FEED && ir[worker]));
 assign m_axis_tkeep=15;
 assign m_axis_tlast=state==GATHER && worker==7 && outpos==73;
 always @* begin
   m_axis_tdata=0;m_axis_tvalid=0;
   if(aresetn && !fault)case(state)
     OUT_HEADER:begin m_axis_tdata=32'h38524d44;m_axis_tvalid=1;end
     OUT_TAG:begin m_axis_tdata=tag;m_axis_tvalid=1;end
     OUT_ID:begin m_axis_tdata={29'b0,worker};m_axis_tvalid=1;end
     GATHER:begin m_axis_tdata=od[worker];m_axis_tvalid=ov[worker];end
     default:begin end
   endcase
 end
 always @(posedge aclk)begin
   if(!aresetn)begin
     if(touched)reset_fault<=1;
     state<=HEADER;pos<=0;worker<=0;outpos<=0;
   end else if(!fault)begin
     if(s_axis_tvalid && s_axis_tready)begin
       touched<=1;
       if(s_axis_tkeep!=15 || s_axis_tlast!=(state==FEED && worker==7 && pos==311))protocol_error<=1;
       case(state)
       HEADER:begin if(s_axis_tdata!=32'h38534d44)protocol_error<=1;state<=TAG;end
       TAG:begin tag<=s_axis_tdata;worker<=0;pos<=0;state<=FEED;end
       FEED:if(pos==311)begin
         pos<=0;
         if(worker==7)begin worker<=0;state<=OUT_HEADER;end
         else worker<=worker+1'b1;
       end else pos<=pos+1'b1;
       endcase
     end
     if(m_axis_tvalid && m_axis_tready)case(state)
       OUT_HEADER:state<=OUT_TAG;
       OUT_TAG:state<=OUT_ID;
       OUT_ID:begin outpos<=0;state<=GATHER;end
       GATHER:begin
         if(ol[worker]!=(outpos==73))protocol_error<=1;
         if(outpos==73)begin
           if(worker==7)begin worker<=0;state<=HEADER;end
           else begin worker<=worker+1'b1;state<=OUT_ID;end
         end else outpos<=outpos+1'b1;
       end
     endcase
   end
 end
endmodule
