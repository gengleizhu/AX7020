`timescale 1ns/1ps
// Request: magic SHS4, tag, then four 416-word unit frames.
// Response: magic SHR4, tag, then four (unit ID + 290-word responses).
module sha512crypt4_axis_top #(
 parameter MIN_ROUNDS=1000
)(
 input aclk,aresetn,input [31:0] s_axis_tdata,input [3:0] s_axis_tkeep,
 input s_axis_tlast,s_axis_tvalid,output s_axis_tready,
 output reg [31:0] m_axis_tdata,output [3:0] m_axis_tkeep,
 output m_axis_tlast,output reg m_axis_tvalid,input m_axis_tready,
 output [31:0] status,output initialized
);
 localparam HEADER=0,TAG=1,FEED=2,OUT_HEADER=3,OUT_TAG=4,OUT_ID=5,GATHER=6;
 reg [2:0] state=HEADER,worker=0;
 reg [8:0] pos=0;
 reg [8:0] outpos=0;
 reg [31:0] tag=0;
 reg protocol_error=0,reset_fault=0,touched=0;
 wire [3:0] ir,ov,ol;
 wire [31:0] od[0:3],ws[0:3];
 wire [3:0] errors,busy;
 wire [3:0] init;
 assign initialized=&init;
 wire fault=protocol_error|reset_fault|(|errors);
 genvar i;
 generate for(i=0;i<4;i=i+1) begin: workers
   assign errors[i]=|ws[i][8:1];
   assign busy[i]=ws[i][0];
   sha512crypt_lane #(.MIN_ROUNDS(MIN_ROUNDS)) lane(
    .aclk(aclk),.aresetn(aresetn),.s_axis_tdata(s_axis_tdata),.s_axis_tkeep(s_axis_tkeep),
    .s_axis_tlast(pos==415),.s_axis_tvalid(s_axis_tvalid && state==FEED && worker==i && !fault),
    .s_axis_tready(ir[i]),.m_axis_tdata(od[i]),.m_axis_tkeep(),.m_axis_tlast(ol[i]),
    .m_axis_tvalid(ov[i]),.m_axis_tready(m_axis_tready && state==GATHER && worker==i && !fault),
    .status(ws[i]),.initialized(init[i]));
 end endgenerate
 assign status={8'hA5,4'b0,errors,4'b0,busy,5'b0,protocol_error,reset_fault,(state!=HEADER)};
 assign s_axis_tready=aresetn && !fault && ((state==HEADER || state==TAG) || (state==FEED && ir[worker]));
 assign m_axis_tkeep=15;
 assign m_axis_tlast=state==GATHER && worker==3 && outpos==289;
 always @* begin
   m_axis_tdata=0;m_axis_tvalid=0;
   if(aresetn && !fault)case(state)
     OUT_HEADER:begin m_axis_tdata=32'h34524853;m_axis_tvalid=1;end
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
       if(s_axis_tkeep!=15 || s_axis_tlast!=(state==FEED && worker==3 && pos==415))protocol_error<=1;
       case(state)
       HEADER:begin if(s_axis_tdata!=32'h34534853)protocol_error<=1;state<=TAG;end
       TAG:begin tag<=s_axis_tdata;worker<=0;pos<=0;state<=FEED;end
       FEED:if(pos==415)begin
         pos<=0;
         if(worker==3)begin worker<=0;state<=OUT_HEADER;end
         else worker<=worker+1'b1;
       end else pos<=pos+1'b1;
       endcase
     end
     if(m_axis_tvalid && m_axis_tready)case(state)
       OUT_HEADER:state<=OUT_TAG;
       OUT_TAG:state<=OUT_ID;
       OUT_ID:begin outpos<=0;state<=GATHER;end
       GATHER:begin
         if(ol[worker]!=(outpos==289))protocol_error<=1;
         if(outpos==289)begin
           if(worker==3)begin worker<=0;state<=HEADER;end
           else begin worker<=worker+1'b1;state<=OUT_ID;end
         end else outpos<=outpos+1'b1;
       end
     endcase
   end
 end
endmodule
