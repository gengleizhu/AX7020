set root [file normalize [file join [file dirname [info script]] ..]]
create_project -force sha256crypt8_test $root/build/sim -part xc7z020clg400-1
source $root/vivado/sources.tcl
add_files -fileset sim_1 [list $root/sim/tb_sha256crypt8.sv $root/sim/input.mem $root/sim/expected.mem]
set_property top tb_sha256crypt8 [get_filesets sim_1]
set_property verilog_define SIMULATION [get_filesets sim_1]
set_property xsim.simulate.log_all_signals false [get_filesets sim_1]
set_property xsim.simulate.runtime all [get_filesets sim_1]
launch_simulation
close_sim
set f [open $root/build/sim/sha256crypt8_test.sim/sim_1/behav/xsim/simulate.log r]
set result [read $f];close $f
if {![string match *SHA256CRYPT8_TEST_PASS* $result] || [string match *Fatal:* $result]} {error "SHA256crypt8 test FAILED"}
puts "SHA256CRYPT8_SIM_COMPLETE"
