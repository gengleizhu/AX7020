set root [file normalize [file join [file dirname [info script]] ..]]
open_project [file join $root build project john_bcrypt_stage1.xpr]
foreach p [list_property [get_filesets sim_1]] {
    if {[regexp -nocase {incr|global|compile|elaborate} $p]} {
        puts "$p = [get_property $p [get_filesets sim_1]]"
    }
}
close_project
