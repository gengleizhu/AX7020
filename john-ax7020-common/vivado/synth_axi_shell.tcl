set root [file normalize [file join [file dirname [info script]] ..]]
create_project -in_memory -part xc7z020clg400-2
read_verilog -sv $root/rtl/john_axi_shell.sv
synth_design -top john_axi_shell -mode out_of_context -part xc7z020clg400-2
create_clock -period 10 [get_ports aclk]
report_utilization -file $root/reports/axi_shell_synth_utilization.rpt
report_timing_summary -file $root/reports/axi_shell_synth_timing.rpt
if {[llength [get_cells -hier -filter {IS_BLACKBOX == 1}]]} {error "Unexpected blackbox"}
puts "AXI_SHELL_SYNTH_PASS"
