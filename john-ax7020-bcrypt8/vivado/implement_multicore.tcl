set root [file normalize [file join [file dirname [info script]] ..]]
set cores_list {8}
if {[llength $argv]} {set cores_list $argv}
set_param general.maxThreads 4
foreach n $cores_list {
    set out [file join $root reports stage4 cores$n]
    file mkdir $out
    create_project -force john_axis_${n} [file join $root build multicore cores$n] -part xc7z020clg400-1
    source [file join $root vivado integration_sources.tcl]
    set_property generic CORES=$n [current_fileset]
    # 原bcrypt_data使用相对路径读S ROM，保持工具工作目录确定。
    set work [file join $root build multicore cores$n]
    file mkdir $work/bcrypt
    file copy -force $original/bcrypt/S_data.txt $work/bcrypt/S_data.txt
    cd $work
    set fp [open $out/clock.xdc w]
    puts $fp {create_clock -name aclk -period 10.000 [get_ports aclk]}
    puts $fp {set_input_delay -clock aclk 2.0 [get_ports -filter {DIRECTION == IN && NAME != aclk}]}
    puts $fp {set_output_delay -clock aclk 2.0 [get_ports -filter {DIRECTION == OUT}]}
    close $fp
    read_xdc $out/clock.xdc
    set status [open $out/status.txt w]
    puts $status "cores=$n scope=full_PL_axis_OOC period_ns=10"
    flush $status
    if {[catch {
        synth_design -top john_axis_top -generic CORES=$n -part xc7z020clg400-1 -mode out_of_context -flatten_hierarchy none
        set actual [get_cells -hier -filter {ORIG_REF_NAME == bcrypt_core || REF_NAME == bcrypt_core}]
        set bb [get_cells -hier -filter {IS_BLACKBOX == 1}]
        puts $status "physical_cores=[llength $actual] blackboxes=[llength $bb]"
        if {[llength $actual]!=$n || [llength $bb]} {error "real-core/blackbox assertion failed"}
        foreach cell $actual {
            if {![llength [get_cells -quiet $cell/fsm]] || ![llength [get_cells -quiet $cell/unit/S]]} {error "missing core datapath $cell"}
        }
        report_utilization -file $out/synth_utilization.rpt
        report_utilization -hierarchical -file $out/synth_hierarchy.rpt
        report_timing_summary -file $out/synth_timing.rpt
        write_checkpoint -force $out/synth.dcp
        puts $status "synthesis=pass"; flush $status
        opt_design
        place_design
        phys_opt_design
        route_design
        report_route_status -file $out/route_status.rpt
        report_utilization -file $out/routed_utilization.rpt
        report_timing_summary -delay_type min_max -max_paths 20 -report_unconstrained -file $out/routed_timing.rpt
        report_drc -file $out/drc.rpt
        report_methodology -file $out/methodology.rpt
        write_checkpoint -force $out/routed.dcp
        set slack [get_property SLACK [lindex [get_timing_paths -max_paths 1] 0]]
        set internal [get_timing_paths -from [all_registers -clock aclk] -to [all_registers -clock aclk] -max_paths 1]
        set iw [get_property SLACK [lindex $internal 0]]
        puts $status "implementation=pass wns_ns=$slack internal_wns_ns=$iw estimated_internal_fmax_mhz=[expr {1000.0/(10.0-$iw)}]"
        puts "IMPLEMENTATION_COMPLETE cores=$n wns=$slack"
    } reason]} {
        puts $status "implementation=failed reason=$reason"
        puts "IMPLEMENTATION_FAILED cores=$n reason=$reason"
    }
    close $status
    close_project
}
