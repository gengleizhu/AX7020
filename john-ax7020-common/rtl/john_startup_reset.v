// Hold resetn low after every PL configuration, then release it synchronously
// after 256 FCLK cycles. This guarantees that AXI peripherals see a reset pulse
// even when PS FCLK_RESET0_N was already deasserted before a bitstream load.
module john_startup_reset (
    input  wire clk,
    output wire resetn
);
    reg [7:0] count = 8'h00;

    always @(posedge clk) begin
        if (!(&count))
            count <= count + 1'b1;
    end

    assign resetn = &count;
endmodule
