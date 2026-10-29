set original $root/vendor/fpga-md5crypt
set dirs [list $original/md5crypt $original/md5crypt/cpu $original/md5crypt/md5core $original/md5crypt/md5engine $original/util]
add_files $root/rtl/log2_compat.vh
set_property IS_GLOBAL_INCLUDE true [get_files $root/rtl/log2_compat.vh]
foreach d [lrange $dirs 1 end] {
 foreach f [glob $d/*.v] {
   if {![string match *_test.v $f] && [file tail $f] ni {asymm_bram.v cpu.v}} {add_files $f}
 }
}
foreach f {md5unit unit_ctrl core_ctrl unit_input_async uob16pq} {add_files $original/md5crypt/$f.v}
add_files [list $root/rtl/asymm_bram.v $root/rtl/cpu_vivado.v $root/rtl/md5crypt_lane.v $root/rtl/md5crypt8_axis_top.v]
set_property include_dirs $dirs [current_fileset]
set_property verilog_define SIMULATION [current_fileset]
set_property XPM_LIBRARIES {XPM_MEMORY} [current_project]
set_property top md5crypt8_axis_top [current_fileset]
