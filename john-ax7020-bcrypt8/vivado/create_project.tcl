set root [file normalize [file join [file dirname [info script]] ..]]
set original [file join $root rtl john_original]
create_project -force john_bcrypt_stage1 [file join $root build project] -part xc7z020clg400-1
set_property target_language Verilog [current_project]
set_property simulator_language Mixed [current_project]
set core_files [glob [file join $original bcrypt bcrypt_core *.v]]
add_files -norecurse $core_files
set_property top bcrypt_core [get_filesets sources_1]
set globals [file join $root rtl stage1 globals.vh]
add_files -norecurse $globals
set_property is_global_include true [get_files $globals]
set inc [list $original [file join $original bcrypt] [file join $original bcrypt bcrypt_core] [file join $original util] [file join $root sim vectors]]
set_property include_dirs $inc [get_filesets sources_1]
set_property verilog_define {SIMULATION} [get_filesets sources_1]
set extra [concat [glob [file join $original bcrypt *.v]] [glob [file join $original pkt_comm *.v]] [glob [file join $original util *.v]]]
foreach f $extra {
    if {[file tail $f] ni {bcrypt_test.v word_gen_b.v}} {add_files -fileset sim_1 -norecurse $f}
}
add_files -fileset sim_1 -norecurse [file join $root rtl stage1 word_gen_b.v]
add_files -fileset sim_1 -norecurse [glob [file join $root sim tb *.sv]]
set_property include_dirs $inc [get_filesets sim_1]
set_property verilog_define {SIMULATION} [get_filesets sim_1]
set_property top tb_core [get_filesets sim_1]
set_property xsim.simulate.runtime all [get_filesets sim_1]
# Vivado 2018.3 incremental xvlog can omit cached global macro definitions
# when switching testbench tops. Recompile each top deterministically.
set_property incremental false [get_filesets sim_1]
add_files -fileset constrs_1 -norecurse [file join $root vivado constraints core.xdc]
update_compile_order -fileset sources_1
update_compile_order -fileset sim_1
puts "STAGE1_PROJECT_READY"
