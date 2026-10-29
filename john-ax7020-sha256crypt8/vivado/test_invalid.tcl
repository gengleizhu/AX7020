set root [file normalize [file join [file dirname [info script]] ..]]
create_project -force sha256crypt8_invalid $root/build/invalid -part xc7z020clg400-1
source $root/vivado/sources.tcl
add_files -fileset sim_1 $root/sim/tb_invalid.sv
set_property top tb_invalid [get_filesets sim_1]
set_property verilog_define SIMULATION [get_filesets sim_1]
set_property xsim.simulate.log_all_signals false [get_filesets sim_1]
set_property xsim.simulate.runtime all [get_filesets sim_1]
launch_simulation
close_sim
set f [open $root/build/invalid/sha256crypt8_invalid.sim/sim_1/behav/xsim/simulate.log r]
set result [read $f];close $f
if {![string match *INVALID_TEST_PASS* $result] || [string match *Fatal:* $result]} {error "Invalid-input test FAILED"}
