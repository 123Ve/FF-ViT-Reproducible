set probe_root [file normalize [file join [file dirname [info script]] .. results option_probe_project]]
open_project [file join $probe_root option_probe.xpr]
set run [get_runs synth_1]
if {[llength $run] != 1} {error "Synthesis run missing"}
set_property STEPS.SYNTH_DESIGN.ARGS.MAX_BRAM_CASCADE_HEIGHT 1 $run
if {[get_property STEPS.SYNTH_DESIGN.ARGS.MAX_BRAM_CASCADE_HEIGHT $run] != 1} {
    error "BRAM mapping option was not applied"
}
puts "SYNTH_OPTION_PROBE_PASS"
exit
