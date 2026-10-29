set original $root/vendor/fpga-sha256crypt
set dirs [list $original/sha256crypt $original/sha256crypt/cpu $original/sha256crypt/sha256core $original/sha256crypt/sha256engine $original/sha256crypt/unit $original/util]
add_files $root/rtl/log2_compat.vh
set_property IS_GLOBAL_INCLUDE true [get_files $root/rtl/log2_compat.vh]
foreach d [lrange $dirs 1 end] {
 foreach f [glob $d/*.v] {
   if {![string match *_test.v $f] && [file tail $f] ni {asymm_bram.v cpu.v}} {add_files $f}
 }
}
add_files [list $root/rtl/asymm_bram.v $root/rtl/cpu_vivado.v $root/rtl/sha256crypt_lane.v $root/rtl/sha256crypt8_axis_top.v]
set_property include_dirs $dirs [current_fileset]
set_property verilog_define SIMULATION [current_fileset]
set_property XPM_LIBRARIES {XPM_MEMORY} [current_project]
set_property top sha256crypt8_axis_top [current_fileset]
