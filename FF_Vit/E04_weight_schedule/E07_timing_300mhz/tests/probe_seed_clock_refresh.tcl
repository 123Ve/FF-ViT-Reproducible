set root [file normalize [file join [file dirname [info script]] ..]]
open_project [file join $root vivado_candidate04 e07.xpr]
open_bd_design [get_files */design_1.bd]
set ps [get_bd_cells zynq_ultra_ps_e_0]
set pin [get_bd_pins zynq_ultra_ps_e_0/pl_clk0]
puts "SEED_CLOCK BEFORE=[get_property CONFIG.FREQ_HZ $pin] ACTUAL=[get_property CONFIG.PSU__CRL_APB__PL0_REF_CTRL__ACT_FREQMHZ $ps]"
set_property CONFIG.PSU__CRL_APB__PL0_REF_CTRL__FREQMHZ 250.0 $ps
puts "SEED_CLOCK AFTER_SAME=[get_property CONFIG.FREQ_HZ $pin] ACTUAL=[get_property CONFIG.PSU__CRL_APB__PL0_REF_CTRL__ACT_FREQMHZ $ps]"
validate_bd_design
puts "SEED_CLOCK AFTER_VALIDATION=[get_property CONFIG.FREQ_HZ $pin] ACTUAL=[get_property CONFIG.PSU__CRL_APB__PL0_REF_CTRL__ACT_FREQMHZ $ps]"
close_project
exit
