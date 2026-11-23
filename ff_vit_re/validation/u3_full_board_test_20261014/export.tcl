set root [file normalize [lindex $argv 0]]
set name [lindex $argv 1]
if {![string match */validation/u3_full_board_test_20261014/outputs/*/hardware $root]} {error "Nonisolated root"}
set app [file normalize [file join $root .. .. ..]]
puts [exec /usr/bin/env -u PYTHONHOME -u PYTHONPATH -u LD_LIBRARY_PATH /home/user/anaconda3/envs/vlm_token/bin/python -B [file join $app qualify.py] --dataset $name]
set out [file join $root release]
if {[file exists $out]} {error "Refusing existing release overwrite"}
file mkdir $out
open_project [file join $root vivado_candidate05 e07.xpr]
set status [get_property STATUS [get_runs impl_1]]
if {![string match "phys_opt_design (Post-Route) Complete*" $status]} {error "Unexpected implementation status: $status"}
launch_runs impl_1 -next_step -jobs 2
wait_on_run impl_1
if {![string match "write_bitstream Complete*" [get_property STATUS [get_runs impl_1]]]} {error "Native BIT generation failed"}
open_run impl_1
report_timing_summary -max_paths 50 -report_unconstrained -file [file join $out timing_final.rpt]
report_route_status -file [file join $out route_final.rpt]
report_drc -file [file join $out drc_final.rpt]
set native [file join [get_property DIRECTORY [get_runs impl_1]] design_1_wrapper.bit]
file copy $native [file join $out design_1_wrapper.bit]
write_hw_platform -fixed -include_bit -file [file join $out u3_platform.xsa]
close_project
exit
