# One local physical fix for the measured negative BRAM/DSP clock skew.
# Use the already-routed candidate02 at its unchanged real 305.525024 MHz.
# No clock reconstraint, HLS/RTL edit, lane change, or full rerun.
set root [file normalize [file join [file dirname [info script]] ..]]
set out [file join $root results candidate03_clockopt]
if {[file exists [file join $out timing.rpt]]} {error "Refusing to overwrite clock optimization evidence"}
file mkdir $out
file copy [file join $root results candidate02 clock.txt] [file join $out clock.txt]
file copy [file join $root results candidate02 csim.log] [file join $out csim.log]
open_project [file join $root vivado_candidate02 e07.xpr]
open_run impl_1
set prior [get_property PERIOD [get_clocks clk_pl_0]]
phys_opt_design -clock_opt
if {[get_property PERIOD [get_clocks clk_pl_0]] != $prior} {error "Clock period changed unexpectedly"}
report_timing_summary -max_paths 50 -report_unconstrained -file [file join $out timing.rpt]
report_timing -max_paths 50 -file [file join $out setup_paths.rpt]
report_route_status -file [file join $out route.rpt]
report_utilization -file [file join $out utilization.rpt]
report_utilization -hierarchical -hierarchical_depth 6 -file [file join $out hierarchy.rpt]
report_drc -file [file join $out drc.rpt]
check_timing -verbose -file [file join $out check_timing.rpt]
write_checkpoint [file join $out e07_postroute.dcp]
write_xdc [file join $out constraints.xdc]
puts [exec python3 [file join $root scripts check_release.py] $out]
write_bitstream [file join $out design_1_wrapper.bit]
write_hw_platform -fixed -include_bit -file [file join $out e07_300mhz_wrapper.xsa]
close_project
exit
