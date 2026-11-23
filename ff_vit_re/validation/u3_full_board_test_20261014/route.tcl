set root [file normalize [lindex $argv 0]]
if {![string match */validation/u3_full_board_test_20261014/outputs/*/hardware $root]} {error "Nonisolated root"}
set_param general.maxThreads 4
set out [file join $root results candidate05]
open_project [file join $root vivado_candidate05 e07.xpr]
foreach prop {IP_REPO_PATHS IP_OUTPUT_REPO IP_USER_FILES_DIR} {
    foreach path [get_property $prop [current_project]] {
        if {![string match ${root}/* [file normalize $path]]} {error "Path escapes root: $prop=$path"}
    }
}
if {[get_property STATUS [get_runs synth_1]] ne "Not started"} {error "Refusing overwrite"}
launch_runs synth_1 -jobs 2
wait_on_run synth_1
if {![string match "*Complete*" [get_property STATUS [get_runs synth_1]]]} {error "Synthesis failed"}
open_run synth_1
report_utilization -file [file join $out utilization_synth.rpt]
report_timing_summary -file [file join $out timing_synth.rpt]
write_checkpoint [file join $out synthesized.dcp]
close_design
launch_runs impl_1 -to_step {phys_opt_design (Post-Route)} -jobs 2
wait_on_run impl_1
set status [get_property STATUS [get_runs impl_1]]
if {![string match "*Complete*" $status]} {error "Implementation failed: $status"}
open_run impl_1
set mmcm [get_cells -hier -filter {REF_NAME == MMCME4_ADV}]
if {[llength $mmcm] != 1} {error "Expected one implemented MMCM"}
set core_clock [get_clocks -of_objects [get_pins $mmcm/CLKOUT0]]
if {[llength $core_clock] != 1} {error "Missing core clock"}
set fh [open [file join $out clock.txt] a]
puts $fh "PL_PERIOD_NS=[get_property PERIOD $core_clock]"
foreach {prop want} {CLKFBOUT_MULT_F 30.625 DIVCLK_DIVIDE 6 CLKOUT0_DIVIDE_F 4.25} {
    set value [get_property $prop $mmcm]
    if {abs($value-$want)>0.00001} {error "Implemented MMCM mismatch"}
    puts $fh "IMPLEMENTED_$prop=$value"
}
close $fh
report_utilization -file [file join $out utilization_postroute.rpt]
report_utilization -hierarchical -hierarchical_depth 6 -file [file join $out hierarchy_postroute.rpt]
report_timing_summary -max_paths 50 -report_unconstrained -file [file join $out timing_postroute.rpt]
report_route_status -file [file join $out route_status.rpt]
report_drc -file [file join $out drc.rpt]
report_clocks -file [file join $out clocks.rpt]
check_timing -verbose -file [file join $out check_timing.rpt]
write_checkpoint [file join $out postroute.dcp]
write_xdc [file join $out constraints.xdc]
close_project
exit
