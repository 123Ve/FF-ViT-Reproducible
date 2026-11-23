# Configuration-only fallback: >=300 MHz without an added PL clocking IP.
# Do not alter the active E07 project or release any image from this probe.
set root [file normalize [file join [file dirname [info script]] ..]]
open_project [file join $root results clock_probe_project clock_probe.xpr]
open_bd_design [get_files */design_1.bd]
set ps [get_bd_cells zynq_ultra_ps_e_0]
set_property -dict [list CONFIG.PSU__CRL_APB__PL0_REF_CTRL__SRCSEL RPLL CONFIG.PSU__CRL_APB__PL0_REF_CTRL__FREQMHZ 317] $ps
set before [dict create]
foreach prop [list_property $ps] {
    if {[string match "CONFIG.*ACT_FREQMHZ" $prop]} {dict set before $prop [get_property $prop $ps]}
}
# Derive feedback from measured configuration properties, never from an
# assumed divider. This auto configuration is feedback=57, DIV2=1, PL div0=3.
set feedback [get_property CONFIG.PSU__CRL_APB__RPLL_CTRL__FBDIV $ps]
set prior_actual [get_property CONFIG.PSU__CRL_APB__PL0_REF_CTRL__ACT_FREQMHZ $ps]
set minimum_feedback [expr {int(ceil(300.0 * $feedback / $prior_actual))}]
puts "CLOCK_MIN_BEFORE feedback=$feedback div2=[get_property CONFIG.PSU__CRL_APB__RPLL_CTRL__DIV2 $ps] pl_div0=[get_property CONFIG.PSU__CRL_APB__PL0_REF_CTRL__DIVISOR0 $ps] selected_feedback=$minimum_feedback"
if {$minimum_feedback > $feedback} {error "Fallback would increase RPLL frequency"}
set_property CONFIG.PSU__OVERRIDE__BASIC_CLOCK 1 $ps
set_property CONFIG.PSU__CRL_APB__RPLL_CTRL__FBDIV $minimum_feedback $ps
set actual [get_property CONFIG.PSU__CRL_APB__PL0_REF_CTRL__ACT_FREQMHZ $ps]
dict for {prop value} $before {
    set after [get_property $prop $ps]
    if {$after ne $value} {puts "CLOCK_MIN_DELTA $prop $value -> $after"}
}
if {$actual < 300.0 || $actual > 310.0} {error "Unexpected fallback frequency: $actual"}
validate_bd_design
puts "CLOCK_MIN_PASS actual=$actual"
close_project
exit
