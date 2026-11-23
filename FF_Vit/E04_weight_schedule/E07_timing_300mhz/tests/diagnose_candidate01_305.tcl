# Diagnostic only. A changed DCP clock constraint does not change PS hardware.
# This script never writes a bitstream or XSA.
set root [file normalize [file join [file dirname [info script]] ..]]
set out [file join $root results diagnostic305]
file mkdir $out
open_checkpoint [file join $root results candidate01 e07_postroute.dcp]
create_clock -name clk_pl_0 -period [expr {1000.0 / 305.525024}] [get_pins {PS8_i/PLCLK[0]}]
report_timing_summary -max_paths 10 -file [file join $out reconstraint_timing.rpt]
report_timing -max_paths 10 -file [file join $out reconstraint_paths.rpt]
close_design
exit
