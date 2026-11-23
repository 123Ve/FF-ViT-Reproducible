# Run with FVIT_HLS_ROOT and FVIT_HLS_SAMPLE absolute paths.
set root $::env(FVIT_HLS_ROOT)
set sample $::env(FVIT_HLS_SAMPLE)
open_project -reset "$root/build/project"
set_top vit_block_top
# C-simulation-only harness: this single TU includes the unmodified block0.cpp.
# Do not separately compile block0.cpp, which would duplicate its definitions.
add_files -tb "$root/testbench.cpp" -cflags "-std=c++14 -I$root/src"
foreach name {weights.bin input.bin output.bin} {
    add_files -tb "$sample/$name"
}
open_solution -reset solution1 -flow_target vivado
set_part {xczu9eg-ffvb1156-2-e}
create_clock -period 5
csim_design -clean
exit
