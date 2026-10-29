set root [file normalize [file join [file dirname [info script]] ..]]
create_project -force md5crypt_known $root/build/known -part xc7z020clg400-1
source $root/vivado/sources.tcl
add_files -fileset sim_1 $root/sim/tb_known.sv
set_property top tb_known [get_filesets sim_1]
set_property verilog_define SIMULATION [get_filesets sim_1]
set_property xsim.elaborate.xelab.more_options { -O0} [get_filesets sim_1]
set_property xsim.simulate.runtime all [get_filesets sim_1]
if {[info exists env(MD5_PROBE)]} {set_property -name xsim.simulate.xsim.more_options -value { -testplusarg PROBE} -objects [get_filesets sim_1]}
launch_simulation
close_sim
set f [open $root/build/known/md5crypt_known.sim/sim_1/behav/xsim/simulate.log r]
set result [read $f];close $f
if {![string match *KNOWN_TEST_PASS* $result] || [string match *Fatal:* $result]} {error "Known-vector test FAILED"}
