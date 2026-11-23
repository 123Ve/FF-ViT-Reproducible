set root [file normalize [file join [file dirname [info script]] ..]]
open_project [file join $root results mmcm_probe probe.xpr]
open_bd_design [get_files */clock_probe.bd]
set wiz [get_bd_cells core_clock]
# Separate updates avoid changing a frequency field while override is enabled.
set_property CONFIG.OVERRIDE_MMCM false $wiz
set_property CONFIG.CLKOUT1_REQUESTED_OUT_FREQ 300.05 $wiz
validate_bd_design
set m [get_property CONFIG.MMCM_CLKFBOUT_MULT_F $wiz]
set d [get_property CONFIG.MMCM_DIVCLK_DIVIDE $wiz]
set o [get_property CONFIG.MMCM_CLKOUT0_DIVIDE_F $wiz]
puts "MMCM_FINAL INPUT_MHZ=249.975021 M=$m D=$d O=$o ACTUAL_MHZ=[expr {249.975021 * $m / $d / $o}]"
puts "MMCM_JITTER_PS=[get_property CONFIG.CLKOUT1_JITTER $wiz]"
save_bd_design
generate_target all [get_files */clock_probe.bd]
close_project
exit
