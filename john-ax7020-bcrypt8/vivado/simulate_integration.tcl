# args: 核数 输入mem绝对路径 输入字节数 独立输出目录
set root [file normalize [file join [file dirname [info script]] ..]]
lassign $argv n input_mem input_bytes out
set out [file normalize $out]
file mkdir $out
create_project -force sim_axis_$n $out/project -part xc7z020clg400-1
source $root/vivado/integration_sources.tcl
add_files -fileset sim_1 -norecurse $root/sim/tb/tb_axis_multicore.sv
set_property top tb_axis_multicore [get_filesets sim_1]
set_property generic "CORES=$n INPUT_BYTES=$input_bytes" [get_filesets sim_1]
set_property include_dirs [get_property include_dirs [get_filesets sources_1]] [get_filesets sim_1]
set_property verilog_define {SIMULATION} [get_filesets sim_1]
set_property incremental false [get_filesets sim_1]
set_property xsim.simulate.runtime all [get_filesets sim_1]
launch_simulation -step compile
launch_simulation -step elaborate
set run_dir $out/project/sim_axis_$n.sim/sim_1/behav/xsim
file mkdir $run_dir/bcrypt
file copy -force $original/bcrypt/S_data.txt $run_dir/bcrypt/S_data.txt
file copy -force $input_mem $run_dir/input.mem
launch_simulation -step simulate
close_sim
foreach f {simulate.log axis_output.hex metrics.txt} {file copy -force $run_dir/$f $out/$f}
set fp [open $out/simulate.log r]; set text [read $fp]; close $fp
if {[string first "INTEGRATION_PASS" $text]<0 || [string first "Fatal:" $text]>=0 || [string first "cannot be opened" $text]>=0} {
    error "Integration RTL self-check failed"
}
puts "INTEGRATION_SIM_PASS cores=$n"
close_project
