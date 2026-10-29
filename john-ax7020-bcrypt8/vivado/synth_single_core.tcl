set root [file normalize [file join [file dirname [info script]] ..]]
set periods {10.000 8.000 6.667}
if {[llength $argv]} {set periods $argv}
set out [file join $root reports stage1 synthesis]
file mkdir $out
foreach period $periods {
    create_project -in_memory -part xc7z020clg400-1
    set original [file join $root rtl john_original]
    set_property include_dirs [list [file join $original bcrypt] [file join $original bcrypt bcrypt_core]] [current_fileset]
    set_property verilog_define {SIMULATION} [current_fileset]
    read_verilog [glob [file join $original bcrypt bcrypt_core *.v]]
    # Apply the target clock before synthesis so memory mapping sees it.
    read_xdc [file join $root vivado constraints core.xdc]
    if {$period != 10.000} {
        set fp [open [file join $out clock_${period}.xdc] w]
        puts $fp "create_clock -name compute_clk -period $period \[get_ports CLK\]"
        close $fp
        remove_files [get_files *core.xdc]
        read_xdc [file join $out clock_${period}.xdc]
    }
    synth_design -top bcrypt_core -part xc7z020clg400-1 -mode out_of_context -flatten_hierarchy none
    if {[llength [get_cells -quiet -hier -filter {IS_BLACKBOX == 1}]]} {error "Blackbox found"}
    foreach cell {fsm unit unit/P unit/S} {
        if {![llength [get_cells -quiet $cell]]} {error "Missing real logic: $cell"}
    }
    set prefix [file join $out core_${period}]
    report_utilization -file ${prefix}_utilization.rpt
    report_utilization -hierarchical -file ${prefix}_hierarchy.rpt
    report_timing_summary -max_paths 10 -file ${prefix}_timing.rpt
    report_methodology -file ${prefix}_methodology.rpt
    set paths [get_timing_paths -max_paths 1]
    if {![llength $paths]} {error "No timed path"}
    set slack [get_property SLACK [lindex $paths 0]]
    set fp [open ${prefix}_status.txt w]
    puts $fp "part=xc7z020clg400-1 period_ns=$period wns_ns=$slack blackboxes=0 real_core=1"
    close $fp
    write_checkpoint -force ${prefix}_synth.dcp
    puts "STAGE1_SYNTH_PASS period_ns=$period wns_ns=$slack"
    if {$period==10.000 && $slack<0} {error "100 MHz timing failed"}
    close_project
}
