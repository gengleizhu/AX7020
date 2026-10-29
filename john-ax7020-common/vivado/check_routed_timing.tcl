# Run before publishing any BIT/HWH/XSA or declaring success.
set setup_paths [get_timing_paths -max_paths 1]
set hold_paths [get_timing_paths -delay_type min -max_paths 1]
if {![llength $setup_paths] || ![llength $hold_paths]} {error "Missing timing paths; cannot accept build"}
set slack [get_property SLACK [lindex $setup_paths 0]]
set hold_slack [get_property SLACK [lindex $hold_paths 0]]
if {$slack < 0 || $hold_slack < 0} {
 set fp [open $out/status.txt w]
 puts $fp "timing_pass=false wns_ns=$slack whs_ns=$hold_slack"
 puts $fp "delivery_exported=false board_tested=false"
 puts $fp "Existing deliverables, if any, belong to a previous build and are not accepted by this run."
 close $fp
 error "Routed timing failed: setup=$slack hold=$hold_slack; delivery not exported"
}
