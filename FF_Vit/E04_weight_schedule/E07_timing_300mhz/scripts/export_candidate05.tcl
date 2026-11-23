# Export the accepted, already completed implementation. Never launch new runs.
set root [file normalize [file join [file dirname [info script]] ..]]
set previous [file join $root results candidate05]
set output_name board_release
if {[info exists ::env(E07_BOARD_OUTPUT)]} {set output_name $::env(E07_BOARD_OUTPUT)}
if {$output_name ni {board_resume board_release}} {error "Unsupported export directory"}
set out [file join $previous $output_name]
foreach artifact {design_1_wrapper.bit e07_300mhz_wrapper.xsa} {
    if {[file exists [file join $out $artifact]]} {
        error "Refusing to overwrite export: $artifact"
    }
}
puts [exec python3 [file join $root scripts check_release.py] $previous]
open_project [file join $root vivado_candidate05 e07.xpr]
if {![string match "*Complete*" [get_property STATUS [get_runs impl_1]]]} {
    error "Existing implementation is not complete"
}
# The previous failed export demonstrated that include_bit requires the BIT
# registered by the project run, not a stand-alone write_bitstream output.
# Continue exactly one completed run step: bit generation, never place/route.
if {![string match "write_bitstream Complete*" [get_property STATUS [get_runs impl_1]]]} {
    if {![string match "phys_opt_design (Post-Route) Complete*" [get_property STATUS [get_runs impl_1]]]} {
        error "Refusing to continue from a step other than completed post-route optimization"
    }
    launch_runs impl_1 -next_step -jobs 8
    wait_on_run impl_1
}
if {![string match "write_bitstream Complete*" [get_property STATUS [get_runs impl_1]]]} {
    error "Native bit generation did not complete"
}
open_run impl_1
set mmcm [get_cells -hier -filter {REF_NAME == MMCME4_ADV}]
if {[llength $mmcm] != 1} {error "Expected exactly one implemented MMCM"}
foreach {prop want} {CLKFBOUT_MULT_F 30.625 DIVCLK_DIVIDE 6 CLKOUT0_DIVIDE_F 4.25} {
    if {abs([get_property $prop $mmcm]-$want)>0.00001} {
        error "Implemented MMCM differs from accepted evidence: $prop"
    }
}
set clocks [get_clocks -of_objects [get_pins $mmcm/CLKOUT0]]
if {[llength $clocks] != 1} {error "Missing or ambiguous core clock"}
set period [get_property PERIOD [lindex $clocks 0]]
if {abs($period-3.331)>0.00051} {error "Unexpected implemented clock period: $period"}
file copy [file join $previous clock.txt] [file join $out clock.txt]
file copy [file join $previous csim.log] [file join $out csim.log]
report_clocks -file [file join $out clocks.rpt]
report_timing_summary -max_paths 50 -report_unconstrained -file [file join $out timing.rpt]
report_route_status -file [file join $out route.rpt]
report_utilization -file [file join $out utilization.rpt]
report_drc -file [file join $out drc.rpt]
puts [exec python3 [file join $root scripts check_release.py] $out]
set native_bit [file join [get_property DIRECTORY [get_runs impl_1]] design_1_wrapper.bit]
if {![file exists $native_bit]} {error "Missing BIT from the accepted implementation run"}
file copy $native_bit [file join $out design_1_wrapper.bit]
write_hw_platform -fixed -include_bit -file [file join $out e07_300mhz_wrapper.xsa]
close_project
exit
