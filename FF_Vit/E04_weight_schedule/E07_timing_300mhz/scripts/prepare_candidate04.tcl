# Clock-only continuation. Fresh project, same E07 IP, seed PS settings unchanged.
set root [file normalize [file join [file dirname [info script]] ..]]
set candidate candidate04
if {[info exists ::env(E07_CANDIDATE)]} {set candidate $::env(E07_CANDIDATE)}
if {$candidate ni {candidate04 candidate05}} {error "Unsupported candidate name"}
set out [file join $root results $candidate]
set project_dir [file join $root vivado_$candidate]
file mkdir $out
set ip_repo [file join $root hls work hls impl ip]
if {![file exists [file join $ip_repo component.xml]]} {error "Checked E07 IP missing"}
if {[file exists [file join $project_dir e07.xpr]]} {
    if {![info exists ::env(E07_RESUME_PREPARE)] || $::env(E07_RESUME_PREPARE) ne "1"} {
        error "Refusing to overwrite candidate04"
    }
    open_project [file join $project_dir e07.xpr]
    if {[get_property STATUS [get_runs synth_1]] ne "Not started"} {
        error "Cannot re-prepare synthesized or active candidate04"
    }
} else {
    create_project e07 $project_dir -part xczu9eg-ffvb1156-2-e
    set_property board_part xilinx.com:zcu102:part0:3.4 [current_project]
    set_property ip_repo_paths [list $ip_repo] [current_project]
    update_ip_catalog -rebuild
    import_files -norecurse [file join $root seed design_1.bd]
}
set bd [get_files */design_1.bd]
open_bd_design $bd
set ps [get_bd_cells zynq_ultra_ps_e_0]
# Reapply the identical 250-MHz request to trigger the PS import callback.
# Without it the seed's clock-pin metadata stays at the IP default 100 MHz.
# probe_seed_clock_refresh.tcl proves ACT_FREQ stays 249.975021 MHz.
set ps_clock_before [dict create]
foreach prop {PSU__CRF_APB__ACPU__ACT_FREQMHZ PSU__CRF_APB__DDR__ACT_FREQMHZ PSU__CRL_APB__SDIO1_REF_CTRL__ACT_FREQMHZ PSU__CRL_APB__GEM3_REF_CTRL__ACT_FREQMHZ PSU__CRL_APB__UART0_REF_CTRL__ACT_FREQMHZ} {
    dict set ps_clock_before $prop [get_property CONFIG.$prop $ps]
}
set_property CONFIG.PSU__CRL_APB__PL0_REF_CTRL__FREQMHZ 250.0 $ps
dict for {prop value} $ps_clock_before {
    if {[get_property CONFIG.$prop $ps] ne $value} {error "Unintended PS clock change: $prop"}
}
set source_mhz [get_property CONFIG.PSU__CRL_APB__PL0_REF_CTRL__ACT_FREQMHZ $ps]
if {abs($source_mhz - 249.975021) > 0.00001} {error "Seed PS clock changed"}
if {[get_property CONFIG.PSU__PSS_REF_CLK__FREQMHZ $ps] ne "33.330" &&
    abs([get_property CONFIG.PSU__PSS_REF_CLK__FREQMHZ $ps]-33.330) > 0.00001} {
    error "Physical PS reference metadata changed"
}
if {[get_property CONFIG.PSU__ENET3__PERIPHERAL__ENABLE $ps] != 1 ||
    [get_property CONFIG.PSU__ENET3__GRP_MDIO__ENABLE $ps] != 1} {error "GEM3/MDIO missing"}
set source_pin [get_bd_pins zynq_ultra_ps_e_0/pl_clk0]
set source_net [get_bd_nets -of_objects $source_pin]
set sinks [get_bd_pins -of_objects $source_net -filter {DIR == I}]
if {[llength $sinks] != 12} {error "Unexpected seed PL clock sink count: [llength $sinks]"}
set wiz [create_bd_cell -type ip -vlnv xilinx.com:ip:clk_wiz:6.0 core_clock]
set_property -dict [list CONFIG.PRIMITIVE MMCM CONFIG.PRIM_SOURCE No_buffer \
    CONFIG.PRIM_IN_FREQ $source_mhz CONFIG.USE_RESET true \
    CONFIG.RESET_TYPE ACTIVE_LOW CONFIG.CLKOUT1_REQUESTED_OUT_FREQ 300.215099] $wiz
set_property CONFIG.OVERRIDE_MMCM true $wiz
set_property -dict [list CONFIG.MMCM_CLKFBOUT_MULT_F 30.625 \
    CONFIG.MMCM_DIVCLK_DIVIDE 6 CONFIG.MMCM_CLKOUT0_DIVIDE_F 4.25] $wiz
connect_bd_net $source_pin [get_bd_pins core_clock/clk_in1]
# Vivado requires native object collections, not strings produced by foreach.
disconnect_bd_net $source_net [get_bd_pins $sinks]
connect_bd_net [get_bd_pins core_clock/clk_out1] [get_bd_pins $sinks]
set reset_pin [get_bd_pins zynq_ultra_ps_e_0/pl_resetn0]
connect_bd_net $reset_pin [get_bd_pins core_clock/resetn]
set locked_pin [get_bd_pins rst_ps8_0_99M/dcm_locked]
set prior_lock_net [get_bd_nets -quiet -of_objects $locked_pin]
if {[llength $prior_lock_net]} {error "Unexpected existing dcm_locked driver"}
connect_bd_net [get_bd_pins core_clock/locked] $locked_pin
validate_bd_design
set output_net [get_bd_nets -of_objects [get_bd_pins core_clock/clk_out1]]
foreach pin $sinks {
    if {[get_bd_nets -of_objects [get_bd_pins $pin]] ne $output_net} {error "Clock sink not moved: $pin"}
}
if {[get_bd_nets -of_objects $locked_pin] ne [get_bd_nets -of_objects [get_bd_pins core_clock/locked]]} {
    error "Clock locked not connected to reset controller"
}
if {[get_property CONFIG.C_EXT_RESET_HIGH [get_bd_cells rst_ps8_0_99M]] != 0} {
    error "PS reset polarity mismatch"
}
set m [get_property CONFIG.MMCM_CLKFBOUT_MULT_F $wiz]
set d [get_property CONFIG.MMCM_DIVCLK_DIVIDE $wiz]
set o [get_property CONFIG.MMCM_CLKOUT0_DIVIDE_F $wiz]
set actual [expr {$source_mhz*$m/$d/$o}]
if {$actual < 300.0 || $actual > 301.0} {error "Invalid actual core frequency: $actual"}
save_bd_design
generate_target all $bd
if {[get_property SYNTH_CHECKPOINT_MODE $bd] ne "None"} {create_ip_run $bd}
export_ip_user_files -of_objects $bd -no_script -sync -force -quiet
set wrapper [make_wrapper -files $bd -top]
add_files -norecurse $wrapper
set_property top design_1_wrapper [get_filesets sources_1]
update_compile_order -fileset sources_1
set_property AUTO_INCREMENTAL_CHECKPOINT 0 [get_runs synth_1]
set_property INCREMENTAL_CHECKPOINT "" [get_runs synth_1]
set_property INCREMENTAL_CHECKPOINT "" [get_runs impl_1]
set_property STRATEGY Flow_PerfOptimized_high [get_runs synth_1]
set_property STEPS.SYNTH_DESIGN.ARGS.GLOBAL_RETIMING on [get_runs synth_1]
set_property STRATEGY Performance_ExplorePostRoutePhysOpt [get_runs impl_1]
foreach run [get_runs -filter {IS_SYNTHESIS == 1}] {
    set_property STEPS.SYNTH_DESIGN.ARGS.MAX_BRAM_CASCADE_HEIGHT 1 $run
}
set fh [open [file join $out clock.txt] w]
foreach {key value} [list CLOCK_SOURCE MMCM PS_PL_ACTUAL_MHZ $source_mhz \
    PL_ACTUAL_MHZ $actual MMCM_MULT $m MMCM_DIVCLK $d MMCM_OUT_DIV $o \
    MMCM_ESTIMATED_JITTER_PS [get_property CONFIG.CLKOUT1_JITTER $wiz] \
    RESET_LOCK_VERIFIED 1 CORE_CLOCK_CONSUMERS_VERIFIED 1 \
    CORE_CLOCK_SINK_COUNT [llength $sinks] PS_REFERENCE_MHZ 33.330] {
    puts $fh "$key=$value"
}
close $fh
report_ip_status -file [file join $out ip_status.rpt]
close_project
exit
