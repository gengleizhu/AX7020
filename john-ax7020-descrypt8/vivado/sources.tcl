set original $root/vendor/fpga-descrypt
add_files $root/rtl/log2_compat.vh
set_property IS_GLOBAL_INCLUDE true [get_files $root/rtl/log2_compat.vh]
add_files [glob $original/descrypt/descrypt_core/*.v]
add_files $original/util/sync.v
add_files $root/rtl/descrypt_axis_top.v
add_files $root/rtl/descrypt8_axis_top.v
set_property include_dirs [list $original/descrypt/descrypt_core $original/util] [current_fileset]
set_property verilog_define CORE_INCLUDE_SRC [current_fileset]
set_property top descrypt8_axis_top [current_fileset]
