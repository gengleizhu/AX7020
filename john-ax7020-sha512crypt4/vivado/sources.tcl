set original $root/vendor/fpga-sha512crypt
set dirs [list $original/sha512crypt $original/sha512crypt/cpu $original/sha512crypt/sha512core $original/sha512crypt/sha512engine $original/sha512crypt/unit $original/util]
add_files $root/rtl/log2_compat.vh
set_property IS_GLOBAL_INCLUDE true [get_files $root/rtl/log2_compat.vh]
foreach d [lrange $dirs 1 end] {
 foreach f [glob $d/*.v] {
   if {![string match *_test.v $f] && [file tail $f] ni {asymm_bram.v cpu.v}} {add_files $f}
 }
}
add_files [list $root/rtl/asymm_bram.v $root/rtl/cpu_vivado.v $root/rtl/sha512crypt_lane.v $root/rtl/sha512crypt4_axis_top.v]
set_property include_dirs $dirs [current_fileset]
set_property verilog_define SIMULATION [current_fileset]
set_property XPM_LIBRARIES {XPM_MEMORY} [current_project]
set_property top sha512crypt4_axis_top [current_fileset]
