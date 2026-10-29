# AX7020 PS7 board-configuration compatibility check for Vivado 2020.1.
set root [file normalize [file join [file dirname [info script]] ..]]
set work [file join $root build ps7_validate]
set report_dir [file join $root reports]
file mkdir $report_dir

create_project -force ax7020_ps7_validate $work -part xc7z020clg400-2
create_bd_design system

set ps7_0 [create_bd_cell -type ip -vlnv xilinx.com:ip:processing_system7:5.5 ps7_0]
source [file join $root board ps_config_alinx_2023_1.tcl]
set_ps_config ps7_0

# John accelerators use one 100 MHz fabric clock, GP0 for control and HP0 for DMA.
set_property -dict [list \
  CONFIG.PCW_USE_M_AXI_GP0 {1} \
  CONFIG.PCW_USE_M_AXI_GP1 {0} \
  CONFIG.PCW_USE_S_AXI_GP0 {0} \
  CONFIG.PCW_USE_S_AXI_HP0 {1} \
  CONFIG.PCW_USE_S_AXI_HP1 {0} \
  CONFIG.PCW_USE_S_AXI_HP2 {0} \
  CONFIG.PCW_USE_S_AXI_HP3 {0} \
  CONFIG.PCW_FPGA0_PERIPHERAL_FREQMHZ {100} \
  CONFIG.PCW_EN_CLK0_PORT {1} \
  CONFIG.PCW_EN_CLK1_PORT {0} \
  CONFIG.PCW_EN_CLK2_PORT {0} \
  CONFIG.PCW_EN_CLK3_PORT {0} \
  CONFIG.PCW_EN_RST0_PORT {1} \
  CONFIG.PCW_EN_RST1_PORT {0} \
  CONFIG.PCW_EN_RST2_PORT {0} \
  CONFIG.PCW_EN_RST3_PORT {0} \
  CONFIG.PCW_USE_FABRIC_INTERRUPT {0}] $ps7_0

make_bd_intf_pins_external [get_bd_intf_pins ps7_0/DDR]
make_bd_intf_pins_external [get_bd_intf_pins ps7_0/FIXED_IO]
connect_bd_net [get_bd_pins ps7_0/FCLK_CLK0] \
  [get_bd_pins ps7_0/M_AXI_GP0_ACLK] \
  [get_bd_pins ps7_0/S_AXI_HP0_ACLK]
validate_bd_design
save_bd_design
write_bd_tcl -force [file join $report_dir ax7020_ps7_2020_1_rebuild.tcl]

set fp [open [file join $report_dir ps7_validation.txt] w]
puts $fp "vivado=[version -short]"
puts $fp "part=[get_property PART [current_project]]"
foreach prop {PCW_PACKAGE_NAME PCW_CRYSTAL_PERIPHERAL_FREQMHZ PCW_UIPARAM_DDR_PARTNO PCW_UIPARAM_DDR_FREQ_MHZ PCW_ENET0_PERIPHERAL_ENABLE PCW_ENET0_ENET0_IO PCW_ENET0_GRP_MDIO_IO PCW_QSPI_PERIPHERAL_ENABLE PCW_SD0_PERIPHERAL_ENABLE PCW_UART1_PERIPHERAL_ENABLE PCW_UART1_UART1_IO PCW_USE_M_AXI_GP0 PCW_USE_S_AXI_HP0 PCW_FPGA0_PERIPHERAL_FREQMHZ} {
  puts $fp "$prop=[get_property CONFIG.$prop $ps7_0]"
}
close $fp
puts "AX7020_PS7_VALIDATE_COMPLETE"
