# Configuration-only exploratory probe. No synthesis or frozen project writes.
set root [file normalize [file join [file dirname [info script]] ..]]
set out [file join $root results mmcm_probe]
if {[file exists [file join $out probe.xpr]]} {error "Refusing to overwrite probe"}
create_project probe $out -part xczu9eg-ffvb1156-2-e
create_bd_design clock_probe
set wiz [create_bd_cell -type ip -vlnv xilinx.com:ip:clk_wiz:6.0 core_clock]
set_property -dict [list CONFIG.PRIMITIVE MMCM CONFIG.PRIM_SOURCE No_buffer \
    CONFIG.PRIM_IN_FREQ 249.975021 CONFIG.USE_RESET true \
    CONFIG.RESET_TYPE ACTIVE_LOW] $wiz
foreach request {300.05 300.2 300.3 301.0} {
    set_property CONFIG.CLKOUT1_REQUESTED_OUT_FREQ $request $wiz
    set m [get_property CONFIG.MMCM_CLKFBOUT_MULT_F $wiz]
    set d [get_property CONFIG.MMCM_DIVCLK_DIVIDE $wiz]
    set o [get_property CONFIG.MMCM_CLKOUT0_DIVIDE_F $wiz]
    set actual [expr {249.975021 * $m / $d / $o}]
    puts "MMCM_PROBE REQUEST=$request M=$m D=$d O=$o ACTUAL=$actual"
}
# Valid divisors are also checked by the installed Clocking Wizard validator.
set_property -dict [list CONFIG.CLKOUT1_REQUESTED_OUT_FREQ 300.215 \
    CONFIG.OVERRIDE_MMCM true CONFIG.MMCM_CLKFBOUT_MULT_F 61.25 \
    CONFIG.MMCM_DIVCLK_DIVIDE 12 CONFIG.MMCM_CLKOUT0_DIVIDE_F 4.25] $wiz
report_property $wiz
save_bd_design
generate_target all [get_files */clock_probe.bd]
close_project
exit
