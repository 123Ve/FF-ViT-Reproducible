set root [file normalize [file join [file dirname [info script]] ..]]
set candidate candidate04
if {[info exists ::env(E07_CANDIDATE)]} {set candidate $::env(E07_CANDIDATE)}
if {$candidate ni {candidate04 candidate05}} {error "Unsupported candidate name"}
set out [file join $root results $candidate]
open_project [file join $root vivado_$candidate e07.xpr]
if {[get_property STATUS [get_runs synth_1]] ne "Not started"} {
    error "Refusing to relaunch an already attempted synthesis"
}
launch_runs synth_1 -jobs 8
wait_on_run synth_1
if {![string match "*Complete*" [get_property STATUS [get_runs synth_1]]]} {error "E07 synthesis failed"}
launch_runs impl_1 -to_step {phys_opt_design (Post-Route)} -jobs 8
wait_on_run impl_1
if {![string match "*Complete*" [get_property STATUS [get_runs impl_1]]]} {error "E07 implementation failed"}
open_run impl_1
set mmcm [get_cells -hier -filter {REF_NAME == MMCME4_ADV}]
if {[llength $mmcm] != 1} {error "Expected exactly one implemented MMCM"}
set clocks [get_clocks -of_objects [get_pins $mmcm/CLKOUT0]]
if {[llength $clocks] != 1} {error "Expected one actual generated core clock: $clocks"}
set core_clock [lindex $clocks 0]
set fh [open [file join $out clock.txt] a]
puts $fh "PL_PERIOD_NS=[get_property PERIOD $core_clock]"
puts $fh "CORE_CLOCK_NAME=$core_clock"
# Reject a mismatch between validated configuration and implemented primitive.
foreach {prop want} {CLKFBOUT_MULT_F 30.625 DIVCLK_DIVIDE 6 CLKOUT0_DIVIDE_F 4.25} {
    set value [get_property $prop $mmcm]
    if {abs($value-$want)>0.00001} {error "Implemented MMCM mismatch: $prop=$value"}
    puts $fh "IMPLEMENTED_$prop=$value"
}
close $fh
report_clocks -file [file join $out clocks.rpt]
report_timing_summary -max_paths 50 -report_unconstrained -file [file join $out timing.rpt]
report_timing -max_paths 50 -file [file join $out setup_paths.rpt]
report_route_status -file [file join $out route.rpt]
report_utilization -file [file join $out utilization.rpt]
report_utilization -hierarchical -hierarchical_depth 6 -file [file join $out hierarchy.rpt]
report_drc -file [file join $out drc.rpt]
check_timing -verbose -file [file join $out check_timing.rpt]
write_checkpoint -force [file join $out e07_postroute.dcp]
write_xdc -force [file join $out constraints.xdc]
puts [exec python3 [file join $root scripts check_release.py] $out]
write_bitstream -force [file join $out design_1_wrapper.bit]
write_hw_platform -fixed -include_bit -force -file [file join $out e07_300mhz_wrapper.xsa]
close_project
exit
