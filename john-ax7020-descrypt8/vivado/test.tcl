set root [file normalize [file join [file dirname [info script]] ..]]
create_project -force descrypt_test $root/build/sim -part xc7z020clg400-1
source $root/vivado/sources.tcl
add_files -fileset sim_1 $root/sim/vectors.mem
add_files -fileset sim_1 $root/sim/tb_descrypt.sv
set_property top tb_descrypt [get_filesets sim_1]
set_property verilog_define CORE_INCLUDE_SRC [get_filesets sim_1]
set_property xsim.simulate.runtime all [get_filesets sim_1]
launch_simulation
close_sim
set f [open $root/build/sim/descrypt_test.sim/sim_1/behav/xsim/simulate.log r]
set simulation_text [read $f];close $f
if {![string match *DESCRYPT_TEST_PASS* $simulation_text] || [string match *Fatal:* $simulation_text]} {error "Self-checking simulation FAILED"}
puts "DESCRYPT_SIM_FINISHED_CHECK_PASS_MARKER"
