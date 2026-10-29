set root [file normalize [file join [file dirname [info script]] ..]]
create_project -force sha512crypt_known $root/build/known -part xc7z020clg400-1
source $root/vivado/sources.tcl
add_files -fileset sim_1 [list $root/sim/tb_known.sv $root/sim/known_input.mem $root/sim/known_expected.mem]
set_property top tb_known [get_filesets sim_1]
set_property verilog_define SIMULATION [get_filesets sim_1]
set_property xsim.simulate.log_all_signals false [get_filesets sim_1]
set_property xsim.simulate.runtime all [get_filesets sim_1]
launch_simulation
close_sim
set f [open $root/build/known/sha512crypt_known.sim/sim_1/behav/xsim/simulate.log r]
set result [read $f];close $f
if {![string match *KNOWN_TEST_PASS* $result] || [string match *Fatal:* $result]} {error "Known unit test FAILED"}
