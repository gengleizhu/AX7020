set root [file normalize [file join [file dirname [info script]] ..]]
set out $root/reports/stage3/adapters
file mkdir $out
create_project -force adapters $out/project -part xc7z020clg400-1
add_files [glob $root/rtl/adapters/*.v]
add_files -fileset sim_1 $root/sim/tb/tb_axis_adapters.sv
set_property top tb_axis_adapters [get_filesets sim_1]
set_property xsim.simulate.runtime all [get_filesets sim_1]
launch_simulation
close_sim
set file $out/project/adapters.sim/sim_1/behav/xsim/simulate.log
file copy -force $file $out/simulate.log
set fp [open $file r]; set txt [read $fp]; close $fp
if {[string first ADAPTERS_PASS $txt]<0 || [string first "Fatal:" $txt]>=0} {error "adapter self-check failed"}
puts "ADAPTERS_VERIFIED"
