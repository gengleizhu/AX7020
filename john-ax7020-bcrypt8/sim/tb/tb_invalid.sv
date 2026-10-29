`timescale 1ns/1ps
// 每个负例独立实例，因为原解析器错误为粘滞状态，未提供软复位。
module tb_invalid;
  reg clk=0;
  always #5 clk=~clk;
  reg [7:0] din[0:8];
  reg [8:0] wr=0;
  wire [8:0] error_checksum,error_len,error_type,error_version;
  genvar g;
  generate for(g=0;g<6;g=g+1) begin: headers
    inpkt_header #(.VERSION(2),.PKT_MAX_LEN(1048576),.PKT_MAX_TYPE(4),.DISABLE_CHECKSUM(0)) h(
      .CLK(clk),.din(din[g]),.wr_en(wr[g]),.pkt_type(),.pkt_id(),.pkt_data(),.pkt_end(),
      .err_pkt_version(error_version[g]),.err_pkt_type(error_type[g]),
      .err_pkt_len(error_len[g]),.err_pkt_checksum(error_checksum[g]));
  end endgenerate
  wire [2:0] config_error,new_config;
  generate for(g=0;g<3;g=g+1) begin: configs
    bcrypt_cmp_config c(.CLK(clk),.din(din[g+6]),.wr_en(wr[g+6]),.full(),
      .error(config_error[g]),.mode_cmp(1'b0),.new_cmp_config(new_config[g]),
      .cmp_config_applied(new_config[g]),.hash_count(),.cmp_wr_addr(),.cmp_wr_en(),
      .cmp_din(),.addr(4'b0),.dout(),.sign_extension_bug());
  end endgenerate
  reg [7:0] packet[0:18];
  reg [31:0] sum;
  integer i,j;
  initial begin #100000; $fatal(1,"NEGATIVE_TIMEOUT"); end
  initial begin
    for(i=0;i<9;i=i+1) din[i]=0;
    repeat(10) @(negedge clk);
    // Header ver2/type1/len1/id0 and payload 0x61, both real checksums.
    for(i=0;i<19;i=i+1) packet[i]=0;
    packet[0]=2;packet[1]=1;packet[4]=1;packet[14]=8'h61;
    sum=~32'h00000103;
    for(i=0;i<4;i=i+1) packet[10+i]=sum[i*8+:8];
    sum=~32'h61;
    for(i=0;i<4;i=i+1) packet[15+i]=sum[i*8+:8];
    for(i=0;i<19;i=i+1) begin
      @(negedge clk); wr[5:0]=6'b111111;
      for(j=0;j<6;j=j+1) din[j]=packet[i];
      if(i==0) din[0]=3;
      if(i==1) din[1]=5;
      if(i==4) din[2]=0;
      if(i==10) din[3]=packet[i]^8'h01;
      if(i==15) din[4]=packet[i]^8'h01;
      // instance5 is the positive control.
    end
    @(negedge clk);wr=0;
    repeat(10) @(negedge clk);
    if(error_version[0]!==1 || error_type[1]!==1 || error_len[2]!==1 ||
       error_checksum[3]!==1 || error_checksum[4]!==1)
      $fatal(1,"header negative case did not trigger");
    if({error_version[5],error_type[5],error_len[5],error_checksum[5]}!==0)
      $fatal(1,"valid control packet rejected");
    // Config subtype invalid, iteration bit20 invalid, magic invalid.
    for(i=0;i<24;i=i+1) begin
      @(negedge clk); wr[8:6]=3'b111;
      for(j=6;j<9;j=j+1) din[j]=0;
      if(i==16) begin din[6]="z";din[7]="a";din[8]="a";end
      if(i==17) begin din[6]=1;din[7]=1;din[8]=1;end
      if(i==19) din[7]=8'h10;
      if(i==23) begin
        // Wait for config handshake before magic.
        wr[8:6]=0; repeat(5) @(negedge clk); wr[8:6]=3'b111;
        din[6]=8'hcc;din[7]=8'hcc;din[8]=8'hcd;
      end
    end
    @(negedge clk);wr=0;
    repeat(10) @(negedge clk);
    if(config_error!==3'b111) $fatal(1,"config negative case did not trigger: %b",config_error);
    $display("STAGE1_PASS tb_invalid");$finish;
  end
endmodule
