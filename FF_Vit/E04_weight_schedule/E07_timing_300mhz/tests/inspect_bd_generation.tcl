set root [file normalize [file join [file dirname [info script]] ..]]
open_project [file join $root vivado_atten e07.xpr]
set bd [get_files */design_1.bd]
puts "BD_GENERATION file=$bd mode=[get_property SYNTH_CHECKPOINT_MODE $bd] enabled=[get_property GENERATE_SYNTH_CHECKPOINT $bd]"
puts "BD_RUNS [get_runs]"
foreach ip [get_ips] {
    set ip_file [get_property IP_FILE $ip]
    puts "IP_GENERATION $ip enabled=[get_property GENERATE_SYNTH_CHECKPOINT [get_files $ip_file]]"
}
close_project
exit
