set root [file normalize [file join [file dirname [info script]] ..]]
create_project -force sha256crypt8_compile $root/build/compile -part xc7z020clg400-1
source $root/vivado/sources.tcl
synth_design -top sha256crypt8_axis_top -part xc7z020clg400-1 -mode out_of_context
set units [get_cells -hier -filter {ORIG_REF_NAME == sha256unit || REF_NAME == sha256unit}]
set cores [get_cells -hier -filter {ORIG_REF_NAME == sha256core || REF_NAME == sha256core}]
if {[llength $units] != 8 || [llength $cores] != 24} {error "Expected 8 units/24 cores, got [llength $units]/[llength $cores]"}
report_utilization -file $root/reports/ooc_utilization.rpt
puts "SHA256CRYPT8_COMPILE_PASS units=8 cores=24"
