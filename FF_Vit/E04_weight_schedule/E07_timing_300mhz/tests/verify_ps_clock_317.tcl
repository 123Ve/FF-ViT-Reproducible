# Minimal native-auto-clock fix for a strict >=300-MHz requirement.
set root [file normalize [file join [file dirname [info script]] ..]]
open_project [file join $root results clock_probe_project clock_probe.xpr]
open_bd_design [get_files */design_1.bd]
set ps [get_bd_cells zynq_ultra_ps_e_0]
set before [dict create]
foreach prop [list_property $ps] {
    if {[string match "CONFIG.*ACT_FREQMHZ" $prop]} {dict set before $prop [get_property $prop $ps]}
}
set_property -dict [list CONFIG.PSU__CRL_APB__PL0_REF_CTRL__SRCSEL RPLL CONFIG.PSU__CRL_APB__PL0_REF_CTRL__FREQMHZ 317] $ps
set actual [get_property CONFIG.PSU__CRL_APB__PL0_REF_CTRL__ACT_FREQMHZ $ps]
if {$actual < 300.0} {error "Actual PL frequency below 300 MHz"}
dict for {prop value} $before {
    set after [get_property $prop $ps]
    if {$after ne $value} {puts "CLOCK_AUTO_DELTA $prop $value -> $after"}
}
validate_bd_design
puts "CLOCK_AUTO_PASS actual=$actual"
close_project
exit
