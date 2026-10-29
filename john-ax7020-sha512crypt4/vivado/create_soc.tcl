# AX7020 PS/DDR/DMA + four original John SHA512crypt units (16 SHA-512 cores), Vivado 2020.1.
set root [file normalize [file join [file dirname [info script]] ..]]
set work $root/build/soc
set out $root/reports/soc
file mkdir $out
create_project -force john_ax7020_sha512crypt4 $work -part xc7z020clg400-2
set_param general.maxThreads 4
source $root/vivado/sources.tcl
create_bd_design system
# AX7020板级PS7参数来自ALINX官方DMA例程，并已由Vivado 2020.1验证。
set ps7_0 [create_bd_cell -type ip -vlnv xilinx.com:ip:processing_system7:5.5 ps7_0]
source $root/board/ps_config_ax7020.tcl
set_ps_config ps7_0
set_property -dict [list \
 CONFIG.PCW_USE_M_AXI_GP0 {1} CONFIG.PCW_USE_M_AXI_GP1 {0} \
 CONFIG.PCW_USE_S_AXI_GP0 {0} CONFIG.PCW_USE_S_AXI_HP0 {1} CONFIG.PCW_USE_S_AXI_HP2 {0} \
 CONFIG.PCW_FPGA0_PERIPHERAL_FREQMHZ {100} \
 CONFIG.PCW_EN_CLK1_PORT {0} CONFIG.PCW_EN_CLK2_PORT {0} CONFIG.PCW_EN_CLK3_PORT {0} \
 CONFIG.PCW_EN_RST1_PORT {0} CONFIG.PCW_EN_RST2_PORT {0} CONFIG.PCW_EN_RST3_PORT {0} \
 CONFIG.PCW_GPIO_EMIO_GPIO_ENABLE {0} CONFIG.PCW_I2C1_PERIPHERAL_ENABLE {0} \
 CONFIG.PCW_USE_FABRIC_INTERRUPT {0}] $ps7_0
make_bd_intf_pins_external [get_bd_intf_pins ps7_0/DDR]
make_bd_intf_pins_external [get_bd_intf_pins ps7_0/FIXED_IO]
set dma [create_bd_cell -type ip -vlnv xilinx.com:ip:axi_dma:7.1 dma]
set_property -dict [list CONFIG.c_include_sg {0} CONFIG.c_sg_length_width {23} \
 CONFIG.c_m_axi_mm2s_data_width {32} CONFIG.c_m_axi_s2mm_data_width {32} \
 CONFIG.c_m_axis_mm2s_tdata_width {32} \
 CONFIG.c_include_mm2s_dre {1} CONFIG.c_include_s2mm_dre {1}] $dma
set control [create_bd_cell -type ip -vlnv xilinx.com:ip:axi_interconnect:2.1 control]
set_property CONFIG.NUM_MI 2 $control
set memory [create_bd_cell -type ip -vlnv xilinx.com:ip:axi_interconnect:2.1 memory]
set_property -dict [list CONFIG.NUM_SI 2 CONFIG.NUM_MI 1] $memory
set gpio [create_bd_cell -type ip -vlnv xilinx.com:ip:axi_gpio:2.0 status]
set_property -dict [list CONFIG.C_GPIO_WIDTH 32 CONFIG.C_ALL_INPUTS 1] $gpio
set rst [create_bd_cell -type ip -vlnv xilinx.com:ip:proc_sys_reset:5.0 reset]
# C_EXT_RESET_HIGH由FCLK_RESET0_N接口极性传播，属于只读参数。
set one [create_bd_cell -type ip -vlnv xilinx.com:ip:xlconstant:1.1 one]
set_property CONFIG.CONST_VAL 1 $one
set zero [create_bd_cell -type ip -vlnv xilinx.com:ip:xlconstant:1.1 zero]
set_property CONFIG.CONST_VAL 0 $zero
connect_bd_net [get_bd_pins one/dout] [get_bd_pins reset/dcm_locked]
connect_bd_net [get_bd_pins zero/dout] [get_bd_pins reset/aux_reset_in] [get_bd_pins reset/mb_debug_sys_rst]
connect_bd_net [get_bd_pins ps7_0/FCLK_RESET0_N] [get_bd_pins reset/ext_reset_in]
foreach pin {ps7_0/M_AXI_GP0_ACLK ps7_0/S_AXI_HP0_ACLK dma/s_axi_lite_aclk dma/m_axi_mm2s_aclk dma/m_axi_s2mm_aclk status/s_axi_aclk reset/slowest_sync_clk control/ACLK control/S00_ACLK control/M00_ACLK control/M01_ACLK memory/ACLK memory/S00_ACLK memory/S01_ACLK memory/M00_ACLK} {
    connect_bd_net [get_bd_pins ps7_0/FCLK_CLK0] [get_bd_pins $pin]
}
foreach pin {dma/axi_resetn status/s_axi_aresetn control/S00_ARESETN control/M00_ARESETN control/M01_ARESETN memory/S00_ARESETN memory/S01_ARESETN memory/M00_ARESETN} {
    connect_bd_net [get_bd_pins reset/peripheral_aresetn] [get_bd_pins $pin]
}
connect_bd_net [get_bd_pins reset/interconnect_aresetn] [get_bd_pins control/ARESETN] [get_bd_pins memory/ARESETN]
connect_bd_intf_net [get_bd_intf_pins ps7_0/M_AXI_GP0] [get_bd_intf_pins control/S00_AXI]
connect_bd_intf_net [get_bd_intf_pins control/M00_AXI] [get_bd_intf_pins dma/S_AXI_LITE]
connect_bd_intf_net [get_bd_intf_pins control/M01_AXI] [get_bd_intf_pins status/S_AXI]
connect_bd_intf_net [get_bd_intf_pins dma/M_AXI_MM2S] [get_bd_intf_pins memory/S00_AXI]
connect_bd_intf_net [get_bd_intf_pins dma/M_AXI_S2MM] [get_bd_intf_pins memory/S01_AXI]
connect_bd_intf_net [get_bd_intf_pins memory/M00_AXI] [get_bd_intf_pins ps7_0/S_AXI_HP0]
make_bd_intf_pins_external [get_bd_intf_pins dma/M_AXIS_MM2S]
set_property name to_pl [get_bd_intf_ports M_AXIS_MM2S_0]
make_bd_intf_pins_external [get_bd_intf_pins dma/S_AXIS_S2MM]
set_property name from_pl [get_bd_intf_ports S_AXIS_S2MM_0]
set_property CONFIG.FREQ_HZ 100000000 [get_bd_intf_ports from_pl]
create_bd_port -dir O -type clk clk100
set_property CONFIG.ASSOCIATED_BUSIF {to_pl:from_pl} [get_bd_ports clk100]
set_property CONFIG.FREQ_HZ 100000000 [get_bd_ports clk100]
connect_bd_net [get_bd_pins ps7_0/FCLK_CLK0] [get_bd_ports clk100]
create_bd_port -dir O -type rst resetn
set_property CONFIG.POLARITY ACTIVE_LOW [get_bd_ports resetn]
connect_bd_net [get_bd_pins reset/peripheral_aresetn] [get_bd_ports resetn]
create_bd_port -dir I -from 31 -to 0 compute_status
connect_bd_net [get_bd_ports compute_status] [get_bd_pins status/gpio_io_i]
assign_bd_address
validate_bd_design
if {[get_property CONFIG.C_EXT_RESET_HIGH $rst] != 0} {error "PS reset polarity mismatch"}
save_bd_design
write_bd_tcl -force $out/system_rebuild.tcl
set bd [get_files */system.bd]
generate_target all $bd
set wrapper [make_wrapper -files $bd -top]
add_files -norecurse $wrapper
set python $root/.venv/Scripts/python.exe
if {[info exists env(JOHN_PYTHON)]} {set python $env(JOHN_PYTHON)}
if {[info exists env(PYTHONHOME)]} {unset env(PYTHONHOME)}
if {[info exists env(PYTHONPATH)]} {unset env(PYTHONPATH)}
puts [exec $python $root/scripts/wrap_soc.py [lindex $wrapper 0] $work/john_soc_top.v]
add_files -norecurse $work/john_soc_top.v
set_property top john_soc_top [current_fileset]
set_property STEPS.SYNTH_DESIGN.ARGS.FLATTEN_HIERARCHY none [get_runs synth_1]
# 关闭分层OOC IP运行，统一综合包含初始化ROM的完整设计。
set_property synth_checkpoint_mode None $bd
if {[info exists env(JOHN_BUILD_MODE)] && $env(JOHN_BUILD_MODE) eq "project"} {
    puts "AX7020_PROJECT_CREATED xpr=$work/john_ax7020_sha512crypt4.xpr"
    exit 0
}
launch_runs synth_1 -jobs 4
wait_on_run synth_1
if {[get_property PROGRESS [get_runs synth_1]]!="100%"} {error "SoC synthesis failed"}
open_run synth_1
set actual [get_cells -hier -filter {ORIG_REF_NAME == sha512unit || REF_NAME == sha512unit}]
if {[llength $actual]!=4 || [llength [get_cells -hier -filter {IS_BLACKBOX == 1}]]} {error "SoC real core check failed"}
set cores [get_cells -hier -filter {ORIG_REF_NAME == core || REF_NAME == core}]
if {[llength $cores]!=16} {error "Expected 16 real SHA512 cores"}
report_utilization -hierarchical -file $out/synth_hierarchy.rpt
report_utilization -file $out/synth_utilization.rpt
close_design
launch_runs impl_1 -to_step write_bitstream -jobs 4
wait_on_run impl_1
if {[get_property PROGRESS [get_runs impl_1]]!="100%"} {error "SoC implementation failed"}
open_run impl_1
report_utilization -file $out/routed_utilization.rpt
report_timing_summary -delay_type min_max -max_paths 20 -report_unconstrained -file $out/routed_timing.rpt
report_route_status -file $out/route_status.rpt
report_drc -file $out/drc.rpt
report_methodology -file $out/methodology.rpt
set slack [get_property SLACK [lindex [get_timing_paths -max_paths 1] 0]]
set hold_slack [get_property SLACK [lindex [get_timing_paths -delay_type min -max_paths 1] 0]]
set fp [open $out/status.txt w]
puts $fp "units=4 sha512cores=16 thread_slots=64 blackboxes=0 scope=full_PS_DMA_PL period_ns=10 wns_ns=$slack whs_ns=$hold_slack"
puts $fp "estimated_fmax_mhz=[expr {1000.0/(10.0-$slack)}]"
puts $fp "board=AX7020 part=xc7z020clg400-2 vivado=[version -short]"
puts $fp "bitstream_generated=true xsa_generated=true board_tested=false"
close $fp
if {$slack < 0} {error "Routed setup timing failed: $slack"}
if {$hold_slack < 0} {error "Routed hold timing failed: $hold_slack"}
file mkdir $root/deliverables
file copy -force $work/john_ax7020_sha512crypt4.runs/impl_1/john_soc_top.bit $root/deliverables/john_ax7020_sha512crypt4.bit
foreach hwh [glob -nocomplain $work/john_ax7020_sha512crypt4.srcs/sources_1/bd/system/hw_handoff/*.hwh] {
    file copy -force $hwh $root/deliverables/john_ax7020_sha512crypt4.hwh
}
write_hw_platform -fixed -include_bit -force $root/deliverables/john_ax7020_sha512crypt4.xsa
puts "SHA512CRYPT_SOC_COMPLETE wns_ns=$slack"
