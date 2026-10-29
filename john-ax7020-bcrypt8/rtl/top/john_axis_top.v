// 保留原解析器/arbiter/wrapper/proxy/core；一个Proxy带N个真实计算Core。
// resetn仅用于启动和AXIS适配器。接收任务后再次复位会锁死会话，必须重配置PL。
module john_axis_top #(parameter CORES=1)(
 (* X_INTERFACE_INFO="xilinx.com:signal:clock:1.0 aclk CLK",
    X_INTERFACE_PARAMETER="ASSOCIATED_BUSIF s_axis:m_axis, ASSOCIATED_RESET aresetn, FREQ_HZ 100000000" *)
 input aclk,
 (* X_INTERFACE_INFO="xilinx.com:signal:reset:1.0 aresetn RST",
    X_INTERFACE_PARAMETER="POLARITY ACTIVE_LOW" *)
 input aresetn,
 input [31:0] s_axis_tdata,input [3:0] s_axis_tkeep,input s_axis_tlast,input s_axis_tvalid,
 output s_axis_tready,
 output [31:0] m_axis_tdata,output [3:0] m_axis_tkeep,output m_axis_tlast,output m_axis_tvalid,
 input m_axis_tready,output [31:0] status,output initialized);
 wire [7:0] din,core_din,app_status,pkt_status;
 wire valid,blocked,in_error,out_error,error_r;
 wire [1:0] ctrl;
 wire cw,ci,cc,cr,ce,cd,empty,rd;
 wire [15:0] dout;
 reg started=0,reset_fault=0;
 always @(posedge aclk) begin
   if(s_axis_tvalid && s_axis_tready) started<=1;
   if(!aresetn && started) reset_fault<=1;
 end
 assign initialized=ci;
 wire run_enable=aresetn && !reset_fault;
 assign status={8'hbc,4'b0,reset_fault,out_error,in_error,error_r,app_status,pkt_status};
 axis_to_john_pktcomm input_adapter(aclk,run_enable,s_axis_tdata,s_axis_tkeep,
   s_axis_tlast,s_axis_tvalid,s_axis_tready,din,valid,!blocked,in_error);
 john_pktcomm_to_axis output_adapter(aclk,run_enable,dout,empty,rd,
   m_axis_tdata,m_axis_tkeep,m_axis_tlast,m_axis_tvalid,m_axis_tready,out_error);
 john_stream_engine #(.NUM_CORES(1),.SIMULATION(0)) engine(
   .CORE_CLK(aclk),.IFCLK(aclk),.hs_input_din(din),.hs_input_wr_en(valid),
   .hs_input_almost_full(blocked),.hs_input_prog_full(),
   .output_dout(dout),.output_rd_en(rd),.output_empty(empty),
   .output_limit(),.output_limit_not_done(),.output_mode_limit(1'b0),.reg_output_limit(1'b0),
   .idle(),.error_r(error_r),.app_mode(8'h40),.app_status(app_status),.pkt_comm_status(pkt_status),
   .debug2(),.debug3(),.mode_cmp(1'b0),.core_din(core_din),.core_ctrl(ctrl),.core_wr_en(cw),
   .core_init_ready(ci),.core_crypt_ready(cc),.core_rd_en(cr),.core_empty(ce),.core_dout(cd));
 bcrypt_wrapper #(.NUM_PROXIES(1),.PROXY_CONF(32'h100+CORES)) wrapper(
   .CLK(aclk),.mode_cmp(1'b0),.din(core_din),.ctrl(ctrl),.wr_en(cw),
   .init_ready(ci),.crypt_ready(cc),.rd_en(cr),.empty(ce),.dout(cd));
endmodule
