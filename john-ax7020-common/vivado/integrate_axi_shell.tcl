# Called after DMA/interconnect creation and before native stream export.
set common [file normalize [file join $root .. john-ax7020-common]]
add_files -norecurse $common/rtl/john_axi_shell.sv
add_files -norecurse $common/rtl/john_axi_shell_bd.v
update_compile_order -fileset sources_1
set shell [create_bd_cell -type module -reference john_axi_shell_bd unified]
set_property CONFIG.ALGORITHM $algorithm_id $shell
set result_slice [create_bd_cell -type ip -vlnv xilinx.com:ip:axis_register_slice:1.1 result_slice]
set_property -dict [list CONFIG.TDATA_NUM_BYTES {4} CONFIG.HAS_TKEEP {1} CONFIG.HAS_TLAST {1} CONFIG.REG_CONFIG {8}] $result_slice
connect_bd_net [get_bd_pins ps7_0/FCLK_CLK0] [get_bd_pins result_slice/aclk]
connect_bd_net [get_bd_pins reset/peripheral_aresetn] [get_bd_pins result_slice/aresetn]
connect_bd_intf_net [get_bd_intf_pins result_slice/M_AXIS] [get_bd_intf_pins unified/NATIVE_RX]
set_property CONFIG.NUM_MI 3 $control
connect_bd_net [get_bd_pins ps7_0/FCLK_CLK0] [get_bd_pins unified/aclk] [get_bd_pins control/M02_ACLK]
connect_bd_net [get_bd_pins reset/peripheral_aresetn] [get_bd_pins unified/aresetn] [get_bd_pins control/M02_ARESETN]
connect_bd_intf_net [get_bd_intf_pins control/M02_AXI] [get_bd_intf_pins unified/S_AXI]
connect_bd_intf_net [get_bd_intf_pins dma/M_AXIS_MM2S] [get_bd_intf_pins unified/S_AXIS]
connect_bd_intf_net [get_bd_intf_pins unified/M_AXIS] [get_bd_intf_pins dma/S_AXIS_S2MM]
create_bd_port -dir I compute_initialized
connect_bd_net [get_bd_ports compute_initialized] [get_bd_pins unified/native_initialized]
# Explicitly fixed addresses; no auto allocation dependence across algorithms.
set shell_segment [get_bd_addr_segs -quiet unified/S_AXI/reg0]
if {[llength $shell_segment] != 1} {error "Expected exactly one unified AXI register segment"}
assign_bd_address -offset 0x43C00000 -range 0x00010000 -target_address_space [get_bd_addr_spaces ps7_0/Data] $shell_segment -force
