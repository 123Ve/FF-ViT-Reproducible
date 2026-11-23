set root [file normalize [file join [file dirname [info script]] ..]]
open_project [file join $root results option_probe_project option_probe.xpr]
set run [get_runs synth_1]
foreach p [list_property $run] {
    if {[string match *RETIM* $p]} {puts "RETIME_PROPERTY $p=[get_property $p $run]"}
}
set_property STEPS.SYNTH_DESIGN.ARGS.GLOBAL_RETIMING on $run
puts "GLOBAL_RETIMING_SELECTED=[get_property STEPS.SYNTH_DESIGN.ARGS.GLOBAL_RETIMING $run]"
puts [help phys_opt_design]
close_project
exit
