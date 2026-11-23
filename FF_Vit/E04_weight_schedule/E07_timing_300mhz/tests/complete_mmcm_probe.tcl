# Complete the throwaway clock probe after the unconnected-input diagnostic.
set root [file normalize [file join [file dirname [info script]] ..]]
open_project [file join $root results mmcm_probe probe.xpr]
open_bd_design [get_files */clock_probe.bd]
set wiz [get_bd_cells core_clock]
set clk [create_bd_port -dir I -type clk source_clock]
set_property CONFIG.FREQ_HZ 249975021 $clk
connect_bd_net $clk [get_bd_pins core_clock/clk_in1]
set rst [create_bd_port -dir I -type rst resetn]
set_property CONFIG.POLARITY ACTIVE_LOW $rst
connect_bd_net $rst [get_bd_pins core_clock/resetn]
make_bd_pins_external [get_bd_pins core_clock/clk_out1]
make_bd_pins_external [get_bd_pins core_clock/locked]
set_property -dict [list CONFIG.OVERRIDE_MMCM false \
    CONFIG.CLKOUT1_REQUESTED_OUT_FREQ 300.05] $wiz
set m [get_property CONFIG.MMCM_CLKFBOUT_MULT_F $wiz]
set d [get_property CONFIG.MMCM_DIVCLK_DIVIDE $wiz]
set o [get_property CONFIG.MMCM_CLKOUT0_DIVIDE_F $wiz]
puts "MMCM_VALIDATED INPUT_MHZ=249.975021 M=$m D=$d O=$o ACTUAL_MHZ=[expr {249.975021 * $m / $d / $o}]"
puts "MMCM_JITTER_PS=[get_property CONFIG.CLKOUT1_JITTER $wiz]"
validate_bd_design
save_bd_design
generate_target all [get_files */clock_probe.bd]
close_project
exit
