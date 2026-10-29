set root [file normalize [file join [file dirname [info script]] ..]]
create_project -force descrypt8_test $root/build/sim8 -part xc7z020clg400-1
source $root/vivado/sources.tcl
add_files -fileset sim_1 [list $root/sim/tb_descrypt8.sv $root/sim/vectors.mem]
set_property top tb_descrypt8 [get_filesets sim_1]
set_property verilog_define CORE_INCLUDE_SRC [get_filesets sim_1]
set_property xsim.simulate.runtime all [get_filesets sim_1]
launch_simulation
close_sim
set f [open $root/build/sim8/descrypt8_test.sim/sim_1/behav/xsim/simulate.log r]
set result [read $f];close $f
if {![string match *DESCRYPT8_TEST_PASS* $result] || [string match *Fatal:* $result]} {error "Eight-core self-check FAILED"}
puts "DESCRYPT8_SIM_COMPLETE"
