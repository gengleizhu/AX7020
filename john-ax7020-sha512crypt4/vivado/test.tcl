set root [file normalize [file join [file dirname [info script]] ..]]
create_project -force sha512crypt4_test $root/build/sim -part xc7z020clg400-1
source $root/vivado/sources.tcl
add_files -fileset sim_1 [list $root/sim/tb_sha512crypt4.sv $root/sim/input.mem $root/sim/expected.mem]
set_property top tb_sha512crypt4 [get_filesets sim_1]
set_property verilog_define SIMULATION [get_filesets sim_1]
set_property xsim.simulate.log_all_signals false [get_filesets sim_1]
set_property xsim.simulate.runtime all [get_filesets sim_1]
launch_simulation
close_sim
set f [open $root/build/sim/sha512crypt4_test.sim/sim_1/behav/xsim/simulate.log r]
set result [read $f];close $f
if {![string match *SHA512CRYPT4_TEST_PASS* $result] || [string match *Fatal:* $result]} {error "SHA512crypt4 test FAILED"}
puts "SHA512CRYPT4_SIM_COMPLETE"
