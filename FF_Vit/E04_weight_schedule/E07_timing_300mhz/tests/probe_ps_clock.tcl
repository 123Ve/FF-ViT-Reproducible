# Configuration-only diagnostic. Never generates or synthesizes E06 IP.
set root [file normalize [file join [file dirname [info script]] ..]]
create_project clock_probe [file join $root results clock_probe_project] -part xczu9eg-ffvb1156-2-e
set_property board_part xilinx.com:zcu102:part0:3.4 [current_project]
set baseline_ip [file normalize [file join $root .. E06_mlp_ln_token_pipeline hls work hls impl ip]]
set_property ip_repo_paths [list $baseline_ip] [current_project]
update_ip_catalog
import_files -norecurse [file join $root seed design_1.bd]
open_bd_design [get_files */design_1.bd]
set ps [get_bd_cells zynq_ultra_ps_e_0]
puts "CLOCK_REFERENCE [get_property CONFIG.PSU__PSS_REF_CLK__FREQMHZ $ps]"
foreach source {IOPLL RPLL} {
    foreach request {300 300.1 301 305 310 320 333.3} {
        set_property -dict [list CONFIG.PSU__CRL_APB__PL0_REF_CTRL__SRCSEL $source CONFIG.PSU__CRL_APB__PL0_REF_CTRL__FREQMHZ $request] $ps
        puts "CLOCK_PROBE source=$source request=$request actual=[get_property CONFIG.PSU__CRL_APB__PL0_REF_CTRL__ACT_FREQMHZ $ps]"
    }
}
close_project
exit
