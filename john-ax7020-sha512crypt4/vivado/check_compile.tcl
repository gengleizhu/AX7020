set root [file normalize [file join [file dirname [info script]] ..]]
create_project -force sha512crypt4_compile $root/build/compile -part xc7z020clg400-1
source $root/vivado/sources.tcl
synth_design -top sha512crypt4_axis_top -part xc7z020clg400-1 -mode out_of_context
set units [get_cells -hier -filter {ORIG_REF_NAME == sha512unit || REF_NAME == sha512unit}]
set cores [get_cells -hier -filter {ORIG_REF_NAME == core || REF_NAME == core}]
if {[llength $units] != 4 || [llength $cores] != 16} {error "Expected 4 units/16 cores, got [llength $units]/[llength $cores]"}
report_utilization -file $root/reports/ooc_utilization.rpt
puts "SHA512CRYPT4_COMPILE_PASS units=4 cores=16"
