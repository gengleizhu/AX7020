# 调用者定义root；仅加入可综合设计，不包含阶段1的FIFO行为模型。
set original [file join $root rtl john_original]
# Explicit header membership avoids Vivado 2020.1 module-reference HDDA crash.
foreach d [list $original $original/bcrypt $original/bcrypt/bcrypt_core $original/pkt_comm $original/util] {
 foreach h [glob -nocomplain $d/*.vh] {add_files -norecurse $h}
}
set globals [file join $root rtl stage1 globals.vh]
add_files -norecurse $globals
set_property is_global_include true [get_files $globals]
set files [concat [glob $original/bcrypt/bcrypt_core/*.v] [glob $original/bcrypt/*.v] [glob $original/pkt_comm/*.v] [glob $original/util/*.v]]
foreach f $files {
    if {[file tail $f] ni {bcrypt.v bcrypt_test.v word_gen_b.v}} {add_files -norecurse $f}
}
add_files -norecurse [file join $root rtl stage1 word_gen_b.v]
add_files -norecurse [glob $root/rtl/integration/*.v]
add_files -norecurse [glob $root/rtl/adapters/*.v]
add_files -norecurse [file join $root rtl top john_axis_top.v]
set_property include_dirs [list $original $original/bcrypt $original/bcrypt/bcrypt_core $original/util] [current_fileset]
set_property verilog_define {SIMULATION} [current_fileset]
set_property top john_axis_top [current_fileset]
update_compile_order -fileset sources_1
