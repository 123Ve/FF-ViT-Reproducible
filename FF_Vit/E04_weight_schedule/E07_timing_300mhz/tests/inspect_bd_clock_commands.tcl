set root [file normalize [file join [file dirname [info script]] ..]]
open_project [file join $root vivado_candidate04 e07.xpr]
open_bd_design [get_files */design_1.bd]
help disconnect_bd_net
help connect_bd_net
set net [get_bd_nets -of_objects [get_bd_pins zynq_ultra_ps_e_0/pl_clk0]]
puts "CLOCK_SOURCE_NET=$net"
puts "CLOCK_SINKS=[get_bd_pins -of_objects $net -filter {DIR == I}]"
puts "RESET_POLARITY=[get_property CONFIG.C_EXT_RESET_HIGH [get_bd_cells rst_ps8_0_99M]]"
close_project
exit
