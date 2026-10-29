`timescale 1ns / 1ps

// Vivado 2018.3 replacement for the original ISE asymmetric-memory
// inference template. The public interfaces and one-cycle synchronous read
// behavior are unchanged; XPM supplies the supported UltraScale+ mapping.

module asymm_bram_min_wr #(
    parameter minWIDTH = 8,
    parameter RATIO = 4,
    parameter maxDEPTH = 512,
    parameter INIT = 0
) (
    input  wire                              wr_clk,
    input  wire [minWIDTH-1:0]               din,
    input  wire                              wr_en,
    input  wire [$clog2(maxDEPTH*RATIO)-1:0] wr_addr,
    input  wire                              rd_clk,
    output wire [minWIDTH*RATIO-1:0]         dout,
    input  wire                              rd_en,
    input  wire [$clog2(maxDEPTH)-1:0]       rd_addr
);

    xpm_memory_sdpram #(
        .ADDR_WIDTH_A($clog2(maxDEPTH*RATIO)),
        .ADDR_WIDTH_B($clog2(maxDEPTH)),
        .AUTO_SLEEP_TIME(0),
        .BYTE_WRITE_WIDTH_A(minWIDTH),
        .CLOCKING_MODE("independent_clock"),
        .ECC_MODE("no_ecc"),
        .MEMORY_INIT_FILE("none"),
        .MEMORY_INIT_PARAM("0"),
        .MEMORY_OPTIMIZATION("true"),
        .MEMORY_PRIMITIVE("block"),
        .MEMORY_SIZE(minWIDTH*RATIO*maxDEPTH),
        .MESSAGE_CONTROL(0),
        .READ_DATA_WIDTH_B(minWIDTH*RATIO),
        .READ_LATENCY_B(1),
        .READ_RESET_VALUE_B("0"),
        .USE_EMBEDDED_CONSTRAINT(0),
        .USE_MEM_INIT(1),
        .WAKEUP_TIME("disable_sleep"),
        .WRITE_DATA_WIDTH_A(minWIDTH),
        .WRITE_MODE_B("no_change")
    ) mem (
        .dbiterrb(), .doutb(dout), .sbiterrb(),
        .addra(wr_addr), .addrb(rd_addr),
        .clka(wr_clk), .clkb(rd_clk), .dina(din),
        .ena(wr_en), .enb(rd_en),
        .injectdbiterra(1'b0), .injectsbiterra(1'b0),
        .regceb(1'b1), .rstb(1'b0), .sleep(1'b0), .wea(wr_en)
    );

endmodule

module asymm_bram_min_rd #(
    parameter minWIDTH = 8,
    parameter RATIO = 4,
    parameter maxDEPTH = 512,
    parameter INIT = 0
) (
    input  wire                              wr_clk,
    input  wire [minWIDTH*RATIO-1:0]         din,
    input  wire                              wr_en,
    input  wire [$clog2(maxDEPTH)-1:0]       wr_addr,
    input  wire                              rd_clk,
    output wire [minWIDTH-1:0]               dout,
    input  wire                              rd_en,
    input  wire [$clog2(maxDEPTH*RATIO)-1:0] rd_addr
);

    xpm_memory_sdpram #(
        .ADDR_WIDTH_A($clog2(maxDEPTH)),
        .ADDR_WIDTH_B($clog2(maxDEPTH*RATIO)),
        .AUTO_SLEEP_TIME(0),
        .BYTE_WRITE_WIDTH_A(minWIDTH*RATIO),
        .CLOCKING_MODE("independent_clock"),
        .ECC_MODE("no_ecc"),
        .MEMORY_INIT_FILE("none"),
        .MEMORY_INIT_PARAM("0"),
        .MEMORY_OPTIMIZATION("true"),
        .MEMORY_PRIMITIVE("block"),
        .MEMORY_SIZE(minWIDTH*RATIO*maxDEPTH),
        .MESSAGE_CONTROL(0),
        .READ_DATA_WIDTH_B(minWIDTH),
        .READ_LATENCY_B(1),
        .READ_RESET_VALUE_B("0"),
        .USE_EMBEDDED_CONSTRAINT(0),
        .USE_MEM_INIT(1),
        .WAKEUP_TIME("disable_sleep"),
        .WRITE_DATA_WIDTH_A(minWIDTH*RATIO),
        .WRITE_MODE_B("no_change")
    ) mem (
        .dbiterrb(), .doutb(dout), .sbiterrb(),
        .addra(wr_addr), .addrb(rd_addr),
        .clka(wr_clk), .clkb(rd_clk), .dina(din),
        .ena(wr_en), .enb(rd_en),
        .injectdbiterra(1'b0), .injectsbiterra(1'b0),
        .regceb(1'b1), .rstb(1'b0), .sleep(1'b0), .wea(wr_en)
    );

endmodule

