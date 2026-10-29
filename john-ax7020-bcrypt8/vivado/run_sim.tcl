set root [file normalize [file join [file dirname [info script]] ..]]
source [file join $root vivado create_project.tcl]
set tops {tb_expand tb_core tb_invalid tb_packet}
if {[llength $argv]>0} {set tops $argv}
file mkdir [file join $root reports stage1]
foreach top $tops {
    set_property top $top [get_filesets sim_1]
    update_compile_order -fileset sim_1
    set depfile [open [file join $root reports stage1 ${top}_compile_order.txt] w]
    set seen {}
    foreach f [get_files -compile_order sources -used_in simulation -of_objects [get_filesets sim_1]] {
        if {$f ni $seen} {puts $depfile $f; lappend seen $f}
    }
    close $depfile
    launch_simulation -step compile
    launch_simulation -step elaborate
    # readmemh使用原源码路径，保留bcrypt/S_data.txt语义。
    set run_dir [file join $root build project john_bcrypt_stage1.sim sim_1 behav xsim]
    file mkdir $run_dir
    file mkdir [file join $run_dir sim vectors]
    foreach vector [glob [file join $root sim vectors *]] {
        file copy -force $vector [file join $run_dir sim vectors]
    }
    file mkdir [file join $run_dir bcrypt]
    file copy -force [file join $root rtl john_original bcrypt S_data.txt] [file join $run_dir bcrypt]
    launch_simulation -step simulate
    close_sim
    set log [file join $run_dir simulate.log]
    set fp [open $log r]; set txt [read $fp]; close $fp
    file copy -force $log [file join $root reports stage1 ${top}.log]
    if {[string first "STAGE1_PASS $top" $txt]<0 || [string first "Fatal:" $txt]>=0 || [string first "cannot be opened" $txt]>=0} {
        error "self-check failed: $top"
    }
    foreach f {core_results.txt packet_output.hex} {
        if {[file exists [file join $run_dir $f]]} {
            file copy -force [file join $run_dir $f] [file join $root reports stage1 $f]
        }
    }
}
puts "STAGE1_SIMULATIONS_PASS"
close_project
