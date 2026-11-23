set root [file normalize [lindex $argv 0]]
if {![string match */validation/u3_full_board_test_20261014/outputs/*/hardware $root]} {error "Nonisolated root"}
source -notrace /opt/vivado/2025.1/Vitis/common/scripts/ipxhls.tcl
set src_dir [file join $root hls work hls]
set ip_out_dir [file join $src_dir impl ip]
set data_file [file join $src_dir hls_data.json]
if {[file exists [file join $ip_out_dir component.xml]]} {error "Refusing overwrite"}
::ipx::utils::package_hls_ip $ip_out_dir $data_file {vitis sysgen} $src_dir {}
exit
