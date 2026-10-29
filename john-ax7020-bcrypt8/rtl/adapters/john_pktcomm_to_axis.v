// 按John头的24bit Payload长度生成TLAST，而非根据Core empty。
// 当前mode_cmp=0只产生48字节D3包；其它长度/类型故障停机，禁止误标完成。
module john_pktcomm_to_axis(
 input clk,input resetn,input [15:0] data,input empty,output read_en,
 output reg [31:0] m_axis_tdata=0,output [3:0] m_axis_tkeep,
 output reg m_axis_tlast=0,output reg m_axis_tvalid=0,input m_axis_tready,
 output reg error=0);
 reg half=0;
 reg [15:0] low=0;
 reg [23:0] word_index=0,total_words=0;
 reg [15:0] length_low=0;
 assign m_axis_tkeep=4'hf;
 assign read_en=resetn && !error && !empty && (!m_axis_tvalid || m_axis_tready);
 always @(posedge clk) begin
   if(!resetn) begin
     half<=0; word_index<=0; total_words<=0; m_axis_tvalid<=0; m_axis_tlast<=0; error<=0;
   end else begin
     if(m_axis_tvalid && m_axis_tready) m_axis_tvalid<=0;
     if(read_en) begin
       if(word_index==0 && data!=16'hd302) error<=1;
       if(word_index==2) length_low<=data;
       if(word_index==3) begin
         total_words<=({data[7:0],length_low}+24'd18)>>1;
         if({data[7:0],length_low}!=30) error<=1;
       end
       if(!half) begin low<=data; half<=1; end
       else begin
         m_axis_tdata<={data,low}; m_axis_tvalid<=1;
         m_axis_tlast<=word_index==total_words-1'b1; half<=0;
       end
       if(word_index==total_words-1'b1 && word_index>3) word_index<=0;
       else word_index<=word_index+1'b1;
     end
   end
 end
endmodule
