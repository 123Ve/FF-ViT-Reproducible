set root [file normalize [file join [file dirname [info script]] ..]]
open_project [file join $root results mmcm_probe probe.xpr]
open_bd_design [get_files */clock_probe.bd]
set wiz [get_bd_cells core_clock]
set_property CONFIG.OVERRIDE_MMCM true $wiz
foreach tuple {{30.625 6 4.25} {21.625 4 4.5} {11.125 2 4.625} {9.625 2 4.0}} {
    lassign $tuple m d o
    set_property -dict [list CONFIG.MMCM_CLKFBOUT_MULT_F $m \
        CONFIG.MMCM_DIVCLK_DIVIDE $d CONFIG.MMCM_CLKOUT0_DIVIDE_F $o] $wiz
    puts "MMCM_JITTER_PROBE M=$m D=$d O=$o ACTUAL_MHZ=[expr {249.975021*$m/$d/$o}] JITTER_PS=[get_property CONFIG.CLKOUT1_JITTER $wiz] PHASE_ERROR_PS=[get_property CONFIG.CLKOUT1_PHASE_ERROR $wiz]"
}
# Keep the low-jitter, near-300-MHz candidate for generated RTL inspection.
set_property -dict [list CONFIG.MMCM_CLKFBOUT_MULT_F 30.625 \
    CONFIG.MMCM_DIVCLK_DIVIDE 6 CONFIG.MMCM_CLKOUT0_DIVIDE_F 4.25] $wiz
validate_bd_design
save_bd_design
generate_target all [get_files */clock_probe.bd]
close_project
exit
