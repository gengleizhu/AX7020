set root [file normalize [file join [file dirname [info script]] ..]]
create_project -force axi_shell_test $root/build/axi_shell_test -part xc7z020clg400-2
create_ip -name axis_register_slice -vendor xilinx.com -library ip -version 1.1 -module_name john_result_slice
set_property -dict [list CONFIG.TDATA_NUM_BYTES {4} CONFIG.HAS_TKEEP {1} CONFIG.HAS_TLAST {1} CONFIG.REG_CONFIG {8}] [get_ips john_result_slice]
generate_target all [get_ips john_result_slice]
add_files $root/rtl/john_axi_shell.sv
add_files -fileset sim_1 $root/sim/tb_axi_shell.sv
set_property top tb_axi_shell [get_filesets sim_1]
set_property xsim.simulate.runtime all [get_filesets sim_1]
foreach alg {1 2 3 4 5} {
 set_property generic ALG=$alg [get_filesets sim_1]
 launch_simulation
 close_sim
 set f [open $root/build/axi_shell_test/axi_shell_test.sim/sim_1/behav/xsim/simulate.log r]
 set result [read $f];close $f
 if {![string match "*AXI_SHELL_PASS ALG=$alg*" $result] || [string match *Fatal:* $result]} {error "AXI shell test failed: algorithm $alg"}
}
