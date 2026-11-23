set root [file normalize [file join [file dirname [info script]] ..]]
open_project [file join $root results clock_probe_project clock_probe.xpr]
open_bd_design [get_files */design_1.bd]
set ps [get_bd_cells zynq_ultra_ps_e_0]
set_property -dict [list CONFIG.PSU__CRL_APB__PL0_REF_CTRL__SRCSEL RPLL CONFIG.PSU__CRL_APB__PL0_REF_CTRL__FREQMHZ 300] $ps
proc print_clocks {label ps} {
    foreach prop {PSU__CRL_APB__RPLL_CTRL__FBDIV PSU__CRL_APB__RPLL_CTRL__DIV2 PSU__CRL_APB__RPLL_CTRL__FRACDATA PSU__CRL_APB__RPLL_FRAC_CFG__ENABLED PSU__CRL_APB__PL0_REF_CTRL__DIVISOR0 PSU__CRL_APB__PL0_REF_CTRL__DIVISOR1 PSU__CRL_APB__PL0_REF_CTRL__ACT_FREQMHZ PSU__CRF_APB__ACPU__ACT_FREQMHZ PSU__CRF_APB__DDR__ACT_FREQMHZ PSU__CRL_APB__SDIO1_REF_CTRL__ACT_FREQMHZ PSU__CRL_APB__GEM3_REF_CTRL__ACT_FREQMHZ PSU__CRL_APB__UART0_REF_CTRL__ACT_FREQMHZ} {
        puts "CLOCK_MANUAL $label $prop=[get_property CONFIG.$prop $ps]"
    }
}
print_clocks before $ps
set_property CONFIG.PSU__OVERRIDE__BASIC_CLOCK 1 $ps
print_clocks manual_only $ps
set_property -dict [list CONFIG.PSU__CRL_APB__RPLL_FRAC_CFG__ENABLED 1 CONFIG.PSU__CRL_APB__RPLL_CTRL__FRACDATA 400] $ps
print_clocks fractional $ps
set before [dict create]
foreach prop [list_property $ps] {
    if {[string match "CONFIG.*ACT_FREQMHZ" $prop]} {dict set before $prop [get_property $prop $ps]}
}
set_property CONFIG.PSU__CRL_APB__RPLL_CTRL__FBDIV 73 $ps
print_clocks integer_73 $ps
dict for {prop value} $before {
    set after [get_property $prop $ps]
    if {$after ne $value} {puts "CLOCK_DELTA $prop $value -> $after"}
}
validate_bd_design
close_project
exit
