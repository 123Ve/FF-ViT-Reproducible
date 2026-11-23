set root [file normalize [file join [file dirname [info script]] ..]]
set log_dir [file join $root results candidate02]
open_project [file join $root vivado_candidate02 e07.xpr]
launch_runs synth_1 -jobs 8
wait_on_run synth_1
if {![string match "*Complete*" [get_property STATUS [get_runs synth_1]]]} {error "E07 synthesis failed"}
launch_runs impl_1 -to_step {phys_opt_design (Post-Route)} -jobs 8
wait_on_run impl_1
if {![string match "*Complete*" [get_property STATUS [get_runs impl_1]]]} {error "E07 implementation failed"}
open_run impl_1
set period [get_property PERIOD [get_clocks clk_pl_0]]
set fh [open [file join $log_dir clock.txt] a]
puts $fh "PL_PERIOD_NS=$period"
close $fh
report_timing_summary -max_paths 50 -report_unconstrained -file [file join $log_dir timing.rpt]
report_timing -max_paths 50 -file [file join $log_dir setup_paths.rpt]
report_route_status -file [file join $log_dir route.rpt]
report_utilization -file [file join $log_dir utilization.rpt]
report_utilization -hierarchical -hierarchical_depth 6 -file [file join $log_dir hierarchy.rpt]
report_drc -file [file join $log_dir drc.rpt]
check_timing -verbose -file [file join $log_dir check_timing.rpt]
write_checkpoint -force [file join $log_dir e07_postroute.dcp]
write_xdc -force [file join $log_dir constraints.xdc]
# A failing timing run produces reports but never a deployable BIT/XSA.
puts [exec python3 [file join $root scripts check_release.py] $log_dir]
write_bitstream -force [file join $log_dir design_1_wrapper.bit]
write_hw_platform -fixed -include_bit -force -file [file join $log_dir e07_300mhz_wrapper.xsa]
close_project
exit
