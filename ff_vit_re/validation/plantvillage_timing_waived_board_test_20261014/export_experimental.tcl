# One-off execution recipe for the user's explicit PlantVillage timing waiver.
# No synthesis, placement, routing, clock changes or DRC severity overrides.
set task [file dirname [file normalize [info script]]]
set source_hw [file normalize [file join $task .. u3_full_board_test_20261014 outputs plantvillage hardware]]
set dcp [file join $source_hw results candidate05 postroute.dcp]
set expected 22a20a705f55984ace741863ba2ca0374652f2eb8c0bbf8eac2bab2a03b1124b
if {[lindex [exec sha256sum $dcp] 0] ne $expected} {error "Original routed checkpoint changed"}
if {![file exists [file join $task USER_WAIVER.json]]} {error "Missing recorded user timing waiver"}
set out [file join $task hardware release]
if {[file exists $out]} {error "Refusing existing experimental export overwrite"}
file mkdir $out
set_param general.maxThreads 4
open_project [file join $source_hw vivado_candidate05 e07.xpr]
set status [get_property STATUS [get_runs impl_1]]
if {![string match "phys_opt_design (Post-Route) Complete*" $status]} {error "Unexpected implementation status: $status"}
puts "EXPERIMENTAL_TIMING_WAIVER: setup WNS -0.115 ns; this is NOT timing qualified."
launch_runs impl_1 -next_step -jobs 2
wait_on_run impl_1
if {![string match "write_bitstream Complete*" [get_property STATUS [get_runs impl_1]]]} {error "Native bitstream generation failed"}
open_run impl_1
report_timing_summary -max_paths 50 -report_unconstrained -file [file join $out timing_final.rpt]
report_route_status -file [file join $out route_final.rpt]
report_drc -file [file join $out drc_final.rpt]
report_utilization -file [file join $out utilization_final.rpt]
set native [file join [get_property DIRECTORY [get_runs impl_1]] design_1_wrapper.bit]
file copy $native [file join $out design_1_wrapper.bit]
write_hw_platform -fixed -include_bit -file [file join $out u3_platform.xsa]
close_project
if {[lindex [exec sha256sum $dcp] 0] ne $expected} {error "Original routed checkpoint changed during export"}
puts "EXPERIMENTAL_BIT_AND_XSA_EXPORTED_NOT_TIMING_QUALIFIED"
exit
