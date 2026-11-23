   
    parameter PROC_NUM = 74;
    parameter ST_IDLE = 3'b000;
    parameter ST_FILTER_FAKE = 3'b001;
    parameter ST_DL_DETECTED = 3'b010;
    parameter ST_DL_REPORT = 3'b100;
   

    reg [2:0] CS_fsm;
    reg [2:0] NS_fsm;
    reg [PROC_NUM - 1:0] dl_detect_reg;
    reg [PROC_NUM - 1:0] dl_done_reg;
    reg [PROC_NUM - 1:0] origin_reg;
    reg [PROC_NUM - 1:0] dl_in_vec_reg;
    reg [31:0] dl_keep_cnt;
    reg stop_report_path;
    reg [PROC_NUM - 1:0] reported_proc;
    integer i;
    integer fp;

    always @ (negedge dl_reset or posedge dl_clock) begin
        if (~dl_reset) begin
            reported_proc <= 'b0;
        end
        else if (CS_fsm == ST_DL_REPORT) begin
            reported_proc <= reported_proc | dl_in_vec;
        end
        else if (CS_fsm == ST_DL_DETECTED) begin
            reported_proc <= 'b0;
        end
    end

    always @ (negedge dl_reset or posedge dl_clock) begin
        if (~dl_reset) begin
            stop_report_path <= 1'b0;
        end
        else if (CS_fsm == ST_DL_REPORT && (|(dl_in_vec & reported_proc))) begin
            stop_report_path <= 1'b1;
        end
        else if (CS_fsm == ST_IDLE) begin
            stop_report_path <= 1'b0;
        end
    end

    // FSM State machine
    always @ (negedge dl_reset or posedge dl_clock) begin
        if (~dl_reset) begin
            CS_fsm <= ST_IDLE;
        end
        else begin
            CS_fsm <= NS_fsm;
        end
    end

    always @ (CS_fsm or dl_in_vec or dl_detect_reg or dl_done_reg or dl_in_vec or origin_reg or dl_keep_cnt) begin
        case (CS_fsm)
            ST_IDLE : begin
                if (|dl_in_vec) begin
                    NS_fsm = ST_FILTER_FAKE;
                end
                else begin
                    NS_fsm = ST_IDLE;
                end
            end
            ST_FILTER_FAKE: begin
                if (dl_keep_cnt >= 32'd1000) begin
                    NS_fsm = ST_DL_DETECTED;
                end
                else if (dl_detect_reg != (dl_detect_reg & dl_in_vec)) begin
                    NS_fsm = ST_IDLE;
                end
                else begin
                    NS_fsm = ST_FILTER_FAKE;
                end
            end
            ST_DL_DETECTED: begin
                // has unreported deadlock cycle
                if ((dl_detect_reg != dl_done_reg) && stop_report_path == 1'b0) begin
                    NS_fsm = ST_DL_REPORT;
                end
                else begin
                    NS_fsm = ST_DL_DETECTED;
                end
            end
            ST_DL_REPORT: begin
                if (|(dl_in_vec & origin_reg)) begin
                    NS_fsm = ST_DL_DETECTED;
                end
                // avoid report deadlock ring.
                else if (|(dl_in_vec & reported_proc)) begin
                    NS_fsm = ST_DL_DETECTED;
                end
                else begin
                    NS_fsm = ST_DL_REPORT;
                end
            end
            default: NS_fsm = ST_IDLE;
        endcase
    end

    // dl_detect_reg record the procs that first detect deadlock
    always @ (negedge dl_reset or posedge dl_clock) begin
        if (~dl_reset) begin
            dl_detect_reg <= 'b0;
        end
        else begin
            if (CS_fsm == ST_IDLE) begin
                dl_detect_reg <= dl_in_vec;
            end
        end
    end

    always @ (negedge dl_reset or posedge dl_clock) begin
        if (~dl_reset) begin
            dl_keep_cnt <= 32'h0;
        end
        else begin
            if (CS_fsm == ST_FILTER_FAKE && (dl_detect_reg == (dl_detect_reg & dl_in_vec))) begin
                dl_keep_cnt <= dl_keep_cnt + 32'h1;
            end
            else if (CS_fsm == ST_FILTER_FAKE && (dl_detect_reg != (dl_detect_reg & dl_in_vec))) begin
                dl_keep_cnt <= 32'h0;
            end
        end
    end

    // dl_detect_out keeps in high after deadlock detected
    assign dl_detect_out = (|dl_detect_reg) && (CS_fsm == ST_DL_DETECTED || CS_fsm == ST_DL_REPORT);

    // dl_done_reg record the cycles has been reported
    always @ (negedge dl_reset or posedge dl_clock) begin
        if (~dl_reset) begin
            dl_done_reg <= 'b0;
        end
        else begin
            if ((CS_fsm == ST_DL_REPORT) && (|(dl_in_vec & dl_detect_reg) == 'b1)) begin
                dl_done_reg <= dl_done_reg | dl_in_vec;
            end
        end
    end

    // clear token once a cycle is done
    assign token_clear = (CS_fsm == ST_DL_REPORT) ? ((|(dl_in_vec & origin_reg)) ? 'b1 : 'b0) : 'b0;

    // origin_reg record the current cycle start id
    always @ (negedge dl_reset or posedge dl_clock) begin
        if (~dl_reset) begin
            origin_reg <= 'b0;
        end
        else begin
            if (CS_fsm == ST_DL_DETECTED) begin
                origin_reg <= origin;
            end
        end
    end
   
    // origin will be valid for only one cycle
    wire [PROC_NUM*PROC_NUM - 1:0] origin_tmp;
    assign origin_tmp[PROC_NUM - 1:0] = (dl_detect_reg[0] & ~dl_done_reg[0]) ? 'b1 : 'b0;
    genvar j;
    generate
    for(j = 1;j < PROC_NUM;j = j + 1) begin: F1
        assign origin_tmp[j*PROC_NUM +: PROC_NUM] = (dl_detect_reg[j] & ~dl_done_reg[j]) ? ('b1 << j) : origin_tmp[(j - 1)*PROC_NUM +: PROC_NUM];
    end
    endgenerate
    always @ (CS_fsm or origin_tmp) begin
        if (CS_fsm == ST_DL_DETECTED) begin
            origin = origin_tmp[(PROC_NUM - 1)*PROC_NUM +: PROC_NUM];
        end
        else begin
            origin = 'b0;
        end
    end

    
    // dl_in_vec_reg record the current cycle dl_in_vec
    always @ (negedge dl_reset or posedge dl_clock) begin
        if (~dl_reset) begin
            dl_in_vec_reg <= 'b0;
        end
        else begin
            if (CS_fsm == ST_DL_DETECTED) begin
                dl_in_vec_reg <= origin;
            end
            else if (CS_fsm == ST_DL_REPORT) begin
                dl_in_vec_reg <= dl_in_vec;
            end
        end
    end
    
    // find_df_deadlock to report the deadlock
    always @ (negedge dl_reset or posedge dl_clock) begin
        if (~dl_reset) begin
            find_df_deadlock <= 1'b0;
        end
        else begin
            if (CS_fsm == ST_DL_DETECTED && ((dl_detect_reg == dl_done_reg) || (stop_report_path == 1'b1))) begin
                find_df_deadlock <= 1'b1;
            end
            else if (CS_fsm == ST_IDLE) begin
                find_df_deadlock <= 1'b0;
            end
        end
    end
    
    // get the first valid proc index in dl vector
    function integer proc_index(input [PROC_NUM - 1:0] dl_vec);
        begin
            proc_index = 0;
            for (i = 0; i < PROC_NUM; i = i + 1) begin
                if (dl_vec[i]) begin
                    proc_index = i;
                end
            end
        end
    endfunction

    // get the proc path based on dl vector
    function [1224:0] proc_path(input [PROC_NUM - 1:0] dl_vec);
        integer index;
        begin
            index = proc_index(dl_vec);
            case (index)
                0 : begin
                    proc_path = "vit_block_top_vit_block_top.grp_initial_overlap_wrapper_fu_5704.task_run_pe_U0";
                end
                1 : begin
                    proc_path = "vit_block_top_vit_block_top.grp_initial_overlap_wrapper_fu_5704.task_run_pe_U0.task_recv_img_U0";
                end
                2 : begin
                    proc_path = "vit_block_top_vit_block_top.grp_initial_overlap_wrapper_fu_5704.task_run_pe_U0.fixed_patch_do_patch_embed_U0";
                end
                3 : begin
                    proc_path = "vit_block_top_vit_block_top.grp_initial_overlap_wrapper_fu_5704.task_run_pe_U0.fixed_patch_do_patch_embed_U0.do_adapt_4_U0";
                end
                4 : begin
                    proc_path = "vit_block_top_vit_block_top.grp_initial_overlap_wrapper_fu_5704.task_run_pe_U0.fixed_patch_do_patch_embed_U0.fixed_patch_step2_mac_replace_shift_U0";
                end
                5 : begin
                    proc_path = "vit_block_top_vit_block_top.grp_initial_overlap_wrapper_fu_5704.task_run_pe_U0.fixed_patch_do_patch_embed_U0.do_adapt_9_1_U0";
                end
                6 : begin
                    proc_path = "vit_block_top_vit_block_top.grp_initial_overlap_wrapper_fu_5704.task_run_pe_U0.task_write_pe_to_fm_U0";
                end
                7 : begin
                    proc_path = "vit_block_top_vit_block_top.grp_initial_overlap_wrapper_fu_5704.task_load_weights_U0";
                end
                8 : begin
                    proc_path = "vit_block_top_vit_block_top.grp_dataflow_wrapper_fu_6443.task_read_fm_split_U0";
                end
                9 : begin
                    proc_path = "vit_block_top_vit_block_top.grp_dataflow_wrapper_fu_6443.dataflow_wrapper_Block_entry_calc_weights_attn_weights_attn_scalars_rd_calc_weig_U0";
                end
                10 : begin
                    proc_path = "vit_block_top_vit_block_top.grp_dataflow_wrapper_fu_6443.task_compute_attn_U0";
                end
                11 : begin
                    proc_path = "vit_block_top_vit_block_top.grp_dataflow_wrapper_fu_6443.task_compute_attn_U0.grp_do_attn_1_fu_5150.do_adapt_10_U0";
                end
                12 : begin
                    proc_path = "vit_block_top_vit_block_top.grp_dataflow_wrapper_fu_6443.task_compute_attn_U0.grp_do_attn_1_fu_5150.do_adapt_7_U0";
                end
                13 : begin
                    proc_path = "vit_block_top_vit_block_top.grp_dataflow_wrapper_fu_6443.task_compute_attn_U0.grp_do_attn_1_fu_5150.do_layernorm_inter_token_1_U0";
                end
                14 : begin
                    proc_path = "vit_block_top_vit_block_top.grp_dataflow_wrapper_fu_6443.task_compute_attn_U0.grp_do_attn_1_fu_5150.stream_copy3_U0";
                end
                15 : begin
                    proc_path = "vit_block_top_vit_block_top.grp_dataflow_wrapper_fu_6443.task_compute_attn_U0.grp_do_attn_1_fu_5150.do_matmul_2_U0";
                end
                16 : begin
                    proc_path = "vit_block_top_vit_block_top.grp_dataflow_wrapper_fu_6443.task_compute_attn_U0.grp_do_attn_1_fu_5150.do_matmul_2_U0.do_adapt_2_U0";
                end
                17 : begin
                    proc_path = "vit_block_top_vit_block_top.grp_dataflow_wrapper_fu_6443.task_compute_attn_U0.grp_do_attn_1_fu_5150.do_matmul_2_U0.matmul_step1_cache_window_2_U0";
                end
                18 : begin
                    proc_path = "vit_block_top_vit_block_top.grp_dataflow_wrapper_fu_6443.task_compute_attn_U0.grp_do_attn_1_fu_5150.do_matmul_2_U0.matmul_step2_mac_2_U0";
                end
                19 : begin
                    proc_path = "vit_block_top_vit_block_top.grp_dataflow_wrapper_fu_6443.task_compute_attn_U0.grp_do_attn_1_fu_5150.do_matmul_2_U0.do_adapt_11_U0";
                end
                20 : begin
                    proc_path = "vit_block_top_vit_block_top.grp_dataflow_wrapper_fu_6443.task_compute_attn_U0.grp_do_attn_1_fu_5150.do_matmul_2_1_U0";
                end
                21 : begin
                    proc_path = "vit_block_top_vit_block_top.grp_dataflow_wrapper_fu_6443.task_compute_attn_U0.grp_do_attn_1_fu_5150.do_matmul_2_1_U0.do_adapt_9_U0";
                end
                22 : begin
                    proc_path = "vit_block_top_vit_block_top.grp_dataflow_wrapper_fu_6443.task_compute_attn_U0.grp_do_attn_1_fu_5150.do_matmul_2_1_U0.matmul_step1_cache_window_10_U0";
                end
                23 : begin
                    proc_path = "vit_block_top_vit_block_top.grp_dataflow_wrapper_fu_6443.task_compute_attn_U0.grp_do_attn_1_fu_5150.do_matmul_2_1_U0.matmul_step2_mac_11_U0";
                end
                24 : begin
                    proc_path = "vit_block_top_vit_block_top.grp_dataflow_wrapper_fu_6443.task_compute_attn_U0.grp_do_attn_1_fu_5150.do_matmul_2_1_U0.do_adapt_12_1_U0";
                end
                25 : begin
                    proc_path = "vit_block_top_vit_block_top.grp_dataflow_wrapper_fu_6443.task_compute_attn_U0.grp_do_attn_1_fu_5150.do_matmul_4_U0";
                end
                26 : begin
                    proc_path = "vit_block_top_vit_block_top.grp_dataflow_wrapper_fu_6443.task_compute_attn_U0.grp_do_attn_1_fu_5150.do_matmul_4_U0.do_adapt_13_U0";
                end
                27 : begin
                    proc_path = "vit_block_top_vit_block_top.grp_dataflow_wrapper_fu_6443.task_compute_attn_U0.grp_do_attn_1_fu_5150.do_matmul_4_U0.matmul_step1_cache_window_4_U0";
                end
                28 : begin
                    proc_path = "vit_block_top_vit_block_top.grp_dataflow_wrapper_fu_6443.task_compute_attn_U0.grp_do_attn_1_fu_5150.do_matmul_4_U0.matmul_step2_mac_4_U0";
                end
                29 : begin
                    proc_path = "vit_block_top_vit_block_top.grp_dataflow_wrapper_fu_6443.task_compute_attn_U0.grp_do_attn_1_fu_5150.do_matmul_4_U0.do_adapt_13_1_U0";
                end
                30 : begin
                    proc_path = "vit_block_top_vit_block_top.grp_dataflow_wrapper_fu_6443.task_compute_attn_U0.grp_do_attn_1_fu_5150.do_quant_U0";
                end
                31 : begin
                    proc_path = "vit_block_top_vit_block_top.grp_dataflow_wrapper_fu_6443.task_compute_attn_U0.grp_do_attn_1_fu_5150.do_quant_3_U0";
                end
                32 : begin
                    proc_path = "vit_block_top_vit_block_top.grp_dataflow_wrapper_fu_6443.task_compute_attn_U0.grp_do_attn_1_fu_5150.do_quant_1_U0";
                end
                33 : begin
                    proc_path = "vit_block_top_vit_block_top.grp_dataflow_wrapper_fu_6443.task_compute_attn_U0.grp_do_attn_1_fu_5150.do_split_4_U0";
                end
                34 : begin
                    proc_path = "vit_block_top_vit_block_top.grp_dataflow_wrapper_fu_6443.task_compute_attn_U0.grp_do_attn_1_fu_5150.do_split_5_U0";
                end
                35 : begin
                    proc_path = "vit_block_top_vit_block_top.grp_dataflow_wrapper_fu_6443.task_compute_attn_U0.grp_do_attn_1_fu_5150.do_split_U0";
                end
                36 : begin
                    proc_path = "vit_block_top_vit_block_top.grp_dataflow_wrapper_fu_6443.task_compute_attn_U0.grp_do_attn_1_fu_5150.do_attn_6_U0";
                end
                37 : begin
                    proc_path = "vit_block_top_vit_block_top.grp_dataflow_wrapper_fu_6443.task_compute_attn_U0.grp_do_attn_1_fu_5150.do_attn_7_U0";
                end
                38 : begin
                    proc_path = "vit_block_top_vit_block_top.grp_dataflow_wrapper_fu_6443.task_compute_attn_U0.grp_do_attn_1_fu_5150.do_attn_U0";
                end
                39 : begin
                    proc_path = "vit_block_top_vit_block_top.grp_dataflow_wrapper_fu_6443.task_compute_attn_U0.grp_do_attn_1_fu_5150.do_merge_U0";
                end
                40 : begin
                    proc_path = "vit_block_top_vit_block_top.grp_dataflow_wrapper_fu_6443.task_compute_attn_U0.grp_do_attn_1_fu_5150.do_quant_2_U0";
                end
                41 : begin
                    proc_path = "vit_block_top_vit_block_top.grp_dataflow_wrapper_fu_6443.task_compute_attn_U0.grp_do_attn_1_fu_5150.do_matmul_1_U0";
                end
                42 : begin
                    proc_path = "vit_block_top_vit_block_top.grp_dataflow_wrapper_fu_6443.task_compute_attn_U0.grp_do_attn_1_fu_5150.do_matmul_1_U0.do_adapt_1_U0";
                end
                43 : begin
                    proc_path = "vit_block_top_vit_block_top.grp_dataflow_wrapper_fu_6443.task_compute_attn_U0.grp_do_attn_1_fu_5150.do_matmul_1_U0.matmul_step1_cache_window_1_U0";
                end
                44 : begin
                    proc_path = "vit_block_top_vit_block_top.grp_dataflow_wrapper_fu_6443.task_compute_attn_U0.grp_do_attn_1_fu_5150.do_matmul_1_U0.matmul_step2_mac_1_U0";
                end
                45 : begin
                    proc_path = "vit_block_top_vit_block_top.grp_dataflow_wrapper_fu_6443.task_compute_attn_U0.grp_do_attn_1_fu_5150.do_matmul_1_U0.do_adapt_8_1_U0";
                end
                46 : begin
                    proc_path = "vit_block_top_vit_block_top.grp_dataflow_wrapper_fu_6443.task_compute_attn_U0.grp_do_attn_1_fu_5150.stream_merge_1_U0";
                end
                47 : begin
                    proc_path = "vit_block_top_vit_block_top.grp_dataflow_wrapper_fu_6443.task_stream_cast_U0";
                end
                48 : begin
                    proc_path = "vit_block_top_vit_block_top.grp_dataflow_wrapper_fu_6443.task_compute_mlp_U0";
                end
                49 : begin
                    proc_path = "vit_block_top_vit_block_top.grp_dataflow_wrapper_fu_6443.task_compute_mlp_U0.grp_do_mlp_fu_4710.stream_copy_U0";
                end
                50 : begin
                    proc_path = "vit_block_top_vit_block_top.grp_dataflow_wrapper_fu_6443.task_compute_mlp_U0.grp_do_mlp_fu_4710.do_adapt_6_U0";
                end
                51 : begin
                    proc_path = "vit_block_top_vit_block_top.grp_dataflow_wrapper_fu_6443.task_compute_mlp_U0.grp_do_mlp_fu_4710.do_adapt_5_U0";
                end
                52 : begin
                    proc_path = "vit_block_top_vit_block_top.grp_dataflow_wrapper_fu_6443.task_compute_mlp_U0.grp_do_mlp_fu_4710.do_layernorm_inter_token_U0";
                end
                53 : begin
                    proc_path = "vit_block_top_vit_block_top.grp_dataflow_wrapper_fu_6443.task_compute_mlp_U0.grp_do_mlp_fu_4710.do_matmul_3_U0";
                end
                54 : begin
                    proc_path = "vit_block_top_vit_block_top.grp_dataflow_wrapper_fu_6443.task_compute_mlp_U0.grp_do_mlp_fu_4710.do_matmul_3_U0.do_adapt_1_1_U0";
                end
                55 : begin
                    proc_path = "vit_block_top_vit_block_top.grp_dataflow_wrapper_fu_6443.task_compute_mlp_U0.grp_do_mlp_fu_4710.do_matmul_3_U0.matmul_step1_cache_window_3_U0";
                end
                56 : begin
                    proc_path = "vit_block_top_vit_block_top.grp_dataflow_wrapper_fu_6443.task_compute_mlp_U0.grp_do_mlp_fu_4710.do_matmul_3_U0.matmul_step2_mac_3_U0";
                end
                57 : begin
                    proc_path = "vit_block_top_vit_block_top.grp_dataflow_wrapper_fu_6443.task_compute_mlp_U0.grp_do_mlp_fu_4710.do_matmul_3_U0.do_adapt_12_U0";
                end
                58 : begin
                    proc_path = "vit_block_top_vit_block_top.grp_dataflow_wrapper_fu_6443.task_compute_mlp_U0.grp_do_mlp_fu_4710.do_gelu_U0";
                end
                59 : begin
                    proc_path = "vit_block_top_vit_block_top.grp_dataflow_wrapper_fu_6443.task_compute_mlp_U0.grp_do_mlp_fu_4710.do_matmul_U0";
                end
                60 : begin
                    proc_path = "vit_block_top_vit_block_top.grp_dataflow_wrapper_fu_6443.task_compute_mlp_U0.grp_do_mlp_fu_4710.do_matmul_U0.do_adapt_U0";
                end
                61 : begin
                    proc_path = "vit_block_top_vit_block_top.grp_dataflow_wrapper_fu_6443.task_compute_mlp_U0.grp_do_mlp_fu_4710.do_matmul_U0.matmul_step1_cache_window_U0";
                end
                62 : begin
                    proc_path = "vit_block_top_vit_block_top.grp_dataflow_wrapper_fu_6443.task_compute_mlp_U0.grp_do_mlp_fu_4710.do_matmul_U0.matmul_step2_mac_U0";
                end
                63 : begin
                    proc_path = "vit_block_top_vit_block_top.grp_dataflow_wrapper_fu_6443.task_compute_mlp_U0.grp_do_mlp_fu_4710.do_matmul_U0.do_adapt_8_U0";
                end
                64 : begin
                    proc_path = "vit_block_top_vit_block_top.grp_dataflow_wrapper_fu_6443.task_compute_mlp_U0.grp_do_mlp_fu_4710.stream_merge_U0";
                end
                65 : begin
                    proc_path = "vit_block_top_vit_block_top.grp_dataflow_wrapper_fu_6443.task_write_fm_U0";
                end
                66 : begin
                    proc_path = "vit_block_top_vit_block_top.grp_dataflow_wrapper_fu_6443.task_load_weights_14_U0";
                end
                67 : begin
                    proc_path = "vit_block_top_vit_block_top.grp_task_run_head_fu_11440.task_read_cls_fm_U0";
                end
                68 : begin
                    proc_path = "vit_block_top_vit_block_top.grp_task_run_head_fu_11440.fixed_head_do_head_U0";
                end
                69 : begin
                    proc_path = "vit_block_top_vit_block_top.grp_task_run_head_fu_11440.fixed_head_do_head_U0.fixed_head_layernorm_U0";
                end
                70 : begin
                    proc_path = "vit_block_top_vit_block_top.grp_task_run_head_fu_11440.fixed_head_do_head_U0.fixed_head_matmul_U0";
                end
                71 : begin
                    proc_path = "vit_block_top_vit_block_top.grp_task_run_head_fu_11440.fixed_head_do_head_U0.fixed_head_matmul_U0.fixed_head_matmul_core_U0";
                end
                72 : begin
                    proc_path = "vit_block_top_vit_block_top.grp_task_run_head_fu_11440.fixed_head_do_head_U0.fixed_head_matmul_U0.do_adapt_3_U0";
                end
                73 : begin
                    proc_path = "vit_block_top_vit_block_top.grp_task_run_head_fu_11440.task_write_logits_U0";
                end
                default : begin
                    proc_path = "unknown";
                end
            endcase
        end
    endfunction

    // print the headlines of deadlock detection
    task print_dl_head;
        begin
            $display("\n//////////////////////////////////////////////////////////////////////////////");
            $display("// ERROR!!! DEADLOCK DETECTED at %0t ns! SIMULATION WILL BE STOPPED! //", $time);
            $display("//////////////////////////////////////////////////////////////////////////////");
            fp = $fopen("deadlock_db.dat", "w");
        end
    endtask

    // print the start of a cycle
    task print_cycle_start(input reg [1224:0] proc_path, input integer cycle_id);
        begin
            $display("/////////////////////////");
            $display("// Dependence cycle %0d:", cycle_id);
            $display("// (1): Process: %0s", proc_path);
            $fdisplay(fp, "Dependence_Cycle_ID %0d", cycle_id);
            $fdisplay(fp, "Dependence_Process_ID 1");
            $fdisplay(fp, "Dependence_Process_path %0s", proc_path);
        end
    endtask

    // print the end of deadlock detection
    task print_dl_end(input integer num, input integer record_time);
        begin
            $display("////////////////////////////////////////////////////////////////////////");
            $display("// Totally %0d cycles detected!", num);
            $display("////////////////////////////////////////////////////////////////////////");
            $display("// ERROR!!! DEADLOCK DETECTED at %0t ns! SIMULATION WILL BE STOPPED! //", record_time);
            $display("//////////////////////////////////////////////////////////////////////////////");
            $fdisplay(fp, "Dependence_Cycle_Number %0d", num);
            $fclose(fp);
        end
    endtask

    // print one proc component in the cycle
    task print_cycle_proc_comp(input reg [1224:0] proc_path, input integer cycle_comp_id);
        begin
            $display("// (%0d): Process: %0s", cycle_comp_id, proc_path);
            $fdisplay(fp, "Dependence_Process_ID %0d", cycle_comp_id);
            $fdisplay(fp, "Dependence_Process_path %0s", proc_path);
        end
    endtask

    // print one channel component in the cycle
    task print_cycle_chan_comp(input [PROC_NUM - 1:0] dl_vec1, input [PROC_NUM - 1:0] dl_vec2);
        reg [1320:0] chan_path;
        integer index1;
        integer index2;
        begin
            index1 = proc_index(dl_vec1);
            index2 = proc_index(dl_vec2);
            case (index1)
                0 : begin // for proc 'vit_block_top_vit_block_top.grp_initial_overlap_wrapper_fu_5704.task_run_pe_U0'
                    case(index2)
                    7: begin //  for dep proc 'vit_block_top_vit_block_top.grp_initial_overlap_wrapper_fu_5704.task_load_weights_U0'
// for dep channel '' info is :
// blk sig is {{vit_block_top_vit_block_top_inst.grp_initial_overlap_wrapper_fu_5704.ap_sync_task_run_pe_U0_ap_ready & vit_block_top_vit_block_top_inst.grp_initial_overlap_wrapper_fu_5704.task_run_pe_U0.ap_idle & ~vit_block_top_vit_block_top_inst.grp_initial_overlap_wrapper_fu_5704.ap_sync_task_load_weights_U0_ap_ready} input_sync} {{ap_done_reg_3 & vit_block_top_vit_block_top_inst.grp_initial_overlap_wrapper_fu_5704.task_run_pe_U0.ap_done & ~vit_block_top_vit_block_top_inst.grp_initial_overlap_wrapper_fu_5704.task_load_weights_U0.ap_done} output_sync}
                        if ((grp_initial_overlap_wrapper_fu_5704.ap_sync_task_run_pe_U0_ap_ready & grp_initial_overlap_wrapper_fu_5704.task_run_pe_U0.ap_idle & ~grp_initial_overlap_wrapper_fu_5704.ap_sync_task_load_weights_U0_ap_ready) | (ap_done_reg_3 & grp_initial_overlap_wrapper_fu_5704.task_run_pe_U0.ap_done & ~grp_initial_overlap_wrapper_fu_5704.task_load_weights_U0.ap_done)) begin
                            $display("//      Blocked by input sync logic with process : 'vit_block_top_vit_block_top.grp_initial_overlap_wrapper_fu_5704.task_load_weights_U0'");
                        end
                    end
                    endcase
                end
                1 : begin // for proc 'vit_block_top_vit_block_top.grp_initial_overlap_wrapper_fu_5704.task_run_pe_U0.task_recv_img_U0'
                    case(index2)
                    2: begin //  for dep proc 'vit_block_top_vit_block_top.grp_initial_overlap_wrapper_fu_5704.task_run_pe_U0.fixed_patch_do_patch_embed_U0'
// for dep channel 'vit_block_top_vit_block_top.grp_initial_overlap_wrapper_fu_5704.task_run_pe_U0.img_sm_U' info is :
// blk sig is {~vit_block_top_vit_block_top_inst.grp_initial_overlap_wrapper_fu_5704.task_run_pe_U0.task_recv_img_U0.img_sm_blk_n data_FIFO}
                        if ((~grp_initial_overlap_wrapper_fu_5704.task_run_pe_U0.task_recv_img_U0.img_sm_blk_n)) begin
                            if (~grp_initial_overlap_wrapper_fu_5704.task_run_pe_U0.img_sm_U.if_empty_n) begin
                                $display("//      Blocked by empty input FIFO 'vit_block_top_vit_block_top.grp_initial_overlap_wrapper_fu_5704.task_run_pe_U0.img_sm_U' written by process 'vit_block_top_vit_block_top.grp_initial_overlap_wrapper_fu_5704.task_run_pe_U0.fixed_patch_do_patch_embed_U0'");
                                $fdisplay(fp, "Dependence_Channel_path vit_block_top_vit_block_top.grp_initial_overlap_wrapper_fu_5704.task_run_pe_U0.img_sm_U");
                                $fdisplay(fp, "Dependence_Channel_status EMPTY");
                            end
                            else if (~grp_initial_overlap_wrapper_fu_5704.task_run_pe_U0.img_sm_U.if_full_n) begin
                                $display("//      Blocked by full output FIFO 'vit_block_top_vit_block_top.grp_initial_overlap_wrapper_fu_5704.task_run_pe_U0.img_sm_U' read by process 'vit_block_top_vit_block_top.grp_initial_overlap_wrapper_fu_5704.task_run_pe_U0.fixed_patch_do_patch_embed_U0'");
                                $fdisplay(fp, "Dependence_Channel_path vit_block_top_vit_block_top.grp_initial_overlap_wrapper_fu_5704.task_run_pe_U0.img_sm_U");
                                $fdisplay(fp, "Dependence_Channel_status FULL");
                            end
                        end
// for dep channel 'vit_block_top_vit_block_top.grp_initial_overlap_wrapper_fu_5704.task_run_pe_U0.start_for_fixed_patch_do_patch_embed_U0_U' info is :
// blk sig is {{~vit_block_top_vit_block_top_inst.grp_initial_overlap_wrapper_fu_5704.task_run_pe_U0.start_for_fixed_patch_do_patch_embed_U0_U.if_full_n & vit_block_top_vit_block_top_inst.grp_initial_overlap_wrapper_fu_5704.task_run_pe_U0.task_recv_img_U0.ap_start & ~vit_block_top_vit_block_top_inst.grp_initial_overlap_wrapper_fu_5704.task_run_pe_U0.task_recv_img_U0.real_start & (trans_in_cnt_0 == trans_out_cnt_0) & ~vit_block_top_vit_block_top_inst.grp_initial_overlap_wrapper_fu_5704.task_run_pe_U0.start_for_fixed_patch_do_patch_embed_U0_U.if_read} start_FIFO}
                        if ((~grp_initial_overlap_wrapper_fu_5704.task_run_pe_U0.start_for_fixed_patch_do_patch_embed_U0_U.if_full_n & grp_initial_overlap_wrapper_fu_5704.task_run_pe_U0.task_recv_img_U0.ap_start & ~grp_initial_overlap_wrapper_fu_5704.task_run_pe_U0.task_recv_img_U0.real_start & (trans_in_cnt_0 == trans_out_cnt_0) & ~grp_initial_overlap_wrapper_fu_5704.task_run_pe_U0.start_for_fixed_patch_do_patch_embed_U0_U.if_read)) begin
                            $display("//      Blocked by full output start propagation FIFO 'vit_block_top_vit_block_top.grp_initial_overlap_wrapper_fu_5704.task_run_pe_U0.start_for_fixed_patch_do_patch_embed_U0_U' read by process 'vit_block_top_vit_block_top.grp_initial_overlap_wrapper_fu_5704.task_run_pe_U0.fixed_patch_do_patch_embed_U0',");
                        end
                    end
                    3: begin //  for dep proc 'vit_block_top_vit_block_top.grp_initial_overlap_wrapper_fu_5704.task_run_pe_U0.fixed_patch_do_patch_embed_U0.do_adapt_4_U0'
// for dep channel 'vit_block_top_vit_block_top.grp_initial_overlap_wrapper_fu_5704.task_run_pe_U0.img_sm_U' info is :
// blk sig is {~vit_block_top_vit_block_top_inst.grp_initial_overlap_wrapper_fu_5704.task_run_pe_U0.task_recv_img_U0.img_sm_blk_n data_FIFO}
                        if ((~grp_initial_overlap_wrapper_fu_5704.task_run_pe_U0.task_recv_img_U0.img_sm_blk_n)) begin
                            if (~grp_initial_overlap_wrapper_fu_5704.task_run_pe_U0.img_sm_U.if_empty_n) begin
                                $display("//      Blocked by empty input FIFO 'vit_block_top_vit_block_top.grp_initial_overlap_wrapper_fu_5704.task_run_pe_U0.img_sm_U' written by process 'vit_block_top_vit_block_top.grp_initial_overlap_wrapper_fu_5704.task_run_pe_U0.fixed_patch_do_patch_embed_U0.do_adapt_4_U0'");
                                $fdisplay(fp, "Dependence_Channel_path vit_block_top_vit_block_top.grp_initial_overlap_wrapper_fu_5704.task_run_pe_U0.img_sm_U");
                                $fdisplay(fp, "Dependence_Channel_status EMPTY");
                            end
                            else if (~grp_initial_overlap_wrapper_fu_5704.task_run_pe_U0.img_sm_U.if_full_n) begin
                                $display("//      Blocked by full output FIFO 'vit_block_top_vit_block_top.grp_initial_overlap_wrapper_fu_5704.task_run_pe_U0.img_sm_U' read by process 'vit_block_top_vit_block_top.grp_initial_overlap_wrapper_fu_5704.task_run_pe_U0.fixed_patch_do_patch_embed_U0.do_adapt_4_U0'");
                                $fdisplay(fp, "Dependence_Channel_path vit_block_top_vit_block_top.grp_initial_overlap_wrapper_fu_5704.task_run_pe_U0.img_sm_U");
                                $fdisplay(fp, "Dependence_Channel_status FULL");
                            end
                        end
                    end
                    endcase
                end
                2 : begin // for proc 'vit_block_top_vit_block_top.grp_initial_overlap_wrapper_fu_5704.task_run_pe_U0.fixed_patch_do_patch_embed_U0'
                    case(index2)
                    1: begin //  for dep proc 'vit_block_top_vit_block_top.grp_initial_overlap_wrapper_fu_5704.task_run_pe_U0.task_recv_img_U0'
// for dep channel 'vit_block_top_vit_block_top.grp_initial_overlap_wrapper_fu_5704.task_run_pe_U0.img_sm_U' info is :
// blk sig is {~vit_block_top_vit_block_top_inst.grp_initial_overlap_wrapper_fu_5704.task_run_pe_U0.fixed_patch_do_patch_embed_U0.do_adapt_4_U0.img_sm_blk_n data_FIFO}
                        if ((~grp_initial_overlap_wrapper_fu_5704.task_run_pe_U0.fixed_patch_do_patch_embed_U0.do_adapt_4_U0.img_sm_blk_n)) begin
                            if (~grp_initial_overlap_wrapper_fu_5704.task_run_pe_U0.img_sm_U.if_empty_n) begin
                                $display("//      Blocked by empty input FIFO 'vit_block_top_vit_block_top.grp_initial_overlap_wrapper_fu_5704.task_run_pe_U0.img_sm_U' written by process 'vit_block_top_vit_block_top.grp_initial_overlap_wrapper_fu_5704.task_run_pe_U0.task_recv_img_U0'");
                                $fdisplay(fp, "Dependence_Channel_path vit_block_top_vit_block_top.grp_initial_overlap_wrapper_fu_5704.task_run_pe_U0.img_sm_U");
                                $fdisplay(fp, "Dependence_Channel_status EMPTY");
                            end
                            else if (~grp_initial_overlap_wrapper_fu_5704.task_run_pe_U0.img_sm_U.if_full_n) begin
                                $display("//      Blocked by full output FIFO 'vit_block_top_vit_block_top.grp_initial_overlap_wrapper_fu_5704.task_run_pe_U0.img_sm_U' read by process 'vit_block_top_vit_block_top.grp_initial_overlap_wrapper_fu_5704.task_run_pe_U0.task_recv_img_U0'");
                                $fdisplay(fp, "Dependence_Channel_path vit_block_top_vit_block_top.grp_initial_overlap_wrapper_fu_5704.task_run_pe_U0.img_sm_U");
                                $fdisplay(fp, "Dependence_Channel_status FULL");
                            end
                        end
// for dep channel 'vit_block_top_vit_block_top.grp_initial_overlap_wrapper_fu_5704.task_run_pe_U0.start_for_fixed_patch_do_patch_embed_U0_U' info is :
// blk sig is {{~vit_block_top_vit_block_top_inst.grp_initial_overlap_wrapper_fu_5704.task_run_pe_U0.start_for_fixed_patch_do_patch_embed_U0_U.if_empty_n & vit_block_top_vit_block_top_inst.grp_initial_overlap_wrapper_fu_5704.task_run_pe_U0.fixed_patch_do_patch_embed_U0.ap_idle & ~vit_block_top_vit_block_top_inst.grp_initial_overlap_wrapper_fu_5704.task_run_pe_U0.start_for_fixed_patch_do_patch_embed_U0_U.if_write} start_FIFO}
                        if ((~grp_initial_overlap_wrapper_fu_5704.task_run_pe_U0.start_for_fixed_patch_do_patch_embed_U0_U.if_empty_n & grp_initial_overlap_wrapper_fu_5704.task_run_pe_U0.fixed_patch_do_patch_embed_U0.ap_idle & ~grp_initial_overlap_wrapper_fu_5704.task_run_pe_U0.start_for_fixed_patch_do_patch_embed_U0_U.if_write)) begin
                            $display("//      Blocked by missing 'ap_start' from start propagation FIFO 'vit_block_top_vit_block_top.grp_initial_overlap_wrapper_fu_5704.task_run_pe_U0.start_for_fixed_patch_do_patch_embed_U0_U' written by process 'vit_block_top_vit_block_top.grp_initial_overlap_wrapper_fu_5704.task_run_pe_U0.task_recv_img_U0',");
                        end
                    end
                    6: begin //  for dep proc 'vit_block_top_vit_block_top.grp_initial_overlap_wrapper_fu_5704.task_run_pe_U0.task_write_pe_to_fm_U0'
// for dep channel 'vit_block_top_vit_block_top.grp_initial_overlap_wrapper_fu_5704.task_run_pe_U0.pe_out_sm_U' info is :
// blk sig is {~vit_block_top_vit_block_top_inst.grp_initial_overlap_wrapper_fu_5704.task_run_pe_U0.fixed_patch_do_patch_embed_U0.do_adapt_9_1_U0.pe_out_sm_blk_n data_FIFO}
                        if ((~grp_initial_overlap_wrapper_fu_5704.task_run_pe_U0.fixed_patch_do_patch_embed_U0.do_adapt_9_1_U0.pe_out_sm_blk_n)) begin
                            if (~grp_initial_overlap_wrapper_fu_5704.task_run_pe_U0.pe_out_sm_U.if_empty_n) begin
                                $display("//      Blocked by empty input FIFO 'vit_block_top_vit_block_top.grp_initial_overlap_wrapper_fu_5704.task_run_pe_U0.pe_out_sm_U' written by process 'vit_block_top_vit_block_top.grp_initial_overlap_wrapper_fu_5704.task_run_pe_U0.task_write_pe_to_fm_U0'");
                                $fdisplay(fp, "Dependence_Channel_path vit_block_top_vit_block_top.grp_initial_overlap_wrapper_fu_5704.task_run_pe_U0.pe_out_sm_U");
                                $fdisplay(fp, "Dependence_Channel_status EMPTY");
                            end
                            else if (~grp_initial_overlap_wrapper_fu_5704.task_run_pe_U0.pe_out_sm_U.if_full_n) begin
                                $display("//      Blocked by full output FIFO 'vit_block_top_vit_block_top.grp_initial_overlap_wrapper_fu_5704.task_run_pe_U0.pe_out_sm_U' read by process 'vit_block_top_vit_block_top.grp_initial_overlap_wrapper_fu_5704.task_run_pe_U0.task_write_pe_to_fm_U0'");
                                $fdisplay(fp, "Dependence_Channel_path vit_block_top_vit_block_top.grp_initial_overlap_wrapper_fu_5704.task_run_pe_U0.pe_out_sm_U");
                                $fdisplay(fp, "Dependence_Channel_status FULL");
                            end
                        end
// for dep channel 'vit_block_top_vit_block_top.grp_initial_overlap_wrapper_fu_5704.task_run_pe_U0.start_for_task_write_pe_to_fm_U0_U' info is :
// blk sig is {{~vit_block_top_vit_block_top_inst.grp_initial_overlap_wrapper_fu_5704.task_run_pe_U0.start_for_task_write_pe_to_fm_U0_U.if_full_n & vit_block_top_vit_block_top_inst.grp_initial_overlap_wrapper_fu_5704.task_run_pe_U0.fixed_patch_do_patch_embed_U0.ap_start & ~vit_block_top_vit_block_top_inst.grp_initial_overlap_wrapper_fu_5704.task_run_pe_U0.fixed_patch_do_patch_embed_U0.real_start & (trans_in_cnt_3 == trans_out_cnt_3) & ~vit_block_top_vit_block_top_inst.grp_initial_overlap_wrapper_fu_5704.task_run_pe_U0.start_for_task_write_pe_to_fm_U0_U.if_read} start_FIFO}
                        if ((~grp_initial_overlap_wrapper_fu_5704.task_run_pe_U0.start_for_task_write_pe_to_fm_U0_U.if_full_n & grp_initial_overlap_wrapper_fu_5704.task_run_pe_U0.fixed_patch_do_patch_embed_U0.ap_start & ~grp_initial_overlap_wrapper_fu_5704.task_run_pe_U0.fixed_patch_do_patch_embed_U0.real_start & (trans_in_cnt_3 == trans_out_cnt_3) & ~grp_initial_overlap_wrapper_fu_5704.task_run_pe_U0.start_for_task_write_pe_to_fm_U0_U.if_read)) begin
                            $display("//      Blocked by full output start propagation FIFO 'vit_block_top_vit_block_top.grp_initial_overlap_wrapper_fu_5704.task_run_pe_U0.start_for_task_write_pe_to_fm_U0_U' read by process 'vit_block_top_vit_block_top.grp_initial_overlap_wrapper_fu_5704.task_run_pe_U0.task_write_pe_to_fm_U0',");
                        end
                    end
                    endcase
                end
                3 : begin // for proc 'vit_block_top_vit_block_top.grp_initial_overlap_wrapper_fu_5704.task_run_pe_U0.fixed_patch_do_patch_embed_U0.do_adapt_4_U0'
                    case(index2)
                    1: begin //  for dep proc 'vit_block_top_vit_block_top.grp_initial_overlap_wrapper_fu_5704.task_run_pe_U0.task_recv_img_U0'
// for dep channel 'vit_block_top_vit_block_top.grp_initial_overlap_wrapper_fu_5704.task_run_pe_U0.img_sm_U' info is :
// blk sig is {~vit_block_top_vit_block_top_inst.grp_initial_overlap_wrapper_fu_5704.task_run_pe_U0.fixed_patch_do_patch_embed_U0.do_adapt_4_U0.img_sm_blk_n data_FIFO}
                        if ((~grp_initial_overlap_wrapper_fu_5704.task_run_pe_U0.fixed_patch_do_patch_embed_U0.do_adapt_4_U0.img_sm_blk_n)) begin
                            if (~grp_initial_overlap_wrapper_fu_5704.task_run_pe_U0.img_sm_U.if_empty_n) begin
                                $display("//      Blocked by empty input FIFO 'vit_block_top_vit_block_top.grp_initial_overlap_wrapper_fu_5704.task_run_pe_U0.img_sm_U' written by process 'vit_block_top_vit_block_top.grp_initial_overlap_wrapper_fu_5704.task_run_pe_U0.task_recv_img_U0'");
                                $fdisplay(fp, "Dependence_Channel_path vit_block_top_vit_block_top.grp_initial_overlap_wrapper_fu_5704.task_run_pe_U0.img_sm_U");
                                $fdisplay(fp, "Dependence_Channel_status EMPTY");
                            end
                            else if (~grp_initial_overlap_wrapper_fu_5704.task_run_pe_U0.img_sm_U.if_full_n) begin
                                $display("//      Blocked by full output FIFO 'vit_block_top_vit_block_top.grp_initial_overlap_wrapper_fu_5704.task_run_pe_U0.img_sm_U' read by process 'vit_block_top_vit_block_top.grp_initial_overlap_wrapper_fu_5704.task_run_pe_U0.task_recv_img_U0'");
                                $fdisplay(fp, "Dependence_Channel_path vit_block_top_vit_block_top.grp_initial_overlap_wrapper_fu_5704.task_run_pe_U0.img_sm_U");
                                $fdisplay(fp, "Dependence_Channel_status FULL");
                            end
                        end
                    end
                    4: begin //  for dep proc 'vit_block_top_vit_block_top.grp_initial_overlap_wrapper_fu_5704.task_run_pe_U0.fixed_patch_do_patch_embed_U0.fixed_patch_step2_mac_replace_shift_U0'
// for dep channel 'vit_block_top_vit_block_top.grp_initial_overlap_wrapper_fu_5704.task_run_pe_U0.fixed_patch_do_patch_embed_U0.adpt_sm_U' info is :
// blk sig is {~vit_block_top_vit_block_top_inst.grp_initial_overlap_wrapper_fu_5704.task_run_pe_U0.fixed_patch_do_patch_embed_U0.do_adapt_4_U0.adpt_sm_blk_n data_FIFO}
                        if ((~grp_initial_overlap_wrapper_fu_5704.task_run_pe_U0.fixed_patch_do_patch_embed_U0.do_adapt_4_U0.adpt_sm_blk_n)) begin
                            if (~grp_initial_overlap_wrapper_fu_5704.task_run_pe_U0.fixed_patch_do_patch_embed_U0.adpt_sm_U.if_empty_n) begin
                                $display("//      Blocked by empty input FIFO 'vit_block_top_vit_block_top.grp_initial_overlap_wrapper_fu_5704.task_run_pe_U0.fixed_patch_do_patch_embed_U0.adpt_sm_U' written by process 'vit_block_top_vit_block_top.grp_initial_overlap_wrapper_fu_5704.task_run_pe_U0.fixed_patch_do_patch_embed_U0.fixed_patch_step2_mac_replace_shift_U0'");
                                $fdisplay(fp, "Dependence_Channel_path vit_block_top_vit_block_top.grp_initial_overlap_wrapper_fu_5704.task_run_pe_U0.fixed_patch_do_patch_embed_U0.adpt_sm_U");
                                $fdisplay(fp, "Dependence_Channel_status EMPTY");
                            end
                            else if (~grp_initial_overlap_wrapper_fu_5704.task_run_pe_U0.fixed_patch_do_patch_embed_U0.adpt_sm_U.if_full_n) begin
                                $display("//      Blocked by full output FIFO 'vit_block_top_vit_block_top.grp_initial_overlap_wrapper_fu_5704.task_run_pe_U0.fixed_patch_do_patch_embed_U0.adpt_sm_U' read by process 'vit_block_top_vit_block_top.grp_initial_overlap_wrapper_fu_5704.task_run_pe_U0.fixed_patch_do_patch_embed_U0.fixed_patch_step2_mac_replace_shift_U0'");
                                $fdisplay(fp, "Dependence_Channel_path vit_block_top_vit_block_top.grp_initial_overlap_wrapper_fu_5704.task_run_pe_U0.fixed_patch_do_patch_embed_U0.adpt_sm_U");
                                $fdisplay(fp, "Dependence_Channel_status FULL");
                            end
                        end
// for dep channel 'vit_block_top_vit_block_top.grp_initial_overlap_wrapper_fu_5704.task_run_pe_U0.fixed_patch_do_patch_embed_U0.start_for_fixed_patch_step2_mac_replace_shift_U0_U' info is :
// blk sig is {{~vit_block_top_vit_block_top_inst.grp_initial_overlap_wrapper_fu_5704.task_run_pe_U0.fixed_patch_do_patch_embed_U0.start_for_fixed_patch_step2_mac_replace_shift_U0_U.if_full_n & vit_block_top_vit_block_top_inst.grp_initial_overlap_wrapper_fu_5704.task_run_pe_U0.fixed_patch_do_patch_embed_U0.do_adapt_4_U0.ap_start & ~vit_block_top_vit_block_top_inst.grp_initial_overlap_wrapper_fu_5704.task_run_pe_U0.fixed_patch_do_patch_embed_U0.do_adapt_4_U0.real_start & (trans_in_cnt_1 == trans_out_cnt_1) & ~vit_block_top_vit_block_top_inst.grp_initial_overlap_wrapper_fu_5704.task_run_pe_U0.fixed_patch_do_patch_embed_U0.start_for_fixed_patch_step2_mac_replace_shift_U0_U.if_read} start_FIFO}
                        if ((~grp_initial_overlap_wrapper_fu_5704.task_run_pe_U0.fixed_patch_do_patch_embed_U0.start_for_fixed_patch_step2_mac_replace_shift_U0_U.if_full_n & grp_initial_overlap_wrapper_fu_5704.task_run_pe_U0.fixed_patch_do_patch_embed_U0.do_adapt_4_U0.ap_start & ~grp_initial_overlap_wrapper_fu_5704.task_run_pe_U0.fixed_patch_do_patch_embed_U0.do_adapt_4_U0.real_start & (trans_in_cnt_1 == trans_out_cnt_1) & ~grp_initial_overlap_wrapper_fu_5704.task_run_pe_U0.fixed_patch_do_patch_embed_U0.start_for_fixed_patch_step2_mac_replace_shift_U0_U.if_read)) begin
                            $display("//      Blocked by full output start propagation FIFO 'vit_block_top_vit_block_top.grp_initial_overlap_wrapper_fu_5704.task_run_pe_U0.fixed_patch_do_patch_embed_U0.start_for_fixed_patch_step2_mac_replace_shift_U0_U' read by process 'vit_block_top_vit_block_top.grp_initial_overlap_wrapper_fu_5704.task_run_pe_U0.fixed_patch_do_patch_embed_U0.fixed_patch_step2_mac_replace_shift_U0',");
                        end
                    end
                    endcase
                end
                4 : begin // for proc 'vit_block_top_vit_block_top.grp_initial_overlap_wrapper_fu_5704.task_run_pe_U0.fixed_patch_do_patch_embed_U0.fixed_patch_step2_mac_replace_shift_U0'
                    case(index2)
                    3: begin //  for dep proc 'vit_block_top_vit_block_top.grp_initial_overlap_wrapper_fu_5704.task_run_pe_U0.fixed_patch_do_patch_embed_U0.do_adapt_4_U0'
// for dep channel 'vit_block_top_vit_block_top.grp_initial_overlap_wrapper_fu_5704.task_run_pe_U0.fixed_patch_do_patch_embed_U0.adpt_sm_U' info is :
// blk sig is {~vit_block_top_vit_block_top_inst.grp_initial_overlap_wrapper_fu_5704.task_run_pe_U0.fixed_patch_do_patch_embed_U0.fixed_patch_step2_mac_replace_shift_U0.grp_fixed_patch_step2_mac_replace_shift_Pipeline_CIT_LOOP_COT_LOOP_fu_790.adpt_sm_blk_n data_FIFO}
                        if ((~grp_initial_overlap_wrapper_fu_5704.task_run_pe_U0.fixed_patch_do_patch_embed_U0.fixed_patch_step2_mac_replace_shift_U0.grp_fixed_patch_step2_mac_replace_shift_Pipeline_CIT_LOOP_COT_LOOP_fu_790.adpt_sm_blk_n)) begin
                            if (~grp_initial_overlap_wrapper_fu_5704.task_run_pe_U0.fixed_patch_do_patch_embed_U0.adpt_sm_U.if_empty_n) begin
                                $display("//      Blocked by empty input FIFO 'vit_block_top_vit_block_top.grp_initial_overlap_wrapper_fu_5704.task_run_pe_U0.fixed_patch_do_patch_embed_U0.adpt_sm_U' written by process 'vit_block_top_vit_block_top.grp_initial_overlap_wrapper_fu_5704.task_run_pe_U0.fixed_patch_do_patch_embed_U0.do_adapt_4_U0'");
                                $fdisplay(fp, "Dependence_Channel_path vit_block_top_vit_block_top.grp_initial_overlap_wrapper_fu_5704.task_run_pe_U0.fixed_patch_do_patch_embed_U0.adpt_sm_U");
                                $fdisplay(fp, "Dependence_Channel_status EMPTY");
                            end
                            else if (~grp_initial_overlap_wrapper_fu_5704.task_run_pe_U0.fixed_patch_do_patch_embed_U0.adpt_sm_U.if_full_n) begin
                                $display("//      Blocked by full output FIFO 'vit_block_top_vit_block_top.grp_initial_overlap_wrapper_fu_5704.task_run_pe_U0.fixed_patch_do_patch_embed_U0.adpt_sm_U' read by process 'vit_block_top_vit_block_top.grp_initial_overlap_wrapper_fu_5704.task_run_pe_U0.fixed_patch_do_patch_embed_U0.do_adapt_4_U0'");
                                $fdisplay(fp, "Dependence_Channel_path vit_block_top_vit_block_top.grp_initial_overlap_wrapper_fu_5704.task_run_pe_U0.fixed_patch_do_patch_embed_U0.adpt_sm_U");
                                $fdisplay(fp, "Dependence_Channel_status FULL");
                            end
                        end
// for dep channel 'vit_block_top_vit_block_top.grp_initial_overlap_wrapper_fu_5704.task_run_pe_U0.fixed_patch_do_patch_embed_U0.start_for_fixed_patch_step2_mac_replace_shift_U0_U' info is :
// blk sig is {{~vit_block_top_vit_block_top_inst.grp_initial_overlap_wrapper_fu_5704.task_run_pe_U0.fixed_patch_do_patch_embed_U0.start_for_fixed_patch_step2_mac_replace_shift_U0_U.if_empty_n & vit_block_top_vit_block_top_inst.grp_initial_overlap_wrapper_fu_5704.task_run_pe_U0.fixed_patch_do_patch_embed_U0.fixed_patch_step2_mac_replace_shift_U0.ap_idle & ~vit_block_top_vit_block_top_inst.grp_initial_overlap_wrapper_fu_5704.task_run_pe_U0.fixed_patch_do_patch_embed_U0.start_for_fixed_patch_step2_mac_replace_shift_U0_U.if_write} start_FIFO}
                        if ((~grp_initial_overlap_wrapper_fu_5704.task_run_pe_U0.fixed_patch_do_patch_embed_U0.start_for_fixed_patch_step2_mac_replace_shift_U0_U.if_empty_n & grp_initial_overlap_wrapper_fu_5704.task_run_pe_U0.fixed_patch_do_patch_embed_U0.fixed_patch_step2_mac_replace_shift_U0.ap_idle & ~grp_initial_overlap_wrapper_fu_5704.task_run_pe_U0.fixed_patch_do_patch_embed_U0.start_for_fixed_patch_step2_mac_replace_shift_U0_U.if_write)) begin
                            $display("//      Blocked by missing 'ap_start' from start propagation FIFO 'vit_block_top_vit_block_top.grp_initial_overlap_wrapper_fu_5704.task_run_pe_U0.fixed_patch_do_patch_embed_U0.start_for_fixed_patch_step2_mac_replace_shift_U0_U' written by process 'vit_block_top_vit_block_top.grp_initial_overlap_wrapper_fu_5704.task_run_pe_U0.fixed_patch_do_patch_embed_U0.do_adapt_4_U0',");
                        end
                    end
                    5: begin //  for dep proc 'vit_block_top_vit_block_top.grp_initial_overlap_wrapper_fu_5704.task_run_pe_U0.fixed_patch_do_patch_embed_U0.do_adapt_9_1_U0'
// for dep channel 'vit_block_top_vit_block_top.grp_initial_overlap_wrapper_fu_5704.task_run_pe_U0.fixed_patch_do_patch_embed_U0.mac_sm_U' info is :
// blk sig is {~vit_block_top_vit_block_top_inst.grp_initial_overlap_wrapper_fu_5704.task_run_pe_U0.fixed_patch_do_patch_embed_U0.fixed_patch_step2_mac_replace_shift_U0.grp_fixed_patch_step2_mac_replace_shift_Pipeline_WRITE_COT_LOOP_fu_1446.mac_sm_blk_n data_FIFO}
                        if ((~grp_initial_overlap_wrapper_fu_5704.task_run_pe_U0.fixed_patch_do_patch_embed_U0.fixed_patch_step2_mac_replace_shift_U0.grp_fixed_patch_step2_mac_replace_shift_Pipeline_WRITE_COT_LOOP_fu_1446.mac_sm_blk_n)) begin
                            if (~grp_initial_overlap_wrapper_fu_5704.task_run_pe_U0.fixed_patch_do_patch_embed_U0.mac_sm_U.if_empty_n) begin
                                $display("//      Blocked by empty input FIFO 'vit_block_top_vit_block_top.grp_initial_overlap_wrapper_fu_5704.task_run_pe_U0.fixed_patch_do_patch_embed_U0.mac_sm_U' written by process 'vit_block_top_vit_block_top.grp_initial_overlap_wrapper_fu_5704.task_run_pe_U0.fixed_patch_do_patch_embed_U0.do_adapt_9_1_U0'");
                                $fdisplay(fp, "Dependence_Channel_path vit_block_top_vit_block_top.grp_initial_overlap_wrapper_fu_5704.task_run_pe_U0.fixed_patch_do_patch_embed_U0.mac_sm_U");
                                $fdisplay(fp, "Dependence_Channel_status EMPTY");
                            end
                            else if (~grp_initial_overlap_wrapper_fu_5704.task_run_pe_U0.fixed_patch_do_patch_embed_U0.mac_sm_U.if_full_n) begin
                                $display("//      Blocked by full output FIFO 'vit_block_top_vit_block_top.grp_initial_overlap_wrapper_fu_5704.task_run_pe_U0.fixed_patch_do_patch_embed_U0.mac_sm_U' read by process 'vit_block_top_vit_block_top.grp_initial_overlap_wrapper_fu_5704.task_run_pe_U0.fixed_patch_do_patch_embed_U0.do_adapt_9_1_U0'");
                                $fdisplay(fp, "Dependence_Channel_path vit_block_top_vit_block_top.grp_initial_overlap_wrapper_fu_5704.task_run_pe_U0.fixed_patch_do_patch_embed_U0.mac_sm_U");
                                $fdisplay(fp, "Dependence_Channel_status FULL");
                            end
                        end
// for dep channel 'vit_block_top_vit_block_top.grp_initial_overlap_wrapper_fu_5704.task_run_pe_U0.fixed_patch_do_patch_embed_U0.start_for_do_adapt_9_1_U0_U' info is :
// blk sig is {{~vit_block_top_vit_block_top_inst.grp_initial_overlap_wrapper_fu_5704.task_run_pe_U0.fixed_patch_do_patch_embed_U0.start_for_do_adapt_9_1_U0_U.if_full_n & vit_block_top_vit_block_top_inst.grp_initial_overlap_wrapper_fu_5704.task_run_pe_U0.fixed_patch_do_patch_embed_U0.fixed_patch_step2_mac_replace_shift_U0.ap_start & ~vit_block_top_vit_block_top_inst.grp_initial_overlap_wrapper_fu_5704.task_run_pe_U0.fixed_patch_do_patch_embed_U0.fixed_patch_step2_mac_replace_shift_U0.real_start & (trans_in_cnt_2 == trans_out_cnt_2) & ~vit_block_top_vit_block_top_inst.grp_initial_overlap_wrapper_fu_5704.task_run_pe_U0.fixed_patch_do_patch_embed_U0.start_for_do_adapt_9_1_U0_U.if_read} start_FIFO}
                        if ((~grp_initial_overlap_wrapper_fu_5704.task_run_pe_U0.fixed_patch_do_patch_embed_U0.start_for_do_adapt_9_1_U0_U.if_full_n & grp_initial_overlap_wrapper_fu_5704.task_run_pe_U0.fixed_patch_do_patch_embed_U0.fixed_patch_step2_mac_replace_shift_U0.ap_start & ~grp_initial_overlap_wrapper_fu_5704.task_run_pe_U0.fixed_patch_do_patch_embed_U0.fixed_patch_step2_mac_replace_shift_U0.real_start & (trans_in_cnt_2 == trans_out_cnt_2) & ~grp_initial_overlap_wrapper_fu_5704.task_run_pe_U0.fixed_patch_do_patch_embed_U0.start_for_do_adapt_9_1_U0_U.if_read)) begin
                            $display("//      Blocked by full output start propagation FIFO 'vit_block_top_vit_block_top.grp_initial_overlap_wrapper_fu_5704.task_run_pe_U0.fixed_patch_do_patch_embed_U0.start_for_do_adapt_9_1_U0_U' read by process 'vit_block_top_vit_block_top.grp_initial_overlap_wrapper_fu_5704.task_run_pe_U0.fixed_patch_do_patch_embed_U0.do_adapt_9_1_U0',");
                        end
                    end
                    endcase
                end
                5 : begin // for proc 'vit_block_top_vit_block_top.grp_initial_overlap_wrapper_fu_5704.task_run_pe_U0.fixed_patch_do_patch_embed_U0.do_adapt_9_1_U0'
                    case(index2)
                    4: begin //  for dep proc 'vit_block_top_vit_block_top.grp_initial_overlap_wrapper_fu_5704.task_run_pe_U0.fixed_patch_do_patch_embed_U0.fixed_patch_step2_mac_replace_shift_U0'
// for dep channel 'vit_block_top_vit_block_top.grp_initial_overlap_wrapper_fu_5704.task_run_pe_U0.fixed_patch_do_patch_embed_U0.mac_sm_U' info is :
// blk sig is {~vit_block_top_vit_block_top_inst.grp_initial_overlap_wrapper_fu_5704.task_run_pe_U0.fixed_patch_do_patch_embed_U0.do_adapt_9_1_U0.mac_sm_blk_n data_FIFO}
                        if ((~grp_initial_overlap_wrapper_fu_5704.task_run_pe_U0.fixed_patch_do_patch_embed_U0.do_adapt_9_1_U0.mac_sm_blk_n)) begin
                            if (~grp_initial_overlap_wrapper_fu_5704.task_run_pe_U0.fixed_patch_do_patch_embed_U0.mac_sm_U.if_empty_n) begin
                                $display("//      Blocked by empty input FIFO 'vit_block_top_vit_block_top.grp_initial_overlap_wrapper_fu_5704.task_run_pe_U0.fixed_patch_do_patch_embed_U0.mac_sm_U' written by process 'vit_block_top_vit_block_top.grp_initial_overlap_wrapper_fu_5704.task_run_pe_U0.fixed_patch_do_patch_embed_U0.fixed_patch_step2_mac_replace_shift_U0'");
                                $fdisplay(fp, "Dependence_Channel_path vit_block_top_vit_block_top.grp_initial_overlap_wrapper_fu_5704.task_run_pe_U0.fixed_patch_do_patch_embed_U0.mac_sm_U");
                                $fdisplay(fp, "Dependence_Channel_status EMPTY");
                            end
                            else if (~grp_initial_overlap_wrapper_fu_5704.task_run_pe_U0.fixed_patch_do_patch_embed_U0.mac_sm_U.if_full_n) begin
                                $display("//      Blocked by full output FIFO 'vit_block_top_vit_block_top.grp_initial_overlap_wrapper_fu_5704.task_run_pe_U0.fixed_patch_do_patch_embed_U0.mac_sm_U' read by process 'vit_block_top_vit_block_top.grp_initial_overlap_wrapper_fu_5704.task_run_pe_U0.fixed_patch_do_patch_embed_U0.fixed_patch_step2_mac_replace_shift_U0'");
                                $fdisplay(fp, "Dependence_Channel_path vit_block_top_vit_block_top.grp_initial_overlap_wrapper_fu_5704.task_run_pe_U0.fixed_patch_do_patch_embed_U0.mac_sm_U");
                                $fdisplay(fp, "Dependence_Channel_status FULL");
                            end
                        end
// for dep channel 'vit_block_top_vit_block_top.grp_initial_overlap_wrapper_fu_5704.task_run_pe_U0.fixed_patch_do_patch_embed_U0.start_for_do_adapt_9_1_U0_U' info is :
// blk sig is {{~vit_block_top_vit_block_top_inst.grp_initial_overlap_wrapper_fu_5704.task_run_pe_U0.fixed_patch_do_patch_embed_U0.start_for_do_adapt_9_1_U0_U.if_empty_n & vit_block_top_vit_block_top_inst.grp_initial_overlap_wrapper_fu_5704.task_run_pe_U0.fixed_patch_do_patch_embed_U0.do_adapt_9_1_U0.ap_idle & ~vit_block_top_vit_block_top_inst.grp_initial_overlap_wrapper_fu_5704.task_run_pe_U0.fixed_patch_do_patch_embed_U0.start_for_do_adapt_9_1_U0_U.if_write} start_FIFO}
                        if ((~grp_initial_overlap_wrapper_fu_5704.task_run_pe_U0.fixed_patch_do_patch_embed_U0.start_for_do_adapt_9_1_U0_U.if_empty_n & grp_initial_overlap_wrapper_fu_5704.task_run_pe_U0.fixed_patch_do_patch_embed_U0.do_adapt_9_1_U0.ap_idle & ~grp_initial_overlap_wrapper_fu_5704.task_run_pe_U0.fixed_patch_do_patch_embed_U0.start_for_do_adapt_9_1_U0_U.if_write)) begin
                            $display("//      Blocked by missing 'ap_start' from start propagation FIFO 'vit_block_top_vit_block_top.grp_initial_overlap_wrapper_fu_5704.task_run_pe_U0.fixed_patch_do_patch_embed_U0.start_for_do_adapt_9_1_U0_U' written by process 'vit_block_top_vit_block_top.grp_initial_overlap_wrapper_fu_5704.task_run_pe_U0.fixed_patch_do_patch_embed_U0.fixed_patch_step2_mac_replace_shift_U0',");
                        end
                    end
                    6: begin //  for dep proc 'vit_block_top_vit_block_top.grp_initial_overlap_wrapper_fu_5704.task_run_pe_U0.task_write_pe_to_fm_U0'
// for dep channel 'vit_block_top_vit_block_top.grp_initial_overlap_wrapper_fu_5704.task_run_pe_U0.pe_out_sm_U' info is :
// blk sig is {~vit_block_top_vit_block_top_inst.grp_initial_overlap_wrapper_fu_5704.task_run_pe_U0.fixed_patch_do_patch_embed_U0.do_adapt_9_1_U0.pe_out_sm_blk_n data_FIFO}
                        if ((~grp_initial_overlap_wrapper_fu_5704.task_run_pe_U0.fixed_patch_do_patch_embed_U0.do_adapt_9_1_U0.pe_out_sm_blk_n)) begin
                            if (~grp_initial_overlap_wrapper_fu_5704.task_run_pe_U0.pe_out_sm_U.if_empty_n) begin
                                $display("//      Blocked by empty input FIFO 'vit_block_top_vit_block_top.grp_initial_overlap_wrapper_fu_5704.task_run_pe_U0.pe_out_sm_U' written by process 'vit_block_top_vit_block_top.grp_initial_overlap_wrapper_fu_5704.task_run_pe_U0.task_write_pe_to_fm_U0'");
                                $fdisplay(fp, "Dependence_Channel_path vit_block_top_vit_block_top.grp_initial_overlap_wrapper_fu_5704.task_run_pe_U0.pe_out_sm_U");
                                $fdisplay(fp, "Dependence_Channel_status EMPTY");
                            end
                            else if (~grp_initial_overlap_wrapper_fu_5704.task_run_pe_U0.pe_out_sm_U.if_full_n) begin
                                $display("//      Blocked by full output FIFO 'vit_block_top_vit_block_top.grp_initial_overlap_wrapper_fu_5704.task_run_pe_U0.pe_out_sm_U' read by process 'vit_block_top_vit_block_top.grp_initial_overlap_wrapper_fu_5704.task_run_pe_U0.task_write_pe_to_fm_U0'");
                                $fdisplay(fp, "Dependence_Channel_path vit_block_top_vit_block_top.grp_initial_overlap_wrapper_fu_5704.task_run_pe_U0.pe_out_sm_U");
                                $fdisplay(fp, "Dependence_Channel_status FULL");
                            end
                        end
                    end
                    endcase
                end
                6 : begin // for proc 'vit_block_top_vit_block_top.grp_initial_overlap_wrapper_fu_5704.task_run_pe_U0.task_write_pe_to_fm_U0'
                    case(index2)
                    2: begin //  for dep proc 'vit_block_top_vit_block_top.grp_initial_overlap_wrapper_fu_5704.task_run_pe_U0.fixed_patch_do_patch_embed_U0'
// for dep channel 'vit_block_top_vit_block_top.grp_initial_overlap_wrapper_fu_5704.task_run_pe_U0.pe_out_sm_U' info is :
// blk sig is {~vit_block_top_vit_block_top_inst.grp_initial_overlap_wrapper_fu_5704.task_run_pe_U0.task_write_pe_to_fm_U0.pe_out_sm_blk_n data_FIFO}
                        if ((~grp_initial_overlap_wrapper_fu_5704.task_run_pe_U0.task_write_pe_to_fm_U0.pe_out_sm_blk_n)) begin
                            if (~grp_initial_overlap_wrapper_fu_5704.task_run_pe_U0.pe_out_sm_U.if_empty_n) begin
                                $display("//      Blocked by empty input FIFO 'vit_block_top_vit_block_top.grp_initial_overlap_wrapper_fu_5704.task_run_pe_U0.pe_out_sm_U' written by process 'vit_block_top_vit_block_top.grp_initial_overlap_wrapper_fu_5704.task_run_pe_U0.fixed_patch_do_patch_embed_U0'");
                                $fdisplay(fp, "Dependence_Channel_path vit_block_top_vit_block_top.grp_initial_overlap_wrapper_fu_5704.task_run_pe_U0.pe_out_sm_U");
                                $fdisplay(fp, "Dependence_Channel_status EMPTY");
                            end
                            else if (~grp_initial_overlap_wrapper_fu_5704.task_run_pe_U0.pe_out_sm_U.if_full_n) begin
                                $display("//      Blocked by full output FIFO 'vit_block_top_vit_block_top.grp_initial_overlap_wrapper_fu_5704.task_run_pe_U0.pe_out_sm_U' read by process 'vit_block_top_vit_block_top.grp_initial_overlap_wrapper_fu_5704.task_run_pe_U0.fixed_patch_do_patch_embed_U0'");
                                $fdisplay(fp, "Dependence_Channel_path vit_block_top_vit_block_top.grp_initial_overlap_wrapper_fu_5704.task_run_pe_U0.pe_out_sm_U");
                                $fdisplay(fp, "Dependence_Channel_status FULL");
                            end
                        end
// for dep channel 'vit_block_top_vit_block_top.grp_initial_overlap_wrapper_fu_5704.task_run_pe_U0.start_for_task_write_pe_to_fm_U0_U' info is :
// blk sig is {{~vit_block_top_vit_block_top_inst.grp_initial_overlap_wrapper_fu_5704.task_run_pe_U0.start_for_task_write_pe_to_fm_U0_U.if_empty_n & vit_block_top_vit_block_top_inst.grp_initial_overlap_wrapper_fu_5704.task_run_pe_U0.task_write_pe_to_fm_U0.ap_idle & ~vit_block_top_vit_block_top_inst.grp_initial_overlap_wrapper_fu_5704.task_run_pe_U0.start_for_task_write_pe_to_fm_U0_U.if_write} start_FIFO}
                        if ((~grp_initial_overlap_wrapper_fu_5704.task_run_pe_U0.start_for_task_write_pe_to_fm_U0_U.if_empty_n & grp_initial_overlap_wrapper_fu_5704.task_run_pe_U0.task_write_pe_to_fm_U0.ap_idle & ~grp_initial_overlap_wrapper_fu_5704.task_run_pe_U0.start_for_task_write_pe_to_fm_U0_U.if_write)) begin
                            $display("//      Blocked by missing 'ap_start' from start propagation FIFO 'vit_block_top_vit_block_top.grp_initial_overlap_wrapper_fu_5704.task_run_pe_U0.start_for_task_write_pe_to_fm_U0_U' written by process 'vit_block_top_vit_block_top.grp_initial_overlap_wrapper_fu_5704.task_run_pe_U0.fixed_patch_do_patch_embed_U0',");
                        end
                    end
                    5: begin //  for dep proc 'vit_block_top_vit_block_top.grp_initial_overlap_wrapper_fu_5704.task_run_pe_U0.fixed_patch_do_patch_embed_U0.do_adapt_9_1_U0'
// for dep channel 'vit_block_top_vit_block_top.grp_initial_overlap_wrapper_fu_5704.task_run_pe_U0.pe_out_sm_U' info is :
// blk sig is {~vit_block_top_vit_block_top_inst.grp_initial_overlap_wrapper_fu_5704.task_run_pe_U0.task_write_pe_to_fm_U0.pe_out_sm_blk_n data_FIFO}
                        if ((~grp_initial_overlap_wrapper_fu_5704.task_run_pe_U0.task_write_pe_to_fm_U0.pe_out_sm_blk_n)) begin
                            if (~grp_initial_overlap_wrapper_fu_5704.task_run_pe_U0.pe_out_sm_U.if_empty_n) begin
                                $display("//      Blocked by empty input FIFO 'vit_block_top_vit_block_top.grp_initial_overlap_wrapper_fu_5704.task_run_pe_U0.pe_out_sm_U' written by process 'vit_block_top_vit_block_top.grp_initial_overlap_wrapper_fu_5704.task_run_pe_U0.fixed_patch_do_patch_embed_U0.do_adapt_9_1_U0'");
                                $fdisplay(fp, "Dependence_Channel_path vit_block_top_vit_block_top.grp_initial_overlap_wrapper_fu_5704.task_run_pe_U0.pe_out_sm_U");
                                $fdisplay(fp, "Dependence_Channel_status EMPTY");
                            end
                            else if (~grp_initial_overlap_wrapper_fu_5704.task_run_pe_U0.pe_out_sm_U.if_full_n) begin
                                $display("//      Blocked by full output FIFO 'vit_block_top_vit_block_top.grp_initial_overlap_wrapper_fu_5704.task_run_pe_U0.pe_out_sm_U' read by process 'vit_block_top_vit_block_top.grp_initial_overlap_wrapper_fu_5704.task_run_pe_U0.fixed_patch_do_patch_embed_U0.do_adapt_9_1_U0'");
                                $fdisplay(fp, "Dependence_Channel_path vit_block_top_vit_block_top.grp_initial_overlap_wrapper_fu_5704.task_run_pe_U0.pe_out_sm_U");
                                $fdisplay(fp, "Dependence_Channel_status FULL");
                            end
                        end
                    end
                    endcase
                end
                7 : begin // for proc 'vit_block_top_vit_block_top.grp_initial_overlap_wrapper_fu_5704.task_load_weights_U0'
                    case(index2)
                    0: begin //  for dep proc 'vit_block_top_vit_block_top.grp_initial_overlap_wrapper_fu_5704.task_run_pe_U0'
// for dep channel '' info is :
// blk sig is {{vit_block_top_vit_block_top_inst.grp_initial_overlap_wrapper_fu_5704.ap_sync_task_load_weights_U0_ap_ready & vit_block_top_vit_block_top_inst.grp_initial_overlap_wrapper_fu_5704.task_load_weights_U0.ap_idle & ~vit_block_top_vit_block_top_inst.grp_initial_overlap_wrapper_fu_5704.ap_sync_task_run_pe_U0_ap_ready} input_sync} {{ap_done_reg_4 & vit_block_top_vit_block_top_inst.grp_initial_overlap_wrapper_fu_5704.task_load_weights_U0.ap_done & ~vit_block_top_vit_block_top_inst.grp_initial_overlap_wrapper_fu_5704.task_run_pe_U0.ap_done} output_sync}
                        if ((grp_initial_overlap_wrapper_fu_5704.ap_sync_task_load_weights_U0_ap_ready & grp_initial_overlap_wrapper_fu_5704.task_load_weights_U0.ap_idle & ~grp_initial_overlap_wrapper_fu_5704.ap_sync_task_run_pe_U0_ap_ready) | (ap_done_reg_4 & grp_initial_overlap_wrapper_fu_5704.task_load_weights_U0.ap_done & ~grp_initial_overlap_wrapper_fu_5704.task_run_pe_U0.ap_done)) begin
                            $display("//      Blocked by input sync logic with process : 'vit_block_top_vit_block_top.grp_initial_overlap_wrapper_fu_5704.task_run_pe_U0'");
                        end
                    end
                    endcase
                end
                8 : begin // for proc 'vit_block_top_vit_block_top.grp_dataflow_wrapper_fu_6443.task_read_fm_split_U0'
                    case(index2)
                    10: begin //  for dep proc 'vit_block_top_vit_block_top.grp_dataflow_wrapper_fu_6443.task_compute_attn_U0'
// for dep channel 'vit_block_top_vit_block_top.grp_dataflow_wrapper_fu_6443.i_stream_main_U' info is :
// blk sig is {~vit_block_top_vit_block_top_inst.grp_dataflow_wrapper_fu_6443.task_read_fm_split_U0.i_stream_main_blk_n data_FIFO}
                        if ((~grp_dataflow_wrapper_fu_6443.task_read_fm_split_U0.i_stream_main_blk_n)) begin
                            if (~grp_dataflow_wrapper_fu_6443.i_stream_main_U.if_empty_n) begin
                                $display("//      Blocked by empty input FIFO 'vit_block_top_vit_block_top.grp_dataflow_wrapper_fu_6443.i_stream_main_U' written by process 'vit_block_top_vit_block_top.grp_dataflow_wrapper_fu_6443.task_compute_attn_U0'");
                                $fdisplay(fp, "Dependence_Channel_path vit_block_top_vit_block_top.grp_dataflow_wrapper_fu_6443.i_stream_main_U");
                                $fdisplay(fp, "Dependence_Channel_status EMPTY");
                            end
                            else if (~grp_dataflow_wrapper_fu_6443.i_stream_main_U.if_full_n) begin
                                $display("//      Blocked by full output FIFO 'vit_block_top_vit_block_top.grp_dataflow_wrapper_fu_6443.i_stream_main_U' read by process 'vit_block_top_vit_block_top.grp_dataflow_wrapper_fu_6443.task_compute_attn_U0'");
                                $fdisplay(fp, "Dependence_Channel_path vit_block_top_vit_block_top.grp_dataflow_wrapper_fu_6443.i_stream_main_U");
                                $fdisplay(fp, "Dependence_Channel_status FULL");
                            end
                        end
// for dep channel 'vit_block_top_vit_block_top.grp_dataflow_wrapper_fu_6443.i_stream_resi_U' info is :
// blk sig is {~vit_block_top_vit_block_top_inst.grp_dataflow_wrapper_fu_6443.task_read_fm_split_U0.i_stream_resi_blk_n data_FIFO}
                        if ((~grp_dataflow_wrapper_fu_6443.task_read_fm_split_U0.i_stream_resi_blk_n)) begin
                            if (~grp_dataflow_wrapper_fu_6443.i_stream_resi_U.if_empty_n) begin
                                $display("//      Blocked by empty input FIFO 'vit_block_top_vit_block_top.grp_dataflow_wrapper_fu_6443.i_stream_resi_U' written by process 'vit_block_top_vit_block_top.grp_dataflow_wrapper_fu_6443.task_compute_attn_U0'");
                                $fdisplay(fp, "Dependence_Channel_path vit_block_top_vit_block_top.grp_dataflow_wrapper_fu_6443.i_stream_resi_U");
                                $fdisplay(fp, "Dependence_Channel_status EMPTY");
                            end
                            else if (~grp_dataflow_wrapper_fu_6443.i_stream_resi_U.if_full_n) begin
                                $display("//      Blocked by full output FIFO 'vit_block_top_vit_block_top.grp_dataflow_wrapper_fu_6443.i_stream_resi_U' read by process 'vit_block_top_vit_block_top.grp_dataflow_wrapper_fu_6443.task_compute_attn_U0'");
                                $fdisplay(fp, "Dependence_Channel_path vit_block_top_vit_block_top.grp_dataflow_wrapper_fu_6443.i_stream_resi_U");
                                $fdisplay(fp, "Dependence_Channel_status FULL");
                            end
                        end
                    end
                    9: begin //  for dep proc 'vit_block_top_vit_block_top.grp_dataflow_wrapper_fu_6443.dataflow_wrapper_Block_entry_calc_weights_attn_weights_attn_scalars_rd_calc_weig_U0'
// for dep channel '' info is :
// blk sig is {{vit_block_top_vit_block_top_inst.grp_dataflow_wrapper_fu_6443.ap_sync_task_read_fm_split_U0_ap_ready & vit_block_top_vit_block_top_inst.grp_dataflow_wrapper_fu_6443.task_read_fm_split_U0.ap_idle & ~vit_block_top_vit_block_top_inst.grp_dataflow_wrapper_fu_6443.ap_sync_dataflow_wrapper_Block_entry_calc_weights_attn_weights_attn_scalars_rd_calc_weig_U0_ap_ready} input_sync}
                        if ((grp_dataflow_wrapper_fu_6443.ap_sync_task_read_fm_split_U0_ap_ready & grp_dataflow_wrapper_fu_6443.task_read_fm_split_U0.ap_idle & ~grp_dataflow_wrapper_fu_6443.ap_sync_dataflow_wrapper_Block_entry_calc_weights_attn_weights_attn_scalars_rd_calc_weig_U0_ap_ready)) begin
                            $display("//      Blocked by input sync logic with process : 'vit_block_top_vit_block_top.grp_dataflow_wrapper_fu_6443.dataflow_wrapper_Block_entry_calc_weights_attn_weights_attn_scalars_rd_calc_weig_U0'");
                        end
                    end
                    endcase
                end
                9 : begin // for proc 'vit_block_top_vit_block_top.grp_dataflow_wrapper_fu_6443.dataflow_wrapper_Block_entry_calc_weights_attn_weights_attn_scalars_rd_calc_weig_U0'
                    case(index2)
                    8: begin //  for dep proc 'vit_block_top_vit_block_top.grp_dataflow_wrapper_fu_6443.task_read_fm_split_U0'
// for dep channel '' info is :
// blk sig is {{vit_block_top_vit_block_top_inst.grp_dataflow_wrapper_fu_6443.ap_sync_dataflow_wrapper_Block_entry_calc_weights_attn_weights_attn_scalars_rd_calc_weig_U0_ap_ready & vit_block_top_vit_block_top_inst.grp_dataflow_wrapper_fu_6443.dataflow_wrapper_Block_entry_calc_weights_attn_weights_attn_scalars_rd_calc_weig_U0.ap_idle & ~vit_block_top_vit_block_top_inst.grp_dataflow_wrapper_fu_6443.ap_sync_task_read_fm_split_U0_ap_ready} input_sync}
                        if ((grp_dataflow_wrapper_fu_6443.ap_sync_dataflow_wrapper_Block_entry_calc_weights_attn_weights_attn_scalars_rd_calc_weig_U0_ap_ready & grp_dataflow_wrapper_fu_6443.dataflow_wrapper_Block_entry_calc_weights_attn_weights_attn_scalars_rd_calc_weig_U0.ap_idle & ~grp_dataflow_wrapper_fu_6443.ap_sync_task_read_fm_split_U0_ap_ready)) begin
                            $display("//      Blocked by input sync logic with process : 'vit_block_top_vit_block_top.grp_dataflow_wrapper_fu_6443.task_read_fm_split_U0'");
                        end
                    end
                    endcase
                end
                10 : begin // for proc 'vit_block_top_vit_block_top.grp_dataflow_wrapper_fu_6443.task_compute_attn_U0'
                    case(index2)
                    9: begin //  for dep proc 'vit_block_top_vit_block_top.grp_dataflow_wrapper_fu_6443.dataflow_wrapper_Block_entry_calc_weights_attn_weights_attn_scalars_rd_calc_weig_U0'
// for dep channel 'vit_block_top_vit_block_top.grp_dataflow_wrapper_fu_6443.calc_weights_attn_weights_attn_scalars_idx_val_loc_channel_U' info is :
// blk sig is {{~vit_block_top_vit_block_top_inst.grp_dataflow_wrapper_fu_6443.calc_weights_attn_weights_attn_scalars_idx_val_loc_channel_U.if_empty_n & vit_block_top_vit_block_top_inst.grp_dataflow_wrapper_fu_6443.task_compute_attn_U0.ap_idle & ~vit_block_top_vit_block_top_inst.grp_dataflow_wrapper_fu_6443.calc_weights_attn_weights_attn_scalars_idx_val_loc_channel_U.if_write} TLF_FIFO}
                        if ((~grp_dataflow_wrapper_fu_6443.calc_weights_attn_weights_attn_scalars_idx_val_loc_channel_U.if_empty_n & grp_dataflow_wrapper_fu_6443.task_compute_attn_U0.ap_idle & ~grp_dataflow_wrapper_fu_6443.calc_weights_attn_weights_attn_scalars_idx_val_loc_channel_U.if_write)) begin
                            if (~grp_dataflow_wrapper_fu_6443.calc_weights_attn_weights_attn_scalars_idx_val_loc_channel_U.if_empty_n) begin
                                $display("//      Blocked by empty input FIFO 'vit_block_top_vit_block_top.grp_dataflow_wrapper_fu_6443.calc_weights_attn_weights_attn_scalars_idx_val_loc_channel_U' written by process 'vit_block_top_vit_block_top.grp_dataflow_wrapper_fu_6443.dataflow_wrapper_Block_entry_calc_weights_attn_weights_attn_scalars_rd_calc_weig_U0'");
                                $fdisplay(fp, "Dependence_Channel_path vit_block_top_vit_block_top.grp_dataflow_wrapper_fu_6443.calc_weights_attn_weights_attn_scalars_idx_val_loc_channel_U");
                                $fdisplay(fp, "Dependence_Channel_status EMPTY");
                            end
                            else if (~grp_dataflow_wrapper_fu_6443.calc_weights_attn_weights_attn_scalars_idx_val_loc_channel_U.if_full_n) begin
                                $display("//      Blocked by full output FIFO 'vit_block_top_vit_block_top.grp_dataflow_wrapper_fu_6443.calc_weights_attn_weights_attn_scalars_idx_val_loc_channel_U' read by process 'vit_block_top_vit_block_top.grp_dataflow_wrapper_fu_6443.dataflow_wrapper_Block_entry_calc_weights_attn_weights_attn_scalars_rd_calc_weig_U0'");
                                $fdisplay(fp, "Dependence_Channel_path vit_block_top_vit_block_top.grp_dataflow_wrapper_fu_6443.calc_weights_attn_weights_attn_scalars_idx_val_loc_channel_U");
                                $fdisplay(fp, "Dependence_Channel_status FULL");
                            end
                        end
// for dep channel 'vit_block_top_vit_block_top.grp_dataflow_wrapper_fu_6443.calc_weights_attn_weights_attn_scalars_idx6_val_loc_channel_U' info is :
// blk sig is {{~vit_block_top_vit_block_top_inst.grp_dataflow_wrapper_fu_6443.calc_weights_attn_weights_attn_scalars_idx6_val_loc_channel_U.if_empty_n & vit_block_top_vit_block_top_inst.grp_dataflow_wrapper_fu_6443.task_compute_attn_U0.ap_idle & ~vit_block_top_vit_block_top_inst.grp_dataflow_wrapper_fu_6443.calc_weights_attn_weights_attn_scalars_idx6_val_loc_channel_U.if_write} TLF_FIFO}
                        if ((~grp_dataflow_wrapper_fu_6443.calc_weights_attn_weights_attn_scalars_idx6_val_loc_channel_U.if_empty_n & grp_dataflow_wrapper_fu_6443.task_compute_attn_U0.ap_idle & ~grp_dataflow_wrapper_fu_6443.calc_weights_attn_weights_attn_scalars_idx6_val_loc_channel_U.if_write)) begin
                            if (~grp_dataflow_wrapper_fu_6443.calc_weights_attn_weights_attn_scalars_idx6_val_loc_channel_U.if_empty_n) begin
                                $display("//      Blocked by empty input FIFO 'vit_block_top_vit_block_top.grp_dataflow_wrapper_fu_6443.calc_weights_attn_weights_attn_scalars_idx6_val_loc_channel_U' written by process 'vit_block_top_vit_block_top.grp_dataflow_wrapper_fu_6443.dataflow_wrapper_Block_entry_calc_weights_attn_weights_attn_scalars_rd_calc_weig_U0'");
                                $fdisplay(fp, "Dependence_Channel_path vit_block_top_vit_block_top.grp_dataflow_wrapper_fu_6443.calc_weights_attn_weights_attn_scalars_idx6_val_loc_channel_U");
                                $fdisplay(fp, "Dependence_Channel_status EMPTY");
                            end
                            else if (~grp_dataflow_wrapper_fu_6443.calc_weights_attn_weights_attn_scalars_idx6_val_loc_channel_U.if_full_n) begin
                                $display("//      Blocked by full output FIFO 'vit_block_top_vit_block_top.grp_dataflow_wrapper_fu_6443.calc_weights_attn_weights_attn_scalars_idx6_val_loc_channel_U' read by process 'vit_block_top_vit_block_top.grp_dataflow_wrapper_fu_6443.dataflow_wrapper_Block_entry_calc_weights_attn_weights_attn_scalars_rd_calc_weig_U0'");
                                $fdisplay(fp, "Dependence_Channel_path vit_block_top_vit_block_top.grp_dataflow_wrapper_fu_6443.calc_weights_attn_weights_attn_scalars_idx6_val_loc_channel_U");
                                $fdisplay(fp, "Dependence_Channel_status FULL");
                            end
                        end
                    end
                    8: begin //  for dep proc 'vit_block_top_vit_block_top.grp_dataflow_wrapper_fu_6443.task_read_fm_split_U0'
// for dep channel 'vit_block_top_vit_block_top.grp_dataflow_wrapper_fu_6443.i_stream_main_U' info is :
// blk sig is {~vit_block_top_vit_block_top_inst.grp_dataflow_wrapper_fu_6443.task_compute_attn_U0.grp_do_attn_1_fu_5150.do_layernorm_inter_token_1_U0.grp_do_layernorm_inter_token_1_Pipeline_WAVE_LOOP_CT_PIPELINE_LOOP_fu_138.i_stream_main_blk_n data_FIFO}
                        if ((~grp_dataflow_wrapper_fu_6443.task_compute_attn_U0.grp_do_attn_1_fu_5150.do_layernorm_inter_token_1_U0.grp_do_layernorm_inter_token_1_Pipeline_WAVE_LOOP_CT_PIPELINE_LOOP_fu_138.i_stream_main_blk_n)) begin
                            if (~grp_dataflow_wrapper_fu_6443.i_stream_main_U.if_empty_n) begin
                                $display("//      Blocked by empty input FIFO 'vit_block_top_vit_block_top.grp_dataflow_wrapper_fu_6443.i_stream_main_U' written by process 'vit_block_top_vit_block_top.grp_dataflow_wrapper_fu_6443.task_read_fm_split_U0'");
                                $fdisplay(fp, "Dependence_Channel_path vit_block_top_vit_block_top.grp_dataflow_wrapper_fu_6443.i_stream_main_U");
                                $fdisplay(fp, "Dependence_Channel_status EMPTY");
                            end
                            else if (~grp_dataflow_wrapper_fu_6443.i_stream_main_U.if_full_n) begin
                                $display("//      Blocked by full output FIFO 'vit_block_top_vit_block_top.grp_dataflow_wrapper_fu_6443.i_stream_main_U' read by process 'vit_block_top_vit_block_top.grp_dataflow_wrapper_fu_6443.task_read_fm_split_U0'");
                                $fdisplay(fp, "Dependence_Channel_path vit_block_top_vit_block_top.grp_dataflow_wrapper_fu_6443.i_stream_main_U");
                                $fdisplay(fp, "Dependence_Channel_status FULL");
                            end
                        end
// for dep channel 'vit_block_top_vit_block_top.grp_dataflow_wrapper_fu_6443.i_stream_resi_U' info is :
// blk sig is {~vit_block_top_vit_block_top_inst.grp_dataflow_wrapper_fu_6443.task_compute_attn_U0.grp_do_attn_1_fu_5150.do_adapt_10_U0.i_stream_resi_blk_n data_FIFO}
                        if ((~grp_dataflow_wrapper_fu_6443.task_compute_attn_U0.grp_do_attn_1_fu_5150.do_adapt_10_U0.i_stream_resi_blk_n)) begin
                            if (~grp_dataflow_wrapper_fu_6443.i_stream_resi_U.if_empty_n) begin
                                $display("//      Blocked by empty input FIFO 'vit_block_top_vit_block_top.grp_dataflow_wrapper_fu_6443.i_stream_resi_U' written by process 'vit_block_top_vit_block_top.grp_dataflow_wrapper_fu_6443.task_read_fm_split_U0'");
                                $fdisplay(fp, "Dependence_Channel_path vit_block_top_vit_block_top.grp_dataflow_wrapper_fu_6443.i_stream_resi_U");
                                $fdisplay(fp, "Dependence_Channel_status EMPTY");
                            end
                            else if (~grp_dataflow_wrapper_fu_6443.i_stream_resi_U.if_full_n) begin
                                $display("//      Blocked by full output FIFO 'vit_block_top_vit_block_top.grp_dataflow_wrapper_fu_6443.i_stream_resi_U' read by process 'vit_block_top_vit_block_top.grp_dataflow_wrapper_fu_6443.task_read_fm_split_U0'");
                                $fdisplay(fp, "Dependence_Channel_path vit_block_top_vit_block_top.grp_dataflow_wrapper_fu_6443.i_stream_resi_U");
                                $fdisplay(fp, "Dependence_Channel_status FULL");
                            end
                        end
                    end
                    47: begin //  for dep proc 'vit_block_top_vit_block_top.grp_dataflow_wrapper_fu_6443.task_stream_cast_U0'
// for dep channel 'vit_block_top_vit_block_top.grp_dataflow_wrapper_fu_6443.mid_stream_int_U' info is :
// blk sig is {~vit_block_top_vit_block_top_inst.grp_dataflow_wrapper_fu_6443.task_compute_attn_U0.grp_do_attn_1_fu_5150.stream_merge_1_U0.grp_stream_merge_1_Pipeline_VITIS_LOOP_554_1_VITIS_LOOP_555_2_fu_34.mid_stream_int_blk_n data_FIFO}
                        if ((~grp_dataflow_wrapper_fu_6443.task_compute_attn_U0.grp_do_attn_1_fu_5150.stream_merge_1_U0.grp_stream_merge_1_Pipeline_VITIS_LOOP_554_1_VITIS_LOOP_555_2_fu_34.mid_stream_int_blk_n)) begin
                            if (~grp_dataflow_wrapper_fu_6443.mid_stream_int_U.if_empty_n) begin
                                $display("//      Blocked by empty input FIFO 'vit_block_top_vit_block_top.grp_dataflow_wrapper_fu_6443.mid_stream_int_U' written by process 'vit_block_top_vit_block_top.grp_dataflow_wrapper_fu_6443.task_stream_cast_U0'");
                                $fdisplay(fp, "Dependence_Channel_path vit_block_top_vit_block_top.grp_dataflow_wrapper_fu_6443.mid_stream_int_U");
                                $fdisplay(fp, "Dependence_Channel_status EMPTY");
                            end
                            else if (~grp_dataflow_wrapper_fu_6443.mid_stream_int_U.if_full_n) begin
                                $display("//      Blocked by full output FIFO 'vit_block_top_vit_block_top.grp_dataflow_wrapper_fu_6443.mid_stream_int_U' read by process 'vit_block_top_vit_block_top.grp_dataflow_wrapper_fu_6443.task_stream_cast_U0'");
                                $fdisplay(fp, "Dependence_Channel_path vit_block_top_vit_block_top.grp_dataflow_wrapper_fu_6443.mid_stream_int_U");
                                $fdisplay(fp, "Dependence_Channel_status FULL");
                            end
                        end
// for dep channel 'vit_block_top_vit_block_top.grp_dataflow_wrapper_fu_6443.start_for_task_stream_cast_U0_U' info is :
// blk sig is {{~vit_block_top_vit_block_top_inst.grp_dataflow_wrapper_fu_6443.start_for_task_stream_cast_U0_U.if_full_n & vit_block_top_vit_block_top_inst.grp_dataflow_wrapper_fu_6443.task_compute_attn_U0.ap_start & ~vit_block_top_vit_block_top_inst.grp_dataflow_wrapper_fu_6443.task_compute_attn_U0.real_start & (trans_in_cnt_30 == trans_out_cnt_30) & ~vit_block_top_vit_block_top_inst.grp_dataflow_wrapper_fu_6443.start_for_task_stream_cast_U0_U.if_read} start_FIFO}
                        if ((~grp_dataflow_wrapper_fu_6443.start_for_task_stream_cast_U0_U.if_full_n & grp_dataflow_wrapper_fu_6443.task_compute_attn_U0.ap_start & ~grp_dataflow_wrapper_fu_6443.task_compute_attn_U0.real_start & (trans_in_cnt_30 == trans_out_cnt_30) & ~grp_dataflow_wrapper_fu_6443.start_for_task_stream_cast_U0_U.if_read)) begin
                            $display("//      Blocked by full output start propagation FIFO 'vit_block_top_vit_block_top.grp_dataflow_wrapper_fu_6443.start_for_task_stream_cast_U0_U' read by process 'vit_block_top_vit_block_top.grp_dataflow_wrapper_fu_6443.task_stream_cast_U0',");
                        end
                    end
                    endcase
                end
                11 : begin // for proc 'vit_block_top_vit_block_top.grp_dataflow_wrapper_fu_6443.task_compute_attn_U0.grp_do_attn_1_fu_5150.do_adapt_10_U0'
                    case(index2)
                    12: begin //  for dep proc 'vit_block_top_vit_block_top.grp_dataflow_wrapper_fu_6443.task_compute_attn_U0.grp_do_attn_1_fu_5150.do_adapt_7_U0'
// for dep channel 'vit_block_top_vit_block_top.grp_dataflow_wrapper_fu_6443.task_compute_attn_U0.grp_do_attn_1_fu_5150.resi_sm_i_U' info is :
// blk sig is {~vit_block_top_vit_block_top_inst.grp_dataflow_wrapper_fu_6443.task_compute_attn_U0.grp_do_attn_1_fu_5150.do_adapt_10_U0.resi_sm_blk_n data_FIFO}
                        if ((~grp_dataflow_wrapper_fu_6443.task_compute_attn_U0.grp_do_attn_1_fu_5150.do_adapt_10_U0.resi_sm_blk_n)) begin
                            if (~grp_dataflow_wrapper_fu_6443.task_compute_attn_U0.grp_do_attn_1_fu_5150.resi_sm_i_U.if_empty_n) begin
                                $display("//      Blocked by empty input FIFO 'vit_block_top_vit_block_top.grp_dataflow_wrapper_fu_6443.task_compute_attn_U0.grp_do_attn_1_fu_5150.resi_sm_i_U' written by process 'vit_block_top_vit_block_top.grp_dataflow_wrapper_fu_6443.task_compute_attn_U0.grp_do_attn_1_fu_5150.do_adapt_7_U0'");
                                $fdisplay(fp, "Dependence_Channel_path vit_block_top_vit_block_top.grp_dataflow_wrapper_fu_6443.task_compute_attn_U0.grp_do_attn_1_fu_5150.resi_sm_i_U");
                                $fdisplay(fp, "Dependence_Channel_status EMPTY");
                            end
                            else if (~grp_dataflow_wrapper_fu_6443.task_compute_attn_U0.grp_do_attn_1_fu_5150.resi_sm_i_U.if_full_n) begin
                                $display("//      Blocked by full output FIFO 'vit_block_top_vit_block_top.grp_dataflow_wrapper_fu_6443.task_compute_attn_U0.grp_do_attn_1_fu_5150.resi_sm_i_U' read by process 'vit_block_top_vit_block_top.grp_dataflow_wrapper_fu_6443.task_compute_attn_U0.grp_do_attn_1_fu_5150.do_adapt_7_U0'");
                                $fdisplay(fp, "Dependence_Channel_path vit_block_top_vit_block_top.grp_dataflow_wrapper_fu_6443.task_compute_attn_U0.grp_do_attn_1_fu_5150.resi_sm_i_U");
                                $fdisplay(fp, "Dependence_Channel_status FULL");
                            end
                        end
// for dep channel 'vit_block_top_vit_block_top.grp_dataflow_wrapper_fu_6443.task_compute_attn_U0.grp_do_attn_1_fu_5150.start_for_do_adapt_7_U0_U' info is :
// blk sig is {{~vit_block_top_vit_block_top_inst.grp_dataflow_wrapper_fu_6443.task_compute_attn_U0.grp_do_attn_1_fu_5150.start_for_do_adapt_7_U0_U.if_full_n & vit_block_top_vit_block_top_inst.grp_dataflow_wrapper_fu_6443.task_compute_attn_U0.grp_do_attn_1_fu_5150.do_adapt_10_U0.ap_start & ~vit_block_top_vit_block_top_inst.grp_dataflow_wrapper_fu_6443.task_compute_attn_U0.grp_do_attn_1_fu_5150.do_adapt_10_U0.real_start & (trans_in_cnt_4 == trans_out_cnt_4) & ~vit_block_top_vit_block_top_inst.grp_dataflow_wrapper_fu_6443.task_compute_attn_U0.grp_do_attn_1_fu_5150.start_for_do_adapt_7_U0_U.if_read} start_FIFO}
                        if ((~grp_dataflow_wrapper_fu_6443.task_compute_attn_U0.grp_do_attn_1_fu_5150.start_for_do_adapt_7_U0_U.if_full_n & grp_dataflow_wrapper_fu_6443.task_compute_attn_U0.grp_do_attn_1_fu_5150.do_adapt_10_U0.ap_start & ~grp_dataflow_wrapper_fu_6443.task_compute_attn_U0.grp_do_attn_1_fu_5150.do_adapt_10_U0.real_start & (trans_in_cnt_4 == trans_out_cnt_4) & ~grp_dataflow_wrapper_fu_6443.task_compute_attn_U0.grp_do_attn_1_fu_5150.start_for_do_adapt_7_U0_U.if_read)) begin
                            $display("//      Blocked by full output start propagation FIFO 'vit_block_top_vit_block_top.grp_dataflow_wrapper_fu_6443.task_compute_attn_U0.grp_do_attn_1_fu_5150.start_for_do_adapt_7_U0_U' read by process 'vit_block_top_vit_block_top.grp_dataflow_wrapper_fu_6443.task_compute_attn_U0.grp_do_attn_1_fu_5150.do_adapt_7_U0',");
                        end
                    end
                    13: begin //  for dep proc 'vit_block_top_vit_block_top.grp_dataflow_wrapper_fu_6443.task_compute_attn_U0.grp_do_attn_1_fu_5150.do_layernorm_inter_token_1_U0'
// for dep channel '' info is :
// blk sig is {{vit_block_top_vit_block_top_inst.grp_dataflow_wrapper_fu_6443.task_compute_attn_U0.grp_do_attn_1_fu_5150.ap_sync_do_adapt_10_U0_ap_ready & vit_block_top_vit_block_top_inst.grp_dataflow_wrapper_fu_6443.task_compute_attn_U0.grp_do_attn_1_fu_5150.do_adapt_10_U0.ap_idle & ~vit_block_top_vit_block_top_inst.grp_dataflow_wrapper_fu_6443.task_compute_attn_U0.grp_do_attn_1_fu_5150.ap_sync_do_layernorm_inter_token_1_U0_ap_ready} input_sync}
                        if ((grp_dataflow_wrapper_fu_6443.task_compute_attn_U0.grp_do_attn_1_fu_5150.ap_sync_do_adapt_10_U0_ap_ready & grp_dataflow_wrapper_fu_6443.task_compute_attn_U0.grp_do_attn_1_fu_5150.do_adapt_10_U0.ap_idle & ~grp_dataflow_wrapper_fu_6443.task_compute_attn_U0.grp_do_attn_1_fu_5150.ap_sync_do_layernorm_inter_token_1_U0_ap_ready)) begin
                            $display("//      Blocked by input sync logic with process : 'vit_block_top_vit_block_top.grp_dataflow_wrapper_fu_6443.task_compute_attn_U0.grp_do_attn_1_fu_5150.do_layernorm_inter_token_1_U0'");
                        end
                    end
                    endcase
                end
                12 : begin // for proc 'vit_block_top_vit_block_top.grp_dataflow_wrapper_fu_6443.task_compute_attn_U0.grp_do_attn_1_fu_5150.do_adapt_7_U0'
                    case(index2)
                    11: begin //  for dep proc 'vit_block_top_vit_block_top.grp_dataflow_wrapper_fu_6443.task_compute_attn_U0.grp_do_attn_1_fu_5150.do_adapt_10_U0'
// for dep channel 'vit_block_top_vit_block_top.grp_dataflow_wrapper_fu_6443.task_compute_attn_U0.grp_do_attn_1_fu_5150.resi_sm_i_U' info is :
// blk sig is {~vit_block_top_vit_block_top_inst.grp_dataflow_wrapper_fu_6443.task_compute_attn_U0.grp_do_attn_1_fu_5150.do_adapt_7_U0.resi_sm_blk_n data_FIFO}
                        if ((~grp_dataflow_wrapper_fu_6443.task_compute_attn_U0.grp_do_attn_1_fu_5150.do_adapt_7_U0.resi_sm_blk_n)) begin
                            if (~grp_dataflow_wrapper_fu_6443.task_compute_attn_U0.grp_do_attn_1_fu_5150.resi_sm_i_U.if_empty_n) begin
                                $display("//      Blocked by empty input FIFO 'vit_block_top_vit_block_top.grp_dataflow_wrapper_fu_6443.task_compute_attn_U0.grp_do_attn_1_fu_5150.resi_sm_i_U' written by process 'vit_block_top_vit_block_top.grp_dataflow_wrapper_fu_6443.task_compute_attn_U0.grp_do_attn_1_fu_5150.do_adapt_10_U0'");
                                $fdisplay(fp, "Dependence_Channel_path vit_block_top_vit_block_top.grp_dataflow_wrapper_fu_6443.task_compute_attn_U0.grp_do_attn_1_fu_5150.resi_sm_i_U");
                                $fdisplay(fp, "Dependence_Channel_status EMPTY");
                            end
                            else if (~grp_dataflow_wrapper_fu_6443.task_compute_attn_U0.grp_do_attn_1_fu_5150.resi_sm_i_U.if_full_n) begin
                                $display("//      Blocked by full output FIFO 'vit_block_top_vit_block_top.grp_dataflow_wrapper_fu_6443.task_compute_attn_U0.grp_do_attn_1_fu_5150.resi_sm_i_U' read by process 'vit_block_top_vit_block_top.grp_dataflow_wrapper_fu_6443.task_compute_attn_U0.grp_do_attn_1_fu_5150.do_adapt_10_U0'");
                                $fdisplay(fp, "Dependence_Channel_path vit_block_top_vit_block_top.grp_dataflow_wrapper_fu_6443.task_compute_attn_U0.grp_do_attn_1_fu_5150.resi_sm_i_U");
                                $fdisplay(fp, "Dependence_Channel_status FULL");
                            end
                        end
// for dep channel 'vit_block_top_vit_block_top.grp_dataflow_wrapper_fu_6443.task_compute_attn_U0.grp_do_attn_1_fu_5150.start_for_do_adapt_7_U0_U' info is :
// blk sig is {{~vit_block_top_vit_block_top_inst.grp_dataflow_wrapper_fu_6443.task_compute_attn_U0.grp_do_attn_1_fu_5150.start_for_do_adapt_7_U0_U.if_empty_n & vit_block_top_vit_block_top_inst.grp_dataflow_wrapper_fu_6443.task_compute_attn_U0.grp_do_attn_1_fu_5150.do_adapt_7_U0.ap_idle & ~vit_block_top_vit_block_top_inst.grp_dataflow_wrapper_fu_6443.task_compute_attn_U0.grp_do_attn_1_fu_5150.start_for_do_adapt_7_U0_U.if_write} start_FIFO}
                        if ((~grp_dataflow_wrapper_fu_6443.task_compute_attn_U0.grp_do_attn_1_fu_5150.start_for_do_adapt_7_U0_U.if_empty_n & grp_dataflow_wrapper_fu_6443.task_compute_attn_U0.grp_do_attn_1_fu_5150.do_adapt_7_U0.ap_idle & ~grp_dataflow_wrapper_fu_6443.task_compute_attn_U0.grp_do_attn_1_fu_5150.start_for_do_adapt_7_U0_U.if_write)) begin
                            $display("//      Blocked by missing 'ap_start' from start propagation FIFO 'vit_block_top_vit_block_top.grp_dataflow_wrapper_fu_6443.task_compute_attn_U0.grp_do_attn_1_fu_5150.start_for_do_adapt_7_U0_U' written by process 'vit_block_top_vit_block_top.grp_dataflow_wrapper_fu_6443.task_compute_attn_U0.grp_do_attn_1_fu_5150.do_adapt_10_U0',");
                        end
                    end
                    46: begin //  for dep proc 'vit_block_top_vit_block_top.grp_dataflow_wrapper_fu_6443.task_compute_attn_U0.grp_do_attn_1_fu_5150.stream_merge_1_U0'
// for dep channel 'vit_block_top_vit_block_top.grp_dataflow_wrapper_fu_6443.task_compute_attn_U0.grp_do_attn_1_fu_5150.resi_o_sm_i_U' info is :
// blk sig is {~vit_block_top_vit_block_top_inst.grp_dataflow_wrapper_fu_6443.task_compute_attn_U0.grp_do_attn_1_fu_5150.do_adapt_7_U0.resi_o_sm_blk_n data_FIFO}
                        if ((~grp_dataflow_wrapper_fu_6443.task_compute_attn_U0.grp_do_attn_1_fu_5150.do_adapt_7_U0.resi_o_sm_blk_n)) begin
                            if (~grp_dataflow_wrapper_fu_6443.task_compute_attn_U0.grp_do_attn_1_fu_5150.resi_o_sm_i_U.if_empty_n) begin
                                $display("//      Blocked by empty input FIFO 'vit_block_top_vit_block_top.grp_dataflow_wrapper_fu_6443.task_compute_attn_U0.grp_do_attn_1_fu_5150.resi_o_sm_i_U' written by process 'vit_block_top_vit_block_top.grp_dataflow_wrapper_fu_6443.task_compute_attn_U0.grp_do_attn_1_fu_5150.stream_merge_1_U0'");
                                $fdisplay(fp, "Dependence_Channel_path vit_block_top_vit_block_top.grp_dataflow_wrapper_fu_6443.task_compute_attn_U0.grp_do_attn_1_fu_5150.resi_o_sm_i_U");
                                $fdisplay(fp, "Dependence_Channel_status EMPTY");
                            end
                            else if (~grp_dataflow_wrapper_fu_6443.task_compute_attn_U0.grp_do_attn_1_fu_5150.resi_o_sm_i_U.if_full_n) begin
                                $display("//      Blocked by full output FIFO 'vit_block_top_vit_block_top.grp_dataflow_wrapper_fu_6443.task_compute_attn_U0.grp_do_attn_1_fu_5150.resi_o_sm_i_U' read by process 'vit_block_top_vit_block_top.grp_dataflow_wrapper_fu_6443.task_compute_attn_U0.grp_do_attn_1_fu_5150.stream_merge_1_U0'");
                                $fdisplay(fp, "Dependence_Channel_path vit_block_top_vit_block_top.grp_dataflow_wrapper_fu_6443.task_compute_attn_U0.grp_do_attn_1_fu_5150.resi_o_sm_i_U");
                                $fdisplay(fp, "Dependence_Channel_status FULL");
                            end
                        end
// for dep channel 'vit_block_top_vit_block_top.grp_dataflow_wrapper_fu_6443.task_compute_attn_U0.grp_do_attn_1_fu_5150.start_for_stream_merge_1_U0_U' info is :
// blk sig is {{~vit_block_top_vit_block_top_inst.grp_dataflow_wrapper_fu_6443.task_compute_attn_U0.grp_do_attn_1_fu_5150.start_for_stream_merge_1_U0_U.if_full_n & vit_block_top_vit_block_top_inst.grp_dataflow_wrapper_fu_6443.task_compute_attn_U0.grp_do_attn_1_fu_5150.do_adapt_7_U0.ap_start & ~vit_block_top_vit_block_top_inst.grp_dataflow_wrapper_fu_6443.task_compute_attn_U0.grp_do_attn_1_fu_5150.do_adapt_7_U0.real_start & (trans_in_cnt_29 == trans_out_cnt_29) & ~vit_block_top_vit_block_top_inst.grp_dataflow_wrapper_fu_6443.task_compute_attn_U0.grp_do_attn_1_fu_5150.start_for_stream_merge_1_U0_U.if_read} start_FIFO}
                        if ((~grp_dataflow_wrapper_fu_6443.task_compute_attn_U0.grp_do_attn_1_fu_5150.start_for_stream_merge_1_U0_U.if_full_n & grp_dataflow_wrapper_fu_6443.task_compute_attn_U0.grp_do_attn_1_fu_5150.do_adapt_7_U0.ap_start & ~grp_dataflow_wrapper_fu_6443.task_compute_attn_U0.grp_do_attn_1_fu_5150.do_adapt_7_U0.real_start & (trans_in_cnt_29 == trans_out_cnt_29) & ~grp_dataflow_wrapper_fu_6443.task_compute_attn_U0.grp_do_attn_1_fu_5150.start_for_stream_merge_1_U0_U.if_read)) begin
                            $display("//      Blocked by full output start propagation FIFO 'vit_block_top_vit_block_top.grp_dataflow_wrapper_fu_6443.task_compute_attn_U0.grp_do_attn_1_fu_5150.start_for_stream_merge_1_U0_U' read by process 'vit_block_top_vit_block_top.grp_dataflow_wrapper_fu_6443.task_compute_attn_U0.grp_do_attn_1_fu_5150.stream_merge_1_U0',");
                        end
                    end
                    endcase
                end
                13 : begin // for proc 'vit_block_top_vit_block_top.grp_dataflow_wrapper_fu_6443.task_compute_attn_U0.grp_do_attn_1_fu_5150.do_layernorm_inter_token_1_U0'
                    case(index2)
                    14: begin //  for dep proc 'vit_block_top_vit_block_top.grp_dataflow_wrapper_fu_6443.task_compute_attn_U0.grp_do_attn_1_fu_5150.stream_copy3_U0'
// for dep channel 'vit_block_top_vit_block_top.grp_dataflow_wrapper_fu_6443.task_compute_attn_U0.grp_do_attn_1_fu_5150.lnq_sm_i_U' info is :
// blk sig is {~vit_block_top_vit_block_top_inst.grp_dataflow_wrapper_fu_6443.task_compute_attn_U0.grp_do_attn_1_fu_5150.do_layernorm_inter_token_1_U0.grp_do_layernorm_inter_token_1_Pipeline_WAVE_LOOP_CT_PIPELINE_LOOP_fu_138.lnq_sm_blk_n data_FIFO}
                        if ((~grp_dataflow_wrapper_fu_6443.task_compute_attn_U0.grp_do_attn_1_fu_5150.do_layernorm_inter_token_1_U0.grp_do_layernorm_inter_token_1_Pipeline_WAVE_LOOP_CT_PIPELINE_LOOP_fu_138.lnq_sm_blk_n)) begin
                            if (~grp_dataflow_wrapper_fu_6443.task_compute_attn_U0.grp_do_attn_1_fu_5150.lnq_sm_i_U.if_empty_n) begin
                                $display("//      Blocked by empty input FIFO 'vit_block_top_vit_block_top.grp_dataflow_wrapper_fu_6443.task_compute_attn_U0.grp_do_attn_1_fu_5150.lnq_sm_i_U' written by process 'vit_block_top_vit_block_top.grp_dataflow_wrapper_fu_6443.task_compute_attn_U0.grp_do_attn_1_fu_5150.stream_copy3_U0'");
                                $fdisplay(fp, "Dependence_Channel_path vit_block_top_vit_block_top.grp_dataflow_wrapper_fu_6443.task_compute_attn_U0.grp_do_attn_1_fu_5150.lnq_sm_i_U");
                                $fdisplay(fp, "Dependence_Channel_status EMPTY");
                            end
                            else if (~grp_dataflow_wrapper_fu_6443.task_compute_attn_U0.grp_do_attn_1_fu_5150.lnq_sm_i_U.if_full_n) begin
                                $display("//      Blocked by full output FIFO 'vit_block_top_vit_block_top.grp_dataflow_wrapper_fu_6443.task_compute_attn_U0.grp_do_attn_1_fu_5150.lnq_sm_i_U' read by process 'vit_block_top_vit_block_top.grp_dataflow_wrapper_fu_6443.task_compute_attn_U0.grp_do_attn_1_fu_5150.stream_copy3_U0'");
                                $fdisplay(fp, "Dependence_Channel_path vit_block_top_vit_block_top.grp_dataflow_wrapper_fu_6443.task_compute_attn_U0.grp_do_attn_1_fu_5150.lnq_sm_i_U");
                                $fdisplay(fp, "Dependence_Channel_status FULL");
                            end
                        end
// for dep channel 'vit_block_top_vit_block_top.grp_dataflow_wrapper_fu_6443.task_compute_attn_U0.grp_do_attn_1_fu_5150.start_for_stream_copy3_U0_U' info is :
// blk sig is {{~vit_block_top_vit_block_top_inst.grp_dataflow_wrapper_fu_6443.task_compute_attn_U0.grp_do_attn_1_fu_5150.start_for_stream_copy3_U0_U.if_full_n & vit_block_top_vit_block_top_inst.grp_dataflow_wrapper_fu_6443.task_compute_attn_U0.grp_do_attn_1_fu_5150.do_layernorm_inter_token_1_U0.ap_start & ~vit_block_top_vit_block_top_inst.grp_dataflow_wrapper_fu_6443.task_compute_attn_U0.grp_do_attn_1_fu_5150.do_layernorm_inter_token_1_U0.real_start & (trans_in_cnt_5 == trans_out_cnt_5) & ~vit_block_top_vit_block_top_inst.grp_dataflow_wrapper_fu_6443.task_compute_attn_U0.grp_do_attn_1_fu_5150.start_for_stream_copy3_U0_U.if_read} start_FIFO}
                        if ((~grp_dataflow_wrapper_fu_6443.task_compute_attn_U0.grp_do_attn_1_fu_5150.start_for_stream_copy3_U0_U.if_full_n & grp_dataflow_wrapper_fu_6443.task_compute_attn_U0.grp_do_attn_1_fu_5150.do_layernorm_inter_token_1_U0.ap_start & ~grp_dataflow_wrapper_fu_6443.task_compute_attn_U0.grp_do_attn_1_fu_5150.do_layernorm_inter_token_1_U0.real_start & (trans_in_cnt_5 == trans_out_cnt_5) & ~grp_dataflow_wrapper_fu_6443.task_compute_attn_U0.grp_do_attn_1_fu_5150.start_for_stream_copy3_U0_U.if_read)) begin
                            $display("//      Blocked by full output start propagation FIFO 'vit_block_top_vit_block_top.grp_dataflow_wrapper_fu_6443.task_compute_attn_U0.grp_do_attn_1_fu_5150.start_for_stream_copy3_U0_U' read by process 'vit_block_top_vit_block_top.grp_dataflow_wrapper_fu_6443.task_compute_attn_U0.grp_do_attn_1_fu_5150.stream_copy3_U0',");
                        end
                    end
                    11: begin //  for dep proc 'vit_block_top_vit_block_top.grp_dataflow_wrapper_fu_6443.task_compute_attn_U0.grp_do_attn_1_fu_5150.do_adapt_10_U0'
// for dep channel '' info is :
// blk sig is {{vit_block_top_vit_block_top_inst.grp_dataflow_wrapper_fu_6443.task_compute_attn_U0.grp_do_attn_1_fu_5150.ap_sync_do_layernorm_inter_token_1_U0_ap_ready & vit_block_top_vit_block_top_inst.grp_dataflow_wrapper_fu_6443.task_compute_attn_U0.grp_do_attn_1_fu_5150.do_layernorm_inter_token_1_U0.ap_idle & ~vit_block_top_vit_block_top_inst.grp_dataflow_wrapper_fu_6443.task_compute_attn_U0.grp_do_attn_1_fu_5150.ap_sync_do_adapt_10_U0_ap_ready} input_sync}
                        if ((grp_dataflow_wrapper_fu_6443.task_compute_attn_U0.grp_do_attn_1_fu_5150.ap_sync_do_layernorm_inter_token_1_U0_ap_ready & grp_dataflow_wrapper_fu_6443.task_compute_attn_U0.grp_do_attn_1_fu_5150.do_layernorm_inter_token_1_U0.ap_idle & ~grp_dataflow_wrapper_fu_6443.task_compute_attn_U0.grp_do_attn_1_fu_5150.ap_sync_do_adapt_10_U0_ap_ready)) begin
                            $display("//      Blocked by input sync logic with process : 'vit_block_top_vit_block_top.grp_dataflow_wrapper_fu_6443.task_compute_attn_U0.grp_do_attn_1_fu_5150.do_adapt_10_U0'");
                        end
                    end
                    endcase
                end
                14 : begin // for proc 'vit_block_top_vit_block_top.grp_dataflow_wrapper_fu_6443.task_compute_attn_U0.grp_do_attn_1_fu_5150.stream_copy3_U0'
                    case(index2)
                    13: begin //  for dep proc 'vit_block_top_vit_block_top.grp_dataflow_wrapper_fu_6443.task_compute_attn_U0.grp_do_attn_1_fu_5150.do_layernorm_inter_token_1_U0'
// for dep channel 'vit_block_top_vit_block_top.grp_dataflow_wrapper_fu_6443.task_compute_attn_U0.grp_do_attn_1_fu_5150.lnq_sm_i_U' info is :
// blk sig is {~vit_block_top_vit_block_top_inst.grp_dataflow_wrapper_fu_6443.task_compute_attn_U0.grp_do_attn_1_fu_5150.stream_copy3_U0.lnq_sm_blk_n data_FIFO}
                        if ((~grp_dataflow_wrapper_fu_6443.task_compute_attn_U0.grp_do_attn_1_fu_5150.stream_copy3_U0.lnq_sm_blk_n)) begin
                            if (~grp_dataflow_wrapper_fu_6443.task_compute_attn_U0.grp_do_attn_1_fu_5150.lnq_sm_i_U.if_empty_n) begin
                                $display("//      Blocked by empty input FIFO 'vit_block_top_vit_block_top.grp_dataflow_wrapper_fu_6443.task_compute_attn_U0.grp_do_attn_1_fu_5150.lnq_sm_i_U' written by process 'vit_block_top_vit_block_top.grp_dataflow_wrapper_fu_6443.task_compute_attn_U0.grp_do_attn_1_fu_5150.do_layernorm_inter_token_1_U0'");
                                $fdisplay(fp, "Dependence_Channel_path vit_block_top_vit_block_top.grp_dataflow_wrapper_fu_6443.task_compute_attn_U0.grp_do_attn_1_fu_5150.lnq_sm_i_U");
                                $fdisplay(fp, "Dependence_Channel_status EMPTY");
                            end
                            else if (~grp_dataflow_wrapper_fu_6443.task_compute_attn_U0.grp_do_attn_1_fu_5150.lnq_sm_i_U.if_full_n) begin
                                $display("//      Blocked by full output FIFO 'vit_block_top_vit_block_top.grp_dataflow_wrapper_fu_6443.task_compute_attn_U0.grp_do_attn_1_fu_5150.lnq_sm_i_U' read by process 'vit_block_top_vit_block_top.grp_dataflow_wrapper_fu_6443.task_compute_attn_U0.grp_do_attn_1_fu_5150.do_layernorm_inter_token_1_U0'");
                                $fdisplay(fp, "Dependence_Channel_path vit_block_top_vit_block_top.grp_dataflow_wrapper_fu_6443.task_compute_attn_U0.grp_do_attn_1_fu_5150.lnq_sm_i_U");
                                $fdisplay(fp, "Dependence_Channel_status FULL");
                            end
                        end
// for dep channel 'vit_block_top_vit_block_top.grp_dataflow_wrapper_fu_6443.task_compute_attn_U0.grp_do_attn_1_fu_5150.start_for_stream_copy3_U0_U' info is :
// blk sig is {{~vit_block_top_vit_block_top_inst.grp_dataflow_wrapper_fu_6443.task_compute_attn_U0.grp_do_attn_1_fu_5150.start_for_stream_copy3_U0_U.if_empty_n & vit_block_top_vit_block_top_inst.grp_dataflow_wrapper_fu_6443.task_compute_attn_U0.grp_do_attn_1_fu_5150.stream_copy3_U0.ap_idle & ~vit_block_top_vit_block_top_inst.grp_dataflow_wrapper_fu_6443.task_compute_attn_U0.grp_do_attn_1_fu_5150.start_for_stream_copy3_U0_U.if_write} start_FIFO}
                        if ((~grp_dataflow_wrapper_fu_6443.task_compute_attn_U0.grp_do_attn_1_fu_5150.start_for_stream_copy3_U0_U.if_empty_n & grp_dataflow_wrapper_fu_6443.task_compute_attn_U0.grp_do_attn_1_fu_5150.stream_copy3_U0.ap_idle & ~grp_dataflow_wrapper_fu_6443.task_compute_attn_U0.grp_do_attn_1_fu_5150.start_for_stream_copy3_U0_U.if_write)) begin
                            $display("//      Blocked by missing 'ap_start' from start propagation FIFO 'vit_block_top_vit_block_top.grp_dataflow_wrapper_fu_6443.task_compute_attn_U0.grp_do_attn_1_fu_5150.start_for_stream_copy3_U0_U' written by process 'vit_block_top_vit_block_top.grp_dataflow_wrapper_fu_6443.task_compute_attn_U0.grp_do_attn_1_fu_5150.do_layernorm_inter_token_1_U0',");
                        end
                    end
                    15: begin //  for dep proc 'vit_block_top_vit_block_top.grp_dataflow_wrapper_fu_6443.task_compute_attn_U0.grp_do_attn_1_fu_5150.do_matmul_2_U0'
// for dep channel 'vit_block_top_vit_block_top.grp_dataflow_wrapper_fu_6443.task_compute_attn_U0.grp_do_attn_1_fu_5150.lnq_sm_cp1_i_U' info is :
// blk sig is {~vit_block_top_vit_block_top_inst.grp_dataflow_wrapper_fu_6443.task_compute_attn_U0.grp_do_attn_1_fu_5150.stream_copy3_U0.lnq_sm_cp1_blk_n data_FIFO}
                        if ((~grp_dataflow_wrapper_fu_6443.task_compute_attn_U0.grp_do_attn_1_fu_5150.stream_copy3_U0.lnq_sm_cp1_blk_n)) begin
                            if (~grp_dataflow_wrapper_fu_6443.task_compute_attn_U0.grp_do_attn_1_fu_5150.lnq_sm_cp1_i_U.if_empty_n) begin
                                $display("//      Blocked by empty input FIFO 'vit_block_top_vit_block_top.grp_dataflow_wrapper_fu_6443.task_compute_attn_U0.grp_do_attn_1_fu_5150.lnq_sm_cp1_i_U' written by process 'vit_block_top_vit_block_top.grp_dataflow_wrapper_fu_6443.task_compute_attn_U0.grp_do_attn_1_fu_5150.do_matmul_2_U0'");
                                $fdisplay(fp, "Dependence_Channel_path vit_block_top_vit_block_top.grp_dataflow_wrapper_fu_6443.task_compute_attn_U0.grp_do_attn_1_fu_5150.lnq_sm_cp1_i_U");
                                $fdisplay(fp, "Dependence_Channel_status EMPTY");
                            end
                            else if (~grp_dataflow_wrapper_fu_6443.task_compute_attn_U0.grp_do_attn_1_fu_5150.lnq_sm_cp1_i_U.if_full_n) begin
                                $display("//      Blocked by full output FIFO 'vit_block_top_vit_block_top.grp_dataflow_wrapper_fu_6443.task_compute_attn_U0.grp_do_attn_1_fu_5150.lnq_sm_cp1_i_U' read by process 'vit_block_top_vit_block_top.grp_dataflow_wrapper_fu_6443.task_compute_attn_U0.grp_do_attn_1_fu_5150.do_matmul_2_U0'");
                                $fdisplay(fp, "Dependence_Channel_path vit_block_top_vit_block_top.grp_dataflow_wrapper_fu_6443.task_compute_attn_U0.grp_do_attn_1_fu_5150.lnq_sm_cp1_i_U");
                                $fdisplay(fp, "Dependence_Channel_status FULL");
                            end
                        end
// for dep channel 'vit_block_top_vit_block_top.grp_dataflow_wrapper_fu_6443.task_compute_attn_U0.grp_do_attn_1_fu_5150.start_for_do_matmul_2_U0_U' info is :
// blk sig is {{~vit_block_top_vit_block_top_inst.grp_dataflow_wrapper_fu_6443.task_compute_attn_U0.grp_do_attn_1_fu_5150.start_for_do_matmul_2_U0_U.if_full_n & vit_block_top_vit_block_top_inst.grp_dataflow_wrapper_fu_6443.task_compute_attn_U0.grp_do_attn_1_fu_5150.stream_copy3_U0.ap_start & ~vit_block_top_vit_block_top_inst.grp_dataflow_wrapper_fu_6443.task_compute_attn_U0.grp_do_attn_1_fu_5150.stream_copy3_U0.real_start & (trans_in_cnt_6 == trans_out_cnt_6) & ~vit_block_top_vit_block_top_inst.grp_dataflow_wrapper_fu_6443.task_compute_attn_U0.grp_do_attn_1_fu_5150.start_for_do_matmul_2_U0_U.if_read} start_FIFO}
                        if ((~grp_dataflow_wrapper_fu_6443.task_compute_attn_U0.grp_do_attn_1_fu_5150.start_for_do_matmul_2_U0_U.if_full_n & grp_dataflow_wrapper_fu_6443.task_compute_attn_U0.grp_do_attn_1_fu_5150.stream_copy3_U0.ap_start & ~grp_dataflow_wrapper_fu_6443.task_compute_attn_U0.grp_do_attn_1_fu_5150.stream_copy3_U0.real_start & (trans_in_cnt_6 == trans_out_cnt_6) & ~grp_dataflow_wrapper_fu_6443.task_compute_attn_U0.grp_do_attn_1_fu_5150.start_for_do_matmul_2_U0_U.if_read)) begin
                            $display("//      Blocked by full output start propagation FIFO 'vit_block_top_vit_block_top.grp_dataflow_wrapper_fu_6443.task_compute_attn_U0.grp_do_attn_1_fu_5150.start_for_do_matmul_2_U0_U' read by process 'vit_block_top_vit_block_top.grp_dataflow_wrapper_fu_6443.task_compute_attn_U0.grp_do_attn_1_fu_5150.do_matmul_2_U0',");
                        end
                    end
                    16: begin //  for dep proc 'vit_block_top_vit_block_top.grp_dataflow_wrapper_fu_6443.task_compute_attn_U0.grp_do_attn_1_fu_5150.do_matmul_2_U0.do_adapt_2_U0'
// for dep channel 'vit_block_top_vit_block_top.grp_dataflow_wrapper_fu_6443.task_compute_attn_U0.grp_do_attn_1_fu_5150.lnq_sm_cp1_i_U' info is :
// blk sig is {~vit_block_top_vit_block_top_inst.grp_dataflow_wrapper_fu_6443.task_compute_attn_U0.grp_do_attn_1_fu_5150.stream_copy3_U0.lnq_sm_cp1_blk_n data_FIFO}
                        if ((~grp_dataflow_wrapper_fu_6443.task_compute_attn_U0.grp_do_attn_1_fu_5150.stream_copy3_U0.lnq_sm_cp1_blk_n)) begin
                            if (~grp_dataflow_wrapper_fu_6443.task_compute_attn_U0.grp_do_attn_1_fu_5150.lnq_sm_cp1_i_U.if_empty_n) begin
                                $display("//      Blocked by empty input FIFO 'vit_block_top_vit_block_top.grp_dataflow_wrapper_fu_6443.task_compute_attn_U0.grp_do_attn_1_fu_5150.lnq_sm_cp1_i_U' written by process 'vit_block_top_vit_block_top.grp_dataflow_wrapper_fu_6443.task_compute_attn_U0.grp_do_attn_1_fu_5150.do_matmul_2_U0.do_adapt_2_U0'");
                                $fdisplay(fp, "Dependence_Channel_path vit_block_top_vit_block_top.grp_dataflow_wrapper_fu_6443.task_compute_attn_U0.grp_do_attn_1_fu_5150.lnq_sm_cp1_i_U");
                                $fdisplay(fp, "Dependence_Channel_status EMPTY");
                            end
                            else if (~grp_dataflow_wrapper_fu_6443.task_compute_attn_U0.grp_do_attn_1_fu_5150.lnq_sm_cp1_i_U.if_full_n) begin
                                $display("//      Blocked by full output FIFO 'vit_block_top_vit_block_top.grp_dataflow_wrapper_fu_6443.task_compute_attn_U0.grp_do_attn_1_fu_5150.lnq_sm_cp1_i_U' read by process 'vit_block_top_vit_block_top.grp_dataflow_wrapper_fu_6443.task_compute_attn_U0.grp_do_attn_1_fu_5150.do_matmul_2_U0.do_adapt_2_U0'");
                                $fdisplay(fp, "Dependence_Channel_path vit_block_top_vit_block_top.grp_dataflow_wrapper_fu_6443.task_compute_attn_U0.grp_do_attn_1_fu_5150.lnq_sm_cp1_i_U");
                                $fdisplay(fp, "Dependence_Channel_status FULL");
                            end
                        end
                    end
                    20: begin //  for dep proc 'vit_block_top_vit_block_top.grp_dataflow_wrapper_fu_6443.task_compute_attn_U0.grp_do_attn_1_fu_5150.do_matmul_2_1_U0'
// for dep channel 'vit_block_top_vit_block_top.grp_dataflow_wrapper_fu_6443.task_compute_attn_U0.grp_do_attn_1_fu_5150.lnq_sm_cp2_i_U' info is :
// blk sig is {~vit_block_top_vit_block_top_inst.grp_dataflow_wrapper_fu_6443.task_compute_attn_U0.grp_do_attn_1_fu_5150.stream_copy3_U0.lnq_sm_cp2_blk_n data_FIFO}
                        if ((~grp_dataflow_wrapper_fu_6443.task_compute_attn_U0.grp_do_attn_1_fu_5150.stream_copy3_U0.lnq_sm_cp2_blk_n)) begin
                            if (~grp_dataflow_wrapper_fu_6443.task_compute_attn_U0.grp_do_attn_1_fu_5150.lnq_sm_cp2_i_U.if_empty_n) begin
                                $display("//      Blocked by empty input FIFO 'vit_block_top_vit_block_top.grp_dataflow_wrapper_fu_6443.task_compute_attn_U0.grp_do_attn_1_fu_5150.lnq_sm_cp2_i_U' written by process 'vit_block_top_vit_block_top.grp_dataflow_wrapper_fu_6443.task_compute_attn_U0.grp_do_attn_1_fu_5150.do_matmul_2_1_U0'");
                                $fdisplay(fp, "Dependence_Channel_path vit_block_top_vit_block_top.grp_dataflow_wrapper_fu_6443.task_compute_attn_U0.grp_do_attn_1_fu_5150.lnq_sm_cp2_i_U");
                                $fdisplay(fp, "Dependence_Channel_status EMPTY");
                            end
                            else if (~grp_dataflow_wrapper_fu_6443.task_compute_attn_U0.grp_do_attn_1_fu_5150.lnq_sm_cp2_i_U.if_full_n) begin
                                $display("//      Blocked by full output FIFO 'vit_block_top_vit_block_top.grp_dataflow_wrapper_fu_6443.task_compute_attn_U0.grp_do_attn_1_fu_5150.lnq_sm_cp2_i_U' read by process 'vit_block_top_vit_block_top.grp_dataflow_wrapper_fu_6443.task_compute_attn_U0.grp_do_attn_1_fu_5150.do_matmul_2_1_U0'");
                                $fdisplay(fp, "Dependence_Channel_path vit_block_top_vit_block_top.grp_dataflow_wrapper_fu_6443.task_compute_attn_U0.grp_do_attn_1_fu_5150.lnq_sm_cp2_i_U");
                                $fdisplay(fp, "Dependence_Channel_status FULL");
                            end
                        end
// for dep channel 'vit_block_top_vit_block_top.grp_dataflow_wrapper_fu_6443.task_compute_attn_U0.grp_do_attn_1_fu_5150.start_for_do_matmul_2_1_U0_U' info is :
// blk sig is {{~vit_block_top_vit_block_top_inst.grp_dataflow_wrapper_fu_6443.task_compute_attn_U0.grp_do_attn_1_fu_5150.start_for_do_matmul_2_1_U0_U.if_full_n & vit_block_top_vit_block_top_inst.grp_dataflow_wrapper_fu_6443.task_compute_attn_U0.grp_do_attn_1_fu_5150.stream_copy3_U0.ap_start & ~vit_block_top_vit_block_top_inst.grp_dataflow_wrapper_fu_6443.task_compute_attn_U0.grp_do_attn_1_fu_5150.stream_copy3_U0.real_start & (trans_in_cnt_6 == trans_out_cnt_6) & ~vit_block_top_vit_block_top_inst.grp_dataflow_wrapper_fu_6443.task_compute_attn_U0.grp_do_attn_1_fu_5150.start_for_do_matmul_2_1_U0_U.if_read} start_FIFO}
                        if ((~grp_dataflow_wrapper_fu_6443.task_compute_attn_U0.grp_do_attn_1_fu_5150.start_for_do_matmul_2_1_U0_U.if_full_n & grp_dataflow_wrapper_fu_6443.task_compute_attn_U0.grp_do_attn_1_fu_5150.stream_copy3_U0.ap_start & ~grp_dataflow_wrapper_fu_6443.task_compute_attn_U0.grp_do_attn_1_fu_5150.stream_copy3_U0.real_start & (trans_in_cnt_6 == trans_out_cnt_6) & ~grp_dataflow_wrapper_fu_6443.task_compute_attn_U0.grp_do_attn_1_fu_5150.start_for_do_matmul_2_1_U0_U.if_read)) begin
                            $display("//      Blocked by full output start propagation FIFO 'vit_block_top_vit_block_top.grp_dataflow_wrapper_fu_6443.task_compute_attn_U0.grp_do_attn_1_fu_5150.start_for_do_matmul_2_1_U0_U' read by process 'vit_block_top_vit_block_top.grp_dataflow_wrapper_fu_6443.task_compute_attn_U0.grp_do_attn_1_fu_5150.do_matmul_2_1_U0',");
                        end
                    end
                    21: begin //  for dep proc 'vit_block_top_vit_block_top.grp_dataflow_wrapper_fu_6443.task_compute_attn_U0.grp_do_attn_1_fu_5150.do_matmul_2_1_U0.do_adapt_9_U0'
// for dep channel 'vit_block_top_vit_block_top.grp_dataflow_wrapper_fu_6443.task_compute_attn_U0.grp_do_attn_1_fu_5150.lnq_sm_cp2_i_U' info is :
// blk sig is {~vit_block_top_vit_block_top_inst.grp_dataflow_wrapper_fu_6443.task_compute_attn_U0.grp_do_attn_1_fu_5150.stream_copy3_U0.lnq_sm_cp2_blk_n data_FIFO}
                        if ((~grp_dataflow_wrapper_fu_6443.task_compute_attn_U0.grp_do_attn_1_fu_5150.stream_copy3_U0.lnq_sm_cp2_blk_n)) begin
                            if (~grp_dataflow_wrapper_fu_6443.task_compute_attn_U0.grp_do_attn_1_fu_5150.lnq_sm_cp2_i_U.if_empty_n) begin
                                $display("//      Blocked by empty input FIFO 'vit_block_top_vit_block_top.grp_dataflow_wrapper_fu_6443.task_compute_attn_U0.grp_do_attn_1_fu_5150.lnq_sm_cp2_i_U' written by process 'vit_block_top_vit_block_top.grp_dataflow_wrapper_fu_6443.task_compute_attn_U0.grp_do_attn_1_fu_5150.do_matmul_2_1_U0.do_adapt_9_U0'");
                                $fdisplay(fp, "Dependence_Channel_path vit_block_top_vit_block_top.grp_dataflow_wrapper_fu_6443.task_compute_attn_U0.grp_do_attn_1_fu_5150.lnq_sm_cp2_i_U");
                                $fdisplay(fp, "Dependence_Channel_status EMPTY");
                            end
                            else if (~grp_dataflow_wrapper_fu_6443.task_compute_attn_U0.grp_do_attn_1_fu_5150.lnq_sm_cp2_i_U.if_full_n) begin
                                $display("//      Blocked by full output FIFO 'vit_block_top_vit_block_top.grp_dataflow_wrapper_fu_6443.task_compute_attn_U0.grp_do_attn_1_fu_5150.lnq_sm_cp2_i_U' read by process 'vit_block_top_vit_block_top.grp_dataflow_wrapper_fu_6443.task_compute_attn_U0.grp_do_attn_1_fu_5150.do_matmul_2_1_U0.do_adapt_9_U0'");
                                $fdisplay(fp, "Dependence_Channel_path vit_block_top_vit_block_top.grp_dataflow_wrapper_fu_6443.task_compute_attn_U0.grp_do_attn_1_fu_5150.lnq_sm_cp2_i_U");
                                $fdisplay(fp, "Dependence_Channel_status FULL");
                            end
                        end
                    end
                    25: begin //  for dep proc 'vit_block_top_vit_block_top.grp_dataflow_wrapper_fu_6443.task_compute_attn_U0.grp_do_attn_1_fu_5150.do_matmul_4_U0'
// for dep channel 'vit_block_top_vit_block_top.grp_dataflow_wrapper_fu_6443.task_compute_attn_U0.grp_do_attn_1_fu_5150.lnq_sm_cp3_i_U' info is :
// blk sig is {~vit_block_top_vit_block_top_inst.grp_dataflow_wrapper_fu_6443.task_compute_attn_U0.grp_do_attn_1_fu_5150.stream_copy3_U0.lnq_sm_cp3_blk_n data_FIFO}
                        if ((~grp_dataflow_wrapper_fu_6443.task_compute_attn_U0.grp_do_attn_1_fu_5150.stream_copy3_U0.lnq_sm_cp3_blk_n)) begin
                            if (~grp_dataflow_wrapper_fu_6443.task_compute_attn_U0.grp_do_attn_1_fu_5150.lnq_sm_cp3_i_U.if_empty_n) begin
                                $display("//      Blocked by empty input FIFO 'vit_block_top_vit_block_top.grp_dataflow_wrapper_fu_6443.task_compute_attn_U0.grp_do_attn_1_fu_5150.lnq_sm_cp3_i_U' written by process 'vit_block_top_vit_block_top.grp_dataflow_wrapper_fu_6443.task_compute_attn_U0.grp_do_attn_1_fu_5150.do_matmul_4_U0'");
                                $fdisplay(fp, "Dependence_Channel_path vit_block_top_vit_block_top.grp_dataflow_wrapper_fu_6443.task_compute_attn_U0.grp_do_attn_1_fu_5150.lnq_sm_cp3_i_U");
                                $fdisplay(fp, "Dependence_Channel_status EMPTY");
                            end
                            else if (~grp_dataflow_wrapper_fu_6443.task_compute_attn_U0.grp_do_attn_1_fu_5150.lnq_sm_cp3_i_U.if_full_n) begin
                                $display("//      Blocked by full output FIFO 'vit_block_top_vit_block_top.grp_dataflow_wrapper_fu_6443.task_compute_attn_U0.grp_do_attn_1_fu_5150.lnq_sm_cp3_i_U' read by process 'vit_block_top_vit_block_top.grp_dataflow_wrapper_fu_6443.task_compute_attn_U0.grp_do_attn_1_fu_5150.do_matmul_4_U0'");
                                $fdisplay(fp, "Dependence_Channel_path vit_block_top_vit_block_top.grp_dataflow_wrapper_fu_6443.task_compute_attn_U0.grp_do_attn_1_fu_5150.lnq_sm_cp3_i_U");
                                $fdisplay(fp, "Dependence_Channel_status FULL");
                            end
                        end
// for dep channel 'vit_block_top_vit_block_top.grp_dataflow_wrapper_fu_6443.task_compute_attn_U0.grp_do_attn_1_fu_5150.start_for_do_matmul_4_U0_U' info is :
// blk sig is {{~vit_block_top_vit_block_top_inst.grp_dataflow_wrapper_fu_6443.task_compute_attn_U0.grp_do_attn_1_fu_5150.start_for_do_matmul_4_U0_U.if_full_n & vit_block_top_vit_block_top_inst.grp_dataflow_wrapper_fu_6443.task_compute_attn_U0.grp_do_attn_1_fu_5150.stream_copy3_U0.ap_start & ~vit_block_top_vit_block_top_inst.grp_dataflow_wrapper_fu_6443.task_compute_attn_U0.grp_do_attn_1_fu_5150.stream_copy3_U0.real_start & (trans_in_cnt_6 == trans_out_cnt_6) & ~vit_block_top_vit_block_top_inst.grp_dataflow_wrapper_fu_6443.task_compute_attn_U0.grp_do_attn_1_fu_5150.start_for_do_matmul_4_U0_U.if_read} start_FIFO}
                        if ((~grp_dataflow_wrapper_fu_6443.task_compute_attn_U0.grp_do_attn_1_fu_5150.start_for_do_matmul_4_U0_U.if_full_n & grp_dataflow_wrapper_fu_6443.task_compute_attn_U0.grp_do_attn_1_fu_5150.stream_copy3_U0.ap_start & ~grp_dataflow_wrapper_fu_6443.task_compute_attn_U0.grp_do_attn_1_fu_5150.stream_copy3_U0.real_start & (trans_in_cnt_6 == trans_out_cnt_6) & ~grp_dataflow_wrapper_fu_6443.task_compute_attn_U0.grp_do_attn_1_fu_5150.start_for_do_matmul_4_U0_U.if_read)) begin
                            $display("//      Blocked by full output start propagation FIFO 'vit_block_top_vit_block_top.grp_dataflow_wrapper_fu_6443.task_compute_attn_U0.grp_do_attn_1_fu_5150.start_for_do_matmul_4_U0_U' read by process 'vit_block_top_vit_block_top.grp_dataflow_wrapper_fu_6443.task_compute_attn_U0.grp_do_attn_1_fu_5150.do_matmul_4_U0',");
                        end
                    end
                    26: begin //  for dep proc 'vit_block_top_vit_block_top.grp_dataflow_wrapper_fu_6443.task_compute_attn_U0.grp_do_attn_1_fu_5150.do_matmul_4_U0.do_adapt_13_U0'
// for dep channel 'vit_block_top_vit_block_top.grp_dataflow_wrapper_fu_6443.task_compute_attn_U0.grp_do_attn_1_fu_5150.lnq_sm_cp3_i_U' info is :
// blk sig is {~vit_block_top_vit_block_top_inst.grp_dataflow_wrapper_fu_6443.task_compute_attn_U0.grp_do_attn_1_fu_5150.stream_copy3_U0.lnq_sm_cp3_blk_n data_FIFO}
                        if ((~grp_dataflow_wrapper_fu_6443.task_compute_attn_U0.grp_do_attn_1_fu_5150.stream_copy3_U0.lnq_sm_cp3_blk_n)) begin
                            if (~grp_dataflow_wrapper_fu_6443.task_compute_attn_U0.grp_do_attn_1_fu_5150.lnq_sm_cp3_i_U.if_empty_n) begin
                                $display("//      Blocked by empty input FIFO 'vit_block_top_vit_block_top.grp_dataflow_wrapper_fu_6443.task_compute_attn_U0.grp_do_attn_1_fu_5150.lnq_sm_cp3_i_U' written by process 'vit_block_top_vit_block_top.grp_dataflow_wrapper_fu_6443.task_compute_attn_U0.grp_do_attn_1_fu_5150.do_matmul_4_U0.do_adapt_13_U0'");
                                $fdisplay(fp, "Dependence_Channel_path vit_block_top_vit_block_top.grp_dataflow_wrapper_fu_6443.task_compute_attn_U0.grp_do_attn_1_fu_5150.lnq_sm_cp3_i_U");
                                $fdisplay(fp, "Dependence_Channel_status EMPTY");
                            end
                            else if (~grp_dataflow_wrapper_fu_6443.task_compute_attn_U0.grp_do_attn_1_fu_5150.lnq_sm_cp3_i_U.if_full_n) begin
                                $display("//      Blocked by full output FIFO 'vit_block_top_vit_block_top.grp_dataflow_wrapper_fu_6443.task_compute_attn_U0.grp_do_attn_1_fu_5150.lnq_sm_cp3_i_U' read by process 'vit_block_top_vit_block_top.grp_dataflow_wrapper_fu_6443.task_compute_attn_U0.grp_do_attn_1_fu_5150.do_matmul_4_U0.do_adapt_13_U0'");
                                $fdisplay(fp, "Dependence_Channel_path vit_block_top_vit_block_top.grp_dataflow_wrapper_fu_6443.task_compute_attn_U0.grp_do_attn_1_fu_5150.lnq_sm_cp3_i_U");
                                $fdisplay(fp, "Dependence_Channel_status FULL");
                            end
                        end
                    end
                    endcase
                end
                15 : begin // for proc 'vit_block_top_vit_block_top.grp_dataflow_wrapper_fu_6443.task_compute_attn_U0.grp_do_attn_1_fu_5150.do_matmul_2_U0'
                    case(index2)
                    14: begin //  for dep proc 'vit_block_top_vit_block_top.grp_dataflow_wrapper_fu_6443.task_compute_attn_U0.grp_do_attn_1_fu_5150.stream_copy3_U0'
// for dep channel 'vit_block_top_vit_block_top.grp_dataflow_wrapper_fu_6443.task_compute_attn_U0.grp_do_attn_1_fu_5150.lnq_sm_cp1_i_U' info is :
// blk sig is {~vit_block_top_vit_block_top_inst.grp_dataflow_wrapper_fu_6443.task_compute_attn_U0.grp_do_attn_1_fu_5150.do_matmul_2_U0.do_adapt_2_U0.lnq_sm_cp1_blk_n data_FIFO}
                        if ((~grp_dataflow_wrapper_fu_6443.task_compute_attn_U0.grp_do_attn_1_fu_5150.do_matmul_2_U0.do_adapt_2_U0.lnq_sm_cp1_blk_n)) begin
                            if (~grp_dataflow_wrapper_fu_6443.task_compute_attn_U0.grp_do_attn_1_fu_5150.lnq_sm_cp1_i_U.if_empty_n) begin
                                $display("//      Blocked by empty input FIFO 'vit_block_top_vit_block_top.grp_dataflow_wrapper_fu_6443.task_compute_attn_U0.grp_do_attn_1_fu_5150.lnq_sm_cp1_i_U' written by process 'vit_block_top_vit_block_top.grp_dataflow_wrapper_fu_6443.task_compute_attn_U0.grp_do_attn_1_fu_5150.stream_copy3_U0'");
                                $fdisplay(fp, "Dependence_Channel_path vit_block_top_vit_block_top.grp_dataflow_wrapper_fu_6443.task_compute_attn_U0.grp_do_attn_1_fu_5150.lnq_sm_cp1_i_U");
                                $fdisplay(fp, "Dependence_Channel_status EMPTY");
                            end
                            else if (~grp_dataflow_wrapper_fu_6443.task_compute_attn_U0.grp_do_attn_1_fu_5150.lnq_sm_cp1_i_U.if_full_n) begin
                                $display("//      Blocked by full output FIFO 'vit_block_top_vit_block_top.grp_dataflow_wrapper_fu_6443.task_compute_attn_U0.grp_do_attn_1_fu_5150.lnq_sm_cp1_i_U' read by process 'vit_block_top_vit_block_top.grp_dataflow_wrapper_fu_6443.task_compute_attn_U0.grp_do_attn_1_fu_5150.stream_copy3_U0'");
                                $fdisplay(fp, "Dependence_Channel_path vit_block_top_vit_block_top.grp_dataflow_wrapper_fu_6443.task_compute_attn_U0.grp_do_attn_1_fu_5150.lnq_sm_cp1_i_U");
                                $fdisplay(fp, "Dependence_Channel_status FULL");
                            end
                        end
// for dep channel 'vit_block_top_vit_block_top.grp_dataflow_wrapper_fu_6443.task_compute_attn_U0.grp_do_attn_1_fu_5150.start_for_do_matmul_2_U0_U' info is :
// blk sig is {{~vit_block_top_vit_block_top_inst.grp_dataflow_wrapper_fu_6443.task_compute_attn_U0.grp_do_attn_1_fu_5150.start_for_do_matmul_2_U0_U.if_empty_n & vit_block_top_vit_block_top_inst.grp_dataflow_wrapper_fu_6443.task_compute_attn_U0.grp_do_attn_1_fu_5150.do_matmul_2_U0.ap_idle & ~vit_block_top_vit_block_top_inst.grp_dataflow_wrapper_fu_6443.task_compute_attn_U0.grp_do_attn_1_fu_5150.start_for_do_matmul_2_U0_U.if_write} start_FIFO}
                        if ((~grp_dataflow_wrapper_fu_6443.task_compute_attn_U0.grp_do_attn_1_fu_5150.start_for_do_matmul_2_U0_U.if_empty_n & grp_dataflow_wrapper_fu_6443.task_compute_attn_U0.grp_do_attn_1_fu_5150.do_matmul_2_U0.ap_idle & ~grp_dataflow_wrapper_fu_6443.task_compute_attn_U0.grp_do_attn_1_fu_5150.start_for_do_matmul_2_U0_U.if_write)) begin
                            $display("//      Blocked by missing 'ap_start' from start propagation FIFO 'vit_block_top_vit_block_top.grp_dataflow_wrapper_fu_6443.task_compute_attn_U0.grp_do_attn_1_fu_5150.start_for_do_matmul_2_U0_U' written by process 'vit_block_top_vit_block_top.grp_dataflow_wrapper_fu_6443.task_compute_attn_U0.grp_do_attn_1_fu_5150.stream_copy3_U0',");
                        end
                    end
                    30: begin //  for dep proc 'vit_block_top_vit_block_top.grp_dataflow_wrapper_fu_6443.task_compute_attn_U0.grp_do_attn_1_fu_5150.do_quant_U0'
// for dep channel 'vit_block_top_vit_block_top.grp_dataflow_wrapper_fu_6443.task_compute_attn_U0.grp_do_attn_1_fu_5150.q_sm_i_U' info is :
// blk sig is {~vit_block_top_vit_block_top_inst.grp_dataflow_wrapper_fu_6443.task_compute_attn_U0.grp_do_attn_1_fu_5150.do_matmul_2_U0.do_adapt_11_U0.q_sm_blk_n data_FIFO}
                        if ((~grp_dataflow_wrapper_fu_6443.task_compute_attn_U0.grp_do_attn_1_fu_5150.do_matmul_2_U0.do_adapt_11_U0.q_sm_blk_n)) begin
                            if (~grp_dataflow_wrapper_fu_6443.task_compute_attn_U0.grp_do_attn_1_fu_5150.q_sm_i_U.if_empty_n) begin
                                $display("//      Blocked by empty input FIFO 'vit_block_top_vit_block_top.grp_dataflow_wrapper_fu_6443.task_compute_attn_U0.grp_do_attn_1_fu_5150.q_sm_i_U' written by process 'vit_block_top_vit_block_top.grp_dataflow_wrapper_fu_6443.task_compute_attn_U0.grp_do_attn_1_fu_5150.do_quant_U0'");
                                $fdisplay(fp, "Dependence_Channel_path vit_block_top_vit_block_top.grp_dataflow_wrapper_fu_6443.task_compute_attn_U0.grp_do_attn_1_fu_5150.q_sm_i_U");
                                $fdisplay(fp, "Dependence_Channel_status EMPTY");
                            end
                            else if (~grp_dataflow_wrapper_fu_6443.task_compute_attn_U0.grp_do_attn_1_fu_5150.q_sm_i_U.if_full_n) begin
                                $display("//      Blocked by full output FIFO 'vit_block_top_vit_block_top.grp_dataflow_wrapper_fu_6443.task_compute_attn_U0.grp_do_attn_1_fu_5150.q_sm_i_U' read by process 'vit_block_top_vit_block_top.grp_dataflow_wrapper_fu_6443.task_compute_attn_U0.grp_do_attn_1_fu_5150.do_quant_U0'");
                                $fdisplay(fp, "Dependence_Channel_path vit_block_top_vit_block_top.grp_dataflow_wrapper_fu_6443.task_compute_attn_U0.grp_do_attn_1_fu_5150.q_sm_i_U");
                                $fdisplay(fp, "Dependence_Channel_status FULL");
                            end
                        end
// for dep channel 'vit_block_top_vit_block_top.grp_dataflow_wrapper_fu_6443.task_compute_attn_U0.grp_do_attn_1_fu_5150.start_for_do_quant_U0_U' info is :
// blk sig is {{~vit_block_top_vit_block_top_inst.grp_dataflow_wrapper_fu_6443.task_compute_attn_U0.grp_do_attn_1_fu_5150.start_for_do_quant_U0_U.if_full_n & vit_block_top_vit_block_top_inst.grp_dataflow_wrapper_fu_6443.task_compute_attn_U0.grp_do_attn_1_fu_5150.do_matmul_2_U0.ap_start & ~vit_block_top_vit_block_top_inst.grp_dataflow_wrapper_fu_6443.task_compute_attn_U0.grp_do_attn_1_fu_5150.do_matmul_2_U0.real_start & (trans_in_cnt_16 == trans_out_cnt_16) & ~vit_block_top_vit_block_top_inst.grp_dataflow_wrapper_fu_6443.task_compute_attn_U0.grp_do_attn_1_fu_5150.start_for_do_quant_U0_U.if_read} start_FIFO}
                        if ((~grp_dataflow_wrapper_fu_6443.task_compute_attn_U0.grp_do_attn_1_fu_5150.start_for_do_quant_U0_U.if_full_n & grp_dataflow_wrapper_fu_6443.task_compute_attn_U0.grp_do_attn_1_fu_5150.do_matmul_2_U0.ap_start & ~grp_dataflow_wrapper_fu_6443.task_compute_attn_U0.grp_do_attn_1_fu_5150.do_matmul_2_U0.real_start & (trans_in_cnt_16 == trans_out_cnt_16) & ~grp_dataflow_wrapper_fu_6443.task_compute_attn_U0.grp_do_attn_1_fu_5150.start_for_do_quant_U0_U.if_read)) begin
                            $display("//      Blocked by full output start propagation FIFO 'vit_block_top_vit_block_top.grp_dataflow_wrapper_fu_6443.task_compute_attn_U0.grp_do_attn_1_fu_5150.start_for_do_quant_U0_U' read by process 'vit_block_top_vit_block_top.grp_dataflow_wrapper_fu_6443.task_compute_attn_U0.grp_do_attn_1_fu_5150.do_quant_U0',");
                        end
                    end
                    endcase
                end
                16 : begin // for proc 'vit_block_top_vit_block_top.grp_dataflow_wrapper_fu_6443.task_compute_attn_U0.grp_do_attn_1_fu_5150.do_matmul_2_U0.do_adapt_2_U0'
                    case(index2)
                    14: begin //  for dep proc 'vit_block_top_vit_block_top.grp_dataflow_wrapper_fu_6443.task_compute_attn_U0.grp_do_attn_1_fu_5150.stream_copy3_U0'
// for dep channel 'vit_block_top_vit_block_top.grp_dataflow_wrapper_fu_6443.task_compute_attn_U0.grp_do_attn_1_fu_5150.lnq_sm_cp1_i_U' info is :
// blk sig is {~vit_block_top_vit_block_top_inst.grp_dataflow_wrapper_fu_6443.task_compute_attn_U0.grp_do_attn_1_fu_5150.do_matmul_2_U0.do_adapt_2_U0.lnq_sm_cp1_blk_n data_FIFO}
                        if ((~grp_dataflow_wrapper_fu_6443.task_compute_attn_U0.grp_do_attn_1_fu_5150.do_matmul_2_U0.do_adapt_2_U0.lnq_sm_cp1_blk_n)) begin
                            if (~grp_dataflow_wrapper_fu_6443.task_compute_attn_U0.grp_do_attn_1_fu_5150.lnq_sm_cp1_i_U.if_empty_n) begin
                                $display("//      Blocked by empty input FIFO 'vit_block_top_vit_block_top.grp_dataflow_wrapper_fu_6443.task_compute_attn_U0.grp_do_attn_1_fu_5150.lnq_sm_cp1_i_U' written by process 'vit_block_top_vit_block_top.grp_dataflow_wrapper_fu_6443.task_compute_attn_U0.grp_do_attn_1_fu_5150.stream_copy3_U0'");
                                $fdisplay(fp, "Dependence_Channel_path vit_block_top_vit_block_top.grp_dataflow_wrapper_fu_6443.task_compute_attn_U0.grp_do_attn_1_fu_5150.lnq_sm_cp1_i_U");
                                $fdisplay(fp, "Dependence_Channel_status EMPTY");
                            end
                            else if (~grp_dataflow_wrapper_fu_6443.task_compute_attn_U0.grp_do_attn_1_fu_5150.lnq_sm_cp1_i_U.if_full_n) begin
                                $display("//      Blocked by full output FIFO 'vit_block_top_vit_block_top.grp_dataflow_wrapper_fu_6443.task_compute_attn_U0.grp_do_attn_1_fu_5150.lnq_sm_cp1_i_U' read by process 'vit_block_top_vit_block_top.grp_dataflow_wrapper_fu_6443.task_compute_attn_U0.grp_do_attn_1_fu_5150.stream_copy3_U0'");
                                $fdisplay(fp, "Dependence_Channel_path vit_block_top_vit_block_top.grp_dataflow_wrapper_fu_6443.task_compute_attn_U0.grp_do_attn_1_fu_5150.lnq_sm_cp1_i_U");
                                $fdisplay(fp, "Dependence_Channel_status FULL");
                            end
                        end
                    end
                    17: begin //  for dep proc 'vit_block_top_vit_block_top.grp_dataflow_wrapper_fu_6443.task_compute_attn_U0.grp_do_attn_1_fu_5150.do_matmul_2_U0.matmul_step1_cache_window_2_U0'
// for dep channel 'vit_block_top_vit_block_top.grp_dataflow_wrapper_fu_6443.task_compute_attn_U0.grp_do_attn_1_fu_5150.do_matmul_2_U0.adpt_sm_i_U' info is :
// blk sig is {~vit_block_top_vit_block_top_inst.grp_dataflow_wrapper_fu_6443.task_compute_attn_U0.grp_do_attn_1_fu_5150.do_matmul_2_U0.do_adapt_2_U0.adpt_sm_blk_n data_FIFO}
                        if ((~grp_dataflow_wrapper_fu_6443.task_compute_attn_U0.grp_do_attn_1_fu_5150.do_matmul_2_U0.do_adapt_2_U0.adpt_sm_blk_n)) begin
                            if (~grp_dataflow_wrapper_fu_6443.task_compute_attn_U0.grp_do_attn_1_fu_5150.do_matmul_2_U0.adpt_sm_i_U.if_empty_n) begin
                                $display("//      Blocked by empty input FIFO 'vit_block_top_vit_block_top.grp_dataflow_wrapper_fu_6443.task_compute_attn_U0.grp_do_attn_1_fu_5150.do_matmul_2_U0.adpt_sm_i_U' written by process 'vit_block_top_vit_block_top.grp_dataflow_wrapper_fu_6443.task_compute_attn_U0.grp_do_attn_1_fu_5150.do_matmul_2_U0.matmul_step1_cache_window_2_U0'");
                                $fdisplay(fp, "Dependence_Channel_path vit_block_top_vit_block_top.grp_dataflow_wrapper_fu_6443.task_compute_attn_U0.grp_do_attn_1_fu_5150.do_matmul_2_U0.adpt_sm_i_U");
                                $fdisplay(fp, "Dependence_Channel_status EMPTY");
                            end
                            else if (~grp_dataflow_wrapper_fu_6443.task_compute_attn_U0.grp_do_attn_1_fu_5150.do_matmul_2_U0.adpt_sm_i_U.if_full_n) begin
                                $display("//      Blocked by full output FIFO 'vit_block_top_vit_block_top.grp_dataflow_wrapper_fu_6443.task_compute_attn_U0.grp_do_attn_1_fu_5150.do_matmul_2_U0.adpt_sm_i_U' read by process 'vit_block_top_vit_block_top.grp_dataflow_wrapper_fu_6443.task_compute_attn_U0.grp_do_attn_1_fu_5150.do_matmul_2_U0.matmul_step1_cache_window_2_U0'");
                                $fdisplay(fp, "Dependence_Channel_path vit_block_top_vit_block_top.grp_dataflow_wrapper_fu_6443.task_compute_attn_U0.grp_do_attn_1_fu_5150.do_matmul_2_U0.adpt_sm_i_U");
                                $fdisplay(fp, "Dependence_Channel_status FULL");
                            end
                        end
// for dep channel 'vit_block_top_vit_block_top.grp_dataflow_wrapper_fu_6443.task_compute_attn_U0.grp_do_attn_1_fu_5150.do_matmul_2_U0.start_for_matmul_step1_cache_window_2_U0_U' info is :
// blk sig is {{~vit_block_top_vit_block_top_inst.grp_dataflow_wrapper_fu_6443.task_compute_attn_U0.grp_do_attn_1_fu_5150.do_matmul_2_U0.start_for_matmul_step1_cache_window_2_U0_U.if_full_n & vit_block_top_vit_block_top_inst.grp_dataflow_wrapper_fu_6443.task_compute_attn_U0.grp_do_attn_1_fu_5150.do_matmul_2_U0.do_adapt_2_U0.ap_start & ~vit_block_top_vit_block_top_inst.grp_dataflow_wrapper_fu_6443.task_compute_attn_U0.grp_do_attn_1_fu_5150.do_matmul_2_U0.do_adapt_2_U0.real_start & (trans_in_cnt_7 == trans_out_cnt_7) & ~vit_block_top_vit_block_top_inst.grp_dataflow_wrapper_fu_6443.task_compute_attn_U0.grp_do_attn_1_fu_5150.do_matmul_2_U0.start_for_matmul_step1_cache_window_2_U0_U.if_read} start_FIFO}
                        if ((~grp_dataflow_wrapper_fu_6443.task_compute_attn_U0.grp_do_attn_1_fu_5150.do_matmul_2_U0.start_for_matmul_step1_cache_window_2_U0_U.if_full_n & grp_dataflow_wrapper_fu_6443.task_compute_attn_U0.grp_do_attn_1_fu_5150.do_matmul_2_U0.do_adapt_2_U0.ap_start & ~grp_dataflow_wrapper_fu_6443.task_compute_attn_U0.grp_do_attn_1_fu_5150.do_matmul_2_U0.do_adapt_2_U0.real_start & (trans_in_cnt_7 == trans_out_cnt_7) & ~grp_dataflow_wrapper_fu_6443.task_compute_attn_U0.grp_do_attn_1_fu_5150.do_matmul_2_U0.start_for_matmul_step1_cache_window_2_U0_U.if_read)) begin
                            $display("//      Blocked by full output start propagation FIFO 'vit_block_top_vit_block_top.grp_dataflow_wrapper_fu_6443.task_compute_attn_U0.grp_do_attn_1_fu_5150.do_matmul_2_U0.start_for_matmul_step1_cache_window_2_U0_U' read by process 'vit_block_top_vit_block_top.grp_dataflow_wrapper_fu_6443.task_compute_attn_U0.grp_do_attn_1_fu_5150.do_matmul_2_U0.matmul_step1_cache_window_2_U0',");
                        end
                    end
                    endcase
                end
                17 : begin // for proc 'vit_block_top_vit_block_top.grp_dataflow_wrapper_fu_6443.task_compute_attn_U0.grp_do_attn_1_fu_5150.do_matmul_2_U0.matmul_step1_cache_window_2_U0'
                    case(index2)
                    16: begin //  for dep proc 'vit_block_top_vit_block_top.grp_dataflow_wrapper_fu_6443.task_compute_attn_U0.grp_do_attn_1_fu_5150.do_matmul_2_U0.do_adapt_2_U0'
// for dep channel 'vit_block_top_vit_block_top.grp_dataflow_wrapper_fu_6443.task_compute_attn_U0.grp_do_attn_1_fu_5150.do_matmul_2_U0.adpt_sm_i_U' info is :
// blk sig is {~vit_block_top_vit_block_top_inst.grp_dataflow_wrapper_fu_6443.task_compute_attn_U0.grp_do_attn_1_fu_5150.do_matmul_2_U0.matmul_step1_cache_window_2_U0.adpt_sm_blk_n data_FIFO}
                        if ((~grp_dataflow_wrapper_fu_6443.task_compute_attn_U0.grp_do_attn_1_fu_5150.do_matmul_2_U0.matmul_step1_cache_window_2_U0.adpt_sm_blk_n)) begin
                            if (~grp_dataflow_wrapper_fu_6443.task_compute_attn_U0.grp_do_attn_1_fu_5150.do_matmul_2_U0.adpt_sm_i_U.if_empty_n) begin
                                $display("//      Blocked by empty input FIFO 'vit_block_top_vit_block_top.grp_dataflow_wrapper_fu_6443.task_compute_attn_U0.grp_do_attn_1_fu_5150.do_matmul_2_U0.adpt_sm_i_U' written by process 'vit_block_top_vit_block_top.grp_dataflow_wrapper_fu_6443.task_compute_attn_U0.grp_do_attn_1_fu_5150.do_matmul_2_U0.do_adapt_2_U0'");
                                $fdisplay(fp, "Dependence_Channel_path vit_block_top_vit_block_top.grp_dataflow_wrapper_fu_6443.task_compute_attn_U0.grp_do_attn_1_fu_5150.do_matmul_2_U0.adpt_sm_i_U");
                                $fdisplay(fp, "Dependence_Channel_status EMPTY");
                            end
                            else if (~grp_dataflow_wrapper_fu_6443.task_compute_attn_U0.grp_do_attn_1_fu_5150.do_matmul_2_U0.adpt_sm_i_U.if_full_n) begin
                                $display("//      Blocked by full output FIFO 'vit_block_top_vit_block_top.grp_dataflow_wrapper_fu_6443.task_compute_attn_U0.grp_do_attn_1_fu_5150.do_matmul_2_U0.adpt_sm_i_U' read by process 'vit_block_top_vit_block_top.grp_dataflow_wrapper_fu_6443.task_compute_attn_U0.grp_do_attn_1_fu_5150.do_matmul_2_U0.do_adapt_2_U0'");
                                $fdisplay(fp, "Dependence_Channel_path vit_block_top_vit_block_top.grp_dataflow_wrapper_fu_6443.task_compute_attn_U0.grp_do_attn_1_fu_5150.do_matmul_2_U0.adpt_sm_i_U");
                                $fdisplay(fp, "Dependence_Channel_status FULL");
                            end
                        end
// for dep channel 'vit_block_top_vit_block_top.grp_dataflow_wrapper_fu_6443.task_compute_attn_U0.grp_do_attn_1_fu_5150.do_matmul_2_U0.start_for_matmul_step1_cache_window_2_U0_U' info is :
// blk sig is {{~vit_block_top_vit_block_top_inst.grp_dataflow_wrapper_fu_6443.task_compute_attn_U0.grp_do_attn_1_fu_5150.do_matmul_2_U0.start_for_matmul_step1_cache_window_2_U0_U.if_empty_n & vit_block_top_vit_block_top_inst.grp_dataflow_wrapper_fu_6443.task_compute_attn_U0.grp_do_attn_1_fu_5150.do_matmul_2_U0.matmul_step1_cache_window_2_U0.ap_idle & ~vit_block_top_vit_block_top_inst.grp_dataflow_wrapper_fu_6443.task_compute_attn_U0.grp_do_attn_1_fu_5150.do_matmul_2_U0.start_for_matmul_step1_cache_window_2_U0_U.if_write} start_FIFO}
                        if ((~grp_dataflow_wrapper_fu_6443.task_compute_attn_U0.grp_do_attn_1_fu_5150.do_matmul_2_U0.start_for_matmul_step1_cache_window_2_U0_U.if_empty_n & grp_dataflow_wrapper_fu_6443.task_compute_attn_U0.grp_do_attn_1_fu_5150.do_matmul_2_U0.matmul_step1_cache_window_2_U0.ap_idle & ~grp_dataflow_wrapper_fu_6443.task_compute_attn_U0.grp_do_attn_1_fu_5150.do_matmul_2_U0.start_for_matmul_step1_cache_window_2_U0_U.if_write)) begin
                            $display("//      Blocked by missing 'ap_start' from start propagation FIFO 'vit_block_top_vit_block_top.grp_dataflow_wrapper_fu_6443.task_compute_attn_U0.grp_do_attn_1_fu_5150.do_matmul_2_U0.start_for_matmul_step1_cache_window_2_U0_U' written by process 'vit_block_top_vit_block_top.grp_dataflow_wrapper_fu_6443.task_compute_attn_U0.grp_do_attn_1_fu_5150.do_matmul_2_U0.do_adapt_2_U0',");
                        end
                    end
                    18: begin //  for dep proc 'vit_block_top_vit_block_top.grp_dataflow_wrapper_fu_6443.task_compute_attn_U0.grp_do_attn_1_fu_5150.do_matmul_2_U0.matmul_step2_mac_2_U0'
// for dep channel 'vit_block_top_vit_block_top.grp_dataflow_wrapper_fu_6443.task_compute_attn_U0.grp_do_attn_1_fu_5150.do_matmul_2_U0.cache_window_sm_i_U' info is :
// blk sig is {~vit_block_top_vit_block_top_inst.grp_dataflow_wrapper_fu_6443.task_compute_attn_U0.grp_do_attn_1_fu_5150.do_matmul_2_U0.matmul_step1_cache_window_2_U0.cache_window_sm_blk_n data_FIFO}
                        if ((~grp_dataflow_wrapper_fu_6443.task_compute_attn_U0.grp_do_attn_1_fu_5150.do_matmul_2_U0.matmul_step1_cache_window_2_U0.cache_window_sm_blk_n)) begin
                            if (~grp_dataflow_wrapper_fu_6443.task_compute_attn_U0.grp_do_attn_1_fu_5150.do_matmul_2_U0.cache_window_sm_i_U.if_empty_n) begin
                                $display("//      Blocked by empty input FIFO 'vit_block_top_vit_block_top.grp_dataflow_wrapper_fu_6443.task_compute_attn_U0.grp_do_attn_1_fu_5150.do_matmul_2_U0.cache_window_sm_i_U' written by process 'vit_block_top_vit_block_top.grp_dataflow_wrapper_fu_6443.task_compute_attn_U0.grp_do_attn_1_fu_5150.do_matmul_2_U0.matmul_step2_mac_2_U0'");
                                $fdisplay(fp, "Dependence_Channel_path vit_block_top_vit_block_top.grp_dataflow_wrapper_fu_6443.task_compute_attn_U0.grp_do_attn_1_fu_5150.do_matmul_2_U0.cache_window_sm_i_U");
                                $fdisplay(fp, "Dependence_Channel_status EMPTY");
                            end
                            else if (~grp_dataflow_wrapper_fu_6443.task_compute_attn_U0.grp_do_attn_1_fu_5150.do_matmul_2_U0.cache_window_sm_i_U.if_full_n) begin
                                $display("//      Blocked by full output FIFO 'vit_block_top_vit_block_top.grp_dataflow_wrapper_fu_6443.task_compute_attn_U0.grp_do_attn_1_fu_5150.do_matmul_2_U0.cache_window_sm_i_U' read by process 'vit_block_top_vit_block_top.grp_dataflow_wrapper_fu_6443.task_compute_attn_U0.grp_do_attn_1_fu_5150.do_matmul_2_U0.matmul_step2_mac_2_U0'");
                                $fdisplay(fp, "Dependence_Channel_path vit_block_top_vit_block_top.grp_dataflow_wrapper_fu_6443.task_compute_attn_U0.grp_do_attn_1_fu_5150.do_matmul_2_U0.cache_window_sm_i_U");
                                $fdisplay(fp, "Dependence_Channel_status FULL");
                            end
                        end
// for dep channel 'vit_block_top_vit_block_top.grp_dataflow_wrapper_fu_6443.task_compute_attn_U0.grp_do_attn_1_fu_5150.do_matmul_2_U0.start_for_matmul_step2_mac_2_U0_U' info is :
// blk sig is {{~vit_block_top_vit_block_top_inst.grp_dataflow_wrapper_fu_6443.task_compute_attn_U0.grp_do_attn_1_fu_5150.do_matmul_2_U0.start_for_matmul_step2_mac_2_U0_U.if_full_n & vit_block_top_vit_block_top_inst.grp_dataflow_wrapper_fu_6443.task_compute_attn_U0.grp_do_attn_1_fu_5150.do_matmul_2_U0.matmul_step1_cache_window_2_U0.ap_start & ~vit_block_top_vit_block_top_inst.grp_dataflow_wrapper_fu_6443.task_compute_attn_U0.grp_do_attn_1_fu_5150.do_matmul_2_U0.matmul_step1_cache_window_2_U0.real_start & (trans_in_cnt_8 == trans_out_cnt_8) & ~vit_block_top_vit_block_top_inst.grp_dataflow_wrapper_fu_6443.task_compute_attn_U0.grp_do_attn_1_fu_5150.do_matmul_2_U0.start_for_matmul_step2_mac_2_U0_U.if_read} start_FIFO}
                        if ((~grp_dataflow_wrapper_fu_6443.task_compute_attn_U0.grp_do_attn_1_fu_5150.do_matmul_2_U0.start_for_matmul_step2_mac_2_U0_U.if_full_n & grp_dataflow_wrapper_fu_6443.task_compute_attn_U0.grp_do_attn_1_fu_5150.do_matmul_2_U0.matmul_step1_cache_window_2_U0.ap_start & ~grp_dataflow_wrapper_fu_6443.task_compute_attn_U0.grp_do_attn_1_fu_5150.do_matmul_2_U0.matmul_step1_cache_window_2_U0.real_start & (trans_in_cnt_8 == trans_out_cnt_8) & ~grp_dataflow_wrapper_fu_6443.task_compute_attn_U0.grp_do_attn_1_fu_5150.do_matmul_2_U0.start_for_matmul_step2_mac_2_U0_U.if_read)) begin
                            $display("//      Blocked by full output start propagation FIFO 'vit_block_top_vit_block_top.grp_dataflow_wrapper_fu_6443.task_compute_attn_U0.grp_do_attn_1_fu_5150.do_matmul_2_U0.start_for_matmul_step2_mac_2_U0_U' read by process 'vit_block_top_vit_block_top.grp_dataflow_wrapper_fu_6443.task_compute_attn_U0.grp_do_attn_1_fu_5150.do_matmul_2_U0.matmul_step2_mac_2_U0',");
                        end
                    end
                    endcase
                end
                18 : begin // for proc 'vit_block_top_vit_block_top.grp_dataflow_wrapper_fu_6443.task_compute_attn_U0.grp_do_attn_1_fu_5150.do_matmul_2_U0.matmul_step2_mac_2_U0'
                    case(index2)
                    17: begin //  for dep proc 'vit_block_top_vit_block_top.grp_dataflow_wrapper_fu_6443.task_compute_attn_U0.grp_do_attn_1_fu_5150.do_matmul_2_U0.matmul_step1_cache_window_2_U0'
// for dep channel 'vit_block_top_vit_block_top.grp_dataflow_wrapper_fu_6443.task_compute_attn_U0.grp_do_attn_1_fu_5150.do_matmul_2_U0.cache_window_sm_i_U' info is :
// blk sig is {~vit_block_top_vit_block_top_inst.grp_dataflow_wrapper_fu_6443.task_compute_attn_U0.grp_do_attn_1_fu_5150.do_matmul_2_U0.matmul_step2_mac_2_U0.cache_window_sm_blk_n data_FIFO}
                        if ((~grp_dataflow_wrapper_fu_6443.task_compute_attn_U0.grp_do_attn_1_fu_5150.do_matmul_2_U0.matmul_step2_mac_2_U0.cache_window_sm_blk_n)) begin
                            if (~grp_dataflow_wrapper_fu_6443.task_compute_attn_U0.grp_do_attn_1_fu_5150.do_matmul_2_U0.cache_window_sm_i_U.if_empty_n) begin
                                $display("//      Blocked by empty input FIFO 'vit_block_top_vit_block_top.grp_dataflow_wrapper_fu_6443.task_compute_attn_U0.grp_do_attn_1_fu_5150.do_matmul_2_U0.cache_window_sm_i_U' written by process 'vit_block_top_vit_block_top.grp_dataflow_wrapper_fu_6443.task_compute_attn_U0.grp_do_attn_1_fu_5150.do_matmul_2_U0.matmul_step1_cache_window_2_U0'");
                                $fdisplay(fp, "Dependence_Channel_path vit_block_top_vit_block_top.grp_dataflow_wrapper_fu_6443.task_compute_attn_U0.grp_do_attn_1_fu_5150.do_matmul_2_U0.cache_window_sm_i_U");
                                $fdisplay(fp, "Dependence_Channel_status EMPTY");
                            end
                            else if (~grp_dataflow_wrapper_fu_6443.task_compute_attn_U0.grp_do_attn_1_fu_5150.do_matmul_2_U0.cache_window_sm_i_U.if_full_n) begin
                                $display("//      Blocked by full output FIFO 'vit_block_top_vit_block_top.grp_dataflow_wrapper_fu_6443.task_compute_attn_U0.grp_do_attn_1_fu_5150.do_matmul_2_U0.cache_window_sm_i_U' read by process 'vit_block_top_vit_block_top.grp_dataflow_wrapper_fu_6443.task_compute_attn_U0.grp_do_attn_1_fu_5150.do_matmul_2_U0.matmul_step1_cache_window_2_U0'");
                                $fdisplay(fp, "Dependence_Channel_path vit_block_top_vit_block_top.grp_dataflow_wrapper_fu_6443.task_compute_attn_U0.grp_do_attn_1_fu_5150.do_matmul_2_U0.cache_window_sm_i_U");
                                $fdisplay(fp, "Dependence_Channel_status FULL");
                            end
                        end
// for dep channel 'vit_block_top_vit_block_top.grp_dataflow_wrapper_fu_6443.task_compute_attn_U0.grp_do_attn_1_fu_5150.do_matmul_2_U0.start_for_matmul_step2_mac_2_U0_U' info is :
// blk sig is {{~vit_block_top_vit_block_top_inst.grp_dataflow_wrapper_fu_6443.task_compute_attn_U0.grp_do_attn_1_fu_5150.do_matmul_2_U0.start_for_matmul_step2_mac_2_U0_U.if_empty_n & vit_block_top_vit_block_top_inst.grp_dataflow_wrapper_fu_6443.task_compute_attn_U0.grp_do_attn_1_fu_5150.do_matmul_2_U0.matmul_step2_mac_2_U0.ap_idle & ~vit_block_top_vit_block_top_inst.grp_dataflow_wrapper_fu_6443.task_compute_attn_U0.grp_do_attn_1_fu_5150.do_matmul_2_U0.start_for_matmul_step2_mac_2_U0_U.if_write} start_FIFO}
                        if ((~grp_dataflow_wrapper_fu_6443.task_compute_attn_U0.grp_do_attn_1_fu_5150.do_matmul_2_U0.start_for_matmul_step2_mac_2_U0_U.if_empty_n & grp_dataflow_wrapper_fu_6443.task_compute_attn_U0.grp_do_attn_1_fu_5150.do_matmul_2_U0.matmul_step2_mac_2_U0.ap_idle & ~grp_dataflow_wrapper_fu_6443.task_compute_attn_U0.grp_do_attn_1_fu_5150.do_matmul_2_U0.start_for_matmul_step2_mac_2_U0_U.if_write)) begin
                            $display("//      Blocked by missing 'ap_start' from start propagation FIFO 'vit_block_top_vit_block_top.grp_dataflow_wrapper_fu_6443.task_compute_attn_U0.grp_do_attn_1_fu_5150.do_matmul_2_U0.start_for_matmul_step2_mac_2_U0_U' written by process 'vit_block_top_vit_block_top.grp_dataflow_wrapper_fu_6443.task_compute_attn_U0.grp_do_attn_1_fu_5150.do_matmul_2_U0.matmul_step1_cache_window_2_U0',");
                        end
                    end
                    19: begin //  for dep proc 'vit_block_top_vit_block_top.grp_dataflow_wrapper_fu_6443.task_compute_attn_U0.grp_do_attn_1_fu_5150.do_matmul_2_U0.do_adapt_11_U0'
// for dep channel 'vit_block_top_vit_block_top.grp_dataflow_wrapper_fu_6443.task_compute_attn_U0.grp_do_attn_1_fu_5150.do_matmul_2_U0.mac_sm_i_U' info is :
// blk sig is {~vit_block_top_vit_block_top_inst.grp_dataflow_wrapper_fu_6443.task_compute_attn_U0.grp_do_attn_1_fu_5150.do_matmul_2_U0.matmul_step2_mac_2_U0.mac_sm_blk_n data_FIFO}
                        if ((~grp_dataflow_wrapper_fu_6443.task_compute_attn_U0.grp_do_attn_1_fu_5150.do_matmul_2_U0.matmul_step2_mac_2_U0.mac_sm_blk_n)) begin
                            if (~grp_dataflow_wrapper_fu_6443.task_compute_attn_U0.grp_do_attn_1_fu_5150.do_matmul_2_U0.mac_sm_i_U.if_empty_n) begin
                                $display("//      Blocked by empty input FIFO 'vit_block_top_vit_block_top.grp_dataflow_wrapper_fu_6443.task_compute_attn_U0.grp_do_attn_1_fu_5150.do_matmul_2_U0.mac_sm_i_U' written by process 'vit_block_top_vit_block_top.grp_dataflow_wrapper_fu_6443.task_compute_attn_U0.grp_do_attn_1_fu_5150.do_matmul_2_U0.do_adapt_11_U0'");
                                $fdisplay(fp, "Dependence_Channel_path vit_block_top_vit_block_top.grp_dataflow_wrapper_fu_6443.task_compute_attn_U0.grp_do_attn_1_fu_5150.do_matmul_2_U0.mac_sm_i_U");
                                $fdisplay(fp, "Dependence_Channel_status EMPTY");
                            end
                            else if (~grp_dataflow_wrapper_fu_6443.task_compute_attn_U0.grp_do_attn_1_fu_5150.do_matmul_2_U0.mac_sm_i_U.if_full_n) begin
                                $display("//      Blocked by full output FIFO 'vit_block_top_vit_block_top.grp_dataflow_wrapper_fu_6443.task_compute_attn_U0.grp_do_attn_1_fu_5150.do_matmul_2_U0.mac_sm_i_U' read by process 'vit_block_top_vit_block_top.grp_dataflow_wrapper_fu_6443.task_compute_attn_U0.grp_do_attn_1_fu_5150.do_matmul_2_U0.do_adapt_11_U0'");
                                $fdisplay(fp, "Dependence_Channel_path vit_block_top_vit_block_top.grp_dataflow_wrapper_fu_6443.task_compute_attn_U0.grp_do_attn_1_fu_5150.do_matmul_2_U0.mac_sm_i_U");
                                $fdisplay(fp, "Dependence_Channel_status FULL");
                            end
                        end
// for dep channel 'vit_block_top_vit_block_top.grp_dataflow_wrapper_fu_6443.task_compute_attn_U0.grp_do_attn_1_fu_5150.do_matmul_2_U0.start_for_do_adapt_11_U0_U' info is :
// blk sig is {{~vit_block_top_vit_block_top_inst.grp_dataflow_wrapper_fu_6443.task_compute_attn_U0.grp_do_attn_1_fu_5150.do_matmul_2_U0.start_for_do_adapt_11_U0_U.if_full_n & vit_block_top_vit_block_top_inst.grp_dataflow_wrapper_fu_6443.task_compute_attn_U0.grp_do_attn_1_fu_5150.do_matmul_2_U0.matmul_step2_mac_2_U0.ap_start & ~vit_block_top_vit_block_top_inst.grp_dataflow_wrapper_fu_6443.task_compute_attn_U0.grp_do_attn_1_fu_5150.do_matmul_2_U0.matmul_step2_mac_2_U0.real_start & (trans_in_cnt_9 == trans_out_cnt_9) & ~vit_block_top_vit_block_top_inst.grp_dataflow_wrapper_fu_6443.task_compute_attn_U0.grp_do_attn_1_fu_5150.do_matmul_2_U0.start_for_do_adapt_11_U0_U.if_read} start_FIFO}
                        if ((~grp_dataflow_wrapper_fu_6443.task_compute_attn_U0.grp_do_attn_1_fu_5150.do_matmul_2_U0.start_for_do_adapt_11_U0_U.if_full_n & grp_dataflow_wrapper_fu_6443.task_compute_attn_U0.grp_do_attn_1_fu_5150.do_matmul_2_U0.matmul_step2_mac_2_U0.ap_start & ~grp_dataflow_wrapper_fu_6443.task_compute_attn_U0.grp_do_attn_1_fu_5150.do_matmul_2_U0.matmul_step2_mac_2_U0.real_start & (trans_in_cnt_9 == trans_out_cnt_9) & ~grp_dataflow_wrapper_fu_6443.task_compute_attn_U0.grp_do_attn_1_fu_5150.do_matmul_2_U0.start_for_do_adapt_11_U0_U.if_read)) begin
                            $display("//      Blocked by full output start propagation FIFO 'vit_block_top_vit_block_top.grp_dataflow_wrapper_fu_6443.task_compute_attn_U0.grp_do_attn_1_fu_5150.do_matmul_2_U0.start_for_do_adapt_11_U0_U' read by process 'vit_block_top_vit_block_top.grp_dataflow_wrapper_fu_6443.task_compute_attn_U0.grp_do_attn_1_fu_5150.do_matmul_2_U0.do_adapt_11_U0',");
                        end
                    end
                    endcase
                end
                19 : begin // for proc 'vit_block_top_vit_block_top.grp_dataflow_wrapper_fu_6443.task_compute_attn_U0.grp_do_attn_1_fu_5150.do_matmul_2_U0.do_adapt_11_U0'
                    case(index2)
                    18: begin //  for dep proc 'vit_block_top_vit_block_top.grp_dataflow_wrapper_fu_6443.task_compute_attn_U0.grp_do_attn_1_fu_5150.do_matmul_2_U0.matmul_step2_mac_2_U0'
// for dep channel 'vit_block_top_vit_block_top.grp_dataflow_wrapper_fu_6443.task_compute_attn_U0.grp_do_attn_1_fu_5150.do_matmul_2_U0.mac_sm_i_U' info is :
// blk sig is {~vit_block_top_vit_block_top_inst.grp_dataflow_wrapper_fu_6443.task_compute_attn_U0.grp_do_attn_1_fu_5150.do_matmul_2_U0.do_adapt_11_U0.mac_sm_blk_n data_FIFO}
                        if ((~grp_dataflow_wrapper_fu_6443.task_compute_attn_U0.grp_do_attn_1_fu_5150.do_matmul_2_U0.do_adapt_11_U0.mac_sm_blk_n)) begin
                            if (~grp_dataflow_wrapper_fu_6443.task_compute_attn_U0.grp_do_attn_1_fu_5150.do_matmul_2_U0.mac_sm_i_U.if_empty_n) begin
                                $display("//      Blocked by empty input FIFO 'vit_block_top_vit_block_top.grp_dataflow_wrapper_fu_6443.task_compute_attn_U0.grp_do_attn_1_fu_5150.do_matmul_2_U0.mac_sm_i_U' written by process 'vit_block_top_vit_block_top.grp_dataflow_wrapper_fu_6443.task_compute_attn_U0.grp_do_attn_1_fu_5150.do_matmul_2_U0.matmul_step2_mac_2_U0'");
                                $fdisplay(fp, "Dependence_Channel_path vit_block_top_vit_block_top.grp_dataflow_wrapper_fu_6443.task_compute_attn_U0.grp_do_attn_1_fu_5150.do_matmul_2_U0.mac_sm_i_U");
                                $fdisplay(fp, "Dependence_Channel_status EMPTY");
                            end
                            else if (~grp_dataflow_wrapper_fu_6443.task_compute_attn_U0.grp_do_attn_1_fu_5150.do_matmul_2_U0.mac_sm_i_U.if_full_n) begin
                                $display("//      Blocked by full output FIFO 'vit_block_top_vit_block_top.grp_dataflow_wrapper_fu_6443.task_compute_attn_U0.grp_do_attn_1_fu_5150.do_matmul_2_U0.mac_sm_i_U' read by process 'vit_block_top_vit_block_top.grp_dataflow_wrapper_fu_6443.task_compute_attn_U0.grp_do_attn_1_fu_5150.do_matmul_2_U0.matmul_step2_mac_2_U0'");
                                $fdisplay(fp, "Dependence_Channel_path vit_block_top_vit_block_top.grp_dataflow_wrapper_fu_6443.task_compute_attn_U0.grp_do_attn_1_fu_5150.do_matmul_2_U0.mac_sm_i_U");
                                $fdisplay(fp, "Dependence_Channel_status FULL");
                            end
                        end
// for dep channel 'vit_block_top_vit_block_top.grp_dataflow_wrapper_fu_6443.task_compute_attn_U0.grp_do_attn_1_fu_5150.do_matmul_2_U0.start_for_do_adapt_11_U0_U' info is :
// blk sig is {{~vit_block_top_vit_block_top_inst.grp_dataflow_wrapper_fu_6443.task_compute_attn_U0.grp_do_attn_1_fu_5150.do_matmul_2_U0.start_for_do_adapt_11_U0_U.if_empty_n & vit_block_top_vit_block_top_inst.grp_dataflow_wrapper_fu_6443.task_compute_attn_U0.grp_do_attn_1_fu_5150.do_matmul_2_U0.do_adapt_11_U0.ap_idle & ~vit_block_top_vit_block_top_inst.grp_dataflow_wrapper_fu_6443.task_compute_attn_U0.grp_do_attn_1_fu_5150.do_matmul_2_U0.start_for_do_adapt_11_U0_U.if_write} start_FIFO}
                        if ((~grp_dataflow_wrapper_fu_6443.task_compute_attn_U0.grp_do_attn_1_fu_5150.do_matmul_2_U0.start_for_do_adapt_11_U0_U.if_empty_n & grp_dataflow_wrapper_fu_6443.task_compute_attn_U0.grp_do_attn_1_fu_5150.do_matmul_2_U0.do_adapt_11_U0.ap_idle & ~grp_dataflow_wrapper_fu_6443.task_compute_attn_U0.grp_do_attn_1_fu_5150.do_matmul_2_U0.start_for_do_adapt_11_U0_U.if_write)) begin
                            $display("//      Blocked by missing 'ap_start' from start propagation FIFO 'vit_block_top_vit_block_top.grp_dataflow_wrapper_fu_6443.task_compute_attn_U0.grp_do_attn_1_fu_5150.do_matmul_2_U0.start_for_do_adapt_11_U0_U' written by process 'vit_block_top_vit_block_top.grp_dataflow_wrapper_fu_6443.task_compute_attn_U0.grp_do_attn_1_fu_5150.do_matmul_2_U0.matmul_step2_mac_2_U0',");
                        end
                    end
                    30: begin //  for dep proc 'vit_block_top_vit_block_top.grp_dataflow_wrapper_fu_6443.task_compute_attn_U0.grp_do_attn_1_fu_5150.do_quant_U0'
// for dep channel 'vit_block_top_vit_block_top.grp_dataflow_wrapper_fu_6443.task_compute_attn_U0.grp_do_attn_1_fu_5150.q_sm_i_U' info is :
// blk sig is {~vit_block_top_vit_block_top_inst.grp_dataflow_wrapper_fu_6443.task_compute_attn_U0.grp_do_attn_1_fu_5150.do_matmul_2_U0.do_adapt_11_U0.q_sm_blk_n data_FIFO}
                        if ((~grp_dataflow_wrapper_fu_6443.task_compute_attn_U0.grp_do_attn_1_fu_5150.do_matmul_2_U0.do_adapt_11_U0.q_sm_blk_n)) begin
                            if (~grp_dataflow_wrapper_fu_6443.task_compute_attn_U0.grp_do_attn_1_fu_5150.q_sm_i_U.if_empty_n) begin
                                $display("//      Blocked by empty input FIFO 'vit_block_top_vit_block_top.grp_dataflow_wrapper_fu_6443.task_compute_attn_U0.grp_do_attn_1_fu_5150.q_sm_i_U' written by process 'vit_block_top_vit_block_top.grp_dataflow_wrapper_fu_6443.task_compute_attn_U0.grp_do_attn_1_fu_5150.do_quant_U0'");
                                $fdisplay(fp, "Dependence_Channel_path vit_block_top_vit_block_top.grp_dataflow_wrapper_fu_6443.task_compute_attn_U0.grp_do_attn_1_fu_5150.q_sm_i_U");
                                $fdisplay(fp, "Dependence_Channel_status EMPTY");
                            end
                            else if (~grp_dataflow_wrapper_fu_6443.task_compute_attn_U0.grp_do_attn_1_fu_5150.q_sm_i_U.if_full_n) begin
                                $display("//      Blocked by full output FIFO 'vit_block_top_vit_block_top.grp_dataflow_wrapper_fu_6443.task_compute_attn_U0.grp_do_attn_1_fu_5150.q_sm_i_U' read by process 'vit_block_top_vit_block_top.grp_dataflow_wrapper_fu_6443.task_compute_attn_U0.grp_do_attn_1_fu_5150.do_quant_U0'");
                                $fdisplay(fp, "Dependence_Channel_path vit_block_top_vit_block_top.grp_dataflow_wrapper_fu_6443.task_compute_attn_U0.grp_do_attn_1_fu_5150.q_sm_i_U");
                                $fdisplay(fp, "Dependence_Channel_status FULL");
                            end
                        end
                    end
                    endcase
                end
                20 : begin // for proc 'vit_block_top_vit_block_top.grp_dataflow_wrapper_fu_6443.task_compute_attn_U0.grp_do_attn_1_fu_5150.do_matmul_2_1_U0'
                    case(index2)
                    14: begin //  for dep proc 'vit_block_top_vit_block_top.grp_dataflow_wrapper_fu_6443.task_compute_attn_U0.grp_do_attn_1_fu_5150.stream_copy3_U0'
// for dep channel 'vit_block_top_vit_block_top.grp_dataflow_wrapper_fu_6443.task_compute_attn_U0.grp_do_attn_1_fu_5150.lnq_sm_cp2_i_U' info is :
// blk sig is {~vit_block_top_vit_block_top_inst.grp_dataflow_wrapper_fu_6443.task_compute_attn_U0.grp_do_attn_1_fu_5150.do_matmul_2_1_U0.do_adapt_9_U0.lnq_sm_cp2_blk_n data_FIFO}
                        if ((~grp_dataflow_wrapper_fu_6443.task_compute_attn_U0.grp_do_attn_1_fu_5150.do_matmul_2_1_U0.do_adapt_9_U0.lnq_sm_cp2_blk_n)) begin
                            if (~grp_dataflow_wrapper_fu_6443.task_compute_attn_U0.grp_do_attn_1_fu_5150.lnq_sm_cp2_i_U.if_empty_n) begin
                                $display("//      Blocked by empty input FIFO 'vit_block_top_vit_block_top.grp_dataflow_wrapper_fu_6443.task_compute_attn_U0.grp_do_attn_1_fu_5150.lnq_sm_cp2_i_U' written by process 'vit_block_top_vit_block_top.grp_dataflow_wrapper_fu_6443.task_compute_attn_U0.grp_do_attn_1_fu_5150.stream_copy3_U0'");
                                $fdisplay(fp, "Dependence_Channel_path vit_block_top_vit_block_top.grp_dataflow_wrapper_fu_6443.task_compute_attn_U0.grp_do_attn_1_fu_5150.lnq_sm_cp2_i_U");
                                $fdisplay(fp, "Dependence_Channel_status EMPTY");
                            end
                            else if (~grp_dataflow_wrapper_fu_6443.task_compute_attn_U0.grp_do_attn_1_fu_5150.lnq_sm_cp2_i_U.if_full_n) begin
                                $display("//      Blocked by full output FIFO 'vit_block_top_vit_block_top.grp_dataflow_wrapper_fu_6443.task_compute_attn_U0.grp_do_attn_1_fu_5150.lnq_sm_cp2_i_U' read by process 'vit_block_top_vit_block_top.grp_dataflow_wrapper_fu_6443.task_compute_attn_U0.grp_do_attn_1_fu_5150.stream_copy3_U0'");
                                $fdisplay(fp, "Dependence_Channel_path vit_block_top_vit_block_top.grp_dataflow_wrapper_fu_6443.task_compute_attn_U0.grp_do_attn_1_fu_5150.lnq_sm_cp2_i_U");
                                $fdisplay(fp, "Dependence_Channel_status FULL");
                            end
                        end
// for dep channel 'vit_block_top_vit_block_top.grp_dataflow_wrapper_fu_6443.task_compute_attn_U0.grp_do_attn_1_fu_5150.start_for_do_matmul_2_1_U0_U' info is :
// blk sig is {{~vit_block_top_vit_block_top_inst.grp_dataflow_wrapper_fu_6443.task_compute_attn_U0.grp_do_attn_1_fu_5150.start_for_do_matmul_2_1_U0_U.if_empty_n & vit_block_top_vit_block_top_inst.grp_dataflow_wrapper_fu_6443.task_compute_attn_U0.grp_do_attn_1_fu_5150.do_matmul_2_1_U0.ap_idle & ~vit_block_top_vit_block_top_inst.grp_dataflow_wrapper_fu_6443.task_compute_attn_U0.grp_do_attn_1_fu_5150.start_for_do_matmul_2_1_U0_U.if_write} start_FIFO}
                        if ((~grp_dataflow_wrapper_fu_6443.task_compute_attn_U0.grp_do_attn_1_fu_5150.start_for_do_matmul_2_1_U0_U.if_empty_n & grp_dataflow_wrapper_fu_6443.task_compute_attn_U0.grp_do_attn_1_fu_5150.do_matmul_2_1_U0.ap_idle & ~grp_dataflow_wrapper_fu_6443.task_compute_attn_U0.grp_do_attn_1_fu_5150.start_for_do_matmul_2_1_U0_U.if_write)) begin
                            $display("//      Blocked by missing 'ap_start' from start propagation FIFO 'vit_block_top_vit_block_top.grp_dataflow_wrapper_fu_6443.task_compute_attn_U0.grp_do_attn_1_fu_5150.start_for_do_matmul_2_1_U0_U' written by process 'vit_block_top_vit_block_top.grp_dataflow_wrapper_fu_6443.task_compute_attn_U0.grp_do_attn_1_fu_5150.stream_copy3_U0',");
                        end
                    end
                    31: begin //  for dep proc 'vit_block_top_vit_block_top.grp_dataflow_wrapper_fu_6443.task_compute_attn_U0.grp_do_attn_1_fu_5150.do_quant_3_U0'
// for dep channel 'vit_block_top_vit_block_top.grp_dataflow_wrapper_fu_6443.task_compute_attn_U0.grp_do_attn_1_fu_5150.k_sm_i_U' info is :
// blk sig is {~vit_block_top_vit_block_top_inst.grp_dataflow_wrapper_fu_6443.task_compute_attn_U0.grp_do_attn_1_fu_5150.do_matmul_2_1_U0.do_adapt_12_1_U0.k_sm_blk_n data_FIFO}
                        if ((~grp_dataflow_wrapper_fu_6443.task_compute_attn_U0.grp_do_attn_1_fu_5150.do_matmul_2_1_U0.do_adapt_12_1_U0.k_sm_blk_n)) begin
                            if (~grp_dataflow_wrapper_fu_6443.task_compute_attn_U0.grp_do_attn_1_fu_5150.k_sm_i_U.if_empty_n) begin
                                $display("//      Blocked by empty input FIFO 'vit_block_top_vit_block_top.grp_dataflow_wrapper_fu_6443.task_compute_attn_U0.grp_do_attn_1_fu_5150.k_sm_i_U' written by process 'vit_block_top_vit_block_top.grp_dataflow_wrapper_fu_6443.task_compute_attn_U0.grp_do_attn_1_fu_5150.do_quant_3_U0'");
                                $fdisplay(fp, "Dependence_Channel_path vit_block_top_vit_block_top.grp_dataflow_wrapper_fu_6443.task_compute_attn_U0.grp_do_attn_1_fu_5150.k_sm_i_U");
                                $fdisplay(fp, "Dependence_Channel_status EMPTY");
                            end
                            else if (~grp_dataflow_wrapper_fu_6443.task_compute_attn_U0.grp_do_attn_1_fu_5150.k_sm_i_U.if_full_n) begin
                                $display("//      Blocked by full output FIFO 'vit_block_top_vit_block_top.grp_dataflow_wrapper_fu_6443.task_compute_attn_U0.grp_do_attn_1_fu_5150.k_sm_i_U' read by process 'vit_block_top_vit_block_top.grp_dataflow_wrapper_fu_6443.task_compute_attn_U0.grp_do_attn_1_fu_5150.do_quant_3_U0'");
                                $fdisplay(fp, "Dependence_Channel_path vit_block_top_vit_block_top.grp_dataflow_wrapper_fu_6443.task_compute_attn_U0.grp_do_attn_1_fu_5150.k_sm_i_U");
                                $fdisplay(fp, "Dependence_Channel_status FULL");
                            end
                        end
// for dep channel 'vit_block_top_vit_block_top.grp_dataflow_wrapper_fu_6443.task_compute_attn_U0.grp_do_attn_1_fu_5150.start_for_do_quant_3_U0_U' info is :
// blk sig is {{~vit_block_top_vit_block_top_inst.grp_dataflow_wrapper_fu_6443.task_compute_attn_U0.grp_do_attn_1_fu_5150.start_for_do_quant_3_U0_U.if_full_n & vit_block_top_vit_block_top_inst.grp_dataflow_wrapper_fu_6443.task_compute_attn_U0.grp_do_attn_1_fu_5150.do_matmul_2_1_U0.ap_start & ~vit_block_top_vit_block_top_inst.grp_dataflow_wrapper_fu_6443.task_compute_attn_U0.grp_do_attn_1_fu_5150.do_matmul_2_1_U0.real_start & (trans_in_cnt_17 == trans_out_cnt_17) & ~vit_block_top_vit_block_top_inst.grp_dataflow_wrapper_fu_6443.task_compute_attn_U0.grp_do_attn_1_fu_5150.start_for_do_quant_3_U0_U.if_read} start_FIFO}
                        if ((~grp_dataflow_wrapper_fu_6443.task_compute_attn_U0.grp_do_attn_1_fu_5150.start_for_do_quant_3_U0_U.if_full_n & grp_dataflow_wrapper_fu_6443.task_compute_attn_U0.grp_do_attn_1_fu_5150.do_matmul_2_1_U0.ap_start & ~grp_dataflow_wrapper_fu_6443.task_compute_attn_U0.grp_do_attn_1_fu_5150.do_matmul_2_1_U0.real_start & (trans_in_cnt_17 == trans_out_cnt_17) & ~grp_dataflow_wrapper_fu_6443.task_compute_attn_U0.grp_do_attn_1_fu_5150.start_for_do_quant_3_U0_U.if_read)) begin
                            $display("//      Blocked by full output start propagation FIFO 'vit_block_top_vit_block_top.grp_dataflow_wrapper_fu_6443.task_compute_attn_U0.grp_do_attn_1_fu_5150.start_for_do_quant_3_U0_U' read by process 'vit_block_top_vit_block_top.grp_dataflow_wrapper_fu_6443.task_compute_attn_U0.grp_do_attn_1_fu_5150.do_quant_3_U0',");
                        end
                    end
                    endcase
                end
                21 : begin // for proc 'vit_block_top_vit_block_top.grp_dataflow_wrapper_fu_6443.task_compute_attn_U0.grp_do_attn_1_fu_5150.do_matmul_2_1_U0.do_adapt_9_U0'
                    case(index2)
                    14: begin //  for dep proc 'vit_block_top_vit_block_top.grp_dataflow_wrapper_fu_6443.task_compute_attn_U0.grp_do_attn_1_fu_5150.stream_copy3_U0'
// for dep channel 'vit_block_top_vit_block_top.grp_dataflow_wrapper_fu_6443.task_compute_attn_U0.grp_do_attn_1_fu_5150.lnq_sm_cp2_i_U' info is :
// blk sig is {~vit_block_top_vit_block_top_inst.grp_dataflow_wrapper_fu_6443.task_compute_attn_U0.grp_do_attn_1_fu_5150.do_matmul_2_1_U0.do_adapt_9_U0.lnq_sm_cp2_blk_n data_FIFO}
                        if ((~grp_dataflow_wrapper_fu_6443.task_compute_attn_U0.grp_do_attn_1_fu_5150.do_matmul_2_1_U0.do_adapt_9_U0.lnq_sm_cp2_blk_n)) begin
                            if (~grp_dataflow_wrapper_fu_6443.task_compute_attn_U0.grp_do_attn_1_fu_5150.lnq_sm_cp2_i_U.if_empty_n) begin
                                $display("//      Blocked by empty input FIFO 'vit_block_top_vit_block_top.grp_dataflow_wrapper_fu_6443.task_compute_attn_U0.grp_do_attn_1_fu_5150.lnq_sm_cp2_i_U' written by process 'vit_block_top_vit_block_top.grp_dataflow_wrapper_fu_6443.task_compute_attn_U0.grp_do_attn_1_fu_5150.stream_copy3_U0'");
                                $fdisplay(fp, "Dependence_Channel_path vit_block_top_vit_block_top.grp_dataflow_wrapper_fu_6443.task_compute_attn_U0.grp_do_attn_1_fu_5150.lnq_sm_cp2_i_U");
                                $fdisplay(fp, "Dependence_Channel_status EMPTY");
                            end
                            else if (~grp_dataflow_wrapper_fu_6443.task_compute_attn_U0.grp_do_attn_1_fu_5150.lnq_sm_cp2_i_U.if_full_n) begin
                                $display("//      Blocked by full output FIFO 'vit_block_top_vit_block_top.grp_dataflow_wrapper_fu_6443.task_compute_attn_U0.grp_do_attn_1_fu_5150.lnq_sm_cp2_i_U' read by process 'vit_block_top_vit_block_top.grp_dataflow_wrapper_fu_6443.task_compute_attn_U0.grp_do_attn_1_fu_5150.stream_copy3_U0'");
                                $fdisplay(fp, "Dependence_Channel_path vit_block_top_vit_block_top.grp_dataflow_wrapper_fu_6443.task_compute_attn_U0.grp_do_attn_1_fu_5150.lnq_sm_cp2_i_U");
                                $fdisplay(fp, "Dependence_Channel_status FULL");
                            end
                        end
                    end
                    22: begin //  for dep proc 'vit_block_top_vit_block_top.grp_dataflow_wrapper_fu_6443.task_compute_attn_U0.grp_do_attn_1_fu_5150.do_matmul_2_1_U0.matmul_step1_cache_window_10_U0'
// for dep channel 'vit_block_top_vit_block_top.grp_dataflow_wrapper_fu_6443.task_compute_attn_U0.grp_do_attn_1_fu_5150.do_matmul_2_1_U0.adpt_sm_i_U' info is :
// blk sig is {~vit_block_top_vit_block_top_inst.grp_dataflow_wrapper_fu_6443.task_compute_attn_U0.grp_do_attn_1_fu_5150.do_matmul_2_1_U0.do_adapt_9_U0.adpt_sm_blk_n data_FIFO}
                        if ((~grp_dataflow_wrapper_fu_6443.task_compute_attn_U0.grp_do_attn_1_fu_5150.do_matmul_2_1_U0.do_adapt_9_U0.adpt_sm_blk_n)) begin
                            if (~grp_dataflow_wrapper_fu_6443.task_compute_attn_U0.grp_do_attn_1_fu_5150.do_matmul_2_1_U0.adpt_sm_i_U.if_empty_n) begin
                                $display("//      Blocked by empty input FIFO 'vit_block_top_vit_block_top.grp_dataflow_wrapper_fu_6443.task_compute_attn_U0.grp_do_attn_1_fu_5150.do_matmul_2_1_U0.adpt_sm_i_U' written by process 'vit_block_top_vit_block_top.grp_dataflow_wrapper_fu_6443.task_compute_attn_U0.grp_do_attn_1_fu_5150.do_matmul_2_1_U0.matmul_step1_cache_window_10_U0'");
                                $fdisplay(fp, "Dependence_Channel_path vit_block_top_vit_block_top.grp_dataflow_wrapper_fu_6443.task_compute_attn_U0.grp_do_attn_1_fu_5150.do_matmul_2_1_U0.adpt_sm_i_U");
                                $fdisplay(fp, "Dependence_Channel_status EMPTY");
                            end
                            else if (~grp_dataflow_wrapper_fu_6443.task_compute_attn_U0.grp_do_attn_1_fu_5150.do_matmul_2_1_U0.adpt_sm_i_U.if_full_n) begin
                                $display("//      Blocked by full output FIFO 'vit_block_top_vit_block_top.grp_dataflow_wrapper_fu_6443.task_compute_attn_U0.grp_do_attn_1_fu_5150.do_matmul_2_1_U0.adpt_sm_i_U' read by process 'vit_block_top_vit_block_top.grp_dataflow_wrapper_fu_6443.task_compute_attn_U0.grp_do_attn_1_fu_5150.do_matmul_2_1_U0.matmul_step1_cache_window_10_U0'");
                                $fdisplay(fp, "Dependence_Channel_path vit_block_top_vit_block_top.grp_dataflow_wrapper_fu_6443.task_compute_attn_U0.grp_do_attn_1_fu_5150.do_matmul_2_1_U0.adpt_sm_i_U");
                                $fdisplay(fp, "Dependence_Channel_status FULL");
                            end
                        end
// for dep channel 'vit_block_top_vit_block_top.grp_dataflow_wrapper_fu_6443.task_compute_attn_U0.grp_do_attn_1_fu_5150.do_matmul_2_1_U0.start_for_matmul_step1_cache_window_10_U0_U' info is :
// blk sig is {{~vit_block_top_vit_block_top_inst.grp_dataflow_wrapper_fu_6443.task_compute_attn_U0.grp_do_attn_1_fu_5150.do_matmul_2_1_U0.start_for_matmul_step1_cache_window_10_U0_U.if_full_n & vit_block_top_vit_block_top_inst.grp_dataflow_wrapper_fu_6443.task_compute_attn_U0.grp_do_attn_1_fu_5150.do_matmul_2_1_U0.do_adapt_9_U0.ap_start & ~vit_block_top_vit_block_top_inst.grp_dataflow_wrapper_fu_6443.task_compute_attn_U0.grp_do_attn_1_fu_5150.do_matmul_2_1_U0.do_adapt_9_U0.real_start & (trans_in_cnt_10 == trans_out_cnt_10) & ~vit_block_top_vit_block_top_inst.grp_dataflow_wrapper_fu_6443.task_compute_attn_U0.grp_do_attn_1_fu_5150.do_matmul_2_1_U0.start_for_matmul_step1_cache_window_10_U0_U.if_read} start_FIFO}
                        if ((~grp_dataflow_wrapper_fu_6443.task_compute_attn_U0.grp_do_attn_1_fu_5150.do_matmul_2_1_U0.start_for_matmul_step1_cache_window_10_U0_U.if_full_n & grp_dataflow_wrapper_fu_6443.task_compute_attn_U0.grp_do_attn_1_fu_5150.do_matmul_2_1_U0.do_adapt_9_U0.ap_start & ~grp_dataflow_wrapper_fu_6443.task_compute_attn_U0.grp_do_attn_1_fu_5150.do_matmul_2_1_U0.do_adapt_9_U0.real_start & (trans_in_cnt_10 == trans_out_cnt_10) & ~grp_dataflow_wrapper_fu_6443.task_compute_attn_U0.grp_do_attn_1_fu_5150.do_matmul_2_1_U0.start_for_matmul_step1_cache_window_10_U0_U.if_read)) begin
                            $display("//      Blocked by full output start propagation FIFO 'vit_block_top_vit_block_top.grp_dataflow_wrapper_fu_6443.task_compute_attn_U0.grp_do_attn_1_fu_5150.do_matmul_2_1_U0.start_for_matmul_step1_cache_window_10_U0_U' read by process 'vit_block_top_vit_block_top.grp_dataflow_wrapper_fu_6443.task_compute_attn_U0.grp_do_attn_1_fu_5150.do_matmul_2_1_U0.matmul_step1_cache_window_10_U0',");
                        end
                    end
                    endcase
                end
                22 : begin // for proc 'vit_block_top_vit_block_top.grp_dataflow_wrapper_fu_6443.task_compute_attn_U0.grp_do_attn_1_fu_5150.do_matmul_2_1_U0.matmul_step1_cache_window_10_U0'
                    case(index2)
                    21: begin //  for dep proc 'vit_block_top_vit_block_top.grp_dataflow_wrapper_fu_6443.task_compute_attn_U0.grp_do_attn_1_fu_5150.do_matmul_2_1_U0.do_adapt_9_U0'
// for dep channel 'vit_block_top_vit_block_top.grp_dataflow_wrapper_fu_6443.task_compute_attn_U0.grp_do_attn_1_fu_5150.do_matmul_2_1_U0.adpt_sm_i_U' info is :
// blk sig is {~vit_block_top_vit_block_top_inst.grp_dataflow_wrapper_fu_6443.task_compute_attn_U0.grp_do_attn_1_fu_5150.do_matmul_2_1_U0.matmul_step1_cache_window_10_U0.adpt_sm_blk_n data_FIFO}
                        if ((~grp_dataflow_wrapper_fu_6443.task_compute_attn_U0.grp_do_attn_1_fu_5150.do_matmul_2_1_U0.matmul_step1_cache_window_10_U0.adpt_sm_blk_n)) begin
                            if (~grp_dataflow_wrapper_fu_6443.task_compute_attn_U0.grp_do_attn_1_fu_5150.do_matmul_2_1_U0.adpt_sm_i_U.if_empty_n) begin
                                $display("//      Blocked by empty input FIFO 'vit_block_top_vit_block_top.grp_dataflow_wrapper_fu_6443.task_compute_attn_U0.grp_do_attn_1_fu_5150.do_matmul_2_1_U0.adpt_sm_i_U' written by process 'vit_block_top_vit_block_top.grp_dataflow_wrapper_fu_6443.task_compute_attn_U0.grp_do_attn_1_fu_5150.do_matmul_2_1_U0.do_adapt_9_U0'");
                                $fdisplay(fp, "Dependence_Channel_path vit_block_top_vit_block_top.grp_dataflow_wrapper_fu_6443.task_compute_attn_U0.grp_do_attn_1_fu_5150.do_matmul_2_1_U0.adpt_sm_i_U");
                                $fdisplay(fp, "Dependence_Channel_status EMPTY");
                            end
                            else if (~grp_dataflow_wrapper_fu_6443.task_compute_attn_U0.grp_do_attn_1_fu_5150.do_matmul_2_1_U0.adpt_sm_i_U.if_full_n) begin
                                $display("//      Blocked by full output FIFO 'vit_block_top_vit_block_top.grp_dataflow_wrapper_fu_6443.task_compute_attn_U0.grp_do_attn_1_fu_5150.do_matmul_2_1_U0.adpt_sm_i_U' read by process 'vit_block_top_vit_block_top.grp_dataflow_wrapper_fu_6443.task_compute_attn_U0.grp_do_attn_1_fu_5150.do_matmul_2_1_U0.do_adapt_9_U0'");
                                $fdisplay(fp, "Dependence_Channel_path vit_block_top_vit_block_top.grp_dataflow_wrapper_fu_6443.task_compute_attn_U0.grp_do_attn_1_fu_5150.do_matmul_2_1_U0.adpt_sm_i_U");
                                $fdisplay(fp, "Dependence_Channel_status FULL");
                            end
                        end
// for dep channel 'vit_block_top_vit_block_top.grp_dataflow_wrapper_fu_6443.task_compute_attn_U0.grp_do_attn_1_fu_5150.do_matmul_2_1_U0.start_for_matmul_step1_cache_window_10_U0_U' info is :
// blk sig is {{~vit_block_top_vit_block_top_inst.grp_dataflow_wrapper_fu_6443.task_compute_attn_U0.grp_do_attn_1_fu_5150.do_matmul_2_1_U0.start_for_matmul_step1_cache_window_10_U0_U.if_empty_n & vit_block_top_vit_block_top_inst.grp_dataflow_wrapper_fu_6443.task_compute_attn_U0.grp_do_attn_1_fu_5150.do_matmul_2_1_U0.matmul_step1_cache_window_10_U0.ap_idle & ~vit_block_top_vit_block_top_inst.grp_dataflow_wrapper_fu_6443.task_compute_attn_U0.grp_do_attn_1_fu_5150.do_matmul_2_1_U0.start_for_matmul_step1_cache_window_10_U0_U.if_write} start_FIFO}
                        if ((~grp_dataflow_wrapper_fu_6443.task_compute_attn_U0.grp_do_attn_1_fu_5150.do_matmul_2_1_U0.start_for_matmul_step1_cache_window_10_U0_U.if_empty_n & grp_dataflow_wrapper_fu_6443.task_compute_attn_U0.grp_do_attn_1_fu_5150.do_matmul_2_1_U0.matmul_step1_cache_window_10_U0.ap_idle & ~grp_dataflow_wrapper_fu_6443.task_compute_attn_U0.grp_do_attn_1_fu_5150.do_matmul_2_1_U0.start_for_matmul_step1_cache_window_10_U0_U.if_write)) begin
                            $display("//      Blocked by missing 'ap_start' from start propagation FIFO 'vit_block_top_vit_block_top.grp_dataflow_wrapper_fu_6443.task_compute_attn_U0.grp_do_attn_1_fu_5150.do_matmul_2_1_U0.start_for_matmul_step1_cache_window_10_U0_U' written by process 'vit_block_top_vit_block_top.grp_dataflow_wrapper_fu_6443.task_compute_attn_U0.grp_do_attn_1_fu_5150.do_matmul_2_1_U0.do_adapt_9_U0',");
                        end
                    end
                    23: begin //  for dep proc 'vit_block_top_vit_block_top.grp_dataflow_wrapper_fu_6443.task_compute_attn_U0.grp_do_attn_1_fu_5150.do_matmul_2_1_U0.matmul_step2_mac_11_U0'
// for dep channel 'vit_block_top_vit_block_top.grp_dataflow_wrapper_fu_6443.task_compute_attn_U0.grp_do_attn_1_fu_5150.do_matmul_2_1_U0.cache_window_sm_i_U' info is :
// blk sig is {~vit_block_top_vit_block_top_inst.grp_dataflow_wrapper_fu_6443.task_compute_attn_U0.grp_do_attn_1_fu_5150.do_matmul_2_1_U0.matmul_step1_cache_window_10_U0.cache_window_sm_blk_n data_FIFO}
                        if ((~grp_dataflow_wrapper_fu_6443.task_compute_attn_U0.grp_do_attn_1_fu_5150.do_matmul_2_1_U0.matmul_step1_cache_window_10_U0.cache_window_sm_blk_n)) begin
                            if (~grp_dataflow_wrapper_fu_6443.task_compute_attn_U0.grp_do_attn_1_fu_5150.do_matmul_2_1_U0.cache_window_sm_i_U.if_empty_n) begin
                                $display("//      Blocked by empty input FIFO 'vit_block_top_vit_block_top.grp_dataflow_wrapper_fu_6443.task_compute_attn_U0.grp_do_attn_1_fu_5150.do_matmul_2_1_U0.cache_window_sm_i_U' written by process 'vit_block_top_vit_block_top.grp_dataflow_wrapper_fu_6443.task_compute_attn_U0.grp_do_attn_1_fu_5150.do_matmul_2_1_U0.matmul_step2_mac_11_U0'");
                                $fdisplay(fp, "Dependence_Channel_path vit_block_top_vit_block_top.grp_dataflow_wrapper_fu_6443.task_compute_attn_U0.grp_do_attn_1_fu_5150.do_matmul_2_1_U0.cache_window_sm_i_U");
                                $fdisplay(fp, "Dependence_Channel_status EMPTY");
                            end
                            else if (~grp_dataflow_wrapper_fu_6443.task_compute_attn_U0.grp_do_attn_1_fu_5150.do_matmul_2_1_U0.cache_window_sm_i_U.if_full_n) begin
                                $display("//      Blocked by full output FIFO 'vit_block_top_vit_block_top.grp_dataflow_wrapper_fu_6443.task_compute_attn_U0.grp_do_attn_1_fu_5150.do_matmul_2_1_U0.cache_window_sm_i_U' read by process 'vit_block_top_vit_block_top.grp_dataflow_wrapper_fu_6443.task_compute_attn_U0.grp_do_attn_1_fu_5150.do_matmul_2_1_U0.matmul_step2_mac_11_U0'");
                                $fdisplay(fp, "Dependence_Channel_path vit_block_top_vit_block_top.grp_dataflow_wrapper_fu_6443.task_compute_attn_U0.grp_do_attn_1_fu_5150.do_matmul_2_1_U0.cache_window_sm_i_U");
                                $fdisplay(fp, "Dependence_Channel_status FULL");
                            end
                        end
// for dep channel 'vit_block_top_vit_block_top.grp_dataflow_wrapper_fu_6443.task_compute_attn_U0.grp_do_attn_1_fu_5150.do_matmul_2_1_U0.start_for_matmul_step2_mac_11_U0_U' info is :
// blk sig is {{~vit_block_top_vit_block_top_inst.grp_dataflow_wrapper_fu_6443.task_compute_attn_U0.grp_do_attn_1_fu_5150.do_matmul_2_1_U0.start_for_matmul_step2_mac_11_U0_U.if_full_n & vit_block_top_vit_block_top_inst.grp_dataflow_wrapper_fu_6443.task_compute_attn_U0.grp_do_attn_1_fu_5150.do_matmul_2_1_U0.matmul_step1_cache_window_10_U0.ap_start & ~vit_block_top_vit_block_top_inst.grp_dataflow_wrapper_fu_6443.task_compute_attn_U0.grp_do_attn_1_fu_5150.do_matmul_2_1_U0.matmul_step1_cache_window_10_U0.real_start & (trans_in_cnt_11 == trans_out_cnt_11) & ~vit_block_top_vit_block_top_inst.grp_dataflow_wrapper_fu_6443.task_compute_attn_U0.grp_do_attn_1_fu_5150.do_matmul_2_1_U0.start_for_matmul_step2_mac_11_U0_U.if_read} start_FIFO}
                        if ((~grp_dataflow_wrapper_fu_6443.task_compute_attn_U0.grp_do_attn_1_fu_5150.do_matmul_2_1_U0.start_for_matmul_step2_mac_11_U0_U.if_full_n & grp_dataflow_wrapper_fu_6443.task_compute_attn_U0.grp_do_attn_1_fu_5150.do_matmul_2_1_U0.matmul_step1_cache_window_10_U0.ap_start & ~grp_dataflow_wrapper_fu_6443.task_compute_attn_U0.grp_do_attn_1_fu_5150.do_matmul_2_1_U0.matmul_step1_cache_window_10_U0.real_start & (trans_in_cnt_11 == trans_out_cnt_11) & ~grp_dataflow_wrapper_fu_6443.task_compute_attn_U0.grp_do_attn_1_fu_5150.do_matmul_2_1_U0.start_for_matmul_step2_mac_11_U0_U.if_read)) begin
                            $display("//      Blocked by full output start propagation FIFO 'vit_block_top_vit_block_top.grp_dataflow_wrapper_fu_6443.task_compute_attn_U0.grp_do_attn_1_fu_5150.do_matmul_2_1_U0.start_for_matmul_step2_mac_11_U0_U' read by process 'vit_block_top_vit_block_top.grp_dataflow_wrapper_fu_6443.task_compute_attn_U0.grp_do_attn_1_fu_5150.do_matmul_2_1_U0.matmul_step2_mac_11_U0',");
                        end
                    end
                    endcase
                end
                23 : begin // for proc 'vit_block_top_vit_block_top.grp_dataflow_wrapper_fu_6443.task_compute_attn_U0.grp_do_attn_1_fu_5150.do_matmul_2_1_U0.matmul_step2_mac_11_U0'
                    case(index2)
                    22: begin //  for dep proc 'vit_block_top_vit_block_top.grp_dataflow_wrapper_fu_6443.task_compute_attn_U0.grp_do_attn_1_fu_5150.do_matmul_2_1_U0.matmul_step1_cache_window_10_U0'
// for dep channel 'vit_block_top_vit_block_top.grp_dataflow_wrapper_fu_6443.task_compute_attn_U0.grp_do_attn_1_fu_5150.do_matmul_2_1_U0.cache_window_sm_i_U' info is :
// blk sig is {~vit_block_top_vit_block_top_inst.grp_dataflow_wrapper_fu_6443.task_compute_attn_U0.grp_do_attn_1_fu_5150.do_matmul_2_1_U0.matmul_step2_mac_11_U0.cache_window_sm_blk_n data_FIFO}
                        if ((~grp_dataflow_wrapper_fu_6443.task_compute_attn_U0.grp_do_attn_1_fu_5150.do_matmul_2_1_U0.matmul_step2_mac_11_U0.cache_window_sm_blk_n)) begin
                            if (~grp_dataflow_wrapper_fu_6443.task_compute_attn_U0.grp_do_attn_1_fu_5150.do_matmul_2_1_U0.cache_window_sm_i_U.if_empty_n) begin
                                $display("//      Blocked by empty input FIFO 'vit_block_top_vit_block_top.grp_dataflow_wrapper_fu_6443.task_compute_attn_U0.grp_do_attn_1_fu_5150.do_matmul_2_1_U0.cache_window_sm_i_U' written by process 'vit_block_top_vit_block_top.grp_dataflow_wrapper_fu_6443.task_compute_attn_U0.grp_do_attn_1_fu_5150.do_matmul_2_1_U0.matmul_step1_cache_window_10_U0'");
                                $fdisplay(fp, "Dependence_Channel_path vit_block_top_vit_block_top.grp_dataflow_wrapper_fu_6443.task_compute_attn_U0.grp_do_attn_1_fu_5150.do_matmul_2_1_U0.cache_window_sm_i_U");
                                $fdisplay(fp, "Dependence_Channel_status EMPTY");
                            end
                            else if (~grp_dataflow_wrapper_fu_6443.task_compute_attn_U0.grp_do_attn_1_fu_5150.do_matmul_2_1_U0.cache_window_sm_i_U.if_full_n) begin
                                $display("//      Blocked by full output FIFO 'vit_block_top_vit_block_top.grp_dataflow_wrapper_fu_6443.task_compute_attn_U0.grp_do_attn_1_fu_5150.do_matmul_2_1_U0.cache_window_sm_i_U' read by process 'vit_block_top_vit_block_top.grp_dataflow_wrapper_fu_6443.task_compute_attn_U0.grp_do_attn_1_fu_5150.do_matmul_2_1_U0.matmul_step1_cache_window_10_U0'");
                                $fdisplay(fp, "Dependence_Channel_path vit_block_top_vit_block_top.grp_dataflow_wrapper_fu_6443.task_compute_attn_U0.grp_do_attn_1_fu_5150.do_matmul_2_1_U0.cache_window_sm_i_U");
                                $fdisplay(fp, "Dependence_Channel_status FULL");
                            end
                        end
// for dep channel 'vit_block_top_vit_block_top.grp_dataflow_wrapper_fu_6443.task_compute_attn_U0.grp_do_attn_1_fu_5150.do_matmul_2_1_U0.start_for_matmul_step2_mac_11_U0_U' info is :
// blk sig is {{~vit_block_top_vit_block_top_inst.grp_dataflow_wrapper_fu_6443.task_compute_attn_U0.grp_do_attn_1_fu_5150.do_matmul_2_1_U0.start_for_matmul_step2_mac_11_U0_U.if_empty_n & vit_block_top_vit_block_top_inst.grp_dataflow_wrapper_fu_6443.task_compute_attn_U0.grp_do_attn_1_fu_5150.do_matmul_2_1_U0.matmul_step2_mac_11_U0.ap_idle & ~vit_block_top_vit_block_top_inst.grp_dataflow_wrapper_fu_6443.task_compute_attn_U0.grp_do_attn_1_fu_5150.do_matmul_2_1_U0.start_for_matmul_step2_mac_11_U0_U.if_write} start_FIFO}
                        if ((~grp_dataflow_wrapper_fu_6443.task_compute_attn_U0.grp_do_attn_1_fu_5150.do_matmul_2_1_U0.start_for_matmul_step2_mac_11_U0_U.if_empty_n & grp_dataflow_wrapper_fu_6443.task_compute_attn_U0.grp_do_attn_1_fu_5150.do_matmul_2_1_U0.matmul_step2_mac_11_U0.ap_idle & ~grp_dataflow_wrapper_fu_6443.task_compute_attn_U0.grp_do_attn_1_fu_5150.do_matmul_2_1_U0.start_for_matmul_step2_mac_11_U0_U.if_write)) begin
                            $display("//      Blocked by missing 'ap_start' from start propagation FIFO 'vit_block_top_vit_block_top.grp_dataflow_wrapper_fu_6443.task_compute_attn_U0.grp_do_attn_1_fu_5150.do_matmul_2_1_U0.start_for_matmul_step2_mac_11_U0_U' written by process 'vit_block_top_vit_block_top.grp_dataflow_wrapper_fu_6443.task_compute_attn_U0.grp_do_attn_1_fu_5150.do_matmul_2_1_U0.matmul_step1_cache_window_10_U0',");
                        end
                    end
                    24: begin //  for dep proc 'vit_block_top_vit_block_top.grp_dataflow_wrapper_fu_6443.task_compute_attn_U0.grp_do_attn_1_fu_5150.do_matmul_2_1_U0.do_adapt_12_1_U0'
// for dep channel 'vit_block_top_vit_block_top.grp_dataflow_wrapper_fu_6443.task_compute_attn_U0.grp_do_attn_1_fu_5150.do_matmul_2_1_U0.mac_sm_i_U' info is :
// blk sig is {~vit_block_top_vit_block_top_inst.grp_dataflow_wrapper_fu_6443.task_compute_attn_U0.grp_do_attn_1_fu_5150.do_matmul_2_1_U0.matmul_step2_mac_11_U0.mac_sm_blk_n data_FIFO}
                        if ((~grp_dataflow_wrapper_fu_6443.task_compute_attn_U0.grp_do_attn_1_fu_5150.do_matmul_2_1_U0.matmul_step2_mac_11_U0.mac_sm_blk_n)) begin
                            if (~grp_dataflow_wrapper_fu_6443.task_compute_attn_U0.grp_do_attn_1_fu_5150.do_matmul_2_1_U0.mac_sm_i_U.if_empty_n) begin
                                $display("//      Blocked by empty input FIFO 'vit_block_top_vit_block_top.grp_dataflow_wrapper_fu_6443.task_compute_attn_U0.grp_do_attn_1_fu_5150.do_matmul_2_1_U0.mac_sm_i_U' written by process 'vit_block_top_vit_block_top.grp_dataflow_wrapper_fu_6443.task_compute_attn_U0.grp_do_attn_1_fu_5150.do_matmul_2_1_U0.do_adapt_12_1_U0'");
                                $fdisplay(fp, "Dependence_Channel_path vit_block_top_vit_block_top.grp_dataflow_wrapper_fu_6443.task_compute_attn_U0.grp_do_attn_1_fu_5150.do_matmul_2_1_U0.mac_sm_i_U");
                                $fdisplay(fp, "Dependence_Channel_status EMPTY");
                            end
                            else if (~grp_dataflow_wrapper_fu_6443.task_compute_attn_U0.grp_do_attn_1_fu_5150.do_matmul_2_1_U0.mac_sm_i_U.if_full_n) begin
                                $display("//      Blocked by full output FIFO 'vit_block_top_vit_block_top.grp_dataflow_wrapper_fu_6443.task_compute_attn_U0.grp_do_attn_1_fu_5150.do_matmul_2_1_U0.mac_sm_i_U' read by process 'vit_block_top_vit_block_top.grp_dataflow_wrapper_fu_6443.task_compute_attn_U0.grp_do_attn_1_fu_5150.do_matmul_2_1_U0.do_adapt_12_1_U0'");
                                $fdisplay(fp, "Dependence_Channel_path vit_block_top_vit_block_top.grp_dataflow_wrapper_fu_6443.task_compute_attn_U0.grp_do_attn_1_fu_5150.do_matmul_2_1_U0.mac_sm_i_U");
                                $fdisplay(fp, "Dependence_Channel_status FULL");
                            end
                        end
// for dep channel 'vit_block_top_vit_block_top.grp_dataflow_wrapper_fu_6443.task_compute_attn_U0.grp_do_attn_1_fu_5150.do_matmul_2_1_U0.start_for_do_adapt_12_1_U0_U' info is :
// blk sig is {{~vit_block_top_vit_block_top_inst.grp_dataflow_wrapper_fu_6443.task_compute_attn_U0.grp_do_attn_1_fu_5150.do_matmul_2_1_U0.start_for_do_adapt_12_1_U0_U.if_full_n & vit_block_top_vit_block_top_inst.grp_dataflow_wrapper_fu_6443.task_compute_attn_U0.grp_do_attn_1_fu_5150.do_matmul_2_1_U0.matmul_step2_mac_11_U0.ap_start & ~vit_block_top_vit_block_top_inst.grp_dataflow_wrapper_fu_6443.task_compute_attn_U0.grp_do_attn_1_fu_5150.do_matmul_2_1_U0.matmul_step2_mac_11_U0.real_start & (trans_in_cnt_12 == trans_out_cnt_12) & ~vit_block_top_vit_block_top_inst.grp_dataflow_wrapper_fu_6443.task_compute_attn_U0.grp_do_attn_1_fu_5150.do_matmul_2_1_U0.start_for_do_adapt_12_1_U0_U.if_read} start_FIFO}
                        if ((~grp_dataflow_wrapper_fu_6443.task_compute_attn_U0.grp_do_attn_1_fu_5150.do_matmul_2_1_U0.start_for_do_adapt_12_1_U0_U.if_full_n & grp_dataflow_wrapper_fu_6443.task_compute_attn_U0.grp_do_attn_1_fu_5150.do_matmul_2_1_U0.matmul_step2_mac_11_U0.ap_start & ~grp_dataflow_wrapper_fu_6443.task_compute_attn_U0.grp_do_attn_1_fu_5150.do_matmul_2_1_U0.matmul_step2_mac_11_U0.real_start & (trans_in_cnt_12 == trans_out_cnt_12) & ~grp_dataflow_wrapper_fu_6443.task_compute_attn_U0.grp_do_attn_1_fu_5150.do_matmul_2_1_U0.start_for_do_adapt_12_1_U0_U.if_read)) begin
                            $display("//      Blocked by full output start propagation FIFO 'vit_block_top_vit_block_top.grp_dataflow_wrapper_fu_6443.task_compute_attn_U0.grp_do_attn_1_fu_5150.do_matmul_2_1_U0.start_for_do_adapt_12_1_U0_U' read by process 'vit_block_top_vit_block_top.grp_dataflow_wrapper_fu_6443.task_compute_attn_U0.grp_do_attn_1_fu_5150.do_matmul_2_1_U0.do_adapt_12_1_U0',");
                        end
                    end
                    endcase
                end
                24 : begin // for proc 'vit_block_top_vit_block_top.grp_dataflow_wrapper_fu_6443.task_compute_attn_U0.grp_do_attn_1_fu_5150.do_matmul_2_1_U0.do_adapt_12_1_U0'
                    case(index2)
                    23: begin //  for dep proc 'vit_block_top_vit_block_top.grp_dataflow_wrapper_fu_6443.task_compute_attn_U0.grp_do_attn_1_fu_5150.do_matmul_2_1_U0.matmul_step2_mac_11_U0'
// for dep channel 'vit_block_top_vit_block_top.grp_dataflow_wrapper_fu_6443.task_compute_attn_U0.grp_do_attn_1_fu_5150.do_matmul_2_1_U0.mac_sm_i_U' info is :
// blk sig is {~vit_block_top_vit_block_top_inst.grp_dataflow_wrapper_fu_6443.task_compute_attn_U0.grp_do_attn_1_fu_5150.do_matmul_2_1_U0.do_adapt_12_1_U0.mac_sm_blk_n data_FIFO}
                        if ((~grp_dataflow_wrapper_fu_6443.task_compute_attn_U0.grp_do_attn_1_fu_5150.do_matmul_2_1_U0.do_adapt_12_1_U0.mac_sm_blk_n)) begin
                            if (~grp_dataflow_wrapper_fu_6443.task_compute_attn_U0.grp_do_attn_1_fu_5150.do_matmul_2_1_U0.mac_sm_i_U.if_empty_n) begin
                                $display("//      Blocked by empty input FIFO 'vit_block_top_vit_block_top.grp_dataflow_wrapper_fu_6443.task_compute_attn_U0.grp_do_attn_1_fu_5150.do_matmul_2_1_U0.mac_sm_i_U' written by process 'vit_block_top_vit_block_top.grp_dataflow_wrapper_fu_6443.task_compute_attn_U0.grp_do_attn_1_fu_5150.do_matmul_2_1_U0.matmul_step2_mac_11_U0'");
                                $fdisplay(fp, "Dependence_Channel_path vit_block_top_vit_block_top.grp_dataflow_wrapper_fu_6443.task_compute_attn_U0.grp_do_attn_1_fu_5150.do_matmul_2_1_U0.mac_sm_i_U");
                                $fdisplay(fp, "Dependence_Channel_status EMPTY");
                            end
                            else if (~grp_dataflow_wrapper_fu_6443.task_compute_attn_U0.grp_do_attn_1_fu_5150.do_matmul_2_1_U0.mac_sm_i_U.if_full_n) begin
                                $display("//      Blocked by full output FIFO 'vit_block_top_vit_block_top.grp_dataflow_wrapper_fu_6443.task_compute_attn_U0.grp_do_attn_1_fu_5150.do_matmul_2_1_U0.mac_sm_i_U' read by process 'vit_block_top_vit_block_top.grp_dataflow_wrapper_fu_6443.task_compute_attn_U0.grp_do_attn_1_fu_5150.do_matmul_2_1_U0.matmul_step2_mac_11_U0'");
                                $fdisplay(fp, "Dependence_Channel_path vit_block_top_vit_block_top.grp_dataflow_wrapper_fu_6443.task_compute_attn_U0.grp_do_attn_1_fu_5150.do_matmul_2_1_U0.mac_sm_i_U");
                                $fdisplay(fp, "Dependence_Channel_status FULL");
                            end
                        end
// for dep channel 'vit_block_top_vit_block_top.grp_dataflow_wrapper_fu_6443.task_compute_attn_U0.grp_do_attn_1_fu_5150.do_matmul_2_1_U0.start_for_do_adapt_12_1_U0_U' info is :
// blk sig is {{~vit_block_top_vit_block_top_inst.grp_dataflow_wrapper_fu_6443.task_compute_attn_U0.grp_do_attn_1_fu_5150.do_matmul_2_1_U0.start_for_do_adapt_12_1_U0_U.if_empty_n & vit_block_top_vit_block_top_inst.grp_dataflow_wrapper_fu_6443.task_compute_attn_U0.grp_do_attn_1_fu_5150.do_matmul_2_1_U0.do_adapt_12_1_U0.ap_idle & ~vit_block_top_vit_block_top_inst.grp_dataflow_wrapper_fu_6443.task_compute_attn_U0.grp_do_attn_1_fu_5150.do_matmul_2_1_U0.start_for_do_adapt_12_1_U0_U.if_write} start_FIFO}
                        if ((~grp_dataflow_wrapper_fu_6443.task_compute_attn_U0.grp_do_attn_1_fu_5150.do_matmul_2_1_U0.start_for_do_adapt_12_1_U0_U.if_empty_n & grp_dataflow_wrapper_fu_6443.task_compute_attn_U0.grp_do_attn_1_fu_5150.do_matmul_2_1_U0.do_adapt_12_1_U0.ap_idle & ~grp_dataflow_wrapper_fu_6443.task_compute_attn_U0.grp_do_attn_1_fu_5150.do_matmul_2_1_U0.start_for_do_adapt_12_1_U0_U.if_write)) begin
                            $display("//      Blocked by missing 'ap_start' from start propagation FIFO 'vit_block_top_vit_block_top.grp_dataflow_wrapper_fu_6443.task_compute_attn_U0.grp_do_attn_1_fu_5150.do_matmul_2_1_U0.start_for_do_adapt_12_1_U0_U' written by process 'vit_block_top_vit_block_top.grp_dataflow_wrapper_fu_6443.task_compute_attn_U0.grp_do_attn_1_fu_5150.do_matmul_2_1_U0.matmul_step2_mac_11_U0',");
                        end
                    end
                    31: begin //  for dep proc 'vit_block_top_vit_block_top.grp_dataflow_wrapper_fu_6443.task_compute_attn_U0.grp_do_attn_1_fu_5150.do_quant_3_U0'
// for dep channel 'vit_block_top_vit_block_top.grp_dataflow_wrapper_fu_6443.task_compute_attn_U0.grp_do_attn_1_fu_5150.k_sm_i_U' info is :
// blk sig is {~vit_block_top_vit_block_top_inst.grp_dataflow_wrapper_fu_6443.task_compute_attn_U0.grp_do_attn_1_fu_5150.do_matmul_2_1_U0.do_adapt_12_1_U0.k_sm_blk_n data_FIFO}
                        if ((~grp_dataflow_wrapper_fu_6443.task_compute_attn_U0.grp_do_attn_1_fu_5150.do_matmul_2_1_U0.do_adapt_12_1_U0.k_sm_blk_n)) begin
                            if (~grp_dataflow_wrapper_fu_6443.task_compute_attn_U0.grp_do_attn_1_fu_5150.k_sm_i_U.if_empty_n) begin
                                $display("//      Blocked by empty input FIFO 'vit_block_top_vit_block_top.grp_dataflow_wrapper_fu_6443.task_compute_attn_U0.grp_do_attn_1_fu_5150.k_sm_i_U' written by process 'vit_block_top_vit_block_top.grp_dataflow_wrapper_fu_6443.task_compute_attn_U0.grp_do_attn_1_fu_5150.do_quant_3_U0'");
                                $fdisplay(fp, "Dependence_Channel_path vit_block_top_vit_block_top.grp_dataflow_wrapper_fu_6443.task_compute_attn_U0.grp_do_attn_1_fu_5150.k_sm_i_U");
                                $fdisplay(fp, "Dependence_Channel_status EMPTY");
                            end
                            else if (~grp_dataflow_wrapper_fu_6443.task_compute_attn_U0.grp_do_attn_1_fu_5150.k_sm_i_U.if_full_n) begin
                                $display("//      Blocked by full output FIFO 'vit_block_top_vit_block_top.grp_dataflow_wrapper_fu_6443.task_compute_attn_U0.grp_do_attn_1_fu_5150.k_sm_i_U' read by process 'vit_block_top_vit_block_top.grp_dataflow_wrapper_fu_6443.task_compute_attn_U0.grp_do_attn_1_fu_5150.do_quant_3_U0'");
                                $fdisplay(fp, "Dependence_Channel_path vit_block_top_vit_block_top.grp_dataflow_wrapper_fu_6443.task_compute_attn_U0.grp_do_attn_1_fu_5150.k_sm_i_U");
                                $fdisplay(fp, "Dependence_Channel_status FULL");
                            end
                        end
                    end
                    endcase
                end
                25 : begin // for proc 'vit_block_top_vit_block_top.grp_dataflow_wrapper_fu_6443.task_compute_attn_U0.grp_do_attn_1_fu_5150.do_matmul_4_U0'
                    case(index2)
                    14: begin //  for dep proc 'vit_block_top_vit_block_top.grp_dataflow_wrapper_fu_6443.task_compute_attn_U0.grp_do_attn_1_fu_5150.stream_copy3_U0'
// for dep channel 'vit_block_top_vit_block_top.grp_dataflow_wrapper_fu_6443.task_compute_attn_U0.grp_do_attn_1_fu_5150.lnq_sm_cp3_i_U' info is :
// blk sig is {~vit_block_top_vit_block_top_inst.grp_dataflow_wrapper_fu_6443.task_compute_attn_U0.grp_do_attn_1_fu_5150.do_matmul_4_U0.do_adapt_13_U0.lnq_sm_cp3_blk_n data_FIFO}
                        if ((~grp_dataflow_wrapper_fu_6443.task_compute_attn_U0.grp_do_attn_1_fu_5150.do_matmul_4_U0.do_adapt_13_U0.lnq_sm_cp3_blk_n)) begin
                            if (~grp_dataflow_wrapper_fu_6443.task_compute_attn_U0.grp_do_attn_1_fu_5150.lnq_sm_cp3_i_U.if_empty_n) begin
                                $display("//      Blocked by empty input FIFO 'vit_block_top_vit_block_top.grp_dataflow_wrapper_fu_6443.task_compute_attn_U0.grp_do_attn_1_fu_5150.lnq_sm_cp3_i_U' written by process 'vit_block_top_vit_block_top.grp_dataflow_wrapper_fu_6443.task_compute_attn_U0.grp_do_attn_1_fu_5150.stream_copy3_U0'");
                                $fdisplay(fp, "Dependence_Channel_path vit_block_top_vit_block_top.grp_dataflow_wrapper_fu_6443.task_compute_attn_U0.grp_do_attn_1_fu_5150.lnq_sm_cp3_i_U");
                                $fdisplay(fp, "Dependence_Channel_status EMPTY");
                            end
                            else if (~grp_dataflow_wrapper_fu_6443.task_compute_attn_U0.grp_do_attn_1_fu_5150.lnq_sm_cp3_i_U.if_full_n) begin
                                $display("//      Blocked by full output FIFO 'vit_block_top_vit_block_top.grp_dataflow_wrapper_fu_6443.task_compute_attn_U0.grp_do_attn_1_fu_5150.lnq_sm_cp3_i_U' read by process 'vit_block_top_vit_block_top.grp_dataflow_wrapper_fu_6443.task_compute_attn_U0.grp_do_attn_1_fu_5150.stream_copy3_U0'");
                                $fdisplay(fp, "Dependence_Channel_path vit_block_top_vit_block_top.grp_dataflow_wrapper_fu_6443.task_compute_attn_U0.grp_do_attn_1_fu_5150.lnq_sm_cp3_i_U");
                                $fdisplay(fp, "Dependence_Channel_status FULL");
                            end
                        end
// for dep channel 'vit_block_top_vit_block_top.grp_dataflow_wrapper_fu_6443.task_compute_attn_U0.grp_do_attn_1_fu_5150.start_for_do_matmul_4_U0_U' info is :
// blk sig is {{~vit_block_top_vit_block_top_inst.grp_dataflow_wrapper_fu_6443.task_compute_attn_U0.grp_do_attn_1_fu_5150.start_for_do_matmul_4_U0_U.if_empty_n & vit_block_top_vit_block_top_inst.grp_dataflow_wrapper_fu_6443.task_compute_attn_U0.grp_do_attn_1_fu_5150.do_matmul_4_U0.ap_idle & ~vit_block_top_vit_block_top_inst.grp_dataflow_wrapper_fu_6443.task_compute_attn_U0.grp_do_attn_1_fu_5150.start_for_do_matmul_4_U0_U.if_write} start_FIFO}
                        if ((~grp_dataflow_wrapper_fu_6443.task_compute_attn_U0.grp_do_attn_1_fu_5150.start_for_do_matmul_4_U0_U.if_empty_n & grp_dataflow_wrapper_fu_6443.task_compute_attn_U0.grp_do_attn_1_fu_5150.do_matmul_4_U0.ap_idle & ~grp_dataflow_wrapper_fu_6443.task_compute_attn_U0.grp_do_attn_1_fu_5150.start_for_do_matmul_4_U0_U.if_write)) begin
                            $display("//      Blocked by missing 'ap_start' from start propagation FIFO 'vit_block_top_vit_block_top.grp_dataflow_wrapper_fu_6443.task_compute_attn_U0.grp_do_attn_1_fu_5150.start_for_do_matmul_4_U0_U' written by process 'vit_block_top_vit_block_top.grp_dataflow_wrapper_fu_6443.task_compute_attn_U0.grp_do_attn_1_fu_5150.stream_copy3_U0',");
                        end
                    end
                    32: begin //  for dep proc 'vit_block_top_vit_block_top.grp_dataflow_wrapper_fu_6443.task_compute_attn_U0.grp_do_attn_1_fu_5150.do_quant_1_U0'
// for dep channel 'vit_block_top_vit_block_top.grp_dataflow_wrapper_fu_6443.task_compute_attn_U0.grp_do_attn_1_fu_5150.v_sm_i_U' info is :
// blk sig is {~vit_block_top_vit_block_top_inst.grp_dataflow_wrapper_fu_6443.task_compute_attn_U0.grp_do_attn_1_fu_5150.do_matmul_4_U0.do_adapt_13_1_U0.v_sm_blk_n data_FIFO}
                        if ((~grp_dataflow_wrapper_fu_6443.task_compute_attn_U0.grp_do_attn_1_fu_5150.do_matmul_4_U0.do_adapt_13_1_U0.v_sm_blk_n)) begin
                            if (~grp_dataflow_wrapper_fu_6443.task_compute_attn_U0.grp_do_attn_1_fu_5150.v_sm_i_U.if_empty_n) begin
                                $display("//      Blocked by empty input FIFO 'vit_block_top_vit_block_top.grp_dataflow_wrapper_fu_6443.task_compute_attn_U0.grp_do_attn_1_fu_5150.v_sm_i_U' written by process 'vit_block_top_vit_block_top.grp_dataflow_wrapper_fu_6443.task_compute_attn_U0.grp_do_attn_1_fu_5150.do_quant_1_U0'");
                                $fdisplay(fp, "Dependence_Channel_path vit_block_top_vit_block_top.grp_dataflow_wrapper_fu_6443.task_compute_attn_U0.grp_do_attn_1_fu_5150.v_sm_i_U");
                                $fdisplay(fp, "Dependence_Channel_status EMPTY");
                            end
                            else if (~grp_dataflow_wrapper_fu_6443.task_compute_attn_U0.grp_do_attn_1_fu_5150.v_sm_i_U.if_full_n) begin
                                $display("//      Blocked by full output FIFO 'vit_block_top_vit_block_top.grp_dataflow_wrapper_fu_6443.task_compute_attn_U0.grp_do_attn_1_fu_5150.v_sm_i_U' read by process 'vit_block_top_vit_block_top.grp_dataflow_wrapper_fu_6443.task_compute_attn_U0.grp_do_attn_1_fu_5150.do_quant_1_U0'");
                                $fdisplay(fp, "Dependence_Channel_path vit_block_top_vit_block_top.grp_dataflow_wrapper_fu_6443.task_compute_attn_U0.grp_do_attn_1_fu_5150.v_sm_i_U");
                                $fdisplay(fp, "Dependence_Channel_status FULL");
                            end
                        end
// for dep channel 'vit_block_top_vit_block_top.grp_dataflow_wrapper_fu_6443.task_compute_attn_U0.grp_do_attn_1_fu_5150.start_for_do_quant_1_U0_U' info is :
// blk sig is {{~vit_block_top_vit_block_top_inst.grp_dataflow_wrapper_fu_6443.task_compute_attn_U0.grp_do_attn_1_fu_5150.start_for_do_quant_1_U0_U.if_full_n & vit_block_top_vit_block_top_inst.grp_dataflow_wrapper_fu_6443.task_compute_attn_U0.grp_do_attn_1_fu_5150.do_matmul_4_U0.ap_start & ~vit_block_top_vit_block_top_inst.grp_dataflow_wrapper_fu_6443.task_compute_attn_U0.grp_do_attn_1_fu_5150.do_matmul_4_U0.real_start & (trans_in_cnt_18 == trans_out_cnt_18) & ~vit_block_top_vit_block_top_inst.grp_dataflow_wrapper_fu_6443.task_compute_attn_U0.grp_do_attn_1_fu_5150.start_for_do_quant_1_U0_U.if_read} start_FIFO}
                        if ((~grp_dataflow_wrapper_fu_6443.task_compute_attn_U0.grp_do_attn_1_fu_5150.start_for_do_quant_1_U0_U.if_full_n & grp_dataflow_wrapper_fu_6443.task_compute_attn_U0.grp_do_attn_1_fu_5150.do_matmul_4_U0.ap_start & ~grp_dataflow_wrapper_fu_6443.task_compute_attn_U0.grp_do_attn_1_fu_5150.do_matmul_4_U0.real_start & (trans_in_cnt_18 == trans_out_cnt_18) & ~grp_dataflow_wrapper_fu_6443.task_compute_attn_U0.grp_do_attn_1_fu_5150.start_for_do_quant_1_U0_U.if_read)) begin
                            $display("//      Blocked by full output start propagation FIFO 'vit_block_top_vit_block_top.grp_dataflow_wrapper_fu_6443.task_compute_attn_U0.grp_do_attn_1_fu_5150.start_for_do_quant_1_U0_U' read by process 'vit_block_top_vit_block_top.grp_dataflow_wrapper_fu_6443.task_compute_attn_U0.grp_do_attn_1_fu_5150.do_quant_1_U0',");
                        end
                    end
                    endcase
                end
                26 : begin // for proc 'vit_block_top_vit_block_top.grp_dataflow_wrapper_fu_6443.task_compute_attn_U0.grp_do_attn_1_fu_5150.do_matmul_4_U0.do_adapt_13_U0'
                    case(index2)
                    14: begin //  for dep proc 'vit_block_top_vit_block_top.grp_dataflow_wrapper_fu_6443.task_compute_attn_U0.grp_do_attn_1_fu_5150.stream_copy3_U0'
// for dep channel 'vit_block_top_vit_block_top.grp_dataflow_wrapper_fu_6443.task_compute_attn_U0.grp_do_attn_1_fu_5150.lnq_sm_cp3_i_U' info is :
// blk sig is {~vit_block_top_vit_block_top_inst.grp_dataflow_wrapper_fu_6443.task_compute_attn_U0.grp_do_attn_1_fu_5150.do_matmul_4_U0.do_adapt_13_U0.lnq_sm_cp3_blk_n data_FIFO}
                        if ((~grp_dataflow_wrapper_fu_6443.task_compute_attn_U0.grp_do_attn_1_fu_5150.do_matmul_4_U0.do_adapt_13_U0.lnq_sm_cp3_blk_n)) begin
                            if (~grp_dataflow_wrapper_fu_6443.task_compute_attn_U0.grp_do_attn_1_fu_5150.lnq_sm_cp3_i_U.if_empty_n) begin
                                $display("//      Blocked by empty input FIFO 'vit_block_top_vit_block_top.grp_dataflow_wrapper_fu_6443.task_compute_attn_U0.grp_do_attn_1_fu_5150.lnq_sm_cp3_i_U' written by process 'vit_block_top_vit_block_top.grp_dataflow_wrapper_fu_6443.task_compute_attn_U0.grp_do_attn_1_fu_5150.stream_copy3_U0'");
                                $fdisplay(fp, "Dependence_Channel_path vit_block_top_vit_block_top.grp_dataflow_wrapper_fu_6443.task_compute_attn_U0.grp_do_attn_1_fu_5150.lnq_sm_cp3_i_U");
                                $fdisplay(fp, "Dependence_Channel_status EMPTY");
                            end
                            else if (~grp_dataflow_wrapper_fu_6443.task_compute_attn_U0.grp_do_attn_1_fu_5150.lnq_sm_cp3_i_U.if_full_n) begin
                                $display("//      Blocked by full output FIFO 'vit_block_top_vit_block_top.grp_dataflow_wrapper_fu_6443.task_compute_attn_U0.grp_do_attn_1_fu_5150.lnq_sm_cp3_i_U' read by process 'vit_block_top_vit_block_top.grp_dataflow_wrapper_fu_6443.task_compute_attn_U0.grp_do_attn_1_fu_5150.stream_copy3_U0'");
                                $fdisplay(fp, "Dependence_Channel_path vit_block_top_vit_block_top.grp_dataflow_wrapper_fu_6443.task_compute_attn_U0.grp_do_attn_1_fu_5150.lnq_sm_cp3_i_U");
                                $fdisplay(fp, "Dependence_Channel_status FULL");
                            end
                        end
                    end
                    27: begin //  for dep proc 'vit_block_top_vit_block_top.grp_dataflow_wrapper_fu_6443.task_compute_attn_U0.grp_do_attn_1_fu_5150.do_matmul_4_U0.matmul_step1_cache_window_4_U0'
// for dep channel 'vit_block_top_vit_block_top.grp_dataflow_wrapper_fu_6443.task_compute_attn_U0.grp_do_attn_1_fu_5150.do_matmul_4_U0.adpt_sm_i_U' info is :
// blk sig is {~vit_block_top_vit_block_top_inst.grp_dataflow_wrapper_fu_6443.task_compute_attn_U0.grp_do_attn_1_fu_5150.do_matmul_4_U0.do_adapt_13_U0.adpt_sm_blk_n data_FIFO}
                        if ((~grp_dataflow_wrapper_fu_6443.task_compute_attn_U0.grp_do_attn_1_fu_5150.do_matmul_4_U0.do_adapt_13_U0.adpt_sm_blk_n)) begin
                            if (~grp_dataflow_wrapper_fu_6443.task_compute_attn_U0.grp_do_attn_1_fu_5150.do_matmul_4_U0.adpt_sm_i_U.if_empty_n) begin
                                $display("//      Blocked by empty input FIFO 'vit_block_top_vit_block_top.grp_dataflow_wrapper_fu_6443.task_compute_attn_U0.grp_do_attn_1_fu_5150.do_matmul_4_U0.adpt_sm_i_U' written by process 'vit_block_top_vit_block_top.grp_dataflow_wrapper_fu_6443.task_compute_attn_U0.grp_do_attn_1_fu_5150.do_matmul_4_U0.matmul_step1_cache_window_4_U0'");
                                $fdisplay(fp, "Dependence_Channel_path vit_block_top_vit_block_top.grp_dataflow_wrapper_fu_6443.task_compute_attn_U0.grp_do_attn_1_fu_5150.do_matmul_4_U0.adpt_sm_i_U");
                                $fdisplay(fp, "Dependence_Channel_status EMPTY");
                            end
                            else if (~grp_dataflow_wrapper_fu_6443.task_compute_attn_U0.grp_do_attn_1_fu_5150.do_matmul_4_U0.adpt_sm_i_U.if_full_n) begin
                                $display("//      Blocked by full output FIFO 'vit_block_top_vit_block_top.grp_dataflow_wrapper_fu_6443.task_compute_attn_U0.grp_do_attn_1_fu_5150.do_matmul_4_U0.adpt_sm_i_U' read by process 'vit_block_top_vit_block_top.grp_dataflow_wrapper_fu_6443.task_compute_attn_U0.grp_do_attn_1_fu_5150.do_matmul_4_U0.matmul_step1_cache_window_4_U0'");
                                $fdisplay(fp, "Dependence_Channel_path vit_block_top_vit_block_top.grp_dataflow_wrapper_fu_6443.task_compute_attn_U0.grp_do_attn_1_fu_5150.do_matmul_4_U0.adpt_sm_i_U");
                                $fdisplay(fp, "Dependence_Channel_status FULL");
                            end
                        end
// for dep channel 'vit_block_top_vit_block_top.grp_dataflow_wrapper_fu_6443.task_compute_attn_U0.grp_do_attn_1_fu_5150.do_matmul_4_U0.start_for_matmul_step1_cache_window_4_U0_U' info is :
// blk sig is {{~vit_block_top_vit_block_top_inst.grp_dataflow_wrapper_fu_6443.task_compute_attn_U0.grp_do_attn_1_fu_5150.do_matmul_4_U0.start_for_matmul_step1_cache_window_4_U0_U.if_full_n & vit_block_top_vit_block_top_inst.grp_dataflow_wrapper_fu_6443.task_compute_attn_U0.grp_do_attn_1_fu_5150.do_matmul_4_U0.do_adapt_13_U0.ap_start & ~vit_block_top_vit_block_top_inst.grp_dataflow_wrapper_fu_6443.task_compute_attn_U0.grp_do_attn_1_fu_5150.do_matmul_4_U0.do_adapt_13_U0.real_start & (trans_in_cnt_13 == trans_out_cnt_13) & ~vit_block_top_vit_block_top_inst.grp_dataflow_wrapper_fu_6443.task_compute_attn_U0.grp_do_attn_1_fu_5150.do_matmul_4_U0.start_for_matmul_step1_cache_window_4_U0_U.if_read} start_FIFO}
                        if ((~grp_dataflow_wrapper_fu_6443.task_compute_attn_U0.grp_do_attn_1_fu_5150.do_matmul_4_U0.start_for_matmul_step1_cache_window_4_U0_U.if_full_n & grp_dataflow_wrapper_fu_6443.task_compute_attn_U0.grp_do_attn_1_fu_5150.do_matmul_4_U0.do_adapt_13_U0.ap_start & ~grp_dataflow_wrapper_fu_6443.task_compute_attn_U0.grp_do_attn_1_fu_5150.do_matmul_4_U0.do_adapt_13_U0.real_start & (trans_in_cnt_13 == trans_out_cnt_13) & ~grp_dataflow_wrapper_fu_6443.task_compute_attn_U0.grp_do_attn_1_fu_5150.do_matmul_4_U0.start_for_matmul_step1_cache_window_4_U0_U.if_read)) begin
                            $display("//      Blocked by full output start propagation FIFO 'vit_block_top_vit_block_top.grp_dataflow_wrapper_fu_6443.task_compute_attn_U0.grp_do_attn_1_fu_5150.do_matmul_4_U0.start_for_matmul_step1_cache_window_4_U0_U' read by process 'vit_block_top_vit_block_top.grp_dataflow_wrapper_fu_6443.task_compute_attn_U0.grp_do_attn_1_fu_5150.do_matmul_4_U0.matmul_step1_cache_window_4_U0',");
                        end
                    end
                    endcase
                end
                27 : begin // for proc 'vit_block_top_vit_block_top.grp_dataflow_wrapper_fu_6443.task_compute_attn_U0.grp_do_attn_1_fu_5150.do_matmul_4_U0.matmul_step1_cache_window_4_U0'
                    case(index2)
                    26: begin //  for dep proc 'vit_block_top_vit_block_top.grp_dataflow_wrapper_fu_6443.task_compute_attn_U0.grp_do_attn_1_fu_5150.do_matmul_4_U0.do_adapt_13_U0'
// for dep channel 'vit_block_top_vit_block_top.grp_dataflow_wrapper_fu_6443.task_compute_attn_U0.grp_do_attn_1_fu_5150.do_matmul_4_U0.adpt_sm_i_U' info is :
// blk sig is {~vit_block_top_vit_block_top_inst.grp_dataflow_wrapper_fu_6443.task_compute_attn_U0.grp_do_attn_1_fu_5150.do_matmul_4_U0.matmul_step1_cache_window_4_U0.adpt_sm_blk_n data_FIFO}
                        if ((~grp_dataflow_wrapper_fu_6443.task_compute_attn_U0.grp_do_attn_1_fu_5150.do_matmul_4_U0.matmul_step1_cache_window_4_U0.adpt_sm_blk_n)) begin
                            if (~grp_dataflow_wrapper_fu_6443.task_compute_attn_U0.grp_do_attn_1_fu_5150.do_matmul_4_U0.adpt_sm_i_U.if_empty_n) begin
                                $display("//      Blocked by empty input FIFO 'vit_block_top_vit_block_top.grp_dataflow_wrapper_fu_6443.task_compute_attn_U0.grp_do_attn_1_fu_5150.do_matmul_4_U0.adpt_sm_i_U' written by process 'vit_block_top_vit_block_top.grp_dataflow_wrapper_fu_6443.task_compute_attn_U0.grp_do_attn_1_fu_5150.do_matmul_4_U0.do_adapt_13_U0'");
                                $fdisplay(fp, "Dependence_Channel_path vit_block_top_vit_block_top.grp_dataflow_wrapper_fu_6443.task_compute_attn_U0.grp_do_attn_1_fu_5150.do_matmul_4_U0.adpt_sm_i_U");
                                $fdisplay(fp, "Dependence_Channel_status EMPTY");
                            end
                            else if (~grp_dataflow_wrapper_fu_6443.task_compute_attn_U0.grp_do_attn_1_fu_5150.do_matmul_4_U0.adpt_sm_i_U.if_full_n) begin
                                $display("//      Blocked by full output FIFO 'vit_block_top_vit_block_top.grp_dataflow_wrapper_fu_6443.task_compute_attn_U0.grp_do_attn_1_fu_5150.do_matmul_4_U0.adpt_sm_i_U' read by process 'vit_block_top_vit_block_top.grp_dataflow_wrapper_fu_6443.task_compute_attn_U0.grp_do_attn_1_fu_5150.do_matmul_4_U0.do_adapt_13_U0'");
                                $fdisplay(fp, "Dependence_Channel_path vit_block_top_vit_block_top.grp_dataflow_wrapper_fu_6443.task_compute_attn_U0.grp_do_attn_1_fu_5150.do_matmul_4_U0.adpt_sm_i_U");
                                $fdisplay(fp, "Dependence_Channel_status FULL");
                            end
                        end
// for dep channel 'vit_block_top_vit_block_top.grp_dataflow_wrapper_fu_6443.task_compute_attn_U0.grp_do_attn_1_fu_5150.do_matmul_4_U0.start_for_matmul_step1_cache_window_4_U0_U' info is :
// blk sig is {{~vit_block_top_vit_block_top_inst.grp_dataflow_wrapper_fu_6443.task_compute_attn_U0.grp_do_attn_1_fu_5150.do_matmul_4_U0.start_for_matmul_step1_cache_window_4_U0_U.if_empty_n & vit_block_top_vit_block_top_inst.grp_dataflow_wrapper_fu_6443.task_compute_attn_U0.grp_do_attn_1_fu_5150.do_matmul_4_U0.matmul_step1_cache_window_4_U0.ap_idle & ~vit_block_top_vit_block_top_inst.grp_dataflow_wrapper_fu_6443.task_compute_attn_U0.grp_do_attn_1_fu_5150.do_matmul_4_U0.start_for_matmul_step1_cache_window_4_U0_U.if_write} start_FIFO}
                        if ((~grp_dataflow_wrapper_fu_6443.task_compute_attn_U0.grp_do_attn_1_fu_5150.do_matmul_4_U0.start_for_matmul_step1_cache_window_4_U0_U.if_empty_n & grp_dataflow_wrapper_fu_6443.task_compute_attn_U0.grp_do_attn_1_fu_5150.do_matmul_4_U0.matmul_step1_cache_window_4_U0.ap_idle & ~grp_dataflow_wrapper_fu_6443.task_compute_attn_U0.grp_do_attn_1_fu_5150.do_matmul_4_U0.start_for_matmul_step1_cache_window_4_U0_U.if_write)) begin
                            $display("//      Blocked by missing 'ap_start' from start propagation FIFO 'vit_block_top_vit_block_top.grp_dataflow_wrapper_fu_6443.task_compute_attn_U0.grp_do_attn_1_fu_5150.do_matmul_4_U0.start_for_matmul_step1_cache_window_4_U0_U' written by process 'vit_block_top_vit_block_top.grp_dataflow_wrapper_fu_6443.task_compute_attn_U0.grp_do_attn_1_fu_5150.do_matmul_4_U0.do_adapt_13_U0',");
                        end
                    end
                    28: begin //  for dep proc 'vit_block_top_vit_block_top.grp_dataflow_wrapper_fu_6443.task_compute_attn_U0.grp_do_attn_1_fu_5150.do_matmul_4_U0.matmul_step2_mac_4_U0'
// for dep channel 'vit_block_top_vit_block_top.grp_dataflow_wrapper_fu_6443.task_compute_attn_U0.grp_do_attn_1_fu_5150.do_matmul_4_U0.cache_window_sm_i_U' info is :
// blk sig is {~vit_block_top_vit_block_top_inst.grp_dataflow_wrapper_fu_6443.task_compute_attn_U0.grp_do_attn_1_fu_5150.do_matmul_4_U0.matmul_step1_cache_window_4_U0.cache_window_sm_blk_n data_FIFO}
                        if ((~grp_dataflow_wrapper_fu_6443.task_compute_attn_U0.grp_do_attn_1_fu_5150.do_matmul_4_U0.matmul_step1_cache_window_4_U0.cache_window_sm_blk_n)) begin
                            if (~grp_dataflow_wrapper_fu_6443.task_compute_attn_U0.grp_do_attn_1_fu_5150.do_matmul_4_U0.cache_window_sm_i_U.if_empty_n) begin
                                $display("//      Blocked by empty input FIFO 'vit_block_top_vit_block_top.grp_dataflow_wrapper_fu_6443.task_compute_attn_U0.grp_do_attn_1_fu_5150.do_matmul_4_U0.cache_window_sm_i_U' written by process 'vit_block_top_vit_block_top.grp_dataflow_wrapper_fu_6443.task_compute_attn_U0.grp_do_attn_1_fu_5150.do_matmul_4_U0.matmul_step2_mac_4_U0'");
                                $fdisplay(fp, "Dependence_Channel_path vit_block_top_vit_block_top.grp_dataflow_wrapper_fu_6443.task_compute_attn_U0.grp_do_attn_1_fu_5150.do_matmul_4_U0.cache_window_sm_i_U");
                                $fdisplay(fp, "Dependence_Channel_status EMPTY");
                            end
                            else if (~grp_dataflow_wrapper_fu_6443.task_compute_attn_U0.grp_do_attn_1_fu_5150.do_matmul_4_U0.cache_window_sm_i_U.if_full_n) begin
                                $display("//      Blocked by full output FIFO 'vit_block_top_vit_block_top.grp_dataflow_wrapper_fu_6443.task_compute_attn_U0.grp_do_attn_1_fu_5150.do_matmul_4_U0.cache_window_sm_i_U' read by process 'vit_block_top_vit_block_top.grp_dataflow_wrapper_fu_6443.task_compute_attn_U0.grp_do_attn_1_fu_5150.do_matmul_4_U0.matmul_step2_mac_4_U0'");
                                $fdisplay(fp, "Dependence_Channel_path vit_block_top_vit_block_top.grp_dataflow_wrapper_fu_6443.task_compute_attn_U0.grp_do_attn_1_fu_5150.do_matmul_4_U0.cache_window_sm_i_U");
                                $fdisplay(fp, "Dependence_Channel_status FULL");
                            end
                        end
// for dep channel 'vit_block_top_vit_block_top.grp_dataflow_wrapper_fu_6443.task_compute_attn_U0.grp_do_attn_1_fu_5150.do_matmul_4_U0.start_for_matmul_step2_mac_4_U0_U' info is :
// blk sig is {{~vit_block_top_vit_block_top_inst.grp_dataflow_wrapper_fu_6443.task_compute_attn_U0.grp_do_attn_1_fu_5150.do_matmul_4_U0.start_for_matmul_step2_mac_4_U0_U.if_full_n & vit_block_top_vit_block_top_inst.grp_dataflow_wrapper_fu_6443.task_compute_attn_U0.grp_do_attn_1_fu_5150.do_matmul_4_U0.matmul_step1_cache_window_4_U0.ap_start & ~vit_block_top_vit_block_top_inst.grp_dataflow_wrapper_fu_6443.task_compute_attn_U0.grp_do_attn_1_fu_5150.do_matmul_4_U0.matmul_step1_cache_window_4_U0.real_start & (trans_in_cnt_14 == trans_out_cnt_14) & ~vit_block_top_vit_block_top_inst.grp_dataflow_wrapper_fu_6443.task_compute_attn_U0.grp_do_attn_1_fu_5150.do_matmul_4_U0.start_for_matmul_step2_mac_4_U0_U.if_read} start_FIFO}
                        if ((~grp_dataflow_wrapper_fu_6443.task_compute_attn_U0.grp_do_attn_1_fu_5150.do_matmul_4_U0.start_for_matmul_step2_mac_4_U0_U.if_full_n & grp_dataflow_wrapper_fu_6443.task_compute_attn_U0.grp_do_attn_1_fu_5150.do_matmul_4_U0.matmul_step1_cache_window_4_U0.ap_start & ~grp_dataflow_wrapper_fu_6443.task_compute_attn_U0.grp_do_attn_1_fu_5150.do_matmul_4_U0.matmul_step1_cache_window_4_U0.real_start & (trans_in_cnt_14 == trans_out_cnt_14) & ~grp_dataflow_wrapper_fu_6443.task_compute_attn_U0.grp_do_attn_1_fu_5150.do_matmul_4_U0.start_for_matmul_step2_mac_4_U0_U.if_read)) begin
                            $display("//      Blocked by full output start propagation FIFO 'vit_block_top_vit_block_top.grp_dataflow_wrapper_fu_6443.task_compute_attn_U0.grp_do_attn_1_fu_5150.do_matmul_4_U0.start_for_matmul_step2_mac_4_U0_U' read by process 'vit_block_top_vit_block_top.grp_dataflow_wrapper_fu_6443.task_compute_attn_U0.grp_do_attn_1_fu_5150.do_matmul_4_U0.matmul_step2_mac_4_U0',");
                        end
                    end
                    endcase
                end
                28 : begin // for proc 'vit_block_top_vit_block_top.grp_dataflow_wrapper_fu_6443.task_compute_attn_U0.grp_do_attn_1_fu_5150.do_matmul_4_U0.matmul_step2_mac_4_U0'
                    case(index2)
                    27: begin //  for dep proc 'vit_block_top_vit_block_top.grp_dataflow_wrapper_fu_6443.task_compute_attn_U0.grp_do_attn_1_fu_5150.do_matmul_4_U0.matmul_step1_cache_window_4_U0'
// for dep channel 'vit_block_top_vit_block_top.grp_dataflow_wrapper_fu_6443.task_compute_attn_U0.grp_do_attn_1_fu_5150.do_matmul_4_U0.cache_window_sm_i_U' info is :
// blk sig is {~vit_block_top_vit_block_top_inst.grp_dataflow_wrapper_fu_6443.task_compute_attn_U0.grp_do_attn_1_fu_5150.do_matmul_4_U0.matmul_step2_mac_4_U0.cache_window_sm_blk_n data_FIFO}
                        if ((~grp_dataflow_wrapper_fu_6443.task_compute_attn_U0.grp_do_attn_1_fu_5150.do_matmul_4_U0.matmul_step2_mac_4_U0.cache_window_sm_blk_n)) begin
                            if (~grp_dataflow_wrapper_fu_6443.task_compute_attn_U0.grp_do_attn_1_fu_5150.do_matmul_4_U0.cache_window_sm_i_U.if_empty_n) begin
                                $display("//      Blocked by empty input FIFO 'vit_block_top_vit_block_top.grp_dataflow_wrapper_fu_6443.task_compute_attn_U0.grp_do_attn_1_fu_5150.do_matmul_4_U0.cache_window_sm_i_U' written by process 'vit_block_top_vit_block_top.grp_dataflow_wrapper_fu_6443.task_compute_attn_U0.grp_do_attn_1_fu_5150.do_matmul_4_U0.matmul_step1_cache_window_4_U0'");
                                $fdisplay(fp, "Dependence_Channel_path vit_block_top_vit_block_top.grp_dataflow_wrapper_fu_6443.task_compute_attn_U0.grp_do_attn_1_fu_5150.do_matmul_4_U0.cache_window_sm_i_U");
                                $fdisplay(fp, "Dependence_Channel_status EMPTY");
                            end
                            else if (~grp_dataflow_wrapper_fu_6443.task_compute_attn_U0.grp_do_attn_1_fu_5150.do_matmul_4_U0.cache_window_sm_i_U.if_full_n) begin
                                $display("//      Blocked by full output FIFO 'vit_block_top_vit_block_top.grp_dataflow_wrapper_fu_6443.task_compute_attn_U0.grp_do_attn_1_fu_5150.do_matmul_4_U0.cache_window_sm_i_U' read by process 'vit_block_top_vit_block_top.grp_dataflow_wrapper_fu_6443.task_compute_attn_U0.grp_do_attn_1_fu_5150.do_matmul_4_U0.matmul_step1_cache_window_4_U0'");
                                $fdisplay(fp, "Dependence_Channel_path vit_block_top_vit_block_top.grp_dataflow_wrapper_fu_6443.task_compute_attn_U0.grp_do_attn_1_fu_5150.do_matmul_4_U0.cache_window_sm_i_U");
                                $fdisplay(fp, "Dependence_Channel_status FULL");
                            end
                        end
// for dep channel 'vit_block_top_vit_block_top.grp_dataflow_wrapper_fu_6443.task_compute_attn_U0.grp_do_attn_1_fu_5150.do_matmul_4_U0.start_for_matmul_step2_mac_4_U0_U' info is :
// blk sig is {{~vit_block_top_vit_block_top_inst.grp_dataflow_wrapper_fu_6443.task_compute_attn_U0.grp_do_attn_1_fu_5150.do_matmul_4_U0.start_for_matmul_step2_mac_4_U0_U.if_empty_n & vit_block_top_vit_block_top_inst.grp_dataflow_wrapper_fu_6443.task_compute_attn_U0.grp_do_attn_1_fu_5150.do_matmul_4_U0.matmul_step2_mac_4_U0.ap_idle & ~vit_block_top_vit_block_top_inst.grp_dataflow_wrapper_fu_6443.task_compute_attn_U0.grp_do_attn_1_fu_5150.do_matmul_4_U0.start_for_matmul_step2_mac_4_U0_U.if_write} start_FIFO}
                        if ((~grp_dataflow_wrapper_fu_6443.task_compute_attn_U0.grp_do_attn_1_fu_5150.do_matmul_4_U0.start_for_matmul_step2_mac_4_U0_U.if_empty_n & grp_dataflow_wrapper_fu_6443.task_compute_attn_U0.grp_do_attn_1_fu_5150.do_matmul_4_U0.matmul_step2_mac_4_U0.ap_idle & ~grp_dataflow_wrapper_fu_6443.task_compute_attn_U0.grp_do_attn_1_fu_5150.do_matmul_4_U0.start_for_matmul_step2_mac_4_U0_U.if_write)) begin
                            $display("//      Blocked by missing 'ap_start' from start propagation FIFO 'vit_block_top_vit_block_top.grp_dataflow_wrapper_fu_6443.task_compute_attn_U0.grp_do_attn_1_fu_5150.do_matmul_4_U0.start_for_matmul_step2_mac_4_U0_U' written by process 'vit_block_top_vit_block_top.grp_dataflow_wrapper_fu_6443.task_compute_attn_U0.grp_do_attn_1_fu_5150.do_matmul_4_U0.matmul_step1_cache_window_4_U0',");
                        end
                    end
                    29: begin //  for dep proc 'vit_block_top_vit_block_top.grp_dataflow_wrapper_fu_6443.task_compute_attn_U0.grp_do_attn_1_fu_5150.do_matmul_4_U0.do_adapt_13_1_U0'
// for dep channel 'vit_block_top_vit_block_top.grp_dataflow_wrapper_fu_6443.task_compute_attn_U0.grp_do_attn_1_fu_5150.do_matmul_4_U0.mac_sm_i_U' info is :
// blk sig is {~vit_block_top_vit_block_top_inst.grp_dataflow_wrapper_fu_6443.task_compute_attn_U0.grp_do_attn_1_fu_5150.do_matmul_4_U0.matmul_step2_mac_4_U0.mac_sm_blk_n data_FIFO}
                        if ((~grp_dataflow_wrapper_fu_6443.task_compute_attn_U0.grp_do_attn_1_fu_5150.do_matmul_4_U0.matmul_step2_mac_4_U0.mac_sm_blk_n)) begin
                            if (~grp_dataflow_wrapper_fu_6443.task_compute_attn_U0.grp_do_attn_1_fu_5150.do_matmul_4_U0.mac_sm_i_U.if_empty_n) begin
                                $display("//      Blocked by empty input FIFO 'vit_block_top_vit_block_top.grp_dataflow_wrapper_fu_6443.task_compute_attn_U0.grp_do_attn_1_fu_5150.do_matmul_4_U0.mac_sm_i_U' written by process 'vit_block_top_vit_block_top.grp_dataflow_wrapper_fu_6443.task_compute_attn_U0.grp_do_attn_1_fu_5150.do_matmul_4_U0.do_adapt_13_1_U0'");
                                $fdisplay(fp, "Dependence_Channel_path vit_block_top_vit_block_top.grp_dataflow_wrapper_fu_6443.task_compute_attn_U0.grp_do_attn_1_fu_5150.do_matmul_4_U0.mac_sm_i_U");
                                $fdisplay(fp, "Dependence_Channel_status EMPTY");
                            end
                            else if (~grp_dataflow_wrapper_fu_6443.task_compute_attn_U0.grp_do_attn_1_fu_5150.do_matmul_4_U0.mac_sm_i_U.if_full_n) begin
                                $display("//      Blocked by full output FIFO 'vit_block_top_vit_block_top.grp_dataflow_wrapper_fu_6443.task_compute_attn_U0.grp_do_attn_1_fu_5150.do_matmul_4_U0.mac_sm_i_U' read by process 'vit_block_top_vit_block_top.grp_dataflow_wrapper_fu_6443.task_compute_attn_U0.grp_do_attn_1_fu_5150.do_matmul_4_U0.do_adapt_13_1_U0'");
                                $fdisplay(fp, "Dependence_Channel_path vit_block_top_vit_block_top.grp_dataflow_wrapper_fu_6443.task_compute_attn_U0.grp_do_attn_1_fu_5150.do_matmul_4_U0.mac_sm_i_U");
                                $fdisplay(fp, "Dependence_Channel_status FULL");
                            end
                        end
// for dep channel 'vit_block_top_vit_block_top.grp_dataflow_wrapper_fu_6443.task_compute_attn_U0.grp_do_attn_1_fu_5150.do_matmul_4_U0.start_for_do_adapt_13_1_U0_U' info is :
// blk sig is {{~vit_block_top_vit_block_top_inst.grp_dataflow_wrapper_fu_6443.task_compute_attn_U0.grp_do_attn_1_fu_5150.do_matmul_4_U0.start_for_do_adapt_13_1_U0_U.if_full_n & vit_block_top_vit_block_top_inst.grp_dataflow_wrapper_fu_6443.task_compute_attn_U0.grp_do_attn_1_fu_5150.do_matmul_4_U0.matmul_step2_mac_4_U0.ap_start & ~vit_block_top_vit_block_top_inst.grp_dataflow_wrapper_fu_6443.task_compute_attn_U0.grp_do_attn_1_fu_5150.do_matmul_4_U0.matmul_step2_mac_4_U0.real_start & (trans_in_cnt_15 == trans_out_cnt_15) & ~vit_block_top_vit_block_top_inst.grp_dataflow_wrapper_fu_6443.task_compute_attn_U0.grp_do_attn_1_fu_5150.do_matmul_4_U0.start_for_do_adapt_13_1_U0_U.if_read} start_FIFO}
                        if ((~grp_dataflow_wrapper_fu_6443.task_compute_attn_U0.grp_do_attn_1_fu_5150.do_matmul_4_U0.start_for_do_adapt_13_1_U0_U.if_full_n & grp_dataflow_wrapper_fu_6443.task_compute_attn_U0.grp_do_attn_1_fu_5150.do_matmul_4_U0.matmul_step2_mac_4_U0.ap_start & ~grp_dataflow_wrapper_fu_6443.task_compute_attn_U0.grp_do_attn_1_fu_5150.do_matmul_4_U0.matmul_step2_mac_4_U0.real_start & (trans_in_cnt_15 == trans_out_cnt_15) & ~grp_dataflow_wrapper_fu_6443.task_compute_attn_U0.grp_do_attn_1_fu_5150.do_matmul_4_U0.start_for_do_adapt_13_1_U0_U.if_read)) begin
                            $display("//      Blocked by full output start propagation FIFO 'vit_block_top_vit_block_top.grp_dataflow_wrapper_fu_6443.task_compute_attn_U0.grp_do_attn_1_fu_5150.do_matmul_4_U0.start_for_do_adapt_13_1_U0_U' read by process 'vit_block_top_vit_block_top.grp_dataflow_wrapper_fu_6443.task_compute_attn_U0.grp_do_attn_1_fu_5150.do_matmul_4_U0.do_adapt_13_1_U0',");
                        end
                    end
                    endcase
                end
                29 : begin // for proc 'vit_block_top_vit_block_top.grp_dataflow_wrapper_fu_6443.task_compute_attn_U0.grp_do_attn_1_fu_5150.do_matmul_4_U0.do_adapt_13_1_U0'
                    case(index2)
                    28: begin //  for dep proc 'vit_block_top_vit_block_top.grp_dataflow_wrapper_fu_6443.task_compute_attn_U0.grp_do_attn_1_fu_5150.do_matmul_4_U0.matmul_step2_mac_4_U0'
// for dep channel 'vit_block_top_vit_block_top.grp_dataflow_wrapper_fu_6443.task_compute_attn_U0.grp_do_attn_1_fu_5150.do_matmul_4_U0.mac_sm_i_U' info is :
// blk sig is {~vit_block_top_vit_block_top_inst.grp_dataflow_wrapper_fu_6443.task_compute_attn_U0.grp_do_attn_1_fu_5150.do_matmul_4_U0.do_adapt_13_1_U0.mac_sm_blk_n data_FIFO}
                        if ((~grp_dataflow_wrapper_fu_6443.task_compute_attn_U0.grp_do_attn_1_fu_5150.do_matmul_4_U0.do_adapt_13_1_U0.mac_sm_blk_n)) begin
                            if (~grp_dataflow_wrapper_fu_6443.task_compute_attn_U0.grp_do_attn_1_fu_5150.do_matmul_4_U0.mac_sm_i_U.if_empty_n) begin
                                $display("//      Blocked by empty input FIFO 'vit_block_top_vit_block_top.grp_dataflow_wrapper_fu_6443.task_compute_attn_U0.grp_do_attn_1_fu_5150.do_matmul_4_U0.mac_sm_i_U' written by process 'vit_block_top_vit_block_top.grp_dataflow_wrapper_fu_6443.task_compute_attn_U0.grp_do_attn_1_fu_5150.do_matmul_4_U0.matmul_step2_mac_4_U0'");
                                $fdisplay(fp, "Dependence_Channel_path vit_block_top_vit_block_top.grp_dataflow_wrapper_fu_6443.task_compute_attn_U0.grp_do_attn_1_fu_5150.do_matmul_4_U0.mac_sm_i_U");
                                $fdisplay(fp, "Dependence_Channel_status EMPTY");
                            end
                            else if (~grp_dataflow_wrapper_fu_6443.task_compute_attn_U0.grp_do_attn_1_fu_5150.do_matmul_4_U0.mac_sm_i_U.if_full_n) begin
                                $display("//      Blocked by full output FIFO 'vit_block_top_vit_block_top.grp_dataflow_wrapper_fu_6443.task_compute_attn_U0.grp_do_attn_1_fu_5150.do_matmul_4_U0.mac_sm_i_U' read by process 'vit_block_top_vit_block_top.grp_dataflow_wrapper_fu_6443.task_compute_attn_U0.grp_do_attn_1_fu_5150.do_matmul_4_U0.matmul_step2_mac_4_U0'");
                                $fdisplay(fp, "Dependence_Channel_path vit_block_top_vit_block_top.grp_dataflow_wrapper_fu_6443.task_compute_attn_U0.grp_do_attn_1_fu_5150.do_matmul_4_U0.mac_sm_i_U");
                                $fdisplay(fp, "Dependence_Channel_status FULL");
                            end
                        end
// for dep channel 'vit_block_top_vit_block_top.grp_dataflow_wrapper_fu_6443.task_compute_attn_U0.grp_do_attn_1_fu_5150.do_matmul_4_U0.start_for_do_adapt_13_1_U0_U' info is :
// blk sig is {{~vit_block_top_vit_block_top_inst.grp_dataflow_wrapper_fu_6443.task_compute_attn_U0.grp_do_attn_1_fu_5150.do_matmul_4_U0.start_for_do_adapt_13_1_U0_U.if_empty_n & vit_block_top_vit_block_top_inst.grp_dataflow_wrapper_fu_6443.task_compute_attn_U0.grp_do_attn_1_fu_5150.do_matmul_4_U0.do_adapt_13_1_U0.ap_idle & ~vit_block_top_vit_block_top_inst.grp_dataflow_wrapper_fu_6443.task_compute_attn_U0.grp_do_attn_1_fu_5150.do_matmul_4_U0.start_for_do_adapt_13_1_U0_U.if_write} start_FIFO}
                        if ((~grp_dataflow_wrapper_fu_6443.task_compute_attn_U0.grp_do_attn_1_fu_5150.do_matmul_4_U0.start_for_do_adapt_13_1_U0_U.if_empty_n & grp_dataflow_wrapper_fu_6443.task_compute_attn_U0.grp_do_attn_1_fu_5150.do_matmul_4_U0.do_adapt_13_1_U0.ap_idle & ~grp_dataflow_wrapper_fu_6443.task_compute_attn_U0.grp_do_attn_1_fu_5150.do_matmul_4_U0.start_for_do_adapt_13_1_U0_U.if_write)) begin
                            $display("//      Blocked by missing 'ap_start' from start propagation FIFO 'vit_block_top_vit_block_top.grp_dataflow_wrapper_fu_6443.task_compute_attn_U0.grp_do_attn_1_fu_5150.do_matmul_4_U0.start_for_do_adapt_13_1_U0_U' written by process 'vit_block_top_vit_block_top.grp_dataflow_wrapper_fu_6443.task_compute_attn_U0.grp_do_attn_1_fu_5150.do_matmul_4_U0.matmul_step2_mac_4_U0',");
                        end
                    end
                    32: begin //  for dep proc 'vit_block_top_vit_block_top.grp_dataflow_wrapper_fu_6443.task_compute_attn_U0.grp_do_attn_1_fu_5150.do_quant_1_U0'
// for dep channel 'vit_block_top_vit_block_top.grp_dataflow_wrapper_fu_6443.task_compute_attn_U0.grp_do_attn_1_fu_5150.v_sm_i_U' info is :
// blk sig is {~vit_block_top_vit_block_top_inst.grp_dataflow_wrapper_fu_6443.task_compute_attn_U0.grp_do_attn_1_fu_5150.do_matmul_4_U0.do_adapt_13_1_U0.v_sm_blk_n data_FIFO}
                        if ((~grp_dataflow_wrapper_fu_6443.task_compute_attn_U0.grp_do_attn_1_fu_5150.do_matmul_4_U0.do_adapt_13_1_U0.v_sm_blk_n)) begin
                            if (~grp_dataflow_wrapper_fu_6443.task_compute_attn_U0.grp_do_attn_1_fu_5150.v_sm_i_U.if_empty_n) begin
                                $display("//      Blocked by empty input FIFO 'vit_block_top_vit_block_top.grp_dataflow_wrapper_fu_6443.task_compute_attn_U0.grp_do_attn_1_fu_5150.v_sm_i_U' written by process 'vit_block_top_vit_block_top.grp_dataflow_wrapper_fu_6443.task_compute_attn_U0.grp_do_attn_1_fu_5150.do_quant_1_U0'");
                                $fdisplay(fp, "Dependence_Channel_path vit_block_top_vit_block_top.grp_dataflow_wrapper_fu_6443.task_compute_attn_U0.grp_do_attn_1_fu_5150.v_sm_i_U");
                                $fdisplay(fp, "Dependence_Channel_status EMPTY");
                            end
                            else if (~grp_dataflow_wrapper_fu_6443.task_compute_attn_U0.grp_do_attn_1_fu_5150.v_sm_i_U.if_full_n) begin
                                $display("//      Blocked by full output FIFO 'vit_block_top_vit_block_top.grp_dataflow_wrapper_fu_6443.task_compute_attn_U0.grp_do_attn_1_fu_5150.v_sm_i_U' read by process 'vit_block_top_vit_block_top.grp_dataflow_wrapper_fu_6443.task_compute_attn_U0.grp_do_attn_1_fu_5150.do_quant_1_U0'");
                                $fdisplay(fp, "Dependence_Channel_path vit_block_top_vit_block_top.grp_dataflow_wrapper_fu_6443.task_compute_attn_U0.grp_do_attn_1_fu_5150.v_sm_i_U");
                                $fdisplay(fp, "Dependence_Channel_status FULL");
                            end
                        end
                    end
                    endcase
                end
                30 : begin // for proc 'vit_block_top_vit_block_top.grp_dataflow_wrapper_fu_6443.task_compute_attn_U0.grp_do_attn_1_fu_5150.do_quant_U0'
                    case(index2)
                    15: begin //  for dep proc 'vit_block_top_vit_block_top.grp_dataflow_wrapper_fu_6443.task_compute_attn_U0.grp_do_attn_1_fu_5150.do_matmul_2_U0'
// for dep channel 'vit_block_top_vit_block_top.grp_dataflow_wrapper_fu_6443.task_compute_attn_U0.grp_do_attn_1_fu_5150.q_sm_i_U' info is :
// blk sig is {~vit_block_top_vit_block_top_inst.grp_dataflow_wrapper_fu_6443.task_compute_attn_U0.grp_do_attn_1_fu_5150.do_quant_U0.grp_do_quant_Pipeline_TT_LOOP_CT_LOOP_fu_82.q_sm_blk_n data_FIFO}
                        if ((~grp_dataflow_wrapper_fu_6443.task_compute_attn_U0.grp_do_attn_1_fu_5150.do_quant_U0.grp_do_quant_Pipeline_TT_LOOP_CT_LOOP_fu_82.q_sm_blk_n)) begin
                            if (~grp_dataflow_wrapper_fu_6443.task_compute_attn_U0.grp_do_attn_1_fu_5150.q_sm_i_U.if_empty_n) begin
                                $display("//      Blocked by empty input FIFO 'vit_block_top_vit_block_top.grp_dataflow_wrapper_fu_6443.task_compute_attn_U0.grp_do_attn_1_fu_5150.q_sm_i_U' written by process 'vit_block_top_vit_block_top.grp_dataflow_wrapper_fu_6443.task_compute_attn_U0.grp_do_attn_1_fu_5150.do_matmul_2_U0'");
                                $fdisplay(fp, "Dependence_Channel_path vit_block_top_vit_block_top.grp_dataflow_wrapper_fu_6443.task_compute_attn_U0.grp_do_attn_1_fu_5150.q_sm_i_U");
                                $fdisplay(fp, "Dependence_Channel_status EMPTY");
                            end
                            else if (~grp_dataflow_wrapper_fu_6443.task_compute_attn_U0.grp_do_attn_1_fu_5150.q_sm_i_U.if_full_n) begin
                                $display("//      Blocked by full output FIFO 'vit_block_top_vit_block_top.grp_dataflow_wrapper_fu_6443.task_compute_attn_U0.grp_do_attn_1_fu_5150.q_sm_i_U' read by process 'vit_block_top_vit_block_top.grp_dataflow_wrapper_fu_6443.task_compute_attn_U0.grp_do_attn_1_fu_5150.do_matmul_2_U0'");
                                $fdisplay(fp, "Dependence_Channel_path vit_block_top_vit_block_top.grp_dataflow_wrapper_fu_6443.task_compute_attn_U0.grp_do_attn_1_fu_5150.q_sm_i_U");
                                $fdisplay(fp, "Dependence_Channel_status FULL");
                            end
                        end
// for dep channel 'vit_block_top_vit_block_top.grp_dataflow_wrapper_fu_6443.task_compute_attn_U0.grp_do_attn_1_fu_5150.start_for_do_quant_U0_U' info is :
// blk sig is {{~vit_block_top_vit_block_top_inst.grp_dataflow_wrapper_fu_6443.task_compute_attn_U0.grp_do_attn_1_fu_5150.start_for_do_quant_U0_U.if_empty_n & vit_block_top_vit_block_top_inst.grp_dataflow_wrapper_fu_6443.task_compute_attn_U0.grp_do_attn_1_fu_5150.do_quant_U0.ap_idle & ~vit_block_top_vit_block_top_inst.grp_dataflow_wrapper_fu_6443.task_compute_attn_U0.grp_do_attn_1_fu_5150.start_for_do_quant_U0_U.if_write} start_FIFO}
                        if ((~grp_dataflow_wrapper_fu_6443.task_compute_attn_U0.grp_do_attn_1_fu_5150.start_for_do_quant_U0_U.if_empty_n & grp_dataflow_wrapper_fu_6443.task_compute_attn_U0.grp_do_attn_1_fu_5150.do_quant_U0.ap_idle & ~grp_dataflow_wrapper_fu_6443.task_compute_attn_U0.grp_do_attn_1_fu_5150.start_for_do_quant_U0_U.if_write)) begin
                            $display("//      Blocked by missing 'ap_start' from start propagation FIFO 'vit_block_top_vit_block_top.grp_dataflow_wrapper_fu_6443.task_compute_attn_U0.grp_do_attn_1_fu_5150.start_for_do_quant_U0_U' written by process 'vit_block_top_vit_block_top.grp_dataflow_wrapper_fu_6443.task_compute_attn_U0.grp_do_attn_1_fu_5150.do_matmul_2_U0',");
                        end
                    end
                    19: begin //  for dep proc 'vit_block_top_vit_block_top.grp_dataflow_wrapper_fu_6443.task_compute_attn_U0.grp_do_attn_1_fu_5150.do_matmul_2_U0.do_adapt_11_U0'
// for dep channel 'vit_block_top_vit_block_top.grp_dataflow_wrapper_fu_6443.task_compute_attn_U0.grp_do_attn_1_fu_5150.q_sm_i_U' info is :
// blk sig is {~vit_block_top_vit_block_top_inst.grp_dataflow_wrapper_fu_6443.task_compute_attn_U0.grp_do_attn_1_fu_5150.do_quant_U0.grp_do_quant_Pipeline_TT_LOOP_CT_LOOP_fu_82.q_sm_blk_n data_FIFO}
                        if ((~grp_dataflow_wrapper_fu_6443.task_compute_attn_U0.grp_do_attn_1_fu_5150.do_quant_U0.grp_do_quant_Pipeline_TT_LOOP_CT_LOOP_fu_82.q_sm_blk_n)) begin
                            if (~grp_dataflow_wrapper_fu_6443.task_compute_attn_U0.grp_do_attn_1_fu_5150.q_sm_i_U.if_empty_n) begin
                                $display("//      Blocked by empty input FIFO 'vit_block_top_vit_block_top.grp_dataflow_wrapper_fu_6443.task_compute_attn_U0.grp_do_attn_1_fu_5150.q_sm_i_U' written by process 'vit_block_top_vit_block_top.grp_dataflow_wrapper_fu_6443.task_compute_attn_U0.grp_do_attn_1_fu_5150.do_matmul_2_U0.do_adapt_11_U0'");
                                $fdisplay(fp, "Dependence_Channel_path vit_block_top_vit_block_top.grp_dataflow_wrapper_fu_6443.task_compute_attn_U0.grp_do_attn_1_fu_5150.q_sm_i_U");
                                $fdisplay(fp, "Dependence_Channel_status EMPTY");
                            end
                            else if (~grp_dataflow_wrapper_fu_6443.task_compute_attn_U0.grp_do_attn_1_fu_5150.q_sm_i_U.if_full_n) begin
                                $display("//      Blocked by full output FIFO 'vit_block_top_vit_block_top.grp_dataflow_wrapper_fu_6443.task_compute_attn_U0.grp_do_attn_1_fu_5150.q_sm_i_U' read by process 'vit_block_top_vit_block_top.grp_dataflow_wrapper_fu_6443.task_compute_attn_U0.grp_do_attn_1_fu_5150.do_matmul_2_U0.do_adapt_11_U0'");
                                $fdisplay(fp, "Dependence_Channel_path vit_block_top_vit_block_top.grp_dataflow_wrapper_fu_6443.task_compute_attn_U0.grp_do_attn_1_fu_5150.q_sm_i_U");
                                $fdisplay(fp, "Dependence_Channel_status FULL");
                            end
                        end
                    end
                    33: begin //  for dep proc 'vit_block_top_vit_block_top.grp_dataflow_wrapper_fu_6443.task_compute_attn_U0.grp_do_attn_1_fu_5150.do_split_4_U0'
// for dep channel 'vit_block_top_vit_block_top.grp_dataflow_wrapper_fu_6443.task_compute_attn_U0.grp_do_attn_1_fu_5150.qq_sm_i_U' info is :
// blk sig is {~vit_block_top_vit_block_top_inst.grp_dataflow_wrapper_fu_6443.task_compute_attn_U0.grp_do_attn_1_fu_5150.do_quant_U0.grp_do_quant_Pipeline_TT_LOOP_CT_LOOP_fu_82.qq_sm_blk_n data_FIFO}
                        if ((~grp_dataflow_wrapper_fu_6443.task_compute_attn_U0.grp_do_attn_1_fu_5150.do_quant_U0.grp_do_quant_Pipeline_TT_LOOP_CT_LOOP_fu_82.qq_sm_blk_n)) begin
                            if (~grp_dataflow_wrapper_fu_6443.task_compute_attn_U0.grp_do_attn_1_fu_5150.qq_sm_i_U.if_empty_n) begin
                                $display("//      Blocked by empty input FIFO 'vit_block_top_vit_block_top.grp_dataflow_wrapper_fu_6443.task_compute_attn_U0.grp_do_attn_1_fu_5150.qq_sm_i_U' written by process 'vit_block_top_vit_block_top.grp_dataflow_wrapper_fu_6443.task_compute_attn_U0.grp_do_attn_1_fu_5150.do_split_4_U0'");
                                $fdisplay(fp, "Dependence_Channel_path vit_block_top_vit_block_top.grp_dataflow_wrapper_fu_6443.task_compute_attn_U0.grp_do_attn_1_fu_5150.qq_sm_i_U");
                                $fdisplay(fp, "Dependence_Channel_status EMPTY");
                            end
                            else if (~grp_dataflow_wrapper_fu_6443.task_compute_attn_U0.grp_do_attn_1_fu_5150.qq_sm_i_U.if_full_n) begin
                                $display("//      Blocked by full output FIFO 'vit_block_top_vit_block_top.grp_dataflow_wrapper_fu_6443.task_compute_attn_U0.grp_do_attn_1_fu_5150.qq_sm_i_U' read by process 'vit_block_top_vit_block_top.grp_dataflow_wrapper_fu_6443.task_compute_attn_U0.grp_do_attn_1_fu_5150.do_split_4_U0'");
                                $fdisplay(fp, "Dependence_Channel_path vit_block_top_vit_block_top.grp_dataflow_wrapper_fu_6443.task_compute_attn_U0.grp_do_attn_1_fu_5150.qq_sm_i_U");
                                $fdisplay(fp, "Dependence_Channel_status FULL");
                            end
                        end
// for dep channel 'vit_block_top_vit_block_top.grp_dataflow_wrapper_fu_6443.task_compute_attn_U0.grp_do_attn_1_fu_5150.start_for_do_split_4_U0_U' info is :
// blk sig is {{~vit_block_top_vit_block_top_inst.grp_dataflow_wrapper_fu_6443.task_compute_attn_U0.grp_do_attn_1_fu_5150.start_for_do_split_4_U0_U.if_full_n & vit_block_top_vit_block_top_inst.grp_dataflow_wrapper_fu_6443.task_compute_attn_U0.grp_do_attn_1_fu_5150.do_quant_U0.ap_start & ~vit_block_top_vit_block_top_inst.grp_dataflow_wrapper_fu_6443.task_compute_attn_U0.grp_do_attn_1_fu_5150.do_quant_U0.real_start & (trans_in_cnt_19 == trans_out_cnt_19) & ~vit_block_top_vit_block_top_inst.grp_dataflow_wrapper_fu_6443.task_compute_attn_U0.grp_do_attn_1_fu_5150.start_for_do_split_4_U0_U.if_read} start_FIFO}
                        if ((~grp_dataflow_wrapper_fu_6443.task_compute_attn_U0.grp_do_attn_1_fu_5150.start_for_do_split_4_U0_U.if_full_n & grp_dataflow_wrapper_fu_6443.task_compute_attn_U0.grp_do_attn_1_fu_5150.do_quant_U0.ap_start & ~grp_dataflow_wrapper_fu_6443.task_compute_attn_U0.grp_do_attn_1_fu_5150.do_quant_U0.real_start & (trans_in_cnt_19 == trans_out_cnt_19) & ~grp_dataflow_wrapper_fu_6443.task_compute_attn_U0.grp_do_attn_1_fu_5150.start_for_do_split_4_U0_U.if_read)) begin
                            $display("//      Blocked by full output start propagation FIFO 'vit_block_top_vit_block_top.grp_dataflow_wrapper_fu_6443.task_compute_attn_U0.grp_do_attn_1_fu_5150.start_for_do_split_4_U0_U' read by process 'vit_block_top_vit_block_top.grp_dataflow_wrapper_fu_6443.task_compute_attn_U0.grp_do_attn_1_fu_5150.do_split_4_U0',");
                        end
                    end
                    endcase
                end
                31 : begin // for proc 'vit_block_top_vit_block_top.grp_dataflow_wrapper_fu_6443.task_compute_attn_U0.grp_do_attn_1_fu_5150.do_quant_3_U0'
                    case(index2)
                    20: begin //  for dep proc 'vit_block_top_vit_block_top.grp_dataflow_wrapper_fu_6443.task_compute_attn_U0.grp_do_attn_1_fu_5150.do_matmul_2_1_U0'
// for dep channel 'vit_block_top_vit_block_top.grp_dataflow_wrapper_fu_6443.task_compute_attn_U0.grp_do_attn_1_fu_5150.k_sm_i_U' info is :
// blk sig is {~vit_block_top_vit_block_top_inst.grp_dataflow_wrapper_fu_6443.task_compute_attn_U0.grp_do_attn_1_fu_5150.do_quant_3_U0.grp_do_quant_3_Pipeline_TT_LOOP_CT_LOOP_fu_82.k_sm_blk_n data_FIFO}
                        if ((~grp_dataflow_wrapper_fu_6443.task_compute_attn_U0.grp_do_attn_1_fu_5150.do_quant_3_U0.grp_do_quant_3_Pipeline_TT_LOOP_CT_LOOP_fu_82.k_sm_blk_n)) begin
                            if (~grp_dataflow_wrapper_fu_6443.task_compute_attn_U0.grp_do_attn_1_fu_5150.k_sm_i_U.if_empty_n) begin
                                $display("//      Blocked by empty input FIFO 'vit_block_top_vit_block_top.grp_dataflow_wrapper_fu_6443.task_compute_attn_U0.grp_do_attn_1_fu_5150.k_sm_i_U' written by process 'vit_block_top_vit_block_top.grp_dataflow_wrapper_fu_6443.task_compute_attn_U0.grp_do_attn_1_fu_5150.do_matmul_2_1_U0'");
                                $fdisplay(fp, "Dependence_Channel_path vit_block_top_vit_block_top.grp_dataflow_wrapper_fu_6443.task_compute_attn_U0.grp_do_attn_1_fu_5150.k_sm_i_U");
                                $fdisplay(fp, "Dependence_Channel_status EMPTY");
                            end
                            else if (~grp_dataflow_wrapper_fu_6443.task_compute_attn_U0.grp_do_attn_1_fu_5150.k_sm_i_U.if_full_n) begin
                                $display("//      Blocked by full output FIFO 'vit_block_top_vit_block_top.grp_dataflow_wrapper_fu_6443.task_compute_attn_U0.grp_do_attn_1_fu_5150.k_sm_i_U' read by process 'vit_block_top_vit_block_top.grp_dataflow_wrapper_fu_6443.task_compute_attn_U0.grp_do_attn_1_fu_5150.do_matmul_2_1_U0'");
                                $fdisplay(fp, "Dependence_Channel_path vit_block_top_vit_block_top.grp_dataflow_wrapper_fu_6443.task_compute_attn_U0.grp_do_attn_1_fu_5150.k_sm_i_U");
                                $fdisplay(fp, "Dependence_Channel_status FULL");
                            end
                        end
// for dep channel 'vit_block_top_vit_block_top.grp_dataflow_wrapper_fu_6443.task_compute_attn_U0.grp_do_attn_1_fu_5150.start_for_do_quant_3_U0_U' info is :
// blk sig is {{~vit_block_top_vit_block_top_inst.grp_dataflow_wrapper_fu_6443.task_compute_attn_U0.grp_do_attn_1_fu_5150.start_for_do_quant_3_U0_U.if_empty_n & vit_block_top_vit_block_top_inst.grp_dataflow_wrapper_fu_6443.task_compute_attn_U0.grp_do_attn_1_fu_5150.do_quant_3_U0.ap_idle & ~vit_block_top_vit_block_top_inst.grp_dataflow_wrapper_fu_6443.task_compute_attn_U0.grp_do_attn_1_fu_5150.start_for_do_quant_3_U0_U.if_write} start_FIFO}
                        if ((~grp_dataflow_wrapper_fu_6443.task_compute_attn_U0.grp_do_attn_1_fu_5150.start_for_do_quant_3_U0_U.if_empty_n & grp_dataflow_wrapper_fu_6443.task_compute_attn_U0.grp_do_attn_1_fu_5150.do_quant_3_U0.ap_idle & ~grp_dataflow_wrapper_fu_6443.task_compute_attn_U0.grp_do_attn_1_fu_5150.start_for_do_quant_3_U0_U.if_write)) begin
                            $display("//      Blocked by missing 'ap_start' from start propagation FIFO 'vit_block_top_vit_block_top.grp_dataflow_wrapper_fu_6443.task_compute_attn_U0.grp_do_attn_1_fu_5150.start_for_do_quant_3_U0_U' written by process 'vit_block_top_vit_block_top.grp_dataflow_wrapper_fu_6443.task_compute_attn_U0.grp_do_attn_1_fu_5150.do_matmul_2_1_U0',");
                        end
                    end
                    24: begin //  for dep proc 'vit_block_top_vit_block_top.grp_dataflow_wrapper_fu_6443.task_compute_attn_U0.grp_do_attn_1_fu_5150.do_matmul_2_1_U0.do_adapt_12_1_U0'
// for dep channel 'vit_block_top_vit_block_top.grp_dataflow_wrapper_fu_6443.task_compute_attn_U0.grp_do_attn_1_fu_5150.k_sm_i_U' info is :
// blk sig is {~vit_block_top_vit_block_top_inst.grp_dataflow_wrapper_fu_6443.task_compute_attn_U0.grp_do_attn_1_fu_5150.do_quant_3_U0.grp_do_quant_3_Pipeline_TT_LOOP_CT_LOOP_fu_82.k_sm_blk_n data_FIFO}
                        if ((~grp_dataflow_wrapper_fu_6443.task_compute_attn_U0.grp_do_attn_1_fu_5150.do_quant_3_U0.grp_do_quant_3_Pipeline_TT_LOOP_CT_LOOP_fu_82.k_sm_blk_n)) begin
                            if (~grp_dataflow_wrapper_fu_6443.task_compute_attn_U0.grp_do_attn_1_fu_5150.k_sm_i_U.if_empty_n) begin
                                $display("//      Blocked by empty input FIFO 'vit_block_top_vit_block_top.grp_dataflow_wrapper_fu_6443.task_compute_attn_U0.grp_do_attn_1_fu_5150.k_sm_i_U' written by process 'vit_block_top_vit_block_top.grp_dataflow_wrapper_fu_6443.task_compute_attn_U0.grp_do_attn_1_fu_5150.do_matmul_2_1_U0.do_adapt_12_1_U0'");
                                $fdisplay(fp, "Dependence_Channel_path vit_block_top_vit_block_top.grp_dataflow_wrapper_fu_6443.task_compute_attn_U0.grp_do_attn_1_fu_5150.k_sm_i_U");
                                $fdisplay(fp, "Dependence_Channel_status EMPTY");
                            end
                            else if (~grp_dataflow_wrapper_fu_6443.task_compute_attn_U0.grp_do_attn_1_fu_5150.k_sm_i_U.if_full_n) begin
                                $display("//      Blocked by full output FIFO 'vit_block_top_vit_block_top.grp_dataflow_wrapper_fu_6443.task_compute_attn_U0.grp_do_attn_1_fu_5150.k_sm_i_U' read by process 'vit_block_top_vit_block_top.grp_dataflow_wrapper_fu_6443.task_compute_attn_U0.grp_do_attn_1_fu_5150.do_matmul_2_1_U0.do_adapt_12_1_U0'");
                                $fdisplay(fp, "Dependence_Channel_path vit_block_top_vit_block_top.grp_dataflow_wrapper_fu_6443.task_compute_attn_U0.grp_do_attn_1_fu_5150.k_sm_i_U");
                                $fdisplay(fp, "Dependence_Channel_status FULL");
                            end
                        end
                    end
                    34: begin //  for dep proc 'vit_block_top_vit_block_top.grp_dataflow_wrapper_fu_6443.task_compute_attn_U0.grp_do_attn_1_fu_5150.do_split_5_U0'
// for dep channel 'vit_block_top_vit_block_top.grp_dataflow_wrapper_fu_6443.task_compute_attn_U0.grp_do_attn_1_fu_5150.kq_sm_i_U' info is :
// blk sig is {~vit_block_top_vit_block_top_inst.grp_dataflow_wrapper_fu_6443.task_compute_attn_U0.grp_do_attn_1_fu_5150.do_quant_3_U0.grp_do_quant_3_Pipeline_TT_LOOP_CT_LOOP_fu_82.kq_sm_blk_n data_FIFO}
                        if ((~grp_dataflow_wrapper_fu_6443.task_compute_attn_U0.grp_do_attn_1_fu_5150.do_quant_3_U0.grp_do_quant_3_Pipeline_TT_LOOP_CT_LOOP_fu_82.kq_sm_blk_n)) begin
                            if (~grp_dataflow_wrapper_fu_6443.task_compute_attn_U0.grp_do_attn_1_fu_5150.kq_sm_i_U.if_empty_n) begin
                                $display("//      Blocked by empty input FIFO 'vit_block_top_vit_block_top.grp_dataflow_wrapper_fu_6443.task_compute_attn_U0.grp_do_attn_1_fu_5150.kq_sm_i_U' written by process 'vit_block_top_vit_block_top.grp_dataflow_wrapper_fu_6443.task_compute_attn_U0.grp_do_attn_1_fu_5150.do_split_5_U0'");
                                $fdisplay(fp, "Dependence_Channel_path vit_block_top_vit_block_top.grp_dataflow_wrapper_fu_6443.task_compute_attn_U0.grp_do_attn_1_fu_5150.kq_sm_i_U");
                                $fdisplay(fp, "Dependence_Channel_status EMPTY");
                            end
                            else if (~grp_dataflow_wrapper_fu_6443.task_compute_attn_U0.grp_do_attn_1_fu_5150.kq_sm_i_U.if_full_n) begin
                                $display("//      Blocked by full output FIFO 'vit_block_top_vit_block_top.grp_dataflow_wrapper_fu_6443.task_compute_attn_U0.grp_do_attn_1_fu_5150.kq_sm_i_U' read by process 'vit_block_top_vit_block_top.grp_dataflow_wrapper_fu_6443.task_compute_attn_U0.grp_do_attn_1_fu_5150.do_split_5_U0'");
                                $fdisplay(fp, "Dependence_Channel_path vit_block_top_vit_block_top.grp_dataflow_wrapper_fu_6443.task_compute_attn_U0.grp_do_attn_1_fu_5150.kq_sm_i_U");
                                $fdisplay(fp, "Dependence_Channel_status FULL");
                            end
                        end
// for dep channel 'vit_block_top_vit_block_top.grp_dataflow_wrapper_fu_6443.task_compute_attn_U0.grp_do_attn_1_fu_5150.start_for_do_split_5_U0_U' info is :
// blk sig is {{~vit_block_top_vit_block_top_inst.grp_dataflow_wrapper_fu_6443.task_compute_attn_U0.grp_do_attn_1_fu_5150.start_for_do_split_5_U0_U.if_full_n & vit_block_top_vit_block_top_inst.grp_dataflow_wrapper_fu_6443.task_compute_attn_U0.grp_do_attn_1_fu_5150.do_quant_3_U0.ap_start & ~vit_block_top_vit_block_top_inst.grp_dataflow_wrapper_fu_6443.task_compute_attn_U0.grp_do_attn_1_fu_5150.do_quant_3_U0.real_start & (trans_in_cnt_20 == trans_out_cnt_20) & ~vit_block_top_vit_block_top_inst.grp_dataflow_wrapper_fu_6443.task_compute_attn_U0.grp_do_attn_1_fu_5150.start_for_do_split_5_U0_U.if_read} start_FIFO}
                        if ((~grp_dataflow_wrapper_fu_6443.task_compute_attn_U0.grp_do_attn_1_fu_5150.start_for_do_split_5_U0_U.if_full_n & grp_dataflow_wrapper_fu_6443.task_compute_attn_U0.grp_do_attn_1_fu_5150.do_quant_3_U0.ap_start & ~grp_dataflow_wrapper_fu_6443.task_compute_attn_U0.grp_do_attn_1_fu_5150.do_quant_3_U0.real_start & (trans_in_cnt_20 == trans_out_cnt_20) & ~grp_dataflow_wrapper_fu_6443.task_compute_attn_U0.grp_do_attn_1_fu_5150.start_for_do_split_5_U0_U.if_read)) begin
                            $display("//      Blocked by full output start propagation FIFO 'vit_block_top_vit_block_top.grp_dataflow_wrapper_fu_6443.task_compute_attn_U0.grp_do_attn_1_fu_5150.start_for_do_split_5_U0_U' read by process 'vit_block_top_vit_block_top.grp_dataflow_wrapper_fu_6443.task_compute_attn_U0.grp_do_attn_1_fu_5150.do_split_5_U0',");
                        end
                    end
                    endcase
                end
                32 : begin // for proc 'vit_block_top_vit_block_top.grp_dataflow_wrapper_fu_6443.task_compute_attn_U0.grp_do_attn_1_fu_5150.do_quant_1_U0'
                    case(index2)
                    25: begin //  for dep proc 'vit_block_top_vit_block_top.grp_dataflow_wrapper_fu_6443.task_compute_attn_U0.grp_do_attn_1_fu_5150.do_matmul_4_U0'
// for dep channel 'vit_block_top_vit_block_top.grp_dataflow_wrapper_fu_6443.task_compute_attn_U0.grp_do_attn_1_fu_5150.v_sm_i_U' info is :
// blk sig is {~vit_block_top_vit_block_top_inst.grp_dataflow_wrapper_fu_6443.task_compute_attn_U0.grp_do_attn_1_fu_5150.do_quant_1_U0.grp_do_quant_1_Pipeline_TT_LOOP_CT_LOOP_fu_82.v_sm_blk_n data_FIFO}
                        if ((~grp_dataflow_wrapper_fu_6443.task_compute_attn_U0.grp_do_attn_1_fu_5150.do_quant_1_U0.grp_do_quant_1_Pipeline_TT_LOOP_CT_LOOP_fu_82.v_sm_blk_n)) begin
                            if (~grp_dataflow_wrapper_fu_6443.task_compute_attn_U0.grp_do_attn_1_fu_5150.v_sm_i_U.if_empty_n) begin
                                $display("//      Blocked by empty input FIFO 'vit_block_top_vit_block_top.grp_dataflow_wrapper_fu_6443.task_compute_attn_U0.grp_do_attn_1_fu_5150.v_sm_i_U' written by process 'vit_block_top_vit_block_top.grp_dataflow_wrapper_fu_6443.task_compute_attn_U0.grp_do_attn_1_fu_5150.do_matmul_4_U0'");
                                $fdisplay(fp, "Dependence_Channel_path vit_block_top_vit_block_top.grp_dataflow_wrapper_fu_6443.task_compute_attn_U0.grp_do_attn_1_fu_5150.v_sm_i_U");
                                $fdisplay(fp, "Dependence_Channel_status EMPTY");
                            end
                            else if (~grp_dataflow_wrapper_fu_6443.task_compute_attn_U0.grp_do_attn_1_fu_5150.v_sm_i_U.if_full_n) begin
                                $display("//      Blocked by full output FIFO 'vit_block_top_vit_block_top.grp_dataflow_wrapper_fu_6443.task_compute_attn_U0.grp_do_attn_1_fu_5150.v_sm_i_U' read by process 'vit_block_top_vit_block_top.grp_dataflow_wrapper_fu_6443.task_compute_attn_U0.grp_do_attn_1_fu_5150.do_matmul_4_U0'");
                                $fdisplay(fp, "Dependence_Channel_path vit_block_top_vit_block_top.grp_dataflow_wrapper_fu_6443.task_compute_attn_U0.grp_do_attn_1_fu_5150.v_sm_i_U");
                                $fdisplay(fp, "Dependence_Channel_status FULL");
                            end
                        end
// for dep channel 'vit_block_top_vit_block_top.grp_dataflow_wrapper_fu_6443.task_compute_attn_U0.grp_do_attn_1_fu_5150.start_for_do_quant_1_U0_U' info is :
// blk sig is {{~vit_block_top_vit_block_top_inst.grp_dataflow_wrapper_fu_6443.task_compute_attn_U0.grp_do_attn_1_fu_5150.start_for_do_quant_1_U0_U.if_empty_n & vit_block_top_vit_block_top_inst.grp_dataflow_wrapper_fu_6443.task_compute_attn_U0.grp_do_attn_1_fu_5150.do_quant_1_U0.ap_idle & ~vit_block_top_vit_block_top_inst.grp_dataflow_wrapper_fu_6443.task_compute_attn_U0.grp_do_attn_1_fu_5150.start_for_do_quant_1_U0_U.if_write} start_FIFO}
                        if ((~grp_dataflow_wrapper_fu_6443.task_compute_attn_U0.grp_do_attn_1_fu_5150.start_for_do_quant_1_U0_U.if_empty_n & grp_dataflow_wrapper_fu_6443.task_compute_attn_U0.grp_do_attn_1_fu_5150.do_quant_1_U0.ap_idle & ~grp_dataflow_wrapper_fu_6443.task_compute_attn_U0.grp_do_attn_1_fu_5150.start_for_do_quant_1_U0_U.if_write)) begin
                            $display("//      Blocked by missing 'ap_start' from start propagation FIFO 'vit_block_top_vit_block_top.grp_dataflow_wrapper_fu_6443.task_compute_attn_U0.grp_do_attn_1_fu_5150.start_for_do_quant_1_U0_U' written by process 'vit_block_top_vit_block_top.grp_dataflow_wrapper_fu_6443.task_compute_attn_U0.grp_do_attn_1_fu_5150.do_matmul_4_U0',");
                        end
                    end
                    29: begin //  for dep proc 'vit_block_top_vit_block_top.grp_dataflow_wrapper_fu_6443.task_compute_attn_U0.grp_do_attn_1_fu_5150.do_matmul_4_U0.do_adapt_13_1_U0'
// for dep channel 'vit_block_top_vit_block_top.grp_dataflow_wrapper_fu_6443.task_compute_attn_U0.grp_do_attn_1_fu_5150.v_sm_i_U' info is :
// blk sig is {~vit_block_top_vit_block_top_inst.grp_dataflow_wrapper_fu_6443.task_compute_attn_U0.grp_do_attn_1_fu_5150.do_quant_1_U0.grp_do_quant_1_Pipeline_TT_LOOP_CT_LOOP_fu_82.v_sm_blk_n data_FIFO}
                        if ((~grp_dataflow_wrapper_fu_6443.task_compute_attn_U0.grp_do_attn_1_fu_5150.do_quant_1_U0.grp_do_quant_1_Pipeline_TT_LOOP_CT_LOOP_fu_82.v_sm_blk_n)) begin
                            if (~grp_dataflow_wrapper_fu_6443.task_compute_attn_U0.grp_do_attn_1_fu_5150.v_sm_i_U.if_empty_n) begin
                                $display("//      Blocked by empty input FIFO 'vit_block_top_vit_block_top.grp_dataflow_wrapper_fu_6443.task_compute_attn_U0.grp_do_attn_1_fu_5150.v_sm_i_U' written by process 'vit_block_top_vit_block_top.grp_dataflow_wrapper_fu_6443.task_compute_attn_U0.grp_do_attn_1_fu_5150.do_matmul_4_U0.do_adapt_13_1_U0'");
                                $fdisplay(fp, "Dependence_Channel_path vit_block_top_vit_block_top.grp_dataflow_wrapper_fu_6443.task_compute_attn_U0.grp_do_attn_1_fu_5150.v_sm_i_U");
                                $fdisplay(fp, "Dependence_Channel_status EMPTY");
                            end
                            else if (~grp_dataflow_wrapper_fu_6443.task_compute_attn_U0.grp_do_attn_1_fu_5150.v_sm_i_U.if_full_n) begin
                                $display("//      Blocked by full output FIFO 'vit_block_top_vit_block_top.grp_dataflow_wrapper_fu_6443.task_compute_attn_U0.grp_do_attn_1_fu_5150.v_sm_i_U' read by process 'vit_block_top_vit_block_top.grp_dataflow_wrapper_fu_6443.task_compute_attn_U0.grp_do_attn_1_fu_5150.do_matmul_4_U0.do_adapt_13_1_U0'");
                                $fdisplay(fp, "Dependence_Channel_path vit_block_top_vit_block_top.grp_dataflow_wrapper_fu_6443.task_compute_attn_U0.grp_do_attn_1_fu_5150.v_sm_i_U");
                                $fdisplay(fp, "Dependence_Channel_status FULL");
                            end
                        end
                    end
                    35: begin //  for dep proc 'vit_block_top_vit_block_top.grp_dataflow_wrapper_fu_6443.task_compute_attn_U0.grp_do_attn_1_fu_5150.do_split_U0'
// for dep channel 'vit_block_top_vit_block_top.grp_dataflow_wrapper_fu_6443.task_compute_attn_U0.grp_do_attn_1_fu_5150.vq_sm_i_U' info is :
// blk sig is {~vit_block_top_vit_block_top_inst.grp_dataflow_wrapper_fu_6443.task_compute_attn_U0.grp_do_attn_1_fu_5150.do_quant_1_U0.grp_do_quant_1_Pipeline_TT_LOOP_CT_LOOP_fu_82.vq_sm_blk_n data_FIFO}
                        if ((~grp_dataflow_wrapper_fu_6443.task_compute_attn_U0.grp_do_attn_1_fu_5150.do_quant_1_U0.grp_do_quant_1_Pipeline_TT_LOOP_CT_LOOP_fu_82.vq_sm_blk_n)) begin
                            if (~grp_dataflow_wrapper_fu_6443.task_compute_attn_U0.grp_do_attn_1_fu_5150.vq_sm_i_U.if_empty_n) begin
                                $display("//      Blocked by empty input FIFO 'vit_block_top_vit_block_top.grp_dataflow_wrapper_fu_6443.task_compute_attn_U0.grp_do_attn_1_fu_5150.vq_sm_i_U' written by process 'vit_block_top_vit_block_top.grp_dataflow_wrapper_fu_6443.task_compute_attn_U0.grp_do_attn_1_fu_5150.do_split_U0'");
                                $fdisplay(fp, "Dependence_Channel_path vit_block_top_vit_block_top.grp_dataflow_wrapper_fu_6443.task_compute_attn_U0.grp_do_attn_1_fu_5150.vq_sm_i_U");
                                $fdisplay(fp, "Dependence_Channel_status EMPTY");
                            end
                            else if (~grp_dataflow_wrapper_fu_6443.task_compute_attn_U0.grp_do_attn_1_fu_5150.vq_sm_i_U.if_full_n) begin
                                $display("//      Blocked by full output FIFO 'vit_block_top_vit_block_top.grp_dataflow_wrapper_fu_6443.task_compute_attn_U0.grp_do_attn_1_fu_5150.vq_sm_i_U' read by process 'vit_block_top_vit_block_top.grp_dataflow_wrapper_fu_6443.task_compute_attn_U0.grp_do_attn_1_fu_5150.do_split_U0'");
                                $fdisplay(fp, "Dependence_Channel_path vit_block_top_vit_block_top.grp_dataflow_wrapper_fu_6443.task_compute_attn_U0.grp_do_attn_1_fu_5150.vq_sm_i_U");
                                $fdisplay(fp, "Dependence_Channel_status FULL");
                            end
                        end
// for dep channel 'vit_block_top_vit_block_top.grp_dataflow_wrapper_fu_6443.task_compute_attn_U0.grp_do_attn_1_fu_5150.start_for_do_split_U0_U' info is :
// blk sig is {{~vit_block_top_vit_block_top_inst.grp_dataflow_wrapper_fu_6443.task_compute_attn_U0.grp_do_attn_1_fu_5150.start_for_do_split_U0_U.if_full_n & vit_block_top_vit_block_top_inst.grp_dataflow_wrapper_fu_6443.task_compute_attn_U0.grp_do_attn_1_fu_5150.do_quant_1_U0.ap_start & ~vit_block_top_vit_block_top_inst.grp_dataflow_wrapper_fu_6443.task_compute_attn_U0.grp_do_attn_1_fu_5150.do_quant_1_U0.real_start & (trans_in_cnt_21 == trans_out_cnt_21) & ~vit_block_top_vit_block_top_inst.grp_dataflow_wrapper_fu_6443.task_compute_attn_U0.grp_do_attn_1_fu_5150.start_for_do_split_U0_U.if_read} start_FIFO}
                        if ((~grp_dataflow_wrapper_fu_6443.task_compute_attn_U0.grp_do_attn_1_fu_5150.start_for_do_split_U0_U.if_full_n & grp_dataflow_wrapper_fu_6443.task_compute_attn_U0.grp_do_attn_1_fu_5150.do_quant_1_U0.ap_start & ~grp_dataflow_wrapper_fu_6443.task_compute_attn_U0.grp_do_attn_1_fu_5150.do_quant_1_U0.real_start & (trans_in_cnt_21 == trans_out_cnt_21) & ~grp_dataflow_wrapper_fu_6443.task_compute_attn_U0.grp_do_attn_1_fu_5150.start_for_do_split_U0_U.if_read)) begin
                            $display("//      Blocked by full output start propagation FIFO 'vit_block_top_vit_block_top.grp_dataflow_wrapper_fu_6443.task_compute_attn_U0.grp_do_attn_1_fu_5150.start_for_do_split_U0_U' read by process 'vit_block_top_vit_block_top.grp_dataflow_wrapper_fu_6443.task_compute_attn_U0.grp_do_attn_1_fu_5150.do_split_U0',");
                        end
                    end
                    endcase
                end
                33 : begin // for proc 'vit_block_top_vit_block_top.grp_dataflow_wrapper_fu_6443.task_compute_attn_U0.grp_do_attn_1_fu_5150.do_split_4_U0'
                    case(index2)
                    30: begin //  for dep proc 'vit_block_top_vit_block_top.grp_dataflow_wrapper_fu_6443.task_compute_attn_U0.grp_do_attn_1_fu_5150.do_quant_U0'
// for dep channel 'vit_block_top_vit_block_top.grp_dataflow_wrapper_fu_6443.task_compute_attn_U0.grp_do_attn_1_fu_5150.qq_sm_i_U' info is :
// blk sig is {~vit_block_top_vit_block_top_inst.grp_dataflow_wrapper_fu_6443.task_compute_attn_U0.grp_do_attn_1_fu_5150.do_split_4_U0.qq_sm_blk_n data_FIFO}
                        if ((~grp_dataflow_wrapper_fu_6443.task_compute_attn_U0.grp_do_attn_1_fu_5150.do_split_4_U0.qq_sm_blk_n)) begin
                            if (~grp_dataflow_wrapper_fu_6443.task_compute_attn_U0.grp_do_attn_1_fu_5150.qq_sm_i_U.if_empty_n) begin
                                $display("//      Blocked by empty input FIFO 'vit_block_top_vit_block_top.grp_dataflow_wrapper_fu_6443.task_compute_attn_U0.grp_do_attn_1_fu_5150.qq_sm_i_U' written by process 'vit_block_top_vit_block_top.grp_dataflow_wrapper_fu_6443.task_compute_attn_U0.grp_do_attn_1_fu_5150.do_quant_U0'");
                                $fdisplay(fp, "Dependence_Channel_path vit_block_top_vit_block_top.grp_dataflow_wrapper_fu_6443.task_compute_attn_U0.grp_do_attn_1_fu_5150.qq_sm_i_U");
                                $fdisplay(fp, "Dependence_Channel_status EMPTY");
                            end
                            else if (~grp_dataflow_wrapper_fu_6443.task_compute_attn_U0.grp_do_attn_1_fu_5150.qq_sm_i_U.if_full_n) begin
                                $display("//      Blocked by full output FIFO 'vit_block_top_vit_block_top.grp_dataflow_wrapper_fu_6443.task_compute_attn_U0.grp_do_attn_1_fu_5150.qq_sm_i_U' read by process 'vit_block_top_vit_block_top.grp_dataflow_wrapper_fu_6443.task_compute_attn_U0.grp_do_attn_1_fu_5150.do_quant_U0'");
                                $fdisplay(fp, "Dependence_Channel_path vit_block_top_vit_block_top.grp_dataflow_wrapper_fu_6443.task_compute_attn_U0.grp_do_attn_1_fu_5150.qq_sm_i_U");
                                $fdisplay(fp, "Dependence_Channel_status FULL");
                            end
                        end
// for dep channel 'vit_block_top_vit_block_top.grp_dataflow_wrapper_fu_6443.task_compute_attn_U0.grp_do_attn_1_fu_5150.start_for_do_split_4_U0_U' info is :
// blk sig is {{~vit_block_top_vit_block_top_inst.grp_dataflow_wrapper_fu_6443.task_compute_attn_U0.grp_do_attn_1_fu_5150.start_for_do_split_4_U0_U.if_empty_n & vit_block_top_vit_block_top_inst.grp_dataflow_wrapper_fu_6443.task_compute_attn_U0.grp_do_attn_1_fu_5150.do_split_4_U0.ap_idle & ~vit_block_top_vit_block_top_inst.grp_dataflow_wrapper_fu_6443.task_compute_attn_U0.grp_do_attn_1_fu_5150.start_for_do_split_4_U0_U.if_write} start_FIFO}
                        if ((~grp_dataflow_wrapper_fu_6443.task_compute_attn_U0.grp_do_attn_1_fu_5150.start_for_do_split_4_U0_U.if_empty_n & grp_dataflow_wrapper_fu_6443.task_compute_attn_U0.grp_do_attn_1_fu_5150.do_split_4_U0.ap_idle & ~grp_dataflow_wrapper_fu_6443.task_compute_attn_U0.grp_do_attn_1_fu_5150.start_for_do_split_4_U0_U.if_write)) begin
                            $display("//      Blocked by missing 'ap_start' from start propagation FIFO 'vit_block_top_vit_block_top.grp_dataflow_wrapper_fu_6443.task_compute_attn_U0.grp_do_attn_1_fu_5150.start_for_do_split_4_U0_U' written by process 'vit_block_top_vit_block_top.grp_dataflow_wrapper_fu_6443.task_compute_attn_U0.grp_do_attn_1_fu_5150.do_quant_U0',");
                        end
                    end
                    36: begin //  for dep proc 'vit_block_top_vit_block_top.grp_dataflow_wrapper_fu_6443.task_compute_attn_U0.grp_do_attn_1_fu_5150.do_attn_6_U0'
// for dep channel 'vit_block_top_vit_block_top.grp_dataflow_wrapper_fu_6443.task_compute_attn_U0.grp_do_attn_1_fu_5150.qq_sm_head_0_i_U' info is :
// blk sig is {~vit_block_top_vit_block_top_inst.grp_dataflow_wrapper_fu_6443.task_compute_attn_U0.grp_do_attn_1_fu_5150.do_split_4_U0.qq_sm_head_0_blk_n data_FIFO}
                        if ((~grp_dataflow_wrapper_fu_6443.task_compute_attn_U0.grp_do_attn_1_fu_5150.do_split_4_U0.qq_sm_head_0_blk_n)) begin
                            if (~grp_dataflow_wrapper_fu_6443.task_compute_attn_U0.grp_do_attn_1_fu_5150.qq_sm_head_0_i_U.if_empty_n) begin
                                $display("//      Blocked by empty input FIFO 'vit_block_top_vit_block_top.grp_dataflow_wrapper_fu_6443.task_compute_attn_U0.grp_do_attn_1_fu_5150.qq_sm_head_0_i_U' written by process 'vit_block_top_vit_block_top.grp_dataflow_wrapper_fu_6443.task_compute_attn_U0.grp_do_attn_1_fu_5150.do_attn_6_U0'");
                                $fdisplay(fp, "Dependence_Channel_path vit_block_top_vit_block_top.grp_dataflow_wrapper_fu_6443.task_compute_attn_U0.grp_do_attn_1_fu_5150.qq_sm_head_0_i_U");
                                $fdisplay(fp, "Dependence_Channel_status EMPTY");
                            end
                            else if (~grp_dataflow_wrapper_fu_6443.task_compute_attn_U0.grp_do_attn_1_fu_5150.qq_sm_head_0_i_U.if_full_n) begin
                                $display("//      Blocked by full output FIFO 'vit_block_top_vit_block_top.grp_dataflow_wrapper_fu_6443.task_compute_attn_U0.grp_do_attn_1_fu_5150.qq_sm_head_0_i_U' read by process 'vit_block_top_vit_block_top.grp_dataflow_wrapper_fu_6443.task_compute_attn_U0.grp_do_attn_1_fu_5150.do_attn_6_U0'");
                                $fdisplay(fp, "Dependence_Channel_path vit_block_top_vit_block_top.grp_dataflow_wrapper_fu_6443.task_compute_attn_U0.grp_do_attn_1_fu_5150.qq_sm_head_0_i_U");
                                $fdisplay(fp, "Dependence_Channel_status FULL");
                            end
                        end
// for dep channel 'vit_block_top_vit_block_top.grp_dataflow_wrapper_fu_6443.task_compute_attn_U0.grp_do_attn_1_fu_5150.start_for_do_attn_6_U0_U' info is :
// blk sig is {{~vit_block_top_vit_block_top_inst.grp_dataflow_wrapper_fu_6443.task_compute_attn_U0.grp_do_attn_1_fu_5150.start_for_do_attn_6_U0_U.if_full_n & vit_block_top_vit_block_top_inst.grp_dataflow_wrapper_fu_6443.task_compute_attn_U0.grp_do_attn_1_fu_5150.do_split_4_U0.ap_start & ~vit_block_top_vit_block_top_inst.grp_dataflow_wrapper_fu_6443.task_compute_attn_U0.grp_do_attn_1_fu_5150.do_split_4_U0.real_start & (trans_in_cnt_22 == trans_out_cnt_22) & ~vit_block_top_vit_block_top_inst.grp_dataflow_wrapper_fu_6443.task_compute_attn_U0.grp_do_attn_1_fu_5150.start_for_do_attn_6_U0_U.if_read} start_FIFO}
                        if ((~grp_dataflow_wrapper_fu_6443.task_compute_attn_U0.grp_do_attn_1_fu_5150.start_for_do_attn_6_U0_U.if_full_n & grp_dataflow_wrapper_fu_6443.task_compute_attn_U0.grp_do_attn_1_fu_5150.do_split_4_U0.ap_start & ~grp_dataflow_wrapper_fu_6443.task_compute_attn_U0.grp_do_attn_1_fu_5150.do_split_4_U0.real_start & (trans_in_cnt_22 == trans_out_cnt_22) & ~grp_dataflow_wrapper_fu_6443.task_compute_attn_U0.grp_do_attn_1_fu_5150.start_for_do_attn_6_U0_U.if_read)) begin
                            $display("//      Blocked by full output start propagation FIFO 'vit_block_top_vit_block_top.grp_dataflow_wrapper_fu_6443.task_compute_attn_U0.grp_do_attn_1_fu_5150.start_for_do_attn_6_U0_U' read by process 'vit_block_top_vit_block_top.grp_dataflow_wrapper_fu_6443.task_compute_attn_U0.grp_do_attn_1_fu_5150.do_attn_6_U0',");
                        end
                    end
                    37: begin //  for dep proc 'vit_block_top_vit_block_top.grp_dataflow_wrapper_fu_6443.task_compute_attn_U0.grp_do_attn_1_fu_5150.do_attn_7_U0'
// for dep channel 'vit_block_top_vit_block_top.grp_dataflow_wrapper_fu_6443.task_compute_attn_U0.grp_do_attn_1_fu_5150.qq_sm_head_1_i_U' info is :
// blk sig is {~vit_block_top_vit_block_top_inst.grp_dataflow_wrapper_fu_6443.task_compute_attn_U0.grp_do_attn_1_fu_5150.do_split_4_U0.qq_sm_head_1_blk_n data_FIFO}
                        if ((~grp_dataflow_wrapper_fu_6443.task_compute_attn_U0.grp_do_attn_1_fu_5150.do_split_4_U0.qq_sm_head_1_blk_n)) begin
                            if (~grp_dataflow_wrapper_fu_6443.task_compute_attn_U0.grp_do_attn_1_fu_5150.qq_sm_head_1_i_U.if_empty_n) begin
                                $display("//      Blocked by empty input FIFO 'vit_block_top_vit_block_top.grp_dataflow_wrapper_fu_6443.task_compute_attn_U0.grp_do_attn_1_fu_5150.qq_sm_head_1_i_U' written by process 'vit_block_top_vit_block_top.grp_dataflow_wrapper_fu_6443.task_compute_attn_U0.grp_do_attn_1_fu_5150.do_attn_7_U0'");
                                $fdisplay(fp, "Dependence_Channel_path vit_block_top_vit_block_top.grp_dataflow_wrapper_fu_6443.task_compute_attn_U0.grp_do_attn_1_fu_5150.qq_sm_head_1_i_U");
                                $fdisplay(fp, "Dependence_Channel_status EMPTY");
                            end
                            else if (~grp_dataflow_wrapper_fu_6443.task_compute_attn_U0.grp_do_attn_1_fu_5150.qq_sm_head_1_i_U.if_full_n) begin
                                $display("//      Blocked by full output FIFO 'vit_block_top_vit_block_top.grp_dataflow_wrapper_fu_6443.task_compute_attn_U0.grp_do_attn_1_fu_5150.qq_sm_head_1_i_U' read by process 'vit_block_top_vit_block_top.grp_dataflow_wrapper_fu_6443.task_compute_attn_U0.grp_do_attn_1_fu_5150.do_attn_7_U0'");
                                $fdisplay(fp, "Dependence_Channel_path vit_block_top_vit_block_top.grp_dataflow_wrapper_fu_6443.task_compute_attn_U0.grp_do_attn_1_fu_5150.qq_sm_head_1_i_U");
                                $fdisplay(fp, "Dependence_Channel_status FULL");
                            end
                        end
// for dep channel 'vit_block_top_vit_block_top.grp_dataflow_wrapper_fu_6443.task_compute_attn_U0.grp_do_attn_1_fu_5150.start_for_do_attn_7_U0_U' info is :
// blk sig is {{~vit_block_top_vit_block_top_inst.grp_dataflow_wrapper_fu_6443.task_compute_attn_U0.grp_do_attn_1_fu_5150.start_for_do_attn_7_U0_U.if_full_n & vit_block_top_vit_block_top_inst.grp_dataflow_wrapper_fu_6443.task_compute_attn_U0.grp_do_attn_1_fu_5150.do_split_4_U0.ap_start & ~vit_block_top_vit_block_top_inst.grp_dataflow_wrapper_fu_6443.task_compute_attn_U0.grp_do_attn_1_fu_5150.do_split_4_U0.real_start & (trans_in_cnt_22 == trans_out_cnt_22) & ~vit_block_top_vit_block_top_inst.grp_dataflow_wrapper_fu_6443.task_compute_attn_U0.grp_do_attn_1_fu_5150.start_for_do_attn_7_U0_U.if_read} start_FIFO}
                        if ((~grp_dataflow_wrapper_fu_6443.task_compute_attn_U0.grp_do_attn_1_fu_5150.start_for_do_attn_7_U0_U.if_full_n & grp_dataflow_wrapper_fu_6443.task_compute_attn_U0.grp_do_attn_1_fu_5150.do_split_4_U0.ap_start & ~grp_dataflow_wrapper_fu_6443.task_compute_attn_U0.grp_do_attn_1_fu_5150.do_split_4_U0.real_start & (trans_in_cnt_22 == trans_out_cnt_22) & ~grp_dataflow_wrapper_fu_6443.task_compute_attn_U0.grp_do_attn_1_fu_5150.start_for_do_attn_7_U0_U.if_read)) begin
                            $display("//      Blocked by full output start propagation FIFO 'vit_block_top_vit_block_top.grp_dataflow_wrapper_fu_6443.task_compute_attn_U0.grp_do_attn_1_fu_5150.start_for_do_attn_7_U0_U' read by process 'vit_block_top_vit_block_top.grp_dataflow_wrapper_fu_6443.task_compute_attn_U0.grp_do_attn_1_fu_5150.do_attn_7_U0',");
                        end
                    end
                    38: begin //  for dep proc 'vit_block_top_vit_block_top.grp_dataflow_wrapper_fu_6443.task_compute_attn_U0.grp_do_attn_1_fu_5150.do_attn_U0'
// for dep channel 'vit_block_top_vit_block_top.grp_dataflow_wrapper_fu_6443.task_compute_attn_U0.grp_do_attn_1_fu_5150.qq_sm_head_2_i_U' info is :
// blk sig is {~vit_block_top_vit_block_top_inst.grp_dataflow_wrapper_fu_6443.task_compute_attn_U0.grp_do_attn_1_fu_5150.do_split_4_U0.qq_sm_head_2_blk_n data_FIFO}
                        if ((~grp_dataflow_wrapper_fu_6443.task_compute_attn_U0.grp_do_attn_1_fu_5150.do_split_4_U0.qq_sm_head_2_blk_n)) begin
                            if (~grp_dataflow_wrapper_fu_6443.task_compute_attn_U0.grp_do_attn_1_fu_5150.qq_sm_head_2_i_U.if_empty_n) begin
                                $display("//      Blocked by empty input FIFO 'vit_block_top_vit_block_top.grp_dataflow_wrapper_fu_6443.task_compute_attn_U0.grp_do_attn_1_fu_5150.qq_sm_head_2_i_U' written by process 'vit_block_top_vit_block_top.grp_dataflow_wrapper_fu_6443.task_compute_attn_U0.grp_do_attn_1_fu_5150.do_attn_U0'");
                                $fdisplay(fp, "Dependence_Channel_path vit_block_top_vit_block_top.grp_dataflow_wrapper_fu_6443.task_compute_attn_U0.grp_do_attn_1_fu_5150.qq_sm_head_2_i_U");
                                $fdisplay(fp, "Dependence_Channel_status EMPTY");
                            end
                            else if (~grp_dataflow_wrapper_fu_6443.task_compute_attn_U0.grp_do_attn_1_fu_5150.qq_sm_head_2_i_U.if_full_n) begin
                                $display("//      Blocked by full output FIFO 'vit_block_top_vit_block_top.grp_dataflow_wrapper_fu_6443.task_compute_attn_U0.grp_do_attn_1_fu_5150.qq_sm_head_2_i_U' read by process 'vit_block_top_vit_block_top.grp_dataflow_wrapper_fu_6443.task_compute_attn_U0.grp_do_attn_1_fu_5150.do_attn_U0'");
                                $fdisplay(fp, "Dependence_Channel_path vit_block_top_vit_block_top.grp_dataflow_wrapper_fu_6443.task_compute_attn_U0.grp_do_attn_1_fu_5150.qq_sm_head_2_i_U");
                                $fdisplay(fp, "Dependence_Channel_status FULL");
                            end
                        end
// for dep channel 'vit_block_top_vit_block_top.grp_dataflow_wrapper_fu_6443.task_compute_attn_U0.grp_do_attn_1_fu_5150.start_for_do_attn_U0_U' info is :
// blk sig is {{~vit_block_top_vit_block_top_inst.grp_dataflow_wrapper_fu_6443.task_compute_attn_U0.grp_do_attn_1_fu_5150.start_for_do_attn_U0_U.if_full_n & vit_block_top_vit_block_top_inst.grp_dataflow_wrapper_fu_6443.task_compute_attn_U0.grp_do_attn_1_fu_5150.do_split_4_U0.ap_start & ~vit_block_top_vit_block_top_inst.grp_dataflow_wrapper_fu_6443.task_compute_attn_U0.grp_do_attn_1_fu_5150.do_split_4_U0.real_start & (trans_in_cnt_22 == trans_out_cnt_22) & ~vit_block_top_vit_block_top_inst.grp_dataflow_wrapper_fu_6443.task_compute_attn_U0.grp_do_attn_1_fu_5150.start_for_do_attn_U0_U.if_read} start_FIFO}
                        if ((~grp_dataflow_wrapper_fu_6443.task_compute_attn_U0.grp_do_attn_1_fu_5150.start_for_do_attn_U0_U.if_full_n & grp_dataflow_wrapper_fu_6443.task_compute_attn_U0.grp_do_attn_1_fu_5150.do_split_4_U0.ap_start & ~grp_dataflow_wrapper_fu_6443.task_compute_attn_U0.grp_do_attn_1_fu_5150.do_split_4_U0.real_start & (trans_in_cnt_22 == trans_out_cnt_22) & ~grp_dataflow_wrapper_fu_6443.task_compute_attn_U0.grp_do_attn_1_fu_5150.start_for_do_attn_U0_U.if_read)) begin
                            $display("//      Blocked by full output start propagation FIFO 'vit_block_top_vit_block_top.grp_dataflow_wrapper_fu_6443.task_compute_attn_U0.grp_do_attn_1_fu_5150.start_for_do_attn_U0_U' read by process 'vit_block_top_vit_block_top.grp_dataflow_wrapper_fu_6443.task_compute_attn_U0.grp_do_attn_1_fu_5150.do_attn_U0',");
                        end
                    end
                    endcase
                end
                34 : begin // for proc 'vit_block_top_vit_block_top.grp_dataflow_wrapper_fu_6443.task_compute_attn_U0.grp_do_attn_1_fu_5150.do_split_5_U0'
                    case(index2)
                    31: begin //  for dep proc 'vit_block_top_vit_block_top.grp_dataflow_wrapper_fu_6443.task_compute_attn_U0.grp_do_attn_1_fu_5150.do_quant_3_U0'
// for dep channel 'vit_block_top_vit_block_top.grp_dataflow_wrapper_fu_6443.task_compute_attn_U0.grp_do_attn_1_fu_5150.kq_sm_i_U' info is :
// blk sig is {~vit_block_top_vit_block_top_inst.grp_dataflow_wrapper_fu_6443.task_compute_attn_U0.grp_do_attn_1_fu_5150.do_split_5_U0.kq_sm_blk_n data_FIFO}
                        if ((~grp_dataflow_wrapper_fu_6443.task_compute_attn_U0.grp_do_attn_1_fu_5150.do_split_5_U0.kq_sm_blk_n)) begin
                            if (~grp_dataflow_wrapper_fu_6443.task_compute_attn_U0.grp_do_attn_1_fu_5150.kq_sm_i_U.if_empty_n) begin
                                $display("//      Blocked by empty input FIFO 'vit_block_top_vit_block_top.grp_dataflow_wrapper_fu_6443.task_compute_attn_U0.grp_do_attn_1_fu_5150.kq_sm_i_U' written by process 'vit_block_top_vit_block_top.grp_dataflow_wrapper_fu_6443.task_compute_attn_U0.grp_do_attn_1_fu_5150.do_quant_3_U0'");
                                $fdisplay(fp, "Dependence_Channel_path vit_block_top_vit_block_top.grp_dataflow_wrapper_fu_6443.task_compute_attn_U0.grp_do_attn_1_fu_5150.kq_sm_i_U");
                                $fdisplay(fp, "Dependence_Channel_status EMPTY");
                            end
                            else if (~grp_dataflow_wrapper_fu_6443.task_compute_attn_U0.grp_do_attn_1_fu_5150.kq_sm_i_U.if_full_n) begin
                                $display("//      Blocked by full output FIFO 'vit_block_top_vit_block_top.grp_dataflow_wrapper_fu_6443.task_compute_attn_U0.grp_do_attn_1_fu_5150.kq_sm_i_U' read by process 'vit_block_top_vit_block_top.grp_dataflow_wrapper_fu_6443.task_compute_attn_U0.grp_do_attn_1_fu_5150.do_quant_3_U0'");
                                $fdisplay(fp, "Dependence_Channel_path vit_block_top_vit_block_top.grp_dataflow_wrapper_fu_6443.task_compute_attn_U0.grp_do_attn_1_fu_5150.kq_sm_i_U");
                                $fdisplay(fp, "Dependence_Channel_status FULL");
                            end
                        end
// for dep channel 'vit_block_top_vit_block_top.grp_dataflow_wrapper_fu_6443.task_compute_attn_U0.grp_do_attn_1_fu_5150.start_for_do_split_5_U0_U' info is :
// blk sig is {{~vit_block_top_vit_block_top_inst.grp_dataflow_wrapper_fu_6443.task_compute_attn_U0.grp_do_attn_1_fu_5150.start_for_do_split_5_U0_U.if_empty_n & vit_block_top_vit_block_top_inst.grp_dataflow_wrapper_fu_6443.task_compute_attn_U0.grp_do_attn_1_fu_5150.do_split_5_U0.ap_idle & ~vit_block_top_vit_block_top_inst.grp_dataflow_wrapper_fu_6443.task_compute_attn_U0.grp_do_attn_1_fu_5150.start_for_do_split_5_U0_U.if_write} start_FIFO}
                        if ((~grp_dataflow_wrapper_fu_6443.task_compute_attn_U0.grp_do_attn_1_fu_5150.start_for_do_split_5_U0_U.if_empty_n & grp_dataflow_wrapper_fu_6443.task_compute_attn_U0.grp_do_attn_1_fu_5150.do_split_5_U0.ap_idle & ~grp_dataflow_wrapper_fu_6443.task_compute_attn_U0.grp_do_attn_1_fu_5150.start_for_do_split_5_U0_U.if_write)) begin
                            $display("//      Blocked by missing 'ap_start' from start propagation FIFO 'vit_block_top_vit_block_top.grp_dataflow_wrapper_fu_6443.task_compute_attn_U0.grp_do_attn_1_fu_5150.start_for_do_split_5_U0_U' written by process 'vit_block_top_vit_block_top.grp_dataflow_wrapper_fu_6443.task_compute_attn_U0.grp_do_attn_1_fu_5150.do_quant_3_U0',");
                        end
                    end
                    36: begin //  for dep proc 'vit_block_top_vit_block_top.grp_dataflow_wrapper_fu_6443.task_compute_attn_U0.grp_do_attn_1_fu_5150.do_attn_6_U0'
// for dep channel 'vit_block_top_vit_block_top.grp_dataflow_wrapper_fu_6443.task_compute_attn_U0.grp_do_attn_1_fu_5150.kq_sm_head_0_i_U' info is :
// blk sig is {~vit_block_top_vit_block_top_inst.grp_dataflow_wrapper_fu_6443.task_compute_attn_U0.grp_do_attn_1_fu_5150.do_split_5_U0.kq_sm_head_0_blk_n data_FIFO}
                        if ((~grp_dataflow_wrapper_fu_6443.task_compute_attn_U0.grp_do_attn_1_fu_5150.do_split_5_U0.kq_sm_head_0_blk_n)) begin
                            if (~grp_dataflow_wrapper_fu_6443.task_compute_attn_U0.grp_do_attn_1_fu_5150.kq_sm_head_0_i_U.if_empty_n) begin
                                $display("//      Blocked by empty input FIFO 'vit_block_top_vit_block_top.grp_dataflow_wrapper_fu_6443.task_compute_attn_U0.grp_do_attn_1_fu_5150.kq_sm_head_0_i_U' written by process 'vit_block_top_vit_block_top.grp_dataflow_wrapper_fu_6443.task_compute_attn_U0.grp_do_attn_1_fu_5150.do_attn_6_U0'");
                                $fdisplay(fp, "Dependence_Channel_path vit_block_top_vit_block_top.grp_dataflow_wrapper_fu_6443.task_compute_attn_U0.grp_do_attn_1_fu_5150.kq_sm_head_0_i_U");
                                $fdisplay(fp, "Dependence_Channel_status EMPTY");
                            end
                            else if (~grp_dataflow_wrapper_fu_6443.task_compute_attn_U0.grp_do_attn_1_fu_5150.kq_sm_head_0_i_U.if_full_n) begin
                                $display("//      Blocked by full output FIFO 'vit_block_top_vit_block_top.grp_dataflow_wrapper_fu_6443.task_compute_attn_U0.grp_do_attn_1_fu_5150.kq_sm_head_0_i_U' read by process 'vit_block_top_vit_block_top.grp_dataflow_wrapper_fu_6443.task_compute_attn_U0.grp_do_attn_1_fu_5150.do_attn_6_U0'");
                                $fdisplay(fp, "Dependence_Channel_path vit_block_top_vit_block_top.grp_dataflow_wrapper_fu_6443.task_compute_attn_U0.grp_do_attn_1_fu_5150.kq_sm_head_0_i_U");
                                $fdisplay(fp, "Dependence_Channel_status FULL");
                            end
                        end
                    end
                    37: begin //  for dep proc 'vit_block_top_vit_block_top.grp_dataflow_wrapper_fu_6443.task_compute_attn_U0.grp_do_attn_1_fu_5150.do_attn_7_U0'
// for dep channel 'vit_block_top_vit_block_top.grp_dataflow_wrapper_fu_6443.task_compute_attn_U0.grp_do_attn_1_fu_5150.kq_sm_head_1_i_U' info is :
// blk sig is {~vit_block_top_vit_block_top_inst.grp_dataflow_wrapper_fu_6443.task_compute_attn_U0.grp_do_attn_1_fu_5150.do_split_5_U0.kq_sm_head_1_blk_n data_FIFO}
                        if ((~grp_dataflow_wrapper_fu_6443.task_compute_attn_U0.grp_do_attn_1_fu_5150.do_split_5_U0.kq_sm_head_1_blk_n)) begin
                            if (~grp_dataflow_wrapper_fu_6443.task_compute_attn_U0.grp_do_attn_1_fu_5150.kq_sm_head_1_i_U.if_empty_n) begin
                                $display("//      Blocked by empty input FIFO 'vit_block_top_vit_block_top.grp_dataflow_wrapper_fu_6443.task_compute_attn_U0.grp_do_attn_1_fu_5150.kq_sm_head_1_i_U' written by process 'vit_block_top_vit_block_top.grp_dataflow_wrapper_fu_6443.task_compute_attn_U0.grp_do_attn_1_fu_5150.do_attn_7_U0'");
                                $fdisplay(fp, "Dependence_Channel_path vit_block_top_vit_block_top.grp_dataflow_wrapper_fu_6443.task_compute_attn_U0.grp_do_attn_1_fu_5150.kq_sm_head_1_i_U");
                                $fdisplay(fp, "Dependence_Channel_status EMPTY");
                            end
                            else if (~grp_dataflow_wrapper_fu_6443.task_compute_attn_U0.grp_do_attn_1_fu_5150.kq_sm_head_1_i_U.if_full_n) begin
                                $display("//      Blocked by full output FIFO 'vit_block_top_vit_block_top.grp_dataflow_wrapper_fu_6443.task_compute_attn_U0.grp_do_attn_1_fu_5150.kq_sm_head_1_i_U' read by process 'vit_block_top_vit_block_top.grp_dataflow_wrapper_fu_6443.task_compute_attn_U0.grp_do_attn_1_fu_5150.do_attn_7_U0'");
                                $fdisplay(fp, "Dependence_Channel_path vit_block_top_vit_block_top.grp_dataflow_wrapper_fu_6443.task_compute_attn_U0.grp_do_attn_1_fu_5150.kq_sm_head_1_i_U");
                                $fdisplay(fp, "Dependence_Channel_status FULL");
                            end
                        end
                    end
                    38: begin //  for dep proc 'vit_block_top_vit_block_top.grp_dataflow_wrapper_fu_6443.task_compute_attn_U0.grp_do_attn_1_fu_5150.do_attn_U0'
// for dep channel 'vit_block_top_vit_block_top.grp_dataflow_wrapper_fu_6443.task_compute_attn_U0.grp_do_attn_1_fu_5150.kq_sm_head_2_i_U' info is :
// blk sig is {~vit_block_top_vit_block_top_inst.grp_dataflow_wrapper_fu_6443.task_compute_attn_U0.grp_do_attn_1_fu_5150.do_split_5_U0.kq_sm_head_2_blk_n data_FIFO}
                        if ((~grp_dataflow_wrapper_fu_6443.task_compute_attn_U0.grp_do_attn_1_fu_5150.do_split_5_U0.kq_sm_head_2_blk_n)) begin
                            if (~grp_dataflow_wrapper_fu_6443.task_compute_attn_U0.grp_do_attn_1_fu_5150.kq_sm_head_2_i_U.if_empty_n) begin
                                $display("//      Blocked by empty input FIFO 'vit_block_top_vit_block_top.grp_dataflow_wrapper_fu_6443.task_compute_attn_U0.grp_do_attn_1_fu_5150.kq_sm_head_2_i_U' written by process 'vit_block_top_vit_block_top.grp_dataflow_wrapper_fu_6443.task_compute_attn_U0.grp_do_attn_1_fu_5150.do_attn_U0'");
                                $fdisplay(fp, "Dependence_Channel_path vit_block_top_vit_block_top.grp_dataflow_wrapper_fu_6443.task_compute_attn_U0.grp_do_attn_1_fu_5150.kq_sm_head_2_i_U");
                                $fdisplay(fp, "Dependence_Channel_status EMPTY");
                            end
                            else if (~grp_dataflow_wrapper_fu_6443.task_compute_attn_U0.grp_do_attn_1_fu_5150.kq_sm_head_2_i_U.if_full_n) begin
                                $display("//      Blocked by full output FIFO 'vit_block_top_vit_block_top.grp_dataflow_wrapper_fu_6443.task_compute_attn_U0.grp_do_attn_1_fu_5150.kq_sm_head_2_i_U' read by process 'vit_block_top_vit_block_top.grp_dataflow_wrapper_fu_6443.task_compute_attn_U0.grp_do_attn_1_fu_5150.do_attn_U0'");
                                $fdisplay(fp, "Dependence_Channel_path vit_block_top_vit_block_top.grp_dataflow_wrapper_fu_6443.task_compute_attn_U0.grp_do_attn_1_fu_5150.kq_sm_head_2_i_U");
                                $fdisplay(fp, "Dependence_Channel_status FULL");
                            end
                        end
                    end
                    endcase
                end
                35 : begin // for proc 'vit_block_top_vit_block_top.grp_dataflow_wrapper_fu_6443.task_compute_attn_U0.grp_do_attn_1_fu_5150.do_split_U0'
                    case(index2)
                    32: begin //  for dep proc 'vit_block_top_vit_block_top.grp_dataflow_wrapper_fu_6443.task_compute_attn_U0.grp_do_attn_1_fu_5150.do_quant_1_U0'
// for dep channel 'vit_block_top_vit_block_top.grp_dataflow_wrapper_fu_6443.task_compute_attn_U0.grp_do_attn_1_fu_5150.vq_sm_i_U' info is :
// blk sig is {~vit_block_top_vit_block_top_inst.grp_dataflow_wrapper_fu_6443.task_compute_attn_U0.grp_do_attn_1_fu_5150.do_split_U0.vq_sm_blk_n data_FIFO}
                        if ((~grp_dataflow_wrapper_fu_6443.task_compute_attn_U0.grp_do_attn_1_fu_5150.do_split_U0.vq_sm_blk_n)) begin
                            if (~grp_dataflow_wrapper_fu_6443.task_compute_attn_U0.grp_do_attn_1_fu_5150.vq_sm_i_U.if_empty_n) begin
                                $display("//      Blocked by empty input FIFO 'vit_block_top_vit_block_top.grp_dataflow_wrapper_fu_6443.task_compute_attn_U0.grp_do_attn_1_fu_5150.vq_sm_i_U' written by process 'vit_block_top_vit_block_top.grp_dataflow_wrapper_fu_6443.task_compute_attn_U0.grp_do_attn_1_fu_5150.do_quant_1_U0'");
                                $fdisplay(fp, "Dependence_Channel_path vit_block_top_vit_block_top.grp_dataflow_wrapper_fu_6443.task_compute_attn_U0.grp_do_attn_1_fu_5150.vq_sm_i_U");
                                $fdisplay(fp, "Dependence_Channel_status EMPTY");
                            end
                            else if (~grp_dataflow_wrapper_fu_6443.task_compute_attn_U0.grp_do_attn_1_fu_5150.vq_sm_i_U.if_full_n) begin
                                $display("//      Blocked by full output FIFO 'vit_block_top_vit_block_top.grp_dataflow_wrapper_fu_6443.task_compute_attn_U0.grp_do_attn_1_fu_5150.vq_sm_i_U' read by process 'vit_block_top_vit_block_top.grp_dataflow_wrapper_fu_6443.task_compute_attn_U0.grp_do_attn_1_fu_5150.do_quant_1_U0'");
                                $fdisplay(fp, "Dependence_Channel_path vit_block_top_vit_block_top.grp_dataflow_wrapper_fu_6443.task_compute_attn_U0.grp_do_attn_1_fu_5150.vq_sm_i_U");
                                $fdisplay(fp, "Dependence_Channel_status FULL");
                            end
                        end
// for dep channel 'vit_block_top_vit_block_top.grp_dataflow_wrapper_fu_6443.task_compute_attn_U0.grp_do_attn_1_fu_5150.start_for_do_split_U0_U' info is :
// blk sig is {{~vit_block_top_vit_block_top_inst.grp_dataflow_wrapper_fu_6443.task_compute_attn_U0.grp_do_attn_1_fu_5150.start_for_do_split_U0_U.if_empty_n & vit_block_top_vit_block_top_inst.grp_dataflow_wrapper_fu_6443.task_compute_attn_U0.grp_do_attn_1_fu_5150.do_split_U0.ap_idle & ~vit_block_top_vit_block_top_inst.grp_dataflow_wrapper_fu_6443.task_compute_attn_U0.grp_do_attn_1_fu_5150.start_for_do_split_U0_U.if_write} start_FIFO}
                        if ((~grp_dataflow_wrapper_fu_6443.task_compute_attn_U0.grp_do_attn_1_fu_5150.start_for_do_split_U0_U.if_empty_n & grp_dataflow_wrapper_fu_6443.task_compute_attn_U0.grp_do_attn_1_fu_5150.do_split_U0.ap_idle & ~grp_dataflow_wrapper_fu_6443.task_compute_attn_U0.grp_do_attn_1_fu_5150.start_for_do_split_U0_U.if_write)) begin
                            $display("//      Blocked by missing 'ap_start' from start propagation FIFO 'vit_block_top_vit_block_top.grp_dataflow_wrapper_fu_6443.task_compute_attn_U0.grp_do_attn_1_fu_5150.start_for_do_split_U0_U' written by process 'vit_block_top_vit_block_top.grp_dataflow_wrapper_fu_6443.task_compute_attn_U0.grp_do_attn_1_fu_5150.do_quant_1_U0',");
                        end
                    end
                    36: begin //  for dep proc 'vit_block_top_vit_block_top.grp_dataflow_wrapper_fu_6443.task_compute_attn_U0.grp_do_attn_1_fu_5150.do_attn_6_U0'
// for dep channel 'vit_block_top_vit_block_top.grp_dataflow_wrapper_fu_6443.task_compute_attn_U0.grp_do_attn_1_fu_5150.vq_sm_head_0_i_U' info is :
// blk sig is {~vit_block_top_vit_block_top_inst.grp_dataflow_wrapper_fu_6443.task_compute_attn_U0.grp_do_attn_1_fu_5150.do_split_U0.vq_sm_head_0_blk_n data_FIFO}
                        if ((~grp_dataflow_wrapper_fu_6443.task_compute_attn_U0.grp_do_attn_1_fu_5150.do_split_U0.vq_sm_head_0_blk_n)) begin
                            if (~grp_dataflow_wrapper_fu_6443.task_compute_attn_U0.grp_do_attn_1_fu_5150.vq_sm_head_0_i_U.if_empty_n) begin
                                $display("//      Blocked by empty input FIFO 'vit_block_top_vit_block_top.grp_dataflow_wrapper_fu_6443.task_compute_attn_U0.grp_do_attn_1_fu_5150.vq_sm_head_0_i_U' written by process 'vit_block_top_vit_block_top.grp_dataflow_wrapper_fu_6443.task_compute_attn_U0.grp_do_attn_1_fu_5150.do_attn_6_U0'");
                                $fdisplay(fp, "Dependence_Channel_path vit_block_top_vit_block_top.grp_dataflow_wrapper_fu_6443.task_compute_attn_U0.grp_do_attn_1_fu_5150.vq_sm_head_0_i_U");
                                $fdisplay(fp, "Dependence_Channel_status EMPTY");
                            end
                            else if (~grp_dataflow_wrapper_fu_6443.task_compute_attn_U0.grp_do_attn_1_fu_5150.vq_sm_head_0_i_U.if_full_n) begin
                                $display("//      Blocked by full output FIFO 'vit_block_top_vit_block_top.grp_dataflow_wrapper_fu_6443.task_compute_attn_U0.grp_do_attn_1_fu_5150.vq_sm_head_0_i_U' read by process 'vit_block_top_vit_block_top.grp_dataflow_wrapper_fu_6443.task_compute_attn_U0.grp_do_attn_1_fu_5150.do_attn_6_U0'");
                                $fdisplay(fp, "Dependence_Channel_path vit_block_top_vit_block_top.grp_dataflow_wrapper_fu_6443.task_compute_attn_U0.grp_do_attn_1_fu_5150.vq_sm_head_0_i_U");
                                $fdisplay(fp, "Dependence_Channel_status FULL");
                            end
                        end
                    end
                    37: begin //  for dep proc 'vit_block_top_vit_block_top.grp_dataflow_wrapper_fu_6443.task_compute_attn_U0.grp_do_attn_1_fu_5150.do_attn_7_U0'
// for dep channel 'vit_block_top_vit_block_top.grp_dataflow_wrapper_fu_6443.task_compute_attn_U0.grp_do_attn_1_fu_5150.vq_sm_head_1_i_U' info is :
// blk sig is {~vit_block_top_vit_block_top_inst.grp_dataflow_wrapper_fu_6443.task_compute_attn_U0.grp_do_attn_1_fu_5150.do_split_U0.vq_sm_head_1_blk_n data_FIFO}
                        if ((~grp_dataflow_wrapper_fu_6443.task_compute_attn_U0.grp_do_attn_1_fu_5150.do_split_U0.vq_sm_head_1_blk_n)) begin
                            if (~grp_dataflow_wrapper_fu_6443.task_compute_attn_U0.grp_do_attn_1_fu_5150.vq_sm_head_1_i_U.if_empty_n) begin
                                $display("//      Blocked by empty input FIFO 'vit_block_top_vit_block_top.grp_dataflow_wrapper_fu_6443.task_compute_attn_U0.grp_do_attn_1_fu_5150.vq_sm_head_1_i_U' written by process 'vit_block_top_vit_block_top.grp_dataflow_wrapper_fu_6443.task_compute_attn_U0.grp_do_attn_1_fu_5150.do_attn_7_U0'");
                                $fdisplay(fp, "Dependence_Channel_path vit_block_top_vit_block_top.grp_dataflow_wrapper_fu_6443.task_compute_attn_U0.grp_do_attn_1_fu_5150.vq_sm_head_1_i_U");
                                $fdisplay(fp, "Dependence_Channel_status EMPTY");
                            end
                            else if (~grp_dataflow_wrapper_fu_6443.task_compute_attn_U0.grp_do_attn_1_fu_5150.vq_sm_head_1_i_U.if_full_n) begin
                                $display("//      Blocked by full output FIFO 'vit_block_top_vit_block_top.grp_dataflow_wrapper_fu_6443.task_compute_attn_U0.grp_do_attn_1_fu_5150.vq_sm_head_1_i_U' read by process 'vit_block_top_vit_block_top.grp_dataflow_wrapper_fu_6443.task_compute_attn_U0.grp_do_attn_1_fu_5150.do_attn_7_U0'");
                                $fdisplay(fp, "Dependence_Channel_path vit_block_top_vit_block_top.grp_dataflow_wrapper_fu_6443.task_compute_attn_U0.grp_do_attn_1_fu_5150.vq_sm_head_1_i_U");
                                $fdisplay(fp, "Dependence_Channel_status FULL");
                            end
                        end
                    end
                    38: begin //  for dep proc 'vit_block_top_vit_block_top.grp_dataflow_wrapper_fu_6443.task_compute_attn_U0.grp_do_attn_1_fu_5150.do_attn_U0'
// for dep channel 'vit_block_top_vit_block_top.grp_dataflow_wrapper_fu_6443.task_compute_attn_U0.grp_do_attn_1_fu_5150.vq_sm_head_2_i_U' info is :
// blk sig is {~vit_block_top_vit_block_top_inst.grp_dataflow_wrapper_fu_6443.task_compute_attn_U0.grp_do_attn_1_fu_5150.do_split_U0.vq_sm_head_2_blk_n data_FIFO}
                        if ((~grp_dataflow_wrapper_fu_6443.task_compute_attn_U0.grp_do_attn_1_fu_5150.do_split_U0.vq_sm_head_2_blk_n)) begin
                            if (~grp_dataflow_wrapper_fu_6443.task_compute_attn_U0.grp_do_attn_1_fu_5150.vq_sm_head_2_i_U.if_empty_n) begin
                                $display("//      Blocked by empty input FIFO 'vit_block_top_vit_block_top.grp_dataflow_wrapper_fu_6443.task_compute_attn_U0.grp_do_attn_1_fu_5150.vq_sm_head_2_i_U' written by process 'vit_block_top_vit_block_top.grp_dataflow_wrapper_fu_6443.task_compute_attn_U0.grp_do_attn_1_fu_5150.do_attn_U0'");
                                $fdisplay(fp, "Dependence_Channel_path vit_block_top_vit_block_top.grp_dataflow_wrapper_fu_6443.task_compute_attn_U0.grp_do_attn_1_fu_5150.vq_sm_head_2_i_U");
                                $fdisplay(fp, "Dependence_Channel_status EMPTY");
                            end
                            else if (~grp_dataflow_wrapper_fu_6443.task_compute_attn_U0.grp_do_attn_1_fu_5150.vq_sm_head_2_i_U.if_full_n) begin
                                $display("//      Blocked by full output FIFO 'vit_block_top_vit_block_top.grp_dataflow_wrapper_fu_6443.task_compute_attn_U0.grp_do_attn_1_fu_5150.vq_sm_head_2_i_U' read by process 'vit_block_top_vit_block_top.grp_dataflow_wrapper_fu_6443.task_compute_attn_U0.grp_do_attn_1_fu_5150.do_attn_U0'");
                                $fdisplay(fp, "Dependence_Channel_path vit_block_top_vit_block_top.grp_dataflow_wrapper_fu_6443.task_compute_attn_U0.grp_do_attn_1_fu_5150.vq_sm_head_2_i_U");
                                $fdisplay(fp, "Dependence_Channel_status FULL");
                            end
                        end
                    end
                    endcase
                end
                36 : begin // for proc 'vit_block_top_vit_block_top.grp_dataflow_wrapper_fu_6443.task_compute_attn_U0.grp_do_attn_1_fu_5150.do_attn_6_U0'
                    case(index2)
                    33: begin //  for dep proc 'vit_block_top_vit_block_top.grp_dataflow_wrapper_fu_6443.task_compute_attn_U0.grp_do_attn_1_fu_5150.do_split_4_U0'
// for dep channel 'vit_block_top_vit_block_top.grp_dataflow_wrapper_fu_6443.task_compute_attn_U0.grp_do_attn_1_fu_5150.qq_sm_head_0_i_U' info is :
// blk sig is {~vit_block_top_vit_block_top_inst.grp_dataflow_wrapper_fu_6443.task_compute_attn_U0.grp_do_attn_1_fu_5150.do_attn_6_U0.grp_do_attn_6_Pipeline_LOAD_LOOP_VITIS_LOOP_65_1_fu_1073.qq_sm_head_0_blk_n data_FIFO}
                        if ((~grp_dataflow_wrapper_fu_6443.task_compute_attn_U0.grp_do_attn_1_fu_5150.do_attn_6_U0.grp_do_attn_6_Pipeline_LOAD_LOOP_VITIS_LOOP_65_1_fu_1073.qq_sm_head_0_blk_n)) begin
                            if (~grp_dataflow_wrapper_fu_6443.task_compute_attn_U0.grp_do_attn_1_fu_5150.qq_sm_head_0_i_U.if_empty_n) begin
                                $display("//      Blocked by empty input FIFO 'vit_block_top_vit_block_top.grp_dataflow_wrapper_fu_6443.task_compute_attn_U0.grp_do_attn_1_fu_5150.qq_sm_head_0_i_U' written by process 'vit_block_top_vit_block_top.grp_dataflow_wrapper_fu_6443.task_compute_attn_U0.grp_do_attn_1_fu_5150.do_split_4_U0'");
                                $fdisplay(fp, "Dependence_Channel_path vit_block_top_vit_block_top.grp_dataflow_wrapper_fu_6443.task_compute_attn_U0.grp_do_attn_1_fu_5150.qq_sm_head_0_i_U");
                                $fdisplay(fp, "Dependence_Channel_status EMPTY");
                            end
                            else if (~grp_dataflow_wrapper_fu_6443.task_compute_attn_U0.grp_do_attn_1_fu_5150.qq_sm_head_0_i_U.if_full_n) begin
                                $display("//      Blocked by full output FIFO 'vit_block_top_vit_block_top.grp_dataflow_wrapper_fu_6443.task_compute_attn_U0.grp_do_attn_1_fu_5150.qq_sm_head_0_i_U' read by process 'vit_block_top_vit_block_top.grp_dataflow_wrapper_fu_6443.task_compute_attn_U0.grp_do_attn_1_fu_5150.do_split_4_U0'");
                                $fdisplay(fp, "Dependence_Channel_path vit_block_top_vit_block_top.grp_dataflow_wrapper_fu_6443.task_compute_attn_U0.grp_do_attn_1_fu_5150.qq_sm_head_0_i_U");
                                $fdisplay(fp, "Dependence_Channel_status FULL");
                            end
                        end
// for dep channel 'vit_block_top_vit_block_top.grp_dataflow_wrapper_fu_6443.task_compute_attn_U0.grp_do_attn_1_fu_5150.start_for_do_attn_6_U0_U' info is :
// blk sig is {{~vit_block_top_vit_block_top_inst.grp_dataflow_wrapper_fu_6443.task_compute_attn_U0.grp_do_attn_1_fu_5150.start_for_do_attn_6_U0_U.if_empty_n & vit_block_top_vit_block_top_inst.grp_dataflow_wrapper_fu_6443.task_compute_attn_U0.grp_do_attn_1_fu_5150.do_attn_6_U0.ap_idle & ~vit_block_top_vit_block_top_inst.grp_dataflow_wrapper_fu_6443.task_compute_attn_U0.grp_do_attn_1_fu_5150.start_for_do_attn_6_U0_U.if_write} start_FIFO}
                        if ((~grp_dataflow_wrapper_fu_6443.task_compute_attn_U0.grp_do_attn_1_fu_5150.start_for_do_attn_6_U0_U.if_empty_n & grp_dataflow_wrapper_fu_6443.task_compute_attn_U0.grp_do_attn_1_fu_5150.do_attn_6_U0.ap_idle & ~grp_dataflow_wrapper_fu_6443.task_compute_attn_U0.grp_do_attn_1_fu_5150.start_for_do_attn_6_U0_U.if_write)) begin
                            $display("//      Blocked by missing 'ap_start' from start propagation FIFO 'vit_block_top_vit_block_top.grp_dataflow_wrapper_fu_6443.task_compute_attn_U0.grp_do_attn_1_fu_5150.start_for_do_attn_6_U0_U' written by process 'vit_block_top_vit_block_top.grp_dataflow_wrapper_fu_6443.task_compute_attn_U0.grp_do_attn_1_fu_5150.do_split_4_U0',");
                        end
                    end
                    34: begin //  for dep proc 'vit_block_top_vit_block_top.grp_dataflow_wrapper_fu_6443.task_compute_attn_U0.grp_do_attn_1_fu_5150.do_split_5_U0'
// for dep channel 'vit_block_top_vit_block_top.grp_dataflow_wrapper_fu_6443.task_compute_attn_U0.grp_do_attn_1_fu_5150.kq_sm_head_0_i_U' info is :
// blk sig is {~vit_block_top_vit_block_top_inst.grp_dataflow_wrapper_fu_6443.task_compute_attn_U0.grp_do_attn_1_fu_5150.do_attn_6_U0.grp_do_attn_6_Pipeline_LOAD_LOOP_VITIS_LOOP_65_1_fu_1073.kq_sm_head_0_blk_n data_FIFO}
                        if ((~grp_dataflow_wrapper_fu_6443.task_compute_attn_U0.grp_do_attn_1_fu_5150.do_attn_6_U0.grp_do_attn_6_Pipeline_LOAD_LOOP_VITIS_LOOP_65_1_fu_1073.kq_sm_head_0_blk_n)) begin
                            if (~grp_dataflow_wrapper_fu_6443.task_compute_attn_U0.grp_do_attn_1_fu_5150.kq_sm_head_0_i_U.if_empty_n) begin
                                $display("//      Blocked by empty input FIFO 'vit_block_top_vit_block_top.grp_dataflow_wrapper_fu_6443.task_compute_attn_U0.grp_do_attn_1_fu_5150.kq_sm_head_0_i_U' written by process 'vit_block_top_vit_block_top.grp_dataflow_wrapper_fu_6443.task_compute_attn_U0.grp_do_attn_1_fu_5150.do_split_5_U0'");
                                $fdisplay(fp, "Dependence_Channel_path vit_block_top_vit_block_top.grp_dataflow_wrapper_fu_6443.task_compute_attn_U0.grp_do_attn_1_fu_5150.kq_sm_head_0_i_U");
                                $fdisplay(fp, "Dependence_Channel_status EMPTY");
                            end
                            else if (~grp_dataflow_wrapper_fu_6443.task_compute_attn_U0.grp_do_attn_1_fu_5150.kq_sm_head_0_i_U.if_full_n) begin
                                $display("//      Blocked by full output FIFO 'vit_block_top_vit_block_top.grp_dataflow_wrapper_fu_6443.task_compute_attn_U0.grp_do_attn_1_fu_5150.kq_sm_head_0_i_U' read by process 'vit_block_top_vit_block_top.grp_dataflow_wrapper_fu_6443.task_compute_attn_U0.grp_do_attn_1_fu_5150.do_split_5_U0'");
                                $fdisplay(fp, "Dependence_Channel_path vit_block_top_vit_block_top.grp_dataflow_wrapper_fu_6443.task_compute_attn_U0.grp_do_attn_1_fu_5150.kq_sm_head_0_i_U");
                                $fdisplay(fp, "Dependence_Channel_status FULL");
                            end
                        end
                    end
                    35: begin //  for dep proc 'vit_block_top_vit_block_top.grp_dataflow_wrapper_fu_6443.task_compute_attn_U0.grp_do_attn_1_fu_5150.do_split_U0'
// for dep channel 'vit_block_top_vit_block_top.grp_dataflow_wrapper_fu_6443.task_compute_attn_U0.grp_do_attn_1_fu_5150.vq_sm_head_0_i_U' info is :
// blk sig is {~vit_block_top_vit_block_top_inst.grp_dataflow_wrapper_fu_6443.task_compute_attn_U0.grp_do_attn_1_fu_5150.do_attn_6_U0.grp_do_attn_6_Pipeline_LOAD_LOOP_VITIS_LOOP_65_1_fu_1073.vq_sm_head_0_blk_n data_FIFO}
                        if ((~grp_dataflow_wrapper_fu_6443.task_compute_attn_U0.grp_do_attn_1_fu_5150.do_attn_6_U0.grp_do_attn_6_Pipeline_LOAD_LOOP_VITIS_LOOP_65_1_fu_1073.vq_sm_head_0_blk_n)) begin
                            if (~grp_dataflow_wrapper_fu_6443.task_compute_attn_U0.grp_do_attn_1_fu_5150.vq_sm_head_0_i_U.if_empty_n) begin
                                $display("//      Blocked by empty input FIFO 'vit_block_top_vit_block_top.grp_dataflow_wrapper_fu_6443.task_compute_attn_U0.grp_do_attn_1_fu_5150.vq_sm_head_0_i_U' written by process 'vit_block_top_vit_block_top.grp_dataflow_wrapper_fu_6443.task_compute_attn_U0.grp_do_attn_1_fu_5150.do_split_U0'");
                                $fdisplay(fp, "Dependence_Channel_path vit_block_top_vit_block_top.grp_dataflow_wrapper_fu_6443.task_compute_attn_U0.grp_do_attn_1_fu_5150.vq_sm_head_0_i_U");
                                $fdisplay(fp, "Dependence_Channel_status EMPTY");
                            end
                            else if (~grp_dataflow_wrapper_fu_6443.task_compute_attn_U0.grp_do_attn_1_fu_5150.vq_sm_head_0_i_U.if_full_n) begin
                                $display("//      Blocked by full output FIFO 'vit_block_top_vit_block_top.grp_dataflow_wrapper_fu_6443.task_compute_attn_U0.grp_do_attn_1_fu_5150.vq_sm_head_0_i_U' read by process 'vit_block_top_vit_block_top.grp_dataflow_wrapper_fu_6443.task_compute_attn_U0.grp_do_attn_1_fu_5150.do_split_U0'");
                                $fdisplay(fp, "Dependence_Channel_path vit_block_top_vit_block_top.grp_dataflow_wrapper_fu_6443.task_compute_attn_U0.grp_do_attn_1_fu_5150.vq_sm_head_0_i_U");
                                $fdisplay(fp, "Dependence_Channel_status FULL");
                            end
                        end
                    end
                    39: begin //  for dep proc 'vit_block_top_vit_block_top.grp_dataflow_wrapper_fu_6443.task_compute_attn_U0.grp_do_attn_1_fu_5150.do_merge_U0'
// for dep channel 'vit_block_top_vit_block_top.grp_dataflow_wrapper_fu_6443.task_compute_attn_U0.grp_do_attn_1_fu_5150.a_sm_head_0_i_U' info is :
// blk sig is {~vit_block_top_vit_block_top_inst.grp_dataflow_wrapper_fu_6443.task_compute_attn_U0.grp_do_attn_1_fu_5150.do_attn_6_U0.grp_do_attn_6_Pipeline_WRITE_CT_LOOP_fu_1476.a_sm_head_0_blk_n data_FIFO}
                        if ((~grp_dataflow_wrapper_fu_6443.task_compute_attn_U0.grp_do_attn_1_fu_5150.do_attn_6_U0.grp_do_attn_6_Pipeline_WRITE_CT_LOOP_fu_1476.a_sm_head_0_blk_n)) begin
                            if (~grp_dataflow_wrapper_fu_6443.task_compute_attn_U0.grp_do_attn_1_fu_5150.a_sm_head_0_i_U.if_empty_n) begin
                                $display("//      Blocked by empty input FIFO 'vit_block_top_vit_block_top.grp_dataflow_wrapper_fu_6443.task_compute_attn_U0.grp_do_attn_1_fu_5150.a_sm_head_0_i_U' written by process 'vit_block_top_vit_block_top.grp_dataflow_wrapper_fu_6443.task_compute_attn_U0.grp_do_attn_1_fu_5150.do_merge_U0'");
                                $fdisplay(fp, "Dependence_Channel_path vit_block_top_vit_block_top.grp_dataflow_wrapper_fu_6443.task_compute_attn_U0.grp_do_attn_1_fu_5150.a_sm_head_0_i_U");
                                $fdisplay(fp, "Dependence_Channel_status EMPTY");
                            end
                            else if (~grp_dataflow_wrapper_fu_6443.task_compute_attn_U0.grp_do_attn_1_fu_5150.a_sm_head_0_i_U.if_full_n) begin
                                $display("//      Blocked by full output FIFO 'vit_block_top_vit_block_top.grp_dataflow_wrapper_fu_6443.task_compute_attn_U0.grp_do_attn_1_fu_5150.a_sm_head_0_i_U' read by process 'vit_block_top_vit_block_top.grp_dataflow_wrapper_fu_6443.task_compute_attn_U0.grp_do_attn_1_fu_5150.do_merge_U0'");
                                $fdisplay(fp, "Dependence_Channel_path vit_block_top_vit_block_top.grp_dataflow_wrapper_fu_6443.task_compute_attn_U0.grp_do_attn_1_fu_5150.a_sm_head_0_i_U");
                                $fdisplay(fp, "Dependence_Channel_status FULL");
                            end
                        end
// for dep channel 'vit_block_top_vit_block_top.grp_dataflow_wrapper_fu_6443.task_compute_attn_U0.grp_do_attn_1_fu_5150.start_for_do_merge_U0_U' info is :
// blk sig is {{~vit_block_top_vit_block_top_inst.grp_dataflow_wrapper_fu_6443.task_compute_attn_U0.grp_do_attn_1_fu_5150.start_for_do_merge_U0_U.if_full_n & vit_block_top_vit_block_top_inst.grp_dataflow_wrapper_fu_6443.task_compute_attn_U0.grp_do_attn_1_fu_5150.do_attn_6_U0.ap_start & ~vit_block_top_vit_block_top_inst.grp_dataflow_wrapper_fu_6443.task_compute_attn_U0.grp_do_attn_1_fu_5150.do_attn_6_U0.real_start & (trans_in_cnt_23 == trans_out_cnt_23) & ~vit_block_top_vit_block_top_inst.grp_dataflow_wrapper_fu_6443.task_compute_attn_U0.grp_do_attn_1_fu_5150.start_for_do_merge_U0_U.if_read} start_FIFO}
                        if ((~grp_dataflow_wrapper_fu_6443.task_compute_attn_U0.grp_do_attn_1_fu_5150.start_for_do_merge_U0_U.if_full_n & grp_dataflow_wrapper_fu_6443.task_compute_attn_U0.grp_do_attn_1_fu_5150.do_attn_6_U0.ap_start & ~grp_dataflow_wrapper_fu_6443.task_compute_attn_U0.grp_do_attn_1_fu_5150.do_attn_6_U0.real_start & (trans_in_cnt_23 == trans_out_cnt_23) & ~grp_dataflow_wrapper_fu_6443.task_compute_attn_U0.grp_do_attn_1_fu_5150.start_for_do_merge_U0_U.if_read)) begin
                            $display("//      Blocked by full output start propagation FIFO 'vit_block_top_vit_block_top.grp_dataflow_wrapper_fu_6443.task_compute_attn_U0.grp_do_attn_1_fu_5150.start_for_do_merge_U0_U' read by process 'vit_block_top_vit_block_top.grp_dataflow_wrapper_fu_6443.task_compute_attn_U0.grp_do_attn_1_fu_5150.do_merge_U0',");
                        end
                    end
                    endcase
                end
                37 : begin // for proc 'vit_block_top_vit_block_top.grp_dataflow_wrapper_fu_6443.task_compute_attn_U0.grp_do_attn_1_fu_5150.do_attn_7_U0'
                    case(index2)
                    33: begin //  for dep proc 'vit_block_top_vit_block_top.grp_dataflow_wrapper_fu_6443.task_compute_attn_U0.grp_do_attn_1_fu_5150.do_split_4_U0'
// for dep channel 'vit_block_top_vit_block_top.grp_dataflow_wrapper_fu_6443.task_compute_attn_U0.grp_do_attn_1_fu_5150.qq_sm_head_1_i_U' info is :
// blk sig is {~vit_block_top_vit_block_top_inst.grp_dataflow_wrapper_fu_6443.task_compute_attn_U0.grp_do_attn_1_fu_5150.do_attn_7_U0.grp_do_attn_7_Pipeline_LOAD_LOOP_VITIS_LOOP_65_1_fu_1073.qq_sm_head_1_blk_n data_FIFO}
                        if ((~grp_dataflow_wrapper_fu_6443.task_compute_attn_U0.grp_do_attn_1_fu_5150.do_attn_7_U0.grp_do_attn_7_Pipeline_LOAD_LOOP_VITIS_LOOP_65_1_fu_1073.qq_sm_head_1_blk_n)) begin
                            if (~grp_dataflow_wrapper_fu_6443.task_compute_attn_U0.grp_do_attn_1_fu_5150.qq_sm_head_1_i_U.if_empty_n) begin
                                $display("//      Blocked by empty input FIFO 'vit_block_top_vit_block_top.grp_dataflow_wrapper_fu_6443.task_compute_attn_U0.grp_do_attn_1_fu_5150.qq_sm_head_1_i_U' written by process 'vit_block_top_vit_block_top.grp_dataflow_wrapper_fu_6443.task_compute_attn_U0.grp_do_attn_1_fu_5150.do_split_4_U0'");
                                $fdisplay(fp, "Dependence_Channel_path vit_block_top_vit_block_top.grp_dataflow_wrapper_fu_6443.task_compute_attn_U0.grp_do_attn_1_fu_5150.qq_sm_head_1_i_U");
                                $fdisplay(fp, "Dependence_Channel_status EMPTY");
                            end
                            else if (~grp_dataflow_wrapper_fu_6443.task_compute_attn_U0.grp_do_attn_1_fu_5150.qq_sm_head_1_i_U.if_full_n) begin
                                $display("//      Blocked by full output FIFO 'vit_block_top_vit_block_top.grp_dataflow_wrapper_fu_6443.task_compute_attn_U0.grp_do_attn_1_fu_5150.qq_sm_head_1_i_U' read by process 'vit_block_top_vit_block_top.grp_dataflow_wrapper_fu_6443.task_compute_attn_U0.grp_do_attn_1_fu_5150.do_split_4_U0'");
                                $fdisplay(fp, "Dependence_Channel_path vit_block_top_vit_block_top.grp_dataflow_wrapper_fu_6443.task_compute_attn_U0.grp_do_attn_1_fu_5150.qq_sm_head_1_i_U");
                                $fdisplay(fp, "Dependence_Channel_status FULL");
                            end
                        end
// for dep channel 'vit_block_top_vit_block_top.grp_dataflow_wrapper_fu_6443.task_compute_attn_U0.grp_do_attn_1_fu_5150.start_for_do_attn_7_U0_U' info is :
// blk sig is {{~vit_block_top_vit_block_top_inst.grp_dataflow_wrapper_fu_6443.task_compute_attn_U0.grp_do_attn_1_fu_5150.start_for_do_attn_7_U0_U.if_empty_n & vit_block_top_vit_block_top_inst.grp_dataflow_wrapper_fu_6443.task_compute_attn_U0.grp_do_attn_1_fu_5150.do_attn_7_U0.ap_idle & ~vit_block_top_vit_block_top_inst.grp_dataflow_wrapper_fu_6443.task_compute_attn_U0.grp_do_attn_1_fu_5150.start_for_do_attn_7_U0_U.if_write} start_FIFO}
                        if ((~grp_dataflow_wrapper_fu_6443.task_compute_attn_U0.grp_do_attn_1_fu_5150.start_for_do_attn_7_U0_U.if_empty_n & grp_dataflow_wrapper_fu_6443.task_compute_attn_U0.grp_do_attn_1_fu_5150.do_attn_7_U0.ap_idle & ~grp_dataflow_wrapper_fu_6443.task_compute_attn_U0.grp_do_attn_1_fu_5150.start_for_do_attn_7_U0_U.if_write)) begin
                            $display("//      Blocked by missing 'ap_start' from start propagation FIFO 'vit_block_top_vit_block_top.grp_dataflow_wrapper_fu_6443.task_compute_attn_U0.grp_do_attn_1_fu_5150.start_for_do_attn_7_U0_U' written by process 'vit_block_top_vit_block_top.grp_dataflow_wrapper_fu_6443.task_compute_attn_U0.grp_do_attn_1_fu_5150.do_split_4_U0',");
                        end
                    end
                    34: begin //  for dep proc 'vit_block_top_vit_block_top.grp_dataflow_wrapper_fu_6443.task_compute_attn_U0.grp_do_attn_1_fu_5150.do_split_5_U0'
// for dep channel 'vit_block_top_vit_block_top.grp_dataflow_wrapper_fu_6443.task_compute_attn_U0.grp_do_attn_1_fu_5150.kq_sm_head_1_i_U' info is :
// blk sig is {~vit_block_top_vit_block_top_inst.grp_dataflow_wrapper_fu_6443.task_compute_attn_U0.grp_do_attn_1_fu_5150.do_attn_7_U0.grp_do_attn_7_Pipeline_LOAD_LOOP_VITIS_LOOP_65_1_fu_1073.kq_sm_head_1_blk_n data_FIFO}
                        if ((~grp_dataflow_wrapper_fu_6443.task_compute_attn_U0.grp_do_attn_1_fu_5150.do_attn_7_U0.grp_do_attn_7_Pipeline_LOAD_LOOP_VITIS_LOOP_65_1_fu_1073.kq_sm_head_1_blk_n)) begin
                            if (~grp_dataflow_wrapper_fu_6443.task_compute_attn_U0.grp_do_attn_1_fu_5150.kq_sm_head_1_i_U.if_empty_n) begin
                                $display("//      Blocked by empty input FIFO 'vit_block_top_vit_block_top.grp_dataflow_wrapper_fu_6443.task_compute_attn_U0.grp_do_attn_1_fu_5150.kq_sm_head_1_i_U' written by process 'vit_block_top_vit_block_top.grp_dataflow_wrapper_fu_6443.task_compute_attn_U0.grp_do_attn_1_fu_5150.do_split_5_U0'");
                                $fdisplay(fp, "Dependence_Channel_path vit_block_top_vit_block_top.grp_dataflow_wrapper_fu_6443.task_compute_attn_U0.grp_do_attn_1_fu_5150.kq_sm_head_1_i_U");
                                $fdisplay(fp, "Dependence_Channel_status EMPTY");
                            end
                            else if (~grp_dataflow_wrapper_fu_6443.task_compute_attn_U0.grp_do_attn_1_fu_5150.kq_sm_head_1_i_U.if_full_n) begin
                                $display("//      Blocked by full output FIFO 'vit_block_top_vit_block_top.grp_dataflow_wrapper_fu_6443.task_compute_attn_U0.grp_do_attn_1_fu_5150.kq_sm_head_1_i_U' read by process 'vit_block_top_vit_block_top.grp_dataflow_wrapper_fu_6443.task_compute_attn_U0.grp_do_attn_1_fu_5150.do_split_5_U0'");
                                $fdisplay(fp, "Dependence_Channel_path vit_block_top_vit_block_top.grp_dataflow_wrapper_fu_6443.task_compute_attn_U0.grp_do_attn_1_fu_5150.kq_sm_head_1_i_U");
                                $fdisplay(fp, "Dependence_Channel_status FULL");
                            end
                        end
                    end
                    35: begin //  for dep proc 'vit_block_top_vit_block_top.grp_dataflow_wrapper_fu_6443.task_compute_attn_U0.grp_do_attn_1_fu_5150.do_split_U0'
// for dep channel 'vit_block_top_vit_block_top.grp_dataflow_wrapper_fu_6443.task_compute_attn_U0.grp_do_attn_1_fu_5150.vq_sm_head_1_i_U' info is :
// blk sig is {~vit_block_top_vit_block_top_inst.grp_dataflow_wrapper_fu_6443.task_compute_attn_U0.grp_do_attn_1_fu_5150.do_attn_7_U0.grp_do_attn_7_Pipeline_LOAD_LOOP_VITIS_LOOP_65_1_fu_1073.vq_sm_head_1_blk_n data_FIFO}
                        if ((~grp_dataflow_wrapper_fu_6443.task_compute_attn_U0.grp_do_attn_1_fu_5150.do_attn_7_U0.grp_do_attn_7_Pipeline_LOAD_LOOP_VITIS_LOOP_65_1_fu_1073.vq_sm_head_1_blk_n)) begin
                            if (~grp_dataflow_wrapper_fu_6443.task_compute_attn_U0.grp_do_attn_1_fu_5150.vq_sm_head_1_i_U.if_empty_n) begin
                                $display("//      Blocked by empty input FIFO 'vit_block_top_vit_block_top.grp_dataflow_wrapper_fu_6443.task_compute_attn_U0.grp_do_attn_1_fu_5150.vq_sm_head_1_i_U' written by process 'vit_block_top_vit_block_top.grp_dataflow_wrapper_fu_6443.task_compute_attn_U0.grp_do_attn_1_fu_5150.do_split_U0'");
                                $fdisplay(fp, "Dependence_Channel_path vit_block_top_vit_block_top.grp_dataflow_wrapper_fu_6443.task_compute_attn_U0.grp_do_attn_1_fu_5150.vq_sm_head_1_i_U");
                                $fdisplay(fp, "Dependence_Channel_status EMPTY");
                            end
                            else if (~grp_dataflow_wrapper_fu_6443.task_compute_attn_U0.grp_do_attn_1_fu_5150.vq_sm_head_1_i_U.if_full_n) begin
                                $display("//      Blocked by full output FIFO 'vit_block_top_vit_block_top.grp_dataflow_wrapper_fu_6443.task_compute_attn_U0.grp_do_attn_1_fu_5150.vq_sm_head_1_i_U' read by process 'vit_block_top_vit_block_top.grp_dataflow_wrapper_fu_6443.task_compute_attn_U0.grp_do_attn_1_fu_5150.do_split_U0'");
                                $fdisplay(fp, "Dependence_Channel_path vit_block_top_vit_block_top.grp_dataflow_wrapper_fu_6443.task_compute_attn_U0.grp_do_attn_1_fu_5150.vq_sm_head_1_i_U");
                                $fdisplay(fp, "Dependence_Channel_status FULL");
                            end
                        end
                    end
                    39: begin //  for dep proc 'vit_block_top_vit_block_top.grp_dataflow_wrapper_fu_6443.task_compute_attn_U0.grp_do_attn_1_fu_5150.do_merge_U0'
// for dep channel 'vit_block_top_vit_block_top.grp_dataflow_wrapper_fu_6443.task_compute_attn_U0.grp_do_attn_1_fu_5150.a_sm_head_1_i_U' info is :
// blk sig is {~vit_block_top_vit_block_top_inst.grp_dataflow_wrapper_fu_6443.task_compute_attn_U0.grp_do_attn_1_fu_5150.do_attn_7_U0.grp_do_attn_7_Pipeline_WRITE_CT_LOOP_fu_1476.a_sm_head_1_blk_n data_FIFO}
                        if ((~grp_dataflow_wrapper_fu_6443.task_compute_attn_U0.grp_do_attn_1_fu_5150.do_attn_7_U0.grp_do_attn_7_Pipeline_WRITE_CT_LOOP_fu_1476.a_sm_head_1_blk_n)) begin
                            if (~grp_dataflow_wrapper_fu_6443.task_compute_attn_U0.grp_do_attn_1_fu_5150.a_sm_head_1_i_U.if_empty_n) begin
                                $display("//      Blocked by empty input FIFO 'vit_block_top_vit_block_top.grp_dataflow_wrapper_fu_6443.task_compute_attn_U0.grp_do_attn_1_fu_5150.a_sm_head_1_i_U' written by process 'vit_block_top_vit_block_top.grp_dataflow_wrapper_fu_6443.task_compute_attn_U0.grp_do_attn_1_fu_5150.do_merge_U0'");
                                $fdisplay(fp, "Dependence_Channel_path vit_block_top_vit_block_top.grp_dataflow_wrapper_fu_6443.task_compute_attn_U0.grp_do_attn_1_fu_5150.a_sm_head_1_i_U");
                                $fdisplay(fp, "Dependence_Channel_status EMPTY");
                            end
                            else if (~grp_dataflow_wrapper_fu_6443.task_compute_attn_U0.grp_do_attn_1_fu_5150.a_sm_head_1_i_U.if_full_n) begin
                                $display("//      Blocked by full output FIFO 'vit_block_top_vit_block_top.grp_dataflow_wrapper_fu_6443.task_compute_attn_U0.grp_do_attn_1_fu_5150.a_sm_head_1_i_U' read by process 'vit_block_top_vit_block_top.grp_dataflow_wrapper_fu_6443.task_compute_attn_U0.grp_do_attn_1_fu_5150.do_merge_U0'");
                                $fdisplay(fp, "Dependence_Channel_path vit_block_top_vit_block_top.grp_dataflow_wrapper_fu_6443.task_compute_attn_U0.grp_do_attn_1_fu_5150.a_sm_head_1_i_U");
                                $fdisplay(fp, "Dependence_Channel_status FULL");
                            end
                        end
                    end
                    endcase
                end
                38 : begin // for proc 'vit_block_top_vit_block_top.grp_dataflow_wrapper_fu_6443.task_compute_attn_U0.grp_do_attn_1_fu_5150.do_attn_U0'
                    case(index2)
                    33: begin //  for dep proc 'vit_block_top_vit_block_top.grp_dataflow_wrapper_fu_6443.task_compute_attn_U0.grp_do_attn_1_fu_5150.do_split_4_U0'
// for dep channel 'vit_block_top_vit_block_top.grp_dataflow_wrapper_fu_6443.task_compute_attn_U0.grp_do_attn_1_fu_5150.qq_sm_head_2_i_U' info is :
// blk sig is {~vit_block_top_vit_block_top_inst.grp_dataflow_wrapper_fu_6443.task_compute_attn_U0.grp_do_attn_1_fu_5150.do_attn_U0.grp_do_attn_Pipeline_LOAD_LOOP_VITIS_LOOP_65_1_fu_1073.qq_sm_head_2_blk_n data_FIFO}
                        if ((~grp_dataflow_wrapper_fu_6443.task_compute_attn_U0.grp_do_attn_1_fu_5150.do_attn_U0.grp_do_attn_Pipeline_LOAD_LOOP_VITIS_LOOP_65_1_fu_1073.qq_sm_head_2_blk_n)) begin
                            if (~grp_dataflow_wrapper_fu_6443.task_compute_attn_U0.grp_do_attn_1_fu_5150.qq_sm_head_2_i_U.if_empty_n) begin
                                $display("//      Blocked by empty input FIFO 'vit_block_top_vit_block_top.grp_dataflow_wrapper_fu_6443.task_compute_attn_U0.grp_do_attn_1_fu_5150.qq_sm_head_2_i_U' written by process 'vit_block_top_vit_block_top.grp_dataflow_wrapper_fu_6443.task_compute_attn_U0.grp_do_attn_1_fu_5150.do_split_4_U0'");
                                $fdisplay(fp, "Dependence_Channel_path vit_block_top_vit_block_top.grp_dataflow_wrapper_fu_6443.task_compute_attn_U0.grp_do_attn_1_fu_5150.qq_sm_head_2_i_U");
                                $fdisplay(fp, "Dependence_Channel_status EMPTY");
                            end
                            else if (~grp_dataflow_wrapper_fu_6443.task_compute_attn_U0.grp_do_attn_1_fu_5150.qq_sm_head_2_i_U.if_full_n) begin
                                $display("//      Blocked by full output FIFO 'vit_block_top_vit_block_top.grp_dataflow_wrapper_fu_6443.task_compute_attn_U0.grp_do_attn_1_fu_5150.qq_sm_head_2_i_U' read by process 'vit_block_top_vit_block_top.grp_dataflow_wrapper_fu_6443.task_compute_attn_U0.grp_do_attn_1_fu_5150.do_split_4_U0'");
                                $fdisplay(fp, "Dependence_Channel_path vit_block_top_vit_block_top.grp_dataflow_wrapper_fu_6443.task_compute_attn_U0.grp_do_attn_1_fu_5150.qq_sm_head_2_i_U");
                                $fdisplay(fp, "Dependence_Channel_status FULL");
                            end
                        end
// for dep channel 'vit_block_top_vit_block_top.grp_dataflow_wrapper_fu_6443.task_compute_attn_U0.grp_do_attn_1_fu_5150.start_for_do_attn_U0_U' info is :
// blk sig is {{~vit_block_top_vit_block_top_inst.grp_dataflow_wrapper_fu_6443.task_compute_attn_U0.grp_do_attn_1_fu_5150.start_for_do_attn_U0_U.if_empty_n & vit_block_top_vit_block_top_inst.grp_dataflow_wrapper_fu_6443.task_compute_attn_U0.grp_do_attn_1_fu_5150.do_attn_U0.ap_idle & ~vit_block_top_vit_block_top_inst.grp_dataflow_wrapper_fu_6443.task_compute_attn_U0.grp_do_attn_1_fu_5150.start_for_do_attn_U0_U.if_write} start_FIFO}
                        if ((~grp_dataflow_wrapper_fu_6443.task_compute_attn_U0.grp_do_attn_1_fu_5150.start_for_do_attn_U0_U.if_empty_n & grp_dataflow_wrapper_fu_6443.task_compute_attn_U0.grp_do_attn_1_fu_5150.do_attn_U0.ap_idle & ~grp_dataflow_wrapper_fu_6443.task_compute_attn_U0.grp_do_attn_1_fu_5150.start_for_do_attn_U0_U.if_write)) begin
                            $display("//      Blocked by missing 'ap_start' from start propagation FIFO 'vit_block_top_vit_block_top.grp_dataflow_wrapper_fu_6443.task_compute_attn_U0.grp_do_attn_1_fu_5150.start_for_do_attn_U0_U' written by process 'vit_block_top_vit_block_top.grp_dataflow_wrapper_fu_6443.task_compute_attn_U0.grp_do_attn_1_fu_5150.do_split_4_U0',");
                        end
                    end
                    34: begin //  for dep proc 'vit_block_top_vit_block_top.grp_dataflow_wrapper_fu_6443.task_compute_attn_U0.grp_do_attn_1_fu_5150.do_split_5_U0'
// for dep channel 'vit_block_top_vit_block_top.grp_dataflow_wrapper_fu_6443.task_compute_attn_U0.grp_do_attn_1_fu_5150.kq_sm_head_2_i_U' info is :
// blk sig is {~vit_block_top_vit_block_top_inst.grp_dataflow_wrapper_fu_6443.task_compute_attn_U0.grp_do_attn_1_fu_5150.do_attn_U0.grp_do_attn_Pipeline_LOAD_LOOP_VITIS_LOOP_65_1_fu_1073.kq_sm_head_2_blk_n data_FIFO}
                        if ((~grp_dataflow_wrapper_fu_6443.task_compute_attn_U0.grp_do_attn_1_fu_5150.do_attn_U0.grp_do_attn_Pipeline_LOAD_LOOP_VITIS_LOOP_65_1_fu_1073.kq_sm_head_2_blk_n)) begin
                            if (~grp_dataflow_wrapper_fu_6443.task_compute_attn_U0.grp_do_attn_1_fu_5150.kq_sm_head_2_i_U.if_empty_n) begin
                                $display("//      Blocked by empty input FIFO 'vit_block_top_vit_block_top.grp_dataflow_wrapper_fu_6443.task_compute_attn_U0.grp_do_attn_1_fu_5150.kq_sm_head_2_i_U' written by process 'vit_block_top_vit_block_top.grp_dataflow_wrapper_fu_6443.task_compute_attn_U0.grp_do_attn_1_fu_5150.do_split_5_U0'");
                                $fdisplay(fp, "Dependence_Channel_path vit_block_top_vit_block_top.grp_dataflow_wrapper_fu_6443.task_compute_attn_U0.grp_do_attn_1_fu_5150.kq_sm_head_2_i_U");
                                $fdisplay(fp, "Dependence_Channel_status EMPTY");
                            end
                            else if (~grp_dataflow_wrapper_fu_6443.task_compute_attn_U0.grp_do_attn_1_fu_5150.kq_sm_head_2_i_U.if_full_n) begin
                                $display("//      Blocked by full output FIFO 'vit_block_top_vit_block_top.grp_dataflow_wrapper_fu_6443.task_compute_attn_U0.grp_do_attn_1_fu_5150.kq_sm_head_2_i_U' read by process 'vit_block_top_vit_block_top.grp_dataflow_wrapper_fu_6443.task_compute_attn_U0.grp_do_attn_1_fu_5150.do_split_5_U0'");
                                $fdisplay(fp, "Dependence_Channel_path vit_block_top_vit_block_top.grp_dataflow_wrapper_fu_6443.task_compute_attn_U0.grp_do_attn_1_fu_5150.kq_sm_head_2_i_U");
                                $fdisplay(fp, "Dependence_Channel_status FULL");
                            end
                        end
                    end
                    35: begin //  for dep proc 'vit_block_top_vit_block_top.grp_dataflow_wrapper_fu_6443.task_compute_attn_U0.grp_do_attn_1_fu_5150.do_split_U0'
// for dep channel 'vit_block_top_vit_block_top.grp_dataflow_wrapper_fu_6443.task_compute_attn_U0.grp_do_attn_1_fu_5150.vq_sm_head_2_i_U' info is :
// blk sig is {~vit_block_top_vit_block_top_inst.grp_dataflow_wrapper_fu_6443.task_compute_attn_U0.grp_do_attn_1_fu_5150.do_attn_U0.grp_do_attn_Pipeline_LOAD_LOOP_VITIS_LOOP_65_1_fu_1073.vq_sm_head_2_blk_n data_FIFO}
                        if ((~grp_dataflow_wrapper_fu_6443.task_compute_attn_U0.grp_do_attn_1_fu_5150.do_attn_U0.grp_do_attn_Pipeline_LOAD_LOOP_VITIS_LOOP_65_1_fu_1073.vq_sm_head_2_blk_n)) begin
                            if (~grp_dataflow_wrapper_fu_6443.task_compute_attn_U0.grp_do_attn_1_fu_5150.vq_sm_head_2_i_U.if_empty_n) begin
                                $display("//      Blocked by empty input FIFO 'vit_block_top_vit_block_top.grp_dataflow_wrapper_fu_6443.task_compute_attn_U0.grp_do_attn_1_fu_5150.vq_sm_head_2_i_U' written by process 'vit_block_top_vit_block_top.grp_dataflow_wrapper_fu_6443.task_compute_attn_U0.grp_do_attn_1_fu_5150.do_split_U0'");
                                $fdisplay(fp, "Dependence_Channel_path vit_block_top_vit_block_top.grp_dataflow_wrapper_fu_6443.task_compute_attn_U0.grp_do_attn_1_fu_5150.vq_sm_head_2_i_U");
                                $fdisplay(fp, "Dependence_Channel_status EMPTY");
                            end
                            else if (~grp_dataflow_wrapper_fu_6443.task_compute_attn_U0.grp_do_attn_1_fu_5150.vq_sm_head_2_i_U.if_full_n) begin
                                $display("//      Blocked by full output FIFO 'vit_block_top_vit_block_top.grp_dataflow_wrapper_fu_6443.task_compute_attn_U0.grp_do_attn_1_fu_5150.vq_sm_head_2_i_U' read by process 'vit_block_top_vit_block_top.grp_dataflow_wrapper_fu_6443.task_compute_attn_U0.grp_do_attn_1_fu_5150.do_split_U0'");
                                $fdisplay(fp, "Dependence_Channel_path vit_block_top_vit_block_top.grp_dataflow_wrapper_fu_6443.task_compute_attn_U0.grp_do_attn_1_fu_5150.vq_sm_head_2_i_U");
                                $fdisplay(fp, "Dependence_Channel_status FULL");
                            end
                        end
                    end
                    39: begin //  for dep proc 'vit_block_top_vit_block_top.grp_dataflow_wrapper_fu_6443.task_compute_attn_U0.grp_do_attn_1_fu_5150.do_merge_U0'
// for dep channel 'vit_block_top_vit_block_top.grp_dataflow_wrapper_fu_6443.task_compute_attn_U0.grp_do_attn_1_fu_5150.a_sm_head_2_i_U' info is :
// blk sig is {~vit_block_top_vit_block_top_inst.grp_dataflow_wrapper_fu_6443.task_compute_attn_U0.grp_do_attn_1_fu_5150.do_attn_U0.grp_do_attn_Pipeline_WRITE_CT_LOOP_fu_1476.a_sm_head_2_blk_n data_FIFO}
                        if ((~grp_dataflow_wrapper_fu_6443.task_compute_attn_U0.grp_do_attn_1_fu_5150.do_attn_U0.grp_do_attn_Pipeline_WRITE_CT_LOOP_fu_1476.a_sm_head_2_blk_n)) begin
                            if (~grp_dataflow_wrapper_fu_6443.task_compute_attn_U0.grp_do_attn_1_fu_5150.a_sm_head_2_i_U.if_empty_n) begin
                                $display("//      Blocked by empty input FIFO 'vit_block_top_vit_block_top.grp_dataflow_wrapper_fu_6443.task_compute_attn_U0.grp_do_attn_1_fu_5150.a_sm_head_2_i_U' written by process 'vit_block_top_vit_block_top.grp_dataflow_wrapper_fu_6443.task_compute_attn_U0.grp_do_attn_1_fu_5150.do_merge_U0'");
                                $fdisplay(fp, "Dependence_Channel_path vit_block_top_vit_block_top.grp_dataflow_wrapper_fu_6443.task_compute_attn_U0.grp_do_attn_1_fu_5150.a_sm_head_2_i_U");
                                $fdisplay(fp, "Dependence_Channel_status EMPTY");
                            end
                            else if (~grp_dataflow_wrapper_fu_6443.task_compute_attn_U0.grp_do_attn_1_fu_5150.a_sm_head_2_i_U.if_full_n) begin
                                $display("//      Blocked by full output FIFO 'vit_block_top_vit_block_top.grp_dataflow_wrapper_fu_6443.task_compute_attn_U0.grp_do_attn_1_fu_5150.a_sm_head_2_i_U' read by process 'vit_block_top_vit_block_top.grp_dataflow_wrapper_fu_6443.task_compute_attn_U0.grp_do_attn_1_fu_5150.do_merge_U0'");
                                $fdisplay(fp, "Dependence_Channel_path vit_block_top_vit_block_top.grp_dataflow_wrapper_fu_6443.task_compute_attn_U0.grp_do_attn_1_fu_5150.a_sm_head_2_i_U");
                                $fdisplay(fp, "Dependence_Channel_status FULL");
                            end
                        end
                    end
                    endcase
                end
                39 : begin // for proc 'vit_block_top_vit_block_top.grp_dataflow_wrapper_fu_6443.task_compute_attn_U0.grp_do_attn_1_fu_5150.do_merge_U0'
                    case(index2)
                    36: begin //  for dep proc 'vit_block_top_vit_block_top.grp_dataflow_wrapper_fu_6443.task_compute_attn_U0.grp_do_attn_1_fu_5150.do_attn_6_U0'
// for dep channel 'vit_block_top_vit_block_top.grp_dataflow_wrapper_fu_6443.task_compute_attn_U0.grp_do_attn_1_fu_5150.a_sm_head_0_i_U' info is :
// blk sig is {~vit_block_top_vit_block_top_inst.grp_dataflow_wrapper_fu_6443.task_compute_attn_U0.grp_do_attn_1_fu_5150.do_merge_U0.a_sm_head_0_blk_n data_FIFO}
                        if ((~grp_dataflow_wrapper_fu_6443.task_compute_attn_U0.grp_do_attn_1_fu_5150.do_merge_U0.a_sm_head_0_blk_n)) begin
                            if (~grp_dataflow_wrapper_fu_6443.task_compute_attn_U0.grp_do_attn_1_fu_5150.a_sm_head_0_i_U.if_empty_n) begin
                                $display("//      Blocked by empty input FIFO 'vit_block_top_vit_block_top.grp_dataflow_wrapper_fu_6443.task_compute_attn_U0.grp_do_attn_1_fu_5150.a_sm_head_0_i_U' written by process 'vit_block_top_vit_block_top.grp_dataflow_wrapper_fu_6443.task_compute_attn_U0.grp_do_attn_1_fu_5150.do_attn_6_U0'");
                                $fdisplay(fp, "Dependence_Channel_path vit_block_top_vit_block_top.grp_dataflow_wrapper_fu_6443.task_compute_attn_U0.grp_do_attn_1_fu_5150.a_sm_head_0_i_U");
                                $fdisplay(fp, "Dependence_Channel_status EMPTY");
                            end
                            else if (~grp_dataflow_wrapper_fu_6443.task_compute_attn_U0.grp_do_attn_1_fu_5150.a_sm_head_0_i_U.if_full_n) begin
                                $display("//      Blocked by full output FIFO 'vit_block_top_vit_block_top.grp_dataflow_wrapper_fu_6443.task_compute_attn_U0.grp_do_attn_1_fu_5150.a_sm_head_0_i_U' read by process 'vit_block_top_vit_block_top.grp_dataflow_wrapper_fu_6443.task_compute_attn_U0.grp_do_attn_1_fu_5150.do_attn_6_U0'");
                                $fdisplay(fp, "Dependence_Channel_path vit_block_top_vit_block_top.grp_dataflow_wrapper_fu_6443.task_compute_attn_U0.grp_do_attn_1_fu_5150.a_sm_head_0_i_U");
                                $fdisplay(fp, "Dependence_Channel_status FULL");
                            end
                        end
// for dep channel 'vit_block_top_vit_block_top.grp_dataflow_wrapper_fu_6443.task_compute_attn_U0.grp_do_attn_1_fu_5150.start_for_do_merge_U0_U' info is :
// blk sig is {{~vit_block_top_vit_block_top_inst.grp_dataflow_wrapper_fu_6443.task_compute_attn_U0.grp_do_attn_1_fu_5150.start_for_do_merge_U0_U.if_empty_n & vit_block_top_vit_block_top_inst.grp_dataflow_wrapper_fu_6443.task_compute_attn_U0.grp_do_attn_1_fu_5150.do_merge_U0.ap_idle & ~vit_block_top_vit_block_top_inst.grp_dataflow_wrapper_fu_6443.task_compute_attn_U0.grp_do_attn_1_fu_5150.start_for_do_merge_U0_U.if_write} start_FIFO}
                        if ((~grp_dataflow_wrapper_fu_6443.task_compute_attn_U0.grp_do_attn_1_fu_5150.start_for_do_merge_U0_U.if_empty_n & grp_dataflow_wrapper_fu_6443.task_compute_attn_U0.grp_do_attn_1_fu_5150.do_merge_U0.ap_idle & ~grp_dataflow_wrapper_fu_6443.task_compute_attn_U0.grp_do_attn_1_fu_5150.start_for_do_merge_U0_U.if_write)) begin
                            $display("//      Blocked by missing 'ap_start' from start propagation FIFO 'vit_block_top_vit_block_top.grp_dataflow_wrapper_fu_6443.task_compute_attn_U0.grp_do_attn_1_fu_5150.start_for_do_merge_U0_U' written by process 'vit_block_top_vit_block_top.grp_dataflow_wrapper_fu_6443.task_compute_attn_U0.grp_do_attn_1_fu_5150.do_attn_6_U0',");
                        end
                    end
                    37: begin //  for dep proc 'vit_block_top_vit_block_top.grp_dataflow_wrapper_fu_6443.task_compute_attn_U0.grp_do_attn_1_fu_5150.do_attn_7_U0'
// for dep channel 'vit_block_top_vit_block_top.grp_dataflow_wrapper_fu_6443.task_compute_attn_U0.grp_do_attn_1_fu_5150.a_sm_head_1_i_U' info is :
// blk sig is {~vit_block_top_vit_block_top_inst.grp_dataflow_wrapper_fu_6443.task_compute_attn_U0.grp_do_attn_1_fu_5150.do_merge_U0.a_sm_head_1_blk_n data_FIFO}
                        if ((~grp_dataflow_wrapper_fu_6443.task_compute_attn_U0.grp_do_attn_1_fu_5150.do_merge_U0.a_sm_head_1_blk_n)) begin
                            if (~grp_dataflow_wrapper_fu_6443.task_compute_attn_U0.grp_do_attn_1_fu_5150.a_sm_head_1_i_U.if_empty_n) begin
                                $display("//      Blocked by empty input FIFO 'vit_block_top_vit_block_top.grp_dataflow_wrapper_fu_6443.task_compute_attn_U0.grp_do_attn_1_fu_5150.a_sm_head_1_i_U' written by process 'vit_block_top_vit_block_top.grp_dataflow_wrapper_fu_6443.task_compute_attn_U0.grp_do_attn_1_fu_5150.do_attn_7_U0'");
                                $fdisplay(fp, "Dependence_Channel_path vit_block_top_vit_block_top.grp_dataflow_wrapper_fu_6443.task_compute_attn_U0.grp_do_attn_1_fu_5150.a_sm_head_1_i_U");
                                $fdisplay(fp, "Dependence_Channel_status EMPTY");
                            end
                            else if (~grp_dataflow_wrapper_fu_6443.task_compute_attn_U0.grp_do_attn_1_fu_5150.a_sm_head_1_i_U.if_full_n) begin
                                $display("//      Blocked by full output FIFO 'vit_block_top_vit_block_top.grp_dataflow_wrapper_fu_6443.task_compute_attn_U0.grp_do_attn_1_fu_5150.a_sm_head_1_i_U' read by process 'vit_block_top_vit_block_top.grp_dataflow_wrapper_fu_6443.task_compute_attn_U0.grp_do_attn_1_fu_5150.do_attn_7_U0'");
                                $fdisplay(fp, "Dependence_Channel_path vit_block_top_vit_block_top.grp_dataflow_wrapper_fu_6443.task_compute_attn_U0.grp_do_attn_1_fu_5150.a_sm_head_1_i_U");
                                $fdisplay(fp, "Dependence_Channel_status FULL");
                            end
                        end
                    end
                    38: begin //  for dep proc 'vit_block_top_vit_block_top.grp_dataflow_wrapper_fu_6443.task_compute_attn_U0.grp_do_attn_1_fu_5150.do_attn_U0'
// for dep channel 'vit_block_top_vit_block_top.grp_dataflow_wrapper_fu_6443.task_compute_attn_U0.grp_do_attn_1_fu_5150.a_sm_head_2_i_U' info is :
// blk sig is {~vit_block_top_vit_block_top_inst.grp_dataflow_wrapper_fu_6443.task_compute_attn_U0.grp_do_attn_1_fu_5150.do_merge_U0.a_sm_head_2_blk_n data_FIFO}
                        if ((~grp_dataflow_wrapper_fu_6443.task_compute_attn_U0.grp_do_attn_1_fu_5150.do_merge_U0.a_sm_head_2_blk_n)) begin
                            if (~grp_dataflow_wrapper_fu_6443.task_compute_attn_U0.grp_do_attn_1_fu_5150.a_sm_head_2_i_U.if_empty_n) begin
                                $display("//      Blocked by empty input FIFO 'vit_block_top_vit_block_top.grp_dataflow_wrapper_fu_6443.task_compute_attn_U0.grp_do_attn_1_fu_5150.a_sm_head_2_i_U' written by process 'vit_block_top_vit_block_top.grp_dataflow_wrapper_fu_6443.task_compute_attn_U0.grp_do_attn_1_fu_5150.do_attn_U0'");
                                $fdisplay(fp, "Dependence_Channel_path vit_block_top_vit_block_top.grp_dataflow_wrapper_fu_6443.task_compute_attn_U0.grp_do_attn_1_fu_5150.a_sm_head_2_i_U");
                                $fdisplay(fp, "Dependence_Channel_status EMPTY");
                            end
                            else if (~grp_dataflow_wrapper_fu_6443.task_compute_attn_U0.grp_do_attn_1_fu_5150.a_sm_head_2_i_U.if_full_n) begin
                                $display("//      Blocked by full output FIFO 'vit_block_top_vit_block_top.grp_dataflow_wrapper_fu_6443.task_compute_attn_U0.grp_do_attn_1_fu_5150.a_sm_head_2_i_U' read by process 'vit_block_top_vit_block_top.grp_dataflow_wrapper_fu_6443.task_compute_attn_U0.grp_do_attn_1_fu_5150.do_attn_U0'");
                                $fdisplay(fp, "Dependence_Channel_path vit_block_top_vit_block_top.grp_dataflow_wrapper_fu_6443.task_compute_attn_U0.grp_do_attn_1_fu_5150.a_sm_head_2_i_U");
                                $fdisplay(fp, "Dependence_Channel_status FULL");
                            end
                        end
                    end
                    40: begin //  for dep proc 'vit_block_top_vit_block_top.grp_dataflow_wrapper_fu_6443.task_compute_attn_U0.grp_do_attn_1_fu_5150.do_quant_2_U0'
// for dep channel 'vit_block_top_vit_block_top.grp_dataflow_wrapper_fu_6443.task_compute_attn_U0.grp_do_attn_1_fu_5150.a_sm_i_U' info is :
// blk sig is {~vit_block_top_vit_block_top_inst.grp_dataflow_wrapper_fu_6443.task_compute_attn_U0.grp_do_attn_1_fu_5150.do_merge_U0.a_sm_blk_n data_FIFO}
                        if ((~grp_dataflow_wrapper_fu_6443.task_compute_attn_U0.grp_do_attn_1_fu_5150.do_merge_U0.a_sm_blk_n)) begin
                            if (~grp_dataflow_wrapper_fu_6443.task_compute_attn_U0.grp_do_attn_1_fu_5150.a_sm_i_U.if_empty_n) begin
                                $display("//      Blocked by empty input FIFO 'vit_block_top_vit_block_top.grp_dataflow_wrapper_fu_6443.task_compute_attn_U0.grp_do_attn_1_fu_5150.a_sm_i_U' written by process 'vit_block_top_vit_block_top.grp_dataflow_wrapper_fu_6443.task_compute_attn_U0.grp_do_attn_1_fu_5150.do_quant_2_U0'");
                                $fdisplay(fp, "Dependence_Channel_path vit_block_top_vit_block_top.grp_dataflow_wrapper_fu_6443.task_compute_attn_U0.grp_do_attn_1_fu_5150.a_sm_i_U");
                                $fdisplay(fp, "Dependence_Channel_status EMPTY");
                            end
                            else if (~grp_dataflow_wrapper_fu_6443.task_compute_attn_U0.grp_do_attn_1_fu_5150.a_sm_i_U.if_full_n) begin
                                $display("//      Blocked by full output FIFO 'vit_block_top_vit_block_top.grp_dataflow_wrapper_fu_6443.task_compute_attn_U0.grp_do_attn_1_fu_5150.a_sm_i_U' read by process 'vit_block_top_vit_block_top.grp_dataflow_wrapper_fu_6443.task_compute_attn_U0.grp_do_attn_1_fu_5150.do_quant_2_U0'");
                                $fdisplay(fp, "Dependence_Channel_path vit_block_top_vit_block_top.grp_dataflow_wrapper_fu_6443.task_compute_attn_U0.grp_do_attn_1_fu_5150.a_sm_i_U");
                                $fdisplay(fp, "Dependence_Channel_status FULL");
                            end
                        end
// for dep channel 'vit_block_top_vit_block_top.grp_dataflow_wrapper_fu_6443.task_compute_attn_U0.grp_do_attn_1_fu_5150.start_for_do_quant_2_U0_U' info is :
// blk sig is {{~vit_block_top_vit_block_top_inst.grp_dataflow_wrapper_fu_6443.task_compute_attn_U0.grp_do_attn_1_fu_5150.start_for_do_quant_2_U0_U.if_full_n & vit_block_top_vit_block_top_inst.grp_dataflow_wrapper_fu_6443.task_compute_attn_U0.grp_do_attn_1_fu_5150.do_merge_U0.ap_start & ~vit_block_top_vit_block_top_inst.grp_dataflow_wrapper_fu_6443.task_compute_attn_U0.grp_do_attn_1_fu_5150.do_merge_U0.real_start & (trans_in_cnt_24 == trans_out_cnt_24) & ~vit_block_top_vit_block_top_inst.grp_dataflow_wrapper_fu_6443.task_compute_attn_U0.grp_do_attn_1_fu_5150.start_for_do_quant_2_U0_U.if_read} start_FIFO}
                        if ((~grp_dataflow_wrapper_fu_6443.task_compute_attn_U0.grp_do_attn_1_fu_5150.start_for_do_quant_2_U0_U.if_full_n & grp_dataflow_wrapper_fu_6443.task_compute_attn_U0.grp_do_attn_1_fu_5150.do_merge_U0.ap_start & ~grp_dataflow_wrapper_fu_6443.task_compute_attn_U0.grp_do_attn_1_fu_5150.do_merge_U0.real_start & (trans_in_cnt_24 == trans_out_cnt_24) & ~grp_dataflow_wrapper_fu_6443.task_compute_attn_U0.grp_do_attn_1_fu_5150.start_for_do_quant_2_U0_U.if_read)) begin
                            $display("//      Blocked by full output start propagation FIFO 'vit_block_top_vit_block_top.grp_dataflow_wrapper_fu_6443.task_compute_attn_U0.grp_do_attn_1_fu_5150.start_for_do_quant_2_U0_U' read by process 'vit_block_top_vit_block_top.grp_dataflow_wrapper_fu_6443.task_compute_attn_U0.grp_do_attn_1_fu_5150.do_quant_2_U0',");
                        end
                    end
                    endcase
                end
                40 : begin // for proc 'vit_block_top_vit_block_top.grp_dataflow_wrapper_fu_6443.task_compute_attn_U0.grp_do_attn_1_fu_5150.do_quant_2_U0'
                    case(index2)
                    39: begin //  for dep proc 'vit_block_top_vit_block_top.grp_dataflow_wrapper_fu_6443.task_compute_attn_U0.grp_do_attn_1_fu_5150.do_merge_U0'
// for dep channel 'vit_block_top_vit_block_top.grp_dataflow_wrapper_fu_6443.task_compute_attn_U0.grp_do_attn_1_fu_5150.a_sm_i_U' info is :
// blk sig is {~vit_block_top_vit_block_top_inst.grp_dataflow_wrapper_fu_6443.task_compute_attn_U0.grp_do_attn_1_fu_5150.do_quant_2_U0.grp_do_quant_2_Pipeline_TT_LOOP_CT_LOOP_fu_82.a_sm_blk_n data_FIFO}
                        if ((~grp_dataflow_wrapper_fu_6443.task_compute_attn_U0.grp_do_attn_1_fu_5150.do_quant_2_U0.grp_do_quant_2_Pipeline_TT_LOOP_CT_LOOP_fu_82.a_sm_blk_n)) begin
                            if (~grp_dataflow_wrapper_fu_6443.task_compute_attn_U0.grp_do_attn_1_fu_5150.a_sm_i_U.if_empty_n) begin
                                $display("//      Blocked by empty input FIFO 'vit_block_top_vit_block_top.grp_dataflow_wrapper_fu_6443.task_compute_attn_U0.grp_do_attn_1_fu_5150.a_sm_i_U' written by process 'vit_block_top_vit_block_top.grp_dataflow_wrapper_fu_6443.task_compute_attn_U0.grp_do_attn_1_fu_5150.do_merge_U0'");
                                $fdisplay(fp, "Dependence_Channel_path vit_block_top_vit_block_top.grp_dataflow_wrapper_fu_6443.task_compute_attn_U0.grp_do_attn_1_fu_5150.a_sm_i_U");
                                $fdisplay(fp, "Dependence_Channel_status EMPTY");
                            end
                            else if (~grp_dataflow_wrapper_fu_6443.task_compute_attn_U0.grp_do_attn_1_fu_5150.a_sm_i_U.if_full_n) begin
                                $display("//      Blocked by full output FIFO 'vit_block_top_vit_block_top.grp_dataflow_wrapper_fu_6443.task_compute_attn_U0.grp_do_attn_1_fu_5150.a_sm_i_U' read by process 'vit_block_top_vit_block_top.grp_dataflow_wrapper_fu_6443.task_compute_attn_U0.grp_do_attn_1_fu_5150.do_merge_U0'");
                                $fdisplay(fp, "Dependence_Channel_path vit_block_top_vit_block_top.grp_dataflow_wrapper_fu_6443.task_compute_attn_U0.grp_do_attn_1_fu_5150.a_sm_i_U");
                                $fdisplay(fp, "Dependence_Channel_status FULL");
                            end
                        end
// for dep channel 'vit_block_top_vit_block_top.grp_dataflow_wrapper_fu_6443.task_compute_attn_U0.grp_do_attn_1_fu_5150.start_for_do_quant_2_U0_U' info is :
// blk sig is {{~vit_block_top_vit_block_top_inst.grp_dataflow_wrapper_fu_6443.task_compute_attn_U0.grp_do_attn_1_fu_5150.start_for_do_quant_2_U0_U.if_empty_n & vit_block_top_vit_block_top_inst.grp_dataflow_wrapper_fu_6443.task_compute_attn_U0.grp_do_attn_1_fu_5150.do_quant_2_U0.ap_idle & ~vit_block_top_vit_block_top_inst.grp_dataflow_wrapper_fu_6443.task_compute_attn_U0.grp_do_attn_1_fu_5150.start_for_do_quant_2_U0_U.if_write} start_FIFO}
                        if ((~grp_dataflow_wrapper_fu_6443.task_compute_attn_U0.grp_do_attn_1_fu_5150.start_for_do_quant_2_U0_U.if_empty_n & grp_dataflow_wrapper_fu_6443.task_compute_attn_U0.grp_do_attn_1_fu_5150.do_quant_2_U0.ap_idle & ~grp_dataflow_wrapper_fu_6443.task_compute_attn_U0.grp_do_attn_1_fu_5150.start_for_do_quant_2_U0_U.if_write)) begin
                            $display("//      Blocked by missing 'ap_start' from start propagation FIFO 'vit_block_top_vit_block_top.grp_dataflow_wrapper_fu_6443.task_compute_attn_U0.grp_do_attn_1_fu_5150.start_for_do_quant_2_U0_U' written by process 'vit_block_top_vit_block_top.grp_dataflow_wrapper_fu_6443.task_compute_attn_U0.grp_do_attn_1_fu_5150.do_merge_U0',");
                        end
                    end
                    41: begin //  for dep proc 'vit_block_top_vit_block_top.grp_dataflow_wrapper_fu_6443.task_compute_attn_U0.grp_do_attn_1_fu_5150.do_matmul_1_U0'
// for dep channel 'vit_block_top_vit_block_top.grp_dataflow_wrapper_fu_6443.task_compute_attn_U0.grp_do_attn_1_fu_5150.aq_sm_i_U' info is :
// blk sig is {~vit_block_top_vit_block_top_inst.grp_dataflow_wrapper_fu_6443.task_compute_attn_U0.grp_do_attn_1_fu_5150.do_quant_2_U0.grp_do_quant_2_Pipeline_TT_LOOP_CT_LOOP_fu_82.aq_sm_blk_n data_FIFO}
                        if ((~grp_dataflow_wrapper_fu_6443.task_compute_attn_U0.grp_do_attn_1_fu_5150.do_quant_2_U0.grp_do_quant_2_Pipeline_TT_LOOP_CT_LOOP_fu_82.aq_sm_blk_n)) begin
                            if (~grp_dataflow_wrapper_fu_6443.task_compute_attn_U0.grp_do_attn_1_fu_5150.aq_sm_i_U.if_empty_n) begin
                                $display("//      Blocked by empty input FIFO 'vit_block_top_vit_block_top.grp_dataflow_wrapper_fu_6443.task_compute_attn_U0.grp_do_attn_1_fu_5150.aq_sm_i_U' written by process 'vit_block_top_vit_block_top.grp_dataflow_wrapper_fu_6443.task_compute_attn_U0.grp_do_attn_1_fu_5150.do_matmul_1_U0'");
                                $fdisplay(fp, "Dependence_Channel_path vit_block_top_vit_block_top.grp_dataflow_wrapper_fu_6443.task_compute_attn_U0.grp_do_attn_1_fu_5150.aq_sm_i_U");
                                $fdisplay(fp, "Dependence_Channel_status EMPTY");
                            end
                            else if (~grp_dataflow_wrapper_fu_6443.task_compute_attn_U0.grp_do_attn_1_fu_5150.aq_sm_i_U.if_full_n) begin
                                $display("//      Blocked by full output FIFO 'vit_block_top_vit_block_top.grp_dataflow_wrapper_fu_6443.task_compute_attn_U0.grp_do_attn_1_fu_5150.aq_sm_i_U' read by process 'vit_block_top_vit_block_top.grp_dataflow_wrapper_fu_6443.task_compute_attn_U0.grp_do_attn_1_fu_5150.do_matmul_1_U0'");
                                $fdisplay(fp, "Dependence_Channel_path vit_block_top_vit_block_top.grp_dataflow_wrapper_fu_6443.task_compute_attn_U0.grp_do_attn_1_fu_5150.aq_sm_i_U");
                                $fdisplay(fp, "Dependence_Channel_status FULL");
                            end
                        end
// for dep channel 'vit_block_top_vit_block_top.grp_dataflow_wrapper_fu_6443.task_compute_attn_U0.grp_do_attn_1_fu_5150.start_for_do_matmul_1_U0_U' info is :
// blk sig is {{~vit_block_top_vit_block_top_inst.grp_dataflow_wrapper_fu_6443.task_compute_attn_U0.grp_do_attn_1_fu_5150.start_for_do_matmul_1_U0_U.if_full_n & vit_block_top_vit_block_top_inst.grp_dataflow_wrapper_fu_6443.task_compute_attn_U0.grp_do_attn_1_fu_5150.do_quant_2_U0.ap_start & ~vit_block_top_vit_block_top_inst.grp_dataflow_wrapper_fu_6443.task_compute_attn_U0.grp_do_attn_1_fu_5150.do_quant_2_U0.real_start & (trans_in_cnt_25 == trans_out_cnt_25) & ~vit_block_top_vit_block_top_inst.grp_dataflow_wrapper_fu_6443.task_compute_attn_U0.grp_do_attn_1_fu_5150.start_for_do_matmul_1_U0_U.if_read} start_FIFO}
                        if ((~grp_dataflow_wrapper_fu_6443.task_compute_attn_U0.grp_do_attn_1_fu_5150.start_for_do_matmul_1_U0_U.if_full_n & grp_dataflow_wrapper_fu_6443.task_compute_attn_U0.grp_do_attn_1_fu_5150.do_quant_2_U0.ap_start & ~grp_dataflow_wrapper_fu_6443.task_compute_attn_U0.grp_do_attn_1_fu_5150.do_quant_2_U0.real_start & (trans_in_cnt_25 == trans_out_cnt_25) & ~grp_dataflow_wrapper_fu_6443.task_compute_attn_U0.grp_do_attn_1_fu_5150.start_for_do_matmul_1_U0_U.if_read)) begin
                            $display("//      Blocked by full output start propagation FIFO 'vit_block_top_vit_block_top.grp_dataflow_wrapper_fu_6443.task_compute_attn_U0.grp_do_attn_1_fu_5150.start_for_do_matmul_1_U0_U' read by process 'vit_block_top_vit_block_top.grp_dataflow_wrapper_fu_6443.task_compute_attn_U0.grp_do_attn_1_fu_5150.do_matmul_1_U0',");
                        end
                    end
                    42: begin //  for dep proc 'vit_block_top_vit_block_top.grp_dataflow_wrapper_fu_6443.task_compute_attn_U0.grp_do_attn_1_fu_5150.do_matmul_1_U0.do_adapt_1_U0'
// for dep channel 'vit_block_top_vit_block_top.grp_dataflow_wrapper_fu_6443.task_compute_attn_U0.grp_do_attn_1_fu_5150.aq_sm_i_U' info is :
// blk sig is {~vit_block_top_vit_block_top_inst.grp_dataflow_wrapper_fu_6443.task_compute_attn_U0.grp_do_attn_1_fu_5150.do_quant_2_U0.grp_do_quant_2_Pipeline_TT_LOOP_CT_LOOP_fu_82.aq_sm_blk_n data_FIFO}
                        if ((~grp_dataflow_wrapper_fu_6443.task_compute_attn_U0.grp_do_attn_1_fu_5150.do_quant_2_U0.grp_do_quant_2_Pipeline_TT_LOOP_CT_LOOP_fu_82.aq_sm_blk_n)) begin
                            if (~grp_dataflow_wrapper_fu_6443.task_compute_attn_U0.grp_do_attn_1_fu_5150.aq_sm_i_U.if_empty_n) begin
                                $display("//      Blocked by empty input FIFO 'vit_block_top_vit_block_top.grp_dataflow_wrapper_fu_6443.task_compute_attn_U0.grp_do_attn_1_fu_5150.aq_sm_i_U' written by process 'vit_block_top_vit_block_top.grp_dataflow_wrapper_fu_6443.task_compute_attn_U0.grp_do_attn_1_fu_5150.do_matmul_1_U0.do_adapt_1_U0'");
                                $fdisplay(fp, "Dependence_Channel_path vit_block_top_vit_block_top.grp_dataflow_wrapper_fu_6443.task_compute_attn_U0.grp_do_attn_1_fu_5150.aq_sm_i_U");
                                $fdisplay(fp, "Dependence_Channel_status EMPTY");
                            end
                            else if (~grp_dataflow_wrapper_fu_6443.task_compute_attn_U0.grp_do_attn_1_fu_5150.aq_sm_i_U.if_full_n) begin
                                $display("//      Blocked by full output FIFO 'vit_block_top_vit_block_top.grp_dataflow_wrapper_fu_6443.task_compute_attn_U0.grp_do_attn_1_fu_5150.aq_sm_i_U' read by process 'vit_block_top_vit_block_top.grp_dataflow_wrapper_fu_6443.task_compute_attn_U0.grp_do_attn_1_fu_5150.do_matmul_1_U0.do_adapt_1_U0'");
                                $fdisplay(fp, "Dependence_Channel_path vit_block_top_vit_block_top.grp_dataflow_wrapper_fu_6443.task_compute_attn_U0.grp_do_attn_1_fu_5150.aq_sm_i_U");
                                $fdisplay(fp, "Dependence_Channel_status FULL");
                            end
                        end
                    end
                    endcase
                end
                41 : begin // for proc 'vit_block_top_vit_block_top.grp_dataflow_wrapper_fu_6443.task_compute_attn_U0.grp_do_attn_1_fu_5150.do_matmul_1_U0'
                    case(index2)
                    40: begin //  for dep proc 'vit_block_top_vit_block_top.grp_dataflow_wrapper_fu_6443.task_compute_attn_U0.grp_do_attn_1_fu_5150.do_quant_2_U0'
// for dep channel 'vit_block_top_vit_block_top.grp_dataflow_wrapper_fu_6443.task_compute_attn_U0.grp_do_attn_1_fu_5150.aq_sm_i_U' info is :
// blk sig is {~vit_block_top_vit_block_top_inst.grp_dataflow_wrapper_fu_6443.task_compute_attn_U0.grp_do_attn_1_fu_5150.do_matmul_1_U0.do_adapt_1_U0.aq_sm_blk_n data_FIFO}
                        if ((~grp_dataflow_wrapper_fu_6443.task_compute_attn_U0.grp_do_attn_1_fu_5150.do_matmul_1_U0.do_adapt_1_U0.aq_sm_blk_n)) begin
                            if (~grp_dataflow_wrapper_fu_6443.task_compute_attn_U0.grp_do_attn_1_fu_5150.aq_sm_i_U.if_empty_n) begin
                                $display("//      Blocked by empty input FIFO 'vit_block_top_vit_block_top.grp_dataflow_wrapper_fu_6443.task_compute_attn_U0.grp_do_attn_1_fu_5150.aq_sm_i_U' written by process 'vit_block_top_vit_block_top.grp_dataflow_wrapper_fu_6443.task_compute_attn_U0.grp_do_attn_1_fu_5150.do_quant_2_U0'");
                                $fdisplay(fp, "Dependence_Channel_path vit_block_top_vit_block_top.grp_dataflow_wrapper_fu_6443.task_compute_attn_U0.grp_do_attn_1_fu_5150.aq_sm_i_U");
                                $fdisplay(fp, "Dependence_Channel_status EMPTY");
                            end
                            else if (~grp_dataflow_wrapper_fu_6443.task_compute_attn_U0.grp_do_attn_1_fu_5150.aq_sm_i_U.if_full_n) begin
                                $display("//      Blocked by full output FIFO 'vit_block_top_vit_block_top.grp_dataflow_wrapper_fu_6443.task_compute_attn_U0.grp_do_attn_1_fu_5150.aq_sm_i_U' read by process 'vit_block_top_vit_block_top.grp_dataflow_wrapper_fu_6443.task_compute_attn_U0.grp_do_attn_1_fu_5150.do_quant_2_U0'");
                                $fdisplay(fp, "Dependence_Channel_path vit_block_top_vit_block_top.grp_dataflow_wrapper_fu_6443.task_compute_attn_U0.grp_do_attn_1_fu_5150.aq_sm_i_U");
                                $fdisplay(fp, "Dependence_Channel_status FULL");
                            end
                        end
// for dep channel 'vit_block_top_vit_block_top.grp_dataflow_wrapper_fu_6443.task_compute_attn_U0.grp_do_attn_1_fu_5150.start_for_do_matmul_1_U0_U' info is :
// blk sig is {{~vit_block_top_vit_block_top_inst.grp_dataflow_wrapper_fu_6443.task_compute_attn_U0.grp_do_attn_1_fu_5150.start_for_do_matmul_1_U0_U.if_empty_n & vit_block_top_vit_block_top_inst.grp_dataflow_wrapper_fu_6443.task_compute_attn_U0.grp_do_attn_1_fu_5150.do_matmul_1_U0.ap_idle & ~vit_block_top_vit_block_top_inst.grp_dataflow_wrapper_fu_6443.task_compute_attn_U0.grp_do_attn_1_fu_5150.start_for_do_matmul_1_U0_U.if_write} start_FIFO}
                        if ((~grp_dataflow_wrapper_fu_6443.task_compute_attn_U0.grp_do_attn_1_fu_5150.start_for_do_matmul_1_U0_U.if_empty_n & grp_dataflow_wrapper_fu_6443.task_compute_attn_U0.grp_do_attn_1_fu_5150.do_matmul_1_U0.ap_idle & ~grp_dataflow_wrapper_fu_6443.task_compute_attn_U0.grp_do_attn_1_fu_5150.start_for_do_matmul_1_U0_U.if_write)) begin
                            $display("//      Blocked by missing 'ap_start' from start propagation FIFO 'vit_block_top_vit_block_top.grp_dataflow_wrapper_fu_6443.task_compute_attn_U0.grp_do_attn_1_fu_5150.start_for_do_matmul_1_U0_U' written by process 'vit_block_top_vit_block_top.grp_dataflow_wrapper_fu_6443.task_compute_attn_U0.grp_do_attn_1_fu_5150.do_quant_2_U0',");
                        end
                    end
                    46: begin //  for dep proc 'vit_block_top_vit_block_top.grp_dataflow_wrapper_fu_6443.task_compute_attn_U0.grp_do_attn_1_fu_5150.stream_merge_1_U0'
// for dep channel 'vit_block_top_vit_block_top.grp_dataflow_wrapper_fu_6443.task_compute_attn_U0.grp_do_attn_1_fu_5150.o_sm_i_U' info is :
// blk sig is {~vit_block_top_vit_block_top_inst.grp_dataflow_wrapper_fu_6443.task_compute_attn_U0.grp_do_attn_1_fu_5150.do_matmul_1_U0.do_adapt_8_1_U0.o_sm_blk_n data_FIFO}
                        if ((~grp_dataflow_wrapper_fu_6443.task_compute_attn_U0.grp_do_attn_1_fu_5150.do_matmul_1_U0.do_adapt_8_1_U0.o_sm_blk_n)) begin
                            if (~grp_dataflow_wrapper_fu_6443.task_compute_attn_U0.grp_do_attn_1_fu_5150.o_sm_i_U.if_empty_n) begin
                                $display("//      Blocked by empty input FIFO 'vit_block_top_vit_block_top.grp_dataflow_wrapper_fu_6443.task_compute_attn_U0.grp_do_attn_1_fu_5150.o_sm_i_U' written by process 'vit_block_top_vit_block_top.grp_dataflow_wrapper_fu_6443.task_compute_attn_U0.grp_do_attn_1_fu_5150.stream_merge_1_U0'");
                                $fdisplay(fp, "Dependence_Channel_path vit_block_top_vit_block_top.grp_dataflow_wrapper_fu_6443.task_compute_attn_U0.grp_do_attn_1_fu_5150.o_sm_i_U");
                                $fdisplay(fp, "Dependence_Channel_status EMPTY");
                            end
                            else if (~grp_dataflow_wrapper_fu_6443.task_compute_attn_U0.grp_do_attn_1_fu_5150.o_sm_i_U.if_full_n) begin
                                $display("//      Blocked by full output FIFO 'vit_block_top_vit_block_top.grp_dataflow_wrapper_fu_6443.task_compute_attn_U0.grp_do_attn_1_fu_5150.o_sm_i_U' read by process 'vit_block_top_vit_block_top.grp_dataflow_wrapper_fu_6443.task_compute_attn_U0.grp_do_attn_1_fu_5150.stream_merge_1_U0'");
                                $fdisplay(fp, "Dependence_Channel_path vit_block_top_vit_block_top.grp_dataflow_wrapper_fu_6443.task_compute_attn_U0.grp_do_attn_1_fu_5150.o_sm_i_U");
                                $fdisplay(fp, "Dependence_Channel_status FULL");
                            end
                        end
                    end
                    endcase
                end
                42 : begin // for proc 'vit_block_top_vit_block_top.grp_dataflow_wrapper_fu_6443.task_compute_attn_U0.grp_do_attn_1_fu_5150.do_matmul_1_U0.do_adapt_1_U0'
                    case(index2)
                    40: begin //  for dep proc 'vit_block_top_vit_block_top.grp_dataflow_wrapper_fu_6443.task_compute_attn_U0.grp_do_attn_1_fu_5150.do_quant_2_U0'
// for dep channel 'vit_block_top_vit_block_top.grp_dataflow_wrapper_fu_6443.task_compute_attn_U0.grp_do_attn_1_fu_5150.aq_sm_i_U' info is :
// blk sig is {~vit_block_top_vit_block_top_inst.grp_dataflow_wrapper_fu_6443.task_compute_attn_U0.grp_do_attn_1_fu_5150.do_matmul_1_U0.do_adapt_1_U0.aq_sm_blk_n data_FIFO}
                        if ((~grp_dataflow_wrapper_fu_6443.task_compute_attn_U0.grp_do_attn_1_fu_5150.do_matmul_1_U0.do_adapt_1_U0.aq_sm_blk_n)) begin
                            if (~grp_dataflow_wrapper_fu_6443.task_compute_attn_U0.grp_do_attn_1_fu_5150.aq_sm_i_U.if_empty_n) begin
                                $display("//      Blocked by empty input FIFO 'vit_block_top_vit_block_top.grp_dataflow_wrapper_fu_6443.task_compute_attn_U0.grp_do_attn_1_fu_5150.aq_sm_i_U' written by process 'vit_block_top_vit_block_top.grp_dataflow_wrapper_fu_6443.task_compute_attn_U0.grp_do_attn_1_fu_5150.do_quant_2_U0'");
                                $fdisplay(fp, "Dependence_Channel_path vit_block_top_vit_block_top.grp_dataflow_wrapper_fu_6443.task_compute_attn_U0.grp_do_attn_1_fu_5150.aq_sm_i_U");
                                $fdisplay(fp, "Dependence_Channel_status EMPTY");
                            end
                            else if (~grp_dataflow_wrapper_fu_6443.task_compute_attn_U0.grp_do_attn_1_fu_5150.aq_sm_i_U.if_full_n) begin
                                $display("//      Blocked by full output FIFO 'vit_block_top_vit_block_top.grp_dataflow_wrapper_fu_6443.task_compute_attn_U0.grp_do_attn_1_fu_5150.aq_sm_i_U' read by process 'vit_block_top_vit_block_top.grp_dataflow_wrapper_fu_6443.task_compute_attn_U0.grp_do_attn_1_fu_5150.do_quant_2_U0'");
                                $fdisplay(fp, "Dependence_Channel_path vit_block_top_vit_block_top.grp_dataflow_wrapper_fu_6443.task_compute_attn_U0.grp_do_attn_1_fu_5150.aq_sm_i_U");
                                $fdisplay(fp, "Dependence_Channel_status FULL");
                            end
                        end
                    end
                    43: begin //  for dep proc 'vit_block_top_vit_block_top.grp_dataflow_wrapper_fu_6443.task_compute_attn_U0.grp_do_attn_1_fu_5150.do_matmul_1_U0.matmul_step1_cache_window_1_U0'
// for dep channel 'vit_block_top_vit_block_top.grp_dataflow_wrapper_fu_6443.task_compute_attn_U0.grp_do_attn_1_fu_5150.do_matmul_1_U0.adpt_sm_i_U' info is :
// blk sig is {~vit_block_top_vit_block_top_inst.grp_dataflow_wrapper_fu_6443.task_compute_attn_U0.grp_do_attn_1_fu_5150.do_matmul_1_U0.do_adapt_1_U0.adpt_sm_blk_n data_FIFO}
                        if ((~grp_dataflow_wrapper_fu_6443.task_compute_attn_U0.grp_do_attn_1_fu_5150.do_matmul_1_U0.do_adapt_1_U0.adpt_sm_blk_n)) begin
                            if (~grp_dataflow_wrapper_fu_6443.task_compute_attn_U0.grp_do_attn_1_fu_5150.do_matmul_1_U0.adpt_sm_i_U.if_empty_n) begin
                                $display("//      Blocked by empty input FIFO 'vit_block_top_vit_block_top.grp_dataflow_wrapper_fu_6443.task_compute_attn_U0.grp_do_attn_1_fu_5150.do_matmul_1_U0.adpt_sm_i_U' written by process 'vit_block_top_vit_block_top.grp_dataflow_wrapper_fu_6443.task_compute_attn_U0.grp_do_attn_1_fu_5150.do_matmul_1_U0.matmul_step1_cache_window_1_U0'");
                                $fdisplay(fp, "Dependence_Channel_path vit_block_top_vit_block_top.grp_dataflow_wrapper_fu_6443.task_compute_attn_U0.grp_do_attn_1_fu_5150.do_matmul_1_U0.adpt_sm_i_U");
                                $fdisplay(fp, "Dependence_Channel_status EMPTY");
                            end
                            else if (~grp_dataflow_wrapper_fu_6443.task_compute_attn_U0.grp_do_attn_1_fu_5150.do_matmul_1_U0.adpt_sm_i_U.if_full_n) begin
                                $display("//      Blocked by full output FIFO 'vit_block_top_vit_block_top.grp_dataflow_wrapper_fu_6443.task_compute_attn_U0.grp_do_attn_1_fu_5150.do_matmul_1_U0.adpt_sm_i_U' read by process 'vit_block_top_vit_block_top.grp_dataflow_wrapper_fu_6443.task_compute_attn_U0.grp_do_attn_1_fu_5150.do_matmul_1_U0.matmul_step1_cache_window_1_U0'");
                                $fdisplay(fp, "Dependence_Channel_path vit_block_top_vit_block_top.grp_dataflow_wrapper_fu_6443.task_compute_attn_U0.grp_do_attn_1_fu_5150.do_matmul_1_U0.adpt_sm_i_U");
                                $fdisplay(fp, "Dependence_Channel_status FULL");
                            end
                        end
// for dep channel 'vit_block_top_vit_block_top.grp_dataflow_wrapper_fu_6443.task_compute_attn_U0.grp_do_attn_1_fu_5150.do_matmul_1_U0.start_for_matmul_step1_cache_window_1_U0_U' info is :
// blk sig is {{~vit_block_top_vit_block_top_inst.grp_dataflow_wrapper_fu_6443.task_compute_attn_U0.grp_do_attn_1_fu_5150.do_matmul_1_U0.start_for_matmul_step1_cache_window_1_U0_U.if_full_n & vit_block_top_vit_block_top_inst.grp_dataflow_wrapper_fu_6443.task_compute_attn_U0.grp_do_attn_1_fu_5150.do_matmul_1_U0.do_adapt_1_U0.ap_start & ~vit_block_top_vit_block_top_inst.grp_dataflow_wrapper_fu_6443.task_compute_attn_U0.grp_do_attn_1_fu_5150.do_matmul_1_U0.do_adapt_1_U0.real_start & (trans_in_cnt_26 == trans_out_cnt_26) & ~vit_block_top_vit_block_top_inst.grp_dataflow_wrapper_fu_6443.task_compute_attn_U0.grp_do_attn_1_fu_5150.do_matmul_1_U0.start_for_matmul_step1_cache_window_1_U0_U.if_read} start_FIFO}
                        if ((~grp_dataflow_wrapper_fu_6443.task_compute_attn_U0.grp_do_attn_1_fu_5150.do_matmul_1_U0.start_for_matmul_step1_cache_window_1_U0_U.if_full_n & grp_dataflow_wrapper_fu_6443.task_compute_attn_U0.grp_do_attn_1_fu_5150.do_matmul_1_U0.do_adapt_1_U0.ap_start & ~grp_dataflow_wrapper_fu_6443.task_compute_attn_U0.grp_do_attn_1_fu_5150.do_matmul_1_U0.do_adapt_1_U0.real_start & (trans_in_cnt_26 == trans_out_cnt_26) & ~grp_dataflow_wrapper_fu_6443.task_compute_attn_U0.grp_do_attn_1_fu_5150.do_matmul_1_U0.start_for_matmul_step1_cache_window_1_U0_U.if_read)) begin
                            $display("//      Blocked by full output start propagation FIFO 'vit_block_top_vit_block_top.grp_dataflow_wrapper_fu_6443.task_compute_attn_U0.grp_do_attn_1_fu_5150.do_matmul_1_U0.start_for_matmul_step1_cache_window_1_U0_U' read by process 'vit_block_top_vit_block_top.grp_dataflow_wrapper_fu_6443.task_compute_attn_U0.grp_do_attn_1_fu_5150.do_matmul_1_U0.matmul_step1_cache_window_1_U0',");
                        end
                    end
                    endcase
                end
                43 : begin // for proc 'vit_block_top_vit_block_top.grp_dataflow_wrapper_fu_6443.task_compute_attn_U0.grp_do_attn_1_fu_5150.do_matmul_1_U0.matmul_step1_cache_window_1_U0'
                    case(index2)
                    42: begin //  for dep proc 'vit_block_top_vit_block_top.grp_dataflow_wrapper_fu_6443.task_compute_attn_U0.grp_do_attn_1_fu_5150.do_matmul_1_U0.do_adapt_1_U0'
// for dep channel 'vit_block_top_vit_block_top.grp_dataflow_wrapper_fu_6443.task_compute_attn_U0.grp_do_attn_1_fu_5150.do_matmul_1_U0.adpt_sm_i_U' info is :
// blk sig is {~vit_block_top_vit_block_top_inst.grp_dataflow_wrapper_fu_6443.task_compute_attn_U0.grp_do_attn_1_fu_5150.do_matmul_1_U0.matmul_step1_cache_window_1_U0.adpt_sm_blk_n data_FIFO}
                        if ((~grp_dataflow_wrapper_fu_6443.task_compute_attn_U0.grp_do_attn_1_fu_5150.do_matmul_1_U0.matmul_step1_cache_window_1_U0.adpt_sm_blk_n)) begin
                            if (~grp_dataflow_wrapper_fu_6443.task_compute_attn_U0.grp_do_attn_1_fu_5150.do_matmul_1_U0.adpt_sm_i_U.if_empty_n) begin
                                $display("//      Blocked by empty input FIFO 'vit_block_top_vit_block_top.grp_dataflow_wrapper_fu_6443.task_compute_attn_U0.grp_do_attn_1_fu_5150.do_matmul_1_U0.adpt_sm_i_U' written by process 'vit_block_top_vit_block_top.grp_dataflow_wrapper_fu_6443.task_compute_attn_U0.grp_do_attn_1_fu_5150.do_matmul_1_U0.do_adapt_1_U0'");
                                $fdisplay(fp, "Dependence_Channel_path vit_block_top_vit_block_top.grp_dataflow_wrapper_fu_6443.task_compute_attn_U0.grp_do_attn_1_fu_5150.do_matmul_1_U0.adpt_sm_i_U");
                                $fdisplay(fp, "Dependence_Channel_status EMPTY");
                            end
                            else if (~grp_dataflow_wrapper_fu_6443.task_compute_attn_U0.grp_do_attn_1_fu_5150.do_matmul_1_U0.adpt_sm_i_U.if_full_n) begin
                                $display("//      Blocked by full output FIFO 'vit_block_top_vit_block_top.grp_dataflow_wrapper_fu_6443.task_compute_attn_U0.grp_do_attn_1_fu_5150.do_matmul_1_U0.adpt_sm_i_U' read by process 'vit_block_top_vit_block_top.grp_dataflow_wrapper_fu_6443.task_compute_attn_U0.grp_do_attn_1_fu_5150.do_matmul_1_U0.do_adapt_1_U0'");
                                $fdisplay(fp, "Dependence_Channel_path vit_block_top_vit_block_top.grp_dataflow_wrapper_fu_6443.task_compute_attn_U0.grp_do_attn_1_fu_5150.do_matmul_1_U0.adpt_sm_i_U");
                                $fdisplay(fp, "Dependence_Channel_status FULL");
                            end
                        end
// for dep channel 'vit_block_top_vit_block_top.grp_dataflow_wrapper_fu_6443.task_compute_attn_U0.grp_do_attn_1_fu_5150.do_matmul_1_U0.start_for_matmul_step1_cache_window_1_U0_U' info is :
// blk sig is {{~vit_block_top_vit_block_top_inst.grp_dataflow_wrapper_fu_6443.task_compute_attn_U0.grp_do_attn_1_fu_5150.do_matmul_1_U0.start_for_matmul_step1_cache_window_1_U0_U.if_empty_n & vit_block_top_vit_block_top_inst.grp_dataflow_wrapper_fu_6443.task_compute_attn_U0.grp_do_attn_1_fu_5150.do_matmul_1_U0.matmul_step1_cache_window_1_U0.ap_idle & ~vit_block_top_vit_block_top_inst.grp_dataflow_wrapper_fu_6443.task_compute_attn_U0.grp_do_attn_1_fu_5150.do_matmul_1_U0.start_for_matmul_step1_cache_window_1_U0_U.if_write} start_FIFO}
                        if ((~grp_dataflow_wrapper_fu_6443.task_compute_attn_U0.grp_do_attn_1_fu_5150.do_matmul_1_U0.start_for_matmul_step1_cache_window_1_U0_U.if_empty_n & grp_dataflow_wrapper_fu_6443.task_compute_attn_U0.grp_do_attn_1_fu_5150.do_matmul_1_U0.matmul_step1_cache_window_1_U0.ap_idle & ~grp_dataflow_wrapper_fu_6443.task_compute_attn_U0.grp_do_attn_1_fu_5150.do_matmul_1_U0.start_for_matmul_step1_cache_window_1_U0_U.if_write)) begin
                            $display("//      Blocked by missing 'ap_start' from start propagation FIFO 'vit_block_top_vit_block_top.grp_dataflow_wrapper_fu_6443.task_compute_attn_U0.grp_do_attn_1_fu_5150.do_matmul_1_U0.start_for_matmul_step1_cache_window_1_U0_U' written by process 'vit_block_top_vit_block_top.grp_dataflow_wrapper_fu_6443.task_compute_attn_U0.grp_do_attn_1_fu_5150.do_matmul_1_U0.do_adapt_1_U0',");
                        end
                    end
                    44: begin //  for dep proc 'vit_block_top_vit_block_top.grp_dataflow_wrapper_fu_6443.task_compute_attn_U0.grp_do_attn_1_fu_5150.do_matmul_1_U0.matmul_step2_mac_1_U0'
// for dep channel 'vit_block_top_vit_block_top.grp_dataflow_wrapper_fu_6443.task_compute_attn_U0.grp_do_attn_1_fu_5150.do_matmul_1_U0.cache_window_sm_i_U' info is :
// blk sig is {~vit_block_top_vit_block_top_inst.grp_dataflow_wrapper_fu_6443.task_compute_attn_U0.grp_do_attn_1_fu_5150.do_matmul_1_U0.matmul_step1_cache_window_1_U0.cache_window_sm_blk_n data_FIFO}
                        if ((~grp_dataflow_wrapper_fu_6443.task_compute_attn_U0.grp_do_attn_1_fu_5150.do_matmul_1_U0.matmul_step1_cache_window_1_U0.cache_window_sm_blk_n)) begin
                            if (~grp_dataflow_wrapper_fu_6443.task_compute_attn_U0.grp_do_attn_1_fu_5150.do_matmul_1_U0.cache_window_sm_i_U.if_empty_n) begin
                                $display("//      Blocked by empty input FIFO 'vit_block_top_vit_block_top.grp_dataflow_wrapper_fu_6443.task_compute_attn_U0.grp_do_attn_1_fu_5150.do_matmul_1_U0.cache_window_sm_i_U' written by process 'vit_block_top_vit_block_top.grp_dataflow_wrapper_fu_6443.task_compute_attn_U0.grp_do_attn_1_fu_5150.do_matmul_1_U0.matmul_step2_mac_1_U0'");
                                $fdisplay(fp, "Dependence_Channel_path vit_block_top_vit_block_top.grp_dataflow_wrapper_fu_6443.task_compute_attn_U0.grp_do_attn_1_fu_5150.do_matmul_1_U0.cache_window_sm_i_U");
                                $fdisplay(fp, "Dependence_Channel_status EMPTY");
                            end
                            else if (~grp_dataflow_wrapper_fu_6443.task_compute_attn_U0.grp_do_attn_1_fu_5150.do_matmul_1_U0.cache_window_sm_i_U.if_full_n) begin
                                $display("//      Blocked by full output FIFO 'vit_block_top_vit_block_top.grp_dataflow_wrapper_fu_6443.task_compute_attn_U0.grp_do_attn_1_fu_5150.do_matmul_1_U0.cache_window_sm_i_U' read by process 'vit_block_top_vit_block_top.grp_dataflow_wrapper_fu_6443.task_compute_attn_U0.grp_do_attn_1_fu_5150.do_matmul_1_U0.matmul_step2_mac_1_U0'");
                                $fdisplay(fp, "Dependence_Channel_path vit_block_top_vit_block_top.grp_dataflow_wrapper_fu_6443.task_compute_attn_U0.grp_do_attn_1_fu_5150.do_matmul_1_U0.cache_window_sm_i_U");
                                $fdisplay(fp, "Dependence_Channel_status FULL");
                            end
                        end
// for dep channel 'vit_block_top_vit_block_top.grp_dataflow_wrapper_fu_6443.task_compute_attn_U0.grp_do_attn_1_fu_5150.do_matmul_1_U0.start_for_matmul_step2_mac_1_U0_U' info is :
// blk sig is {{~vit_block_top_vit_block_top_inst.grp_dataflow_wrapper_fu_6443.task_compute_attn_U0.grp_do_attn_1_fu_5150.do_matmul_1_U0.start_for_matmul_step2_mac_1_U0_U.if_full_n & vit_block_top_vit_block_top_inst.grp_dataflow_wrapper_fu_6443.task_compute_attn_U0.grp_do_attn_1_fu_5150.do_matmul_1_U0.matmul_step1_cache_window_1_U0.ap_start & ~vit_block_top_vit_block_top_inst.grp_dataflow_wrapper_fu_6443.task_compute_attn_U0.grp_do_attn_1_fu_5150.do_matmul_1_U0.matmul_step1_cache_window_1_U0.real_start & (trans_in_cnt_27 == trans_out_cnt_27) & ~vit_block_top_vit_block_top_inst.grp_dataflow_wrapper_fu_6443.task_compute_attn_U0.grp_do_attn_1_fu_5150.do_matmul_1_U0.start_for_matmul_step2_mac_1_U0_U.if_read} start_FIFO}
                        if ((~grp_dataflow_wrapper_fu_6443.task_compute_attn_U0.grp_do_attn_1_fu_5150.do_matmul_1_U0.start_for_matmul_step2_mac_1_U0_U.if_full_n & grp_dataflow_wrapper_fu_6443.task_compute_attn_U0.grp_do_attn_1_fu_5150.do_matmul_1_U0.matmul_step1_cache_window_1_U0.ap_start & ~grp_dataflow_wrapper_fu_6443.task_compute_attn_U0.grp_do_attn_1_fu_5150.do_matmul_1_U0.matmul_step1_cache_window_1_U0.real_start & (trans_in_cnt_27 == trans_out_cnt_27) & ~grp_dataflow_wrapper_fu_6443.task_compute_attn_U0.grp_do_attn_1_fu_5150.do_matmul_1_U0.start_for_matmul_step2_mac_1_U0_U.if_read)) begin
                            $display("//      Blocked by full output start propagation FIFO 'vit_block_top_vit_block_top.grp_dataflow_wrapper_fu_6443.task_compute_attn_U0.grp_do_attn_1_fu_5150.do_matmul_1_U0.start_for_matmul_step2_mac_1_U0_U' read by process 'vit_block_top_vit_block_top.grp_dataflow_wrapper_fu_6443.task_compute_attn_U0.grp_do_attn_1_fu_5150.do_matmul_1_U0.matmul_step2_mac_1_U0',");
                        end
                    end
                    endcase
                end
                44 : begin // for proc 'vit_block_top_vit_block_top.grp_dataflow_wrapper_fu_6443.task_compute_attn_U0.grp_do_attn_1_fu_5150.do_matmul_1_U0.matmul_step2_mac_1_U0'
                    case(index2)
                    43: begin //  for dep proc 'vit_block_top_vit_block_top.grp_dataflow_wrapper_fu_6443.task_compute_attn_U0.grp_do_attn_1_fu_5150.do_matmul_1_U0.matmul_step1_cache_window_1_U0'
// for dep channel 'vit_block_top_vit_block_top.grp_dataflow_wrapper_fu_6443.task_compute_attn_U0.grp_do_attn_1_fu_5150.do_matmul_1_U0.cache_window_sm_i_U' info is :
// blk sig is {~vit_block_top_vit_block_top_inst.grp_dataflow_wrapper_fu_6443.task_compute_attn_U0.grp_do_attn_1_fu_5150.do_matmul_1_U0.matmul_step2_mac_1_U0.cache_window_sm_blk_n data_FIFO}
                        if ((~grp_dataflow_wrapper_fu_6443.task_compute_attn_U0.grp_do_attn_1_fu_5150.do_matmul_1_U0.matmul_step2_mac_1_U0.cache_window_sm_blk_n)) begin
                            if (~grp_dataflow_wrapper_fu_6443.task_compute_attn_U0.grp_do_attn_1_fu_5150.do_matmul_1_U0.cache_window_sm_i_U.if_empty_n) begin
                                $display("//      Blocked by empty input FIFO 'vit_block_top_vit_block_top.grp_dataflow_wrapper_fu_6443.task_compute_attn_U0.grp_do_attn_1_fu_5150.do_matmul_1_U0.cache_window_sm_i_U' written by process 'vit_block_top_vit_block_top.grp_dataflow_wrapper_fu_6443.task_compute_attn_U0.grp_do_attn_1_fu_5150.do_matmul_1_U0.matmul_step1_cache_window_1_U0'");
                                $fdisplay(fp, "Dependence_Channel_path vit_block_top_vit_block_top.grp_dataflow_wrapper_fu_6443.task_compute_attn_U0.grp_do_attn_1_fu_5150.do_matmul_1_U0.cache_window_sm_i_U");
                                $fdisplay(fp, "Dependence_Channel_status EMPTY");
                            end
                            else if (~grp_dataflow_wrapper_fu_6443.task_compute_attn_U0.grp_do_attn_1_fu_5150.do_matmul_1_U0.cache_window_sm_i_U.if_full_n) begin
                                $display("//      Blocked by full output FIFO 'vit_block_top_vit_block_top.grp_dataflow_wrapper_fu_6443.task_compute_attn_U0.grp_do_attn_1_fu_5150.do_matmul_1_U0.cache_window_sm_i_U' read by process 'vit_block_top_vit_block_top.grp_dataflow_wrapper_fu_6443.task_compute_attn_U0.grp_do_attn_1_fu_5150.do_matmul_1_U0.matmul_step1_cache_window_1_U0'");
                                $fdisplay(fp, "Dependence_Channel_path vit_block_top_vit_block_top.grp_dataflow_wrapper_fu_6443.task_compute_attn_U0.grp_do_attn_1_fu_5150.do_matmul_1_U0.cache_window_sm_i_U");
                                $fdisplay(fp, "Dependence_Channel_status FULL");
                            end
                        end
// for dep channel 'vit_block_top_vit_block_top.grp_dataflow_wrapper_fu_6443.task_compute_attn_U0.grp_do_attn_1_fu_5150.do_matmul_1_U0.start_for_matmul_step2_mac_1_U0_U' info is :
// blk sig is {{~vit_block_top_vit_block_top_inst.grp_dataflow_wrapper_fu_6443.task_compute_attn_U0.grp_do_attn_1_fu_5150.do_matmul_1_U0.start_for_matmul_step2_mac_1_U0_U.if_empty_n & vit_block_top_vit_block_top_inst.grp_dataflow_wrapper_fu_6443.task_compute_attn_U0.grp_do_attn_1_fu_5150.do_matmul_1_U0.matmul_step2_mac_1_U0.ap_idle & ~vit_block_top_vit_block_top_inst.grp_dataflow_wrapper_fu_6443.task_compute_attn_U0.grp_do_attn_1_fu_5150.do_matmul_1_U0.start_for_matmul_step2_mac_1_U0_U.if_write} start_FIFO}
                        if ((~grp_dataflow_wrapper_fu_6443.task_compute_attn_U0.grp_do_attn_1_fu_5150.do_matmul_1_U0.start_for_matmul_step2_mac_1_U0_U.if_empty_n & grp_dataflow_wrapper_fu_6443.task_compute_attn_U0.grp_do_attn_1_fu_5150.do_matmul_1_U0.matmul_step2_mac_1_U0.ap_idle & ~grp_dataflow_wrapper_fu_6443.task_compute_attn_U0.grp_do_attn_1_fu_5150.do_matmul_1_U0.start_for_matmul_step2_mac_1_U0_U.if_write)) begin
                            $display("//      Blocked by missing 'ap_start' from start propagation FIFO 'vit_block_top_vit_block_top.grp_dataflow_wrapper_fu_6443.task_compute_attn_U0.grp_do_attn_1_fu_5150.do_matmul_1_U0.start_for_matmul_step2_mac_1_U0_U' written by process 'vit_block_top_vit_block_top.grp_dataflow_wrapper_fu_6443.task_compute_attn_U0.grp_do_attn_1_fu_5150.do_matmul_1_U0.matmul_step1_cache_window_1_U0',");
                        end
                    end
                    45: begin //  for dep proc 'vit_block_top_vit_block_top.grp_dataflow_wrapper_fu_6443.task_compute_attn_U0.grp_do_attn_1_fu_5150.do_matmul_1_U0.do_adapt_8_1_U0'
// for dep channel 'vit_block_top_vit_block_top.grp_dataflow_wrapper_fu_6443.task_compute_attn_U0.grp_do_attn_1_fu_5150.do_matmul_1_U0.mac_sm_i_U' info is :
// blk sig is {~vit_block_top_vit_block_top_inst.grp_dataflow_wrapper_fu_6443.task_compute_attn_U0.grp_do_attn_1_fu_5150.do_matmul_1_U0.matmul_step2_mac_1_U0.mac_sm_blk_n data_FIFO}
                        if ((~grp_dataflow_wrapper_fu_6443.task_compute_attn_U0.grp_do_attn_1_fu_5150.do_matmul_1_U0.matmul_step2_mac_1_U0.mac_sm_blk_n)) begin
                            if (~grp_dataflow_wrapper_fu_6443.task_compute_attn_U0.grp_do_attn_1_fu_5150.do_matmul_1_U0.mac_sm_i_U.if_empty_n) begin
                                $display("//      Blocked by empty input FIFO 'vit_block_top_vit_block_top.grp_dataflow_wrapper_fu_6443.task_compute_attn_U0.grp_do_attn_1_fu_5150.do_matmul_1_U0.mac_sm_i_U' written by process 'vit_block_top_vit_block_top.grp_dataflow_wrapper_fu_6443.task_compute_attn_U0.grp_do_attn_1_fu_5150.do_matmul_1_U0.do_adapt_8_1_U0'");
                                $fdisplay(fp, "Dependence_Channel_path vit_block_top_vit_block_top.grp_dataflow_wrapper_fu_6443.task_compute_attn_U0.grp_do_attn_1_fu_5150.do_matmul_1_U0.mac_sm_i_U");
                                $fdisplay(fp, "Dependence_Channel_status EMPTY");
                            end
                            else if (~grp_dataflow_wrapper_fu_6443.task_compute_attn_U0.grp_do_attn_1_fu_5150.do_matmul_1_U0.mac_sm_i_U.if_full_n) begin
                                $display("//      Blocked by full output FIFO 'vit_block_top_vit_block_top.grp_dataflow_wrapper_fu_6443.task_compute_attn_U0.grp_do_attn_1_fu_5150.do_matmul_1_U0.mac_sm_i_U' read by process 'vit_block_top_vit_block_top.grp_dataflow_wrapper_fu_6443.task_compute_attn_U0.grp_do_attn_1_fu_5150.do_matmul_1_U0.do_adapt_8_1_U0'");
                                $fdisplay(fp, "Dependence_Channel_path vit_block_top_vit_block_top.grp_dataflow_wrapper_fu_6443.task_compute_attn_U0.grp_do_attn_1_fu_5150.do_matmul_1_U0.mac_sm_i_U");
                                $fdisplay(fp, "Dependence_Channel_status FULL");
                            end
                        end
// for dep channel 'vit_block_top_vit_block_top.grp_dataflow_wrapper_fu_6443.task_compute_attn_U0.grp_do_attn_1_fu_5150.do_matmul_1_U0.start_for_do_adapt_8_1_U0_U' info is :
// blk sig is {{~vit_block_top_vit_block_top_inst.grp_dataflow_wrapper_fu_6443.task_compute_attn_U0.grp_do_attn_1_fu_5150.do_matmul_1_U0.start_for_do_adapt_8_1_U0_U.if_full_n & vit_block_top_vit_block_top_inst.grp_dataflow_wrapper_fu_6443.task_compute_attn_U0.grp_do_attn_1_fu_5150.do_matmul_1_U0.matmul_step2_mac_1_U0.ap_start & ~vit_block_top_vit_block_top_inst.grp_dataflow_wrapper_fu_6443.task_compute_attn_U0.grp_do_attn_1_fu_5150.do_matmul_1_U0.matmul_step2_mac_1_U0.real_start & (trans_in_cnt_28 == trans_out_cnt_28) & ~vit_block_top_vit_block_top_inst.grp_dataflow_wrapper_fu_6443.task_compute_attn_U0.grp_do_attn_1_fu_5150.do_matmul_1_U0.start_for_do_adapt_8_1_U0_U.if_read} start_FIFO}
                        if ((~grp_dataflow_wrapper_fu_6443.task_compute_attn_U0.grp_do_attn_1_fu_5150.do_matmul_1_U0.start_for_do_adapt_8_1_U0_U.if_full_n & grp_dataflow_wrapper_fu_6443.task_compute_attn_U0.grp_do_attn_1_fu_5150.do_matmul_1_U0.matmul_step2_mac_1_U0.ap_start & ~grp_dataflow_wrapper_fu_6443.task_compute_attn_U0.grp_do_attn_1_fu_5150.do_matmul_1_U0.matmul_step2_mac_1_U0.real_start & (trans_in_cnt_28 == trans_out_cnt_28) & ~grp_dataflow_wrapper_fu_6443.task_compute_attn_U0.grp_do_attn_1_fu_5150.do_matmul_1_U0.start_for_do_adapt_8_1_U0_U.if_read)) begin
                            $display("//      Blocked by full output start propagation FIFO 'vit_block_top_vit_block_top.grp_dataflow_wrapper_fu_6443.task_compute_attn_U0.grp_do_attn_1_fu_5150.do_matmul_1_U0.start_for_do_adapt_8_1_U0_U' read by process 'vit_block_top_vit_block_top.grp_dataflow_wrapper_fu_6443.task_compute_attn_U0.grp_do_attn_1_fu_5150.do_matmul_1_U0.do_adapt_8_1_U0',");
                        end
                    end
                    endcase
                end
                45 : begin // for proc 'vit_block_top_vit_block_top.grp_dataflow_wrapper_fu_6443.task_compute_attn_U0.grp_do_attn_1_fu_5150.do_matmul_1_U0.do_adapt_8_1_U0'
                    case(index2)
                    44: begin //  for dep proc 'vit_block_top_vit_block_top.grp_dataflow_wrapper_fu_6443.task_compute_attn_U0.grp_do_attn_1_fu_5150.do_matmul_1_U0.matmul_step2_mac_1_U0'
// for dep channel 'vit_block_top_vit_block_top.grp_dataflow_wrapper_fu_6443.task_compute_attn_U0.grp_do_attn_1_fu_5150.do_matmul_1_U0.mac_sm_i_U' info is :
// blk sig is {~vit_block_top_vit_block_top_inst.grp_dataflow_wrapper_fu_6443.task_compute_attn_U0.grp_do_attn_1_fu_5150.do_matmul_1_U0.do_adapt_8_1_U0.mac_sm_blk_n data_FIFO}
                        if ((~grp_dataflow_wrapper_fu_6443.task_compute_attn_U0.grp_do_attn_1_fu_5150.do_matmul_1_U0.do_adapt_8_1_U0.mac_sm_blk_n)) begin
                            if (~grp_dataflow_wrapper_fu_6443.task_compute_attn_U0.grp_do_attn_1_fu_5150.do_matmul_1_U0.mac_sm_i_U.if_empty_n) begin
                                $display("//      Blocked by empty input FIFO 'vit_block_top_vit_block_top.grp_dataflow_wrapper_fu_6443.task_compute_attn_U0.grp_do_attn_1_fu_5150.do_matmul_1_U0.mac_sm_i_U' written by process 'vit_block_top_vit_block_top.grp_dataflow_wrapper_fu_6443.task_compute_attn_U0.grp_do_attn_1_fu_5150.do_matmul_1_U0.matmul_step2_mac_1_U0'");
                                $fdisplay(fp, "Dependence_Channel_path vit_block_top_vit_block_top.grp_dataflow_wrapper_fu_6443.task_compute_attn_U0.grp_do_attn_1_fu_5150.do_matmul_1_U0.mac_sm_i_U");
                                $fdisplay(fp, "Dependence_Channel_status EMPTY");
                            end
                            else if (~grp_dataflow_wrapper_fu_6443.task_compute_attn_U0.grp_do_attn_1_fu_5150.do_matmul_1_U0.mac_sm_i_U.if_full_n) begin
                                $display("//      Blocked by full output FIFO 'vit_block_top_vit_block_top.grp_dataflow_wrapper_fu_6443.task_compute_attn_U0.grp_do_attn_1_fu_5150.do_matmul_1_U0.mac_sm_i_U' read by process 'vit_block_top_vit_block_top.grp_dataflow_wrapper_fu_6443.task_compute_attn_U0.grp_do_attn_1_fu_5150.do_matmul_1_U0.matmul_step2_mac_1_U0'");
                                $fdisplay(fp, "Dependence_Channel_path vit_block_top_vit_block_top.grp_dataflow_wrapper_fu_6443.task_compute_attn_U0.grp_do_attn_1_fu_5150.do_matmul_1_U0.mac_sm_i_U");
                                $fdisplay(fp, "Dependence_Channel_status FULL");
                            end
                        end
// for dep channel 'vit_block_top_vit_block_top.grp_dataflow_wrapper_fu_6443.task_compute_attn_U0.grp_do_attn_1_fu_5150.do_matmul_1_U0.start_for_do_adapt_8_1_U0_U' info is :
// blk sig is {{~vit_block_top_vit_block_top_inst.grp_dataflow_wrapper_fu_6443.task_compute_attn_U0.grp_do_attn_1_fu_5150.do_matmul_1_U0.start_for_do_adapt_8_1_U0_U.if_empty_n & vit_block_top_vit_block_top_inst.grp_dataflow_wrapper_fu_6443.task_compute_attn_U0.grp_do_attn_1_fu_5150.do_matmul_1_U0.do_adapt_8_1_U0.ap_idle & ~vit_block_top_vit_block_top_inst.grp_dataflow_wrapper_fu_6443.task_compute_attn_U0.grp_do_attn_1_fu_5150.do_matmul_1_U0.start_for_do_adapt_8_1_U0_U.if_write} start_FIFO}
                        if ((~grp_dataflow_wrapper_fu_6443.task_compute_attn_U0.grp_do_attn_1_fu_5150.do_matmul_1_U0.start_for_do_adapt_8_1_U0_U.if_empty_n & grp_dataflow_wrapper_fu_6443.task_compute_attn_U0.grp_do_attn_1_fu_5150.do_matmul_1_U0.do_adapt_8_1_U0.ap_idle & ~grp_dataflow_wrapper_fu_6443.task_compute_attn_U0.grp_do_attn_1_fu_5150.do_matmul_1_U0.start_for_do_adapt_8_1_U0_U.if_write)) begin
                            $display("//      Blocked by missing 'ap_start' from start propagation FIFO 'vit_block_top_vit_block_top.grp_dataflow_wrapper_fu_6443.task_compute_attn_U0.grp_do_attn_1_fu_5150.do_matmul_1_U0.start_for_do_adapt_8_1_U0_U' written by process 'vit_block_top_vit_block_top.grp_dataflow_wrapper_fu_6443.task_compute_attn_U0.grp_do_attn_1_fu_5150.do_matmul_1_U0.matmul_step2_mac_1_U0',");
                        end
                    end
                    46: begin //  for dep proc 'vit_block_top_vit_block_top.grp_dataflow_wrapper_fu_6443.task_compute_attn_U0.grp_do_attn_1_fu_5150.stream_merge_1_U0'
// for dep channel 'vit_block_top_vit_block_top.grp_dataflow_wrapper_fu_6443.task_compute_attn_U0.grp_do_attn_1_fu_5150.o_sm_i_U' info is :
// blk sig is {~vit_block_top_vit_block_top_inst.grp_dataflow_wrapper_fu_6443.task_compute_attn_U0.grp_do_attn_1_fu_5150.do_matmul_1_U0.do_adapt_8_1_U0.o_sm_blk_n data_FIFO}
                        if ((~grp_dataflow_wrapper_fu_6443.task_compute_attn_U0.grp_do_attn_1_fu_5150.do_matmul_1_U0.do_adapt_8_1_U0.o_sm_blk_n)) begin
                            if (~grp_dataflow_wrapper_fu_6443.task_compute_attn_U0.grp_do_attn_1_fu_5150.o_sm_i_U.if_empty_n) begin
                                $display("//      Blocked by empty input FIFO 'vit_block_top_vit_block_top.grp_dataflow_wrapper_fu_6443.task_compute_attn_U0.grp_do_attn_1_fu_5150.o_sm_i_U' written by process 'vit_block_top_vit_block_top.grp_dataflow_wrapper_fu_6443.task_compute_attn_U0.grp_do_attn_1_fu_5150.stream_merge_1_U0'");
                                $fdisplay(fp, "Dependence_Channel_path vit_block_top_vit_block_top.grp_dataflow_wrapper_fu_6443.task_compute_attn_U0.grp_do_attn_1_fu_5150.o_sm_i_U");
                                $fdisplay(fp, "Dependence_Channel_status EMPTY");
                            end
                            else if (~grp_dataflow_wrapper_fu_6443.task_compute_attn_U0.grp_do_attn_1_fu_5150.o_sm_i_U.if_full_n) begin
                                $display("//      Blocked by full output FIFO 'vit_block_top_vit_block_top.grp_dataflow_wrapper_fu_6443.task_compute_attn_U0.grp_do_attn_1_fu_5150.o_sm_i_U' read by process 'vit_block_top_vit_block_top.grp_dataflow_wrapper_fu_6443.task_compute_attn_U0.grp_do_attn_1_fu_5150.stream_merge_1_U0'");
                                $fdisplay(fp, "Dependence_Channel_path vit_block_top_vit_block_top.grp_dataflow_wrapper_fu_6443.task_compute_attn_U0.grp_do_attn_1_fu_5150.o_sm_i_U");
                                $fdisplay(fp, "Dependence_Channel_status FULL");
                            end
                        end
                    end
                    endcase
                end
                46 : begin // for proc 'vit_block_top_vit_block_top.grp_dataflow_wrapper_fu_6443.task_compute_attn_U0.grp_do_attn_1_fu_5150.stream_merge_1_U0'
                    case(index2)
                    12: begin //  for dep proc 'vit_block_top_vit_block_top.grp_dataflow_wrapper_fu_6443.task_compute_attn_U0.grp_do_attn_1_fu_5150.do_adapt_7_U0'
// for dep channel 'vit_block_top_vit_block_top.grp_dataflow_wrapper_fu_6443.task_compute_attn_U0.grp_do_attn_1_fu_5150.resi_o_sm_i_U' info is :
// blk sig is {~vit_block_top_vit_block_top_inst.grp_dataflow_wrapper_fu_6443.task_compute_attn_U0.grp_do_attn_1_fu_5150.stream_merge_1_U0.grp_stream_merge_1_Pipeline_VITIS_LOOP_554_1_VITIS_LOOP_555_2_fu_34.resi_o_sm_blk_n data_FIFO}
                        if ((~grp_dataflow_wrapper_fu_6443.task_compute_attn_U0.grp_do_attn_1_fu_5150.stream_merge_1_U0.grp_stream_merge_1_Pipeline_VITIS_LOOP_554_1_VITIS_LOOP_555_2_fu_34.resi_o_sm_blk_n)) begin
                            if (~grp_dataflow_wrapper_fu_6443.task_compute_attn_U0.grp_do_attn_1_fu_5150.resi_o_sm_i_U.if_empty_n) begin
                                $display("//      Blocked by empty input FIFO 'vit_block_top_vit_block_top.grp_dataflow_wrapper_fu_6443.task_compute_attn_U0.grp_do_attn_1_fu_5150.resi_o_sm_i_U' written by process 'vit_block_top_vit_block_top.grp_dataflow_wrapper_fu_6443.task_compute_attn_U0.grp_do_attn_1_fu_5150.do_adapt_7_U0'");
                                $fdisplay(fp, "Dependence_Channel_path vit_block_top_vit_block_top.grp_dataflow_wrapper_fu_6443.task_compute_attn_U0.grp_do_attn_1_fu_5150.resi_o_sm_i_U");
                                $fdisplay(fp, "Dependence_Channel_status EMPTY");
                            end
                            else if (~grp_dataflow_wrapper_fu_6443.task_compute_attn_U0.grp_do_attn_1_fu_5150.resi_o_sm_i_U.if_full_n) begin
                                $display("//      Blocked by full output FIFO 'vit_block_top_vit_block_top.grp_dataflow_wrapper_fu_6443.task_compute_attn_U0.grp_do_attn_1_fu_5150.resi_o_sm_i_U' read by process 'vit_block_top_vit_block_top.grp_dataflow_wrapper_fu_6443.task_compute_attn_U0.grp_do_attn_1_fu_5150.do_adapt_7_U0'");
                                $fdisplay(fp, "Dependence_Channel_path vit_block_top_vit_block_top.grp_dataflow_wrapper_fu_6443.task_compute_attn_U0.grp_do_attn_1_fu_5150.resi_o_sm_i_U");
                                $fdisplay(fp, "Dependence_Channel_status FULL");
                            end
                        end
// for dep channel 'vit_block_top_vit_block_top.grp_dataflow_wrapper_fu_6443.task_compute_attn_U0.grp_do_attn_1_fu_5150.start_for_stream_merge_1_U0_U' info is :
// blk sig is {{~vit_block_top_vit_block_top_inst.grp_dataflow_wrapper_fu_6443.task_compute_attn_U0.grp_do_attn_1_fu_5150.start_for_stream_merge_1_U0_U.if_empty_n & vit_block_top_vit_block_top_inst.grp_dataflow_wrapper_fu_6443.task_compute_attn_U0.grp_do_attn_1_fu_5150.stream_merge_1_U0.ap_idle & ~vit_block_top_vit_block_top_inst.grp_dataflow_wrapper_fu_6443.task_compute_attn_U0.grp_do_attn_1_fu_5150.start_for_stream_merge_1_U0_U.if_write} start_FIFO}
                        if ((~grp_dataflow_wrapper_fu_6443.task_compute_attn_U0.grp_do_attn_1_fu_5150.start_for_stream_merge_1_U0_U.if_empty_n & grp_dataflow_wrapper_fu_6443.task_compute_attn_U0.grp_do_attn_1_fu_5150.stream_merge_1_U0.ap_idle & ~grp_dataflow_wrapper_fu_6443.task_compute_attn_U0.grp_do_attn_1_fu_5150.start_for_stream_merge_1_U0_U.if_write)) begin
                            $display("//      Blocked by missing 'ap_start' from start propagation FIFO 'vit_block_top_vit_block_top.grp_dataflow_wrapper_fu_6443.task_compute_attn_U0.grp_do_attn_1_fu_5150.start_for_stream_merge_1_U0_U' written by process 'vit_block_top_vit_block_top.grp_dataflow_wrapper_fu_6443.task_compute_attn_U0.grp_do_attn_1_fu_5150.do_adapt_7_U0',");
                        end
                    end
                    41: begin //  for dep proc 'vit_block_top_vit_block_top.grp_dataflow_wrapper_fu_6443.task_compute_attn_U0.grp_do_attn_1_fu_5150.do_matmul_1_U0'
// for dep channel 'vit_block_top_vit_block_top.grp_dataflow_wrapper_fu_6443.task_compute_attn_U0.grp_do_attn_1_fu_5150.o_sm_i_U' info is :
// blk sig is {~vit_block_top_vit_block_top_inst.grp_dataflow_wrapper_fu_6443.task_compute_attn_U0.grp_do_attn_1_fu_5150.stream_merge_1_U0.grp_stream_merge_1_Pipeline_VITIS_LOOP_554_1_VITIS_LOOP_555_2_fu_34.o_sm_blk_n data_FIFO}
                        if ((~grp_dataflow_wrapper_fu_6443.task_compute_attn_U0.grp_do_attn_1_fu_5150.stream_merge_1_U0.grp_stream_merge_1_Pipeline_VITIS_LOOP_554_1_VITIS_LOOP_555_2_fu_34.o_sm_blk_n)) begin
                            if (~grp_dataflow_wrapper_fu_6443.task_compute_attn_U0.grp_do_attn_1_fu_5150.o_sm_i_U.if_empty_n) begin
                                $display("//      Blocked by empty input FIFO 'vit_block_top_vit_block_top.grp_dataflow_wrapper_fu_6443.task_compute_attn_U0.grp_do_attn_1_fu_5150.o_sm_i_U' written by process 'vit_block_top_vit_block_top.grp_dataflow_wrapper_fu_6443.task_compute_attn_U0.grp_do_attn_1_fu_5150.do_matmul_1_U0'");
                                $fdisplay(fp, "Dependence_Channel_path vit_block_top_vit_block_top.grp_dataflow_wrapper_fu_6443.task_compute_attn_U0.grp_do_attn_1_fu_5150.o_sm_i_U");
                                $fdisplay(fp, "Dependence_Channel_status EMPTY");
                            end
                            else if (~grp_dataflow_wrapper_fu_6443.task_compute_attn_U0.grp_do_attn_1_fu_5150.o_sm_i_U.if_full_n) begin
                                $display("//      Blocked by full output FIFO 'vit_block_top_vit_block_top.grp_dataflow_wrapper_fu_6443.task_compute_attn_U0.grp_do_attn_1_fu_5150.o_sm_i_U' read by process 'vit_block_top_vit_block_top.grp_dataflow_wrapper_fu_6443.task_compute_attn_U0.grp_do_attn_1_fu_5150.do_matmul_1_U0'");
                                $fdisplay(fp, "Dependence_Channel_path vit_block_top_vit_block_top.grp_dataflow_wrapper_fu_6443.task_compute_attn_U0.grp_do_attn_1_fu_5150.o_sm_i_U");
                                $fdisplay(fp, "Dependence_Channel_status FULL");
                            end
                        end
                    end
                    45: begin //  for dep proc 'vit_block_top_vit_block_top.grp_dataflow_wrapper_fu_6443.task_compute_attn_U0.grp_do_attn_1_fu_5150.do_matmul_1_U0.do_adapt_8_1_U0'
// for dep channel 'vit_block_top_vit_block_top.grp_dataflow_wrapper_fu_6443.task_compute_attn_U0.grp_do_attn_1_fu_5150.o_sm_i_U' info is :
// blk sig is {~vit_block_top_vit_block_top_inst.grp_dataflow_wrapper_fu_6443.task_compute_attn_U0.grp_do_attn_1_fu_5150.stream_merge_1_U0.grp_stream_merge_1_Pipeline_VITIS_LOOP_554_1_VITIS_LOOP_555_2_fu_34.o_sm_blk_n data_FIFO}
                        if ((~grp_dataflow_wrapper_fu_6443.task_compute_attn_U0.grp_do_attn_1_fu_5150.stream_merge_1_U0.grp_stream_merge_1_Pipeline_VITIS_LOOP_554_1_VITIS_LOOP_555_2_fu_34.o_sm_blk_n)) begin
                            if (~grp_dataflow_wrapper_fu_6443.task_compute_attn_U0.grp_do_attn_1_fu_5150.o_sm_i_U.if_empty_n) begin
                                $display("//      Blocked by empty input FIFO 'vit_block_top_vit_block_top.grp_dataflow_wrapper_fu_6443.task_compute_attn_U0.grp_do_attn_1_fu_5150.o_sm_i_U' written by process 'vit_block_top_vit_block_top.grp_dataflow_wrapper_fu_6443.task_compute_attn_U0.grp_do_attn_1_fu_5150.do_matmul_1_U0.do_adapt_8_1_U0'");
                                $fdisplay(fp, "Dependence_Channel_path vit_block_top_vit_block_top.grp_dataflow_wrapper_fu_6443.task_compute_attn_U0.grp_do_attn_1_fu_5150.o_sm_i_U");
                                $fdisplay(fp, "Dependence_Channel_status EMPTY");
                            end
                            else if (~grp_dataflow_wrapper_fu_6443.task_compute_attn_U0.grp_do_attn_1_fu_5150.o_sm_i_U.if_full_n) begin
                                $display("//      Blocked by full output FIFO 'vit_block_top_vit_block_top.grp_dataflow_wrapper_fu_6443.task_compute_attn_U0.grp_do_attn_1_fu_5150.o_sm_i_U' read by process 'vit_block_top_vit_block_top.grp_dataflow_wrapper_fu_6443.task_compute_attn_U0.grp_do_attn_1_fu_5150.do_matmul_1_U0.do_adapt_8_1_U0'");
                                $fdisplay(fp, "Dependence_Channel_path vit_block_top_vit_block_top.grp_dataflow_wrapper_fu_6443.task_compute_attn_U0.grp_do_attn_1_fu_5150.o_sm_i_U");
                                $fdisplay(fp, "Dependence_Channel_status FULL");
                            end
                        end
                    end
                    endcase
                end
                47 : begin // for proc 'vit_block_top_vit_block_top.grp_dataflow_wrapper_fu_6443.task_stream_cast_U0'
                    case(index2)
                    10: begin //  for dep proc 'vit_block_top_vit_block_top.grp_dataflow_wrapper_fu_6443.task_compute_attn_U0'
// for dep channel 'vit_block_top_vit_block_top.grp_dataflow_wrapper_fu_6443.mid_stream_int_U' info is :
// blk sig is {~vit_block_top_vit_block_top_inst.grp_dataflow_wrapper_fu_6443.task_stream_cast_U0.mid_stream_int_blk_n data_FIFO}
                        if ((~grp_dataflow_wrapper_fu_6443.task_stream_cast_U0.mid_stream_int_blk_n)) begin
                            if (~grp_dataflow_wrapper_fu_6443.mid_stream_int_U.if_empty_n) begin
                                $display("//      Blocked by empty input FIFO 'vit_block_top_vit_block_top.grp_dataflow_wrapper_fu_6443.mid_stream_int_U' written by process 'vit_block_top_vit_block_top.grp_dataflow_wrapper_fu_6443.task_compute_attn_U0'");
                                $fdisplay(fp, "Dependence_Channel_path vit_block_top_vit_block_top.grp_dataflow_wrapper_fu_6443.mid_stream_int_U");
                                $fdisplay(fp, "Dependence_Channel_status EMPTY");
                            end
                            else if (~grp_dataflow_wrapper_fu_6443.mid_stream_int_U.if_full_n) begin
                                $display("//      Blocked by full output FIFO 'vit_block_top_vit_block_top.grp_dataflow_wrapper_fu_6443.mid_stream_int_U' read by process 'vit_block_top_vit_block_top.grp_dataflow_wrapper_fu_6443.task_compute_attn_U0'");
                                $fdisplay(fp, "Dependence_Channel_path vit_block_top_vit_block_top.grp_dataflow_wrapper_fu_6443.mid_stream_int_U");
                                $fdisplay(fp, "Dependence_Channel_status FULL");
                            end
                        end
// for dep channel 'vit_block_top_vit_block_top.grp_dataflow_wrapper_fu_6443.start_for_task_stream_cast_U0_U' info is :
// blk sig is {{~vit_block_top_vit_block_top_inst.grp_dataflow_wrapper_fu_6443.start_for_task_stream_cast_U0_U.if_empty_n & vit_block_top_vit_block_top_inst.grp_dataflow_wrapper_fu_6443.task_stream_cast_U0.ap_idle & ~vit_block_top_vit_block_top_inst.grp_dataflow_wrapper_fu_6443.start_for_task_stream_cast_U0_U.if_write} start_FIFO}
                        if ((~grp_dataflow_wrapper_fu_6443.start_for_task_stream_cast_U0_U.if_empty_n & grp_dataflow_wrapper_fu_6443.task_stream_cast_U0.ap_idle & ~grp_dataflow_wrapper_fu_6443.start_for_task_stream_cast_U0_U.if_write)) begin
                            $display("//      Blocked by missing 'ap_start' from start propagation FIFO 'vit_block_top_vit_block_top.grp_dataflow_wrapper_fu_6443.start_for_task_stream_cast_U0_U' written by process 'vit_block_top_vit_block_top.grp_dataflow_wrapper_fu_6443.task_compute_attn_U0',");
                        end
                    end
                    48: begin //  for dep proc 'vit_block_top_vit_block_top.grp_dataflow_wrapper_fu_6443.task_compute_mlp_U0'
// for dep channel 'vit_block_top_vit_block_top.grp_dataflow_wrapper_fu_6443.mlp_in_stream_U' info is :
// blk sig is {~vit_block_top_vit_block_top_inst.grp_dataflow_wrapper_fu_6443.task_stream_cast_U0.mlp_in_stream_blk_n data_FIFO}
                        if ((~grp_dataflow_wrapper_fu_6443.task_stream_cast_U0.mlp_in_stream_blk_n)) begin
                            if (~grp_dataflow_wrapper_fu_6443.mlp_in_stream_U.if_empty_n) begin
                                $display("//      Blocked by empty input FIFO 'vit_block_top_vit_block_top.grp_dataflow_wrapper_fu_6443.mlp_in_stream_U' written by process 'vit_block_top_vit_block_top.grp_dataflow_wrapper_fu_6443.task_compute_mlp_U0'");
                                $fdisplay(fp, "Dependence_Channel_path vit_block_top_vit_block_top.grp_dataflow_wrapper_fu_6443.mlp_in_stream_U");
                                $fdisplay(fp, "Dependence_Channel_status EMPTY");
                            end
                            else if (~grp_dataflow_wrapper_fu_6443.mlp_in_stream_U.if_full_n) begin
                                $display("//      Blocked by full output FIFO 'vit_block_top_vit_block_top.grp_dataflow_wrapper_fu_6443.mlp_in_stream_U' read by process 'vit_block_top_vit_block_top.grp_dataflow_wrapper_fu_6443.task_compute_mlp_U0'");
                                $fdisplay(fp, "Dependence_Channel_path vit_block_top_vit_block_top.grp_dataflow_wrapper_fu_6443.mlp_in_stream_U");
                                $fdisplay(fp, "Dependence_Channel_status FULL");
                            end
                        end
                    end
                    endcase
                end
                48 : begin // for proc 'vit_block_top_vit_block_top.grp_dataflow_wrapper_fu_6443.task_compute_mlp_U0'
                    case(index2)
                    9: begin //  for dep proc 'vit_block_top_vit_block_top.grp_dataflow_wrapper_fu_6443.dataflow_wrapper_Block_entry_calc_weights_attn_weights_attn_scalars_rd_calc_weig_U0'
// for dep channel 'vit_block_top_vit_block_top.grp_dataflow_wrapper_fu_6443.calc_weights_mlp_weights_mlp_scalars_idx_val_loc_channel_U' info is :
// blk sig is {{~vit_block_top_vit_block_top_inst.grp_dataflow_wrapper_fu_6443.calc_weights_mlp_weights_mlp_scalars_idx_val_loc_channel_U.if_empty_n & vit_block_top_vit_block_top_inst.grp_dataflow_wrapper_fu_6443.task_compute_mlp_U0.ap_idle & ~vit_block_top_vit_block_top_inst.grp_dataflow_wrapper_fu_6443.calc_weights_mlp_weights_mlp_scalars_idx_val_loc_channel_U.if_write} TLF_FIFO}
                        if ((~grp_dataflow_wrapper_fu_6443.calc_weights_mlp_weights_mlp_scalars_idx_val_loc_channel_U.if_empty_n & grp_dataflow_wrapper_fu_6443.task_compute_mlp_U0.ap_idle & ~grp_dataflow_wrapper_fu_6443.calc_weights_mlp_weights_mlp_scalars_idx_val_loc_channel_U.if_write)) begin
                            if (~grp_dataflow_wrapper_fu_6443.calc_weights_mlp_weights_mlp_scalars_idx_val_loc_channel_U.if_empty_n) begin
                                $display("//      Blocked by empty input FIFO 'vit_block_top_vit_block_top.grp_dataflow_wrapper_fu_6443.calc_weights_mlp_weights_mlp_scalars_idx_val_loc_channel_U' written by process 'vit_block_top_vit_block_top.grp_dataflow_wrapper_fu_6443.dataflow_wrapper_Block_entry_calc_weights_attn_weights_attn_scalars_rd_calc_weig_U0'");
                                $fdisplay(fp, "Dependence_Channel_path vit_block_top_vit_block_top.grp_dataflow_wrapper_fu_6443.calc_weights_mlp_weights_mlp_scalars_idx_val_loc_channel_U");
                                $fdisplay(fp, "Dependence_Channel_status EMPTY");
                            end
                            else if (~grp_dataflow_wrapper_fu_6443.calc_weights_mlp_weights_mlp_scalars_idx_val_loc_channel_U.if_full_n) begin
                                $display("//      Blocked by full output FIFO 'vit_block_top_vit_block_top.grp_dataflow_wrapper_fu_6443.calc_weights_mlp_weights_mlp_scalars_idx_val_loc_channel_U' read by process 'vit_block_top_vit_block_top.grp_dataflow_wrapper_fu_6443.dataflow_wrapper_Block_entry_calc_weights_attn_weights_attn_scalars_rd_calc_weig_U0'");
                                $fdisplay(fp, "Dependence_Channel_path vit_block_top_vit_block_top.grp_dataflow_wrapper_fu_6443.calc_weights_mlp_weights_mlp_scalars_idx_val_loc_channel_U");
                                $fdisplay(fp, "Dependence_Channel_status FULL");
                            end
                        end
// for dep channel 'vit_block_top_vit_block_top.grp_dataflow_wrapper_fu_6443.calc_weights_mlp_weights_mlp_scalars_idx7_val_loc_channel_U' info is :
// blk sig is {{~vit_block_top_vit_block_top_inst.grp_dataflow_wrapper_fu_6443.calc_weights_mlp_weights_mlp_scalars_idx7_val_loc_channel_U.if_empty_n & vit_block_top_vit_block_top_inst.grp_dataflow_wrapper_fu_6443.task_compute_mlp_U0.ap_idle & ~vit_block_top_vit_block_top_inst.grp_dataflow_wrapper_fu_6443.calc_weights_mlp_weights_mlp_scalars_idx7_val_loc_channel_U.if_write} TLF_FIFO}
                        if ((~grp_dataflow_wrapper_fu_6443.calc_weights_mlp_weights_mlp_scalars_idx7_val_loc_channel_U.if_empty_n & grp_dataflow_wrapper_fu_6443.task_compute_mlp_U0.ap_idle & ~grp_dataflow_wrapper_fu_6443.calc_weights_mlp_weights_mlp_scalars_idx7_val_loc_channel_U.if_write)) begin
                            if (~grp_dataflow_wrapper_fu_6443.calc_weights_mlp_weights_mlp_scalars_idx7_val_loc_channel_U.if_empty_n) begin
                                $display("//      Blocked by empty input FIFO 'vit_block_top_vit_block_top.grp_dataflow_wrapper_fu_6443.calc_weights_mlp_weights_mlp_scalars_idx7_val_loc_channel_U' written by process 'vit_block_top_vit_block_top.grp_dataflow_wrapper_fu_6443.dataflow_wrapper_Block_entry_calc_weights_attn_weights_attn_scalars_rd_calc_weig_U0'");
                                $fdisplay(fp, "Dependence_Channel_path vit_block_top_vit_block_top.grp_dataflow_wrapper_fu_6443.calc_weights_mlp_weights_mlp_scalars_idx7_val_loc_channel_U");
                                $fdisplay(fp, "Dependence_Channel_status EMPTY");
                            end
                            else if (~grp_dataflow_wrapper_fu_6443.calc_weights_mlp_weights_mlp_scalars_idx7_val_loc_channel_U.if_full_n) begin
                                $display("//      Blocked by full output FIFO 'vit_block_top_vit_block_top.grp_dataflow_wrapper_fu_6443.calc_weights_mlp_weights_mlp_scalars_idx7_val_loc_channel_U' read by process 'vit_block_top_vit_block_top.grp_dataflow_wrapper_fu_6443.dataflow_wrapper_Block_entry_calc_weights_attn_weights_attn_scalars_rd_calc_weig_U0'");
                                $fdisplay(fp, "Dependence_Channel_path vit_block_top_vit_block_top.grp_dataflow_wrapper_fu_6443.calc_weights_mlp_weights_mlp_scalars_idx7_val_loc_channel_U");
                                $fdisplay(fp, "Dependence_Channel_status FULL");
                            end
                        end
                    end
                    47: begin //  for dep proc 'vit_block_top_vit_block_top.grp_dataflow_wrapper_fu_6443.task_stream_cast_U0'
// for dep channel 'vit_block_top_vit_block_top.grp_dataflow_wrapper_fu_6443.mlp_in_stream_U' info is :
// blk sig is {~vit_block_top_vit_block_top_inst.grp_dataflow_wrapper_fu_6443.task_compute_mlp_U0.grp_do_mlp_fu_4710.stream_copy_U0.mlp_in_stream_blk_n data_FIFO}
                        if ((~grp_dataflow_wrapper_fu_6443.task_compute_mlp_U0.grp_do_mlp_fu_4710.stream_copy_U0.mlp_in_stream_blk_n)) begin
                            if (~grp_dataflow_wrapper_fu_6443.mlp_in_stream_U.if_empty_n) begin
                                $display("//      Blocked by empty input FIFO 'vit_block_top_vit_block_top.grp_dataflow_wrapper_fu_6443.mlp_in_stream_U' written by process 'vit_block_top_vit_block_top.grp_dataflow_wrapper_fu_6443.task_stream_cast_U0'");
                                $fdisplay(fp, "Dependence_Channel_path vit_block_top_vit_block_top.grp_dataflow_wrapper_fu_6443.mlp_in_stream_U");
                                $fdisplay(fp, "Dependence_Channel_status EMPTY");
                            end
                            else if (~grp_dataflow_wrapper_fu_6443.mlp_in_stream_U.if_full_n) begin
                                $display("//      Blocked by full output FIFO 'vit_block_top_vit_block_top.grp_dataflow_wrapper_fu_6443.mlp_in_stream_U' read by process 'vit_block_top_vit_block_top.grp_dataflow_wrapper_fu_6443.task_stream_cast_U0'");
                                $fdisplay(fp, "Dependence_Channel_path vit_block_top_vit_block_top.grp_dataflow_wrapper_fu_6443.mlp_in_stream_U");
                                $fdisplay(fp, "Dependence_Channel_status FULL");
                            end
                        end
                    end
                    65: begin //  for dep proc 'vit_block_top_vit_block_top.grp_dataflow_wrapper_fu_6443.task_write_fm_U0'
// for dep channel 'vit_block_top_vit_block_top.grp_dataflow_wrapper_fu_6443.o_stream_int_U' info is :
// blk sig is {~vit_block_top_vit_block_top_inst.grp_dataflow_wrapper_fu_6443.task_compute_mlp_U0.grp_do_mlp_fu_4710.stream_merge_U0.grp_stream_merge_Pipeline_VITIS_LOOP_393_1_VITIS_LOOP_394_2_fu_34.o_stream_int_blk_n data_FIFO}
                        if ((~grp_dataflow_wrapper_fu_6443.task_compute_mlp_U0.grp_do_mlp_fu_4710.stream_merge_U0.grp_stream_merge_Pipeline_VITIS_LOOP_393_1_VITIS_LOOP_394_2_fu_34.o_stream_int_blk_n)) begin
                            if (~grp_dataflow_wrapper_fu_6443.o_stream_int_U.if_empty_n) begin
                                $display("//      Blocked by empty input FIFO 'vit_block_top_vit_block_top.grp_dataflow_wrapper_fu_6443.o_stream_int_U' written by process 'vit_block_top_vit_block_top.grp_dataflow_wrapper_fu_6443.task_write_fm_U0'");
                                $fdisplay(fp, "Dependence_Channel_path vit_block_top_vit_block_top.grp_dataflow_wrapper_fu_6443.o_stream_int_U");
                                $fdisplay(fp, "Dependence_Channel_status EMPTY");
                            end
                            else if (~grp_dataflow_wrapper_fu_6443.o_stream_int_U.if_full_n) begin
                                $display("//      Blocked by full output FIFO 'vit_block_top_vit_block_top.grp_dataflow_wrapper_fu_6443.o_stream_int_U' read by process 'vit_block_top_vit_block_top.grp_dataflow_wrapper_fu_6443.task_write_fm_U0'");
                                $fdisplay(fp, "Dependence_Channel_path vit_block_top_vit_block_top.grp_dataflow_wrapper_fu_6443.o_stream_int_U");
                                $fdisplay(fp, "Dependence_Channel_status FULL");
                            end
                        end
// for dep channel 'vit_block_top_vit_block_top.grp_dataflow_wrapper_fu_6443.start_for_task_write_fm_U0_U' info is :
// blk sig is {{~vit_block_top_vit_block_top_inst.grp_dataflow_wrapper_fu_6443.start_for_task_write_fm_U0_U.if_full_n & vit_block_top_vit_block_top_inst.grp_dataflow_wrapper_fu_6443.task_compute_mlp_U0.ap_start & ~vit_block_top_vit_block_top_inst.grp_dataflow_wrapper_fu_6443.task_compute_mlp_U0.real_start & (trans_in_cnt_43 == trans_out_cnt_43) & ~vit_block_top_vit_block_top_inst.grp_dataflow_wrapper_fu_6443.start_for_task_write_fm_U0_U.if_read} start_FIFO}
                        if ((~grp_dataflow_wrapper_fu_6443.start_for_task_write_fm_U0_U.if_full_n & grp_dataflow_wrapper_fu_6443.task_compute_mlp_U0.ap_start & ~grp_dataflow_wrapper_fu_6443.task_compute_mlp_U0.real_start & (trans_in_cnt_43 == trans_out_cnt_43) & ~grp_dataflow_wrapper_fu_6443.start_for_task_write_fm_U0_U.if_read)) begin
                            $display("//      Blocked by full output start propagation FIFO 'vit_block_top_vit_block_top.grp_dataflow_wrapper_fu_6443.start_for_task_write_fm_U0_U' read by process 'vit_block_top_vit_block_top.grp_dataflow_wrapper_fu_6443.task_write_fm_U0',");
                        end
                    end
                    endcase
                end
                49 : begin // for proc 'vit_block_top_vit_block_top.grp_dataflow_wrapper_fu_6443.task_compute_mlp_U0.grp_do_mlp_fu_4710.stream_copy_U0'
                    case(index2)
                    52: begin //  for dep proc 'vit_block_top_vit_block_top.grp_dataflow_wrapper_fu_6443.task_compute_mlp_U0.grp_do_mlp_fu_4710.do_layernorm_inter_token_U0'
// for dep channel 'vit_block_top_vit_block_top.grp_dataflow_wrapper_fu_6443.task_compute_mlp_U0.grp_do_mlp_fu_4710.main_sm_i_U' info is :
// blk sig is {~vit_block_top_vit_block_top_inst.grp_dataflow_wrapper_fu_6443.task_compute_mlp_U0.grp_do_mlp_fu_4710.stream_copy_U0.main_sm_blk_n data_FIFO}
                        if ((~grp_dataflow_wrapper_fu_6443.task_compute_mlp_U0.grp_do_mlp_fu_4710.stream_copy_U0.main_sm_blk_n)) begin
                            if (~grp_dataflow_wrapper_fu_6443.task_compute_mlp_U0.grp_do_mlp_fu_4710.main_sm_i_U.if_empty_n) begin
                                $display("//      Blocked by empty input FIFO 'vit_block_top_vit_block_top.grp_dataflow_wrapper_fu_6443.task_compute_mlp_U0.grp_do_mlp_fu_4710.main_sm_i_U' written by process 'vit_block_top_vit_block_top.grp_dataflow_wrapper_fu_6443.task_compute_mlp_U0.grp_do_mlp_fu_4710.do_layernorm_inter_token_U0'");
                                $fdisplay(fp, "Dependence_Channel_path vit_block_top_vit_block_top.grp_dataflow_wrapper_fu_6443.task_compute_mlp_U0.grp_do_mlp_fu_4710.main_sm_i_U");
                                $fdisplay(fp, "Dependence_Channel_status EMPTY");
                            end
                            else if (~grp_dataflow_wrapper_fu_6443.task_compute_mlp_U0.grp_do_mlp_fu_4710.main_sm_i_U.if_full_n) begin
                                $display("//      Blocked by full output FIFO 'vit_block_top_vit_block_top.grp_dataflow_wrapper_fu_6443.task_compute_mlp_U0.grp_do_mlp_fu_4710.main_sm_i_U' read by process 'vit_block_top_vit_block_top.grp_dataflow_wrapper_fu_6443.task_compute_mlp_U0.grp_do_mlp_fu_4710.do_layernorm_inter_token_U0'");
                                $fdisplay(fp, "Dependence_Channel_path vit_block_top_vit_block_top.grp_dataflow_wrapper_fu_6443.task_compute_mlp_U0.grp_do_mlp_fu_4710.main_sm_i_U");
                                $fdisplay(fp, "Dependence_Channel_status FULL");
                            end
                        end
// for dep channel 'vit_block_top_vit_block_top.grp_dataflow_wrapper_fu_6443.task_compute_mlp_U0.grp_do_mlp_fu_4710.start_for_do_layernorm_inter_token_U0_U' info is :
// blk sig is {{~vit_block_top_vit_block_top_inst.grp_dataflow_wrapper_fu_6443.task_compute_mlp_U0.grp_do_mlp_fu_4710.start_for_do_layernorm_inter_token_U0_U.if_full_n & vit_block_top_vit_block_top_inst.grp_dataflow_wrapper_fu_6443.task_compute_mlp_U0.grp_do_mlp_fu_4710.stream_copy_U0.ap_start & ~vit_block_top_vit_block_top_inst.grp_dataflow_wrapper_fu_6443.task_compute_mlp_U0.grp_do_mlp_fu_4710.stream_copy_U0.real_start & (trans_in_cnt_31 == trans_out_cnt_31) & ~vit_block_top_vit_block_top_inst.grp_dataflow_wrapper_fu_6443.task_compute_mlp_U0.grp_do_mlp_fu_4710.start_for_do_layernorm_inter_token_U0_U.if_read} start_FIFO}
                        if ((~grp_dataflow_wrapper_fu_6443.task_compute_mlp_U0.grp_do_mlp_fu_4710.start_for_do_layernorm_inter_token_U0_U.if_full_n & grp_dataflow_wrapper_fu_6443.task_compute_mlp_U0.grp_do_mlp_fu_4710.stream_copy_U0.ap_start & ~grp_dataflow_wrapper_fu_6443.task_compute_mlp_U0.grp_do_mlp_fu_4710.stream_copy_U0.real_start & (trans_in_cnt_31 == trans_out_cnt_31) & ~grp_dataflow_wrapper_fu_6443.task_compute_mlp_U0.grp_do_mlp_fu_4710.start_for_do_layernorm_inter_token_U0_U.if_read)) begin
                            $display("//      Blocked by full output start propagation FIFO 'vit_block_top_vit_block_top.grp_dataflow_wrapper_fu_6443.task_compute_mlp_U0.grp_do_mlp_fu_4710.start_for_do_layernorm_inter_token_U0_U' read by process 'vit_block_top_vit_block_top.grp_dataflow_wrapper_fu_6443.task_compute_mlp_U0.grp_do_mlp_fu_4710.do_layernorm_inter_token_U0',");
                        end
                    end
                    50: begin //  for dep proc 'vit_block_top_vit_block_top.grp_dataflow_wrapper_fu_6443.task_compute_mlp_U0.grp_do_mlp_fu_4710.do_adapt_6_U0'
// for dep channel 'vit_block_top_vit_block_top.grp_dataflow_wrapper_fu_6443.task_compute_mlp_U0.grp_do_mlp_fu_4710.resi_i_sm_i_U' info is :
// blk sig is {~vit_block_top_vit_block_top_inst.grp_dataflow_wrapper_fu_6443.task_compute_mlp_U0.grp_do_mlp_fu_4710.stream_copy_U0.resi_i_sm_blk_n data_FIFO}
                        if ((~grp_dataflow_wrapper_fu_6443.task_compute_mlp_U0.grp_do_mlp_fu_4710.stream_copy_U0.resi_i_sm_blk_n)) begin
                            if (~grp_dataflow_wrapper_fu_6443.task_compute_mlp_U0.grp_do_mlp_fu_4710.resi_i_sm_i_U.if_empty_n) begin
                                $display("//      Blocked by empty input FIFO 'vit_block_top_vit_block_top.grp_dataflow_wrapper_fu_6443.task_compute_mlp_U0.grp_do_mlp_fu_4710.resi_i_sm_i_U' written by process 'vit_block_top_vit_block_top.grp_dataflow_wrapper_fu_6443.task_compute_mlp_U0.grp_do_mlp_fu_4710.do_adapt_6_U0'");
                                $fdisplay(fp, "Dependence_Channel_path vit_block_top_vit_block_top.grp_dataflow_wrapper_fu_6443.task_compute_mlp_U0.grp_do_mlp_fu_4710.resi_i_sm_i_U");
                                $fdisplay(fp, "Dependence_Channel_status EMPTY");
                            end
                            else if (~grp_dataflow_wrapper_fu_6443.task_compute_mlp_U0.grp_do_mlp_fu_4710.resi_i_sm_i_U.if_full_n) begin
                                $display("//      Blocked by full output FIFO 'vit_block_top_vit_block_top.grp_dataflow_wrapper_fu_6443.task_compute_mlp_U0.grp_do_mlp_fu_4710.resi_i_sm_i_U' read by process 'vit_block_top_vit_block_top.grp_dataflow_wrapper_fu_6443.task_compute_mlp_U0.grp_do_mlp_fu_4710.do_adapt_6_U0'");
                                $fdisplay(fp, "Dependence_Channel_path vit_block_top_vit_block_top.grp_dataflow_wrapper_fu_6443.task_compute_mlp_U0.grp_do_mlp_fu_4710.resi_i_sm_i_U");
                                $fdisplay(fp, "Dependence_Channel_status FULL");
                            end
                        end
// for dep channel 'vit_block_top_vit_block_top.grp_dataflow_wrapper_fu_6443.task_compute_mlp_U0.grp_do_mlp_fu_4710.start_for_do_adapt_6_U0_U' info is :
// blk sig is {{~vit_block_top_vit_block_top_inst.grp_dataflow_wrapper_fu_6443.task_compute_mlp_U0.grp_do_mlp_fu_4710.start_for_do_adapt_6_U0_U.if_full_n & vit_block_top_vit_block_top_inst.grp_dataflow_wrapper_fu_6443.task_compute_mlp_U0.grp_do_mlp_fu_4710.stream_copy_U0.ap_start & ~vit_block_top_vit_block_top_inst.grp_dataflow_wrapper_fu_6443.task_compute_mlp_U0.grp_do_mlp_fu_4710.stream_copy_U0.real_start & (trans_in_cnt_31 == trans_out_cnt_31) & ~vit_block_top_vit_block_top_inst.grp_dataflow_wrapper_fu_6443.task_compute_mlp_U0.grp_do_mlp_fu_4710.start_for_do_adapt_6_U0_U.if_read} start_FIFO}
                        if ((~grp_dataflow_wrapper_fu_6443.task_compute_mlp_U0.grp_do_mlp_fu_4710.start_for_do_adapt_6_U0_U.if_full_n & grp_dataflow_wrapper_fu_6443.task_compute_mlp_U0.grp_do_mlp_fu_4710.stream_copy_U0.ap_start & ~grp_dataflow_wrapper_fu_6443.task_compute_mlp_U0.grp_do_mlp_fu_4710.stream_copy_U0.real_start & (trans_in_cnt_31 == trans_out_cnt_31) & ~grp_dataflow_wrapper_fu_6443.task_compute_mlp_U0.grp_do_mlp_fu_4710.start_for_do_adapt_6_U0_U.if_read)) begin
                            $display("//      Blocked by full output start propagation FIFO 'vit_block_top_vit_block_top.grp_dataflow_wrapper_fu_6443.task_compute_mlp_U0.grp_do_mlp_fu_4710.start_for_do_adapt_6_U0_U' read by process 'vit_block_top_vit_block_top.grp_dataflow_wrapper_fu_6443.task_compute_mlp_U0.grp_do_mlp_fu_4710.do_adapt_6_U0',");
                        end
                    end
                    endcase
                end
                50 : begin // for proc 'vit_block_top_vit_block_top.grp_dataflow_wrapper_fu_6443.task_compute_mlp_U0.grp_do_mlp_fu_4710.do_adapt_6_U0'
                    case(index2)
                    49: begin //  for dep proc 'vit_block_top_vit_block_top.grp_dataflow_wrapper_fu_6443.task_compute_mlp_U0.grp_do_mlp_fu_4710.stream_copy_U0'
// for dep channel 'vit_block_top_vit_block_top.grp_dataflow_wrapper_fu_6443.task_compute_mlp_U0.grp_do_mlp_fu_4710.resi_i_sm_i_U' info is :
// blk sig is {~vit_block_top_vit_block_top_inst.grp_dataflow_wrapper_fu_6443.task_compute_mlp_U0.grp_do_mlp_fu_4710.do_adapt_6_U0.resi_i_sm_blk_n data_FIFO}
                        if ((~grp_dataflow_wrapper_fu_6443.task_compute_mlp_U0.grp_do_mlp_fu_4710.do_adapt_6_U0.resi_i_sm_blk_n)) begin
                            if (~grp_dataflow_wrapper_fu_6443.task_compute_mlp_U0.grp_do_mlp_fu_4710.resi_i_sm_i_U.if_empty_n) begin
                                $display("//      Blocked by empty input FIFO 'vit_block_top_vit_block_top.grp_dataflow_wrapper_fu_6443.task_compute_mlp_U0.grp_do_mlp_fu_4710.resi_i_sm_i_U' written by process 'vit_block_top_vit_block_top.grp_dataflow_wrapper_fu_6443.task_compute_mlp_U0.grp_do_mlp_fu_4710.stream_copy_U0'");
                                $fdisplay(fp, "Dependence_Channel_path vit_block_top_vit_block_top.grp_dataflow_wrapper_fu_6443.task_compute_mlp_U0.grp_do_mlp_fu_4710.resi_i_sm_i_U");
                                $fdisplay(fp, "Dependence_Channel_status EMPTY");
                            end
                            else if (~grp_dataflow_wrapper_fu_6443.task_compute_mlp_U0.grp_do_mlp_fu_4710.resi_i_sm_i_U.if_full_n) begin
                                $display("//      Blocked by full output FIFO 'vit_block_top_vit_block_top.grp_dataflow_wrapper_fu_6443.task_compute_mlp_U0.grp_do_mlp_fu_4710.resi_i_sm_i_U' read by process 'vit_block_top_vit_block_top.grp_dataflow_wrapper_fu_6443.task_compute_mlp_U0.grp_do_mlp_fu_4710.stream_copy_U0'");
                                $fdisplay(fp, "Dependence_Channel_path vit_block_top_vit_block_top.grp_dataflow_wrapper_fu_6443.task_compute_mlp_U0.grp_do_mlp_fu_4710.resi_i_sm_i_U");
                                $fdisplay(fp, "Dependence_Channel_status FULL");
                            end
                        end
// for dep channel 'vit_block_top_vit_block_top.grp_dataflow_wrapper_fu_6443.task_compute_mlp_U0.grp_do_mlp_fu_4710.start_for_do_adapt_6_U0_U' info is :
// blk sig is {{~vit_block_top_vit_block_top_inst.grp_dataflow_wrapper_fu_6443.task_compute_mlp_U0.grp_do_mlp_fu_4710.start_for_do_adapt_6_U0_U.if_empty_n & vit_block_top_vit_block_top_inst.grp_dataflow_wrapper_fu_6443.task_compute_mlp_U0.grp_do_mlp_fu_4710.do_adapt_6_U0.ap_idle & ~vit_block_top_vit_block_top_inst.grp_dataflow_wrapper_fu_6443.task_compute_mlp_U0.grp_do_mlp_fu_4710.start_for_do_adapt_6_U0_U.if_write} start_FIFO}
                        if ((~grp_dataflow_wrapper_fu_6443.task_compute_mlp_U0.grp_do_mlp_fu_4710.start_for_do_adapt_6_U0_U.if_empty_n & grp_dataflow_wrapper_fu_6443.task_compute_mlp_U0.grp_do_mlp_fu_4710.do_adapt_6_U0.ap_idle & ~grp_dataflow_wrapper_fu_6443.task_compute_mlp_U0.grp_do_mlp_fu_4710.start_for_do_adapt_6_U0_U.if_write)) begin
                            $display("//      Blocked by missing 'ap_start' from start propagation FIFO 'vit_block_top_vit_block_top.grp_dataflow_wrapper_fu_6443.task_compute_mlp_U0.grp_do_mlp_fu_4710.start_for_do_adapt_6_U0_U' written by process 'vit_block_top_vit_block_top.grp_dataflow_wrapper_fu_6443.task_compute_mlp_U0.grp_do_mlp_fu_4710.stream_copy_U0',");
                        end
                    end
                    51: begin //  for dep proc 'vit_block_top_vit_block_top.grp_dataflow_wrapper_fu_6443.task_compute_mlp_U0.grp_do_mlp_fu_4710.do_adapt_5_U0'
// for dep channel 'vit_block_top_vit_block_top.grp_dataflow_wrapper_fu_6443.task_compute_mlp_U0.grp_do_mlp_fu_4710.resi_sm_i_U' info is :
// blk sig is {~vit_block_top_vit_block_top_inst.grp_dataflow_wrapper_fu_6443.task_compute_mlp_U0.grp_do_mlp_fu_4710.do_adapt_6_U0.resi_sm_blk_n data_FIFO}
                        if ((~grp_dataflow_wrapper_fu_6443.task_compute_mlp_U0.grp_do_mlp_fu_4710.do_adapt_6_U0.resi_sm_blk_n)) begin
                            if (~grp_dataflow_wrapper_fu_6443.task_compute_mlp_U0.grp_do_mlp_fu_4710.resi_sm_i_U.if_empty_n) begin
                                $display("//      Blocked by empty input FIFO 'vit_block_top_vit_block_top.grp_dataflow_wrapper_fu_6443.task_compute_mlp_U0.grp_do_mlp_fu_4710.resi_sm_i_U' written by process 'vit_block_top_vit_block_top.grp_dataflow_wrapper_fu_6443.task_compute_mlp_U0.grp_do_mlp_fu_4710.do_adapt_5_U0'");
                                $fdisplay(fp, "Dependence_Channel_path vit_block_top_vit_block_top.grp_dataflow_wrapper_fu_6443.task_compute_mlp_U0.grp_do_mlp_fu_4710.resi_sm_i_U");
                                $fdisplay(fp, "Dependence_Channel_status EMPTY");
                            end
                            else if (~grp_dataflow_wrapper_fu_6443.task_compute_mlp_U0.grp_do_mlp_fu_4710.resi_sm_i_U.if_full_n) begin
                                $display("//      Blocked by full output FIFO 'vit_block_top_vit_block_top.grp_dataflow_wrapper_fu_6443.task_compute_mlp_U0.grp_do_mlp_fu_4710.resi_sm_i_U' read by process 'vit_block_top_vit_block_top.grp_dataflow_wrapper_fu_6443.task_compute_mlp_U0.grp_do_mlp_fu_4710.do_adapt_5_U0'");
                                $fdisplay(fp, "Dependence_Channel_path vit_block_top_vit_block_top.grp_dataflow_wrapper_fu_6443.task_compute_mlp_U0.grp_do_mlp_fu_4710.resi_sm_i_U");
                                $fdisplay(fp, "Dependence_Channel_status FULL");
                            end
                        end
// for dep channel 'vit_block_top_vit_block_top.grp_dataflow_wrapper_fu_6443.task_compute_mlp_U0.grp_do_mlp_fu_4710.start_for_do_adapt_5_U0_U' info is :
// blk sig is {{~vit_block_top_vit_block_top_inst.grp_dataflow_wrapper_fu_6443.task_compute_mlp_U0.grp_do_mlp_fu_4710.start_for_do_adapt_5_U0_U.if_full_n & vit_block_top_vit_block_top_inst.grp_dataflow_wrapper_fu_6443.task_compute_mlp_U0.grp_do_mlp_fu_4710.do_adapt_6_U0.ap_start & ~vit_block_top_vit_block_top_inst.grp_dataflow_wrapper_fu_6443.task_compute_mlp_U0.grp_do_mlp_fu_4710.do_adapt_6_U0.real_start & (trans_in_cnt_32 == trans_out_cnt_32) & ~vit_block_top_vit_block_top_inst.grp_dataflow_wrapper_fu_6443.task_compute_mlp_U0.grp_do_mlp_fu_4710.start_for_do_adapt_5_U0_U.if_read} start_FIFO}
                        if ((~grp_dataflow_wrapper_fu_6443.task_compute_mlp_U0.grp_do_mlp_fu_4710.start_for_do_adapt_5_U0_U.if_full_n & grp_dataflow_wrapper_fu_6443.task_compute_mlp_U0.grp_do_mlp_fu_4710.do_adapt_6_U0.ap_start & ~grp_dataflow_wrapper_fu_6443.task_compute_mlp_U0.grp_do_mlp_fu_4710.do_adapt_6_U0.real_start & (trans_in_cnt_32 == trans_out_cnt_32) & ~grp_dataflow_wrapper_fu_6443.task_compute_mlp_U0.grp_do_mlp_fu_4710.start_for_do_adapt_5_U0_U.if_read)) begin
                            $display("//      Blocked by full output start propagation FIFO 'vit_block_top_vit_block_top.grp_dataflow_wrapper_fu_6443.task_compute_mlp_U0.grp_do_mlp_fu_4710.start_for_do_adapt_5_U0_U' read by process 'vit_block_top_vit_block_top.grp_dataflow_wrapper_fu_6443.task_compute_mlp_U0.grp_do_mlp_fu_4710.do_adapt_5_U0',");
                        end
                    end
                    endcase
                end
                51 : begin // for proc 'vit_block_top_vit_block_top.grp_dataflow_wrapper_fu_6443.task_compute_mlp_U0.grp_do_mlp_fu_4710.do_adapt_5_U0'
                    case(index2)
                    50: begin //  for dep proc 'vit_block_top_vit_block_top.grp_dataflow_wrapper_fu_6443.task_compute_mlp_U0.grp_do_mlp_fu_4710.do_adapt_6_U0'
// for dep channel 'vit_block_top_vit_block_top.grp_dataflow_wrapper_fu_6443.task_compute_mlp_U0.grp_do_mlp_fu_4710.resi_sm_i_U' info is :
// blk sig is {~vit_block_top_vit_block_top_inst.grp_dataflow_wrapper_fu_6443.task_compute_mlp_U0.grp_do_mlp_fu_4710.do_adapt_5_U0.resi_sm_blk_n data_FIFO}
                        if ((~grp_dataflow_wrapper_fu_6443.task_compute_mlp_U0.grp_do_mlp_fu_4710.do_adapt_5_U0.resi_sm_blk_n)) begin
                            if (~grp_dataflow_wrapper_fu_6443.task_compute_mlp_U0.grp_do_mlp_fu_4710.resi_sm_i_U.if_empty_n) begin
                                $display("//      Blocked by empty input FIFO 'vit_block_top_vit_block_top.grp_dataflow_wrapper_fu_6443.task_compute_mlp_U0.grp_do_mlp_fu_4710.resi_sm_i_U' written by process 'vit_block_top_vit_block_top.grp_dataflow_wrapper_fu_6443.task_compute_mlp_U0.grp_do_mlp_fu_4710.do_adapt_6_U0'");
                                $fdisplay(fp, "Dependence_Channel_path vit_block_top_vit_block_top.grp_dataflow_wrapper_fu_6443.task_compute_mlp_U0.grp_do_mlp_fu_4710.resi_sm_i_U");
                                $fdisplay(fp, "Dependence_Channel_status EMPTY");
                            end
                            else if (~grp_dataflow_wrapper_fu_6443.task_compute_mlp_U0.grp_do_mlp_fu_4710.resi_sm_i_U.if_full_n) begin
                                $display("//      Blocked by full output FIFO 'vit_block_top_vit_block_top.grp_dataflow_wrapper_fu_6443.task_compute_mlp_U0.grp_do_mlp_fu_4710.resi_sm_i_U' read by process 'vit_block_top_vit_block_top.grp_dataflow_wrapper_fu_6443.task_compute_mlp_U0.grp_do_mlp_fu_4710.do_adapt_6_U0'");
                                $fdisplay(fp, "Dependence_Channel_path vit_block_top_vit_block_top.grp_dataflow_wrapper_fu_6443.task_compute_mlp_U0.grp_do_mlp_fu_4710.resi_sm_i_U");
                                $fdisplay(fp, "Dependence_Channel_status FULL");
                            end
                        end
// for dep channel 'vit_block_top_vit_block_top.grp_dataflow_wrapper_fu_6443.task_compute_mlp_U0.grp_do_mlp_fu_4710.start_for_do_adapt_5_U0_U' info is :
// blk sig is {{~vit_block_top_vit_block_top_inst.grp_dataflow_wrapper_fu_6443.task_compute_mlp_U0.grp_do_mlp_fu_4710.start_for_do_adapt_5_U0_U.if_empty_n & vit_block_top_vit_block_top_inst.grp_dataflow_wrapper_fu_6443.task_compute_mlp_U0.grp_do_mlp_fu_4710.do_adapt_5_U0.ap_idle & ~vit_block_top_vit_block_top_inst.grp_dataflow_wrapper_fu_6443.task_compute_mlp_U0.grp_do_mlp_fu_4710.start_for_do_adapt_5_U0_U.if_write} start_FIFO}
                        if ((~grp_dataflow_wrapper_fu_6443.task_compute_mlp_U0.grp_do_mlp_fu_4710.start_for_do_adapt_5_U0_U.if_empty_n & grp_dataflow_wrapper_fu_6443.task_compute_mlp_U0.grp_do_mlp_fu_4710.do_adapt_5_U0.ap_idle & ~grp_dataflow_wrapper_fu_6443.task_compute_mlp_U0.grp_do_mlp_fu_4710.start_for_do_adapt_5_U0_U.if_write)) begin
                            $display("//      Blocked by missing 'ap_start' from start propagation FIFO 'vit_block_top_vit_block_top.grp_dataflow_wrapper_fu_6443.task_compute_mlp_U0.grp_do_mlp_fu_4710.start_for_do_adapt_5_U0_U' written by process 'vit_block_top_vit_block_top.grp_dataflow_wrapper_fu_6443.task_compute_mlp_U0.grp_do_mlp_fu_4710.do_adapt_6_U0',");
                        end
                    end
                    64: begin //  for dep proc 'vit_block_top_vit_block_top.grp_dataflow_wrapper_fu_6443.task_compute_mlp_U0.grp_do_mlp_fu_4710.stream_merge_U0'
// for dep channel 'vit_block_top_vit_block_top.grp_dataflow_wrapper_fu_6443.task_compute_mlp_U0.grp_do_mlp_fu_4710.resi_o_sm_i_U' info is :
// blk sig is {~vit_block_top_vit_block_top_inst.grp_dataflow_wrapper_fu_6443.task_compute_mlp_U0.grp_do_mlp_fu_4710.do_adapt_5_U0.resi_o_sm_blk_n data_FIFO}
                        if ((~grp_dataflow_wrapper_fu_6443.task_compute_mlp_U0.grp_do_mlp_fu_4710.do_adapt_5_U0.resi_o_sm_blk_n)) begin
                            if (~grp_dataflow_wrapper_fu_6443.task_compute_mlp_U0.grp_do_mlp_fu_4710.resi_o_sm_i_U.if_empty_n) begin
                                $display("//      Blocked by empty input FIFO 'vit_block_top_vit_block_top.grp_dataflow_wrapper_fu_6443.task_compute_mlp_U0.grp_do_mlp_fu_4710.resi_o_sm_i_U' written by process 'vit_block_top_vit_block_top.grp_dataflow_wrapper_fu_6443.task_compute_mlp_U0.grp_do_mlp_fu_4710.stream_merge_U0'");
                                $fdisplay(fp, "Dependence_Channel_path vit_block_top_vit_block_top.grp_dataflow_wrapper_fu_6443.task_compute_mlp_U0.grp_do_mlp_fu_4710.resi_o_sm_i_U");
                                $fdisplay(fp, "Dependence_Channel_status EMPTY");
                            end
                            else if (~grp_dataflow_wrapper_fu_6443.task_compute_mlp_U0.grp_do_mlp_fu_4710.resi_o_sm_i_U.if_full_n) begin
                                $display("//      Blocked by full output FIFO 'vit_block_top_vit_block_top.grp_dataflow_wrapper_fu_6443.task_compute_mlp_U0.grp_do_mlp_fu_4710.resi_o_sm_i_U' read by process 'vit_block_top_vit_block_top.grp_dataflow_wrapper_fu_6443.task_compute_mlp_U0.grp_do_mlp_fu_4710.stream_merge_U0'");
                                $fdisplay(fp, "Dependence_Channel_path vit_block_top_vit_block_top.grp_dataflow_wrapper_fu_6443.task_compute_mlp_U0.grp_do_mlp_fu_4710.resi_o_sm_i_U");
                                $fdisplay(fp, "Dependence_Channel_status FULL");
                            end
                        end
// for dep channel 'vit_block_top_vit_block_top.grp_dataflow_wrapper_fu_6443.task_compute_mlp_U0.grp_do_mlp_fu_4710.start_for_stream_merge_U0_U' info is :
// blk sig is {{~vit_block_top_vit_block_top_inst.grp_dataflow_wrapper_fu_6443.task_compute_mlp_U0.grp_do_mlp_fu_4710.start_for_stream_merge_U0_U.if_full_n & vit_block_top_vit_block_top_inst.grp_dataflow_wrapper_fu_6443.task_compute_mlp_U0.grp_do_mlp_fu_4710.do_adapt_5_U0.ap_start & ~vit_block_top_vit_block_top_inst.grp_dataflow_wrapper_fu_6443.task_compute_mlp_U0.grp_do_mlp_fu_4710.do_adapt_5_U0.real_start & (trans_in_cnt_42 == trans_out_cnt_42) & ~vit_block_top_vit_block_top_inst.grp_dataflow_wrapper_fu_6443.task_compute_mlp_U0.grp_do_mlp_fu_4710.start_for_stream_merge_U0_U.if_read} start_FIFO}
                        if ((~grp_dataflow_wrapper_fu_6443.task_compute_mlp_U0.grp_do_mlp_fu_4710.start_for_stream_merge_U0_U.if_full_n & grp_dataflow_wrapper_fu_6443.task_compute_mlp_U0.grp_do_mlp_fu_4710.do_adapt_5_U0.ap_start & ~grp_dataflow_wrapper_fu_6443.task_compute_mlp_U0.grp_do_mlp_fu_4710.do_adapt_5_U0.real_start & (trans_in_cnt_42 == trans_out_cnt_42) & ~grp_dataflow_wrapper_fu_6443.task_compute_mlp_U0.grp_do_mlp_fu_4710.start_for_stream_merge_U0_U.if_read)) begin
                            $display("//      Blocked by full output start propagation FIFO 'vit_block_top_vit_block_top.grp_dataflow_wrapper_fu_6443.task_compute_mlp_U0.grp_do_mlp_fu_4710.start_for_stream_merge_U0_U' read by process 'vit_block_top_vit_block_top.grp_dataflow_wrapper_fu_6443.task_compute_mlp_U0.grp_do_mlp_fu_4710.stream_merge_U0',");
                        end
                    end
                    endcase
                end
                52 : begin // for proc 'vit_block_top_vit_block_top.grp_dataflow_wrapper_fu_6443.task_compute_mlp_U0.grp_do_mlp_fu_4710.do_layernorm_inter_token_U0'
                    case(index2)
                    49: begin //  for dep proc 'vit_block_top_vit_block_top.grp_dataflow_wrapper_fu_6443.task_compute_mlp_U0.grp_do_mlp_fu_4710.stream_copy_U0'
// for dep channel 'vit_block_top_vit_block_top.grp_dataflow_wrapper_fu_6443.task_compute_mlp_U0.grp_do_mlp_fu_4710.main_sm_i_U' info is :
// blk sig is {~vit_block_top_vit_block_top_inst.grp_dataflow_wrapper_fu_6443.task_compute_mlp_U0.grp_do_mlp_fu_4710.do_layernorm_inter_token_U0.grp_do_layernorm_inter_token_Pipeline_WAVE_LOOP_CT_PIPELINE_LOOP_fu_138.main_sm_blk_n data_FIFO}
                        if ((~grp_dataflow_wrapper_fu_6443.task_compute_mlp_U0.grp_do_mlp_fu_4710.do_layernorm_inter_token_U0.grp_do_layernorm_inter_token_Pipeline_WAVE_LOOP_CT_PIPELINE_LOOP_fu_138.main_sm_blk_n)) begin
                            if (~grp_dataflow_wrapper_fu_6443.task_compute_mlp_U0.grp_do_mlp_fu_4710.main_sm_i_U.if_empty_n) begin
                                $display("//      Blocked by empty input FIFO 'vit_block_top_vit_block_top.grp_dataflow_wrapper_fu_6443.task_compute_mlp_U0.grp_do_mlp_fu_4710.main_sm_i_U' written by process 'vit_block_top_vit_block_top.grp_dataflow_wrapper_fu_6443.task_compute_mlp_U0.grp_do_mlp_fu_4710.stream_copy_U0'");
                                $fdisplay(fp, "Dependence_Channel_path vit_block_top_vit_block_top.grp_dataflow_wrapper_fu_6443.task_compute_mlp_U0.grp_do_mlp_fu_4710.main_sm_i_U");
                                $fdisplay(fp, "Dependence_Channel_status EMPTY");
                            end
                            else if (~grp_dataflow_wrapper_fu_6443.task_compute_mlp_U0.grp_do_mlp_fu_4710.main_sm_i_U.if_full_n) begin
                                $display("//      Blocked by full output FIFO 'vit_block_top_vit_block_top.grp_dataflow_wrapper_fu_6443.task_compute_mlp_U0.grp_do_mlp_fu_4710.main_sm_i_U' read by process 'vit_block_top_vit_block_top.grp_dataflow_wrapper_fu_6443.task_compute_mlp_U0.grp_do_mlp_fu_4710.stream_copy_U0'");
                                $fdisplay(fp, "Dependence_Channel_path vit_block_top_vit_block_top.grp_dataflow_wrapper_fu_6443.task_compute_mlp_U0.grp_do_mlp_fu_4710.main_sm_i_U");
                                $fdisplay(fp, "Dependence_Channel_status FULL");
                            end
                        end
// for dep channel 'vit_block_top_vit_block_top.grp_dataflow_wrapper_fu_6443.task_compute_mlp_U0.grp_do_mlp_fu_4710.start_for_do_layernorm_inter_token_U0_U' info is :
// blk sig is {{~vit_block_top_vit_block_top_inst.grp_dataflow_wrapper_fu_6443.task_compute_mlp_U0.grp_do_mlp_fu_4710.start_for_do_layernorm_inter_token_U0_U.if_empty_n & vit_block_top_vit_block_top_inst.grp_dataflow_wrapper_fu_6443.task_compute_mlp_U0.grp_do_mlp_fu_4710.do_layernorm_inter_token_U0.ap_idle & ~vit_block_top_vit_block_top_inst.grp_dataflow_wrapper_fu_6443.task_compute_mlp_U0.grp_do_mlp_fu_4710.start_for_do_layernorm_inter_token_U0_U.if_write} start_FIFO}
                        if ((~grp_dataflow_wrapper_fu_6443.task_compute_mlp_U0.grp_do_mlp_fu_4710.start_for_do_layernorm_inter_token_U0_U.if_empty_n & grp_dataflow_wrapper_fu_6443.task_compute_mlp_U0.grp_do_mlp_fu_4710.do_layernorm_inter_token_U0.ap_idle & ~grp_dataflow_wrapper_fu_6443.task_compute_mlp_U0.grp_do_mlp_fu_4710.start_for_do_layernorm_inter_token_U0_U.if_write)) begin
                            $display("//      Blocked by missing 'ap_start' from start propagation FIFO 'vit_block_top_vit_block_top.grp_dataflow_wrapper_fu_6443.task_compute_mlp_U0.grp_do_mlp_fu_4710.start_for_do_layernorm_inter_token_U0_U' written by process 'vit_block_top_vit_block_top.grp_dataflow_wrapper_fu_6443.task_compute_mlp_U0.grp_do_mlp_fu_4710.stream_copy_U0',");
                        end
                    end
                    53: begin //  for dep proc 'vit_block_top_vit_block_top.grp_dataflow_wrapper_fu_6443.task_compute_mlp_U0.grp_do_mlp_fu_4710.do_matmul_3_U0'
// for dep channel 'vit_block_top_vit_block_top.grp_dataflow_wrapper_fu_6443.task_compute_mlp_U0.grp_do_mlp_fu_4710.ln_sm_i_U' info is :
// blk sig is {~vit_block_top_vit_block_top_inst.grp_dataflow_wrapper_fu_6443.task_compute_mlp_U0.grp_do_mlp_fu_4710.do_layernorm_inter_token_U0.grp_do_layernorm_inter_token_Pipeline_WAVE_LOOP_CT_PIPELINE_LOOP_fu_138.ln_sm_blk_n data_FIFO}
                        if ((~grp_dataflow_wrapper_fu_6443.task_compute_mlp_U0.grp_do_mlp_fu_4710.do_layernorm_inter_token_U0.grp_do_layernorm_inter_token_Pipeline_WAVE_LOOP_CT_PIPELINE_LOOP_fu_138.ln_sm_blk_n)) begin
                            if (~grp_dataflow_wrapper_fu_6443.task_compute_mlp_U0.grp_do_mlp_fu_4710.ln_sm_i_U.if_empty_n) begin
                                $display("//      Blocked by empty input FIFO 'vit_block_top_vit_block_top.grp_dataflow_wrapper_fu_6443.task_compute_mlp_U0.grp_do_mlp_fu_4710.ln_sm_i_U' written by process 'vit_block_top_vit_block_top.grp_dataflow_wrapper_fu_6443.task_compute_mlp_U0.grp_do_mlp_fu_4710.do_matmul_3_U0'");
                                $fdisplay(fp, "Dependence_Channel_path vit_block_top_vit_block_top.grp_dataflow_wrapper_fu_6443.task_compute_mlp_U0.grp_do_mlp_fu_4710.ln_sm_i_U");
                                $fdisplay(fp, "Dependence_Channel_status EMPTY");
                            end
                            else if (~grp_dataflow_wrapper_fu_6443.task_compute_mlp_U0.grp_do_mlp_fu_4710.ln_sm_i_U.if_full_n) begin
                                $display("//      Blocked by full output FIFO 'vit_block_top_vit_block_top.grp_dataflow_wrapper_fu_6443.task_compute_mlp_U0.grp_do_mlp_fu_4710.ln_sm_i_U' read by process 'vit_block_top_vit_block_top.grp_dataflow_wrapper_fu_6443.task_compute_mlp_U0.grp_do_mlp_fu_4710.do_matmul_3_U0'");
                                $fdisplay(fp, "Dependence_Channel_path vit_block_top_vit_block_top.grp_dataflow_wrapper_fu_6443.task_compute_mlp_U0.grp_do_mlp_fu_4710.ln_sm_i_U");
                                $fdisplay(fp, "Dependence_Channel_status FULL");
                            end
                        end
// for dep channel 'vit_block_top_vit_block_top.grp_dataflow_wrapper_fu_6443.task_compute_mlp_U0.grp_do_mlp_fu_4710.start_for_do_matmul_3_U0_U' info is :
// blk sig is {{~vit_block_top_vit_block_top_inst.grp_dataflow_wrapper_fu_6443.task_compute_mlp_U0.grp_do_mlp_fu_4710.start_for_do_matmul_3_U0_U.if_full_n & vit_block_top_vit_block_top_inst.grp_dataflow_wrapper_fu_6443.task_compute_mlp_U0.grp_do_mlp_fu_4710.do_layernorm_inter_token_U0.ap_start & ~vit_block_top_vit_block_top_inst.grp_dataflow_wrapper_fu_6443.task_compute_mlp_U0.grp_do_mlp_fu_4710.do_layernorm_inter_token_U0.real_start & (trans_in_cnt_33 == trans_out_cnt_33) & ~vit_block_top_vit_block_top_inst.grp_dataflow_wrapper_fu_6443.task_compute_mlp_U0.grp_do_mlp_fu_4710.start_for_do_matmul_3_U0_U.if_read} start_FIFO}
                        if ((~grp_dataflow_wrapper_fu_6443.task_compute_mlp_U0.grp_do_mlp_fu_4710.start_for_do_matmul_3_U0_U.if_full_n & grp_dataflow_wrapper_fu_6443.task_compute_mlp_U0.grp_do_mlp_fu_4710.do_layernorm_inter_token_U0.ap_start & ~grp_dataflow_wrapper_fu_6443.task_compute_mlp_U0.grp_do_mlp_fu_4710.do_layernorm_inter_token_U0.real_start & (trans_in_cnt_33 == trans_out_cnt_33) & ~grp_dataflow_wrapper_fu_6443.task_compute_mlp_U0.grp_do_mlp_fu_4710.start_for_do_matmul_3_U0_U.if_read)) begin
                            $display("//      Blocked by full output start propagation FIFO 'vit_block_top_vit_block_top.grp_dataflow_wrapper_fu_6443.task_compute_mlp_U0.grp_do_mlp_fu_4710.start_for_do_matmul_3_U0_U' read by process 'vit_block_top_vit_block_top.grp_dataflow_wrapper_fu_6443.task_compute_mlp_U0.grp_do_mlp_fu_4710.do_matmul_3_U0',");
                        end
                    end
                    54: begin //  for dep proc 'vit_block_top_vit_block_top.grp_dataflow_wrapper_fu_6443.task_compute_mlp_U0.grp_do_mlp_fu_4710.do_matmul_3_U0.do_adapt_1_1_U0'
// for dep channel 'vit_block_top_vit_block_top.grp_dataflow_wrapper_fu_6443.task_compute_mlp_U0.grp_do_mlp_fu_4710.ln_sm_i_U' info is :
// blk sig is {~vit_block_top_vit_block_top_inst.grp_dataflow_wrapper_fu_6443.task_compute_mlp_U0.grp_do_mlp_fu_4710.do_layernorm_inter_token_U0.grp_do_layernorm_inter_token_Pipeline_WAVE_LOOP_CT_PIPELINE_LOOP_fu_138.ln_sm_blk_n data_FIFO}
                        if ((~grp_dataflow_wrapper_fu_6443.task_compute_mlp_U0.grp_do_mlp_fu_4710.do_layernorm_inter_token_U0.grp_do_layernorm_inter_token_Pipeline_WAVE_LOOP_CT_PIPELINE_LOOP_fu_138.ln_sm_blk_n)) begin
                            if (~grp_dataflow_wrapper_fu_6443.task_compute_mlp_U0.grp_do_mlp_fu_4710.ln_sm_i_U.if_empty_n) begin
                                $display("//      Blocked by empty input FIFO 'vit_block_top_vit_block_top.grp_dataflow_wrapper_fu_6443.task_compute_mlp_U0.grp_do_mlp_fu_4710.ln_sm_i_U' written by process 'vit_block_top_vit_block_top.grp_dataflow_wrapper_fu_6443.task_compute_mlp_U0.grp_do_mlp_fu_4710.do_matmul_3_U0.do_adapt_1_1_U0'");
                                $fdisplay(fp, "Dependence_Channel_path vit_block_top_vit_block_top.grp_dataflow_wrapper_fu_6443.task_compute_mlp_U0.grp_do_mlp_fu_4710.ln_sm_i_U");
                                $fdisplay(fp, "Dependence_Channel_status EMPTY");
                            end
                            else if (~grp_dataflow_wrapper_fu_6443.task_compute_mlp_U0.grp_do_mlp_fu_4710.ln_sm_i_U.if_full_n) begin
                                $display("//      Blocked by full output FIFO 'vit_block_top_vit_block_top.grp_dataflow_wrapper_fu_6443.task_compute_mlp_U0.grp_do_mlp_fu_4710.ln_sm_i_U' read by process 'vit_block_top_vit_block_top.grp_dataflow_wrapper_fu_6443.task_compute_mlp_U0.grp_do_mlp_fu_4710.do_matmul_3_U0.do_adapt_1_1_U0'");
                                $fdisplay(fp, "Dependence_Channel_path vit_block_top_vit_block_top.grp_dataflow_wrapper_fu_6443.task_compute_mlp_U0.grp_do_mlp_fu_4710.ln_sm_i_U");
                                $fdisplay(fp, "Dependence_Channel_status FULL");
                            end
                        end
                    end
                    endcase
                end
                53 : begin // for proc 'vit_block_top_vit_block_top.grp_dataflow_wrapper_fu_6443.task_compute_mlp_U0.grp_do_mlp_fu_4710.do_matmul_3_U0'
                    case(index2)
                    52: begin //  for dep proc 'vit_block_top_vit_block_top.grp_dataflow_wrapper_fu_6443.task_compute_mlp_U0.grp_do_mlp_fu_4710.do_layernorm_inter_token_U0'
// for dep channel 'vit_block_top_vit_block_top.grp_dataflow_wrapper_fu_6443.task_compute_mlp_U0.grp_do_mlp_fu_4710.ln_sm_i_U' info is :
// blk sig is {~vit_block_top_vit_block_top_inst.grp_dataflow_wrapper_fu_6443.task_compute_mlp_U0.grp_do_mlp_fu_4710.do_matmul_3_U0.do_adapt_1_1_U0.ln_sm_blk_n data_FIFO}
                        if ((~grp_dataflow_wrapper_fu_6443.task_compute_mlp_U0.grp_do_mlp_fu_4710.do_matmul_3_U0.do_adapt_1_1_U0.ln_sm_blk_n)) begin
                            if (~grp_dataflow_wrapper_fu_6443.task_compute_mlp_U0.grp_do_mlp_fu_4710.ln_sm_i_U.if_empty_n) begin
                                $display("//      Blocked by empty input FIFO 'vit_block_top_vit_block_top.grp_dataflow_wrapper_fu_6443.task_compute_mlp_U0.grp_do_mlp_fu_4710.ln_sm_i_U' written by process 'vit_block_top_vit_block_top.grp_dataflow_wrapper_fu_6443.task_compute_mlp_U0.grp_do_mlp_fu_4710.do_layernorm_inter_token_U0'");
                                $fdisplay(fp, "Dependence_Channel_path vit_block_top_vit_block_top.grp_dataflow_wrapper_fu_6443.task_compute_mlp_U0.grp_do_mlp_fu_4710.ln_sm_i_U");
                                $fdisplay(fp, "Dependence_Channel_status EMPTY");
                            end
                            else if (~grp_dataflow_wrapper_fu_6443.task_compute_mlp_U0.grp_do_mlp_fu_4710.ln_sm_i_U.if_full_n) begin
                                $display("//      Blocked by full output FIFO 'vit_block_top_vit_block_top.grp_dataflow_wrapper_fu_6443.task_compute_mlp_U0.grp_do_mlp_fu_4710.ln_sm_i_U' read by process 'vit_block_top_vit_block_top.grp_dataflow_wrapper_fu_6443.task_compute_mlp_U0.grp_do_mlp_fu_4710.do_layernorm_inter_token_U0'");
                                $fdisplay(fp, "Dependence_Channel_path vit_block_top_vit_block_top.grp_dataflow_wrapper_fu_6443.task_compute_mlp_U0.grp_do_mlp_fu_4710.ln_sm_i_U");
                                $fdisplay(fp, "Dependence_Channel_status FULL");
                            end
                        end
// for dep channel 'vit_block_top_vit_block_top.grp_dataflow_wrapper_fu_6443.task_compute_mlp_U0.grp_do_mlp_fu_4710.start_for_do_matmul_3_U0_U' info is :
// blk sig is {{~vit_block_top_vit_block_top_inst.grp_dataflow_wrapper_fu_6443.task_compute_mlp_U0.grp_do_mlp_fu_4710.start_for_do_matmul_3_U0_U.if_empty_n & vit_block_top_vit_block_top_inst.grp_dataflow_wrapper_fu_6443.task_compute_mlp_U0.grp_do_mlp_fu_4710.do_matmul_3_U0.ap_idle & ~vit_block_top_vit_block_top_inst.grp_dataflow_wrapper_fu_6443.task_compute_mlp_U0.grp_do_mlp_fu_4710.start_for_do_matmul_3_U0_U.if_write} start_FIFO}
                        if ((~grp_dataflow_wrapper_fu_6443.task_compute_mlp_U0.grp_do_mlp_fu_4710.start_for_do_matmul_3_U0_U.if_empty_n & grp_dataflow_wrapper_fu_6443.task_compute_mlp_U0.grp_do_mlp_fu_4710.do_matmul_3_U0.ap_idle & ~grp_dataflow_wrapper_fu_6443.task_compute_mlp_U0.grp_do_mlp_fu_4710.start_for_do_matmul_3_U0_U.if_write)) begin
                            $display("//      Blocked by missing 'ap_start' from start propagation FIFO 'vit_block_top_vit_block_top.grp_dataflow_wrapper_fu_6443.task_compute_mlp_U0.grp_do_mlp_fu_4710.start_for_do_matmul_3_U0_U' written by process 'vit_block_top_vit_block_top.grp_dataflow_wrapper_fu_6443.task_compute_mlp_U0.grp_do_mlp_fu_4710.do_layernorm_inter_token_U0',");
                        end
                    end
                    58: begin //  for dep proc 'vit_block_top_vit_block_top.grp_dataflow_wrapper_fu_6443.task_compute_mlp_U0.grp_do_mlp_fu_4710.do_gelu_U0'
// for dep channel 'vit_block_top_vit_block_top.grp_dataflow_wrapper_fu_6443.task_compute_mlp_U0.grp_do_mlp_fu_4710.m1_sm_i_U' info is :
// blk sig is {~vit_block_top_vit_block_top_inst.grp_dataflow_wrapper_fu_6443.task_compute_mlp_U0.grp_do_mlp_fu_4710.do_matmul_3_U0.do_adapt_12_U0.m1_sm_blk_n data_FIFO}
                        if ((~grp_dataflow_wrapper_fu_6443.task_compute_mlp_U0.grp_do_mlp_fu_4710.do_matmul_3_U0.do_adapt_12_U0.m1_sm_blk_n)) begin
                            if (~grp_dataflow_wrapper_fu_6443.task_compute_mlp_U0.grp_do_mlp_fu_4710.m1_sm_i_U.if_empty_n) begin
                                $display("//      Blocked by empty input FIFO 'vit_block_top_vit_block_top.grp_dataflow_wrapper_fu_6443.task_compute_mlp_U0.grp_do_mlp_fu_4710.m1_sm_i_U' written by process 'vit_block_top_vit_block_top.grp_dataflow_wrapper_fu_6443.task_compute_mlp_U0.grp_do_mlp_fu_4710.do_gelu_U0'");
                                $fdisplay(fp, "Dependence_Channel_path vit_block_top_vit_block_top.grp_dataflow_wrapper_fu_6443.task_compute_mlp_U0.grp_do_mlp_fu_4710.m1_sm_i_U");
                                $fdisplay(fp, "Dependence_Channel_status EMPTY");
                            end
                            else if (~grp_dataflow_wrapper_fu_6443.task_compute_mlp_U0.grp_do_mlp_fu_4710.m1_sm_i_U.if_full_n) begin
                                $display("//      Blocked by full output FIFO 'vit_block_top_vit_block_top.grp_dataflow_wrapper_fu_6443.task_compute_mlp_U0.grp_do_mlp_fu_4710.m1_sm_i_U' read by process 'vit_block_top_vit_block_top.grp_dataflow_wrapper_fu_6443.task_compute_mlp_U0.grp_do_mlp_fu_4710.do_gelu_U0'");
                                $fdisplay(fp, "Dependence_Channel_path vit_block_top_vit_block_top.grp_dataflow_wrapper_fu_6443.task_compute_mlp_U0.grp_do_mlp_fu_4710.m1_sm_i_U");
                                $fdisplay(fp, "Dependence_Channel_status FULL");
                            end
                        end
// for dep channel 'vit_block_top_vit_block_top.grp_dataflow_wrapper_fu_6443.task_compute_mlp_U0.grp_do_mlp_fu_4710.start_for_do_gelu_U0_U' info is :
// blk sig is {{~vit_block_top_vit_block_top_inst.grp_dataflow_wrapper_fu_6443.task_compute_mlp_U0.grp_do_mlp_fu_4710.start_for_do_gelu_U0_U.if_full_n & vit_block_top_vit_block_top_inst.grp_dataflow_wrapper_fu_6443.task_compute_mlp_U0.grp_do_mlp_fu_4710.do_matmul_3_U0.ap_start & ~vit_block_top_vit_block_top_inst.grp_dataflow_wrapper_fu_6443.task_compute_mlp_U0.grp_do_mlp_fu_4710.do_matmul_3_U0.real_start & (trans_in_cnt_37 == trans_out_cnt_37) & ~vit_block_top_vit_block_top_inst.grp_dataflow_wrapper_fu_6443.task_compute_mlp_U0.grp_do_mlp_fu_4710.start_for_do_gelu_U0_U.if_read} start_FIFO}
                        if ((~grp_dataflow_wrapper_fu_6443.task_compute_mlp_U0.grp_do_mlp_fu_4710.start_for_do_gelu_U0_U.if_full_n & grp_dataflow_wrapper_fu_6443.task_compute_mlp_U0.grp_do_mlp_fu_4710.do_matmul_3_U0.ap_start & ~grp_dataflow_wrapper_fu_6443.task_compute_mlp_U0.grp_do_mlp_fu_4710.do_matmul_3_U0.real_start & (trans_in_cnt_37 == trans_out_cnt_37) & ~grp_dataflow_wrapper_fu_6443.task_compute_mlp_U0.grp_do_mlp_fu_4710.start_for_do_gelu_U0_U.if_read)) begin
                            $display("//      Blocked by full output start propagation FIFO 'vit_block_top_vit_block_top.grp_dataflow_wrapper_fu_6443.task_compute_mlp_U0.grp_do_mlp_fu_4710.start_for_do_gelu_U0_U' read by process 'vit_block_top_vit_block_top.grp_dataflow_wrapper_fu_6443.task_compute_mlp_U0.grp_do_mlp_fu_4710.do_gelu_U0',");
                        end
                    end
                    endcase
                end
                54 : begin // for proc 'vit_block_top_vit_block_top.grp_dataflow_wrapper_fu_6443.task_compute_mlp_U0.grp_do_mlp_fu_4710.do_matmul_3_U0.do_adapt_1_1_U0'
                    case(index2)
                    52: begin //  for dep proc 'vit_block_top_vit_block_top.grp_dataflow_wrapper_fu_6443.task_compute_mlp_U0.grp_do_mlp_fu_4710.do_layernorm_inter_token_U0'
// for dep channel 'vit_block_top_vit_block_top.grp_dataflow_wrapper_fu_6443.task_compute_mlp_U0.grp_do_mlp_fu_4710.ln_sm_i_U' info is :
// blk sig is {~vit_block_top_vit_block_top_inst.grp_dataflow_wrapper_fu_6443.task_compute_mlp_U0.grp_do_mlp_fu_4710.do_matmul_3_U0.do_adapt_1_1_U0.ln_sm_blk_n data_FIFO}
                        if ((~grp_dataflow_wrapper_fu_6443.task_compute_mlp_U0.grp_do_mlp_fu_4710.do_matmul_3_U0.do_adapt_1_1_U0.ln_sm_blk_n)) begin
                            if (~grp_dataflow_wrapper_fu_6443.task_compute_mlp_U0.grp_do_mlp_fu_4710.ln_sm_i_U.if_empty_n) begin
                                $display("//      Blocked by empty input FIFO 'vit_block_top_vit_block_top.grp_dataflow_wrapper_fu_6443.task_compute_mlp_U0.grp_do_mlp_fu_4710.ln_sm_i_U' written by process 'vit_block_top_vit_block_top.grp_dataflow_wrapper_fu_6443.task_compute_mlp_U0.grp_do_mlp_fu_4710.do_layernorm_inter_token_U0'");
                                $fdisplay(fp, "Dependence_Channel_path vit_block_top_vit_block_top.grp_dataflow_wrapper_fu_6443.task_compute_mlp_U0.grp_do_mlp_fu_4710.ln_sm_i_U");
                                $fdisplay(fp, "Dependence_Channel_status EMPTY");
                            end
                            else if (~grp_dataflow_wrapper_fu_6443.task_compute_mlp_U0.grp_do_mlp_fu_4710.ln_sm_i_U.if_full_n) begin
                                $display("//      Blocked by full output FIFO 'vit_block_top_vit_block_top.grp_dataflow_wrapper_fu_6443.task_compute_mlp_U0.grp_do_mlp_fu_4710.ln_sm_i_U' read by process 'vit_block_top_vit_block_top.grp_dataflow_wrapper_fu_6443.task_compute_mlp_U0.grp_do_mlp_fu_4710.do_layernorm_inter_token_U0'");
                                $fdisplay(fp, "Dependence_Channel_path vit_block_top_vit_block_top.grp_dataflow_wrapper_fu_6443.task_compute_mlp_U0.grp_do_mlp_fu_4710.ln_sm_i_U");
                                $fdisplay(fp, "Dependence_Channel_status FULL");
                            end
                        end
                    end
                    55: begin //  for dep proc 'vit_block_top_vit_block_top.grp_dataflow_wrapper_fu_6443.task_compute_mlp_U0.grp_do_mlp_fu_4710.do_matmul_3_U0.matmul_step1_cache_window_3_U0'
// for dep channel 'vit_block_top_vit_block_top.grp_dataflow_wrapper_fu_6443.task_compute_mlp_U0.grp_do_mlp_fu_4710.do_matmul_3_U0.adpt_sm_i_U' info is :
// blk sig is {~vit_block_top_vit_block_top_inst.grp_dataflow_wrapper_fu_6443.task_compute_mlp_U0.grp_do_mlp_fu_4710.do_matmul_3_U0.do_adapt_1_1_U0.adpt_sm_blk_n data_FIFO}
                        if ((~grp_dataflow_wrapper_fu_6443.task_compute_mlp_U0.grp_do_mlp_fu_4710.do_matmul_3_U0.do_adapt_1_1_U0.adpt_sm_blk_n)) begin
                            if (~grp_dataflow_wrapper_fu_6443.task_compute_mlp_U0.grp_do_mlp_fu_4710.do_matmul_3_U0.adpt_sm_i_U.if_empty_n) begin
                                $display("//      Blocked by empty input FIFO 'vit_block_top_vit_block_top.grp_dataflow_wrapper_fu_6443.task_compute_mlp_U0.grp_do_mlp_fu_4710.do_matmul_3_U0.adpt_sm_i_U' written by process 'vit_block_top_vit_block_top.grp_dataflow_wrapper_fu_6443.task_compute_mlp_U0.grp_do_mlp_fu_4710.do_matmul_3_U0.matmul_step1_cache_window_3_U0'");
                                $fdisplay(fp, "Dependence_Channel_path vit_block_top_vit_block_top.grp_dataflow_wrapper_fu_6443.task_compute_mlp_U0.grp_do_mlp_fu_4710.do_matmul_3_U0.adpt_sm_i_U");
                                $fdisplay(fp, "Dependence_Channel_status EMPTY");
                            end
                            else if (~grp_dataflow_wrapper_fu_6443.task_compute_mlp_U0.grp_do_mlp_fu_4710.do_matmul_3_U0.adpt_sm_i_U.if_full_n) begin
                                $display("//      Blocked by full output FIFO 'vit_block_top_vit_block_top.grp_dataflow_wrapper_fu_6443.task_compute_mlp_U0.grp_do_mlp_fu_4710.do_matmul_3_U0.adpt_sm_i_U' read by process 'vit_block_top_vit_block_top.grp_dataflow_wrapper_fu_6443.task_compute_mlp_U0.grp_do_mlp_fu_4710.do_matmul_3_U0.matmul_step1_cache_window_3_U0'");
                                $fdisplay(fp, "Dependence_Channel_path vit_block_top_vit_block_top.grp_dataflow_wrapper_fu_6443.task_compute_mlp_U0.grp_do_mlp_fu_4710.do_matmul_3_U0.adpt_sm_i_U");
                                $fdisplay(fp, "Dependence_Channel_status FULL");
                            end
                        end
// for dep channel 'vit_block_top_vit_block_top.grp_dataflow_wrapper_fu_6443.task_compute_mlp_U0.grp_do_mlp_fu_4710.do_matmul_3_U0.start_for_matmul_step1_cache_window_3_U0_U' info is :
// blk sig is {{~vit_block_top_vit_block_top_inst.grp_dataflow_wrapper_fu_6443.task_compute_mlp_U0.grp_do_mlp_fu_4710.do_matmul_3_U0.start_for_matmul_step1_cache_window_3_U0_U.if_full_n & vit_block_top_vit_block_top_inst.grp_dataflow_wrapper_fu_6443.task_compute_mlp_U0.grp_do_mlp_fu_4710.do_matmul_3_U0.do_adapt_1_1_U0.ap_start & ~vit_block_top_vit_block_top_inst.grp_dataflow_wrapper_fu_6443.task_compute_mlp_U0.grp_do_mlp_fu_4710.do_matmul_3_U0.do_adapt_1_1_U0.real_start & (trans_in_cnt_34 == trans_out_cnt_34) & ~vit_block_top_vit_block_top_inst.grp_dataflow_wrapper_fu_6443.task_compute_mlp_U0.grp_do_mlp_fu_4710.do_matmul_3_U0.start_for_matmul_step1_cache_window_3_U0_U.if_read} start_FIFO}
                        if ((~grp_dataflow_wrapper_fu_6443.task_compute_mlp_U0.grp_do_mlp_fu_4710.do_matmul_3_U0.start_for_matmul_step1_cache_window_3_U0_U.if_full_n & grp_dataflow_wrapper_fu_6443.task_compute_mlp_U0.grp_do_mlp_fu_4710.do_matmul_3_U0.do_adapt_1_1_U0.ap_start & ~grp_dataflow_wrapper_fu_6443.task_compute_mlp_U0.grp_do_mlp_fu_4710.do_matmul_3_U0.do_adapt_1_1_U0.real_start & (trans_in_cnt_34 == trans_out_cnt_34) & ~grp_dataflow_wrapper_fu_6443.task_compute_mlp_U0.grp_do_mlp_fu_4710.do_matmul_3_U0.start_for_matmul_step1_cache_window_3_U0_U.if_read)) begin
                            $display("//      Blocked by full output start propagation FIFO 'vit_block_top_vit_block_top.grp_dataflow_wrapper_fu_6443.task_compute_mlp_U0.grp_do_mlp_fu_4710.do_matmul_3_U0.start_for_matmul_step1_cache_window_3_U0_U' read by process 'vit_block_top_vit_block_top.grp_dataflow_wrapper_fu_6443.task_compute_mlp_U0.grp_do_mlp_fu_4710.do_matmul_3_U0.matmul_step1_cache_window_3_U0',");
                        end
                    end
                    endcase
                end
                55 : begin // for proc 'vit_block_top_vit_block_top.grp_dataflow_wrapper_fu_6443.task_compute_mlp_U0.grp_do_mlp_fu_4710.do_matmul_3_U0.matmul_step1_cache_window_3_U0'
                    case(index2)
                    54: begin //  for dep proc 'vit_block_top_vit_block_top.grp_dataflow_wrapper_fu_6443.task_compute_mlp_U0.grp_do_mlp_fu_4710.do_matmul_3_U0.do_adapt_1_1_U0'
// for dep channel 'vit_block_top_vit_block_top.grp_dataflow_wrapper_fu_6443.task_compute_mlp_U0.grp_do_mlp_fu_4710.do_matmul_3_U0.adpt_sm_i_U' info is :
// blk sig is {~vit_block_top_vit_block_top_inst.grp_dataflow_wrapper_fu_6443.task_compute_mlp_U0.grp_do_mlp_fu_4710.do_matmul_3_U0.matmul_step1_cache_window_3_U0.adpt_sm_blk_n data_FIFO}
                        if ((~grp_dataflow_wrapper_fu_6443.task_compute_mlp_U0.grp_do_mlp_fu_4710.do_matmul_3_U0.matmul_step1_cache_window_3_U0.adpt_sm_blk_n)) begin
                            if (~grp_dataflow_wrapper_fu_6443.task_compute_mlp_U0.grp_do_mlp_fu_4710.do_matmul_3_U0.adpt_sm_i_U.if_empty_n) begin
                                $display("//      Blocked by empty input FIFO 'vit_block_top_vit_block_top.grp_dataflow_wrapper_fu_6443.task_compute_mlp_U0.grp_do_mlp_fu_4710.do_matmul_3_U0.adpt_sm_i_U' written by process 'vit_block_top_vit_block_top.grp_dataflow_wrapper_fu_6443.task_compute_mlp_U0.grp_do_mlp_fu_4710.do_matmul_3_U0.do_adapt_1_1_U0'");
                                $fdisplay(fp, "Dependence_Channel_path vit_block_top_vit_block_top.grp_dataflow_wrapper_fu_6443.task_compute_mlp_U0.grp_do_mlp_fu_4710.do_matmul_3_U0.adpt_sm_i_U");
                                $fdisplay(fp, "Dependence_Channel_status EMPTY");
                            end
                            else if (~grp_dataflow_wrapper_fu_6443.task_compute_mlp_U0.grp_do_mlp_fu_4710.do_matmul_3_U0.adpt_sm_i_U.if_full_n) begin
                                $display("//      Blocked by full output FIFO 'vit_block_top_vit_block_top.grp_dataflow_wrapper_fu_6443.task_compute_mlp_U0.grp_do_mlp_fu_4710.do_matmul_3_U0.adpt_sm_i_U' read by process 'vit_block_top_vit_block_top.grp_dataflow_wrapper_fu_6443.task_compute_mlp_U0.grp_do_mlp_fu_4710.do_matmul_3_U0.do_adapt_1_1_U0'");
                                $fdisplay(fp, "Dependence_Channel_path vit_block_top_vit_block_top.grp_dataflow_wrapper_fu_6443.task_compute_mlp_U0.grp_do_mlp_fu_4710.do_matmul_3_U0.adpt_sm_i_U");
                                $fdisplay(fp, "Dependence_Channel_status FULL");
                            end
                        end
// for dep channel 'vit_block_top_vit_block_top.grp_dataflow_wrapper_fu_6443.task_compute_mlp_U0.grp_do_mlp_fu_4710.do_matmul_3_U0.start_for_matmul_step1_cache_window_3_U0_U' info is :
// blk sig is {{~vit_block_top_vit_block_top_inst.grp_dataflow_wrapper_fu_6443.task_compute_mlp_U0.grp_do_mlp_fu_4710.do_matmul_3_U0.start_for_matmul_step1_cache_window_3_U0_U.if_empty_n & vit_block_top_vit_block_top_inst.grp_dataflow_wrapper_fu_6443.task_compute_mlp_U0.grp_do_mlp_fu_4710.do_matmul_3_U0.matmul_step1_cache_window_3_U0.ap_idle & ~vit_block_top_vit_block_top_inst.grp_dataflow_wrapper_fu_6443.task_compute_mlp_U0.grp_do_mlp_fu_4710.do_matmul_3_U0.start_for_matmul_step1_cache_window_3_U0_U.if_write} start_FIFO}
                        if ((~grp_dataflow_wrapper_fu_6443.task_compute_mlp_U0.grp_do_mlp_fu_4710.do_matmul_3_U0.start_for_matmul_step1_cache_window_3_U0_U.if_empty_n & grp_dataflow_wrapper_fu_6443.task_compute_mlp_U0.grp_do_mlp_fu_4710.do_matmul_3_U0.matmul_step1_cache_window_3_U0.ap_idle & ~grp_dataflow_wrapper_fu_6443.task_compute_mlp_U0.grp_do_mlp_fu_4710.do_matmul_3_U0.start_for_matmul_step1_cache_window_3_U0_U.if_write)) begin
                            $display("//      Blocked by missing 'ap_start' from start propagation FIFO 'vit_block_top_vit_block_top.grp_dataflow_wrapper_fu_6443.task_compute_mlp_U0.grp_do_mlp_fu_4710.do_matmul_3_U0.start_for_matmul_step1_cache_window_3_U0_U' written by process 'vit_block_top_vit_block_top.grp_dataflow_wrapper_fu_6443.task_compute_mlp_U0.grp_do_mlp_fu_4710.do_matmul_3_U0.do_adapt_1_1_U0',");
                        end
                    end
                    56: begin //  for dep proc 'vit_block_top_vit_block_top.grp_dataflow_wrapper_fu_6443.task_compute_mlp_U0.grp_do_mlp_fu_4710.do_matmul_3_U0.matmul_step2_mac_3_U0'
// for dep channel 'vit_block_top_vit_block_top.grp_dataflow_wrapper_fu_6443.task_compute_mlp_U0.grp_do_mlp_fu_4710.do_matmul_3_U0.cache_window_sm_i_U' info is :
// blk sig is {~vit_block_top_vit_block_top_inst.grp_dataflow_wrapper_fu_6443.task_compute_mlp_U0.grp_do_mlp_fu_4710.do_matmul_3_U0.matmul_step1_cache_window_3_U0.cache_window_sm_blk_n data_FIFO}
                        if ((~grp_dataflow_wrapper_fu_6443.task_compute_mlp_U0.grp_do_mlp_fu_4710.do_matmul_3_U0.matmul_step1_cache_window_3_U0.cache_window_sm_blk_n)) begin
                            if (~grp_dataflow_wrapper_fu_6443.task_compute_mlp_U0.grp_do_mlp_fu_4710.do_matmul_3_U0.cache_window_sm_i_U.if_empty_n) begin
                                $display("//      Blocked by empty input FIFO 'vit_block_top_vit_block_top.grp_dataflow_wrapper_fu_6443.task_compute_mlp_U0.grp_do_mlp_fu_4710.do_matmul_3_U0.cache_window_sm_i_U' written by process 'vit_block_top_vit_block_top.grp_dataflow_wrapper_fu_6443.task_compute_mlp_U0.grp_do_mlp_fu_4710.do_matmul_3_U0.matmul_step2_mac_3_U0'");
                                $fdisplay(fp, "Dependence_Channel_path vit_block_top_vit_block_top.grp_dataflow_wrapper_fu_6443.task_compute_mlp_U0.grp_do_mlp_fu_4710.do_matmul_3_U0.cache_window_sm_i_U");
                                $fdisplay(fp, "Dependence_Channel_status EMPTY");
                            end
                            else if (~grp_dataflow_wrapper_fu_6443.task_compute_mlp_U0.grp_do_mlp_fu_4710.do_matmul_3_U0.cache_window_sm_i_U.if_full_n) begin
                                $display("//      Blocked by full output FIFO 'vit_block_top_vit_block_top.grp_dataflow_wrapper_fu_6443.task_compute_mlp_U0.grp_do_mlp_fu_4710.do_matmul_3_U0.cache_window_sm_i_U' read by process 'vit_block_top_vit_block_top.grp_dataflow_wrapper_fu_6443.task_compute_mlp_U0.grp_do_mlp_fu_4710.do_matmul_3_U0.matmul_step2_mac_3_U0'");
                                $fdisplay(fp, "Dependence_Channel_path vit_block_top_vit_block_top.grp_dataflow_wrapper_fu_6443.task_compute_mlp_U0.grp_do_mlp_fu_4710.do_matmul_3_U0.cache_window_sm_i_U");
                                $fdisplay(fp, "Dependence_Channel_status FULL");
                            end
                        end
// for dep channel 'vit_block_top_vit_block_top.grp_dataflow_wrapper_fu_6443.task_compute_mlp_U0.grp_do_mlp_fu_4710.do_matmul_3_U0.start_for_matmul_step2_mac_3_U0_U' info is :
// blk sig is {{~vit_block_top_vit_block_top_inst.grp_dataflow_wrapper_fu_6443.task_compute_mlp_U0.grp_do_mlp_fu_4710.do_matmul_3_U0.start_for_matmul_step2_mac_3_U0_U.if_full_n & vit_block_top_vit_block_top_inst.grp_dataflow_wrapper_fu_6443.task_compute_mlp_U0.grp_do_mlp_fu_4710.do_matmul_3_U0.matmul_step1_cache_window_3_U0.ap_start & ~vit_block_top_vit_block_top_inst.grp_dataflow_wrapper_fu_6443.task_compute_mlp_U0.grp_do_mlp_fu_4710.do_matmul_3_U0.matmul_step1_cache_window_3_U0.real_start & (trans_in_cnt_35 == trans_out_cnt_35) & ~vit_block_top_vit_block_top_inst.grp_dataflow_wrapper_fu_6443.task_compute_mlp_U0.grp_do_mlp_fu_4710.do_matmul_3_U0.start_for_matmul_step2_mac_3_U0_U.if_read} start_FIFO}
                        if ((~grp_dataflow_wrapper_fu_6443.task_compute_mlp_U0.grp_do_mlp_fu_4710.do_matmul_3_U0.start_for_matmul_step2_mac_3_U0_U.if_full_n & grp_dataflow_wrapper_fu_6443.task_compute_mlp_U0.grp_do_mlp_fu_4710.do_matmul_3_U0.matmul_step1_cache_window_3_U0.ap_start & ~grp_dataflow_wrapper_fu_6443.task_compute_mlp_U0.grp_do_mlp_fu_4710.do_matmul_3_U0.matmul_step1_cache_window_3_U0.real_start & (trans_in_cnt_35 == trans_out_cnt_35) & ~grp_dataflow_wrapper_fu_6443.task_compute_mlp_U0.grp_do_mlp_fu_4710.do_matmul_3_U0.start_for_matmul_step2_mac_3_U0_U.if_read)) begin
                            $display("//      Blocked by full output start propagation FIFO 'vit_block_top_vit_block_top.grp_dataflow_wrapper_fu_6443.task_compute_mlp_U0.grp_do_mlp_fu_4710.do_matmul_3_U0.start_for_matmul_step2_mac_3_U0_U' read by process 'vit_block_top_vit_block_top.grp_dataflow_wrapper_fu_6443.task_compute_mlp_U0.grp_do_mlp_fu_4710.do_matmul_3_U0.matmul_step2_mac_3_U0',");
                        end
                    end
                    endcase
                end
                56 : begin // for proc 'vit_block_top_vit_block_top.grp_dataflow_wrapper_fu_6443.task_compute_mlp_U0.grp_do_mlp_fu_4710.do_matmul_3_U0.matmul_step2_mac_3_U0'
                    case(index2)
                    55: begin //  for dep proc 'vit_block_top_vit_block_top.grp_dataflow_wrapper_fu_6443.task_compute_mlp_U0.grp_do_mlp_fu_4710.do_matmul_3_U0.matmul_step1_cache_window_3_U0'
// for dep channel 'vit_block_top_vit_block_top.grp_dataflow_wrapper_fu_6443.task_compute_mlp_U0.grp_do_mlp_fu_4710.do_matmul_3_U0.cache_window_sm_i_U' info is :
// blk sig is {~vit_block_top_vit_block_top_inst.grp_dataflow_wrapper_fu_6443.task_compute_mlp_U0.grp_do_mlp_fu_4710.do_matmul_3_U0.matmul_step2_mac_3_U0.cache_window_sm_blk_n data_FIFO}
                        if ((~grp_dataflow_wrapper_fu_6443.task_compute_mlp_U0.grp_do_mlp_fu_4710.do_matmul_3_U0.matmul_step2_mac_3_U0.cache_window_sm_blk_n)) begin
                            if (~grp_dataflow_wrapper_fu_6443.task_compute_mlp_U0.grp_do_mlp_fu_4710.do_matmul_3_U0.cache_window_sm_i_U.if_empty_n) begin
                                $display("//      Blocked by empty input FIFO 'vit_block_top_vit_block_top.grp_dataflow_wrapper_fu_6443.task_compute_mlp_U0.grp_do_mlp_fu_4710.do_matmul_3_U0.cache_window_sm_i_U' written by process 'vit_block_top_vit_block_top.grp_dataflow_wrapper_fu_6443.task_compute_mlp_U0.grp_do_mlp_fu_4710.do_matmul_3_U0.matmul_step1_cache_window_3_U0'");
                                $fdisplay(fp, "Dependence_Channel_path vit_block_top_vit_block_top.grp_dataflow_wrapper_fu_6443.task_compute_mlp_U0.grp_do_mlp_fu_4710.do_matmul_3_U0.cache_window_sm_i_U");
                                $fdisplay(fp, "Dependence_Channel_status EMPTY");
                            end
                            else if (~grp_dataflow_wrapper_fu_6443.task_compute_mlp_U0.grp_do_mlp_fu_4710.do_matmul_3_U0.cache_window_sm_i_U.if_full_n) begin
                                $display("//      Blocked by full output FIFO 'vit_block_top_vit_block_top.grp_dataflow_wrapper_fu_6443.task_compute_mlp_U0.grp_do_mlp_fu_4710.do_matmul_3_U0.cache_window_sm_i_U' read by process 'vit_block_top_vit_block_top.grp_dataflow_wrapper_fu_6443.task_compute_mlp_U0.grp_do_mlp_fu_4710.do_matmul_3_U0.matmul_step1_cache_window_3_U0'");
                                $fdisplay(fp, "Dependence_Channel_path vit_block_top_vit_block_top.grp_dataflow_wrapper_fu_6443.task_compute_mlp_U0.grp_do_mlp_fu_4710.do_matmul_3_U0.cache_window_sm_i_U");
                                $fdisplay(fp, "Dependence_Channel_status FULL");
                            end
                        end
// for dep channel 'vit_block_top_vit_block_top.grp_dataflow_wrapper_fu_6443.task_compute_mlp_U0.grp_do_mlp_fu_4710.do_matmul_3_U0.start_for_matmul_step2_mac_3_U0_U' info is :
// blk sig is {{~vit_block_top_vit_block_top_inst.grp_dataflow_wrapper_fu_6443.task_compute_mlp_U0.grp_do_mlp_fu_4710.do_matmul_3_U0.start_for_matmul_step2_mac_3_U0_U.if_empty_n & vit_block_top_vit_block_top_inst.grp_dataflow_wrapper_fu_6443.task_compute_mlp_U0.grp_do_mlp_fu_4710.do_matmul_3_U0.matmul_step2_mac_3_U0.ap_idle & ~vit_block_top_vit_block_top_inst.grp_dataflow_wrapper_fu_6443.task_compute_mlp_U0.grp_do_mlp_fu_4710.do_matmul_3_U0.start_for_matmul_step2_mac_3_U0_U.if_write} start_FIFO}
                        if ((~grp_dataflow_wrapper_fu_6443.task_compute_mlp_U0.grp_do_mlp_fu_4710.do_matmul_3_U0.start_for_matmul_step2_mac_3_U0_U.if_empty_n & grp_dataflow_wrapper_fu_6443.task_compute_mlp_U0.grp_do_mlp_fu_4710.do_matmul_3_U0.matmul_step2_mac_3_U0.ap_idle & ~grp_dataflow_wrapper_fu_6443.task_compute_mlp_U0.grp_do_mlp_fu_4710.do_matmul_3_U0.start_for_matmul_step2_mac_3_U0_U.if_write)) begin
                            $display("//      Blocked by missing 'ap_start' from start propagation FIFO 'vit_block_top_vit_block_top.grp_dataflow_wrapper_fu_6443.task_compute_mlp_U0.grp_do_mlp_fu_4710.do_matmul_3_U0.start_for_matmul_step2_mac_3_U0_U' written by process 'vit_block_top_vit_block_top.grp_dataflow_wrapper_fu_6443.task_compute_mlp_U0.grp_do_mlp_fu_4710.do_matmul_3_U0.matmul_step1_cache_window_3_U0',");
                        end
                    end
                    57: begin //  for dep proc 'vit_block_top_vit_block_top.grp_dataflow_wrapper_fu_6443.task_compute_mlp_U0.grp_do_mlp_fu_4710.do_matmul_3_U0.do_adapt_12_U0'
// for dep channel 'vit_block_top_vit_block_top.grp_dataflow_wrapper_fu_6443.task_compute_mlp_U0.grp_do_mlp_fu_4710.do_matmul_3_U0.mac_sm_i_U' info is :
// blk sig is {~vit_block_top_vit_block_top_inst.grp_dataflow_wrapper_fu_6443.task_compute_mlp_U0.grp_do_mlp_fu_4710.do_matmul_3_U0.matmul_step2_mac_3_U0.mac_sm_blk_n data_FIFO}
                        if ((~grp_dataflow_wrapper_fu_6443.task_compute_mlp_U0.grp_do_mlp_fu_4710.do_matmul_3_U0.matmul_step2_mac_3_U0.mac_sm_blk_n)) begin
                            if (~grp_dataflow_wrapper_fu_6443.task_compute_mlp_U0.grp_do_mlp_fu_4710.do_matmul_3_U0.mac_sm_i_U.if_empty_n) begin
                                $display("//      Blocked by empty input FIFO 'vit_block_top_vit_block_top.grp_dataflow_wrapper_fu_6443.task_compute_mlp_U0.grp_do_mlp_fu_4710.do_matmul_3_U0.mac_sm_i_U' written by process 'vit_block_top_vit_block_top.grp_dataflow_wrapper_fu_6443.task_compute_mlp_U0.grp_do_mlp_fu_4710.do_matmul_3_U0.do_adapt_12_U0'");
                                $fdisplay(fp, "Dependence_Channel_path vit_block_top_vit_block_top.grp_dataflow_wrapper_fu_6443.task_compute_mlp_U0.grp_do_mlp_fu_4710.do_matmul_3_U0.mac_sm_i_U");
                                $fdisplay(fp, "Dependence_Channel_status EMPTY");
                            end
                            else if (~grp_dataflow_wrapper_fu_6443.task_compute_mlp_U0.grp_do_mlp_fu_4710.do_matmul_3_U0.mac_sm_i_U.if_full_n) begin
                                $display("//      Blocked by full output FIFO 'vit_block_top_vit_block_top.grp_dataflow_wrapper_fu_6443.task_compute_mlp_U0.grp_do_mlp_fu_4710.do_matmul_3_U0.mac_sm_i_U' read by process 'vit_block_top_vit_block_top.grp_dataflow_wrapper_fu_6443.task_compute_mlp_U0.grp_do_mlp_fu_4710.do_matmul_3_U0.do_adapt_12_U0'");
                                $fdisplay(fp, "Dependence_Channel_path vit_block_top_vit_block_top.grp_dataflow_wrapper_fu_6443.task_compute_mlp_U0.grp_do_mlp_fu_4710.do_matmul_3_U0.mac_sm_i_U");
                                $fdisplay(fp, "Dependence_Channel_status FULL");
                            end
                        end
// for dep channel 'vit_block_top_vit_block_top.grp_dataflow_wrapper_fu_6443.task_compute_mlp_U0.grp_do_mlp_fu_4710.do_matmul_3_U0.start_for_do_adapt_12_U0_U' info is :
// blk sig is {{~vit_block_top_vit_block_top_inst.grp_dataflow_wrapper_fu_6443.task_compute_mlp_U0.grp_do_mlp_fu_4710.do_matmul_3_U0.start_for_do_adapt_12_U0_U.if_full_n & vit_block_top_vit_block_top_inst.grp_dataflow_wrapper_fu_6443.task_compute_mlp_U0.grp_do_mlp_fu_4710.do_matmul_3_U0.matmul_step2_mac_3_U0.ap_start & ~vit_block_top_vit_block_top_inst.grp_dataflow_wrapper_fu_6443.task_compute_mlp_U0.grp_do_mlp_fu_4710.do_matmul_3_U0.matmul_step2_mac_3_U0.real_start & (trans_in_cnt_36 == trans_out_cnt_36) & ~vit_block_top_vit_block_top_inst.grp_dataflow_wrapper_fu_6443.task_compute_mlp_U0.grp_do_mlp_fu_4710.do_matmul_3_U0.start_for_do_adapt_12_U0_U.if_read} start_FIFO}
                        if ((~grp_dataflow_wrapper_fu_6443.task_compute_mlp_U0.grp_do_mlp_fu_4710.do_matmul_3_U0.start_for_do_adapt_12_U0_U.if_full_n & grp_dataflow_wrapper_fu_6443.task_compute_mlp_U0.grp_do_mlp_fu_4710.do_matmul_3_U0.matmul_step2_mac_3_U0.ap_start & ~grp_dataflow_wrapper_fu_6443.task_compute_mlp_U0.grp_do_mlp_fu_4710.do_matmul_3_U0.matmul_step2_mac_3_U0.real_start & (trans_in_cnt_36 == trans_out_cnt_36) & ~grp_dataflow_wrapper_fu_6443.task_compute_mlp_U0.grp_do_mlp_fu_4710.do_matmul_3_U0.start_for_do_adapt_12_U0_U.if_read)) begin
                            $display("//      Blocked by full output start propagation FIFO 'vit_block_top_vit_block_top.grp_dataflow_wrapper_fu_6443.task_compute_mlp_U0.grp_do_mlp_fu_4710.do_matmul_3_U0.start_for_do_adapt_12_U0_U' read by process 'vit_block_top_vit_block_top.grp_dataflow_wrapper_fu_6443.task_compute_mlp_U0.grp_do_mlp_fu_4710.do_matmul_3_U0.do_adapt_12_U0',");
                        end
                    end
                    endcase
                end
                57 : begin // for proc 'vit_block_top_vit_block_top.grp_dataflow_wrapper_fu_6443.task_compute_mlp_U0.grp_do_mlp_fu_4710.do_matmul_3_U0.do_adapt_12_U0'
                    case(index2)
                    56: begin //  for dep proc 'vit_block_top_vit_block_top.grp_dataflow_wrapper_fu_6443.task_compute_mlp_U0.grp_do_mlp_fu_4710.do_matmul_3_U0.matmul_step2_mac_3_U0'
// for dep channel 'vit_block_top_vit_block_top.grp_dataflow_wrapper_fu_6443.task_compute_mlp_U0.grp_do_mlp_fu_4710.do_matmul_3_U0.mac_sm_i_U' info is :
// blk sig is {~vit_block_top_vit_block_top_inst.grp_dataflow_wrapper_fu_6443.task_compute_mlp_U0.grp_do_mlp_fu_4710.do_matmul_3_U0.do_adapt_12_U0.mac_sm_blk_n data_FIFO}
                        if ((~grp_dataflow_wrapper_fu_6443.task_compute_mlp_U0.grp_do_mlp_fu_4710.do_matmul_3_U0.do_adapt_12_U0.mac_sm_blk_n)) begin
                            if (~grp_dataflow_wrapper_fu_6443.task_compute_mlp_U0.grp_do_mlp_fu_4710.do_matmul_3_U0.mac_sm_i_U.if_empty_n) begin
                                $display("//      Blocked by empty input FIFO 'vit_block_top_vit_block_top.grp_dataflow_wrapper_fu_6443.task_compute_mlp_U0.grp_do_mlp_fu_4710.do_matmul_3_U0.mac_sm_i_U' written by process 'vit_block_top_vit_block_top.grp_dataflow_wrapper_fu_6443.task_compute_mlp_U0.grp_do_mlp_fu_4710.do_matmul_3_U0.matmul_step2_mac_3_U0'");
                                $fdisplay(fp, "Dependence_Channel_path vit_block_top_vit_block_top.grp_dataflow_wrapper_fu_6443.task_compute_mlp_U0.grp_do_mlp_fu_4710.do_matmul_3_U0.mac_sm_i_U");
                                $fdisplay(fp, "Dependence_Channel_status EMPTY");
                            end
                            else if (~grp_dataflow_wrapper_fu_6443.task_compute_mlp_U0.grp_do_mlp_fu_4710.do_matmul_3_U0.mac_sm_i_U.if_full_n) begin
                                $display("//      Blocked by full output FIFO 'vit_block_top_vit_block_top.grp_dataflow_wrapper_fu_6443.task_compute_mlp_U0.grp_do_mlp_fu_4710.do_matmul_3_U0.mac_sm_i_U' read by process 'vit_block_top_vit_block_top.grp_dataflow_wrapper_fu_6443.task_compute_mlp_U0.grp_do_mlp_fu_4710.do_matmul_3_U0.matmul_step2_mac_3_U0'");
                                $fdisplay(fp, "Dependence_Channel_path vit_block_top_vit_block_top.grp_dataflow_wrapper_fu_6443.task_compute_mlp_U0.grp_do_mlp_fu_4710.do_matmul_3_U0.mac_sm_i_U");
                                $fdisplay(fp, "Dependence_Channel_status FULL");
                            end
                        end
// for dep channel 'vit_block_top_vit_block_top.grp_dataflow_wrapper_fu_6443.task_compute_mlp_U0.grp_do_mlp_fu_4710.do_matmul_3_U0.start_for_do_adapt_12_U0_U' info is :
// blk sig is {{~vit_block_top_vit_block_top_inst.grp_dataflow_wrapper_fu_6443.task_compute_mlp_U0.grp_do_mlp_fu_4710.do_matmul_3_U0.start_for_do_adapt_12_U0_U.if_empty_n & vit_block_top_vit_block_top_inst.grp_dataflow_wrapper_fu_6443.task_compute_mlp_U0.grp_do_mlp_fu_4710.do_matmul_3_U0.do_adapt_12_U0.ap_idle & ~vit_block_top_vit_block_top_inst.grp_dataflow_wrapper_fu_6443.task_compute_mlp_U0.grp_do_mlp_fu_4710.do_matmul_3_U0.start_for_do_adapt_12_U0_U.if_write} start_FIFO}
                        if ((~grp_dataflow_wrapper_fu_6443.task_compute_mlp_U0.grp_do_mlp_fu_4710.do_matmul_3_U0.start_for_do_adapt_12_U0_U.if_empty_n & grp_dataflow_wrapper_fu_6443.task_compute_mlp_U0.grp_do_mlp_fu_4710.do_matmul_3_U0.do_adapt_12_U0.ap_idle & ~grp_dataflow_wrapper_fu_6443.task_compute_mlp_U0.grp_do_mlp_fu_4710.do_matmul_3_U0.start_for_do_adapt_12_U0_U.if_write)) begin
                            $display("//      Blocked by missing 'ap_start' from start propagation FIFO 'vit_block_top_vit_block_top.grp_dataflow_wrapper_fu_6443.task_compute_mlp_U0.grp_do_mlp_fu_4710.do_matmul_3_U0.start_for_do_adapt_12_U0_U' written by process 'vit_block_top_vit_block_top.grp_dataflow_wrapper_fu_6443.task_compute_mlp_U0.grp_do_mlp_fu_4710.do_matmul_3_U0.matmul_step2_mac_3_U0',");
                        end
                    end
                    58: begin //  for dep proc 'vit_block_top_vit_block_top.grp_dataflow_wrapper_fu_6443.task_compute_mlp_U0.grp_do_mlp_fu_4710.do_gelu_U0'
// for dep channel 'vit_block_top_vit_block_top.grp_dataflow_wrapper_fu_6443.task_compute_mlp_U0.grp_do_mlp_fu_4710.m1_sm_i_U' info is :
// blk sig is {~vit_block_top_vit_block_top_inst.grp_dataflow_wrapper_fu_6443.task_compute_mlp_U0.grp_do_mlp_fu_4710.do_matmul_3_U0.do_adapt_12_U0.m1_sm_blk_n data_FIFO}
                        if ((~grp_dataflow_wrapper_fu_6443.task_compute_mlp_U0.grp_do_mlp_fu_4710.do_matmul_3_U0.do_adapt_12_U0.m1_sm_blk_n)) begin
                            if (~grp_dataflow_wrapper_fu_6443.task_compute_mlp_U0.grp_do_mlp_fu_4710.m1_sm_i_U.if_empty_n) begin
                                $display("//      Blocked by empty input FIFO 'vit_block_top_vit_block_top.grp_dataflow_wrapper_fu_6443.task_compute_mlp_U0.grp_do_mlp_fu_4710.m1_sm_i_U' written by process 'vit_block_top_vit_block_top.grp_dataflow_wrapper_fu_6443.task_compute_mlp_U0.grp_do_mlp_fu_4710.do_gelu_U0'");
                                $fdisplay(fp, "Dependence_Channel_path vit_block_top_vit_block_top.grp_dataflow_wrapper_fu_6443.task_compute_mlp_U0.grp_do_mlp_fu_4710.m1_sm_i_U");
                                $fdisplay(fp, "Dependence_Channel_status EMPTY");
                            end
                            else if (~grp_dataflow_wrapper_fu_6443.task_compute_mlp_U0.grp_do_mlp_fu_4710.m1_sm_i_U.if_full_n) begin
                                $display("//      Blocked by full output FIFO 'vit_block_top_vit_block_top.grp_dataflow_wrapper_fu_6443.task_compute_mlp_U0.grp_do_mlp_fu_4710.m1_sm_i_U' read by process 'vit_block_top_vit_block_top.grp_dataflow_wrapper_fu_6443.task_compute_mlp_U0.grp_do_mlp_fu_4710.do_gelu_U0'");
                                $fdisplay(fp, "Dependence_Channel_path vit_block_top_vit_block_top.grp_dataflow_wrapper_fu_6443.task_compute_mlp_U0.grp_do_mlp_fu_4710.m1_sm_i_U");
                                $fdisplay(fp, "Dependence_Channel_status FULL");
                            end
                        end
                    end
                    endcase
                end
                58 : begin // for proc 'vit_block_top_vit_block_top.grp_dataflow_wrapper_fu_6443.task_compute_mlp_U0.grp_do_mlp_fu_4710.do_gelu_U0'
                    case(index2)
                    53: begin //  for dep proc 'vit_block_top_vit_block_top.grp_dataflow_wrapper_fu_6443.task_compute_mlp_U0.grp_do_mlp_fu_4710.do_matmul_3_U0'
// for dep channel 'vit_block_top_vit_block_top.grp_dataflow_wrapper_fu_6443.task_compute_mlp_U0.grp_do_mlp_fu_4710.m1_sm_i_U' info is :
// blk sig is {~vit_block_top_vit_block_top_inst.grp_dataflow_wrapper_fu_6443.task_compute_mlp_U0.grp_do_mlp_fu_4710.do_gelu_U0.grp_do_gelu_Pipeline_TT_LOOP_CT_LOOP_fu_206.m1_sm_blk_n data_FIFO}
                        if ((~grp_dataflow_wrapper_fu_6443.task_compute_mlp_U0.grp_do_mlp_fu_4710.do_gelu_U0.grp_do_gelu_Pipeline_TT_LOOP_CT_LOOP_fu_206.m1_sm_blk_n)) begin
                            if (~grp_dataflow_wrapper_fu_6443.task_compute_mlp_U0.grp_do_mlp_fu_4710.m1_sm_i_U.if_empty_n) begin
                                $display("//      Blocked by empty input FIFO 'vit_block_top_vit_block_top.grp_dataflow_wrapper_fu_6443.task_compute_mlp_U0.grp_do_mlp_fu_4710.m1_sm_i_U' written by process 'vit_block_top_vit_block_top.grp_dataflow_wrapper_fu_6443.task_compute_mlp_U0.grp_do_mlp_fu_4710.do_matmul_3_U0'");
                                $fdisplay(fp, "Dependence_Channel_path vit_block_top_vit_block_top.grp_dataflow_wrapper_fu_6443.task_compute_mlp_U0.grp_do_mlp_fu_4710.m1_sm_i_U");
                                $fdisplay(fp, "Dependence_Channel_status EMPTY");
                            end
                            else if (~grp_dataflow_wrapper_fu_6443.task_compute_mlp_U0.grp_do_mlp_fu_4710.m1_sm_i_U.if_full_n) begin
                                $display("//      Blocked by full output FIFO 'vit_block_top_vit_block_top.grp_dataflow_wrapper_fu_6443.task_compute_mlp_U0.grp_do_mlp_fu_4710.m1_sm_i_U' read by process 'vit_block_top_vit_block_top.grp_dataflow_wrapper_fu_6443.task_compute_mlp_U0.grp_do_mlp_fu_4710.do_matmul_3_U0'");
                                $fdisplay(fp, "Dependence_Channel_path vit_block_top_vit_block_top.grp_dataflow_wrapper_fu_6443.task_compute_mlp_U0.grp_do_mlp_fu_4710.m1_sm_i_U");
                                $fdisplay(fp, "Dependence_Channel_status FULL");
                            end
                        end
// for dep channel 'vit_block_top_vit_block_top.grp_dataflow_wrapper_fu_6443.task_compute_mlp_U0.grp_do_mlp_fu_4710.start_for_do_gelu_U0_U' info is :
// blk sig is {{~vit_block_top_vit_block_top_inst.grp_dataflow_wrapper_fu_6443.task_compute_mlp_U0.grp_do_mlp_fu_4710.start_for_do_gelu_U0_U.if_empty_n & vit_block_top_vit_block_top_inst.grp_dataflow_wrapper_fu_6443.task_compute_mlp_U0.grp_do_mlp_fu_4710.do_gelu_U0.ap_idle & ~vit_block_top_vit_block_top_inst.grp_dataflow_wrapper_fu_6443.task_compute_mlp_U0.grp_do_mlp_fu_4710.start_for_do_gelu_U0_U.if_write} start_FIFO}
                        if ((~grp_dataflow_wrapper_fu_6443.task_compute_mlp_U0.grp_do_mlp_fu_4710.start_for_do_gelu_U0_U.if_empty_n & grp_dataflow_wrapper_fu_6443.task_compute_mlp_U0.grp_do_mlp_fu_4710.do_gelu_U0.ap_idle & ~grp_dataflow_wrapper_fu_6443.task_compute_mlp_U0.grp_do_mlp_fu_4710.start_for_do_gelu_U0_U.if_write)) begin
                            $display("//      Blocked by missing 'ap_start' from start propagation FIFO 'vit_block_top_vit_block_top.grp_dataflow_wrapper_fu_6443.task_compute_mlp_U0.grp_do_mlp_fu_4710.start_for_do_gelu_U0_U' written by process 'vit_block_top_vit_block_top.grp_dataflow_wrapper_fu_6443.task_compute_mlp_U0.grp_do_mlp_fu_4710.do_matmul_3_U0',");
                        end
                    end
                    57: begin //  for dep proc 'vit_block_top_vit_block_top.grp_dataflow_wrapper_fu_6443.task_compute_mlp_U0.grp_do_mlp_fu_4710.do_matmul_3_U0.do_adapt_12_U0'
// for dep channel 'vit_block_top_vit_block_top.grp_dataflow_wrapper_fu_6443.task_compute_mlp_U0.grp_do_mlp_fu_4710.m1_sm_i_U' info is :
// blk sig is {~vit_block_top_vit_block_top_inst.grp_dataflow_wrapper_fu_6443.task_compute_mlp_U0.grp_do_mlp_fu_4710.do_gelu_U0.grp_do_gelu_Pipeline_TT_LOOP_CT_LOOP_fu_206.m1_sm_blk_n data_FIFO}
                        if ((~grp_dataflow_wrapper_fu_6443.task_compute_mlp_U0.grp_do_mlp_fu_4710.do_gelu_U0.grp_do_gelu_Pipeline_TT_LOOP_CT_LOOP_fu_206.m1_sm_blk_n)) begin
                            if (~grp_dataflow_wrapper_fu_6443.task_compute_mlp_U0.grp_do_mlp_fu_4710.m1_sm_i_U.if_empty_n) begin
                                $display("//      Blocked by empty input FIFO 'vit_block_top_vit_block_top.grp_dataflow_wrapper_fu_6443.task_compute_mlp_U0.grp_do_mlp_fu_4710.m1_sm_i_U' written by process 'vit_block_top_vit_block_top.grp_dataflow_wrapper_fu_6443.task_compute_mlp_U0.grp_do_mlp_fu_4710.do_matmul_3_U0.do_adapt_12_U0'");
                                $fdisplay(fp, "Dependence_Channel_path vit_block_top_vit_block_top.grp_dataflow_wrapper_fu_6443.task_compute_mlp_U0.grp_do_mlp_fu_4710.m1_sm_i_U");
                                $fdisplay(fp, "Dependence_Channel_status EMPTY");
                            end
                            else if (~grp_dataflow_wrapper_fu_6443.task_compute_mlp_U0.grp_do_mlp_fu_4710.m1_sm_i_U.if_full_n) begin
                                $display("//      Blocked by full output FIFO 'vit_block_top_vit_block_top.grp_dataflow_wrapper_fu_6443.task_compute_mlp_U0.grp_do_mlp_fu_4710.m1_sm_i_U' read by process 'vit_block_top_vit_block_top.grp_dataflow_wrapper_fu_6443.task_compute_mlp_U0.grp_do_mlp_fu_4710.do_matmul_3_U0.do_adapt_12_U0'");
                                $fdisplay(fp, "Dependence_Channel_path vit_block_top_vit_block_top.grp_dataflow_wrapper_fu_6443.task_compute_mlp_U0.grp_do_mlp_fu_4710.m1_sm_i_U");
                                $fdisplay(fp, "Dependence_Channel_status FULL");
                            end
                        end
                    end
                    59: begin //  for dep proc 'vit_block_top_vit_block_top.grp_dataflow_wrapper_fu_6443.task_compute_mlp_U0.grp_do_mlp_fu_4710.do_matmul_U0'
// for dep channel 'vit_block_top_vit_block_top.grp_dataflow_wrapper_fu_6443.task_compute_mlp_U0.grp_do_mlp_fu_4710.ge_sm_i_U' info is :
// blk sig is {~vit_block_top_vit_block_top_inst.grp_dataflow_wrapper_fu_6443.task_compute_mlp_U0.grp_do_mlp_fu_4710.do_gelu_U0.grp_do_gelu_Pipeline_TT_LOOP_CT_LOOP_fu_206.ge_sm_blk_n data_FIFO}
                        if ((~grp_dataflow_wrapper_fu_6443.task_compute_mlp_U0.grp_do_mlp_fu_4710.do_gelu_U0.grp_do_gelu_Pipeline_TT_LOOP_CT_LOOP_fu_206.ge_sm_blk_n)) begin
                            if (~grp_dataflow_wrapper_fu_6443.task_compute_mlp_U0.grp_do_mlp_fu_4710.ge_sm_i_U.if_empty_n) begin
                                $display("//      Blocked by empty input FIFO 'vit_block_top_vit_block_top.grp_dataflow_wrapper_fu_6443.task_compute_mlp_U0.grp_do_mlp_fu_4710.ge_sm_i_U' written by process 'vit_block_top_vit_block_top.grp_dataflow_wrapper_fu_6443.task_compute_mlp_U0.grp_do_mlp_fu_4710.do_matmul_U0'");
                                $fdisplay(fp, "Dependence_Channel_path vit_block_top_vit_block_top.grp_dataflow_wrapper_fu_6443.task_compute_mlp_U0.grp_do_mlp_fu_4710.ge_sm_i_U");
                                $fdisplay(fp, "Dependence_Channel_status EMPTY");
                            end
                            else if (~grp_dataflow_wrapper_fu_6443.task_compute_mlp_U0.grp_do_mlp_fu_4710.ge_sm_i_U.if_full_n) begin
                                $display("//      Blocked by full output FIFO 'vit_block_top_vit_block_top.grp_dataflow_wrapper_fu_6443.task_compute_mlp_U0.grp_do_mlp_fu_4710.ge_sm_i_U' read by process 'vit_block_top_vit_block_top.grp_dataflow_wrapper_fu_6443.task_compute_mlp_U0.grp_do_mlp_fu_4710.do_matmul_U0'");
                                $fdisplay(fp, "Dependence_Channel_path vit_block_top_vit_block_top.grp_dataflow_wrapper_fu_6443.task_compute_mlp_U0.grp_do_mlp_fu_4710.ge_sm_i_U");
                                $fdisplay(fp, "Dependence_Channel_status FULL");
                            end
                        end
// for dep channel 'vit_block_top_vit_block_top.grp_dataflow_wrapper_fu_6443.task_compute_mlp_U0.grp_do_mlp_fu_4710.start_for_do_matmul_U0_U' info is :
// blk sig is {{~vit_block_top_vit_block_top_inst.grp_dataflow_wrapper_fu_6443.task_compute_mlp_U0.grp_do_mlp_fu_4710.start_for_do_matmul_U0_U.if_full_n & vit_block_top_vit_block_top_inst.grp_dataflow_wrapper_fu_6443.task_compute_mlp_U0.grp_do_mlp_fu_4710.do_gelu_U0.ap_start & ~vit_block_top_vit_block_top_inst.grp_dataflow_wrapper_fu_6443.task_compute_mlp_U0.grp_do_mlp_fu_4710.do_gelu_U0.real_start & (trans_in_cnt_38 == trans_out_cnt_38) & ~vit_block_top_vit_block_top_inst.grp_dataflow_wrapper_fu_6443.task_compute_mlp_U0.grp_do_mlp_fu_4710.start_for_do_matmul_U0_U.if_read} start_FIFO}
                        if ((~grp_dataflow_wrapper_fu_6443.task_compute_mlp_U0.grp_do_mlp_fu_4710.start_for_do_matmul_U0_U.if_full_n & grp_dataflow_wrapper_fu_6443.task_compute_mlp_U0.grp_do_mlp_fu_4710.do_gelu_U0.ap_start & ~grp_dataflow_wrapper_fu_6443.task_compute_mlp_U0.grp_do_mlp_fu_4710.do_gelu_U0.real_start & (trans_in_cnt_38 == trans_out_cnt_38) & ~grp_dataflow_wrapper_fu_6443.task_compute_mlp_U0.grp_do_mlp_fu_4710.start_for_do_matmul_U0_U.if_read)) begin
                            $display("//      Blocked by full output start propagation FIFO 'vit_block_top_vit_block_top.grp_dataflow_wrapper_fu_6443.task_compute_mlp_U0.grp_do_mlp_fu_4710.start_for_do_matmul_U0_U' read by process 'vit_block_top_vit_block_top.grp_dataflow_wrapper_fu_6443.task_compute_mlp_U0.grp_do_mlp_fu_4710.do_matmul_U0',");
                        end
                    end
                    60: begin //  for dep proc 'vit_block_top_vit_block_top.grp_dataflow_wrapper_fu_6443.task_compute_mlp_U0.grp_do_mlp_fu_4710.do_matmul_U0.do_adapt_U0'
// for dep channel 'vit_block_top_vit_block_top.grp_dataflow_wrapper_fu_6443.task_compute_mlp_U0.grp_do_mlp_fu_4710.ge_sm_i_U' info is :
// blk sig is {~vit_block_top_vit_block_top_inst.grp_dataflow_wrapper_fu_6443.task_compute_mlp_U0.grp_do_mlp_fu_4710.do_gelu_U0.grp_do_gelu_Pipeline_TT_LOOP_CT_LOOP_fu_206.ge_sm_blk_n data_FIFO}
                        if ((~grp_dataflow_wrapper_fu_6443.task_compute_mlp_U0.grp_do_mlp_fu_4710.do_gelu_U0.grp_do_gelu_Pipeline_TT_LOOP_CT_LOOP_fu_206.ge_sm_blk_n)) begin
                            if (~grp_dataflow_wrapper_fu_6443.task_compute_mlp_U0.grp_do_mlp_fu_4710.ge_sm_i_U.if_empty_n) begin
                                $display("//      Blocked by empty input FIFO 'vit_block_top_vit_block_top.grp_dataflow_wrapper_fu_6443.task_compute_mlp_U0.grp_do_mlp_fu_4710.ge_sm_i_U' written by process 'vit_block_top_vit_block_top.grp_dataflow_wrapper_fu_6443.task_compute_mlp_U0.grp_do_mlp_fu_4710.do_matmul_U0.do_adapt_U0'");
                                $fdisplay(fp, "Dependence_Channel_path vit_block_top_vit_block_top.grp_dataflow_wrapper_fu_6443.task_compute_mlp_U0.grp_do_mlp_fu_4710.ge_sm_i_U");
                                $fdisplay(fp, "Dependence_Channel_status EMPTY");
                            end
                            else if (~grp_dataflow_wrapper_fu_6443.task_compute_mlp_U0.grp_do_mlp_fu_4710.ge_sm_i_U.if_full_n) begin
                                $display("//      Blocked by full output FIFO 'vit_block_top_vit_block_top.grp_dataflow_wrapper_fu_6443.task_compute_mlp_U0.grp_do_mlp_fu_4710.ge_sm_i_U' read by process 'vit_block_top_vit_block_top.grp_dataflow_wrapper_fu_6443.task_compute_mlp_U0.grp_do_mlp_fu_4710.do_matmul_U0.do_adapt_U0'");
                                $fdisplay(fp, "Dependence_Channel_path vit_block_top_vit_block_top.grp_dataflow_wrapper_fu_6443.task_compute_mlp_U0.grp_do_mlp_fu_4710.ge_sm_i_U");
                                $fdisplay(fp, "Dependence_Channel_status FULL");
                            end
                        end
                    end
                    endcase
                end
                59 : begin // for proc 'vit_block_top_vit_block_top.grp_dataflow_wrapper_fu_6443.task_compute_mlp_U0.grp_do_mlp_fu_4710.do_matmul_U0'
                    case(index2)
                    58: begin //  for dep proc 'vit_block_top_vit_block_top.grp_dataflow_wrapper_fu_6443.task_compute_mlp_U0.grp_do_mlp_fu_4710.do_gelu_U0'
// for dep channel 'vit_block_top_vit_block_top.grp_dataflow_wrapper_fu_6443.task_compute_mlp_U0.grp_do_mlp_fu_4710.ge_sm_i_U' info is :
// blk sig is {~vit_block_top_vit_block_top_inst.grp_dataflow_wrapper_fu_6443.task_compute_mlp_U0.grp_do_mlp_fu_4710.do_matmul_U0.do_adapt_U0.ge_sm_blk_n data_FIFO}
                        if ((~grp_dataflow_wrapper_fu_6443.task_compute_mlp_U0.grp_do_mlp_fu_4710.do_matmul_U0.do_adapt_U0.ge_sm_blk_n)) begin
                            if (~grp_dataflow_wrapper_fu_6443.task_compute_mlp_U0.grp_do_mlp_fu_4710.ge_sm_i_U.if_empty_n) begin
                                $display("//      Blocked by empty input FIFO 'vit_block_top_vit_block_top.grp_dataflow_wrapper_fu_6443.task_compute_mlp_U0.grp_do_mlp_fu_4710.ge_sm_i_U' written by process 'vit_block_top_vit_block_top.grp_dataflow_wrapper_fu_6443.task_compute_mlp_U0.grp_do_mlp_fu_4710.do_gelu_U0'");
                                $fdisplay(fp, "Dependence_Channel_path vit_block_top_vit_block_top.grp_dataflow_wrapper_fu_6443.task_compute_mlp_U0.grp_do_mlp_fu_4710.ge_sm_i_U");
                                $fdisplay(fp, "Dependence_Channel_status EMPTY");
                            end
                            else if (~grp_dataflow_wrapper_fu_6443.task_compute_mlp_U0.grp_do_mlp_fu_4710.ge_sm_i_U.if_full_n) begin
                                $display("//      Blocked by full output FIFO 'vit_block_top_vit_block_top.grp_dataflow_wrapper_fu_6443.task_compute_mlp_U0.grp_do_mlp_fu_4710.ge_sm_i_U' read by process 'vit_block_top_vit_block_top.grp_dataflow_wrapper_fu_6443.task_compute_mlp_U0.grp_do_mlp_fu_4710.do_gelu_U0'");
                                $fdisplay(fp, "Dependence_Channel_path vit_block_top_vit_block_top.grp_dataflow_wrapper_fu_6443.task_compute_mlp_U0.grp_do_mlp_fu_4710.ge_sm_i_U");
                                $fdisplay(fp, "Dependence_Channel_status FULL");
                            end
                        end
// for dep channel 'vit_block_top_vit_block_top.grp_dataflow_wrapper_fu_6443.task_compute_mlp_U0.grp_do_mlp_fu_4710.start_for_do_matmul_U0_U' info is :
// blk sig is {{~vit_block_top_vit_block_top_inst.grp_dataflow_wrapper_fu_6443.task_compute_mlp_U0.grp_do_mlp_fu_4710.start_for_do_matmul_U0_U.if_empty_n & vit_block_top_vit_block_top_inst.grp_dataflow_wrapper_fu_6443.task_compute_mlp_U0.grp_do_mlp_fu_4710.do_matmul_U0.ap_idle & ~vit_block_top_vit_block_top_inst.grp_dataflow_wrapper_fu_6443.task_compute_mlp_U0.grp_do_mlp_fu_4710.start_for_do_matmul_U0_U.if_write} start_FIFO}
                        if ((~grp_dataflow_wrapper_fu_6443.task_compute_mlp_U0.grp_do_mlp_fu_4710.start_for_do_matmul_U0_U.if_empty_n & grp_dataflow_wrapper_fu_6443.task_compute_mlp_U0.grp_do_mlp_fu_4710.do_matmul_U0.ap_idle & ~grp_dataflow_wrapper_fu_6443.task_compute_mlp_U0.grp_do_mlp_fu_4710.start_for_do_matmul_U0_U.if_write)) begin
                            $display("//      Blocked by missing 'ap_start' from start propagation FIFO 'vit_block_top_vit_block_top.grp_dataflow_wrapper_fu_6443.task_compute_mlp_U0.grp_do_mlp_fu_4710.start_for_do_matmul_U0_U' written by process 'vit_block_top_vit_block_top.grp_dataflow_wrapper_fu_6443.task_compute_mlp_U0.grp_do_mlp_fu_4710.do_gelu_U0',");
                        end
                    end
                    64: begin //  for dep proc 'vit_block_top_vit_block_top.grp_dataflow_wrapper_fu_6443.task_compute_mlp_U0.grp_do_mlp_fu_4710.stream_merge_U0'
// for dep channel 'vit_block_top_vit_block_top.grp_dataflow_wrapper_fu_6443.task_compute_mlp_U0.grp_do_mlp_fu_4710.m2_sm_i_U' info is :
// blk sig is {~vit_block_top_vit_block_top_inst.grp_dataflow_wrapper_fu_6443.task_compute_mlp_U0.grp_do_mlp_fu_4710.do_matmul_U0.do_adapt_8_U0.m2_sm_blk_n data_FIFO}
                        if ((~grp_dataflow_wrapper_fu_6443.task_compute_mlp_U0.grp_do_mlp_fu_4710.do_matmul_U0.do_adapt_8_U0.m2_sm_blk_n)) begin
                            if (~grp_dataflow_wrapper_fu_6443.task_compute_mlp_U0.grp_do_mlp_fu_4710.m2_sm_i_U.if_empty_n) begin
                                $display("//      Blocked by empty input FIFO 'vit_block_top_vit_block_top.grp_dataflow_wrapper_fu_6443.task_compute_mlp_U0.grp_do_mlp_fu_4710.m2_sm_i_U' written by process 'vit_block_top_vit_block_top.grp_dataflow_wrapper_fu_6443.task_compute_mlp_U0.grp_do_mlp_fu_4710.stream_merge_U0'");
                                $fdisplay(fp, "Dependence_Channel_path vit_block_top_vit_block_top.grp_dataflow_wrapper_fu_6443.task_compute_mlp_U0.grp_do_mlp_fu_4710.m2_sm_i_U");
                                $fdisplay(fp, "Dependence_Channel_status EMPTY");
                            end
                            else if (~grp_dataflow_wrapper_fu_6443.task_compute_mlp_U0.grp_do_mlp_fu_4710.m2_sm_i_U.if_full_n) begin
                                $display("//      Blocked by full output FIFO 'vit_block_top_vit_block_top.grp_dataflow_wrapper_fu_6443.task_compute_mlp_U0.grp_do_mlp_fu_4710.m2_sm_i_U' read by process 'vit_block_top_vit_block_top.grp_dataflow_wrapper_fu_6443.task_compute_mlp_U0.grp_do_mlp_fu_4710.stream_merge_U0'");
                                $fdisplay(fp, "Dependence_Channel_path vit_block_top_vit_block_top.grp_dataflow_wrapper_fu_6443.task_compute_mlp_U0.grp_do_mlp_fu_4710.m2_sm_i_U");
                                $fdisplay(fp, "Dependence_Channel_status FULL");
                            end
                        end
                    end
                    endcase
                end
                60 : begin // for proc 'vit_block_top_vit_block_top.grp_dataflow_wrapper_fu_6443.task_compute_mlp_U0.grp_do_mlp_fu_4710.do_matmul_U0.do_adapt_U0'
                    case(index2)
                    58: begin //  for dep proc 'vit_block_top_vit_block_top.grp_dataflow_wrapper_fu_6443.task_compute_mlp_U0.grp_do_mlp_fu_4710.do_gelu_U0'
// for dep channel 'vit_block_top_vit_block_top.grp_dataflow_wrapper_fu_6443.task_compute_mlp_U0.grp_do_mlp_fu_4710.ge_sm_i_U' info is :
// blk sig is {~vit_block_top_vit_block_top_inst.grp_dataflow_wrapper_fu_6443.task_compute_mlp_U0.grp_do_mlp_fu_4710.do_matmul_U0.do_adapt_U0.ge_sm_blk_n data_FIFO}
                        if ((~grp_dataflow_wrapper_fu_6443.task_compute_mlp_U0.grp_do_mlp_fu_4710.do_matmul_U0.do_adapt_U0.ge_sm_blk_n)) begin
                            if (~grp_dataflow_wrapper_fu_6443.task_compute_mlp_U0.grp_do_mlp_fu_4710.ge_sm_i_U.if_empty_n) begin
                                $display("//      Blocked by empty input FIFO 'vit_block_top_vit_block_top.grp_dataflow_wrapper_fu_6443.task_compute_mlp_U0.grp_do_mlp_fu_4710.ge_sm_i_U' written by process 'vit_block_top_vit_block_top.grp_dataflow_wrapper_fu_6443.task_compute_mlp_U0.grp_do_mlp_fu_4710.do_gelu_U0'");
                                $fdisplay(fp, "Dependence_Channel_path vit_block_top_vit_block_top.grp_dataflow_wrapper_fu_6443.task_compute_mlp_U0.grp_do_mlp_fu_4710.ge_sm_i_U");
                                $fdisplay(fp, "Dependence_Channel_status EMPTY");
                            end
                            else if (~grp_dataflow_wrapper_fu_6443.task_compute_mlp_U0.grp_do_mlp_fu_4710.ge_sm_i_U.if_full_n) begin
                                $display("//      Blocked by full output FIFO 'vit_block_top_vit_block_top.grp_dataflow_wrapper_fu_6443.task_compute_mlp_U0.grp_do_mlp_fu_4710.ge_sm_i_U' read by process 'vit_block_top_vit_block_top.grp_dataflow_wrapper_fu_6443.task_compute_mlp_U0.grp_do_mlp_fu_4710.do_gelu_U0'");
                                $fdisplay(fp, "Dependence_Channel_path vit_block_top_vit_block_top.grp_dataflow_wrapper_fu_6443.task_compute_mlp_U0.grp_do_mlp_fu_4710.ge_sm_i_U");
                                $fdisplay(fp, "Dependence_Channel_status FULL");
                            end
                        end
                    end
                    61: begin //  for dep proc 'vit_block_top_vit_block_top.grp_dataflow_wrapper_fu_6443.task_compute_mlp_U0.grp_do_mlp_fu_4710.do_matmul_U0.matmul_step1_cache_window_U0'
// for dep channel 'vit_block_top_vit_block_top.grp_dataflow_wrapper_fu_6443.task_compute_mlp_U0.grp_do_mlp_fu_4710.do_matmul_U0.adpt_sm_i_U' info is :
// blk sig is {~vit_block_top_vit_block_top_inst.grp_dataflow_wrapper_fu_6443.task_compute_mlp_U0.grp_do_mlp_fu_4710.do_matmul_U0.do_adapt_U0.adpt_sm_blk_n data_FIFO}
                        if ((~grp_dataflow_wrapper_fu_6443.task_compute_mlp_U0.grp_do_mlp_fu_4710.do_matmul_U0.do_adapt_U0.adpt_sm_blk_n)) begin
                            if (~grp_dataflow_wrapper_fu_6443.task_compute_mlp_U0.grp_do_mlp_fu_4710.do_matmul_U0.adpt_sm_i_U.if_empty_n) begin
                                $display("//      Blocked by empty input FIFO 'vit_block_top_vit_block_top.grp_dataflow_wrapper_fu_6443.task_compute_mlp_U0.grp_do_mlp_fu_4710.do_matmul_U0.adpt_sm_i_U' written by process 'vit_block_top_vit_block_top.grp_dataflow_wrapper_fu_6443.task_compute_mlp_U0.grp_do_mlp_fu_4710.do_matmul_U0.matmul_step1_cache_window_U0'");
                                $fdisplay(fp, "Dependence_Channel_path vit_block_top_vit_block_top.grp_dataflow_wrapper_fu_6443.task_compute_mlp_U0.grp_do_mlp_fu_4710.do_matmul_U0.adpt_sm_i_U");
                                $fdisplay(fp, "Dependence_Channel_status EMPTY");
                            end
                            else if (~grp_dataflow_wrapper_fu_6443.task_compute_mlp_U0.grp_do_mlp_fu_4710.do_matmul_U0.adpt_sm_i_U.if_full_n) begin
                                $display("//      Blocked by full output FIFO 'vit_block_top_vit_block_top.grp_dataflow_wrapper_fu_6443.task_compute_mlp_U0.grp_do_mlp_fu_4710.do_matmul_U0.adpt_sm_i_U' read by process 'vit_block_top_vit_block_top.grp_dataflow_wrapper_fu_6443.task_compute_mlp_U0.grp_do_mlp_fu_4710.do_matmul_U0.matmul_step1_cache_window_U0'");
                                $fdisplay(fp, "Dependence_Channel_path vit_block_top_vit_block_top.grp_dataflow_wrapper_fu_6443.task_compute_mlp_U0.grp_do_mlp_fu_4710.do_matmul_U0.adpt_sm_i_U");
                                $fdisplay(fp, "Dependence_Channel_status FULL");
                            end
                        end
// for dep channel 'vit_block_top_vit_block_top.grp_dataflow_wrapper_fu_6443.task_compute_mlp_U0.grp_do_mlp_fu_4710.do_matmul_U0.start_for_matmul_step1_cache_window_U0_U' info is :
// blk sig is {{~vit_block_top_vit_block_top_inst.grp_dataflow_wrapper_fu_6443.task_compute_mlp_U0.grp_do_mlp_fu_4710.do_matmul_U0.start_for_matmul_step1_cache_window_U0_U.if_full_n & vit_block_top_vit_block_top_inst.grp_dataflow_wrapper_fu_6443.task_compute_mlp_U0.grp_do_mlp_fu_4710.do_matmul_U0.do_adapt_U0.ap_start & ~vit_block_top_vit_block_top_inst.grp_dataflow_wrapper_fu_6443.task_compute_mlp_U0.grp_do_mlp_fu_4710.do_matmul_U0.do_adapt_U0.real_start & (trans_in_cnt_39 == trans_out_cnt_39) & ~vit_block_top_vit_block_top_inst.grp_dataflow_wrapper_fu_6443.task_compute_mlp_U0.grp_do_mlp_fu_4710.do_matmul_U0.start_for_matmul_step1_cache_window_U0_U.if_read} start_FIFO}
                        if ((~grp_dataflow_wrapper_fu_6443.task_compute_mlp_U0.grp_do_mlp_fu_4710.do_matmul_U0.start_for_matmul_step1_cache_window_U0_U.if_full_n & grp_dataflow_wrapper_fu_6443.task_compute_mlp_U0.grp_do_mlp_fu_4710.do_matmul_U0.do_adapt_U0.ap_start & ~grp_dataflow_wrapper_fu_6443.task_compute_mlp_U0.grp_do_mlp_fu_4710.do_matmul_U0.do_adapt_U0.real_start & (trans_in_cnt_39 == trans_out_cnt_39) & ~grp_dataflow_wrapper_fu_6443.task_compute_mlp_U0.grp_do_mlp_fu_4710.do_matmul_U0.start_for_matmul_step1_cache_window_U0_U.if_read)) begin
                            $display("//      Blocked by full output start propagation FIFO 'vit_block_top_vit_block_top.grp_dataflow_wrapper_fu_6443.task_compute_mlp_U0.grp_do_mlp_fu_4710.do_matmul_U0.start_for_matmul_step1_cache_window_U0_U' read by process 'vit_block_top_vit_block_top.grp_dataflow_wrapper_fu_6443.task_compute_mlp_U0.grp_do_mlp_fu_4710.do_matmul_U0.matmul_step1_cache_window_U0',");
                        end
                    end
                    endcase
                end
                61 : begin // for proc 'vit_block_top_vit_block_top.grp_dataflow_wrapper_fu_6443.task_compute_mlp_U0.grp_do_mlp_fu_4710.do_matmul_U0.matmul_step1_cache_window_U0'
                    case(index2)
                    60: begin //  for dep proc 'vit_block_top_vit_block_top.grp_dataflow_wrapper_fu_6443.task_compute_mlp_U0.grp_do_mlp_fu_4710.do_matmul_U0.do_adapt_U0'
// for dep channel 'vit_block_top_vit_block_top.grp_dataflow_wrapper_fu_6443.task_compute_mlp_U0.grp_do_mlp_fu_4710.do_matmul_U0.adpt_sm_i_U' info is :
// blk sig is {~vit_block_top_vit_block_top_inst.grp_dataflow_wrapper_fu_6443.task_compute_mlp_U0.grp_do_mlp_fu_4710.do_matmul_U0.matmul_step1_cache_window_U0.adpt_sm_blk_n data_FIFO}
                        if ((~grp_dataflow_wrapper_fu_6443.task_compute_mlp_U0.grp_do_mlp_fu_4710.do_matmul_U0.matmul_step1_cache_window_U0.adpt_sm_blk_n)) begin
                            if (~grp_dataflow_wrapper_fu_6443.task_compute_mlp_U0.grp_do_mlp_fu_4710.do_matmul_U0.adpt_sm_i_U.if_empty_n) begin
                                $display("//      Blocked by empty input FIFO 'vit_block_top_vit_block_top.grp_dataflow_wrapper_fu_6443.task_compute_mlp_U0.grp_do_mlp_fu_4710.do_matmul_U0.adpt_sm_i_U' written by process 'vit_block_top_vit_block_top.grp_dataflow_wrapper_fu_6443.task_compute_mlp_U0.grp_do_mlp_fu_4710.do_matmul_U0.do_adapt_U0'");
                                $fdisplay(fp, "Dependence_Channel_path vit_block_top_vit_block_top.grp_dataflow_wrapper_fu_6443.task_compute_mlp_U0.grp_do_mlp_fu_4710.do_matmul_U0.adpt_sm_i_U");
                                $fdisplay(fp, "Dependence_Channel_status EMPTY");
                            end
                            else if (~grp_dataflow_wrapper_fu_6443.task_compute_mlp_U0.grp_do_mlp_fu_4710.do_matmul_U0.adpt_sm_i_U.if_full_n) begin
                                $display("//      Blocked by full output FIFO 'vit_block_top_vit_block_top.grp_dataflow_wrapper_fu_6443.task_compute_mlp_U0.grp_do_mlp_fu_4710.do_matmul_U0.adpt_sm_i_U' read by process 'vit_block_top_vit_block_top.grp_dataflow_wrapper_fu_6443.task_compute_mlp_U0.grp_do_mlp_fu_4710.do_matmul_U0.do_adapt_U0'");
                                $fdisplay(fp, "Dependence_Channel_path vit_block_top_vit_block_top.grp_dataflow_wrapper_fu_6443.task_compute_mlp_U0.grp_do_mlp_fu_4710.do_matmul_U0.adpt_sm_i_U");
                                $fdisplay(fp, "Dependence_Channel_status FULL");
                            end
                        end
// for dep channel 'vit_block_top_vit_block_top.grp_dataflow_wrapper_fu_6443.task_compute_mlp_U0.grp_do_mlp_fu_4710.do_matmul_U0.start_for_matmul_step1_cache_window_U0_U' info is :
// blk sig is {{~vit_block_top_vit_block_top_inst.grp_dataflow_wrapper_fu_6443.task_compute_mlp_U0.grp_do_mlp_fu_4710.do_matmul_U0.start_for_matmul_step1_cache_window_U0_U.if_empty_n & vit_block_top_vit_block_top_inst.grp_dataflow_wrapper_fu_6443.task_compute_mlp_U0.grp_do_mlp_fu_4710.do_matmul_U0.matmul_step1_cache_window_U0.ap_idle & ~vit_block_top_vit_block_top_inst.grp_dataflow_wrapper_fu_6443.task_compute_mlp_U0.grp_do_mlp_fu_4710.do_matmul_U0.start_for_matmul_step1_cache_window_U0_U.if_write} start_FIFO}
                        if ((~grp_dataflow_wrapper_fu_6443.task_compute_mlp_U0.grp_do_mlp_fu_4710.do_matmul_U0.start_for_matmul_step1_cache_window_U0_U.if_empty_n & grp_dataflow_wrapper_fu_6443.task_compute_mlp_U0.grp_do_mlp_fu_4710.do_matmul_U0.matmul_step1_cache_window_U0.ap_idle & ~grp_dataflow_wrapper_fu_6443.task_compute_mlp_U0.grp_do_mlp_fu_4710.do_matmul_U0.start_for_matmul_step1_cache_window_U0_U.if_write)) begin
                            $display("//      Blocked by missing 'ap_start' from start propagation FIFO 'vit_block_top_vit_block_top.grp_dataflow_wrapper_fu_6443.task_compute_mlp_U0.grp_do_mlp_fu_4710.do_matmul_U0.start_for_matmul_step1_cache_window_U0_U' written by process 'vit_block_top_vit_block_top.grp_dataflow_wrapper_fu_6443.task_compute_mlp_U0.grp_do_mlp_fu_4710.do_matmul_U0.do_adapt_U0',");
                        end
                    end
                    62: begin //  for dep proc 'vit_block_top_vit_block_top.grp_dataflow_wrapper_fu_6443.task_compute_mlp_U0.grp_do_mlp_fu_4710.do_matmul_U0.matmul_step2_mac_U0'
// for dep channel 'vit_block_top_vit_block_top.grp_dataflow_wrapper_fu_6443.task_compute_mlp_U0.grp_do_mlp_fu_4710.do_matmul_U0.cache_window_sm_i_U' info is :
// blk sig is {~vit_block_top_vit_block_top_inst.grp_dataflow_wrapper_fu_6443.task_compute_mlp_U0.grp_do_mlp_fu_4710.do_matmul_U0.matmul_step1_cache_window_U0.cache_window_sm_blk_n data_FIFO}
                        if ((~grp_dataflow_wrapper_fu_6443.task_compute_mlp_U0.grp_do_mlp_fu_4710.do_matmul_U0.matmul_step1_cache_window_U0.cache_window_sm_blk_n)) begin
                            if (~grp_dataflow_wrapper_fu_6443.task_compute_mlp_U0.grp_do_mlp_fu_4710.do_matmul_U0.cache_window_sm_i_U.if_empty_n) begin
                                $display("//      Blocked by empty input FIFO 'vit_block_top_vit_block_top.grp_dataflow_wrapper_fu_6443.task_compute_mlp_U0.grp_do_mlp_fu_4710.do_matmul_U0.cache_window_sm_i_U' written by process 'vit_block_top_vit_block_top.grp_dataflow_wrapper_fu_6443.task_compute_mlp_U0.grp_do_mlp_fu_4710.do_matmul_U0.matmul_step2_mac_U0'");
                                $fdisplay(fp, "Dependence_Channel_path vit_block_top_vit_block_top.grp_dataflow_wrapper_fu_6443.task_compute_mlp_U0.grp_do_mlp_fu_4710.do_matmul_U0.cache_window_sm_i_U");
                                $fdisplay(fp, "Dependence_Channel_status EMPTY");
                            end
                            else if (~grp_dataflow_wrapper_fu_6443.task_compute_mlp_U0.grp_do_mlp_fu_4710.do_matmul_U0.cache_window_sm_i_U.if_full_n) begin
                                $display("//      Blocked by full output FIFO 'vit_block_top_vit_block_top.grp_dataflow_wrapper_fu_6443.task_compute_mlp_U0.grp_do_mlp_fu_4710.do_matmul_U0.cache_window_sm_i_U' read by process 'vit_block_top_vit_block_top.grp_dataflow_wrapper_fu_6443.task_compute_mlp_U0.grp_do_mlp_fu_4710.do_matmul_U0.matmul_step2_mac_U0'");
                                $fdisplay(fp, "Dependence_Channel_path vit_block_top_vit_block_top.grp_dataflow_wrapper_fu_6443.task_compute_mlp_U0.grp_do_mlp_fu_4710.do_matmul_U0.cache_window_sm_i_U");
                                $fdisplay(fp, "Dependence_Channel_status FULL");
                            end
                        end
// for dep channel 'vit_block_top_vit_block_top.grp_dataflow_wrapper_fu_6443.task_compute_mlp_U0.grp_do_mlp_fu_4710.do_matmul_U0.start_for_matmul_step2_mac_U0_U' info is :
// blk sig is {{~vit_block_top_vit_block_top_inst.grp_dataflow_wrapper_fu_6443.task_compute_mlp_U0.grp_do_mlp_fu_4710.do_matmul_U0.start_for_matmul_step2_mac_U0_U.if_full_n & vit_block_top_vit_block_top_inst.grp_dataflow_wrapper_fu_6443.task_compute_mlp_U0.grp_do_mlp_fu_4710.do_matmul_U0.matmul_step1_cache_window_U0.ap_start & ~vit_block_top_vit_block_top_inst.grp_dataflow_wrapper_fu_6443.task_compute_mlp_U0.grp_do_mlp_fu_4710.do_matmul_U0.matmul_step1_cache_window_U0.real_start & (trans_in_cnt_40 == trans_out_cnt_40) & ~vit_block_top_vit_block_top_inst.grp_dataflow_wrapper_fu_6443.task_compute_mlp_U0.grp_do_mlp_fu_4710.do_matmul_U0.start_for_matmul_step2_mac_U0_U.if_read} start_FIFO}
                        if ((~grp_dataflow_wrapper_fu_6443.task_compute_mlp_U0.grp_do_mlp_fu_4710.do_matmul_U0.start_for_matmul_step2_mac_U0_U.if_full_n & grp_dataflow_wrapper_fu_6443.task_compute_mlp_U0.grp_do_mlp_fu_4710.do_matmul_U0.matmul_step1_cache_window_U0.ap_start & ~grp_dataflow_wrapper_fu_6443.task_compute_mlp_U0.grp_do_mlp_fu_4710.do_matmul_U0.matmul_step1_cache_window_U0.real_start & (trans_in_cnt_40 == trans_out_cnt_40) & ~grp_dataflow_wrapper_fu_6443.task_compute_mlp_U0.grp_do_mlp_fu_4710.do_matmul_U0.start_for_matmul_step2_mac_U0_U.if_read)) begin
                            $display("//      Blocked by full output start propagation FIFO 'vit_block_top_vit_block_top.grp_dataflow_wrapper_fu_6443.task_compute_mlp_U0.grp_do_mlp_fu_4710.do_matmul_U0.start_for_matmul_step2_mac_U0_U' read by process 'vit_block_top_vit_block_top.grp_dataflow_wrapper_fu_6443.task_compute_mlp_U0.grp_do_mlp_fu_4710.do_matmul_U0.matmul_step2_mac_U0',");
                        end
                    end
                    endcase
                end
                62 : begin // for proc 'vit_block_top_vit_block_top.grp_dataflow_wrapper_fu_6443.task_compute_mlp_U0.grp_do_mlp_fu_4710.do_matmul_U0.matmul_step2_mac_U0'
                    case(index2)
                    61: begin //  for dep proc 'vit_block_top_vit_block_top.grp_dataflow_wrapper_fu_6443.task_compute_mlp_U0.grp_do_mlp_fu_4710.do_matmul_U0.matmul_step1_cache_window_U0'
// for dep channel 'vit_block_top_vit_block_top.grp_dataflow_wrapper_fu_6443.task_compute_mlp_U0.grp_do_mlp_fu_4710.do_matmul_U0.cache_window_sm_i_U' info is :
// blk sig is {~vit_block_top_vit_block_top_inst.grp_dataflow_wrapper_fu_6443.task_compute_mlp_U0.grp_do_mlp_fu_4710.do_matmul_U0.matmul_step2_mac_U0.cache_window_sm_blk_n data_FIFO}
                        if ((~grp_dataflow_wrapper_fu_6443.task_compute_mlp_U0.grp_do_mlp_fu_4710.do_matmul_U0.matmul_step2_mac_U0.cache_window_sm_blk_n)) begin
                            if (~grp_dataflow_wrapper_fu_6443.task_compute_mlp_U0.grp_do_mlp_fu_4710.do_matmul_U0.cache_window_sm_i_U.if_empty_n) begin
                                $display("//      Blocked by empty input FIFO 'vit_block_top_vit_block_top.grp_dataflow_wrapper_fu_6443.task_compute_mlp_U0.grp_do_mlp_fu_4710.do_matmul_U0.cache_window_sm_i_U' written by process 'vit_block_top_vit_block_top.grp_dataflow_wrapper_fu_6443.task_compute_mlp_U0.grp_do_mlp_fu_4710.do_matmul_U0.matmul_step1_cache_window_U0'");
                                $fdisplay(fp, "Dependence_Channel_path vit_block_top_vit_block_top.grp_dataflow_wrapper_fu_6443.task_compute_mlp_U0.grp_do_mlp_fu_4710.do_matmul_U0.cache_window_sm_i_U");
                                $fdisplay(fp, "Dependence_Channel_status EMPTY");
                            end
                            else if (~grp_dataflow_wrapper_fu_6443.task_compute_mlp_U0.grp_do_mlp_fu_4710.do_matmul_U0.cache_window_sm_i_U.if_full_n) begin
                                $display("//      Blocked by full output FIFO 'vit_block_top_vit_block_top.grp_dataflow_wrapper_fu_6443.task_compute_mlp_U0.grp_do_mlp_fu_4710.do_matmul_U0.cache_window_sm_i_U' read by process 'vit_block_top_vit_block_top.grp_dataflow_wrapper_fu_6443.task_compute_mlp_U0.grp_do_mlp_fu_4710.do_matmul_U0.matmul_step1_cache_window_U0'");
                                $fdisplay(fp, "Dependence_Channel_path vit_block_top_vit_block_top.grp_dataflow_wrapper_fu_6443.task_compute_mlp_U0.grp_do_mlp_fu_4710.do_matmul_U0.cache_window_sm_i_U");
                                $fdisplay(fp, "Dependence_Channel_status FULL");
                            end
                        end
// for dep channel 'vit_block_top_vit_block_top.grp_dataflow_wrapper_fu_6443.task_compute_mlp_U0.grp_do_mlp_fu_4710.do_matmul_U0.start_for_matmul_step2_mac_U0_U' info is :
// blk sig is {{~vit_block_top_vit_block_top_inst.grp_dataflow_wrapper_fu_6443.task_compute_mlp_U0.grp_do_mlp_fu_4710.do_matmul_U0.start_for_matmul_step2_mac_U0_U.if_empty_n & vit_block_top_vit_block_top_inst.grp_dataflow_wrapper_fu_6443.task_compute_mlp_U0.grp_do_mlp_fu_4710.do_matmul_U0.matmul_step2_mac_U0.ap_idle & ~vit_block_top_vit_block_top_inst.grp_dataflow_wrapper_fu_6443.task_compute_mlp_U0.grp_do_mlp_fu_4710.do_matmul_U0.start_for_matmul_step2_mac_U0_U.if_write} start_FIFO}
                        if ((~grp_dataflow_wrapper_fu_6443.task_compute_mlp_U0.grp_do_mlp_fu_4710.do_matmul_U0.start_for_matmul_step2_mac_U0_U.if_empty_n & grp_dataflow_wrapper_fu_6443.task_compute_mlp_U0.grp_do_mlp_fu_4710.do_matmul_U0.matmul_step2_mac_U0.ap_idle & ~grp_dataflow_wrapper_fu_6443.task_compute_mlp_U0.grp_do_mlp_fu_4710.do_matmul_U0.start_for_matmul_step2_mac_U0_U.if_write)) begin
                            $display("//      Blocked by missing 'ap_start' from start propagation FIFO 'vit_block_top_vit_block_top.grp_dataflow_wrapper_fu_6443.task_compute_mlp_U0.grp_do_mlp_fu_4710.do_matmul_U0.start_for_matmul_step2_mac_U0_U' written by process 'vit_block_top_vit_block_top.grp_dataflow_wrapper_fu_6443.task_compute_mlp_U0.grp_do_mlp_fu_4710.do_matmul_U0.matmul_step1_cache_window_U0',");
                        end
                    end
                    63: begin //  for dep proc 'vit_block_top_vit_block_top.grp_dataflow_wrapper_fu_6443.task_compute_mlp_U0.grp_do_mlp_fu_4710.do_matmul_U0.do_adapt_8_U0'
// for dep channel 'vit_block_top_vit_block_top.grp_dataflow_wrapper_fu_6443.task_compute_mlp_U0.grp_do_mlp_fu_4710.do_matmul_U0.mac_sm_i_U' info is :
// blk sig is {~vit_block_top_vit_block_top_inst.grp_dataflow_wrapper_fu_6443.task_compute_mlp_U0.grp_do_mlp_fu_4710.do_matmul_U0.matmul_step2_mac_U0.mac_sm_blk_n data_FIFO}
                        if ((~grp_dataflow_wrapper_fu_6443.task_compute_mlp_U0.grp_do_mlp_fu_4710.do_matmul_U0.matmul_step2_mac_U0.mac_sm_blk_n)) begin
                            if (~grp_dataflow_wrapper_fu_6443.task_compute_mlp_U0.grp_do_mlp_fu_4710.do_matmul_U0.mac_sm_i_U.if_empty_n) begin
                                $display("//      Blocked by empty input FIFO 'vit_block_top_vit_block_top.grp_dataflow_wrapper_fu_6443.task_compute_mlp_U0.grp_do_mlp_fu_4710.do_matmul_U0.mac_sm_i_U' written by process 'vit_block_top_vit_block_top.grp_dataflow_wrapper_fu_6443.task_compute_mlp_U0.grp_do_mlp_fu_4710.do_matmul_U0.do_adapt_8_U0'");
                                $fdisplay(fp, "Dependence_Channel_path vit_block_top_vit_block_top.grp_dataflow_wrapper_fu_6443.task_compute_mlp_U0.grp_do_mlp_fu_4710.do_matmul_U0.mac_sm_i_U");
                                $fdisplay(fp, "Dependence_Channel_status EMPTY");
                            end
                            else if (~grp_dataflow_wrapper_fu_6443.task_compute_mlp_U0.grp_do_mlp_fu_4710.do_matmul_U0.mac_sm_i_U.if_full_n) begin
                                $display("//      Blocked by full output FIFO 'vit_block_top_vit_block_top.grp_dataflow_wrapper_fu_6443.task_compute_mlp_U0.grp_do_mlp_fu_4710.do_matmul_U0.mac_sm_i_U' read by process 'vit_block_top_vit_block_top.grp_dataflow_wrapper_fu_6443.task_compute_mlp_U0.grp_do_mlp_fu_4710.do_matmul_U0.do_adapt_8_U0'");
                                $fdisplay(fp, "Dependence_Channel_path vit_block_top_vit_block_top.grp_dataflow_wrapper_fu_6443.task_compute_mlp_U0.grp_do_mlp_fu_4710.do_matmul_U0.mac_sm_i_U");
                                $fdisplay(fp, "Dependence_Channel_status FULL");
                            end
                        end
// for dep channel 'vit_block_top_vit_block_top.grp_dataflow_wrapper_fu_6443.task_compute_mlp_U0.grp_do_mlp_fu_4710.do_matmul_U0.start_for_do_adapt_8_U0_U' info is :
// blk sig is {{~vit_block_top_vit_block_top_inst.grp_dataflow_wrapper_fu_6443.task_compute_mlp_U0.grp_do_mlp_fu_4710.do_matmul_U0.start_for_do_adapt_8_U0_U.if_full_n & vit_block_top_vit_block_top_inst.grp_dataflow_wrapper_fu_6443.task_compute_mlp_U0.grp_do_mlp_fu_4710.do_matmul_U0.matmul_step2_mac_U0.ap_start & ~vit_block_top_vit_block_top_inst.grp_dataflow_wrapper_fu_6443.task_compute_mlp_U0.grp_do_mlp_fu_4710.do_matmul_U0.matmul_step2_mac_U0.real_start & (trans_in_cnt_41 == trans_out_cnt_41) & ~vit_block_top_vit_block_top_inst.grp_dataflow_wrapper_fu_6443.task_compute_mlp_U0.grp_do_mlp_fu_4710.do_matmul_U0.start_for_do_adapt_8_U0_U.if_read} start_FIFO}
                        if ((~grp_dataflow_wrapper_fu_6443.task_compute_mlp_U0.grp_do_mlp_fu_4710.do_matmul_U0.start_for_do_adapt_8_U0_U.if_full_n & grp_dataflow_wrapper_fu_6443.task_compute_mlp_U0.grp_do_mlp_fu_4710.do_matmul_U0.matmul_step2_mac_U0.ap_start & ~grp_dataflow_wrapper_fu_6443.task_compute_mlp_U0.grp_do_mlp_fu_4710.do_matmul_U0.matmul_step2_mac_U0.real_start & (trans_in_cnt_41 == trans_out_cnt_41) & ~grp_dataflow_wrapper_fu_6443.task_compute_mlp_U0.grp_do_mlp_fu_4710.do_matmul_U0.start_for_do_adapt_8_U0_U.if_read)) begin
                            $display("//      Blocked by full output start propagation FIFO 'vit_block_top_vit_block_top.grp_dataflow_wrapper_fu_6443.task_compute_mlp_U0.grp_do_mlp_fu_4710.do_matmul_U0.start_for_do_adapt_8_U0_U' read by process 'vit_block_top_vit_block_top.grp_dataflow_wrapper_fu_6443.task_compute_mlp_U0.grp_do_mlp_fu_4710.do_matmul_U0.do_adapt_8_U0',");
                        end
                    end
                    endcase
                end
                63 : begin // for proc 'vit_block_top_vit_block_top.grp_dataflow_wrapper_fu_6443.task_compute_mlp_U0.grp_do_mlp_fu_4710.do_matmul_U0.do_adapt_8_U0'
                    case(index2)
                    62: begin //  for dep proc 'vit_block_top_vit_block_top.grp_dataflow_wrapper_fu_6443.task_compute_mlp_U0.grp_do_mlp_fu_4710.do_matmul_U0.matmul_step2_mac_U0'
// for dep channel 'vit_block_top_vit_block_top.grp_dataflow_wrapper_fu_6443.task_compute_mlp_U0.grp_do_mlp_fu_4710.do_matmul_U0.mac_sm_i_U' info is :
// blk sig is {~vit_block_top_vit_block_top_inst.grp_dataflow_wrapper_fu_6443.task_compute_mlp_U0.grp_do_mlp_fu_4710.do_matmul_U0.do_adapt_8_U0.mac_sm_blk_n data_FIFO}
                        if ((~grp_dataflow_wrapper_fu_6443.task_compute_mlp_U0.grp_do_mlp_fu_4710.do_matmul_U0.do_adapt_8_U0.mac_sm_blk_n)) begin
                            if (~grp_dataflow_wrapper_fu_6443.task_compute_mlp_U0.grp_do_mlp_fu_4710.do_matmul_U0.mac_sm_i_U.if_empty_n) begin
                                $display("//      Blocked by empty input FIFO 'vit_block_top_vit_block_top.grp_dataflow_wrapper_fu_6443.task_compute_mlp_U0.grp_do_mlp_fu_4710.do_matmul_U0.mac_sm_i_U' written by process 'vit_block_top_vit_block_top.grp_dataflow_wrapper_fu_6443.task_compute_mlp_U0.grp_do_mlp_fu_4710.do_matmul_U0.matmul_step2_mac_U0'");
                                $fdisplay(fp, "Dependence_Channel_path vit_block_top_vit_block_top.grp_dataflow_wrapper_fu_6443.task_compute_mlp_U0.grp_do_mlp_fu_4710.do_matmul_U0.mac_sm_i_U");
                                $fdisplay(fp, "Dependence_Channel_status EMPTY");
                            end
                            else if (~grp_dataflow_wrapper_fu_6443.task_compute_mlp_U0.grp_do_mlp_fu_4710.do_matmul_U0.mac_sm_i_U.if_full_n) begin
                                $display("//      Blocked by full output FIFO 'vit_block_top_vit_block_top.grp_dataflow_wrapper_fu_6443.task_compute_mlp_U0.grp_do_mlp_fu_4710.do_matmul_U0.mac_sm_i_U' read by process 'vit_block_top_vit_block_top.grp_dataflow_wrapper_fu_6443.task_compute_mlp_U0.grp_do_mlp_fu_4710.do_matmul_U0.matmul_step2_mac_U0'");
                                $fdisplay(fp, "Dependence_Channel_path vit_block_top_vit_block_top.grp_dataflow_wrapper_fu_6443.task_compute_mlp_U0.grp_do_mlp_fu_4710.do_matmul_U0.mac_sm_i_U");
                                $fdisplay(fp, "Dependence_Channel_status FULL");
                            end
                        end
// for dep channel 'vit_block_top_vit_block_top.grp_dataflow_wrapper_fu_6443.task_compute_mlp_U0.grp_do_mlp_fu_4710.do_matmul_U0.start_for_do_adapt_8_U0_U' info is :
// blk sig is {{~vit_block_top_vit_block_top_inst.grp_dataflow_wrapper_fu_6443.task_compute_mlp_U0.grp_do_mlp_fu_4710.do_matmul_U0.start_for_do_adapt_8_U0_U.if_empty_n & vit_block_top_vit_block_top_inst.grp_dataflow_wrapper_fu_6443.task_compute_mlp_U0.grp_do_mlp_fu_4710.do_matmul_U0.do_adapt_8_U0.ap_idle & ~vit_block_top_vit_block_top_inst.grp_dataflow_wrapper_fu_6443.task_compute_mlp_U0.grp_do_mlp_fu_4710.do_matmul_U0.start_for_do_adapt_8_U0_U.if_write} start_FIFO}
                        if ((~grp_dataflow_wrapper_fu_6443.task_compute_mlp_U0.grp_do_mlp_fu_4710.do_matmul_U0.start_for_do_adapt_8_U0_U.if_empty_n & grp_dataflow_wrapper_fu_6443.task_compute_mlp_U0.grp_do_mlp_fu_4710.do_matmul_U0.do_adapt_8_U0.ap_idle & ~grp_dataflow_wrapper_fu_6443.task_compute_mlp_U0.grp_do_mlp_fu_4710.do_matmul_U0.start_for_do_adapt_8_U0_U.if_write)) begin
                            $display("//      Blocked by missing 'ap_start' from start propagation FIFO 'vit_block_top_vit_block_top.grp_dataflow_wrapper_fu_6443.task_compute_mlp_U0.grp_do_mlp_fu_4710.do_matmul_U0.start_for_do_adapt_8_U0_U' written by process 'vit_block_top_vit_block_top.grp_dataflow_wrapper_fu_6443.task_compute_mlp_U0.grp_do_mlp_fu_4710.do_matmul_U0.matmul_step2_mac_U0',");
                        end
                    end
                    64: begin //  for dep proc 'vit_block_top_vit_block_top.grp_dataflow_wrapper_fu_6443.task_compute_mlp_U0.grp_do_mlp_fu_4710.stream_merge_U0'
// for dep channel 'vit_block_top_vit_block_top.grp_dataflow_wrapper_fu_6443.task_compute_mlp_U0.grp_do_mlp_fu_4710.m2_sm_i_U' info is :
// blk sig is {~vit_block_top_vit_block_top_inst.grp_dataflow_wrapper_fu_6443.task_compute_mlp_U0.grp_do_mlp_fu_4710.do_matmul_U0.do_adapt_8_U0.m2_sm_blk_n data_FIFO}
                        if ((~grp_dataflow_wrapper_fu_6443.task_compute_mlp_U0.grp_do_mlp_fu_4710.do_matmul_U0.do_adapt_8_U0.m2_sm_blk_n)) begin
                            if (~grp_dataflow_wrapper_fu_6443.task_compute_mlp_U0.grp_do_mlp_fu_4710.m2_sm_i_U.if_empty_n) begin
                                $display("//      Blocked by empty input FIFO 'vit_block_top_vit_block_top.grp_dataflow_wrapper_fu_6443.task_compute_mlp_U0.grp_do_mlp_fu_4710.m2_sm_i_U' written by process 'vit_block_top_vit_block_top.grp_dataflow_wrapper_fu_6443.task_compute_mlp_U0.grp_do_mlp_fu_4710.stream_merge_U0'");
                                $fdisplay(fp, "Dependence_Channel_path vit_block_top_vit_block_top.grp_dataflow_wrapper_fu_6443.task_compute_mlp_U0.grp_do_mlp_fu_4710.m2_sm_i_U");
                                $fdisplay(fp, "Dependence_Channel_status EMPTY");
                            end
                            else if (~grp_dataflow_wrapper_fu_6443.task_compute_mlp_U0.grp_do_mlp_fu_4710.m2_sm_i_U.if_full_n) begin
                                $display("//      Blocked by full output FIFO 'vit_block_top_vit_block_top.grp_dataflow_wrapper_fu_6443.task_compute_mlp_U0.grp_do_mlp_fu_4710.m2_sm_i_U' read by process 'vit_block_top_vit_block_top.grp_dataflow_wrapper_fu_6443.task_compute_mlp_U0.grp_do_mlp_fu_4710.stream_merge_U0'");
                                $fdisplay(fp, "Dependence_Channel_path vit_block_top_vit_block_top.grp_dataflow_wrapper_fu_6443.task_compute_mlp_U0.grp_do_mlp_fu_4710.m2_sm_i_U");
                                $fdisplay(fp, "Dependence_Channel_status FULL");
                            end
                        end
                    end
                    endcase
                end
                64 : begin // for proc 'vit_block_top_vit_block_top.grp_dataflow_wrapper_fu_6443.task_compute_mlp_U0.grp_do_mlp_fu_4710.stream_merge_U0'
                    case(index2)
                    51: begin //  for dep proc 'vit_block_top_vit_block_top.grp_dataflow_wrapper_fu_6443.task_compute_mlp_U0.grp_do_mlp_fu_4710.do_adapt_5_U0'
// for dep channel 'vit_block_top_vit_block_top.grp_dataflow_wrapper_fu_6443.task_compute_mlp_U0.grp_do_mlp_fu_4710.resi_o_sm_i_U' info is :
// blk sig is {~vit_block_top_vit_block_top_inst.grp_dataflow_wrapper_fu_6443.task_compute_mlp_U0.grp_do_mlp_fu_4710.stream_merge_U0.grp_stream_merge_Pipeline_VITIS_LOOP_393_1_VITIS_LOOP_394_2_fu_34.resi_o_sm_blk_n data_FIFO}
                        if ((~grp_dataflow_wrapper_fu_6443.task_compute_mlp_U0.grp_do_mlp_fu_4710.stream_merge_U0.grp_stream_merge_Pipeline_VITIS_LOOP_393_1_VITIS_LOOP_394_2_fu_34.resi_o_sm_blk_n)) begin
                            if (~grp_dataflow_wrapper_fu_6443.task_compute_mlp_U0.grp_do_mlp_fu_4710.resi_o_sm_i_U.if_empty_n) begin
                                $display("//      Blocked by empty input FIFO 'vit_block_top_vit_block_top.grp_dataflow_wrapper_fu_6443.task_compute_mlp_U0.grp_do_mlp_fu_4710.resi_o_sm_i_U' written by process 'vit_block_top_vit_block_top.grp_dataflow_wrapper_fu_6443.task_compute_mlp_U0.grp_do_mlp_fu_4710.do_adapt_5_U0'");
                                $fdisplay(fp, "Dependence_Channel_path vit_block_top_vit_block_top.grp_dataflow_wrapper_fu_6443.task_compute_mlp_U0.grp_do_mlp_fu_4710.resi_o_sm_i_U");
                                $fdisplay(fp, "Dependence_Channel_status EMPTY");
                            end
                            else if (~grp_dataflow_wrapper_fu_6443.task_compute_mlp_U0.grp_do_mlp_fu_4710.resi_o_sm_i_U.if_full_n) begin
                                $display("//      Blocked by full output FIFO 'vit_block_top_vit_block_top.grp_dataflow_wrapper_fu_6443.task_compute_mlp_U0.grp_do_mlp_fu_4710.resi_o_sm_i_U' read by process 'vit_block_top_vit_block_top.grp_dataflow_wrapper_fu_6443.task_compute_mlp_U0.grp_do_mlp_fu_4710.do_adapt_5_U0'");
                                $fdisplay(fp, "Dependence_Channel_path vit_block_top_vit_block_top.grp_dataflow_wrapper_fu_6443.task_compute_mlp_U0.grp_do_mlp_fu_4710.resi_o_sm_i_U");
                                $fdisplay(fp, "Dependence_Channel_status FULL");
                            end
                        end
// for dep channel 'vit_block_top_vit_block_top.grp_dataflow_wrapper_fu_6443.task_compute_mlp_U0.grp_do_mlp_fu_4710.start_for_stream_merge_U0_U' info is :
// blk sig is {{~vit_block_top_vit_block_top_inst.grp_dataflow_wrapper_fu_6443.task_compute_mlp_U0.grp_do_mlp_fu_4710.start_for_stream_merge_U0_U.if_empty_n & vit_block_top_vit_block_top_inst.grp_dataflow_wrapper_fu_6443.task_compute_mlp_U0.grp_do_mlp_fu_4710.stream_merge_U0.ap_idle & ~vit_block_top_vit_block_top_inst.grp_dataflow_wrapper_fu_6443.task_compute_mlp_U0.grp_do_mlp_fu_4710.start_for_stream_merge_U0_U.if_write} start_FIFO}
                        if ((~grp_dataflow_wrapper_fu_6443.task_compute_mlp_U0.grp_do_mlp_fu_4710.start_for_stream_merge_U0_U.if_empty_n & grp_dataflow_wrapper_fu_6443.task_compute_mlp_U0.grp_do_mlp_fu_4710.stream_merge_U0.ap_idle & ~grp_dataflow_wrapper_fu_6443.task_compute_mlp_U0.grp_do_mlp_fu_4710.start_for_stream_merge_U0_U.if_write)) begin
                            $display("//      Blocked by missing 'ap_start' from start propagation FIFO 'vit_block_top_vit_block_top.grp_dataflow_wrapper_fu_6443.task_compute_mlp_U0.grp_do_mlp_fu_4710.start_for_stream_merge_U0_U' written by process 'vit_block_top_vit_block_top.grp_dataflow_wrapper_fu_6443.task_compute_mlp_U0.grp_do_mlp_fu_4710.do_adapt_5_U0',");
                        end
                    end
                    59: begin //  for dep proc 'vit_block_top_vit_block_top.grp_dataflow_wrapper_fu_6443.task_compute_mlp_U0.grp_do_mlp_fu_4710.do_matmul_U0'
// for dep channel 'vit_block_top_vit_block_top.grp_dataflow_wrapper_fu_6443.task_compute_mlp_U0.grp_do_mlp_fu_4710.m2_sm_i_U' info is :
// blk sig is {~vit_block_top_vit_block_top_inst.grp_dataflow_wrapper_fu_6443.task_compute_mlp_U0.grp_do_mlp_fu_4710.stream_merge_U0.grp_stream_merge_Pipeline_VITIS_LOOP_393_1_VITIS_LOOP_394_2_fu_34.m2_sm_blk_n data_FIFO}
                        if ((~grp_dataflow_wrapper_fu_6443.task_compute_mlp_U0.grp_do_mlp_fu_4710.stream_merge_U0.grp_stream_merge_Pipeline_VITIS_LOOP_393_1_VITIS_LOOP_394_2_fu_34.m2_sm_blk_n)) begin
                            if (~grp_dataflow_wrapper_fu_6443.task_compute_mlp_U0.grp_do_mlp_fu_4710.m2_sm_i_U.if_empty_n) begin
                                $display("//      Blocked by empty input FIFO 'vit_block_top_vit_block_top.grp_dataflow_wrapper_fu_6443.task_compute_mlp_U0.grp_do_mlp_fu_4710.m2_sm_i_U' written by process 'vit_block_top_vit_block_top.grp_dataflow_wrapper_fu_6443.task_compute_mlp_U0.grp_do_mlp_fu_4710.do_matmul_U0'");
                                $fdisplay(fp, "Dependence_Channel_path vit_block_top_vit_block_top.grp_dataflow_wrapper_fu_6443.task_compute_mlp_U0.grp_do_mlp_fu_4710.m2_sm_i_U");
                                $fdisplay(fp, "Dependence_Channel_status EMPTY");
                            end
                            else if (~grp_dataflow_wrapper_fu_6443.task_compute_mlp_U0.grp_do_mlp_fu_4710.m2_sm_i_U.if_full_n) begin
                                $display("//      Blocked by full output FIFO 'vit_block_top_vit_block_top.grp_dataflow_wrapper_fu_6443.task_compute_mlp_U0.grp_do_mlp_fu_4710.m2_sm_i_U' read by process 'vit_block_top_vit_block_top.grp_dataflow_wrapper_fu_6443.task_compute_mlp_U0.grp_do_mlp_fu_4710.do_matmul_U0'");
                                $fdisplay(fp, "Dependence_Channel_path vit_block_top_vit_block_top.grp_dataflow_wrapper_fu_6443.task_compute_mlp_U0.grp_do_mlp_fu_4710.m2_sm_i_U");
                                $fdisplay(fp, "Dependence_Channel_status FULL");
                            end
                        end
                    end
                    63: begin //  for dep proc 'vit_block_top_vit_block_top.grp_dataflow_wrapper_fu_6443.task_compute_mlp_U0.grp_do_mlp_fu_4710.do_matmul_U0.do_adapt_8_U0'
// for dep channel 'vit_block_top_vit_block_top.grp_dataflow_wrapper_fu_6443.task_compute_mlp_U0.grp_do_mlp_fu_4710.m2_sm_i_U' info is :
// blk sig is {~vit_block_top_vit_block_top_inst.grp_dataflow_wrapper_fu_6443.task_compute_mlp_U0.grp_do_mlp_fu_4710.stream_merge_U0.grp_stream_merge_Pipeline_VITIS_LOOP_393_1_VITIS_LOOP_394_2_fu_34.m2_sm_blk_n data_FIFO}
                        if ((~grp_dataflow_wrapper_fu_6443.task_compute_mlp_U0.grp_do_mlp_fu_4710.stream_merge_U0.grp_stream_merge_Pipeline_VITIS_LOOP_393_1_VITIS_LOOP_394_2_fu_34.m2_sm_blk_n)) begin
                            if (~grp_dataflow_wrapper_fu_6443.task_compute_mlp_U0.grp_do_mlp_fu_4710.m2_sm_i_U.if_empty_n) begin
                                $display("//      Blocked by empty input FIFO 'vit_block_top_vit_block_top.grp_dataflow_wrapper_fu_6443.task_compute_mlp_U0.grp_do_mlp_fu_4710.m2_sm_i_U' written by process 'vit_block_top_vit_block_top.grp_dataflow_wrapper_fu_6443.task_compute_mlp_U0.grp_do_mlp_fu_4710.do_matmul_U0.do_adapt_8_U0'");
                                $fdisplay(fp, "Dependence_Channel_path vit_block_top_vit_block_top.grp_dataflow_wrapper_fu_6443.task_compute_mlp_U0.grp_do_mlp_fu_4710.m2_sm_i_U");
                                $fdisplay(fp, "Dependence_Channel_status EMPTY");
                            end
                            else if (~grp_dataflow_wrapper_fu_6443.task_compute_mlp_U0.grp_do_mlp_fu_4710.m2_sm_i_U.if_full_n) begin
                                $display("//      Blocked by full output FIFO 'vit_block_top_vit_block_top.grp_dataflow_wrapper_fu_6443.task_compute_mlp_U0.grp_do_mlp_fu_4710.m2_sm_i_U' read by process 'vit_block_top_vit_block_top.grp_dataflow_wrapper_fu_6443.task_compute_mlp_U0.grp_do_mlp_fu_4710.do_matmul_U0.do_adapt_8_U0'");
                                $fdisplay(fp, "Dependence_Channel_path vit_block_top_vit_block_top.grp_dataflow_wrapper_fu_6443.task_compute_mlp_U0.grp_do_mlp_fu_4710.m2_sm_i_U");
                                $fdisplay(fp, "Dependence_Channel_status FULL");
                            end
                        end
                    end
                    endcase
                end
                65 : begin // for proc 'vit_block_top_vit_block_top.grp_dataflow_wrapper_fu_6443.task_write_fm_U0'
                    case(index2)
                    48: begin //  for dep proc 'vit_block_top_vit_block_top.grp_dataflow_wrapper_fu_6443.task_compute_mlp_U0'
// for dep channel 'vit_block_top_vit_block_top.grp_dataflow_wrapper_fu_6443.o_stream_int_U' info is :
// blk sig is {~vit_block_top_vit_block_top_inst.grp_dataflow_wrapper_fu_6443.task_write_fm_U0.o_stream_int_blk_n data_FIFO}
                        if ((~grp_dataflow_wrapper_fu_6443.task_write_fm_U0.o_stream_int_blk_n)) begin
                            if (~grp_dataflow_wrapper_fu_6443.o_stream_int_U.if_empty_n) begin
                                $display("//      Blocked by empty input FIFO 'vit_block_top_vit_block_top.grp_dataflow_wrapper_fu_6443.o_stream_int_U' written by process 'vit_block_top_vit_block_top.grp_dataflow_wrapper_fu_6443.task_compute_mlp_U0'");
                                $fdisplay(fp, "Dependence_Channel_path vit_block_top_vit_block_top.grp_dataflow_wrapper_fu_6443.o_stream_int_U");
                                $fdisplay(fp, "Dependence_Channel_status EMPTY");
                            end
                            else if (~grp_dataflow_wrapper_fu_6443.o_stream_int_U.if_full_n) begin
                                $display("//      Blocked by full output FIFO 'vit_block_top_vit_block_top.grp_dataflow_wrapper_fu_6443.o_stream_int_U' read by process 'vit_block_top_vit_block_top.grp_dataflow_wrapper_fu_6443.task_compute_mlp_U0'");
                                $fdisplay(fp, "Dependence_Channel_path vit_block_top_vit_block_top.grp_dataflow_wrapper_fu_6443.o_stream_int_U");
                                $fdisplay(fp, "Dependence_Channel_status FULL");
                            end
                        end
// for dep channel 'vit_block_top_vit_block_top.grp_dataflow_wrapper_fu_6443.start_for_task_write_fm_U0_U' info is :
// blk sig is {{~vit_block_top_vit_block_top_inst.grp_dataflow_wrapper_fu_6443.start_for_task_write_fm_U0_U.if_empty_n & vit_block_top_vit_block_top_inst.grp_dataflow_wrapper_fu_6443.task_write_fm_U0.ap_idle & ~vit_block_top_vit_block_top_inst.grp_dataflow_wrapper_fu_6443.start_for_task_write_fm_U0_U.if_write} start_FIFO}
                        if ((~grp_dataflow_wrapper_fu_6443.start_for_task_write_fm_U0_U.if_empty_n & grp_dataflow_wrapper_fu_6443.task_write_fm_U0.ap_idle & ~grp_dataflow_wrapper_fu_6443.start_for_task_write_fm_U0_U.if_write)) begin
                            $display("//      Blocked by missing 'ap_start' from start propagation FIFO 'vit_block_top_vit_block_top.grp_dataflow_wrapper_fu_6443.start_for_task_write_fm_U0_U' written by process 'vit_block_top_vit_block_top.grp_dataflow_wrapper_fu_6443.task_compute_mlp_U0',");
                        end
                    end
                    66: begin //  for dep proc 'vit_block_top_vit_block_top.grp_dataflow_wrapper_fu_6443.task_load_weights_14_U0'
// for dep channel '' info is :
// blk sig is {{ap_done_reg_5 & vit_block_top_vit_block_top_inst.grp_dataflow_wrapper_fu_6443.task_write_fm_U0.ap_done & ~vit_block_top_vit_block_top_inst.grp_dataflow_wrapper_fu_6443.task_load_weights_14_U0.ap_done} output_sync}
                        if ((ap_done_reg_5 & grp_dataflow_wrapper_fu_6443.task_write_fm_U0.ap_done & ~grp_dataflow_wrapper_fu_6443.task_load_weights_14_U0.ap_done)) begin
                            $display("//      Blocked by output sync logic with process : 'vit_block_top_vit_block_top.grp_dataflow_wrapper_fu_6443.task_load_weights_14_U0'");
                        end
                    end
                    endcase
                end
                66 : begin // for proc 'vit_block_top_vit_block_top.grp_dataflow_wrapper_fu_6443.task_load_weights_14_U0'
                    case(index2)
                    9: begin //  for dep proc 'vit_block_top_vit_block_top.grp_dataflow_wrapper_fu_6443.dataflow_wrapper_Block_entry_calc_weights_attn_weights_attn_scalars_rd_calc_weig_U0'
// for dep channel 'vit_block_top_vit_block_top.grp_dataflow_wrapper_fu_6443.add_loc_channel_U' info is :
// blk sig is {{~vit_block_top_vit_block_top_inst.grp_dataflow_wrapper_fu_6443.add_loc_channel_U.if_empty_n & vit_block_top_vit_block_top_inst.grp_dataflow_wrapper_fu_6443.task_load_weights_14_U0.ap_idle & ~vit_block_top_vit_block_top_inst.grp_dataflow_wrapper_fu_6443.add_loc_channel_U.if_write} TLF_FIFO}
                        if ((~grp_dataflow_wrapper_fu_6443.add_loc_channel_U.if_empty_n & grp_dataflow_wrapper_fu_6443.task_load_weights_14_U0.ap_idle & ~grp_dataflow_wrapper_fu_6443.add_loc_channel_U.if_write)) begin
                            if (~grp_dataflow_wrapper_fu_6443.add_loc_channel_U.if_empty_n) begin
                                $display("//      Blocked by empty input FIFO 'vit_block_top_vit_block_top.grp_dataflow_wrapper_fu_6443.add_loc_channel_U' written by process 'vit_block_top_vit_block_top.grp_dataflow_wrapper_fu_6443.dataflow_wrapper_Block_entry_calc_weights_attn_weights_attn_scalars_rd_calc_weig_U0'");
                                $fdisplay(fp, "Dependence_Channel_path vit_block_top_vit_block_top.grp_dataflow_wrapper_fu_6443.add_loc_channel_U");
                                $fdisplay(fp, "Dependence_Channel_status EMPTY");
                            end
                            else if (~grp_dataflow_wrapper_fu_6443.add_loc_channel_U.if_full_n) begin
                                $display("//      Blocked by full output FIFO 'vit_block_top_vit_block_top.grp_dataflow_wrapper_fu_6443.add_loc_channel_U' read by process 'vit_block_top_vit_block_top.grp_dataflow_wrapper_fu_6443.dataflow_wrapper_Block_entry_calc_weights_attn_weights_attn_scalars_rd_calc_weig_U0'");
                                $fdisplay(fp, "Dependence_Channel_path vit_block_top_vit_block_top.grp_dataflow_wrapper_fu_6443.add_loc_channel_U");
                                $fdisplay(fp, "Dependence_Channel_status FULL");
                            end
                        end
                    end
                    65: begin //  for dep proc 'vit_block_top_vit_block_top.grp_dataflow_wrapper_fu_6443.task_write_fm_U0'
// for dep channel '' info is :
// blk sig is {{ap_done_reg_2 & vit_block_top_vit_block_top_inst.grp_dataflow_wrapper_fu_6443.task_load_weights_14_U0.ap_done & ~vit_block_top_vit_block_top_inst.grp_dataflow_wrapper_fu_6443.task_write_fm_U0.ap_done} output_sync}
                        if ((ap_done_reg_2 & grp_dataflow_wrapper_fu_6443.task_load_weights_14_U0.ap_done & ~grp_dataflow_wrapper_fu_6443.task_write_fm_U0.ap_done)) begin
                            $display("//      Blocked by output sync logic with process : 'vit_block_top_vit_block_top.grp_dataflow_wrapper_fu_6443.task_write_fm_U0'");
                        end
                    end
                    endcase
                end
                67 : begin // for proc 'vit_block_top_vit_block_top.grp_task_run_head_fu_11440.task_read_cls_fm_U0'
                    case(index2)
                    68: begin //  for dep proc 'vit_block_top_vit_block_top.grp_task_run_head_fu_11440.fixed_head_do_head_U0'
// for dep channel 'vit_block_top_vit_block_top.grp_task_run_head_fu_11440.head_in_sm_U' info is :
// blk sig is {~vit_block_top_vit_block_top_inst.grp_task_run_head_fu_11440.task_read_cls_fm_U0.head_in_sm_blk_n data_FIFO}
                        if ((~grp_task_run_head_fu_11440.task_read_cls_fm_U0.head_in_sm_blk_n)) begin
                            if (~grp_task_run_head_fu_11440.head_in_sm_U.if_empty_n) begin
                                $display("//      Blocked by empty input FIFO 'vit_block_top_vit_block_top.grp_task_run_head_fu_11440.head_in_sm_U' written by process 'vit_block_top_vit_block_top.grp_task_run_head_fu_11440.fixed_head_do_head_U0'");
                                $fdisplay(fp, "Dependence_Channel_path vit_block_top_vit_block_top.grp_task_run_head_fu_11440.head_in_sm_U");
                                $fdisplay(fp, "Dependence_Channel_status EMPTY");
                            end
                            else if (~grp_task_run_head_fu_11440.head_in_sm_U.if_full_n) begin
                                $display("//      Blocked by full output FIFO 'vit_block_top_vit_block_top.grp_task_run_head_fu_11440.head_in_sm_U' read by process 'vit_block_top_vit_block_top.grp_task_run_head_fu_11440.fixed_head_do_head_U0'");
                                $fdisplay(fp, "Dependence_Channel_path vit_block_top_vit_block_top.grp_task_run_head_fu_11440.head_in_sm_U");
                                $fdisplay(fp, "Dependence_Channel_status FULL");
                            end
                        end
// for dep channel 'vit_block_top_vit_block_top.grp_task_run_head_fu_11440.start_for_fixed_head_do_head_U0_U' info is :
// blk sig is {{~vit_block_top_vit_block_top_inst.grp_task_run_head_fu_11440.start_for_fixed_head_do_head_U0_U.if_full_n & vit_block_top_vit_block_top_inst.grp_task_run_head_fu_11440.task_read_cls_fm_U0.ap_start & ~vit_block_top_vit_block_top_inst.grp_task_run_head_fu_11440.task_read_cls_fm_U0.real_start & (trans_in_cnt_44 == trans_out_cnt_44) & ~vit_block_top_vit_block_top_inst.grp_task_run_head_fu_11440.start_for_fixed_head_do_head_U0_U.if_read} start_FIFO}
                        if ((~grp_task_run_head_fu_11440.start_for_fixed_head_do_head_U0_U.if_full_n & grp_task_run_head_fu_11440.task_read_cls_fm_U0.ap_start & ~grp_task_run_head_fu_11440.task_read_cls_fm_U0.real_start & (trans_in_cnt_44 == trans_out_cnt_44) & ~grp_task_run_head_fu_11440.start_for_fixed_head_do_head_U0_U.if_read)) begin
                            $display("//      Blocked by full output start propagation FIFO 'vit_block_top_vit_block_top.grp_task_run_head_fu_11440.start_for_fixed_head_do_head_U0_U' read by process 'vit_block_top_vit_block_top.grp_task_run_head_fu_11440.fixed_head_do_head_U0',");
                        end
                    end
                    69: begin //  for dep proc 'vit_block_top_vit_block_top.grp_task_run_head_fu_11440.fixed_head_do_head_U0.fixed_head_layernorm_U0'
// for dep channel 'vit_block_top_vit_block_top.grp_task_run_head_fu_11440.head_in_sm_U' info is :
// blk sig is {~vit_block_top_vit_block_top_inst.grp_task_run_head_fu_11440.task_read_cls_fm_U0.head_in_sm_blk_n data_FIFO}
                        if ((~grp_task_run_head_fu_11440.task_read_cls_fm_U0.head_in_sm_blk_n)) begin
                            if (~grp_task_run_head_fu_11440.head_in_sm_U.if_empty_n) begin
                                $display("//      Blocked by empty input FIFO 'vit_block_top_vit_block_top.grp_task_run_head_fu_11440.head_in_sm_U' written by process 'vit_block_top_vit_block_top.grp_task_run_head_fu_11440.fixed_head_do_head_U0.fixed_head_layernorm_U0'");
                                $fdisplay(fp, "Dependence_Channel_path vit_block_top_vit_block_top.grp_task_run_head_fu_11440.head_in_sm_U");
                                $fdisplay(fp, "Dependence_Channel_status EMPTY");
                            end
                            else if (~grp_task_run_head_fu_11440.head_in_sm_U.if_full_n) begin
                                $display("//      Blocked by full output FIFO 'vit_block_top_vit_block_top.grp_task_run_head_fu_11440.head_in_sm_U' read by process 'vit_block_top_vit_block_top.grp_task_run_head_fu_11440.fixed_head_do_head_U0.fixed_head_layernorm_U0'");
                                $fdisplay(fp, "Dependence_Channel_path vit_block_top_vit_block_top.grp_task_run_head_fu_11440.head_in_sm_U");
                                $fdisplay(fp, "Dependence_Channel_status FULL");
                            end
                        end
                    end
                    endcase
                end
                68 : begin // for proc 'vit_block_top_vit_block_top.grp_task_run_head_fu_11440.fixed_head_do_head_U0'
                    case(index2)
                    67: begin //  for dep proc 'vit_block_top_vit_block_top.grp_task_run_head_fu_11440.task_read_cls_fm_U0'
// for dep channel 'vit_block_top_vit_block_top.grp_task_run_head_fu_11440.head_in_sm_U' info is :
// blk sig is {~vit_block_top_vit_block_top_inst.grp_task_run_head_fu_11440.fixed_head_do_head_U0.fixed_head_layernorm_U0.head_in_sm_blk_n data_FIFO}
                        if ((~grp_task_run_head_fu_11440.fixed_head_do_head_U0.fixed_head_layernorm_U0.head_in_sm_blk_n)) begin
                            if (~grp_task_run_head_fu_11440.head_in_sm_U.if_empty_n) begin
                                $display("//      Blocked by empty input FIFO 'vit_block_top_vit_block_top.grp_task_run_head_fu_11440.head_in_sm_U' written by process 'vit_block_top_vit_block_top.grp_task_run_head_fu_11440.task_read_cls_fm_U0'");
                                $fdisplay(fp, "Dependence_Channel_path vit_block_top_vit_block_top.grp_task_run_head_fu_11440.head_in_sm_U");
                                $fdisplay(fp, "Dependence_Channel_status EMPTY");
                            end
                            else if (~grp_task_run_head_fu_11440.head_in_sm_U.if_full_n) begin
                                $display("//      Blocked by full output FIFO 'vit_block_top_vit_block_top.grp_task_run_head_fu_11440.head_in_sm_U' read by process 'vit_block_top_vit_block_top.grp_task_run_head_fu_11440.task_read_cls_fm_U0'");
                                $fdisplay(fp, "Dependence_Channel_path vit_block_top_vit_block_top.grp_task_run_head_fu_11440.head_in_sm_U");
                                $fdisplay(fp, "Dependence_Channel_status FULL");
                            end
                        end
// for dep channel 'vit_block_top_vit_block_top.grp_task_run_head_fu_11440.start_for_fixed_head_do_head_U0_U' info is :
// blk sig is {{~vit_block_top_vit_block_top_inst.grp_task_run_head_fu_11440.start_for_fixed_head_do_head_U0_U.if_empty_n & vit_block_top_vit_block_top_inst.grp_task_run_head_fu_11440.fixed_head_do_head_U0.ap_idle & ~vit_block_top_vit_block_top_inst.grp_task_run_head_fu_11440.start_for_fixed_head_do_head_U0_U.if_write} start_FIFO}
                        if ((~grp_task_run_head_fu_11440.start_for_fixed_head_do_head_U0_U.if_empty_n & grp_task_run_head_fu_11440.fixed_head_do_head_U0.ap_idle & ~grp_task_run_head_fu_11440.start_for_fixed_head_do_head_U0_U.if_write)) begin
                            $display("//      Blocked by missing 'ap_start' from start propagation FIFO 'vit_block_top_vit_block_top.grp_task_run_head_fu_11440.start_for_fixed_head_do_head_U0_U' written by process 'vit_block_top_vit_block_top.grp_task_run_head_fu_11440.task_read_cls_fm_U0',");
                        end
                    end
                    73: begin //  for dep proc 'vit_block_top_vit_block_top.grp_task_run_head_fu_11440.task_write_logits_U0'
// for dep channel 'vit_block_top_vit_block_top.grp_task_run_head_fu_11440.head_out_sm_U' info is :
// blk sig is {~vit_block_top_vit_block_top_inst.grp_task_run_head_fu_11440.fixed_head_do_head_U0.fixed_head_matmul_U0.do_adapt_3_U0.head_out_sm_blk_n data_FIFO}
                        if ((~grp_task_run_head_fu_11440.fixed_head_do_head_U0.fixed_head_matmul_U0.do_adapt_3_U0.head_out_sm_blk_n)) begin
                            if (~grp_task_run_head_fu_11440.head_out_sm_U.if_empty_n) begin
                                $display("//      Blocked by empty input FIFO 'vit_block_top_vit_block_top.grp_task_run_head_fu_11440.head_out_sm_U' written by process 'vit_block_top_vit_block_top.grp_task_run_head_fu_11440.task_write_logits_U0'");
                                $fdisplay(fp, "Dependence_Channel_path vit_block_top_vit_block_top.grp_task_run_head_fu_11440.head_out_sm_U");
                                $fdisplay(fp, "Dependence_Channel_status EMPTY");
                            end
                            else if (~grp_task_run_head_fu_11440.head_out_sm_U.if_full_n) begin
                                $display("//      Blocked by full output FIFO 'vit_block_top_vit_block_top.grp_task_run_head_fu_11440.head_out_sm_U' read by process 'vit_block_top_vit_block_top.grp_task_run_head_fu_11440.task_write_logits_U0'");
                                $fdisplay(fp, "Dependence_Channel_path vit_block_top_vit_block_top.grp_task_run_head_fu_11440.head_out_sm_U");
                                $fdisplay(fp, "Dependence_Channel_status FULL");
                            end
                        end
// for dep channel 'vit_block_top_vit_block_top.grp_task_run_head_fu_11440.start_for_task_write_logits_U0_U' info is :
// blk sig is {{~vit_block_top_vit_block_top_inst.grp_task_run_head_fu_11440.start_for_task_write_logits_U0_U.if_full_n & vit_block_top_vit_block_top_inst.grp_task_run_head_fu_11440.fixed_head_do_head_U0.ap_start & ~vit_block_top_vit_block_top_inst.grp_task_run_head_fu_11440.fixed_head_do_head_U0.real_start & (trans_in_cnt_47 == trans_out_cnt_47) & ~vit_block_top_vit_block_top_inst.grp_task_run_head_fu_11440.start_for_task_write_logits_U0_U.if_read} start_FIFO}
                        if ((~grp_task_run_head_fu_11440.start_for_task_write_logits_U0_U.if_full_n & grp_task_run_head_fu_11440.fixed_head_do_head_U0.ap_start & ~grp_task_run_head_fu_11440.fixed_head_do_head_U0.real_start & (trans_in_cnt_47 == trans_out_cnt_47) & ~grp_task_run_head_fu_11440.start_for_task_write_logits_U0_U.if_read)) begin
                            $display("//      Blocked by full output start propagation FIFO 'vit_block_top_vit_block_top.grp_task_run_head_fu_11440.start_for_task_write_logits_U0_U' read by process 'vit_block_top_vit_block_top.grp_task_run_head_fu_11440.task_write_logits_U0',");
                        end
                    end
                    endcase
                end
                69 : begin // for proc 'vit_block_top_vit_block_top.grp_task_run_head_fu_11440.fixed_head_do_head_U0.fixed_head_layernorm_U0'
                    case(index2)
                    67: begin //  for dep proc 'vit_block_top_vit_block_top.grp_task_run_head_fu_11440.task_read_cls_fm_U0'
// for dep channel 'vit_block_top_vit_block_top.grp_task_run_head_fu_11440.head_in_sm_U' info is :
// blk sig is {~vit_block_top_vit_block_top_inst.grp_task_run_head_fu_11440.fixed_head_do_head_U0.fixed_head_layernorm_U0.head_in_sm_blk_n data_FIFO}
                        if ((~grp_task_run_head_fu_11440.fixed_head_do_head_U0.fixed_head_layernorm_U0.head_in_sm_blk_n)) begin
                            if (~grp_task_run_head_fu_11440.head_in_sm_U.if_empty_n) begin
                                $display("//      Blocked by empty input FIFO 'vit_block_top_vit_block_top.grp_task_run_head_fu_11440.head_in_sm_U' written by process 'vit_block_top_vit_block_top.grp_task_run_head_fu_11440.task_read_cls_fm_U0'");
                                $fdisplay(fp, "Dependence_Channel_path vit_block_top_vit_block_top.grp_task_run_head_fu_11440.head_in_sm_U");
                                $fdisplay(fp, "Dependence_Channel_status EMPTY");
                            end
                            else if (~grp_task_run_head_fu_11440.head_in_sm_U.if_full_n) begin
                                $display("//      Blocked by full output FIFO 'vit_block_top_vit_block_top.grp_task_run_head_fu_11440.head_in_sm_U' read by process 'vit_block_top_vit_block_top.grp_task_run_head_fu_11440.task_read_cls_fm_U0'");
                                $fdisplay(fp, "Dependence_Channel_path vit_block_top_vit_block_top.grp_task_run_head_fu_11440.head_in_sm_U");
                                $fdisplay(fp, "Dependence_Channel_status FULL");
                            end
                        end
                    end
                    70: begin //  for dep proc 'vit_block_top_vit_block_top.grp_task_run_head_fu_11440.fixed_head_do_head_U0.fixed_head_matmul_U0'
// for dep channel 'vit_block_top_vit_block_top.grp_task_run_head_fu_11440.fixed_head_do_head_U0.ln_sm_U' info is :
// blk sig is {~vit_block_top_vit_block_top_inst.grp_task_run_head_fu_11440.fixed_head_do_head_U0.fixed_head_layernorm_U0.ln_sm_blk_n data_FIFO}
                        if ((~grp_task_run_head_fu_11440.fixed_head_do_head_U0.fixed_head_layernorm_U0.ln_sm_blk_n)) begin
                            if (~grp_task_run_head_fu_11440.fixed_head_do_head_U0.ln_sm_U.if_empty_n) begin
                                $display("//      Blocked by empty input FIFO 'vit_block_top_vit_block_top.grp_task_run_head_fu_11440.fixed_head_do_head_U0.ln_sm_U' written by process 'vit_block_top_vit_block_top.grp_task_run_head_fu_11440.fixed_head_do_head_U0.fixed_head_matmul_U0'");
                                $fdisplay(fp, "Dependence_Channel_path vit_block_top_vit_block_top.grp_task_run_head_fu_11440.fixed_head_do_head_U0.ln_sm_U");
                                $fdisplay(fp, "Dependence_Channel_status EMPTY");
                            end
                            else if (~grp_task_run_head_fu_11440.fixed_head_do_head_U0.ln_sm_U.if_full_n) begin
                                $display("//      Blocked by full output FIFO 'vit_block_top_vit_block_top.grp_task_run_head_fu_11440.fixed_head_do_head_U0.ln_sm_U' read by process 'vit_block_top_vit_block_top.grp_task_run_head_fu_11440.fixed_head_do_head_U0.fixed_head_matmul_U0'");
                                $fdisplay(fp, "Dependence_Channel_path vit_block_top_vit_block_top.grp_task_run_head_fu_11440.fixed_head_do_head_U0.ln_sm_U");
                                $fdisplay(fp, "Dependence_Channel_status FULL");
                            end
                        end
// for dep channel 'vit_block_top_vit_block_top.grp_task_run_head_fu_11440.fixed_head_do_head_U0.start_for_fixed_head_matmul_U0_U' info is :
// blk sig is {{~vit_block_top_vit_block_top_inst.grp_task_run_head_fu_11440.fixed_head_do_head_U0.start_for_fixed_head_matmul_U0_U.if_full_n & vit_block_top_vit_block_top_inst.grp_task_run_head_fu_11440.fixed_head_do_head_U0.fixed_head_layernorm_U0.ap_start & ~vit_block_top_vit_block_top_inst.grp_task_run_head_fu_11440.fixed_head_do_head_U0.fixed_head_layernorm_U0.real_start & (trans_in_cnt_45 == trans_out_cnt_45) & ~vit_block_top_vit_block_top_inst.grp_task_run_head_fu_11440.fixed_head_do_head_U0.start_for_fixed_head_matmul_U0_U.if_read} start_FIFO}
                        if ((~grp_task_run_head_fu_11440.fixed_head_do_head_U0.start_for_fixed_head_matmul_U0_U.if_full_n & grp_task_run_head_fu_11440.fixed_head_do_head_U0.fixed_head_layernorm_U0.ap_start & ~grp_task_run_head_fu_11440.fixed_head_do_head_U0.fixed_head_layernorm_U0.real_start & (trans_in_cnt_45 == trans_out_cnt_45) & ~grp_task_run_head_fu_11440.fixed_head_do_head_U0.start_for_fixed_head_matmul_U0_U.if_read)) begin
                            $display("//      Blocked by full output start propagation FIFO 'vit_block_top_vit_block_top.grp_task_run_head_fu_11440.fixed_head_do_head_U0.start_for_fixed_head_matmul_U0_U' read by process 'vit_block_top_vit_block_top.grp_task_run_head_fu_11440.fixed_head_do_head_U0.fixed_head_matmul_U0',");
                        end
                    end
                    71: begin //  for dep proc 'vit_block_top_vit_block_top.grp_task_run_head_fu_11440.fixed_head_do_head_U0.fixed_head_matmul_U0.fixed_head_matmul_core_U0'
// for dep channel 'vit_block_top_vit_block_top.grp_task_run_head_fu_11440.fixed_head_do_head_U0.ln_sm_U' info is :
// blk sig is {~vit_block_top_vit_block_top_inst.grp_task_run_head_fu_11440.fixed_head_do_head_U0.fixed_head_layernorm_U0.ln_sm_blk_n data_FIFO}
                        if ((~grp_task_run_head_fu_11440.fixed_head_do_head_U0.fixed_head_layernorm_U0.ln_sm_blk_n)) begin
                            if (~grp_task_run_head_fu_11440.fixed_head_do_head_U0.ln_sm_U.if_empty_n) begin
                                $display("//      Blocked by empty input FIFO 'vit_block_top_vit_block_top.grp_task_run_head_fu_11440.fixed_head_do_head_U0.ln_sm_U' written by process 'vit_block_top_vit_block_top.grp_task_run_head_fu_11440.fixed_head_do_head_U0.fixed_head_matmul_U0.fixed_head_matmul_core_U0'");
                                $fdisplay(fp, "Dependence_Channel_path vit_block_top_vit_block_top.grp_task_run_head_fu_11440.fixed_head_do_head_U0.ln_sm_U");
                                $fdisplay(fp, "Dependence_Channel_status EMPTY");
                            end
                            else if (~grp_task_run_head_fu_11440.fixed_head_do_head_U0.ln_sm_U.if_full_n) begin
                                $display("//      Blocked by full output FIFO 'vit_block_top_vit_block_top.grp_task_run_head_fu_11440.fixed_head_do_head_U0.ln_sm_U' read by process 'vit_block_top_vit_block_top.grp_task_run_head_fu_11440.fixed_head_do_head_U0.fixed_head_matmul_U0.fixed_head_matmul_core_U0'");
                                $fdisplay(fp, "Dependence_Channel_path vit_block_top_vit_block_top.grp_task_run_head_fu_11440.fixed_head_do_head_U0.ln_sm_U");
                                $fdisplay(fp, "Dependence_Channel_status FULL");
                            end
                        end
                    end
                    endcase
                end
                70 : begin // for proc 'vit_block_top_vit_block_top.grp_task_run_head_fu_11440.fixed_head_do_head_U0.fixed_head_matmul_U0'
                    case(index2)
                    69: begin //  for dep proc 'vit_block_top_vit_block_top.grp_task_run_head_fu_11440.fixed_head_do_head_U0.fixed_head_layernorm_U0'
// for dep channel 'vit_block_top_vit_block_top.grp_task_run_head_fu_11440.fixed_head_do_head_U0.ln_sm_U' info is :
// blk sig is {~vit_block_top_vit_block_top_inst.grp_task_run_head_fu_11440.fixed_head_do_head_U0.fixed_head_matmul_U0.fixed_head_matmul_core_U0.grp_fixed_head_matmul_core_Pipeline_READ_LOOP_fu_50.ln_sm_blk_n data_FIFO}
                        if ((~grp_task_run_head_fu_11440.fixed_head_do_head_U0.fixed_head_matmul_U0.fixed_head_matmul_core_U0.grp_fixed_head_matmul_core_Pipeline_READ_LOOP_fu_50.ln_sm_blk_n)) begin
                            if (~grp_task_run_head_fu_11440.fixed_head_do_head_U0.ln_sm_U.if_empty_n) begin
                                $display("//      Blocked by empty input FIFO 'vit_block_top_vit_block_top.grp_task_run_head_fu_11440.fixed_head_do_head_U0.ln_sm_U' written by process 'vit_block_top_vit_block_top.grp_task_run_head_fu_11440.fixed_head_do_head_U0.fixed_head_layernorm_U0'");
                                $fdisplay(fp, "Dependence_Channel_path vit_block_top_vit_block_top.grp_task_run_head_fu_11440.fixed_head_do_head_U0.ln_sm_U");
                                $fdisplay(fp, "Dependence_Channel_status EMPTY");
                            end
                            else if (~grp_task_run_head_fu_11440.fixed_head_do_head_U0.ln_sm_U.if_full_n) begin
                                $display("//      Blocked by full output FIFO 'vit_block_top_vit_block_top.grp_task_run_head_fu_11440.fixed_head_do_head_U0.ln_sm_U' read by process 'vit_block_top_vit_block_top.grp_task_run_head_fu_11440.fixed_head_do_head_U0.fixed_head_layernorm_U0'");
                                $fdisplay(fp, "Dependence_Channel_path vit_block_top_vit_block_top.grp_task_run_head_fu_11440.fixed_head_do_head_U0.ln_sm_U");
                                $fdisplay(fp, "Dependence_Channel_status FULL");
                            end
                        end
// for dep channel 'vit_block_top_vit_block_top.grp_task_run_head_fu_11440.fixed_head_do_head_U0.start_for_fixed_head_matmul_U0_U' info is :
// blk sig is {{~vit_block_top_vit_block_top_inst.grp_task_run_head_fu_11440.fixed_head_do_head_U0.start_for_fixed_head_matmul_U0_U.if_empty_n & vit_block_top_vit_block_top_inst.grp_task_run_head_fu_11440.fixed_head_do_head_U0.fixed_head_matmul_U0.ap_idle & ~vit_block_top_vit_block_top_inst.grp_task_run_head_fu_11440.fixed_head_do_head_U0.start_for_fixed_head_matmul_U0_U.if_write} start_FIFO}
                        if ((~grp_task_run_head_fu_11440.fixed_head_do_head_U0.start_for_fixed_head_matmul_U0_U.if_empty_n & grp_task_run_head_fu_11440.fixed_head_do_head_U0.fixed_head_matmul_U0.ap_idle & ~grp_task_run_head_fu_11440.fixed_head_do_head_U0.start_for_fixed_head_matmul_U0_U.if_write)) begin
                            $display("//      Blocked by missing 'ap_start' from start propagation FIFO 'vit_block_top_vit_block_top.grp_task_run_head_fu_11440.fixed_head_do_head_U0.start_for_fixed_head_matmul_U0_U' written by process 'vit_block_top_vit_block_top.grp_task_run_head_fu_11440.fixed_head_do_head_U0.fixed_head_layernorm_U0',");
                        end
                    end
                    73: begin //  for dep proc 'vit_block_top_vit_block_top.grp_task_run_head_fu_11440.task_write_logits_U0'
// for dep channel 'vit_block_top_vit_block_top.grp_task_run_head_fu_11440.head_out_sm_U' info is :
// blk sig is {~vit_block_top_vit_block_top_inst.grp_task_run_head_fu_11440.fixed_head_do_head_U0.fixed_head_matmul_U0.do_adapt_3_U0.head_out_sm_blk_n data_FIFO}
                        if ((~grp_task_run_head_fu_11440.fixed_head_do_head_U0.fixed_head_matmul_U0.do_adapt_3_U0.head_out_sm_blk_n)) begin
                            if (~grp_task_run_head_fu_11440.head_out_sm_U.if_empty_n) begin
                                $display("//      Blocked by empty input FIFO 'vit_block_top_vit_block_top.grp_task_run_head_fu_11440.head_out_sm_U' written by process 'vit_block_top_vit_block_top.grp_task_run_head_fu_11440.task_write_logits_U0'");
                                $fdisplay(fp, "Dependence_Channel_path vit_block_top_vit_block_top.grp_task_run_head_fu_11440.head_out_sm_U");
                                $fdisplay(fp, "Dependence_Channel_status EMPTY");
                            end
                            else if (~grp_task_run_head_fu_11440.head_out_sm_U.if_full_n) begin
                                $display("//      Blocked by full output FIFO 'vit_block_top_vit_block_top.grp_task_run_head_fu_11440.head_out_sm_U' read by process 'vit_block_top_vit_block_top.grp_task_run_head_fu_11440.task_write_logits_U0'");
                                $fdisplay(fp, "Dependence_Channel_path vit_block_top_vit_block_top.grp_task_run_head_fu_11440.head_out_sm_U");
                                $fdisplay(fp, "Dependence_Channel_status FULL");
                            end
                        end
                    end
                    endcase
                end
                71 : begin // for proc 'vit_block_top_vit_block_top.grp_task_run_head_fu_11440.fixed_head_do_head_U0.fixed_head_matmul_U0.fixed_head_matmul_core_U0'
                    case(index2)
                    69: begin //  for dep proc 'vit_block_top_vit_block_top.grp_task_run_head_fu_11440.fixed_head_do_head_U0.fixed_head_layernorm_U0'
// for dep channel 'vit_block_top_vit_block_top.grp_task_run_head_fu_11440.fixed_head_do_head_U0.ln_sm_U' info is :
// blk sig is {~vit_block_top_vit_block_top_inst.grp_task_run_head_fu_11440.fixed_head_do_head_U0.fixed_head_matmul_U0.fixed_head_matmul_core_U0.grp_fixed_head_matmul_core_Pipeline_READ_LOOP_fu_50.ln_sm_blk_n data_FIFO}
                        if ((~grp_task_run_head_fu_11440.fixed_head_do_head_U0.fixed_head_matmul_U0.fixed_head_matmul_core_U0.grp_fixed_head_matmul_core_Pipeline_READ_LOOP_fu_50.ln_sm_blk_n)) begin
                            if (~grp_task_run_head_fu_11440.fixed_head_do_head_U0.ln_sm_U.if_empty_n) begin
                                $display("//      Blocked by empty input FIFO 'vit_block_top_vit_block_top.grp_task_run_head_fu_11440.fixed_head_do_head_U0.ln_sm_U' written by process 'vit_block_top_vit_block_top.grp_task_run_head_fu_11440.fixed_head_do_head_U0.fixed_head_layernorm_U0'");
                                $fdisplay(fp, "Dependence_Channel_path vit_block_top_vit_block_top.grp_task_run_head_fu_11440.fixed_head_do_head_U0.ln_sm_U");
                                $fdisplay(fp, "Dependence_Channel_status EMPTY");
                            end
                            else if (~grp_task_run_head_fu_11440.fixed_head_do_head_U0.ln_sm_U.if_full_n) begin
                                $display("//      Blocked by full output FIFO 'vit_block_top_vit_block_top.grp_task_run_head_fu_11440.fixed_head_do_head_U0.ln_sm_U' read by process 'vit_block_top_vit_block_top.grp_task_run_head_fu_11440.fixed_head_do_head_U0.fixed_head_layernorm_U0'");
                                $fdisplay(fp, "Dependence_Channel_path vit_block_top_vit_block_top.grp_task_run_head_fu_11440.fixed_head_do_head_U0.ln_sm_U");
                                $fdisplay(fp, "Dependence_Channel_status FULL");
                            end
                        end
                    end
                    72: begin //  for dep proc 'vit_block_top_vit_block_top.grp_task_run_head_fu_11440.fixed_head_do_head_U0.fixed_head_matmul_U0.do_adapt_3_U0'
// for dep channel 'vit_block_top_vit_block_top.grp_task_run_head_fu_11440.fixed_head_do_head_U0.fixed_head_matmul_U0.mac_sm_U' info is :
// blk sig is {~vit_block_top_vit_block_top_inst.grp_task_run_head_fu_11440.fixed_head_do_head_U0.fixed_head_matmul_U0.fixed_head_matmul_core_U0.grp_fixed_head_matmul_core_Pipeline_COT_LOOP_CIT_LOOP_fu_58.mac_sm_blk_n data_FIFO}
                        if ((~grp_task_run_head_fu_11440.fixed_head_do_head_U0.fixed_head_matmul_U0.fixed_head_matmul_core_U0.grp_fixed_head_matmul_core_Pipeline_COT_LOOP_CIT_LOOP_fu_58.mac_sm_blk_n)) begin
                            if (~grp_task_run_head_fu_11440.fixed_head_do_head_U0.fixed_head_matmul_U0.mac_sm_U.if_empty_n) begin
                                $display("//      Blocked by empty input FIFO 'vit_block_top_vit_block_top.grp_task_run_head_fu_11440.fixed_head_do_head_U0.fixed_head_matmul_U0.mac_sm_U' written by process 'vit_block_top_vit_block_top.grp_task_run_head_fu_11440.fixed_head_do_head_U0.fixed_head_matmul_U0.do_adapt_3_U0'");
                                $fdisplay(fp, "Dependence_Channel_path vit_block_top_vit_block_top.grp_task_run_head_fu_11440.fixed_head_do_head_U0.fixed_head_matmul_U0.mac_sm_U");
                                $fdisplay(fp, "Dependence_Channel_status EMPTY");
                            end
                            else if (~grp_task_run_head_fu_11440.fixed_head_do_head_U0.fixed_head_matmul_U0.mac_sm_U.if_full_n) begin
                                $display("//      Blocked by full output FIFO 'vit_block_top_vit_block_top.grp_task_run_head_fu_11440.fixed_head_do_head_U0.fixed_head_matmul_U0.mac_sm_U' read by process 'vit_block_top_vit_block_top.grp_task_run_head_fu_11440.fixed_head_do_head_U0.fixed_head_matmul_U0.do_adapt_3_U0'");
                                $fdisplay(fp, "Dependence_Channel_path vit_block_top_vit_block_top.grp_task_run_head_fu_11440.fixed_head_do_head_U0.fixed_head_matmul_U0.mac_sm_U");
                                $fdisplay(fp, "Dependence_Channel_status FULL");
                            end
                        end
// for dep channel 'vit_block_top_vit_block_top.grp_task_run_head_fu_11440.fixed_head_do_head_U0.fixed_head_matmul_U0.start_for_do_adapt_3_U0_U' info is :
// blk sig is {{~vit_block_top_vit_block_top_inst.grp_task_run_head_fu_11440.fixed_head_do_head_U0.fixed_head_matmul_U0.start_for_do_adapt_3_U0_U.if_full_n & vit_block_top_vit_block_top_inst.grp_task_run_head_fu_11440.fixed_head_do_head_U0.fixed_head_matmul_U0.fixed_head_matmul_core_U0.ap_start & ~vit_block_top_vit_block_top_inst.grp_task_run_head_fu_11440.fixed_head_do_head_U0.fixed_head_matmul_U0.fixed_head_matmul_core_U0.real_start & (trans_in_cnt_46 == trans_out_cnt_46) & ~vit_block_top_vit_block_top_inst.grp_task_run_head_fu_11440.fixed_head_do_head_U0.fixed_head_matmul_U0.start_for_do_adapt_3_U0_U.if_read} start_FIFO}
                        if ((~grp_task_run_head_fu_11440.fixed_head_do_head_U0.fixed_head_matmul_U0.start_for_do_adapt_3_U0_U.if_full_n & grp_task_run_head_fu_11440.fixed_head_do_head_U0.fixed_head_matmul_U0.fixed_head_matmul_core_U0.ap_start & ~grp_task_run_head_fu_11440.fixed_head_do_head_U0.fixed_head_matmul_U0.fixed_head_matmul_core_U0.real_start & (trans_in_cnt_46 == trans_out_cnt_46) & ~grp_task_run_head_fu_11440.fixed_head_do_head_U0.fixed_head_matmul_U0.start_for_do_adapt_3_U0_U.if_read)) begin
                            $display("//      Blocked by full output start propagation FIFO 'vit_block_top_vit_block_top.grp_task_run_head_fu_11440.fixed_head_do_head_U0.fixed_head_matmul_U0.start_for_do_adapt_3_U0_U' read by process 'vit_block_top_vit_block_top.grp_task_run_head_fu_11440.fixed_head_do_head_U0.fixed_head_matmul_U0.do_adapt_3_U0',");
                        end
                    end
                    endcase
                end
                72 : begin // for proc 'vit_block_top_vit_block_top.grp_task_run_head_fu_11440.fixed_head_do_head_U0.fixed_head_matmul_U0.do_adapt_3_U0'
                    case(index2)
                    71: begin //  for dep proc 'vit_block_top_vit_block_top.grp_task_run_head_fu_11440.fixed_head_do_head_U0.fixed_head_matmul_U0.fixed_head_matmul_core_U0'
// for dep channel 'vit_block_top_vit_block_top.grp_task_run_head_fu_11440.fixed_head_do_head_U0.fixed_head_matmul_U0.mac_sm_U' info is :
// blk sig is {~vit_block_top_vit_block_top_inst.grp_task_run_head_fu_11440.fixed_head_do_head_U0.fixed_head_matmul_U0.do_adapt_3_U0.mac_sm_blk_n data_FIFO}
                        if ((~grp_task_run_head_fu_11440.fixed_head_do_head_U0.fixed_head_matmul_U0.do_adapt_3_U0.mac_sm_blk_n)) begin
                            if (~grp_task_run_head_fu_11440.fixed_head_do_head_U0.fixed_head_matmul_U0.mac_sm_U.if_empty_n) begin
                                $display("//      Blocked by empty input FIFO 'vit_block_top_vit_block_top.grp_task_run_head_fu_11440.fixed_head_do_head_U0.fixed_head_matmul_U0.mac_sm_U' written by process 'vit_block_top_vit_block_top.grp_task_run_head_fu_11440.fixed_head_do_head_U0.fixed_head_matmul_U0.fixed_head_matmul_core_U0'");
                                $fdisplay(fp, "Dependence_Channel_path vit_block_top_vit_block_top.grp_task_run_head_fu_11440.fixed_head_do_head_U0.fixed_head_matmul_U0.mac_sm_U");
                                $fdisplay(fp, "Dependence_Channel_status EMPTY");
                            end
                            else if (~grp_task_run_head_fu_11440.fixed_head_do_head_U0.fixed_head_matmul_U0.mac_sm_U.if_full_n) begin
                                $display("//      Blocked by full output FIFO 'vit_block_top_vit_block_top.grp_task_run_head_fu_11440.fixed_head_do_head_U0.fixed_head_matmul_U0.mac_sm_U' read by process 'vit_block_top_vit_block_top.grp_task_run_head_fu_11440.fixed_head_do_head_U0.fixed_head_matmul_U0.fixed_head_matmul_core_U0'");
                                $fdisplay(fp, "Dependence_Channel_path vit_block_top_vit_block_top.grp_task_run_head_fu_11440.fixed_head_do_head_U0.fixed_head_matmul_U0.mac_sm_U");
                                $fdisplay(fp, "Dependence_Channel_status FULL");
                            end
                        end
// for dep channel 'vit_block_top_vit_block_top.grp_task_run_head_fu_11440.fixed_head_do_head_U0.fixed_head_matmul_U0.start_for_do_adapt_3_U0_U' info is :
// blk sig is {{~vit_block_top_vit_block_top_inst.grp_task_run_head_fu_11440.fixed_head_do_head_U0.fixed_head_matmul_U0.start_for_do_adapt_3_U0_U.if_empty_n & vit_block_top_vit_block_top_inst.grp_task_run_head_fu_11440.fixed_head_do_head_U0.fixed_head_matmul_U0.do_adapt_3_U0.ap_idle & ~vit_block_top_vit_block_top_inst.grp_task_run_head_fu_11440.fixed_head_do_head_U0.fixed_head_matmul_U0.start_for_do_adapt_3_U0_U.if_write} start_FIFO}
                        if ((~grp_task_run_head_fu_11440.fixed_head_do_head_U0.fixed_head_matmul_U0.start_for_do_adapt_3_U0_U.if_empty_n & grp_task_run_head_fu_11440.fixed_head_do_head_U0.fixed_head_matmul_U0.do_adapt_3_U0.ap_idle & ~grp_task_run_head_fu_11440.fixed_head_do_head_U0.fixed_head_matmul_U0.start_for_do_adapt_3_U0_U.if_write)) begin
                            $display("//      Blocked by missing 'ap_start' from start propagation FIFO 'vit_block_top_vit_block_top.grp_task_run_head_fu_11440.fixed_head_do_head_U0.fixed_head_matmul_U0.start_for_do_adapt_3_U0_U' written by process 'vit_block_top_vit_block_top.grp_task_run_head_fu_11440.fixed_head_do_head_U0.fixed_head_matmul_U0.fixed_head_matmul_core_U0',");
                        end
                    end
                    73: begin //  for dep proc 'vit_block_top_vit_block_top.grp_task_run_head_fu_11440.task_write_logits_U0'
// for dep channel 'vit_block_top_vit_block_top.grp_task_run_head_fu_11440.head_out_sm_U' info is :
// blk sig is {~vit_block_top_vit_block_top_inst.grp_task_run_head_fu_11440.fixed_head_do_head_U0.fixed_head_matmul_U0.do_adapt_3_U0.head_out_sm_blk_n data_FIFO}
                        if ((~grp_task_run_head_fu_11440.fixed_head_do_head_U0.fixed_head_matmul_U0.do_adapt_3_U0.head_out_sm_blk_n)) begin
                            if (~grp_task_run_head_fu_11440.head_out_sm_U.if_empty_n) begin
                                $display("//      Blocked by empty input FIFO 'vit_block_top_vit_block_top.grp_task_run_head_fu_11440.head_out_sm_U' written by process 'vit_block_top_vit_block_top.grp_task_run_head_fu_11440.task_write_logits_U0'");
                                $fdisplay(fp, "Dependence_Channel_path vit_block_top_vit_block_top.grp_task_run_head_fu_11440.head_out_sm_U");
                                $fdisplay(fp, "Dependence_Channel_status EMPTY");
                            end
                            else if (~grp_task_run_head_fu_11440.head_out_sm_U.if_full_n) begin
                                $display("//      Blocked by full output FIFO 'vit_block_top_vit_block_top.grp_task_run_head_fu_11440.head_out_sm_U' read by process 'vit_block_top_vit_block_top.grp_task_run_head_fu_11440.task_write_logits_U0'");
                                $fdisplay(fp, "Dependence_Channel_path vit_block_top_vit_block_top.grp_task_run_head_fu_11440.head_out_sm_U");
                                $fdisplay(fp, "Dependence_Channel_status FULL");
                            end
                        end
                    end
                    endcase
                end
                73 : begin // for proc 'vit_block_top_vit_block_top.grp_task_run_head_fu_11440.task_write_logits_U0'
                    case(index2)
                    68: begin //  for dep proc 'vit_block_top_vit_block_top.grp_task_run_head_fu_11440.fixed_head_do_head_U0'
// for dep channel 'vit_block_top_vit_block_top.grp_task_run_head_fu_11440.head_out_sm_U' info is :
// blk sig is {~vit_block_top_vit_block_top_inst.grp_task_run_head_fu_11440.task_write_logits_U0.head_out_sm_blk_n data_FIFO}
                        if ((~grp_task_run_head_fu_11440.task_write_logits_U0.head_out_sm_blk_n)) begin
                            if (~grp_task_run_head_fu_11440.head_out_sm_U.if_empty_n) begin
                                $display("//      Blocked by empty input FIFO 'vit_block_top_vit_block_top.grp_task_run_head_fu_11440.head_out_sm_U' written by process 'vit_block_top_vit_block_top.grp_task_run_head_fu_11440.fixed_head_do_head_U0'");
                                $fdisplay(fp, "Dependence_Channel_path vit_block_top_vit_block_top.grp_task_run_head_fu_11440.head_out_sm_U");
                                $fdisplay(fp, "Dependence_Channel_status EMPTY");
                            end
                            else if (~grp_task_run_head_fu_11440.head_out_sm_U.if_full_n) begin
                                $display("//      Blocked by full output FIFO 'vit_block_top_vit_block_top.grp_task_run_head_fu_11440.head_out_sm_U' read by process 'vit_block_top_vit_block_top.grp_task_run_head_fu_11440.fixed_head_do_head_U0'");
                                $fdisplay(fp, "Dependence_Channel_path vit_block_top_vit_block_top.grp_task_run_head_fu_11440.head_out_sm_U");
                                $fdisplay(fp, "Dependence_Channel_status FULL");
                            end
                        end
// for dep channel 'vit_block_top_vit_block_top.grp_task_run_head_fu_11440.start_for_task_write_logits_U0_U' info is :
// blk sig is {{~vit_block_top_vit_block_top_inst.grp_task_run_head_fu_11440.start_for_task_write_logits_U0_U.if_empty_n & vit_block_top_vit_block_top_inst.grp_task_run_head_fu_11440.task_write_logits_U0.ap_idle & ~vit_block_top_vit_block_top_inst.grp_task_run_head_fu_11440.start_for_task_write_logits_U0_U.if_write} start_FIFO}
                        if ((~grp_task_run_head_fu_11440.start_for_task_write_logits_U0_U.if_empty_n & grp_task_run_head_fu_11440.task_write_logits_U0.ap_idle & ~grp_task_run_head_fu_11440.start_for_task_write_logits_U0_U.if_write)) begin
                            $display("//      Blocked by missing 'ap_start' from start propagation FIFO 'vit_block_top_vit_block_top.grp_task_run_head_fu_11440.start_for_task_write_logits_U0_U' written by process 'vit_block_top_vit_block_top.grp_task_run_head_fu_11440.fixed_head_do_head_U0',");
                        end
                    end
                    70: begin //  for dep proc 'vit_block_top_vit_block_top.grp_task_run_head_fu_11440.fixed_head_do_head_U0.fixed_head_matmul_U0'
// for dep channel 'vit_block_top_vit_block_top.grp_task_run_head_fu_11440.head_out_sm_U' info is :
// blk sig is {~vit_block_top_vit_block_top_inst.grp_task_run_head_fu_11440.task_write_logits_U0.head_out_sm_blk_n data_FIFO}
                        if ((~grp_task_run_head_fu_11440.task_write_logits_U0.head_out_sm_blk_n)) begin
                            if (~grp_task_run_head_fu_11440.head_out_sm_U.if_empty_n) begin
                                $display("//      Blocked by empty input FIFO 'vit_block_top_vit_block_top.grp_task_run_head_fu_11440.head_out_sm_U' written by process 'vit_block_top_vit_block_top.grp_task_run_head_fu_11440.fixed_head_do_head_U0.fixed_head_matmul_U0'");
                                $fdisplay(fp, "Dependence_Channel_path vit_block_top_vit_block_top.grp_task_run_head_fu_11440.head_out_sm_U");
                                $fdisplay(fp, "Dependence_Channel_status EMPTY");
                            end
                            else if (~grp_task_run_head_fu_11440.head_out_sm_U.if_full_n) begin
                                $display("//      Blocked by full output FIFO 'vit_block_top_vit_block_top.grp_task_run_head_fu_11440.head_out_sm_U' read by process 'vit_block_top_vit_block_top.grp_task_run_head_fu_11440.fixed_head_do_head_U0.fixed_head_matmul_U0'");
                                $fdisplay(fp, "Dependence_Channel_path vit_block_top_vit_block_top.grp_task_run_head_fu_11440.head_out_sm_U");
                                $fdisplay(fp, "Dependence_Channel_status FULL");
                            end
                        end
                    end
                    72: begin //  for dep proc 'vit_block_top_vit_block_top.grp_task_run_head_fu_11440.fixed_head_do_head_U0.fixed_head_matmul_U0.do_adapt_3_U0'
// for dep channel 'vit_block_top_vit_block_top.grp_task_run_head_fu_11440.head_out_sm_U' info is :
// blk sig is {~vit_block_top_vit_block_top_inst.grp_task_run_head_fu_11440.task_write_logits_U0.head_out_sm_blk_n data_FIFO}
                        if ((~grp_task_run_head_fu_11440.task_write_logits_U0.head_out_sm_blk_n)) begin
                            if (~grp_task_run_head_fu_11440.head_out_sm_U.if_empty_n) begin
                                $display("//      Blocked by empty input FIFO 'vit_block_top_vit_block_top.grp_task_run_head_fu_11440.head_out_sm_U' written by process 'vit_block_top_vit_block_top.grp_task_run_head_fu_11440.fixed_head_do_head_U0.fixed_head_matmul_U0.do_adapt_3_U0'");
                                $fdisplay(fp, "Dependence_Channel_path vit_block_top_vit_block_top.grp_task_run_head_fu_11440.head_out_sm_U");
                                $fdisplay(fp, "Dependence_Channel_status EMPTY");
                            end
                            else if (~grp_task_run_head_fu_11440.head_out_sm_U.if_full_n) begin
                                $display("//      Blocked by full output FIFO 'vit_block_top_vit_block_top.grp_task_run_head_fu_11440.head_out_sm_U' read by process 'vit_block_top_vit_block_top.grp_task_run_head_fu_11440.fixed_head_do_head_U0.fixed_head_matmul_U0.do_adapt_3_U0'");
                                $fdisplay(fp, "Dependence_Channel_path vit_block_top_vit_block_top.grp_task_run_head_fu_11440.head_out_sm_U");
                                $fdisplay(fp, "Dependence_Channel_status FULL");
                            end
                        end
                    end
                    endcase
                end
            endcase
        end
    endtask

    // report
    initial begin : report_deadlock
        integer cycle_id;
        integer cycle_comp_id;
        integer record_time;
        wait (dl_reset == 1);
        cycle_id = 1;
        record_time = 0;
        while (1) begin
            @ (negedge dl_clock);
            case (CS_fsm)
                ST_DL_DETECTED: begin
                    cycle_comp_id = 2;
                    if (dl_detect_reg != dl_done_reg && stop_report_path == 1'b0) begin
                        if (dl_done_reg == 'b0) begin
                            print_dl_head;
                            record_time = $time;
                        end
                        print_cycle_start(proc_path(origin), cycle_id);
                        cycle_id = cycle_id + 1;
                    end
                    else begin
                        print_dl_end((cycle_id - 1),record_time);
                        @(negedge dl_clock);
                        @(negedge dl_clock);
                        $finish;
                    end
                end
                ST_DL_REPORT: begin
                    if ((|(dl_in_vec)) & ~(|(dl_in_vec & origin_reg)) & ~(|(reported_proc & dl_in_vec))) begin
                        print_cycle_chan_comp(dl_in_vec_reg, dl_in_vec);
                        print_cycle_proc_comp(proc_path(dl_in_vec), cycle_comp_id);
                        cycle_comp_id = cycle_comp_id + 1;
                    end
                    else begin
                        print_cycle_chan_comp(dl_in_vec_reg, dl_in_vec);
                    end
                end
            endcase
        end
    end
 
