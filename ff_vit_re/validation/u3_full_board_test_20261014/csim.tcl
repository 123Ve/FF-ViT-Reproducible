set root [file normalize $::env(U3_BOARD_HARDWARE)]
set fixture [file normalize $::env(U3_BOARD_FIXTURE)]
if {![string match */validation/u3_full_board_test_20261014/outputs/*/hardware $root]} {error "Nonisolated root"}
open_project [file join $root csim project]
set_top vit_block_top
add_files -tb [file join $root testbench.cpp] -cflags "-std=c++14 -I$root/src"
foreach name {weights.bin input_dma.bin expected.bin} {
    add_files -tb [file join $fixture $name]
}
open_solution solution1 -flow_target vivado
set_part {xczu9eg-ffvb1156-2-e}
create_clock -period 3
csim_design -clean
exit
