# Fresh project and regenerated IP. No frozen E06 project is opened.
set root [file normalize [file join [file dirname [info script]] ..]]
set log_dir [file join $root results candidate01]
file mkdir $log_dir
set ip_repo [file join $root hls work hls impl ip]
if {![file exists [file join $ip_repo component.xml]]} {error "Fresh E07 IP missing"}
set project_dir [file join $root vivado_atten]
if {[file exists [file join $project_dir e07.xpr]]} {
    if {![info exists ::env(E07_RESUME_PREPARE)] || $::env(E07_RESUME_PREPARE) ne "1"} {
        error "E07 project already exists; resume explicitly"
    }
    open_project [file join $project_dir e07.xpr]
    if {[get_property STATUS [get_runs synth_1]] ne "Not started"} {
        error "Refusing to re-prepare a synthesized or active E07 project"
    }
} else {
    create_project e07 $project_dir -part xczu9eg-ffvb1156-2-e
    set_property board_part xilinx.com:zcu102:part0:3.4 [current_project]
    set_property ip_repo_paths [list $ip_repo] [current_project]
    update_ip_catalog -rebuild
    import_files -norecurse [file join $root seed design_1.bd]
}
set bd [get_files */design_1.bd]
if {[llength $bd] != 1} {error "Expected one imported BD"}
open_bd_design $bd
set ps [get_bd_cells zynq_ultra_ps_e_0]
# With the physical 33.330-MHz reference, a requested 300 MHz produces
# 299.970032 MHz. The configuration-only clock probe/BD validation proved
# native RPLL auto selection at request=317 gives 316.635010 MHz, while
# A53/DDR/SDIO1/GEM3/UART0 frequencies stay unchanged (unused DP_STC changes).
# Use the resulting clock for timing; never alter the reference-clock metadata.
set_property -dict [list CONFIG.PSU__CRL_APB__PL0_REF_CTRL__SRCSEL RPLL \
    CONFIG.PSU__CRL_APB__PL0_REF_CTRL__FREQMHZ 317] $ps
if {[get_property CONFIG.PSU__ENET3__PERIPHERAL__ENABLE $ps] != 1 ||
    [get_property CONFIG.PSU__ENET3__GRP_MDIO__ENABLE $ps] != 1} {error "GEM3/MDIO missing"}
set actual [get_property CONFIG.PSU__CRL_APB__PL0_REF_CTRL__ACT_FREQMHZ $ps]
if {$actual < 300.0} {error "PS PL clock below 300 MHz: $actual"}
validate_bd_design
save_bd_design
generate_target all $bd
# The accepted E06 BD uses global synthesis (None), not OOC per IP.
# Preserve that mode. create_ip_run is legal only for synthesis-enabled IP;
# the top synth_1 run covers all RAM mappings in this global configuration.
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
set_property STRATEGY Performance_ExplorePostRoutePhysOpt [get_runs impl_1]
# The frozen weight-read FIFO has a four-BRAM combinational cascade on its
# critical path. Keep its depth/outstanding count, but constrain physical RAM
# mapping instead. UG835 synth_design supports -max_bram_cascade_height.
foreach synth_run [get_runs -filter {IS_SYNTHESIS == 1}] {
    set_property STEPS.SYNTH_DESIGN.ARGS.MAX_BRAM_CASCADE_HEIGHT 1 $synth_run
}
set fh [open [file join $log_dir clock.txt] w]
puts $fh "PL_ACTUAL_MHZ=$actual"
puts $fh "PL_REQUEST_MHZ=317"
puts $fh "PL_SOURCE=RPLL"
puts $fh "PS_REFERENCE_MHZ=[get_property CONFIG.PSU__PSS_REF_CLK__FREQMHZ $ps]"
close $fh
report_ip_status -file [file join $log_dir ip_status.rpt]
close_project
exit
