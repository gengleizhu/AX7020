set root [file normalize [file join [file dirname [info script]] ..]]
set out $root/reports/stage3/reset
file mkdir $out
create_project -force reset_test $out/project -part xc7z020clg400-1
source $root/vivado/integration_sources.tcl
add_files -fileset sim_1 $root/sim/tb/tb_axis_reset.sv
set_property top tb_axis_reset [get_filesets sim_1]
set_property include_dirs [get_property include_dirs [get_filesets sources_1]] [get_filesets sim_1]
set_property verilog_define {SIMULATION} [get_filesets sim_1]
set_property xsim.simulate.runtime all [get_filesets sim_1]
launch_simulation -step compile
launch_simulation -step elaborate
set run_dir $out/project/reset_test.sim/sim_1/behav/xsim
file mkdir $run_dir/bcrypt
file copy -force $original/bcrypt/S_data.txt $run_dir/bcrypt/S_data.txt
launch_simulation -step simulate
close_sim
file copy -force $run_dir/simulate.log $out/simulate.log
set fp [open $out/simulate.log r]; set txt [read $fp]; close $fp
if {[string first RESET_GUARD_PASS $txt]<0 || [string first "Fatal:" $txt]>=0 || [string first "cannot be opened" $txt]>=0} {error "reset guard failed"}
puts "RESET_GUARD_VERIFIED"
