# Read only the completed E07 checkpoint; no synthesis, optimization or implementation.
set root [file normalize [file join [file dirname [info script]] ..]]
set out [file join $root results paper_evidence]
set checkpoint [file join $root vivado_candidate05 e07.runs impl_1 design_1_wrapper_postroute_physopt.dcp]
open_checkpoint $checkpoint
set f [open [file join $out E07_BRAM_Cells.csv] {WRONLY CREAT EXCL}]
puts $f "cell,primitive"
foreach c [get_cells -hier -filter {REF_NAME == RAMB18E2 || REF_NAME == RAMB36E2}] {
    puts $f "[get_property NAME $c],[get_property REF_NAME $c]"
}
close $f
set f [open [file join $out E07_DSP_Cells.csv] {WRONLY CREAT EXCL}]
puts $f "cell,primitive"
foreach c [get_cells -hier -filter {REF_NAME == DSP48E2}] {
    puts $f "[get_property NAME $c],[get_property REF_NAME $c]"
}
close $f
report_utilization -hierarchical -hierarchical_depth 8 -file [file join $out E07_Utilization_Hierarchical.rpt]
close_design
exit
