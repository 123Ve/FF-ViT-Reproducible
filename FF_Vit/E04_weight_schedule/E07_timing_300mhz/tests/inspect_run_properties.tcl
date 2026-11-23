set project [file normalize [file join [file dirname [info script]] .. results option_probe_project option_probe.xpr]]
open_project $project
set probe_run [get_runs synth_1]
foreach p [list_property $probe_run] {
    if {[string match *CASCADE* $p] || [string match *MORE* $p]} {
        puts "E07_RUN_PROPERTY: $p=[get_property $p $probe_run]"
    }
}
exit
