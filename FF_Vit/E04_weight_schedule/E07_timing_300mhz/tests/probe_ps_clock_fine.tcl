set root [file normalize [file join [file dirname [info script]] ..]]
open_project [file join $root results clock_probe_project clock_probe.xpr]
open_bd_design [get_files */design_1.bd]
set ps [get_bd_cells zynq_ultra_ps_e_0]
foreach request {310.1 311 312 313 314 315 316 317 318 319} {
    set_property -dict [list CONFIG.PSU__CRL_APB__PL0_REF_CTRL__SRCSEL RPLL CONFIG.PSU__CRL_APB__PL0_REF_CTRL__FREQMHZ $request] $ps
    puts "CLOCK_FINE request=$request actual=[get_property CONFIG.PSU__CRL_APB__PL0_REF_CTRL__ACT_FREQMHZ $ps]"
}
puts "CLOCK_FRACTION_ENABLE_BEFORE [get_property CONFIG.PSU__CRL_APB__RPLL_FRAC_CFG__ENABLED $ps]"
if {[catch {
    set_property -dict [list CONFIG.PSU__CRL_APB__RPLL_FRAC_CFG__ENABLED 1 CONFIG.PSU__CRL_APB__PL0_REF_CTRL__FREQMHZ 300] $ps
    puts "CLOCK_FRACTION actual=[get_property CONFIG.PSU__CRL_APB__PL0_REF_CTRL__ACT_FREQMHZ $ps] enabled=[get_property CONFIG.PSU__CRL_APB__RPLL_FRAC_CFG__ENABLED $ps]"
} issue]} {puts "CLOCK_FRACTION_UNAVAILABLE $issue"}
close_project
exit
