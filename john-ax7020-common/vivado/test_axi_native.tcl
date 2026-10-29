set common [file normalize [file join [file dirname [info script]] ..]]
set alg [lindex $argv 0]
if {$alg ni {3 4 5}} {error "Usage: -tclargs 3|4|5"}
set names [dict create 3 md5crypt8 4 sha256crypt8 5 sha512crypt4]
set root [file normalize [file join $common .. john-ax7020-[dict get $names $alg]]]
set work $common/build/native_$alg
create_project -force axi_native $work -part xc7z020clg400-2
source $root/vivado/sources.tcl
create_ip -name axis_register_slice -vendor xilinx.com -library ip -version 1.1 -module_name john_result_slice
set_property -dict [list CONFIG.TDATA_NUM_BYTES {4} CONFIG.HAS_TKEEP {1} CONFIG.HAS_TLAST {1} CONFIG.REG_CONFIG {8}] [get_ips john_result_slice]
generate_target all [get_ips john_result_slice]
add_files $common/rtl/john_axi_shell.sv
add_files -fileset sim_1 [list $common/sim/tb_axi_native.sv $root/sim/input.mem $root/sim/expected.mem]
set_property top tb_axi_native [get_filesets sim_1]
set_property generic ALG=$alg [get_filesets sim_1]
set_property verilog_define SIMULATION [get_filesets sim_1]
set_property xsim.elaborate.xelab.more_options { -O0} [get_filesets sim_1]
set_property xsim.simulate.runtime all [get_filesets sim_1]
launch_simulation
close_sim
set f [open $work/axi_native.sim/sim_1/behav/xsim/simulate.log r]
set result [read $f];close $f
if {![string match "*AXI_NATIVE_PASS ALG=$alg*" $result] || [string match *Fatal:* $result]} {error "Native AXI integration failed"}
