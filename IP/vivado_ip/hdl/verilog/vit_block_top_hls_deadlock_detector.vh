
    wire dl_reset;
    wire dl_clock;
    assign dl_reset = ap_rst_n;
    assign dl_clock = ap_clk;
    wire [0:0] proc_0_data_FIFO_blk;
    wire [0:0] proc_0_data_PIPO_blk;
    wire [0:0] proc_0_start_FIFO_blk;
    wire [0:0] proc_0_TLF_FIFO_blk;
    wire [0:0] proc_0_input_sync_blk;
    wire [0:0] proc_0_output_sync_blk;
    wire [0:0] proc_dep_vld_vec_0;
    reg [0:0] proc_dep_vld_vec_0_reg;
    wire [0:0] in_chan_dep_vld_vec_0;
    wire [73:0] in_chan_dep_data_vec_0;
    wire [0:0] token_in_vec_0;
    wire [0:0] out_chan_dep_vld_vec_0;
    wire [73:0] out_chan_dep_data_0;
    wire [0:0] token_out_vec_0;
    wire dl_detect_out_0;
    wire dep_chan_vld_7_0;
    wire [73:0] dep_chan_data_7_0;
    wire token_7_0;
    wire [1:0] proc_1_data_FIFO_blk;
    wire [1:0] proc_1_data_PIPO_blk;
    wire [1:0] proc_1_start_FIFO_blk;
    wire [1:0] proc_1_TLF_FIFO_blk;
    wire [1:0] proc_1_input_sync_blk;
    wire [1:0] proc_1_output_sync_blk;
    wire [1:0] proc_dep_vld_vec_1;
    reg [1:0] proc_dep_vld_vec_1_reg;
    wire [1:0] in_chan_dep_vld_vec_1;
    wire [147:0] in_chan_dep_data_vec_1;
    wire [1:0] token_in_vec_1;
    wire [1:0] out_chan_dep_vld_vec_1;
    wire [73:0] out_chan_dep_data_1;
    wire [1:0] token_out_vec_1;
    wire dl_detect_out_1;
    wire dep_chan_vld_2_1;
    wire [73:0] dep_chan_data_2_1;
    wire token_2_1;
    wire dep_chan_vld_3_1;
    wire [73:0] dep_chan_data_3_1;
    wire token_3_1;
    wire [1:0] proc_2_data_FIFO_blk;
    wire [1:0] proc_2_data_PIPO_blk;
    wire [1:0] proc_2_start_FIFO_blk;
    wire [1:0] proc_2_TLF_FIFO_blk;
    wire [1:0] proc_2_input_sync_blk;
    wire [1:0] proc_2_output_sync_blk;
    wire [1:0] proc_dep_vld_vec_2;
    reg [1:0] proc_dep_vld_vec_2_reg;
    wire [1:0] in_chan_dep_vld_vec_2;
    wire [147:0] in_chan_dep_data_vec_2;
    wire [1:0] token_in_vec_2;
    wire [1:0] out_chan_dep_vld_vec_2;
    wire [73:0] out_chan_dep_data_2;
    wire [1:0] token_out_vec_2;
    wire dl_detect_out_2;
    wire dep_chan_vld_1_2;
    wire [73:0] dep_chan_data_1_2;
    wire token_1_2;
    wire dep_chan_vld_6_2;
    wire [73:0] dep_chan_data_6_2;
    wire token_6_2;
    wire [1:0] proc_3_data_FIFO_blk;
    wire [1:0] proc_3_data_PIPO_blk;
    wire [1:0] proc_3_start_FIFO_blk;
    wire [1:0] proc_3_TLF_FIFO_blk;
    wire [1:0] proc_3_input_sync_blk;
    wire [1:0] proc_3_output_sync_blk;
    wire [1:0] proc_dep_vld_vec_3;
    reg [1:0] proc_dep_vld_vec_3_reg;
    wire [1:0] in_chan_dep_vld_vec_3;
    wire [147:0] in_chan_dep_data_vec_3;
    wire [1:0] token_in_vec_3;
    wire [1:0] out_chan_dep_vld_vec_3;
    wire [73:0] out_chan_dep_data_3;
    wire [1:0] token_out_vec_3;
    wire dl_detect_out_3;
    wire dep_chan_vld_1_3;
    wire [73:0] dep_chan_data_1_3;
    wire token_1_3;
    wire dep_chan_vld_4_3;
    wire [73:0] dep_chan_data_4_3;
    wire token_4_3;
    wire [1:0] proc_4_data_FIFO_blk;
    wire [1:0] proc_4_data_PIPO_blk;
    wire [1:0] proc_4_start_FIFO_blk;
    wire [1:0] proc_4_TLF_FIFO_blk;
    wire [1:0] proc_4_input_sync_blk;
    wire [1:0] proc_4_output_sync_blk;
    wire [1:0] proc_dep_vld_vec_4;
    reg [1:0] proc_dep_vld_vec_4_reg;
    wire [1:0] in_chan_dep_vld_vec_4;
    wire [147:0] in_chan_dep_data_vec_4;
    wire [1:0] token_in_vec_4;
    wire [1:0] out_chan_dep_vld_vec_4;
    wire [73:0] out_chan_dep_data_4;
    wire [1:0] token_out_vec_4;
    wire dl_detect_out_4;
    wire dep_chan_vld_3_4;
    wire [73:0] dep_chan_data_3_4;
    wire token_3_4;
    wire dep_chan_vld_5_4;
    wire [73:0] dep_chan_data_5_4;
    wire token_5_4;
    wire [1:0] proc_5_data_FIFO_blk;
    wire [1:0] proc_5_data_PIPO_blk;
    wire [1:0] proc_5_start_FIFO_blk;
    wire [1:0] proc_5_TLF_FIFO_blk;
    wire [1:0] proc_5_input_sync_blk;
    wire [1:0] proc_5_output_sync_blk;
    wire [1:0] proc_dep_vld_vec_5;
    reg [1:0] proc_dep_vld_vec_5_reg;
    wire [1:0] in_chan_dep_vld_vec_5;
    wire [147:0] in_chan_dep_data_vec_5;
    wire [1:0] token_in_vec_5;
    wire [1:0] out_chan_dep_vld_vec_5;
    wire [73:0] out_chan_dep_data_5;
    wire [1:0] token_out_vec_5;
    wire dl_detect_out_5;
    wire dep_chan_vld_4_5;
    wire [73:0] dep_chan_data_4_5;
    wire token_4_5;
    wire dep_chan_vld_6_5;
    wire [73:0] dep_chan_data_6_5;
    wire token_6_5;
    wire [1:0] proc_6_data_FIFO_blk;
    wire [1:0] proc_6_data_PIPO_blk;
    wire [1:0] proc_6_start_FIFO_blk;
    wire [1:0] proc_6_TLF_FIFO_blk;
    wire [1:0] proc_6_input_sync_blk;
    wire [1:0] proc_6_output_sync_blk;
    wire [1:0] proc_dep_vld_vec_6;
    reg [1:0] proc_dep_vld_vec_6_reg;
    wire [1:0] in_chan_dep_vld_vec_6;
    wire [147:0] in_chan_dep_data_vec_6;
    wire [1:0] token_in_vec_6;
    wire [1:0] out_chan_dep_vld_vec_6;
    wire [73:0] out_chan_dep_data_6;
    wire [1:0] token_out_vec_6;
    wire dl_detect_out_6;
    wire dep_chan_vld_2_6;
    wire [73:0] dep_chan_data_2_6;
    wire token_2_6;
    wire dep_chan_vld_5_6;
    wire [73:0] dep_chan_data_5_6;
    wire token_5_6;
    wire [0:0] proc_7_data_FIFO_blk;
    wire [0:0] proc_7_data_PIPO_blk;
    wire [0:0] proc_7_start_FIFO_blk;
    wire [0:0] proc_7_TLF_FIFO_blk;
    wire [0:0] proc_7_input_sync_blk;
    wire [0:0] proc_7_output_sync_blk;
    wire [0:0] proc_dep_vld_vec_7;
    reg [0:0] proc_dep_vld_vec_7_reg;
    wire [0:0] in_chan_dep_vld_vec_7;
    wire [73:0] in_chan_dep_data_vec_7;
    wire [0:0] token_in_vec_7;
    wire [0:0] out_chan_dep_vld_vec_7;
    wire [73:0] out_chan_dep_data_7;
    wire [0:0] token_out_vec_7;
    wire dl_detect_out_7;
    wire dep_chan_vld_0_7;
    wire [73:0] dep_chan_data_0_7;
    wire token_0_7;
    wire [1:0] proc_8_data_FIFO_blk;
    wire [1:0] proc_8_data_PIPO_blk;
    wire [1:0] proc_8_start_FIFO_blk;
    wire [1:0] proc_8_TLF_FIFO_blk;
    wire [1:0] proc_8_input_sync_blk;
    wire [1:0] proc_8_output_sync_blk;
    wire [1:0] proc_dep_vld_vec_8;
    reg [1:0] proc_dep_vld_vec_8_reg;
    wire [1:0] in_chan_dep_vld_vec_8;
    wire [147:0] in_chan_dep_data_vec_8;
    wire [1:0] token_in_vec_8;
    wire [1:0] out_chan_dep_vld_vec_8;
    wire [73:0] out_chan_dep_data_8;
    wire [1:0] token_out_vec_8;
    wire dl_detect_out_8;
    wire dep_chan_vld_9_8;
    wire [73:0] dep_chan_data_9_8;
    wire token_9_8;
    wire dep_chan_vld_10_8;
    wire [73:0] dep_chan_data_10_8;
    wire token_10_8;
    wire [0:0] proc_9_data_FIFO_blk;
    wire [0:0] proc_9_data_PIPO_blk;
    wire [0:0] proc_9_start_FIFO_blk;
    wire [0:0] proc_9_TLF_FIFO_blk;
    wire [0:0] proc_9_input_sync_blk;
    wire [0:0] proc_9_output_sync_blk;
    wire [0:0] proc_dep_vld_vec_9;
    reg [0:0] proc_dep_vld_vec_9_reg;
    wire [3:0] in_chan_dep_vld_vec_9;
    wire [295:0] in_chan_dep_data_vec_9;
    wire [3:0] token_in_vec_9;
    wire [0:0] out_chan_dep_vld_vec_9;
    wire [73:0] out_chan_dep_data_9;
    wire [0:0] token_out_vec_9;
    wire dl_detect_out_9;
    wire dep_chan_vld_8_9;
    wire [73:0] dep_chan_data_8_9;
    wire token_8_9;
    wire dep_chan_vld_10_9;
    wire [73:0] dep_chan_data_10_9;
    wire token_10_9;
    wire dep_chan_vld_48_9;
    wire [73:0] dep_chan_data_48_9;
    wire token_48_9;
    wire dep_chan_vld_66_9;
    wire [73:0] dep_chan_data_66_9;
    wire token_66_9;
    wire [2:0] proc_10_data_FIFO_blk;
    wire [2:0] proc_10_data_PIPO_blk;
    wire [2:0] proc_10_start_FIFO_blk;
    wire [2:0] proc_10_TLF_FIFO_blk;
    wire [2:0] proc_10_input_sync_blk;
    wire [2:0] proc_10_output_sync_blk;
    wire [2:0] proc_dep_vld_vec_10;
    reg [2:0] proc_dep_vld_vec_10_reg;
    wire [1:0] in_chan_dep_vld_vec_10;
    wire [147:0] in_chan_dep_data_vec_10;
    wire [1:0] token_in_vec_10;
    wire [2:0] out_chan_dep_vld_vec_10;
    wire [73:0] out_chan_dep_data_10;
    wire [2:0] token_out_vec_10;
    wire dl_detect_out_10;
    wire dep_chan_vld_8_10;
    wire [73:0] dep_chan_data_8_10;
    wire token_8_10;
    wire dep_chan_vld_47_10;
    wire [73:0] dep_chan_data_47_10;
    wire token_47_10;
    wire [1:0] proc_11_data_FIFO_blk;
    wire [1:0] proc_11_data_PIPO_blk;
    wire [1:0] proc_11_start_FIFO_blk;
    wire [1:0] proc_11_TLF_FIFO_blk;
    wire [1:0] proc_11_input_sync_blk;
    wire [1:0] proc_11_output_sync_blk;
    wire [1:0] proc_dep_vld_vec_11;
    reg [1:0] proc_dep_vld_vec_11_reg;
    wire [1:0] in_chan_dep_vld_vec_11;
    wire [147:0] in_chan_dep_data_vec_11;
    wire [1:0] token_in_vec_11;
    wire [1:0] out_chan_dep_vld_vec_11;
    wire [73:0] out_chan_dep_data_11;
    wire [1:0] token_out_vec_11;
    wire dl_detect_out_11;
    wire dep_chan_vld_12_11;
    wire [73:0] dep_chan_data_12_11;
    wire token_12_11;
    wire dep_chan_vld_13_11;
    wire [73:0] dep_chan_data_13_11;
    wire token_13_11;
    wire [1:0] proc_12_data_FIFO_blk;
    wire [1:0] proc_12_data_PIPO_blk;
    wire [1:0] proc_12_start_FIFO_blk;
    wire [1:0] proc_12_TLF_FIFO_blk;
    wire [1:0] proc_12_input_sync_blk;
    wire [1:0] proc_12_output_sync_blk;
    wire [1:0] proc_dep_vld_vec_12;
    reg [1:0] proc_dep_vld_vec_12_reg;
    wire [1:0] in_chan_dep_vld_vec_12;
    wire [147:0] in_chan_dep_data_vec_12;
    wire [1:0] token_in_vec_12;
    wire [1:0] out_chan_dep_vld_vec_12;
    wire [73:0] out_chan_dep_data_12;
    wire [1:0] token_out_vec_12;
    wire dl_detect_out_12;
    wire dep_chan_vld_11_12;
    wire [73:0] dep_chan_data_11_12;
    wire token_11_12;
    wire dep_chan_vld_46_12;
    wire [73:0] dep_chan_data_46_12;
    wire token_46_12;
    wire [1:0] proc_13_data_FIFO_blk;
    wire [1:0] proc_13_data_PIPO_blk;
    wire [1:0] proc_13_start_FIFO_blk;
    wire [1:0] proc_13_TLF_FIFO_blk;
    wire [1:0] proc_13_input_sync_blk;
    wire [1:0] proc_13_output_sync_blk;
    wire [1:0] proc_dep_vld_vec_13;
    reg [1:0] proc_dep_vld_vec_13_reg;
    wire [1:0] in_chan_dep_vld_vec_13;
    wire [147:0] in_chan_dep_data_vec_13;
    wire [1:0] token_in_vec_13;
    wire [1:0] out_chan_dep_vld_vec_13;
    wire [73:0] out_chan_dep_data_13;
    wire [1:0] token_out_vec_13;
    wire dl_detect_out_13;
    wire dep_chan_vld_11_13;
    wire [73:0] dep_chan_data_11_13;
    wire token_11_13;
    wire dep_chan_vld_14_13;
    wire [73:0] dep_chan_data_14_13;
    wire token_14_13;
    wire [6:0] proc_14_data_FIFO_blk;
    wire [6:0] proc_14_data_PIPO_blk;
    wire [6:0] proc_14_start_FIFO_blk;
    wire [6:0] proc_14_TLF_FIFO_blk;
    wire [6:0] proc_14_input_sync_blk;
    wire [6:0] proc_14_output_sync_blk;
    wire [6:0] proc_dep_vld_vec_14;
    reg [6:0] proc_dep_vld_vec_14_reg;
    wire [6:0] in_chan_dep_vld_vec_14;
    wire [517:0] in_chan_dep_data_vec_14;
    wire [6:0] token_in_vec_14;
    wire [6:0] out_chan_dep_vld_vec_14;
    wire [73:0] out_chan_dep_data_14;
    wire [6:0] token_out_vec_14;
    wire dl_detect_out_14;
    wire dep_chan_vld_13_14;
    wire [73:0] dep_chan_data_13_14;
    wire token_13_14;
    wire dep_chan_vld_15_14;
    wire [73:0] dep_chan_data_15_14;
    wire token_15_14;
    wire dep_chan_vld_16_14;
    wire [73:0] dep_chan_data_16_14;
    wire token_16_14;
    wire dep_chan_vld_20_14;
    wire [73:0] dep_chan_data_20_14;
    wire token_20_14;
    wire dep_chan_vld_21_14;
    wire [73:0] dep_chan_data_21_14;
    wire token_21_14;
    wire dep_chan_vld_25_14;
    wire [73:0] dep_chan_data_25_14;
    wire token_25_14;
    wire dep_chan_vld_26_14;
    wire [73:0] dep_chan_data_26_14;
    wire token_26_14;
    wire [1:0] proc_15_data_FIFO_blk;
    wire [1:0] proc_15_data_PIPO_blk;
    wire [1:0] proc_15_start_FIFO_blk;
    wire [1:0] proc_15_TLF_FIFO_blk;
    wire [1:0] proc_15_input_sync_blk;
    wire [1:0] proc_15_output_sync_blk;
    wire [1:0] proc_dep_vld_vec_15;
    reg [1:0] proc_dep_vld_vec_15_reg;
    wire [1:0] in_chan_dep_vld_vec_15;
    wire [147:0] in_chan_dep_data_vec_15;
    wire [1:0] token_in_vec_15;
    wire [1:0] out_chan_dep_vld_vec_15;
    wire [73:0] out_chan_dep_data_15;
    wire [1:0] token_out_vec_15;
    wire dl_detect_out_15;
    wire dep_chan_vld_14_15;
    wire [73:0] dep_chan_data_14_15;
    wire token_14_15;
    wire dep_chan_vld_30_15;
    wire [73:0] dep_chan_data_30_15;
    wire token_30_15;
    wire [1:0] proc_16_data_FIFO_blk;
    wire [1:0] proc_16_data_PIPO_blk;
    wire [1:0] proc_16_start_FIFO_blk;
    wire [1:0] proc_16_TLF_FIFO_blk;
    wire [1:0] proc_16_input_sync_blk;
    wire [1:0] proc_16_output_sync_blk;
    wire [1:0] proc_dep_vld_vec_16;
    reg [1:0] proc_dep_vld_vec_16_reg;
    wire [1:0] in_chan_dep_vld_vec_16;
    wire [147:0] in_chan_dep_data_vec_16;
    wire [1:0] token_in_vec_16;
    wire [1:0] out_chan_dep_vld_vec_16;
    wire [73:0] out_chan_dep_data_16;
    wire [1:0] token_out_vec_16;
    wire dl_detect_out_16;
    wire dep_chan_vld_14_16;
    wire [73:0] dep_chan_data_14_16;
    wire token_14_16;
    wire dep_chan_vld_17_16;
    wire [73:0] dep_chan_data_17_16;
    wire token_17_16;
    wire [1:0] proc_17_data_FIFO_blk;
    wire [1:0] proc_17_data_PIPO_blk;
    wire [1:0] proc_17_start_FIFO_blk;
    wire [1:0] proc_17_TLF_FIFO_blk;
    wire [1:0] proc_17_input_sync_blk;
    wire [1:0] proc_17_output_sync_blk;
    wire [1:0] proc_dep_vld_vec_17;
    reg [1:0] proc_dep_vld_vec_17_reg;
    wire [1:0] in_chan_dep_vld_vec_17;
    wire [147:0] in_chan_dep_data_vec_17;
    wire [1:0] token_in_vec_17;
    wire [1:0] out_chan_dep_vld_vec_17;
    wire [73:0] out_chan_dep_data_17;
    wire [1:0] token_out_vec_17;
    wire dl_detect_out_17;
    wire dep_chan_vld_16_17;
    wire [73:0] dep_chan_data_16_17;
    wire token_16_17;
    wire dep_chan_vld_18_17;
    wire [73:0] dep_chan_data_18_17;
    wire token_18_17;
    wire [1:0] proc_18_data_FIFO_blk;
    wire [1:0] proc_18_data_PIPO_blk;
    wire [1:0] proc_18_start_FIFO_blk;
    wire [1:0] proc_18_TLF_FIFO_blk;
    wire [1:0] proc_18_input_sync_blk;
    wire [1:0] proc_18_output_sync_blk;
    wire [1:0] proc_dep_vld_vec_18;
    reg [1:0] proc_dep_vld_vec_18_reg;
    wire [1:0] in_chan_dep_vld_vec_18;
    wire [147:0] in_chan_dep_data_vec_18;
    wire [1:0] token_in_vec_18;
    wire [1:0] out_chan_dep_vld_vec_18;
    wire [73:0] out_chan_dep_data_18;
    wire [1:0] token_out_vec_18;
    wire dl_detect_out_18;
    wire dep_chan_vld_17_18;
    wire [73:0] dep_chan_data_17_18;
    wire token_17_18;
    wire dep_chan_vld_19_18;
    wire [73:0] dep_chan_data_19_18;
    wire token_19_18;
    wire [1:0] proc_19_data_FIFO_blk;
    wire [1:0] proc_19_data_PIPO_blk;
    wire [1:0] proc_19_start_FIFO_blk;
    wire [1:0] proc_19_TLF_FIFO_blk;
    wire [1:0] proc_19_input_sync_blk;
    wire [1:0] proc_19_output_sync_blk;
    wire [1:0] proc_dep_vld_vec_19;
    reg [1:0] proc_dep_vld_vec_19_reg;
    wire [1:0] in_chan_dep_vld_vec_19;
    wire [147:0] in_chan_dep_data_vec_19;
    wire [1:0] token_in_vec_19;
    wire [1:0] out_chan_dep_vld_vec_19;
    wire [73:0] out_chan_dep_data_19;
    wire [1:0] token_out_vec_19;
    wire dl_detect_out_19;
    wire dep_chan_vld_18_19;
    wire [73:0] dep_chan_data_18_19;
    wire token_18_19;
    wire dep_chan_vld_30_19;
    wire [73:0] dep_chan_data_30_19;
    wire token_30_19;
    wire [1:0] proc_20_data_FIFO_blk;
    wire [1:0] proc_20_data_PIPO_blk;
    wire [1:0] proc_20_start_FIFO_blk;
    wire [1:0] proc_20_TLF_FIFO_blk;
    wire [1:0] proc_20_input_sync_blk;
    wire [1:0] proc_20_output_sync_blk;
    wire [1:0] proc_dep_vld_vec_20;
    reg [1:0] proc_dep_vld_vec_20_reg;
    wire [1:0] in_chan_dep_vld_vec_20;
    wire [147:0] in_chan_dep_data_vec_20;
    wire [1:0] token_in_vec_20;
    wire [1:0] out_chan_dep_vld_vec_20;
    wire [73:0] out_chan_dep_data_20;
    wire [1:0] token_out_vec_20;
    wire dl_detect_out_20;
    wire dep_chan_vld_14_20;
    wire [73:0] dep_chan_data_14_20;
    wire token_14_20;
    wire dep_chan_vld_31_20;
    wire [73:0] dep_chan_data_31_20;
    wire token_31_20;
    wire [1:0] proc_21_data_FIFO_blk;
    wire [1:0] proc_21_data_PIPO_blk;
    wire [1:0] proc_21_start_FIFO_blk;
    wire [1:0] proc_21_TLF_FIFO_blk;
    wire [1:0] proc_21_input_sync_blk;
    wire [1:0] proc_21_output_sync_blk;
    wire [1:0] proc_dep_vld_vec_21;
    reg [1:0] proc_dep_vld_vec_21_reg;
    wire [1:0] in_chan_dep_vld_vec_21;
    wire [147:0] in_chan_dep_data_vec_21;
    wire [1:0] token_in_vec_21;
    wire [1:0] out_chan_dep_vld_vec_21;
    wire [73:0] out_chan_dep_data_21;
    wire [1:0] token_out_vec_21;
    wire dl_detect_out_21;
    wire dep_chan_vld_14_21;
    wire [73:0] dep_chan_data_14_21;
    wire token_14_21;
    wire dep_chan_vld_22_21;
    wire [73:0] dep_chan_data_22_21;
    wire token_22_21;
    wire [1:0] proc_22_data_FIFO_blk;
    wire [1:0] proc_22_data_PIPO_blk;
    wire [1:0] proc_22_start_FIFO_blk;
    wire [1:0] proc_22_TLF_FIFO_blk;
    wire [1:0] proc_22_input_sync_blk;
    wire [1:0] proc_22_output_sync_blk;
    wire [1:0] proc_dep_vld_vec_22;
    reg [1:0] proc_dep_vld_vec_22_reg;
    wire [1:0] in_chan_dep_vld_vec_22;
    wire [147:0] in_chan_dep_data_vec_22;
    wire [1:0] token_in_vec_22;
    wire [1:0] out_chan_dep_vld_vec_22;
    wire [73:0] out_chan_dep_data_22;
    wire [1:0] token_out_vec_22;
    wire dl_detect_out_22;
    wire dep_chan_vld_21_22;
    wire [73:0] dep_chan_data_21_22;
    wire token_21_22;
    wire dep_chan_vld_23_22;
    wire [73:0] dep_chan_data_23_22;
    wire token_23_22;
    wire [1:0] proc_23_data_FIFO_blk;
    wire [1:0] proc_23_data_PIPO_blk;
    wire [1:0] proc_23_start_FIFO_blk;
    wire [1:0] proc_23_TLF_FIFO_blk;
    wire [1:0] proc_23_input_sync_blk;
    wire [1:0] proc_23_output_sync_blk;
    wire [1:0] proc_dep_vld_vec_23;
    reg [1:0] proc_dep_vld_vec_23_reg;
    wire [1:0] in_chan_dep_vld_vec_23;
    wire [147:0] in_chan_dep_data_vec_23;
    wire [1:0] token_in_vec_23;
    wire [1:0] out_chan_dep_vld_vec_23;
    wire [73:0] out_chan_dep_data_23;
    wire [1:0] token_out_vec_23;
    wire dl_detect_out_23;
    wire dep_chan_vld_22_23;
    wire [73:0] dep_chan_data_22_23;
    wire token_22_23;
    wire dep_chan_vld_24_23;
    wire [73:0] dep_chan_data_24_23;
    wire token_24_23;
    wire [1:0] proc_24_data_FIFO_blk;
    wire [1:0] proc_24_data_PIPO_blk;
    wire [1:0] proc_24_start_FIFO_blk;
    wire [1:0] proc_24_TLF_FIFO_blk;
    wire [1:0] proc_24_input_sync_blk;
    wire [1:0] proc_24_output_sync_blk;
    wire [1:0] proc_dep_vld_vec_24;
    reg [1:0] proc_dep_vld_vec_24_reg;
    wire [1:0] in_chan_dep_vld_vec_24;
    wire [147:0] in_chan_dep_data_vec_24;
    wire [1:0] token_in_vec_24;
    wire [1:0] out_chan_dep_vld_vec_24;
    wire [73:0] out_chan_dep_data_24;
    wire [1:0] token_out_vec_24;
    wire dl_detect_out_24;
    wire dep_chan_vld_23_24;
    wire [73:0] dep_chan_data_23_24;
    wire token_23_24;
    wire dep_chan_vld_31_24;
    wire [73:0] dep_chan_data_31_24;
    wire token_31_24;
    wire [1:0] proc_25_data_FIFO_blk;
    wire [1:0] proc_25_data_PIPO_blk;
    wire [1:0] proc_25_start_FIFO_blk;
    wire [1:0] proc_25_TLF_FIFO_blk;
    wire [1:0] proc_25_input_sync_blk;
    wire [1:0] proc_25_output_sync_blk;
    wire [1:0] proc_dep_vld_vec_25;
    reg [1:0] proc_dep_vld_vec_25_reg;
    wire [1:0] in_chan_dep_vld_vec_25;
    wire [147:0] in_chan_dep_data_vec_25;
    wire [1:0] token_in_vec_25;
    wire [1:0] out_chan_dep_vld_vec_25;
    wire [73:0] out_chan_dep_data_25;
    wire [1:0] token_out_vec_25;
    wire dl_detect_out_25;
    wire dep_chan_vld_14_25;
    wire [73:0] dep_chan_data_14_25;
    wire token_14_25;
    wire dep_chan_vld_32_25;
    wire [73:0] dep_chan_data_32_25;
    wire token_32_25;
    wire [1:0] proc_26_data_FIFO_blk;
    wire [1:0] proc_26_data_PIPO_blk;
    wire [1:0] proc_26_start_FIFO_blk;
    wire [1:0] proc_26_TLF_FIFO_blk;
    wire [1:0] proc_26_input_sync_blk;
    wire [1:0] proc_26_output_sync_blk;
    wire [1:0] proc_dep_vld_vec_26;
    reg [1:0] proc_dep_vld_vec_26_reg;
    wire [1:0] in_chan_dep_vld_vec_26;
    wire [147:0] in_chan_dep_data_vec_26;
    wire [1:0] token_in_vec_26;
    wire [1:0] out_chan_dep_vld_vec_26;
    wire [73:0] out_chan_dep_data_26;
    wire [1:0] token_out_vec_26;
    wire dl_detect_out_26;
    wire dep_chan_vld_14_26;
    wire [73:0] dep_chan_data_14_26;
    wire token_14_26;
    wire dep_chan_vld_27_26;
    wire [73:0] dep_chan_data_27_26;
    wire token_27_26;
    wire [1:0] proc_27_data_FIFO_blk;
    wire [1:0] proc_27_data_PIPO_blk;
    wire [1:0] proc_27_start_FIFO_blk;
    wire [1:0] proc_27_TLF_FIFO_blk;
    wire [1:0] proc_27_input_sync_blk;
    wire [1:0] proc_27_output_sync_blk;
    wire [1:0] proc_dep_vld_vec_27;
    reg [1:0] proc_dep_vld_vec_27_reg;
    wire [1:0] in_chan_dep_vld_vec_27;
    wire [147:0] in_chan_dep_data_vec_27;
    wire [1:0] token_in_vec_27;
    wire [1:0] out_chan_dep_vld_vec_27;
    wire [73:0] out_chan_dep_data_27;
    wire [1:0] token_out_vec_27;
    wire dl_detect_out_27;
    wire dep_chan_vld_26_27;
    wire [73:0] dep_chan_data_26_27;
    wire token_26_27;
    wire dep_chan_vld_28_27;
    wire [73:0] dep_chan_data_28_27;
    wire token_28_27;
    wire [1:0] proc_28_data_FIFO_blk;
    wire [1:0] proc_28_data_PIPO_blk;
    wire [1:0] proc_28_start_FIFO_blk;
    wire [1:0] proc_28_TLF_FIFO_blk;
    wire [1:0] proc_28_input_sync_blk;
    wire [1:0] proc_28_output_sync_blk;
    wire [1:0] proc_dep_vld_vec_28;
    reg [1:0] proc_dep_vld_vec_28_reg;
    wire [1:0] in_chan_dep_vld_vec_28;
    wire [147:0] in_chan_dep_data_vec_28;
    wire [1:0] token_in_vec_28;
    wire [1:0] out_chan_dep_vld_vec_28;
    wire [73:0] out_chan_dep_data_28;
    wire [1:0] token_out_vec_28;
    wire dl_detect_out_28;
    wire dep_chan_vld_27_28;
    wire [73:0] dep_chan_data_27_28;
    wire token_27_28;
    wire dep_chan_vld_29_28;
    wire [73:0] dep_chan_data_29_28;
    wire token_29_28;
    wire [1:0] proc_29_data_FIFO_blk;
    wire [1:0] proc_29_data_PIPO_blk;
    wire [1:0] proc_29_start_FIFO_blk;
    wire [1:0] proc_29_TLF_FIFO_blk;
    wire [1:0] proc_29_input_sync_blk;
    wire [1:0] proc_29_output_sync_blk;
    wire [1:0] proc_dep_vld_vec_29;
    reg [1:0] proc_dep_vld_vec_29_reg;
    wire [1:0] in_chan_dep_vld_vec_29;
    wire [147:0] in_chan_dep_data_vec_29;
    wire [1:0] token_in_vec_29;
    wire [1:0] out_chan_dep_vld_vec_29;
    wire [73:0] out_chan_dep_data_29;
    wire [1:0] token_out_vec_29;
    wire dl_detect_out_29;
    wire dep_chan_vld_28_29;
    wire [73:0] dep_chan_data_28_29;
    wire token_28_29;
    wire dep_chan_vld_32_29;
    wire [73:0] dep_chan_data_32_29;
    wire token_32_29;
    wire [2:0] proc_30_data_FIFO_blk;
    wire [2:0] proc_30_data_PIPO_blk;
    wire [2:0] proc_30_start_FIFO_blk;
    wire [2:0] proc_30_TLF_FIFO_blk;
    wire [2:0] proc_30_input_sync_blk;
    wire [2:0] proc_30_output_sync_blk;
    wire [2:0] proc_dep_vld_vec_30;
    reg [2:0] proc_dep_vld_vec_30_reg;
    wire [2:0] in_chan_dep_vld_vec_30;
    wire [221:0] in_chan_dep_data_vec_30;
    wire [2:0] token_in_vec_30;
    wire [2:0] out_chan_dep_vld_vec_30;
    wire [73:0] out_chan_dep_data_30;
    wire [2:0] token_out_vec_30;
    wire dl_detect_out_30;
    wire dep_chan_vld_15_30;
    wire [73:0] dep_chan_data_15_30;
    wire token_15_30;
    wire dep_chan_vld_19_30;
    wire [73:0] dep_chan_data_19_30;
    wire token_19_30;
    wire dep_chan_vld_33_30;
    wire [73:0] dep_chan_data_33_30;
    wire token_33_30;
    wire [2:0] proc_31_data_FIFO_blk;
    wire [2:0] proc_31_data_PIPO_blk;
    wire [2:0] proc_31_start_FIFO_blk;
    wire [2:0] proc_31_TLF_FIFO_blk;
    wire [2:0] proc_31_input_sync_blk;
    wire [2:0] proc_31_output_sync_blk;
    wire [2:0] proc_dep_vld_vec_31;
    reg [2:0] proc_dep_vld_vec_31_reg;
    wire [2:0] in_chan_dep_vld_vec_31;
    wire [221:0] in_chan_dep_data_vec_31;
    wire [2:0] token_in_vec_31;
    wire [2:0] out_chan_dep_vld_vec_31;
    wire [73:0] out_chan_dep_data_31;
    wire [2:0] token_out_vec_31;
    wire dl_detect_out_31;
    wire dep_chan_vld_20_31;
    wire [73:0] dep_chan_data_20_31;
    wire token_20_31;
    wire dep_chan_vld_24_31;
    wire [73:0] dep_chan_data_24_31;
    wire token_24_31;
    wire dep_chan_vld_34_31;
    wire [73:0] dep_chan_data_34_31;
    wire token_34_31;
    wire [2:0] proc_32_data_FIFO_blk;
    wire [2:0] proc_32_data_PIPO_blk;
    wire [2:0] proc_32_start_FIFO_blk;
    wire [2:0] proc_32_TLF_FIFO_blk;
    wire [2:0] proc_32_input_sync_blk;
    wire [2:0] proc_32_output_sync_blk;
    wire [2:0] proc_dep_vld_vec_32;
    reg [2:0] proc_dep_vld_vec_32_reg;
    wire [2:0] in_chan_dep_vld_vec_32;
    wire [221:0] in_chan_dep_data_vec_32;
    wire [2:0] token_in_vec_32;
    wire [2:0] out_chan_dep_vld_vec_32;
    wire [73:0] out_chan_dep_data_32;
    wire [2:0] token_out_vec_32;
    wire dl_detect_out_32;
    wire dep_chan_vld_25_32;
    wire [73:0] dep_chan_data_25_32;
    wire token_25_32;
    wire dep_chan_vld_29_32;
    wire [73:0] dep_chan_data_29_32;
    wire token_29_32;
    wire dep_chan_vld_35_32;
    wire [73:0] dep_chan_data_35_32;
    wire token_35_32;
    wire [3:0] proc_33_data_FIFO_blk;
    wire [3:0] proc_33_data_PIPO_blk;
    wire [3:0] proc_33_start_FIFO_blk;
    wire [3:0] proc_33_TLF_FIFO_blk;
    wire [3:0] proc_33_input_sync_blk;
    wire [3:0] proc_33_output_sync_blk;
    wire [3:0] proc_dep_vld_vec_33;
    reg [3:0] proc_dep_vld_vec_33_reg;
    wire [3:0] in_chan_dep_vld_vec_33;
    wire [295:0] in_chan_dep_data_vec_33;
    wire [3:0] token_in_vec_33;
    wire [3:0] out_chan_dep_vld_vec_33;
    wire [73:0] out_chan_dep_data_33;
    wire [3:0] token_out_vec_33;
    wire dl_detect_out_33;
    wire dep_chan_vld_30_33;
    wire [73:0] dep_chan_data_30_33;
    wire token_30_33;
    wire dep_chan_vld_36_33;
    wire [73:0] dep_chan_data_36_33;
    wire token_36_33;
    wire dep_chan_vld_37_33;
    wire [73:0] dep_chan_data_37_33;
    wire token_37_33;
    wire dep_chan_vld_38_33;
    wire [73:0] dep_chan_data_38_33;
    wire token_38_33;
    wire [3:0] proc_34_data_FIFO_blk;
    wire [3:0] proc_34_data_PIPO_blk;
    wire [3:0] proc_34_start_FIFO_blk;
    wire [3:0] proc_34_TLF_FIFO_blk;
    wire [3:0] proc_34_input_sync_blk;
    wire [3:0] proc_34_output_sync_blk;
    wire [3:0] proc_dep_vld_vec_34;
    reg [3:0] proc_dep_vld_vec_34_reg;
    wire [3:0] in_chan_dep_vld_vec_34;
    wire [295:0] in_chan_dep_data_vec_34;
    wire [3:0] token_in_vec_34;
    wire [3:0] out_chan_dep_vld_vec_34;
    wire [73:0] out_chan_dep_data_34;
    wire [3:0] token_out_vec_34;
    wire dl_detect_out_34;
    wire dep_chan_vld_31_34;
    wire [73:0] dep_chan_data_31_34;
    wire token_31_34;
    wire dep_chan_vld_36_34;
    wire [73:0] dep_chan_data_36_34;
    wire token_36_34;
    wire dep_chan_vld_37_34;
    wire [73:0] dep_chan_data_37_34;
    wire token_37_34;
    wire dep_chan_vld_38_34;
    wire [73:0] dep_chan_data_38_34;
    wire token_38_34;
    wire [3:0] proc_35_data_FIFO_blk;
    wire [3:0] proc_35_data_PIPO_blk;
    wire [3:0] proc_35_start_FIFO_blk;
    wire [3:0] proc_35_TLF_FIFO_blk;
    wire [3:0] proc_35_input_sync_blk;
    wire [3:0] proc_35_output_sync_blk;
    wire [3:0] proc_dep_vld_vec_35;
    reg [3:0] proc_dep_vld_vec_35_reg;
    wire [3:0] in_chan_dep_vld_vec_35;
    wire [295:0] in_chan_dep_data_vec_35;
    wire [3:0] token_in_vec_35;
    wire [3:0] out_chan_dep_vld_vec_35;
    wire [73:0] out_chan_dep_data_35;
    wire [3:0] token_out_vec_35;
    wire dl_detect_out_35;
    wire dep_chan_vld_32_35;
    wire [73:0] dep_chan_data_32_35;
    wire token_32_35;
    wire dep_chan_vld_36_35;
    wire [73:0] dep_chan_data_36_35;
    wire token_36_35;
    wire dep_chan_vld_37_35;
    wire [73:0] dep_chan_data_37_35;
    wire token_37_35;
    wire dep_chan_vld_38_35;
    wire [73:0] dep_chan_data_38_35;
    wire token_38_35;
    wire [3:0] proc_36_data_FIFO_blk;
    wire [3:0] proc_36_data_PIPO_blk;
    wire [3:0] proc_36_start_FIFO_blk;
    wire [3:0] proc_36_TLF_FIFO_blk;
    wire [3:0] proc_36_input_sync_blk;
    wire [3:0] proc_36_output_sync_blk;
    wire [3:0] proc_dep_vld_vec_36;
    reg [3:0] proc_dep_vld_vec_36_reg;
    wire [3:0] in_chan_dep_vld_vec_36;
    wire [295:0] in_chan_dep_data_vec_36;
    wire [3:0] token_in_vec_36;
    wire [3:0] out_chan_dep_vld_vec_36;
    wire [73:0] out_chan_dep_data_36;
    wire [3:0] token_out_vec_36;
    wire dl_detect_out_36;
    wire dep_chan_vld_33_36;
    wire [73:0] dep_chan_data_33_36;
    wire token_33_36;
    wire dep_chan_vld_34_36;
    wire [73:0] dep_chan_data_34_36;
    wire token_34_36;
    wire dep_chan_vld_35_36;
    wire [73:0] dep_chan_data_35_36;
    wire token_35_36;
    wire dep_chan_vld_39_36;
    wire [73:0] dep_chan_data_39_36;
    wire token_39_36;
    wire [3:0] proc_37_data_FIFO_blk;
    wire [3:0] proc_37_data_PIPO_blk;
    wire [3:0] proc_37_start_FIFO_blk;
    wire [3:0] proc_37_TLF_FIFO_blk;
    wire [3:0] proc_37_input_sync_blk;
    wire [3:0] proc_37_output_sync_blk;
    wire [3:0] proc_dep_vld_vec_37;
    reg [3:0] proc_dep_vld_vec_37_reg;
    wire [3:0] in_chan_dep_vld_vec_37;
    wire [295:0] in_chan_dep_data_vec_37;
    wire [3:0] token_in_vec_37;
    wire [3:0] out_chan_dep_vld_vec_37;
    wire [73:0] out_chan_dep_data_37;
    wire [3:0] token_out_vec_37;
    wire dl_detect_out_37;
    wire dep_chan_vld_33_37;
    wire [73:0] dep_chan_data_33_37;
    wire token_33_37;
    wire dep_chan_vld_34_37;
    wire [73:0] dep_chan_data_34_37;
    wire token_34_37;
    wire dep_chan_vld_35_37;
    wire [73:0] dep_chan_data_35_37;
    wire token_35_37;
    wire dep_chan_vld_39_37;
    wire [73:0] dep_chan_data_39_37;
    wire token_39_37;
    wire [3:0] proc_38_data_FIFO_blk;
    wire [3:0] proc_38_data_PIPO_blk;
    wire [3:0] proc_38_start_FIFO_blk;
    wire [3:0] proc_38_TLF_FIFO_blk;
    wire [3:0] proc_38_input_sync_blk;
    wire [3:0] proc_38_output_sync_blk;
    wire [3:0] proc_dep_vld_vec_38;
    reg [3:0] proc_dep_vld_vec_38_reg;
    wire [3:0] in_chan_dep_vld_vec_38;
    wire [295:0] in_chan_dep_data_vec_38;
    wire [3:0] token_in_vec_38;
    wire [3:0] out_chan_dep_vld_vec_38;
    wire [73:0] out_chan_dep_data_38;
    wire [3:0] token_out_vec_38;
    wire dl_detect_out_38;
    wire dep_chan_vld_33_38;
    wire [73:0] dep_chan_data_33_38;
    wire token_33_38;
    wire dep_chan_vld_34_38;
    wire [73:0] dep_chan_data_34_38;
    wire token_34_38;
    wire dep_chan_vld_35_38;
    wire [73:0] dep_chan_data_35_38;
    wire token_35_38;
    wire dep_chan_vld_39_38;
    wire [73:0] dep_chan_data_39_38;
    wire token_39_38;
    wire [3:0] proc_39_data_FIFO_blk;
    wire [3:0] proc_39_data_PIPO_blk;
    wire [3:0] proc_39_start_FIFO_blk;
    wire [3:0] proc_39_TLF_FIFO_blk;
    wire [3:0] proc_39_input_sync_blk;
    wire [3:0] proc_39_output_sync_blk;
    wire [3:0] proc_dep_vld_vec_39;
    reg [3:0] proc_dep_vld_vec_39_reg;
    wire [3:0] in_chan_dep_vld_vec_39;
    wire [295:0] in_chan_dep_data_vec_39;
    wire [3:0] token_in_vec_39;
    wire [3:0] out_chan_dep_vld_vec_39;
    wire [73:0] out_chan_dep_data_39;
    wire [3:0] token_out_vec_39;
    wire dl_detect_out_39;
    wire dep_chan_vld_36_39;
    wire [73:0] dep_chan_data_36_39;
    wire token_36_39;
    wire dep_chan_vld_37_39;
    wire [73:0] dep_chan_data_37_39;
    wire token_37_39;
    wire dep_chan_vld_38_39;
    wire [73:0] dep_chan_data_38_39;
    wire token_38_39;
    wire dep_chan_vld_40_39;
    wire [73:0] dep_chan_data_40_39;
    wire token_40_39;
    wire [2:0] proc_40_data_FIFO_blk;
    wire [2:0] proc_40_data_PIPO_blk;
    wire [2:0] proc_40_start_FIFO_blk;
    wire [2:0] proc_40_TLF_FIFO_blk;
    wire [2:0] proc_40_input_sync_blk;
    wire [2:0] proc_40_output_sync_blk;
    wire [2:0] proc_dep_vld_vec_40;
    reg [2:0] proc_dep_vld_vec_40_reg;
    wire [2:0] in_chan_dep_vld_vec_40;
    wire [221:0] in_chan_dep_data_vec_40;
    wire [2:0] token_in_vec_40;
    wire [2:0] out_chan_dep_vld_vec_40;
    wire [73:0] out_chan_dep_data_40;
    wire [2:0] token_out_vec_40;
    wire dl_detect_out_40;
    wire dep_chan_vld_39_40;
    wire [73:0] dep_chan_data_39_40;
    wire token_39_40;
    wire dep_chan_vld_41_40;
    wire [73:0] dep_chan_data_41_40;
    wire token_41_40;
    wire dep_chan_vld_42_40;
    wire [73:0] dep_chan_data_42_40;
    wire token_42_40;
    wire [1:0] proc_41_data_FIFO_blk;
    wire [1:0] proc_41_data_PIPO_blk;
    wire [1:0] proc_41_start_FIFO_blk;
    wire [1:0] proc_41_TLF_FIFO_blk;
    wire [1:0] proc_41_input_sync_blk;
    wire [1:0] proc_41_output_sync_blk;
    wire [1:0] proc_dep_vld_vec_41;
    reg [1:0] proc_dep_vld_vec_41_reg;
    wire [1:0] in_chan_dep_vld_vec_41;
    wire [147:0] in_chan_dep_data_vec_41;
    wire [1:0] token_in_vec_41;
    wire [1:0] out_chan_dep_vld_vec_41;
    wire [73:0] out_chan_dep_data_41;
    wire [1:0] token_out_vec_41;
    wire dl_detect_out_41;
    wire dep_chan_vld_40_41;
    wire [73:0] dep_chan_data_40_41;
    wire token_40_41;
    wire dep_chan_vld_46_41;
    wire [73:0] dep_chan_data_46_41;
    wire token_46_41;
    wire [1:0] proc_42_data_FIFO_blk;
    wire [1:0] proc_42_data_PIPO_blk;
    wire [1:0] proc_42_start_FIFO_blk;
    wire [1:0] proc_42_TLF_FIFO_blk;
    wire [1:0] proc_42_input_sync_blk;
    wire [1:0] proc_42_output_sync_blk;
    wire [1:0] proc_dep_vld_vec_42;
    reg [1:0] proc_dep_vld_vec_42_reg;
    wire [1:0] in_chan_dep_vld_vec_42;
    wire [147:0] in_chan_dep_data_vec_42;
    wire [1:0] token_in_vec_42;
    wire [1:0] out_chan_dep_vld_vec_42;
    wire [73:0] out_chan_dep_data_42;
    wire [1:0] token_out_vec_42;
    wire dl_detect_out_42;
    wire dep_chan_vld_40_42;
    wire [73:0] dep_chan_data_40_42;
    wire token_40_42;
    wire dep_chan_vld_43_42;
    wire [73:0] dep_chan_data_43_42;
    wire token_43_42;
    wire [1:0] proc_43_data_FIFO_blk;
    wire [1:0] proc_43_data_PIPO_blk;
    wire [1:0] proc_43_start_FIFO_blk;
    wire [1:0] proc_43_TLF_FIFO_blk;
    wire [1:0] proc_43_input_sync_blk;
    wire [1:0] proc_43_output_sync_blk;
    wire [1:0] proc_dep_vld_vec_43;
    reg [1:0] proc_dep_vld_vec_43_reg;
    wire [1:0] in_chan_dep_vld_vec_43;
    wire [147:0] in_chan_dep_data_vec_43;
    wire [1:0] token_in_vec_43;
    wire [1:0] out_chan_dep_vld_vec_43;
    wire [73:0] out_chan_dep_data_43;
    wire [1:0] token_out_vec_43;
    wire dl_detect_out_43;
    wire dep_chan_vld_42_43;
    wire [73:0] dep_chan_data_42_43;
    wire token_42_43;
    wire dep_chan_vld_44_43;
    wire [73:0] dep_chan_data_44_43;
    wire token_44_43;
    wire [1:0] proc_44_data_FIFO_blk;
    wire [1:0] proc_44_data_PIPO_blk;
    wire [1:0] proc_44_start_FIFO_blk;
    wire [1:0] proc_44_TLF_FIFO_blk;
    wire [1:0] proc_44_input_sync_blk;
    wire [1:0] proc_44_output_sync_blk;
    wire [1:0] proc_dep_vld_vec_44;
    reg [1:0] proc_dep_vld_vec_44_reg;
    wire [1:0] in_chan_dep_vld_vec_44;
    wire [147:0] in_chan_dep_data_vec_44;
    wire [1:0] token_in_vec_44;
    wire [1:0] out_chan_dep_vld_vec_44;
    wire [73:0] out_chan_dep_data_44;
    wire [1:0] token_out_vec_44;
    wire dl_detect_out_44;
    wire dep_chan_vld_43_44;
    wire [73:0] dep_chan_data_43_44;
    wire token_43_44;
    wire dep_chan_vld_45_44;
    wire [73:0] dep_chan_data_45_44;
    wire token_45_44;
    wire [1:0] proc_45_data_FIFO_blk;
    wire [1:0] proc_45_data_PIPO_blk;
    wire [1:0] proc_45_start_FIFO_blk;
    wire [1:0] proc_45_TLF_FIFO_blk;
    wire [1:0] proc_45_input_sync_blk;
    wire [1:0] proc_45_output_sync_blk;
    wire [1:0] proc_dep_vld_vec_45;
    reg [1:0] proc_dep_vld_vec_45_reg;
    wire [1:0] in_chan_dep_vld_vec_45;
    wire [147:0] in_chan_dep_data_vec_45;
    wire [1:0] token_in_vec_45;
    wire [1:0] out_chan_dep_vld_vec_45;
    wire [73:0] out_chan_dep_data_45;
    wire [1:0] token_out_vec_45;
    wire dl_detect_out_45;
    wire dep_chan_vld_44_45;
    wire [73:0] dep_chan_data_44_45;
    wire token_44_45;
    wire dep_chan_vld_46_45;
    wire [73:0] dep_chan_data_46_45;
    wire token_46_45;
    wire [2:0] proc_46_data_FIFO_blk;
    wire [2:0] proc_46_data_PIPO_blk;
    wire [2:0] proc_46_start_FIFO_blk;
    wire [2:0] proc_46_TLF_FIFO_blk;
    wire [2:0] proc_46_input_sync_blk;
    wire [2:0] proc_46_output_sync_blk;
    wire [2:0] proc_dep_vld_vec_46;
    reg [2:0] proc_dep_vld_vec_46_reg;
    wire [2:0] in_chan_dep_vld_vec_46;
    wire [221:0] in_chan_dep_data_vec_46;
    wire [2:0] token_in_vec_46;
    wire [2:0] out_chan_dep_vld_vec_46;
    wire [73:0] out_chan_dep_data_46;
    wire [2:0] token_out_vec_46;
    wire dl_detect_out_46;
    wire dep_chan_vld_12_46;
    wire [73:0] dep_chan_data_12_46;
    wire token_12_46;
    wire dep_chan_vld_41_46;
    wire [73:0] dep_chan_data_41_46;
    wire token_41_46;
    wire dep_chan_vld_45_46;
    wire [73:0] dep_chan_data_45_46;
    wire token_45_46;
    wire [1:0] proc_47_data_FIFO_blk;
    wire [1:0] proc_47_data_PIPO_blk;
    wire [1:0] proc_47_start_FIFO_blk;
    wire [1:0] proc_47_TLF_FIFO_blk;
    wire [1:0] proc_47_input_sync_blk;
    wire [1:0] proc_47_output_sync_blk;
    wire [1:0] proc_dep_vld_vec_47;
    reg [1:0] proc_dep_vld_vec_47_reg;
    wire [1:0] in_chan_dep_vld_vec_47;
    wire [147:0] in_chan_dep_data_vec_47;
    wire [1:0] token_in_vec_47;
    wire [1:0] out_chan_dep_vld_vec_47;
    wire [73:0] out_chan_dep_data_47;
    wire [1:0] token_out_vec_47;
    wire dl_detect_out_47;
    wire dep_chan_vld_10_47;
    wire [73:0] dep_chan_data_10_47;
    wire token_10_47;
    wire dep_chan_vld_48_47;
    wire [73:0] dep_chan_data_48_47;
    wire token_48_47;
    wire [2:0] proc_48_data_FIFO_blk;
    wire [2:0] proc_48_data_PIPO_blk;
    wire [2:0] proc_48_start_FIFO_blk;
    wire [2:0] proc_48_TLF_FIFO_blk;
    wire [2:0] proc_48_input_sync_blk;
    wire [2:0] proc_48_output_sync_blk;
    wire [2:0] proc_dep_vld_vec_48;
    reg [2:0] proc_dep_vld_vec_48_reg;
    wire [1:0] in_chan_dep_vld_vec_48;
    wire [147:0] in_chan_dep_data_vec_48;
    wire [1:0] token_in_vec_48;
    wire [2:0] out_chan_dep_vld_vec_48;
    wire [73:0] out_chan_dep_data_48;
    wire [2:0] token_out_vec_48;
    wire dl_detect_out_48;
    wire dep_chan_vld_47_48;
    wire [73:0] dep_chan_data_47_48;
    wire token_47_48;
    wire dep_chan_vld_65_48;
    wire [73:0] dep_chan_data_65_48;
    wire token_65_48;
    wire [1:0] proc_49_data_FIFO_blk;
    wire [1:0] proc_49_data_PIPO_blk;
    wire [1:0] proc_49_start_FIFO_blk;
    wire [1:0] proc_49_TLF_FIFO_blk;
    wire [1:0] proc_49_input_sync_blk;
    wire [1:0] proc_49_output_sync_blk;
    wire [1:0] proc_dep_vld_vec_49;
    reg [1:0] proc_dep_vld_vec_49_reg;
    wire [1:0] in_chan_dep_vld_vec_49;
    wire [147:0] in_chan_dep_data_vec_49;
    wire [1:0] token_in_vec_49;
    wire [1:0] out_chan_dep_vld_vec_49;
    wire [73:0] out_chan_dep_data_49;
    wire [1:0] token_out_vec_49;
    wire dl_detect_out_49;
    wire dep_chan_vld_50_49;
    wire [73:0] dep_chan_data_50_49;
    wire token_50_49;
    wire dep_chan_vld_52_49;
    wire [73:0] dep_chan_data_52_49;
    wire token_52_49;
    wire [1:0] proc_50_data_FIFO_blk;
    wire [1:0] proc_50_data_PIPO_blk;
    wire [1:0] proc_50_start_FIFO_blk;
    wire [1:0] proc_50_TLF_FIFO_blk;
    wire [1:0] proc_50_input_sync_blk;
    wire [1:0] proc_50_output_sync_blk;
    wire [1:0] proc_dep_vld_vec_50;
    reg [1:0] proc_dep_vld_vec_50_reg;
    wire [1:0] in_chan_dep_vld_vec_50;
    wire [147:0] in_chan_dep_data_vec_50;
    wire [1:0] token_in_vec_50;
    wire [1:0] out_chan_dep_vld_vec_50;
    wire [73:0] out_chan_dep_data_50;
    wire [1:0] token_out_vec_50;
    wire dl_detect_out_50;
    wire dep_chan_vld_49_50;
    wire [73:0] dep_chan_data_49_50;
    wire token_49_50;
    wire dep_chan_vld_51_50;
    wire [73:0] dep_chan_data_51_50;
    wire token_51_50;
    wire [1:0] proc_51_data_FIFO_blk;
    wire [1:0] proc_51_data_PIPO_blk;
    wire [1:0] proc_51_start_FIFO_blk;
    wire [1:0] proc_51_TLF_FIFO_blk;
    wire [1:0] proc_51_input_sync_blk;
    wire [1:0] proc_51_output_sync_blk;
    wire [1:0] proc_dep_vld_vec_51;
    reg [1:0] proc_dep_vld_vec_51_reg;
    wire [1:0] in_chan_dep_vld_vec_51;
    wire [147:0] in_chan_dep_data_vec_51;
    wire [1:0] token_in_vec_51;
    wire [1:0] out_chan_dep_vld_vec_51;
    wire [73:0] out_chan_dep_data_51;
    wire [1:0] token_out_vec_51;
    wire dl_detect_out_51;
    wire dep_chan_vld_50_51;
    wire [73:0] dep_chan_data_50_51;
    wire token_50_51;
    wire dep_chan_vld_64_51;
    wire [73:0] dep_chan_data_64_51;
    wire token_64_51;
    wire [2:0] proc_52_data_FIFO_blk;
    wire [2:0] proc_52_data_PIPO_blk;
    wire [2:0] proc_52_start_FIFO_blk;
    wire [2:0] proc_52_TLF_FIFO_blk;
    wire [2:0] proc_52_input_sync_blk;
    wire [2:0] proc_52_output_sync_blk;
    wire [2:0] proc_dep_vld_vec_52;
    reg [2:0] proc_dep_vld_vec_52_reg;
    wire [2:0] in_chan_dep_vld_vec_52;
    wire [221:0] in_chan_dep_data_vec_52;
    wire [2:0] token_in_vec_52;
    wire [2:0] out_chan_dep_vld_vec_52;
    wire [73:0] out_chan_dep_data_52;
    wire [2:0] token_out_vec_52;
    wire dl_detect_out_52;
    wire dep_chan_vld_49_52;
    wire [73:0] dep_chan_data_49_52;
    wire token_49_52;
    wire dep_chan_vld_53_52;
    wire [73:0] dep_chan_data_53_52;
    wire token_53_52;
    wire dep_chan_vld_54_52;
    wire [73:0] dep_chan_data_54_52;
    wire token_54_52;
    wire [1:0] proc_53_data_FIFO_blk;
    wire [1:0] proc_53_data_PIPO_blk;
    wire [1:0] proc_53_start_FIFO_blk;
    wire [1:0] proc_53_TLF_FIFO_blk;
    wire [1:0] proc_53_input_sync_blk;
    wire [1:0] proc_53_output_sync_blk;
    wire [1:0] proc_dep_vld_vec_53;
    reg [1:0] proc_dep_vld_vec_53_reg;
    wire [1:0] in_chan_dep_vld_vec_53;
    wire [147:0] in_chan_dep_data_vec_53;
    wire [1:0] token_in_vec_53;
    wire [1:0] out_chan_dep_vld_vec_53;
    wire [73:0] out_chan_dep_data_53;
    wire [1:0] token_out_vec_53;
    wire dl_detect_out_53;
    wire dep_chan_vld_52_53;
    wire [73:0] dep_chan_data_52_53;
    wire token_52_53;
    wire dep_chan_vld_58_53;
    wire [73:0] dep_chan_data_58_53;
    wire token_58_53;
    wire [1:0] proc_54_data_FIFO_blk;
    wire [1:0] proc_54_data_PIPO_blk;
    wire [1:0] proc_54_start_FIFO_blk;
    wire [1:0] proc_54_TLF_FIFO_blk;
    wire [1:0] proc_54_input_sync_blk;
    wire [1:0] proc_54_output_sync_blk;
    wire [1:0] proc_dep_vld_vec_54;
    reg [1:0] proc_dep_vld_vec_54_reg;
    wire [1:0] in_chan_dep_vld_vec_54;
    wire [147:0] in_chan_dep_data_vec_54;
    wire [1:0] token_in_vec_54;
    wire [1:0] out_chan_dep_vld_vec_54;
    wire [73:0] out_chan_dep_data_54;
    wire [1:0] token_out_vec_54;
    wire dl_detect_out_54;
    wire dep_chan_vld_52_54;
    wire [73:0] dep_chan_data_52_54;
    wire token_52_54;
    wire dep_chan_vld_55_54;
    wire [73:0] dep_chan_data_55_54;
    wire token_55_54;
    wire [1:0] proc_55_data_FIFO_blk;
    wire [1:0] proc_55_data_PIPO_blk;
    wire [1:0] proc_55_start_FIFO_blk;
    wire [1:0] proc_55_TLF_FIFO_blk;
    wire [1:0] proc_55_input_sync_blk;
    wire [1:0] proc_55_output_sync_blk;
    wire [1:0] proc_dep_vld_vec_55;
    reg [1:0] proc_dep_vld_vec_55_reg;
    wire [1:0] in_chan_dep_vld_vec_55;
    wire [147:0] in_chan_dep_data_vec_55;
    wire [1:0] token_in_vec_55;
    wire [1:0] out_chan_dep_vld_vec_55;
    wire [73:0] out_chan_dep_data_55;
    wire [1:0] token_out_vec_55;
    wire dl_detect_out_55;
    wire dep_chan_vld_54_55;
    wire [73:0] dep_chan_data_54_55;
    wire token_54_55;
    wire dep_chan_vld_56_55;
    wire [73:0] dep_chan_data_56_55;
    wire token_56_55;
    wire [1:0] proc_56_data_FIFO_blk;
    wire [1:0] proc_56_data_PIPO_blk;
    wire [1:0] proc_56_start_FIFO_blk;
    wire [1:0] proc_56_TLF_FIFO_blk;
    wire [1:0] proc_56_input_sync_blk;
    wire [1:0] proc_56_output_sync_blk;
    wire [1:0] proc_dep_vld_vec_56;
    reg [1:0] proc_dep_vld_vec_56_reg;
    wire [1:0] in_chan_dep_vld_vec_56;
    wire [147:0] in_chan_dep_data_vec_56;
    wire [1:0] token_in_vec_56;
    wire [1:0] out_chan_dep_vld_vec_56;
    wire [73:0] out_chan_dep_data_56;
    wire [1:0] token_out_vec_56;
    wire dl_detect_out_56;
    wire dep_chan_vld_55_56;
    wire [73:0] dep_chan_data_55_56;
    wire token_55_56;
    wire dep_chan_vld_57_56;
    wire [73:0] dep_chan_data_57_56;
    wire token_57_56;
    wire [1:0] proc_57_data_FIFO_blk;
    wire [1:0] proc_57_data_PIPO_blk;
    wire [1:0] proc_57_start_FIFO_blk;
    wire [1:0] proc_57_TLF_FIFO_blk;
    wire [1:0] proc_57_input_sync_blk;
    wire [1:0] proc_57_output_sync_blk;
    wire [1:0] proc_dep_vld_vec_57;
    reg [1:0] proc_dep_vld_vec_57_reg;
    wire [1:0] in_chan_dep_vld_vec_57;
    wire [147:0] in_chan_dep_data_vec_57;
    wire [1:0] token_in_vec_57;
    wire [1:0] out_chan_dep_vld_vec_57;
    wire [73:0] out_chan_dep_data_57;
    wire [1:0] token_out_vec_57;
    wire dl_detect_out_57;
    wire dep_chan_vld_56_57;
    wire [73:0] dep_chan_data_56_57;
    wire token_56_57;
    wire dep_chan_vld_58_57;
    wire [73:0] dep_chan_data_58_57;
    wire token_58_57;
    wire [3:0] proc_58_data_FIFO_blk;
    wire [3:0] proc_58_data_PIPO_blk;
    wire [3:0] proc_58_start_FIFO_blk;
    wire [3:0] proc_58_TLF_FIFO_blk;
    wire [3:0] proc_58_input_sync_blk;
    wire [3:0] proc_58_output_sync_blk;
    wire [3:0] proc_dep_vld_vec_58;
    reg [3:0] proc_dep_vld_vec_58_reg;
    wire [3:0] in_chan_dep_vld_vec_58;
    wire [295:0] in_chan_dep_data_vec_58;
    wire [3:0] token_in_vec_58;
    wire [3:0] out_chan_dep_vld_vec_58;
    wire [73:0] out_chan_dep_data_58;
    wire [3:0] token_out_vec_58;
    wire dl_detect_out_58;
    wire dep_chan_vld_53_58;
    wire [73:0] dep_chan_data_53_58;
    wire token_53_58;
    wire dep_chan_vld_57_58;
    wire [73:0] dep_chan_data_57_58;
    wire token_57_58;
    wire dep_chan_vld_59_58;
    wire [73:0] dep_chan_data_59_58;
    wire token_59_58;
    wire dep_chan_vld_60_58;
    wire [73:0] dep_chan_data_60_58;
    wire token_60_58;
    wire [1:0] proc_59_data_FIFO_blk;
    wire [1:0] proc_59_data_PIPO_blk;
    wire [1:0] proc_59_start_FIFO_blk;
    wire [1:0] proc_59_TLF_FIFO_blk;
    wire [1:0] proc_59_input_sync_blk;
    wire [1:0] proc_59_output_sync_blk;
    wire [1:0] proc_dep_vld_vec_59;
    reg [1:0] proc_dep_vld_vec_59_reg;
    wire [1:0] in_chan_dep_vld_vec_59;
    wire [147:0] in_chan_dep_data_vec_59;
    wire [1:0] token_in_vec_59;
    wire [1:0] out_chan_dep_vld_vec_59;
    wire [73:0] out_chan_dep_data_59;
    wire [1:0] token_out_vec_59;
    wire dl_detect_out_59;
    wire dep_chan_vld_58_59;
    wire [73:0] dep_chan_data_58_59;
    wire token_58_59;
    wire dep_chan_vld_64_59;
    wire [73:0] dep_chan_data_64_59;
    wire token_64_59;
    wire [1:0] proc_60_data_FIFO_blk;
    wire [1:0] proc_60_data_PIPO_blk;
    wire [1:0] proc_60_start_FIFO_blk;
    wire [1:0] proc_60_TLF_FIFO_blk;
    wire [1:0] proc_60_input_sync_blk;
    wire [1:0] proc_60_output_sync_blk;
    wire [1:0] proc_dep_vld_vec_60;
    reg [1:0] proc_dep_vld_vec_60_reg;
    wire [1:0] in_chan_dep_vld_vec_60;
    wire [147:0] in_chan_dep_data_vec_60;
    wire [1:0] token_in_vec_60;
    wire [1:0] out_chan_dep_vld_vec_60;
    wire [73:0] out_chan_dep_data_60;
    wire [1:0] token_out_vec_60;
    wire dl_detect_out_60;
    wire dep_chan_vld_58_60;
    wire [73:0] dep_chan_data_58_60;
    wire token_58_60;
    wire dep_chan_vld_61_60;
    wire [73:0] dep_chan_data_61_60;
    wire token_61_60;
    wire [1:0] proc_61_data_FIFO_blk;
    wire [1:0] proc_61_data_PIPO_blk;
    wire [1:0] proc_61_start_FIFO_blk;
    wire [1:0] proc_61_TLF_FIFO_blk;
    wire [1:0] proc_61_input_sync_blk;
    wire [1:0] proc_61_output_sync_blk;
    wire [1:0] proc_dep_vld_vec_61;
    reg [1:0] proc_dep_vld_vec_61_reg;
    wire [1:0] in_chan_dep_vld_vec_61;
    wire [147:0] in_chan_dep_data_vec_61;
    wire [1:0] token_in_vec_61;
    wire [1:0] out_chan_dep_vld_vec_61;
    wire [73:0] out_chan_dep_data_61;
    wire [1:0] token_out_vec_61;
    wire dl_detect_out_61;
    wire dep_chan_vld_60_61;
    wire [73:0] dep_chan_data_60_61;
    wire token_60_61;
    wire dep_chan_vld_62_61;
    wire [73:0] dep_chan_data_62_61;
    wire token_62_61;
    wire [1:0] proc_62_data_FIFO_blk;
    wire [1:0] proc_62_data_PIPO_blk;
    wire [1:0] proc_62_start_FIFO_blk;
    wire [1:0] proc_62_TLF_FIFO_blk;
    wire [1:0] proc_62_input_sync_blk;
    wire [1:0] proc_62_output_sync_blk;
    wire [1:0] proc_dep_vld_vec_62;
    reg [1:0] proc_dep_vld_vec_62_reg;
    wire [1:0] in_chan_dep_vld_vec_62;
    wire [147:0] in_chan_dep_data_vec_62;
    wire [1:0] token_in_vec_62;
    wire [1:0] out_chan_dep_vld_vec_62;
    wire [73:0] out_chan_dep_data_62;
    wire [1:0] token_out_vec_62;
    wire dl_detect_out_62;
    wire dep_chan_vld_61_62;
    wire [73:0] dep_chan_data_61_62;
    wire token_61_62;
    wire dep_chan_vld_63_62;
    wire [73:0] dep_chan_data_63_62;
    wire token_63_62;
    wire [1:0] proc_63_data_FIFO_blk;
    wire [1:0] proc_63_data_PIPO_blk;
    wire [1:0] proc_63_start_FIFO_blk;
    wire [1:0] proc_63_TLF_FIFO_blk;
    wire [1:0] proc_63_input_sync_blk;
    wire [1:0] proc_63_output_sync_blk;
    wire [1:0] proc_dep_vld_vec_63;
    reg [1:0] proc_dep_vld_vec_63_reg;
    wire [1:0] in_chan_dep_vld_vec_63;
    wire [147:0] in_chan_dep_data_vec_63;
    wire [1:0] token_in_vec_63;
    wire [1:0] out_chan_dep_vld_vec_63;
    wire [73:0] out_chan_dep_data_63;
    wire [1:0] token_out_vec_63;
    wire dl_detect_out_63;
    wire dep_chan_vld_62_63;
    wire [73:0] dep_chan_data_62_63;
    wire token_62_63;
    wire dep_chan_vld_64_63;
    wire [73:0] dep_chan_data_64_63;
    wire token_64_63;
    wire [2:0] proc_64_data_FIFO_blk;
    wire [2:0] proc_64_data_PIPO_blk;
    wire [2:0] proc_64_start_FIFO_blk;
    wire [2:0] proc_64_TLF_FIFO_blk;
    wire [2:0] proc_64_input_sync_blk;
    wire [2:0] proc_64_output_sync_blk;
    wire [2:0] proc_dep_vld_vec_64;
    reg [2:0] proc_dep_vld_vec_64_reg;
    wire [2:0] in_chan_dep_vld_vec_64;
    wire [221:0] in_chan_dep_data_vec_64;
    wire [2:0] token_in_vec_64;
    wire [2:0] out_chan_dep_vld_vec_64;
    wire [73:0] out_chan_dep_data_64;
    wire [2:0] token_out_vec_64;
    wire dl_detect_out_64;
    wire dep_chan_vld_51_64;
    wire [73:0] dep_chan_data_51_64;
    wire token_51_64;
    wire dep_chan_vld_59_64;
    wire [73:0] dep_chan_data_59_64;
    wire token_59_64;
    wire dep_chan_vld_63_64;
    wire [73:0] dep_chan_data_63_64;
    wire token_63_64;
    wire [1:0] proc_65_data_FIFO_blk;
    wire [1:0] proc_65_data_PIPO_blk;
    wire [1:0] proc_65_start_FIFO_blk;
    wire [1:0] proc_65_TLF_FIFO_blk;
    wire [1:0] proc_65_input_sync_blk;
    wire [1:0] proc_65_output_sync_blk;
    wire [1:0] proc_dep_vld_vec_65;
    reg [1:0] proc_dep_vld_vec_65_reg;
    wire [1:0] in_chan_dep_vld_vec_65;
    wire [147:0] in_chan_dep_data_vec_65;
    wire [1:0] token_in_vec_65;
    wire [1:0] out_chan_dep_vld_vec_65;
    wire [73:0] out_chan_dep_data_65;
    wire [1:0] token_out_vec_65;
    wire dl_detect_out_65;
    wire dep_chan_vld_48_65;
    wire [73:0] dep_chan_data_48_65;
    wire token_48_65;
    wire dep_chan_vld_66_65;
    wire [73:0] dep_chan_data_66_65;
    wire token_66_65;
    wire [1:0] proc_66_data_FIFO_blk;
    wire [1:0] proc_66_data_PIPO_blk;
    wire [1:0] proc_66_start_FIFO_blk;
    wire [1:0] proc_66_TLF_FIFO_blk;
    wire [1:0] proc_66_input_sync_blk;
    wire [1:0] proc_66_output_sync_blk;
    wire [1:0] proc_dep_vld_vec_66;
    reg [1:0] proc_dep_vld_vec_66_reg;
    wire [0:0] in_chan_dep_vld_vec_66;
    wire [73:0] in_chan_dep_data_vec_66;
    wire [0:0] token_in_vec_66;
    wire [1:0] out_chan_dep_vld_vec_66;
    wire [73:0] out_chan_dep_data_66;
    wire [1:0] token_out_vec_66;
    wire dl_detect_out_66;
    wire dep_chan_vld_65_66;
    wire [73:0] dep_chan_data_65_66;
    wire token_65_66;
    wire [1:0] proc_67_data_FIFO_blk;
    wire [1:0] proc_67_data_PIPO_blk;
    wire [1:0] proc_67_start_FIFO_blk;
    wire [1:0] proc_67_TLF_FIFO_blk;
    wire [1:0] proc_67_input_sync_blk;
    wire [1:0] proc_67_output_sync_blk;
    wire [1:0] proc_dep_vld_vec_67;
    reg [1:0] proc_dep_vld_vec_67_reg;
    wire [1:0] in_chan_dep_vld_vec_67;
    wire [147:0] in_chan_dep_data_vec_67;
    wire [1:0] token_in_vec_67;
    wire [1:0] out_chan_dep_vld_vec_67;
    wire [73:0] out_chan_dep_data_67;
    wire [1:0] token_out_vec_67;
    wire dl_detect_out_67;
    wire dep_chan_vld_68_67;
    wire [73:0] dep_chan_data_68_67;
    wire token_68_67;
    wire dep_chan_vld_69_67;
    wire [73:0] dep_chan_data_69_67;
    wire token_69_67;
    wire [1:0] proc_68_data_FIFO_blk;
    wire [1:0] proc_68_data_PIPO_blk;
    wire [1:0] proc_68_start_FIFO_blk;
    wire [1:0] proc_68_TLF_FIFO_blk;
    wire [1:0] proc_68_input_sync_blk;
    wire [1:0] proc_68_output_sync_blk;
    wire [1:0] proc_dep_vld_vec_68;
    reg [1:0] proc_dep_vld_vec_68_reg;
    wire [1:0] in_chan_dep_vld_vec_68;
    wire [147:0] in_chan_dep_data_vec_68;
    wire [1:0] token_in_vec_68;
    wire [1:0] out_chan_dep_vld_vec_68;
    wire [73:0] out_chan_dep_data_68;
    wire [1:0] token_out_vec_68;
    wire dl_detect_out_68;
    wire dep_chan_vld_67_68;
    wire [73:0] dep_chan_data_67_68;
    wire token_67_68;
    wire dep_chan_vld_73_68;
    wire [73:0] dep_chan_data_73_68;
    wire token_73_68;
    wire [2:0] proc_69_data_FIFO_blk;
    wire [2:0] proc_69_data_PIPO_blk;
    wire [2:0] proc_69_start_FIFO_blk;
    wire [2:0] proc_69_TLF_FIFO_blk;
    wire [2:0] proc_69_input_sync_blk;
    wire [2:0] proc_69_output_sync_blk;
    wire [2:0] proc_dep_vld_vec_69;
    reg [2:0] proc_dep_vld_vec_69_reg;
    wire [2:0] in_chan_dep_vld_vec_69;
    wire [221:0] in_chan_dep_data_vec_69;
    wire [2:0] token_in_vec_69;
    wire [2:0] out_chan_dep_vld_vec_69;
    wire [73:0] out_chan_dep_data_69;
    wire [2:0] token_out_vec_69;
    wire dl_detect_out_69;
    wire dep_chan_vld_67_69;
    wire [73:0] dep_chan_data_67_69;
    wire token_67_69;
    wire dep_chan_vld_70_69;
    wire [73:0] dep_chan_data_70_69;
    wire token_70_69;
    wire dep_chan_vld_71_69;
    wire [73:0] dep_chan_data_71_69;
    wire token_71_69;
    wire [1:0] proc_70_data_FIFO_blk;
    wire [1:0] proc_70_data_PIPO_blk;
    wire [1:0] proc_70_start_FIFO_blk;
    wire [1:0] proc_70_TLF_FIFO_blk;
    wire [1:0] proc_70_input_sync_blk;
    wire [1:0] proc_70_output_sync_blk;
    wire [1:0] proc_dep_vld_vec_70;
    reg [1:0] proc_dep_vld_vec_70_reg;
    wire [1:0] in_chan_dep_vld_vec_70;
    wire [147:0] in_chan_dep_data_vec_70;
    wire [1:0] token_in_vec_70;
    wire [1:0] out_chan_dep_vld_vec_70;
    wire [73:0] out_chan_dep_data_70;
    wire [1:0] token_out_vec_70;
    wire dl_detect_out_70;
    wire dep_chan_vld_69_70;
    wire [73:0] dep_chan_data_69_70;
    wire token_69_70;
    wire dep_chan_vld_73_70;
    wire [73:0] dep_chan_data_73_70;
    wire token_73_70;
    wire [1:0] proc_71_data_FIFO_blk;
    wire [1:0] proc_71_data_PIPO_blk;
    wire [1:0] proc_71_start_FIFO_blk;
    wire [1:0] proc_71_TLF_FIFO_blk;
    wire [1:0] proc_71_input_sync_blk;
    wire [1:0] proc_71_output_sync_blk;
    wire [1:0] proc_dep_vld_vec_71;
    reg [1:0] proc_dep_vld_vec_71_reg;
    wire [1:0] in_chan_dep_vld_vec_71;
    wire [147:0] in_chan_dep_data_vec_71;
    wire [1:0] token_in_vec_71;
    wire [1:0] out_chan_dep_vld_vec_71;
    wire [73:0] out_chan_dep_data_71;
    wire [1:0] token_out_vec_71;
    wire dl_detect_out_71;
    wire dep_chan_vld_69_71;
    wire [73:0] dep_chan_data_69_71;
    wire token_69_71;
    wire dep_chan_vld_72_71;
    wire [73:0] dep_chan_data_72_71;
    wire token_72_71;
    wire [1:0] proc_72_data_FIFO_blk;
    wire [1:0] proc_72_data_PIPO_blk;
    wire [1:0] proc_72_start_FIFO_blk;
    wire [1:0] proc_72_TLF_FIFO_blk;
    wire [1:0] proc_72_input_sync_blk;
    wire [1:0] proc_72_output_sync_blk;
    wire [1:0] proc_dep_vld_vec_72;
    reg [1:0] proc_dep_vld_vec_72_reg;
    wire [1:0] in_chan_dep_vld_vec_72;
    wire [147:0] in_chan_dep_data_vec_72;
    wire [1:0] token_in_vec_72;
    wire [1:0] out_chan_dep_vld_vec_72;
    wire [73:0] out_chan_dep_data_72;
    wire [1:0] token_out_vec_72;
    wire dl_detect_out_72;
    wire dep_chan_vld_71_72;
    wire [73:0] dep_chan_data_71_72;
    wire token_71_72;
    wire dep_chan_vld_73_72;
    wire [73:0] dep_chan_data_73_72;
    wire token_73_72;
    wire [2:0] proc_73_data_FIFO_blk;
    wire [2:0] proc_73_data_PIPO_blk;
    wire [2:0] proc_73_start_FIFO_blk;
    wire [2:0] proc_73_TLF_FIFO_blk;
    wire [2:0] proc_73_input_sync_blk;
    wire [2:0] proc_73_output_sync_blk;
    wire [2:0] proc_dep_vld_vec_73;
    reg [2:0] proc_dep_vld_vec_73_reg;
    wire [2:0] in_chan_dep_vld_vec_73;
    wire [221:0] in_chan_dep_data_vec_73;
    wire [2:0] token_in_vec_73;
    wire [2:0] out_chan_dep_vld_vec_73;
    wire [73:0] out_chan_dep_data_73;
    wire [2:0] token_out_vec_73;
    wire dl_detect_out_73;
    wire dep_chan_vld_68_73;
    wire [73:0] dep_chan_data_68_73;
    wire token_68_73;
    wire dep_chan_vld_70_73;
    wire [73:0] dep_chan_data_70_73;
    wire token_70_73;
    wire dep_chan_vld_72_73;
    wire [73:0] dep_chan_data_72_73;
    wire token_72_73;
    wire [73:0] dl_in_vec;
    wire dl_detect_out;
    wire token_clear;
    reg [73:0] origin;

    reg ap_done_reg_0;// for module grp_dataflow_wrapper_fu_6443.task_compute_attn_U0
    always @ (negedge dl_reset or posedge dl_clock) begin
        if (~dl_reset) begin
            ap_done_reg_0 <= 'b0;
        end
        else begin
            ap_done_reg_0 <= grp_dataflow_wrapper_fu_6443.task_compute_attn_U0.ap_done & ~grp_dataflow_wrapper_fu_6443.task_compute_attn_U0.ap_continue;
        end
    end

    reg ap_done_reg_1;// for module grp_dataflow_wrapper_fu_6443.task_compute_mlp_U0
    always @ (negedge dl_reset or posedge dl_clock) begin
        if (~dl_reset) begin
            ap_done_reg_1 <= 'b0;
        end
        else begin
            ap_done_reg_1 <= grp_dataflow_wrapper_fu_6443.task_compute_mlp_U0.ap_done & ~grp_dataflow_wrapper_fu_6443.task_compute_mlp_U0.ap_continue;
        end
    end

    reg ap_done_reg_2;// for module grp_dataflow_wrapper_fu_6443.task_load_weights_14_U0
    always @ (negedge dl_reset or posedge dl_clock) begin
        if (~dl_reset) begin
            ap_done_reg_2 <= 'b0;
        end
        else begin
            ap_done_reg_2 <= grp_dataflow_wrapper_fu_6443.task_load_weights_14_U0.ap_done & ~grp_dataflow_wrapper_fu_6443.task_load_weights_14_U0.ap_continue;
        end
    end

    reg ap_done_reg_3;// for module grp_initial_overlap_wrapper_fu_5704.task_run_pe_U0
    always @ (negedge dl_reset or posedge dl_clock) begin
        if (~dl_reset) begin
            ap_done_reg_3 <= 'b0;
        end
        else begin
            ap_done_reg_3 <= grp_initial_overlap_wrapper_fu_5704.task_run_pe_U0.ap_done & ~grp_initial_overlap_wrapper_fu_5704.task_run_pe_U0.ap_continue;
        end
    end

    reg ap_done_reg_4;// for module grp_initial_overlap_wrapper_fu_5704.task_load_weights_U0
    always @ (negedge dl_reset or posedge dl_clock) begin
        if (~dl_reset) begin
            ap_done_reg_4 <= 'b0;
        end
        else begin
            ap_done_reg_4 <= grp_initial_overlap_wrapper_fu_5704.task_load_weights_U0.ap_done & ~grp_initial_overlap_wrapper_fu_5704.task_load_weights_U0.ap_continue;
        end
    end

    reg ap_done_reg_5;// for module grp_dataflow_wrapper_fu_6443.task_write_fm_U0
    always @ (negedge dl_reset or posedge dl_clock) begin
        if (~dl_reset) begin
            ap_done_reg_5 <= 'b0;
        end
        else begin
            ap_done_reg_5 <= grp_dataflow_wrapper_fu_6443.task_write_fm_U0.ap_done & ~grp_dataflow_wrapper_fu_6443.task_write_fm_U0.ap_continue;
        end
    end

reg [15:0] trans_in_cnt_0;// for process grp_initial_overlap_wrapper_fu_5704.task_run_pe_U0.task_recv_img_U0
always @(negedge dl_reset or posedge dl_clock) begin
    if (~dl_reset) begin
         trans_in_cnt_0 <= 16'h0;
    end
    else if (grp_initial_overlap_wrapper_fu_5704.task_run_pe_U0.task_recv_img_U0.start_write == 1'b1) begin
        trans_in_cnt_0 <= trans_in_cnt_0 + 16'h1;
    end
    else begin
        trans_in_cnt_0 <= trans_in_cnt_0;
    end
end

reg [15:0] trans_out_cnt_0;// for process grp_initial_overlap_wrapper_fu_5704.task_run_pe_U0.task_recv_img_U0
always @(negedge dl_reset or posedge dl_clock) begin
    if (~dl_reset) begin
         trans_out_cnt_0 <= 16'h0;
    end
    else if (grp_initial_overlap_wrapper_fu_5704.task_run_pe_U0.task_recv_img_U0.ap_done == 1'b1 && grp_initial_overlap_wrapper_fu_5704.task_run_pe_U0.task_recv_img_U0.ap_continue == 1'b1) begin
        trans_out_cnt_0 <= trans_out_cnt_0 + 16'h1;
    end
    else begin
        trans_out_cnt_0 <= trans_out_cnt_0;
    end
end

reg [15:0] trans_in_cnt_1;// for process grp_initial_overlap_wrapper_fu_5704.task_run_pe_U0.fixed_patch_do_patch_embed_U0.do_adapt_4_U0
always @(negedge dl_reset or posedge dl_clock) begin
    if (~dl_reset) begin
         trans_in_cnt_1 <= 16'h0;
    end
    else if (grp_initial_overlap_wrapper_fu_5704.task_run_pe_U0.fixed_patch_do_patch_embed_U0.do_adapt_4_U0.start_write == 1'b1) begin
        trans_in_cnt_1 <= trans_in_cnt_1 + 16'h1;
    end
    else begin
        trans_in_cnt_1 <= trans_in_cnt_1;
    end
end

reg [15:0] trans_out_cnt_1;// for process grp_initial_overlap_wrapper_fu_5704.task_run_pe_U0.fixed_patch_do_patch_embed_U0.do_adapt_4_U0
always @(negedge dl_reset or posedge dl_clock) begin
    if (~dl_reset) begin
         trans_out_cnt_1 <= 16'h0;
    end
    else if (grp_initial_overlap_wrapper_fu_5704.task_run_pe_U0.fixed_patch_do_patch_embed_U0.do_adapt_4_U0.ap_done == 1'b1 && grp_initial_overlap_wrapper_fu_5704.task_run_pe_U0.fixed_patch_do_patch_embed_U0.do_adapt_4_U0.ap_continue == 1'b1) begin
        trans_out_cnt_1 <= trans_out_cnt_1 + 16'h1;
    end
    else begin
        trans_out_cnt_1 <= trans_out_cnt_1;
    end
end

reg [15:0] trans_in_cnt_2;// for process grp_initial_overlap_wrapper_fu_5704.task_run_pe_U0.fixed_patch_do_patch_embed_U0.fixed_patch_step2_mac_replace_shift_U0
always @(negedge dl_reset or posedge dl_clock) begin
    if (~dl_reset) begin
         trans_in_cnt_2 <= 16'h0;
    end
    else if (grp_initial_overlap_wrapper_fu_5704.task_run_pe_U0.fixed_patch_do_patch_embed_U0.fixed_patch_step2_mac_replace_shift_U0.start_write == 1'b1) begin
        trans_in_cnt_2 <= trans_in_cnt_2 + 16'h1;
    end
    else begin
        trans_in_cnt_2 <= trans_in_cnt_2;
    end
end

reg [15:0] trans_out_cnt_2;// for process grp_initial_overlap_wrapper_fu_5704.task_run_pe_U0.fixed_patch_do_patch_embed_U0.fixed_patch_step2_mac_replace_shift_U0
always @(negedge dl_reset or posedge dl_clock) begin
    if (~dl_reset) begin
         trans_out_cnt_2 <= 16'h0;
    end
    else if (grp_initial_overlap_wrapper_fu_5704.task_run_pe_U0.fixed_patch_do_patch_embed_U0.fixed_patch_step2_mac_replace_shift_U0.ap_done == 1'b1 && grp_initial_overlap_wrapper_fu_5704.task_run_pe_U0.fixed_patch_do_patch_embed_U0.fixed_patch_step2_mac_replace_shift_U0.ap_continue == 1'b1) begin
        trans_out_cnt_2 <= trans_out_cnt_2 + 16'h1;
    end
    else begin
        trans_out_cnt_2 <= trans_out_cnt_2;
    end
end

reg [15:0] trans_in_cnt_3;// for process grp_initial_overlap_wrapper_fu_5704.task_run_pe_U0.fixed_patch_do_patch_embed_U0
always @(negedge dl_reset or posedge dl_clock) begin
    if (~dl_reset) begin
         trans_in_cnt_3 <= 16'h0;
    end
    else if (grp_initial_overlap_wrapper_fu_5704.task_run_pe_U0.fixed_patch_do_patch_embed_U0.start_write == 1'b1) begin
        trans_in_cnt_3 <= trans_in_cnt_3 + 16'h1;
    end
    else begin
        trans_in_cnt_3 <= trans_in_cnt_3;
    end
end

reg [15:0] trans_out_cnt_3;// for process grp_initial_overlap_wrapper_fu_5704.task_run_pe_U0.fixed_patch_do_patch_embed_U0
always @(negedge dl_reset or posedge dl_clock) begin
    if (~dl_reset) begin
         trans_out_cnt_3 <= 16'h0;
    end
    else if (grp_initial_overlap_wrapper_fu_5704.task_run_pe_U0.fixed_patch_do_patch_embed_U0.ap_done == 1'b1 && grp_initial_overlap_wrapper_fu_5704.task_run_pe_U0.fixed_patch_do_patch_embed_U0.ap_continue == 1'b1) begin
        trans_out_cnt_3 <= trans_out_cnt_3 + 16'h1;
    end
    else begin
        trans_out_cnt_3 <= trans_out_cnt_3;
    end
end

reg [15:0] trans_in_cnt_4;// for process grp_dataflow_wrapper_fu_6443.task_compute_attn_U0.grp_do_attn_1_fu_5150.do_adapt_10_U0
always @(negedge dl_reset or posedge dl_clock) begin
    if (~dl_reset) begin
         trans_in_cnt_4 <= 16'h0;
    end
    else if (grp_dataflow_wrapper_fu_6443.task_compute_attn_U0.grp_do_attn_1_fu_5150.do_adapt_10_U0.start_write == 1'b1) begin
        trans_in_cnt_4 <= trans_in_cnt_4 + 16'h1;
    end
    else begin
        trans_in_cnt_4 <= trans_in_cnt_4;
    end
end

reg [15:0] trans_out_cnt_4;// for process grp_dataflow_wrapper_fu_6443.task_compute_attn_U0.grp_do_attn_1_fu_5150.do_adapt_10_U0
always @(negedge dl_reset or posedge dl_clock) begin
    if (~dl_reset) begin
         trans_out_cnt_4 <= 16'h0;
    end
    else if (grp_dataflow_wrapper_fu_6443.task_compute_attn_U0.grp_do_attn_1_fu_5150.do_adapt_10_U0.ap_done == 1'b1 && grp_dataflow_wrapper_fu_6443.task_compute_attn_U0.grp_do_attn_1_fu_5150.do_adapt_10_U0.ap_continue == 1'b1) begin
        trans_out_cnt_4 <= trans_out_cnt_4 + 16'h1;
    end
    else begin
        trans_out_cnt_4 <= trans_out_cnt_4;
    end
end

reg [15:0] trans_in_cnt_5;// for process grp_dataflow_wrapper_fu_6443.task_compute_attn_U0.grp_do_attn_1_fu_5150.do_layernorm_inter_token_1_U0
always @(negedge dl_reset or posedge dl_clock) begin
    if (~dl_reset) begin
         trans_in_cnt_5 <= 16'h0;
    end
    else if (grp_dataflow_wrapper_fu_6443.task_compute_attn_U0.grp_do_attn_1_fu_5150.do_layernorm_inter_token_1_U0.start_write == 1'b1) begin
        trans_in_cnt_5 <= trans_in_cnt_5 + 16'h1;
    end
    else begin
        trans_in_cnt_5 <= trans_in_cnt_5;
    end
end

reg [15:0] trans_out_cnt_5;// for process grp_dataflow_wrapper_fu_6443.task_compute_attn_U0.grp_do_attn_1_fu_5150.do_layernorm_inter_token_1_U0
always @(negedge dl_reset or posedge dl_clock) begin
    if (~dl_reset) begin
         trans_out_cnt_5 <= 16'h0;
    end
    else if (grp_dataflow_wrapper_fu_6443.task_compute_attn_U0.grp_do_attn_1_fu_5150.do_layernorm_inter_token_1_U0.ap_done == 1'b1 && grp_dataflow_wrapper_fu_6443.task_compute_attn_U0.grp_do_attn_1_fu_5150.do_layernorm_inter_token_1_U0.ap_continue == 1'b1) begin
        trans_out_cnt_5 <= trans_out_cnt_5 + 16'h1;
    end
    else begin
        trans_out_cnt_5 <= trans_out_cnt_5;
    end
end

reg [15:0] trans_in_cnt_6;// for process grp_dataflow_wrapper_fu_6443.task_compute_attn_U0.grp_do_attn_1_fu_5150.stream_copy3_U0
always @(negedge dl_reset or posedge dl_clock) begin
    if (~dl_reset) begin
         trans_in_cnt_6 <= 16'h0;
    end
    else if (grp_dataflow_wrapper_fu_6443.task_compute_attn_U0.grp_do_attn_1_fu_5150.stream_copy3_U0.start_write == 1'b1) begin
        trans_in_cnt_6 <= trans_in_cnt_6 + 16'h1;
    end
    else begin
        trans_in_cnt_6 <= trans_in_cnt_6;
    end
end

reg [15:0] trans_out_cnt_6;// for process grp_dataflow_wrapper_fu_6443.task_compute_attn_U0.grp_do_attn_1_fu_5150.stream_copy3_U0
always @(negedge dl_reset or posedge dl_clock) begin
    if (~dl_reset) begin
         trans_out_cnt_6 <= 16'h0;
    end
    else if (grp_dataflow_wrapper_fu_6443.task_compute_attn_U0.grp_do_attn_1_fu_5150.stream_copy3_U0.ap_done == 1'b1 && grp_dataflow_wrapper_fu_6443.task_compute_attn_U0.grp_do_attn_1_fu_5150.stream_copy3_U0.ap_continue == 1'b1) begin
        trans_out_cnt_6 <= trans_out_cnt_6 + 16'h1;
    end
    else begin
        trans_out_cnt_6 <= trans_out_cnt_6;
    end
end

reg [15:0] trans_in_cnt_7;// for process grp_dataflow_wrapper_fu_6443.task_compute_attn_U0.grp_do_attn_1_fu_5150.do_matmul_2_U0.do_adapt_2_U0
always @(negedge dl_reset or posedge dl_clock) begin
    if (~dl_reset) begin
         trans_in_cnt_7 <= 16'h0;
    end
    else if (grp_dataflow_wrapper_fu_6443.task_compute_attn_U0.grp_do_attn_1_fu_5150.do_matmul_2_U0.do_adapt_2_U0.start_write == 1'b1) begin
        trans_in_cnt_7 <= trans_in_cnt_7 + 16'h1;
    end
    else begin
        trans_in_cnt_7 <= trans_in_cnt_7;
    end
end

reg [15:0] trans_out_cnt_7;// for process grp_dataflow_wrapper_fu_6443.task_compute_attn_U0.grp_do_attn_1_fu_5150.do_matmul_2_U0.do_adapt_2_U0
always @(negedge dl_reset or posedge dl_clock) begin
    if (~dl_reset) begin
         trans_out_cnt_7 <= 16'h0;
    end
    else if (grp_dataflow_wrapper_fu_6443.task_compute_attn_U0.grp_do_attn_1_fu_5150.do_matmul_2_U0.do_adapt_2_U0.ap_done == 1'b1 && grp_dataflow_wrapper_fu_6443.task_compute_attn_U0.grp_do_attn_1_fu_5150.do_matmul_2_U0.do_adapt_2_U0.ap_continue == 1'b1) begin
        trans_out_cnt_7 <= trans_out_cnt_7 + 16'h1;
    end
    else begin
        trans_out_cnt_7 <= trans_out_cnt_7;
    end
end

reg [15:0] trans_in_cnt_8;// for process grp_dataflow_wrapper_fu_6443.task_compute_attn_U0.grp_do_attn_1_fu_5150.do_matmul_2_U0.matmul_step1_cache_window_2_U0
always @(negedge dl_reset or posedge dl_clock) begin
    if (~dl_reset) begin
         trans_in_cnt_8 <= 16'h0;
    end
    else if (grp_dataflow_wrapper_fu_6443.task_compute_attn_U0.grp_do_attn_1_fu_5150.do_matmul_2_U0.matmul_step1_cache_window_2_U0.start_write == 1'b1) begin
        trans_in_cnt_8 <= trans_in_cnt_8 + 16'h1;
    end
    else begin
        trans_in_cnt_8 <= trans_in_cnt_8;
    end
end

reg [15:0] trans_out_cnt_8;// for process grp_dataflow_wrapper_fu_6443.task_compute_attn_U0.grp_do_attn_1_fu_5150.do_matmul_2_U0.matmul_step1_cache_window_2_U0
always @(negedge dl_reset or posedge dl_clock) begin
    if (~dl_reset) begin
         trans_out_cnt_8 <= 16'h0;
    end
    else if (grp_dataflow_wrapper_fu_6443.task_compute_attn_U0.grp_do_attn_1_fu_5150.do_matmul_2_U0.matmul_step1_cache_window_2_U0.ap_done == 1'b1 && grp_dataflow_wrapper_fu_6443.task_compute_attn_U0.grp_do_attn_1_fu_5150.do_matmul_2_U0.matmul_step1_cache_window_2_U0.ap_continue == 1'b1) begin
        trans_out_cnt_8 <= trans_out_cnt_8 + 16'h1;
    end
    else begin
        trans_out_cnt_8 <= trans_out_cnt_8;
    end
end

reg [15:0] trans_in_cnt_9;// for process grp_dataflow_wrapper_fu_6443.task_compute_attn_U0.grp_do_attn_1_fu_5150.do_matmul_2_U0.matmul_step2_mac_2_U0
always @(negedge dl_reset or posedge dl_clock) begin
    if (~dl_reset) begin
         trans_in_cnt_9 <= 16'h0;
    end
    else if (grp_dataflow_wrapper_fu_6443.task_compute_attn_U0.grp_do_attn_1_fu_5150.do_matmul_2_U0.matmul_step2_mac_2_U0.start_write == 1'b1) begin
        trans_in_cnt_9 <= trans_in_cnt_9 + 16'h1;
    end
    else begin
        trans_in_cnt_9 <= trans_in_cnt_9;
    end
end

reg [15:0] trans_out_cnt_9;// for process grp_dataflow_wrapper_fu_6443.task_compute_attn_U0.grp_do_attn_1_fu_5150.do_matmul_2_U0.matmul_step2_mac_2_U0
always @(negedge dl_reset or posedge dl_clock) begin
    if (~dl_reset) begin
         trans_out_cnt_9 <= 16'h0;
    end
    else if (grp_dataflow_wrapper_fu_6443.task_compute_attn_U0.grp_do_attn_1_fu_5150.do_matmul_2_U0.matmul_step2_mac_2_U0.ap_done == 1'b1 && grp_dataflow_wrapper_fu_6443.task_compute_attn_U0.grp_do_attn_1_fu_5150.do_matmul_2_U0.matmul_step2_mac_2_U0.ap_continue == 1'b1) begin
        trans_out_cnt_9 <= trans_out_cnt_9 + 16'h1;
    end
    else begin
        trans_out_cnt_9 <= trans_out_cnt_9;
    end
end

reg [15:0] trans_in_cnt_10;// for process grp_dataflow_wrapper_fu_6443.task_compute_attn_U0.grp_do_attn_1_fu_5150.do_matmul_2_1_U0.do_adapt_9_U0
always @(negedge dl_reset or posedge dl_clock) begin
    if (~dl_reset) begin
         trans_in_cnt_10 <= 16'h0;
    end
    else if (grp_dataflow_wrapper_fu_6443.task_compute_attn_U0.grp_do_attn_1_fu_5150.do_matmul_2_1_U0.do_adapt_9_U0.start_write == 1'b1) begin
        trans_in_cnt_10 <= trans_in_cnt_10 + 16'h1;
    end
    else begin
        trans_in_cnt_10 <= trans_in_cnt_10;
    end
end

reg [15:0] trans_out_cnt_10;// for process grp_dataflow_wrapper_fu_6443.task_compute_attn_U0.grp_do_attn_1_fu_5150.do_matmul_2_1_U0.do_adapt_9_U0
always @(negedge dl_reset or posedge dl_clock) begin
    if (~dl_reset) begin
         trans_out_cnt_10 <= 16'h0;
    end
    else if (grp_dataflow_wrapper_fu_6443.task_compute_attn_U0.grp_do_attn_1_fu_5150.do_matmul_2_1_U0.do_adapt_9_U0.ap_done == 1'b1 && grp_dataflow_wrapper_fu_6443.task_compute_attn_U0.grp_do_attn_1_fu_5150.do_matmul_2_1_U0.do_adapt_9_U0.ap_continue == 1'b1) begin
        trans_out_cnt_10 <= trans_out_cnt_10 + 16'h1;
    end
    else begin
        trans_out_cnt_10 <= trans_out_cnt_10;
    end
end

reg [15:0] trans_in_cnt_11;// for process grp_dataflow_wrapper_fu_6443.task_compute_attn_U0.grp_do_attn_1_fu_5150.do_matmul_2_1_U0.matmul_step1_cache_window_10_U0
always @(negedge dl_reset or posedge dl_clock) begin
    if (~dl_reset) begin
         trans_in_cnt_11 <= 16'h0;
    end
    else if (grp_dataflow_wrapper_fu_6443.task_compute_attn_U0.grp_do_attn_1_fu_5150.do_matmul_2_1_U0.matmul_step1_cache_window_10_U0.start_write == 1'b1) begin
        trans_in_cnt_11 <= trans_in_cnt_11 + 16'h1;
    end
    else begin
        trans_in_cnt_11 <= trans_in_cnt_11;
    end
end

reg [15:0] trans_out_cnt_11;// for process grp_dataflow_wrapper_fu_6443.task_compute_attn_U0.grp_do_attn_1_fu_5150.do_matmul_2_1_U0.matmul_step1_cache_window_10_U0
always @(negedge dl_reset or posedge dl_clock) begin
    if (~dl_reset) begin
         trans_out_cnt_11 <= 16'h0;
    end
    else if (grp_dataflow_wrapper_fu_6443.task_compute_attn_U0.grp_do_attn_1_fu_5150.do_matmul_2_1_U0.matmul_step1_cache_window_10_U0.ap_done == 1'b1 && grp_dataflow_wrapper_fu_6443.task_compute_attn_U0.grp_do_attn_1_fu_5150.do_matmul_2_1_U0.matmul_step1_cache_window_10_U0.ap_continue == 1'b1) begin
        trans_out_cnt_11 <= trans_out_cnt_11 + 16'h1;
    end
    else begin
        trans_out_cnt_11 <= trans_out_cnt_11;
    end
end

reg [15:0] trans_in_cnt_12;// for process grp_dataflow_wrapper_fu_6443.task_compute_attn_U0.grp_do_attn_1_fu_5150.do_matmul_2_1_U0.matmul_step2_mac_11_U0
always @(negedge dl_reset or posedge dl_clock) begin
    if (~dl_reset) begin
         trans_in_cnt_12 <= 16'h0;
    end
    else if (grp_dataflow_wrapper_fu_6443.task_compute_attn_U0.grp_do_attn_1_fu_5150.do_matmul_2_1_U0.matmul_step2_mac_11_U0.start_write == 1'b1) begin
        trans_in_cnt_12 <= trans_in_cnt_12 + 16'h1;
    end
    else begin
        trans_in_cnt_12 <= trans_in_cnt_12;
    end
end

reg [15:0] trans_out_cnt_12;// for process grp_dataflow_wrapper_fu_6443.task_compute_attn_U0.grp_do_attn_1_fu_5150.do_matmul_2_1_U0.matmul_step2_mac_11_U0
always @(negedge dl_reset or posedge dl_clock) begin
    if (~dl_reset) begin
         trans_out_cnt_12 <= 16'h0;
    end
    else if (grp_dataflow_wrapper_fu_6443.task_compute_attn_U0.grp_do_attn_1_fu_5150.do_matmul_2_1_U0.matmul_step2_mac_11_U0.ap_done == 1'b1 && grp_dataflow_wrapper_fu_6443.task_compute_attn_U0.grp_do_attn_1_fu_5150.do_matmul_2_1_U0.matmul_step2_mac_11_U0.ap_continue == 1'b1) begin
        trans_out_cnt_12 <= trans_out_cnt_12 + 16'h1;
    end
    else begin
        trans_out_cnt_12 <= trans_out_cnt_12;
    end
end

reg [15:0] trans_in_cnt_13;// for process grp_dataflow_wrapper_fu_6443.task_compute_attn_U0.grp_do_attn_1_fu_5150.do_matmul_4_U0.do_adapt_13_U0
always @(negedge dl_reset or posedge dl_clock) begin
    if (~dl_reset) begin
         trans_in_cnt_13 <= 16'h0;
    end
    else if (grp_dataflow_wrapper_fu_6443.task_compute_attn_U0.grp_do_attn_1_fu_5150.do_matmul_4_U0.do_adapt_13_U0.start_write == 1'b1) begin
        trans_in_cnt_13 <= trans_in_cnt_13 + 16'h1;
    end
    else begin
        trans_in_cnt_13 <= trans_in_cnt_13;
    end
end

reg [15:0] trans_out_cnt_13;// for process grp_dataflow_wrapper_fu_6443.task_compute_attn_U0.grp_do_attn_1_fu_5150.do_matmul_4_U0.do_adapt_13_U0
always @(negedge dl_reset or posedge dl_clock) begin
    if (~dl_reset) begin
         trans_out_cnt_13 <= 16'h0;
    end
    else if (grp_dataflow_wrapper_fu_6443.task_compute_attn_U0.grp_do_attn_1_fu_5150.do_matmul_4_U0.do_adapt_13_U0.ap_done == 1'b1 && grp_dataflow_wrapper_fu_6443.task_compute_attn_U0.grp_do_attn_1_fu_5150.do_matmul_4_U0.do_adapt_13_U0.ap_continue == 1'b1) begin
        trans_out_cnt_13 <= trans_out_cnt_13 + 16'h1;
    end
    else begin
        trans_out_cnt_13 <= trans_out_cnt_13;
    end
end

reg [15:0] trans_in_cnt_14;// for process grp_dataflow_wrapper_fu_6443.task_compute_attn_U0.grp_do_attn_1_fu_5150.do_matmul_4_U0.matmul_step1_cache_window_4_U0
always @(negedge dl_reset or posedge dl_clock) begin
    if (~dl_reset) begin
         trans_in_cnt_14 <= 16'h0;
    end
    else if (grp_dataflow_wrapper_fu_6443.task_compute_attn_U0.grp_do_attn_1_fu_5150.do_matmul_4_U0.matmul_step1_cache_window_4_U0.start_write == 1'b1) begin
        trans_in_cnt_14 <= trans_in_cnt_14 + 16'h1;
    end
    else begin
        trans_in_cnt_14 <= trans_in_cnt_14;
    end
end

reg [15:0] trans_out_cnt_14;// for process grp_dataflow_wrapper_fu_6443.task_compute_attn_U0.grp_do_attn_1_fu_5150.do_matmul_4_U0.matmul_step1_cache_window_4_U0
always @(negedge dl_reset or posedge dl_clock) begin
    if (~dl_reset) begin
         trans_out_cnt_14 <= 16'h0;
    end
    else if (grp_dataflow_wrapper_fu_6443.task_compute_attn_U0.grp_do_attn_1_fu_5150.do_matmul_4_U0.matmul_step1_cache_window_4_U0.ap_done == 1'b1 && grp_dataflow_wrapper_fu_6443.task_compute_attn_U0.grp_do_attn_1_fu_5150.do_matmul_4_U0.matmul_step1_cache_window_4_U0.ap_continue == 1'b1) begin
        trans_out_cnt_14 <= trans_out_cnt_14 + 16'h1;
    end
    else begin
        trans_out_cnt_14 <= trans_out_cnt_14;
    end
end

reg [15:0] trans_in_cnt_15;// for process grp_dataflow_wrapper_fu_6443.task_compute_attn_U0.grp_do_attn_1_fu_5150.do_matmul_4_U0.matmul_step2_mac_4_U0
always @(negedge dl_reset or posedge dl_clock) begin
    if (~dl_reset) begin
         trans_in_cnt_15 <= 16'h0;
    end
    else if (grp_dataflow_wrapper_fu_6443.task_compute_attn_U0.grp_do_attn_1_fu_5150.do_matmul_4_U0.matmul_step2_mac_4_U0.start_write == 1'b1) begin
        trans_in_cnt_15 <= trans_in_cnt_15 + 16'h1;
    end
    else begin
        trans_in_cnt_15 <= trans_in_cnt_15;
    end
end

reg [15:0] trans_out_cnt_15;// for process grp_dataflow_wrapper_fu_6443.task_compute_attn_U0.grp_do_attn_1_fu_5150.do_matmul_4_U0.matmul_step2_mac_4_U0
always @(negedge dl_reset or posedge dl_clock) begin
    if (~dl_reset) begin
         trans_out_cnt_15 <= 16'h0;
    end
    else if (grp_dataflow_wrapper_fu_6443.task_compute_attn_U0.grp_do_attn_1_fu_5150.do_matmul_4_U0.matmul_step2_mac_4_U0.ap_done == 1'b1 && grp_dataflow_wrapper_fu_6443.task_compute_attn_U0.grp_do_attn_1_fu_5150.do_matmul_4_U0.matmul_step2_mac_4_U0.ap_continue == 1'b1) begin
        trans_out_cnt_15 <= trans_out_cnt_15 + 16'h1;
    end
    else begin
        trans_out_cnt_15 <= trans_out_cnt_15;
    end
end

reg [15:0] trans_in_cnt_16;// for process grp_dataflow_wrapper_fu_6443.task_compute_attn_U0.grp_do_attn_1_fu_5150.do_matmul_2_U0
always @(negedge dl_reset or posedge dl_clock) begin
    if (~dl_reset) begin
         trans_in_cnt_16 <= 16'h0;
    end
    else if (grp_dataflow_wrapper_fu_6443.task_compute_attn_U0.grp_do_attn_1_fu_5150.do_matmul_2_U0.start_write == 1'b1) begin
        trans_in_cnt_16 <= trans_in_cnt_16 + 16'h1;
    end
    else begin
        trans_in_cnt_16 <= trans_in_cnt_16;
    end
end

reg [15:0] trans_out_cnt_16;// for process grp_dataflow_wrapper_fu_6443.task_compute_attn_U0.grp_do_attn_1_fu_5150.do_matmul_2_U0
always @(negedge dl_reset or posedge dl_clock) begin
    if (~dl_reset) begin
         trans_out_cnt_16 <= 16'h0;
    end
    else if (grp_dataflow_wrapper_fu_6443.task_compute_attn_U0.grp_do_attn_1_fu_5150.do_matmul_2_U0.ap_done == 1'b1 && grp_dataflow_wrapper_fu_6443.task_compute_attn_U0.grp_do_attn_1_fu_5150.do_matmul_2_U0.ap_continue == 1'b1) begin
        trans_out_cnt_16 <= trans_out_cnt_16 + 16'h1;
    end
    else begin
        trans_out_cnt_16 <= trans_out_cnt_16;
    end
end

reg [15:0] trans_in_cnt_17;// for process grp_dataflow_wrapper_fu_6443.task_compute_attn_U0.grp_do_attn_1_fu_5150.do_matmul_2_1_U0
always @(negedge dl_reset or posedge dl_clock) begin
    if (~dl_reset) begin
         trans_in_cnt_17 <= 16'h0;
    end
    else if (grp_dataflow_wrapper_fu_6443.task_compute_attn_U0.grp_do_attn_1_fu_5150.do_matmul_2_1_U0.start_write == 1'b1) begin
        trans_in_cnt_17 <= trans_in_cnt_17 + 16'h1;
    end
    else begin
        trans_in_cnt_17 <= trans_in_cnt_17;
    end
end

reg [15:0] trans_out_cnt_17;// for process grp_dataflow_wrapper_fu_6443.task_compute_attn_U0.grp_do_attn_1_fu_5150.do_matmul_2_1_U0
always @(negedge dl_reset or posedge dl_clock) begin
    if (~dl_reset) begin
         trans_out_cnt_17 <= 16'h0;
    end
    else if (grp_dataflow_wrapper_fu_6443.task_compute_attn_U0.grp_do_attn_1_fu_5150.do_matmul_2_1_U0.ap_done == 1'b1 && grp_dataflow_wrapper_fu_6443.task_compute_attn_U0.grp_do_attn_1_fu_5150.do_matmul_2_1_U0.ap_continue == 1'b1) begin
        trans_out_cnt_17 <= trans_out_cnt_17 + 16'h1;
    end
    else begin
        trans_out_cnt_17 <= trans_out_cnt_17;
    end
end

reg [15:0] trans_in_cnt_18;// for process grp_dataflow_wrapper_fu_6443.task_compute_attn_U0.grp_do_attn_1_fu_5150.do_matmul_4_U0
always @(negedge dl_reset or posedge dl_clock) begin
    if (~dl_reset) begin
         trans_in_cnt_18 <= 16'h0;
    end
    else if (grp_dataflow_wrapper_fu_6443.task_compute_attn_U0.grp_do_attn_1_fu_5150.do_matmul_4_U0.start_write == 1'b1) begin
        trans_in_cnt_18 <= trans_in_cnt_18 + 16'h1;
    end
    else begin
        trans_in_cnt_18 <= trans_in_cnt_18;
    end
end

reg [15:0] trans_out_cnt_18;// for process grp_dataflow_wrapper_fu_6443.task_compute_attn_U0.grp_do_attn_1_fu_5150.do_matmul_4_U0
always @(negedge dl_reset or posedge dl_clock) begin
    if (~dl_reset) begin
         trans_out_cnt_18 <= 16'h0;
    end
    else if (grp_dataflow_wrapper_fu_6443.task_compute_attn_U0.grp_do_attn_1_fu_5150.do_matmul_4_U0.ap_done == 1'b1 && grp_dataflow_wrapper_fu_6443.task_compute_attn_U0.grp_do_attn_1_fu_5150.do_matmul_4_U0.ap_continue == 1'b1) begin
        trans_out_cnt_18 <= trans_out_cnt_18 + 16'h1;
    end
    else begin
        trans_out_cnt_18 <= trans_out_cnt_18;
    end
end

reg [15:0] trans_in_cnt_19;// for process grp_dataflow_wrapper_fu_6443.task_compute_attn_U0.grp_do_attn_1_fu_5150.do_quant_U0
always @(negedge dl_reset or posedge dl_clock) begin
    if (~dl_reset) begin
         trans_in_cnt_19 <= 16'h0;
    end
    else if (grp_dataflow_wrapper_fu_6443.task_compute_attn_U0.grp_do_attn_1_fu_5150.do_quant_U0.start_write == 1'b1) begin
        trans_in_cnt_19 <= trans_in_cnt_19 + 16'h1;
    end
    else begin
        trans_in_cnt_19 <= trans_in_cnt_19;
    end
end

reg [15:0] trans_out_cnt_19;// for process grp_dataflow_wrapper_fu_6443.task_compute_attn_U0.grp_do_attn_1_fu_5150.do_quant_U0
always @(negedge dl_reset or posedge dl_clock) begin
    if (~dl_reset) begin
         trans_out_cnt_19 <= 16'h0;
    end
    else if (grp_dataflow_wrapper_fu_6443.task_compute_attn_U0.grp_do_attn_1_fu_5150.do_quant_U0.ap_done == 1'b1 && grp_dataflow_wrapper_fu_6443.task_compute_attn_U0.grp_do_attn_1_fu_5150.do_quant_U0.ap_continue == 1'b1) begin
        trans_out_cnt_19 <= trans_out_cnt_19 + 16'h1;
    end
    else begin
        trans_out_cnt_19 <= trans_out_cnt_19;
    end
end

reg [15:0] trans_in_cnt_20;// for process grp_dataflow_wrapper_fu_6443.task_compute_attn_U0.grp_do_attn_1_fu_5150.do_quant_3_U0
always @(negedge dl_reset or posedge dl_clock) begin
    if (~dl_reset) begin
         trans_in_cnt_20 <= 16'h0;
    end
    else if (grp_dataflow_wrapper_fu_6443.task_compute_attn_U0.grp_do_attn_1_fu_5150.do_quant_3_U0.start_write == 1'b1) begin
        trans_in_cnt_20 <= trans_in_cnt_20 + 16'h1;
    end
    else begin
        trans_in_cnt_20 <= trans_in_cnt_20;
    end
end

reg [15:0] trans_out_cnt_20;// for process grp_dataflow_wrapper_fu_6443.task_compute_attn_U0.grp_do_attn_1_fu_5150.do_quant_3_U0
always @(negedge dl_reset or posedge dl_clock) begin
    if (~dl_reset) begin
         trans_out_cnt_20 <= 16'h0;
    end
    else if (grp_dataflow_wrapper_fu_6443.task_compute_attn_U0.grp_do_attn_1_fu_5150.do_quant_3_U0.ap_done == 1'b1 && grp_dataflow_wrapper_fu_6443.task_compute_attn_U0.grp_do_attn_1_fu_5150.do_quant_3_U0.ap_continue == 1'b1) begin
        trans_out_cnt_20 <= trans_out_cnt_20 + 16'h1;
    end
    else begin
        trans_out_cnt_20 <= trans_out_cnt_20;
    end
end

reg [15:0] trans_in_cnt_21;// for process grp_dataflow_wrapper_fu_6443.task_compute_attn_U0.grp_do_attn_1_fu_5150.do_quant_1_U0
always @(negedge dl_reset or posedge dl_clock) begin
    if (~dl_reset) begin
         trans_in_cnt_21 <= 16'h0;
    end
    else if (grp_dataflow_wrapper_fu_6443.task_compute_attn_U0.grp_do_attn_1_fu_5150.do_quant_1_U0.start_write == 1'b1) begin
        trans_in_cnt_21 <= trans_in_cnt_21 + 16'h1;
    end
    else begin
        trans_in_cnt_21 <= trans_in_cnt_21;
    end
end

reg [15:0] trans_out_cnt_21;// for process grp_dataflow_wrapper_fu_6443.task_compute_attn_U0.grp_do_attn_1_fu_5150.do_quant_1_U0
always @(negedge dl_reset or posedge dl_clock) begin
    if (~dl_reset) begin
         trans_out_cnt_21 <= 16'h0;
    end
    else if (grp_dataflow_wrapper_fu_6443.task_compute_attn_U0.grp_do_attn_1_fu_5150.do_quant_1_U0.ap_done == 1'b1 && grp_dataflow_wrapper_fu_6443.task_compute_attn_U0.grp_do_attn_1_fu_5150.do_quant_1_U0.ap_continue == 1'b1) begin
        trans_out_cnt_21 <= trans_out_cnt_21 + 16'h1;
    end
    else begin
        trans_out_cnt_21 <= trans_out_cnt_21;
    end
end

reg [15:0] trans_in_cnt_22;// for process grp_dataflow_wrapper_fu_6443.task_compute_attn_U0.grp_do_attn_1_fu_5150.do_split_4_U0
always @(negedge dl_reset or posedge dl_clock) begin
    if (~dl_reset) begin
         trans_in_cnt_22 <= 16'h0;
    end
    else if (grp_dataflow_wrapper_fu_6443.task_compute_attn_U0.grp_do_attn_1_fu_5150.do_split_4_U0.start_write == 1'b1) begin
        trans_in_cnt_22 <= trans_in_cnt_22 + 16'h1;
    end
    else begin
        trans_in_cnt_22 <= trans_in_cnt_22;
    end
end

reg [15:0] trans_out_cnt_22;// for process grp_dataflow_wrapper_fu_6443.task_compute_attn_U0.grp_do_attn_1_fu_5150.do_split_4_U0
always @(negedge dl_reset or posedge dl_clock) begin
    if (~dl_reset) begin
         trans_out_cnt_22 <= 16'h0;
    end
    else if (grp_dataflow_wrapper_fu_6443.task_compute_attn_U0.grp_do_attn_1_fu_5150.do_split_4_U0.ap_done == 1'b1 && grp_dataflow_wrapper_fu_6443.task_compute_attn_U0.grp_do_attn_1_fu_5150.do_split_4_U0.ap_continue == 1'b1) begin
        trans_out_cnt_22 <= trans_out_cnt_22 + 16'h1;
    end
    else begin
        trans_out_cnt_22 <= trans_out_cnt_22;
    end
end

reg [15:0] trans_in_cnt_23;// for process grp_dataflow_wrapper_fu_6443.task_compute_attn_U0.grp_do_attn_1_fu_5150.do_attn_6_U0
always @(negedge dl_reset or posedge dl_clock) begin
    if (~dl_reset) begin
         trans_in_cnt_23 <= 16'h0;
    end
    else if (grp_dataflow_wrapper_fu_6443.task_compute_attn_U0.grp_do_attn_1_fu_5150.do_attn_6_U0.start_write == 1'b1) begin
        trans_in_cnt_23 <= trans_in_cnt_23 + 16'h1;
    end
    else begin
        trans_in_cnt_23 <= trans_in_cnt_23;
    end
end

reg [15:0] trans_out_cnt_23;// for process grp_dataflow_wrapper_fu_6443.task_compute_attn_U0.grp_do_attn_1_fu_5150.do_attn_6_U0
always @(negedge dl_reset or posedge dl_clock) begin
    if (~dl_reset) begin
         trans_out_cnt_23 <= 16'h0;
    end
    else if (grp_dataflow_wrapper_fu_6443.task_compute_attn_U0.grp_do_attn_1_fu_5150.do_attn_6_U0.ap_done == 1'b1 && grp_dataflow_wrapper_fu_6443.task_compute_attn_U0.grp_do_attn_1_fu_5150.do_attn_6_U0.ap_continue == 1'b1) begin
        trans_out_cnt_23 <= trans_out_cnt_23 + 16'h1;
    end
    else begin
        trans_out_cnt_23 <= trans_out_cnt_23;
    end
end

reg [15:0] trans_in_cnt_24;// for process grp_dataflow_wrapper_fu_6443.task_compute_attn_U0.grp_do_attn_1_fu_5150.do_merge_U0
always @(negedge dl_reset or posedge dl_clock) begin
    if (~dl_reset) begin
         trans_in_cnt_24 <= 16'h0;
    end
    else if (grp_dataflow_wrapper_fu_6443.task_compute_attn_U0.grp_do_attn_1_fu_5150.do_merge_U0.start_write == 1'b1) begin
        trans_in_cnt_24 <= trans_in_cnt_24 + 16'h1;
    end
    else begin
        trans_in_cnt_24 <= trans_in_cnt_24;
    end
end

reg [15:0] trans_out_cnt_24;// for process grp_dataflow_wrapper_fu_6443.task_compute_attn_U0.grp_do_attn_1_fu_5150.do_merge_U0
always @(negedge dl_reset or posedge dl_clock) begin
    if (~dl_reset) begin
         trans_out_cnt_24 <= 16'h0;
    end
    else if (grp_dataflow_wrapper_fu_6443.task_compute_attn_U0.grp_do_attn_1_fu_5150.do_merge_U0.ap_done == 1'b1 && grp_dataflow_wrapper_fu_6443.task_compute_attn_U0.grp_do_attn_1_fu_5150.do_merge_U0.ap_continue == 1'b1) begin
        trans_out_cnt_24 <= trans_out_cnt_24 + 16'h1;
    end
    else begin
        trans_out_cnt_24 <= trans_out_cnt_24;
    end
end

reg [15:0] trans_in_cnt_25;// for process grp_dataflow_wrapper_fu_6443.task_compute_attn_U0.grp_do_attn_1_fu_5150.do_quant_2_U0
always @(negedge dl_reset or posedge dl_clock) begin
    if (~dl_reset) begin
         trans_in_cnt_25 <= 16'h0;
    end
    else if (grp_dataflow_wrapper_fu_6443.task_compute_attn_U0.grp_do_attn_1_fu_5150.do_quant_2_U0.start_write == 1'b1) begin
        trans_in_cnt_25 <= trans_in_cnt_25 + 16'h1;
    end
    else begin
        trans_in_cnt_25 <= trans_in_cnt_25;
    end
end

reg [15:0] trans_out_cnt_25;// for process grp_dataflow_wrapper_fu_6443.task_compute_attn_U0.grp_do_attn_1_fu_5150.do_quant_2_U0
always @(negedge dl_reset or posedge dl_clock) begin
    if (~dl_reset) begin
         trans_out_cnt_25 <= 16'h0;
    end
    else if (grp_dataflow_wrapper_fu_6443.task_compute_attn_U0.grp_do_attn_1_fu_5150.do_quant_2_U0.ap_done == 1'b1 && grp_dataflow_wrapper_fu_6443.task_compute_attn_U0.grp_do_attn_1_fu_5150.do_quant_2_U0.ap_continue == 1'b1) begin
        trans_out_cnt_25 <= trans_out_cnt_25 + 16'h1;
    end
    else begin
        trans_out_cnt_25 <= trans_out_cnt_25;
    end
end

reg [15:0] trans_in_cnt_26;// for process grp_dataflow_wrapper_fu_6443.task_compute_attn_U0.grp_do_attn_1_fu_5150.do_matmul_1_U0.do_adapt_1_U0
always @(negedge dl_reset or posedge dl_clock) begin
    if (~dl_reset) begin
         trans_in_cnt_26 <= 16'h0;
    end
    else if (grp_dataflow_wrapper_fu_6443.task_compute_attn_U0.grp_do_attn_1_fu_5150.do_matmul_1_U0.do_adapt_1_U0.start_write == 1'b1) begin
        trans_in_cnt_26 <= trans_in_cnt_26 + 16'h1;
    end
    else begin
        trans_in_cnt_26 <= trans_in_cnt_26;
    end
end

reg [15:0] trans_out_cnt_26;// for process grp_dataflow_wrapper_fu_6443.task_compute_attn_U0.grp_do_attn_1_fu_5150.do_matmul_1_U0.do_adapt_1_U0
always @(negedge dl_reset or posedge dl_clock) begin
    if (~dl_reset) begin
         trans_out_cnt_26 <= 16'h0;
    end
    else if (grp_dataflow_wrapper_fu_6443.task_compute_attn_U0.grp_do_attn_1_fu_5150.do_matmul_1_U0.do_adapt_1_U0.ap_done == 1'b1 && grp_dataflow_wrapper_fu_6443.task_compute_attn_U0.grp_do_attn_1_fu_5150.do_matmul_1_U0.do_adapt_1_U0.ap_continue == 1'b1) begin
        trans_out_cnt_26 <= trans_out_cnt_26 + 16'h1;
    end
    else begin
        trans_out_cnt_26 <= trans_out_cnt_26;
    end
end

reg [15:0] trans_in_cnt_27;// for process grp_dataflow_wrapper_fu_6443.task_compute_attn_U0.grp_do_attn_1_fu_5150.do_matmul_1_U0.matmul_step1_cache_window_1_U0
always @(negedge dl_reset or posedge dl_clock) begin
    if (~dl_reset) begin
         trans_in_cnt_27 <= 16'h0;
    end
    else if (grp_dataflow_wrapper_fu_6443.task_compute_attn_U0.grp_do_attn_1_fu_5150.do_matmul_1_U0.matmul_step1_cache_window_1_U0.start_write == 1'b1) begin
        trans_in_cnt_27 <= trans_in_cnt_27 + 16'h1;
    end
    else begin
        trans_in_cnt_27 <= trans_in_cnt_27;
    end
end

reg [15:0] trans_out_cnt_27;// for process grp_dataflow_wrapper_fu_6443.task_compute_attn_U0.grp_do_attn_1_fu_5150.do_matmul_1_U0.matmul_step1_cache_window_1_U0
always @(negedge dl_reset or posedge dl_clock) begin
    if (~dl_reset) begin
         trans_out_cnt_27 <= 16'h0;
    end
    else if (grp_dataflow_wrapper_fu_6443.task_compute_attn_U0.grp_do_attn_1_fu_5150.do_matmul_1_U0.matmul_step1_cache_window_1_U0.ap_done == 1'b1 && grp_dataflow_wrapper_fu_6443.task_compute_attn_U0.grp_do_attn_1_fu_5150.do_matmul_1_U0.matmul_step1_cache_window_1_U0.ap_continue == 1'b1) begin
        trans_out_cnt_27 <= trans_out_cnt_27 + 16'h1;
    end
    else begin
        trans_out_cnt_27 <= trans_out_cnt_27;
    end
end

reg [15:0] trans_in_cnt_28;// for process grp_dataflow_wrapper_fu_6443.task_compute_attn_U0.grp_do_attn_1_fu_5150.do_matmul_1_U0.matmul_step2_mac_1_U0
always @(negedge dl_reset or posedge dl_clock) begin
    if (~dl_reset) begin
         trans_in_cnt_28 <= 16'h0;
    end
    else if (grp_dataflow_wrapper_fu_6443.task_compute_attn_U0.grp_do_attn_1_fu_5150.do_matmul_1_U0.matmul_step2_mac_1_U0.start_write == 1'b1) begin
        trans_in_cnt_28 <= trans_in_cnt_28 + 16'h1;
    end
    else begin
        trans_in_cnt_28 <= trans_in_cnt_28;
    end
end

reg [15:0] trans_out_cnt_28;// for process grp_dataflow_wrapper_fu_6443.task_compute_attn_U0.grp_do_attn_1_fu_5150.do_matmul_1_U0.matmul_step2_mac_1_U0
always @(negedge dl_reset or posedge dl_clock) begin
    if (~dl_reset) begin
         trans_out_cnt_28 <= 16'h0;
    end
    else if (grp_dataflow_wrapper_fu_6443.task_compute_attn_U0.grp_do_attn_1_fu_5150.do_matmul_1_U0.matmul_step2_mac_1_U0.ap_done == 1'b1 && grp_dataflow_wrapper_fu_6443.task_compute_attn_U0.grp_do_attn_1_fu_5150.do_matmul_1_U0.matmul_step2_mac_1_U0.ap_continue == 1'b1) begin
        trans_out_cnt_28 <= trans_out_cnt_28 + 16'h1;
    end
    else begin
        trans_out_cnt_28 <= trans_out_cnt_28;
    end
end

reg [15:0] trans_in_cnt_29;// for process grp_dataflow_wrapper_fu_6443.task_compute_attn_U0.grp_do_attn_1_fu_5150.do_adapt_7_U0
always @(negedge dl_reset or posedge dl_clock) begin
    if (~dl_reset) begin
         trans_in_cnt_29 <= 16'h0;
    end
    else if (grp_dataflow_wrapper_fu_6443.task_compute_attn_U0.grp_do_attn_1_fu_5150.do_adapt_7_U0.start_write == 1'b1) begin
        trans_in_cnt_29 <= trans_in_cnt_29 + 16'h1;
    end
    else begin
        trans_in_cnt_29 <= trans_in_cnt_29;
    end
end

reg [15:0] trans_out_cnt_29;// for process grp_dataflow_wrapper_fu_6443.task_compute_attn_U0.grp_do_attn_1_fu_5150.do_adapt_7_U0
always @(negedge dl_reset or posedge dl_clock) begin
    if (~dl_reset) begin
         trans_out_cnt_29 <= 16'h0;
    end
    else if (grp_dataflow_wrapper_fu_6443.task_compute_attn_U0.grp_do_attn_1_fu_5150.do_adapt_7_U0.ap_done == 1'b1 && grp_dataflow_wrapper_fu_6443.task_compute_attn_U0.grp_do_attn_1_fu_5150.do_adapt_7_U0.ap_continue == 1'b1) begin
        trans_out_cnt_29 <= trans_out_cnt_29 + 16'h1;
    end
    else begin
        trans_out_cnt_29 <= trans_out_cnt_29;
    end
end

reg [15:0] trans_in_cnt_30;// for process grp_dataflow_wrapper_fu_6443.task_compute_attn_U0
always @(negedge dl_reset or posedge dl_clock) begin
    if (~dl_reset) begin
         trans_in_cnt_30 <= 16'h0;
    end
    else if (grp_dataflow_wrapper_fu_6443.task_compute_attn_U0.start_write == 1'b1) begin
        trans_in_cnt_30 <= trans_in_cnt_30 + 16'h1;
    end
    else begin
        trans_in_cnt_30 <= trans_in_cnt_30;
    end
end

reg [15:0] trans_out_cnt_30;// for process grp_dataflow_wrapper_fu_6443.task_compute_attn_U0
always @(negedge dl_reset or posedge dl_clock) begin
    if (~dl_reset) begin
         trans_out_cnt_30 <= 16'h0;
    end
    else if (grp_dataflow_wrapper_fu_6443.task_compute_attn_U0.ap_done == 1'b1 && grp_dataflow_wrapper_fu_6443.task_compute_attn_U0.ap_continue == 1'b1) begin
        trans_out_cnt_30 <= trans_out_cnt_30 + 16'h1;
    end
    else begin
        trans_out_cnt_30 <= trans_out_cnt_30;
    end
end

reg [15:0] trans_in_cnt_31;// for process grp_dataflow_wrapper_fu_6443.task_compute_mlp_U0.grp_do_mlp_fu_4710.stream_copy_U0
always @(negedge dl_reset or posedge dl_clock) begin
    if (~dl_reset) begin
         trans_in_cnt_31 <= 16'h0;
    end
    else if (grp_dataflow_wrapper_fu_6443.task_compute_mlp_U0.grp_do_mlp_fu_4710.stream_copy_U0.start_write == 1'b1) begin
        trans_in_cnt_31 <= trans_in_cnt_31 + 16'h1;
    end
    else begin
        trans_in_cnt_31 <= trans_in_cnt_31;
    end
end

reg [15:0] trans_out_cnt_31;// for process grp_dataflow_wrapper_fu_6443.task_compute_mlp_U0.grp_do_mlp_fu_4710.stream_copy_U0
always @(negedge dl_reset or posedge dl_clock) begin
    if (~dl_reset) begin
         trans_out_cnt_31 <= 16'h0;
    end
    else if (grp_dataflow_wrapper_fu_6443.task_compute_mlp_U0.grp_do_mlp_fu_4710.stream_copy_U0.ap_done == 1'b1 && grp_dataflow_wrapper_fu_6443.task_compute_mlp_U0.grp_do_mlp_fu_4710.stream_copy_U0.ap_continue == 1'b1) begin
        trans_out_cnt_31 <= trans_out_cnt_31 + 16'h1;
    end
    else begin
        trans_out_cnt_31 <= trans_out_cnt_31;
    end
end

reg [15:0] trans_in_cnt_32;// for process grp_dataflow_wrapper_fu_6443.task_compute_mlp_U0.grp_do_mlp_fu_4710.do_adapt_6_U0
always @(negedge dl_reset or posedge dl_clock) begin
    if (~dl_reset) begin
         trans_in_cnt_32 <= 16'h0;
    end
    else if (grp_dataflow_wrapper_fu_6443.task_compute_mlp_U0.grp_do_mlp_fu_4710.do_adapt_6_U0.start_write == 1'b1) begin
        trans_in_cnt_32 <= trans_in_cnt_32 + 16'h1;
    end
    else begin
        trans_in_cnt_32 <= trans_in_cnt_32;
    end
end

reg [15:0] trans_out_cnt_32;// for process grp_dataflow_wrapper_fu_6443.task_compute_mlp_U0.grp_do_mlp_fu_4710.do_adapt_6_U0
always @(negedge dl_reset or posedge dl_clock) begin
    if (~dl_reset) begin
         trans_out_cnt_32 <= 16'h0;
    end
    else if (grp_dataflow_wrapper_fu_6443.task_compute_mlp_U0.grp_do_mlp_fu_4710.do_adapt_6_U0.ap_done == 1'b1 && grp_dataflow_wrapper_fu_6443.task_compute_mlp_U0.grp_do_mlp_fu_4710.do_adapt_6_U0.ap_continue == 1'b1) begin
        trans_out_cnt_32 <= trans_out_cnt_32 + 16'h1;
    end
    else begin
        trans_out_cnt_32 <= trans_out_cnt_32;
    end
end

reg [15:0] trans_in_cnt_33;// for process grp_dataflow_wrapper_fu_6443.task_compute_mlp_U0.grp_do_mlp_fu_4710.do_layernorm_inter_token_U0
always @(negedge dl_reset or posedge dl_clock) begin
    if (~dl_reset) begin
         trans_in_cnt_33 <= 16'h0;
    end
    else if (grp_dataflow_wrapper_fu_6443.task_compute_mlp_U0.grp_do_mlp_fu_4710.do_layernorm_inter_token_U0.start_write == 1'b1) begin
        trans_in_cnt_33 <= trans_in_cnt_33 + 16'h1;
    end
    else begin
        trans_in_cnt_33 <= trans_in_cnt_33;
    end
end

reg [15:0] trans_out_cnt_33;// for process grp_dataflow_wrapper_fu_6443.task_compute_mlp_U0.grp_do_mlp_fu_4710.do_layernorm_inter_token_U0
always @(negedge dl_reset or posedge dl_clock) begin
    if (~dl_reset) begin
         trans_out_cnt_33 <= 16'h0;
    end
    else if (grp_dataflow_wrapper_fu_6443.task_compute_mlp_U0.grp_do_mlp_fu_4710.do_layernorm_inter_token_U0.ap_done == 1'b1 && grp_dataflow_wrapper_fu_6443.task_compute_mlp_U0.grp_do_mlp_fu_4710.do_layernorm_inter_token_U0.ap_continue == 1'b1) begin
        trans_out_cnt_33 <= trans_out_cnt_33 + 16'h1;
    end
    else begin
        trans_out_cnt_33 <= trans_out_cnt_33;
    end
end

reg [15:0] trans_in_cnt_34;// for process grp_dataflow_wrapper_fu_6443.task_compute_mlp_U0.grp_do_mlp_fu_4710.do_matmul_3_U0.do_adapt_1_1_U0
always @(negedge dl_reset or posedge dl_clock) begin
    if (~dl_reset) begin
         trans_in_cnt_34 <= 16'h0;
    end
    else if (grp_dataflow_wrapper_fu_6443.task_compute_mlp_U0.grp_do_mlp_fu_4710.do_matmul_3_U0.do_adapt_1_1_U0.start_write == 1'b1) begin
        trans_in_cnt_34 <= trans_in_cnt_34 + 16'h1;
    end
    else begin
        trans_in_cnt_34 <= trans_in_cnt_34;
    end
end

reg [15:0] trans_out_cnt_34;// for process grp_dataflow_wrapper_fu_6443.task_compute_mlp_U0.grp_do_mlp_fu_4710.do_matmul_3_U0.do_adapt_1_1_U0
always @(negedge dl_reset or posedge dl_clock) begin
    if (~dl_reset) begin
         trans_out_cnt_34 <= 16'h0;
    end
    else if (grp_dataflow_wrapper_fu_6443.task_compute_mlp_U0.grp_do_mlp_fu_4710.do_matmul_3_U0.do_adapt_1_1_U0.ap_done == 1'b1 && grp_dataflow_wrapper_fu_6443.task_compute_mlp_U0.grp_do_mlp_fu_4710.do_matmul_3_U0.do_adapt_1_1_U0.ap_continue == 1'b1) begin
        trans_out_cnt_34 <= trans_out_cnt_34 + 16'h1;
    end
    else begin
        trans_out_cnt_34 <= trans_out_cnt_34;
    end
end

reg [15:0] trans_in_cnt_35;// for process grp_dataflow_wrapper_fu_6443.task_compute_mlp_U0.grp_do_mlp_fu_4710.do_matmul_3_U0.matmul_step1_cache_window_3_U0
always @(negedge dl_reset or posedge dl_clock) begin
    if (~dl_reset) begin
         trans_in_cnt_35 <= 16'h0;
    end
    else if (grp_dataflow_wrapper_fu_6443.task_compute_mlp_U0.grp_do_mlp_fu_4710.do_matmul_3_U0.matmul_step1_cache_window_3_U0.start_write == 1'b1) begin
        trans_in_cnt_35 <= trans_in_cnt_35 + 16'h1;
    end
    else begin
        trans_in_cnt_35 <= trans_in_cnt_35;
    end
end

reg [15:0] trans_out_cnt_35;// for process grp_dataflow_wrapper_fu_6443.task_compute_mlp_U0.grp_do_mlp_fu_4710.do_matmul_3_U0.matmul_step1_cache_window_3_U0
always @(negedge dl_reset or posedge dl_clock) begin
    if (~dl_reset) begin
         trans_out_cnt_35 <= 16'h0;
    end
    else if (grp_dataflow_wrapper_fu_6443.task_compute_mlp_U0.grp_do_mlp_fu_4710.do_matmul_3_U0.matmul_step1_cache_window_3_U0.ap_done == 1'b1 && grp_dataflow_wrapper_fu_6443.task_compute_mlp_U0.grp_do_mlp_fu_4710.do_matmul_3_U0.matmul_step1_cache_window_3_U0.ap_continue == 1'b1) begin
        trans_out_cnt_35 <= trans_out_cnt_35 + 16'h1;
    end
    else begin
        trans_out_cnt_35 <= trans_out_cnt_35;
    end
end

reg [15:0] trans_in_cnt_36;// for process grp_dataflow_wrapper_fu_6443.task_compute_mlp_U0.grp_do_mlp_fu_4710.do_matmul_3_U0.matmul_step2_mac_3_U0
always @(negedge dl_reset or posedge dl_clock) begin
    if (~dl_reset) begin
         trans_in_cnt_36 <= 16'h0;
    end
    else if (grp_dataflow_wrapper_fu_6443.task_compute_mlp_U0.grp_do_mlp_fu_4710.do_matmul_3_U0.matmul_step2_mac_3_U0.start_write == 1'b1) begin
        trans_in_cnt_36 <= trans_in_cnt_36 + 16'h1;
    end
    else begin
        trans_in_cnt_36 <= trans_in_cnt_36;
    end
end

reg [15:0] trans_out_cnt_36;// for process grp_dataflow_wrapper_fu_6443.task_compute_mlp_U0.grp_do_mlp_fu_4710.do_matmul_3_U0.matmul_step2_mac_3_U0
always @(negedge dl_reset or posedge dl_clock) begin
    if (~dl_reset) begin
         trans_out_cnt_36 <= 16'h0;
    end
    else if (grp_dataflow_wrapper_fu_6443.task_compute_mlp_U0.grp_do_mlp_fu_4710.do_matmul_3_U0.matmul_step2_mac_3_U0.ap_done == 1'b1 && grp_dataflow_wrapper_fu_6443.task_compute_mlp_U0.grp_do_mlp_fu_4710.do_matmul_3_U0.matmul_step2_mac_3_U0.ap_continue == 1'b1) begin
        trans_out_cnt_36 <= trans_out_cnt_36 + 16'h1;
    end
    else begin
        trans_out_cnt_36 <= trans_out_cnt_36;
    end
end

reg [15:0] trans_in_cnt_37;// for process grp_dataflow_wrapper_fu_6443.task_compute_mlp_U0.grp_do_mlp_fu_4710.do_matmul_3_U0
always @(negedge dl_reset or posedge dl_clock) begin
    if (~dl_reset) begin
         trans_in_cnt_37 <= 16'h0;
    end
    else if (grp_dataflow_wrapper_fu_6443.task_compute_mlp_U0.grp_do_mlp_fu_4710.do_matmul_3_U0.start_write == 1'b1) begin
        trans_in_cnt_37 <= trans_in_cnt_37 + 16'h1;
    end
    else begin
        trans_in_cnt_37 <= trans_in_cnt_37;
    end
end

reg [15:0] trans_out_cnt_37;// for process grp_dataflow_wrapper_fu_6443.task_compute_mlp_U0.grp_do_mlp_fu_4710.do_matmul_3_U0
always @(negedge dl_reset or posedge dl_clock) begin
    if (~dl_reset) begin
         trans_out_cnt_37 <= 16'h0;
    end
    else if (grp_dataflow_wrapper_fu_6443.task_compute_mlp_U0.grp_do_mlp_fu_4710.do_matmul_3_U0.ap_done == 1'b1 && grp_dataflow_wrapper_fu_6443.task_compute_mlp_U0.grp_do_mlp_fu_4710.do_matmul_3_U0.ap_continue == 1'b1) begin
        trans_out_cnt_37 <= trans_out_cnt_37 + 16'h1;
    end
    else begin
        trans_out_cnt_37 <= trans_out_cnt_37;
    end
end

reg [15:0] trans_in_cnt_38;// for process grp_dataflow_wrapper_fu_6443.task_compute_mlp_U0.grp_do_mlp_fu_4710.do_gelu_U0
always @(negedge dl_reset or posedge dl_clock) begin
    if (~dl_reset) begin
         trans_in_cnt_38 <= 16'h0;
    end
    else if (grp_dataflow_wrapper_fu_6443.task_compute_mlp_U0.grp_do_mlp_fu_4710.do_gelu_U0.start_write == 1'b1) begin
        trans_in_cnt_38 <= trans_in_cnt_38 + 16'h1;
    end
    else begin
        trans_in_cnt_38 <= trans_in_cnt_38;
    end
end

reg [15:0] trans_out_cnt_38;// for process grp_dataflow_wrapper_fu_6443.task_compute_mlp_U0.grp_do_mlp_fu_4710.do_gelu_U0
always @(negedge dl_reset or posedge dl_clock) begin
    if (~dl_reset) begin
         trans_out_cnt_38 <= 16'h0;
    end
    else if (grp_dataflow_wrapper_fu_6443.task_compute_mlp_U0.grp_do_mlp_fu_4710.do_gelu_U0.ap_done == 1'b1 && grp_dataflow_wrapper_fu_6443.task_compute_mlp_U0.grp_do_mlp_fu_4710.do_gelu_U0.ap_continue == 1'b1) begin
        trans_out_cnt_38 <= trans_out_cnt_38 + 16'h1;
    end
    else begin
        trans_out_cnt_38 <= trans_out_cnt_38;
    end
end

reg [15:0] trans_in_cnt_39;// for process grp_dataflow_wrapper_fu_6443.task_compute_mlp_U0.grp_do_mlp_fu_4710.do_matmul_U0.do_adapt_U0
always @(negedge dl_reset or posedge dl_clock) begin
    if (~dl_reset) begin
         trans_in_cnt_39 <= 16'h0;
    end
    else if (grp_dataflow_wrapper_fu_6443.task_compute_mlp_U0.grp_do_mlp_fu_4710.do_matmul_U0.do_adapt_U0.start_write == 1'b1) begin
        trans_in_cnt_39 <= trans_in_cnt_39 + 16'h1;
    end
    else begin
        trans_in_cnt_39 <= trans_in_cnt_39;
    end
end

reg [15:0] trans_out_cnt_39;// for process grp_dataflow_wrapper_fu_6443.task_compute_mlp_U0.grp_do_mlp_fu_4710.do_matmul_U0.do_adapt_U0
always @(negedge dl_reset or posedge dl_clock) begin
    if (~dl_reset) begin
         trans_out_cnt_39 <= 16'h0;
    end
    else if (grp_dataflow_wrapper_fu_6443.task_compute_mlp_U0.grp_do_mlp_fu_4710.do_matmul_U0.do_adapt_U0.ap_done == 1'b1 && grp_dataflow_wrapper_fu_6443.task_compute_mlp_U0.grp_do_mlp_fu_4710.do_matmul_U0.do_adapt_U0.ap_continue == 1'b1) begin
        trans_out_cnt_39 <= trans_out_cnt_39 + 16'h1;
    end
    else begin
        trans_out_cnt_39 <= trans_out_cnt_39;
    end
end

reg [15:0] trans_in_cnt_40;// for process grp_dataflow_wrapper_fu_6443.task_compute_mlp_U0.grp_do_mlp_fu_4710.do_matmul_U0.matmul_step1_cache_window_U0
always @(negedge dl_reset or posedge dl_clock) begin
    if (~dl_reset) begin
         trans_in_cnt_40 <= 16'h0;
    end
    else if (grp_dataflow_wrapper_fu_6443.task_compute_mlp_U0.grp_do_mlp_fu_4710.do_matmul_U0.matmul_step1_cache_window_U0.start_write == 1'b1) begin
        trans_in_cnt_40 <= trans_in_cnt_40 + 16'h1;
    end
    else begin
        trans_in_cnt_40 <= trans_in_cnt_40;
    end
end

reg [15:0] trans_out_cnt_40;// for process grp_dataflow_wrapper_fu_6443.task_compute_mlp_U0.grp_do_mlp_fu_4710.do_matmul_U0.matmul_step1_cache_window_U0
always @(negedge dl_reset or posedge dl_clock) begin
    if (~dl_reset) begin
         trans_out_cnt_40 <= 16'h0;
    end
    else if (grp_dataflow_wrapper_fu_6443.task_compute_mlp_U0.grp_do_mlp_fu_4710.do_matmul_U0.matmul_step1_cache_window_U0.ap_done == 1'b1 && grp_dataflow_wrapper_fu_6443.task_compute_mlp_U0.grp_do_mlp_fu_4710.do_matmul_U0.matmul_step1_cache_window_U0.ap_continue == 1'b1) begin
        trans_out_cnt_40 <= trans_out_cnt_40 + 16'h1;
    end
    else begin
        trans_out_cnt_40 <= trans_out_cnt_40;
    end
end

reg [15:0] trans_in_cnt_41;// for process grp_dataflow_wrapper_fu_6443.task_compute_mlp_U0.grp_do_mlp_fu_4710.do_matmul_U0.matmul_step2_mac_U0
always @(negedge dl_reset or posedge dl_clock) begin
    if (~dl_reset) begin
         trans_in_cnt_41 <= 16'h0;
    end
    else if (grp_dataflow_wrapper_fu_6443.task_compute_mlp_U0.grp_do_mlp_fu_4710.do_matmul_U0.matmul_step2_mac_U0.start_write == 1'b1) begin
        trans_in_cnt_41 <= trans_in_cnt_41 + 16'h1;
    end
    else begin
        trans_in_cnt_41 <= trans_in_cnt_41;
    end
end

reg [15:0] trans_out_cnt_41;// for process grp_dataflow_wrapper_fu_6443.task_compute_mlp_U0.grp_do_mlp_fu_4710.do_matmul_U0.matmul_step2_mac_U0
always @(negedge dl_reset or posedge dl_clock) begin
    if (~dl_reset) begin
         trans_out_cnt_41 <= 16'h0;
    end
    else if (grp_dataflow_wrapper_fu_6443.task_compute_mlp_U0.grp_do_mlp_fu_4710.do_matmul_U0.matmul_step2_mac_U0.ap_done == 1'b1 && grp_dataflow_wrapper_fu_6443.task_compute_mlp_U0.grp_do_mlp_fu_4710.do_matmul_U0.matmul_step2_mac_U0.ap_continue == 1'b1) begin
        trans_out_cnt_41 <= trans_out_cnt_41 + 16'h1;
    end
    else begin
        trans_out_cnt_41 <= trans_out_cnt_41;
    end
end

reg [15:0] trans_in_cnt_42;// for process grp_dataflow_wrapper_fu_6443.task_compute_mlp_U0.grp_do_mlp_fu_4710.do_adapt_5_U0
always @(negedge dl_reset or posedge dl_clock) begin
    if (~dl_reset) begin
         trans_in_cnt_42 <= 16'h0;
    end
    else if (grp_dataflow_wrapper_fu_6443.task_compute_mlp_U0.grp_do_mlp_fu_4710.do_adapt_5_U0.start_write == 1'b1) begin
        trans_in_cnt_42 <= trans_in_cnt_42 + 16'h1;
    end
    else begin
        trans_in_cnt_42 <= trans_in_cnt_42;
    end
end

reg [15:0] trans_out_cnt_42;// for process grp_dataflow_wrapper_fu_6443.task_compute_mlp_U0.grp_do_mlp_fu_4710.do_adapt_5_U0
always @(negedge dl_reset or posedge dl_clock) begin
    if (~dl_reset) begin
         trans_out_cnt_42 <= 16'h0;
    end
    else if (grp_dataflow_wrapper_fu_6443.task_compute_mlp_U0.grp_do_mlp_fu_4710.do_adapt_5_U0.ap_done == 1'b1 && grp_dataflow_wrapper_fu_6443.task_compute_mlp_U0.grp_do_mlp_fu_4710.do_adapt_5_U0.ap_continue == 1'b1) begin
        trans_out_cnt_42 <= trans_out_cnt_42 + 16'h1;
    end
    else begin
        trans_out_cnt_42 <= trans_out_cnt_42;
    end
end

reg [15:0] trans_in_cnt_43;// for process grp_dataflow_wrapper_fu_6443.task_compute_mlp_U0
always @(negedge dl_reset or posedge dl_clock) begin
    if (~dl_reset) begin
         trans_in_cnt_43 <= 16'h0;
    end
    else if (grp_dataflow_wrapper_fu_6443.task_compute_mlp_U0.start_write == 1'b1) begin
        trans_in_cnt_43 <= trans_in_cnt_43 + 16'h1;
    end
    else begin
        trans_in_cnt_43 <= trans_in_cnt_43;
    end
end

reg [15:0] trans_out_cnt_43;// for process grp_dataflow_wrapper_fu_6443.task_compute_mlp_U0
always @(negedge dl_reset or posedge dl_clock) begin
    if (~dl_reset) begin
         trans_out_cnt_43 <= 16'h0;
    end
    else if (grp_dataflow_wrapper_fu_6443.task_compute_mlp_U0.ap_done == 1'b1 && grp_dataflow_wrapper_fu_6443.task_compute_mlp_U0.ap_continue == 1'b1) begin
        trans_out_cnt_43 <= trans_out_cnt_43 + 16'h1;
    end
    else begin
        trans_out_cnt_43 <= trans_out_cnt_43;
    end
end

reg [15:0] trans_in_cnt_44;// for process grp_task_run_head_fu_11440.task_read_cls_fm_U0
always @(negedge dl_reset or posedge dl_clock) begin
    if (~dl_reset) begin
         trans_in_cnt_44 <= 16'h0;
    end
    else if (grp_task_run_head_fu_11440.task_read_cls_fm_U0.start_write == 1'b1) begin
        trans_in_cnt_44 <= trans_in_cnt_44 + 16'h1;
    end
    else begin
        trans_in_cnt_44 <= trans_in_cnt_44;
    end
end

reg [15:0] trans_out_cnt_44;// for process grp_task_run_head_fu_11440.task_read_cls_fm_U0
always @(negedge dl_reset or posedge dl_clock) begin
    if (~dl_reset) begin
         trans_out_cnt_44 <= 16'h0;
    end
    else if (grp_task_run_head_fu_11440.task_read_cls_fm_U0.ap_done == 1'b1 && grp_task_run_head_fu_11440.task_read_cls_fm_U0.ap_continue == 1'b1) begin
        trans_out_cnt_44 <= trans_out_cnt_44 + 16'h1;
    end
    else begin
        trans_out_cnt_44 <= trans_out_cnt_44;
    end
end

reg [15:0] trans_in_cnt_45;// for process grp_task_run_head_fu_11440.fixed_head_do_head_U0.fixed_head_layernorm_U0
always @(negedge dl_reset or posedge dl_clock) begin
    if (~dl_reset) begin
         trans_in_cnt_45 <= 16'h0;
    end
    else if (grp_task_run_head_fu_11440.fixed_head_do_head_U0.fixed_head_layernorm_U0.start_write == 1'b1) begin
        trans_in_cnt_45 <= trans_in_cnt_45 + 16'h1;
    end
    else begin
        trans_in_cnt_45 <= trans_in_cnt_45;
    end
end

reg [15:0] trans_out_cnt_45;// for process grp_task_run_head_fu_11440.fixed_head_do_head_U0.fixed_head_layernorm_U0
always @(negedge dl_reset or posedge dl_clock) begin
    if (~dl_reset) begin
         trans_out_cnt_45 <= 16'h0;
    end
    else if (grp_task_run_head_fu_11440.fixed_head_do_head_U0.fixed_head_layernorm_U0.ap_done == 1'b1 && grp_task_run_head_fu_11440.fixed_head_do_head_U0.fixed_head_layernorm_U0.ap_continue == 1'b1) begin
        trans_out_cnt_45 <= trans_out_cnt_45 + 16'h1;
    end
    else begin
        trans_out_cnt_45 <= trans_out_cnt_45;
    end
end

reg [15:0] trans_in_cnt_46;// for process grp_task_run_head_fu_11440.fixed_head_do_head_U0.fixed_head_matmul_U0.fixed_head_matmul_core_U0
always @(negedge dl_reset or posedge dl_clock) begin
    if (~dl_reset) begin
         trans_in_cnt_46 <= 16'h0;
    end
    else if (grp_task_run_head_fu_11440.fixed_head_do_head_U0.fixed_head_matmul_U0.fixed_head_matmul_core_U0.start_write == 1'b1) begin
        trans_in_cnt_46 <= trans_in_cnt_46 + 16'h1;
    end
    else begin
        trans_in_cnt_46 <= trans_in_cnt_46;
    end
end

reg [15:0] trans_out_cnt_46;// for process grp_task_run_head_fu_11440.fixed_head_do_head_U0.fixed_head_matmul_U0.fixed_head_matmul_core_U0
always @(negedge dl_reset or posedge dl_clock) begin
    if (~dl_reset) begin
         trans_out_cnt_46 <= 16'h0;
    end
    else if (grp_task_run_head_fu_11440.fixed_head_do_head_U0.fixed_head_matmul_U0.fixed_head_matmul_core_U0.ap_done == 1'b1 && grp_task_run_head_fu_11440.fixed_head_do_head_U0.fixed_head_matmul_U0.fixed_head_matmul_core_U0.ap_continue == 1'b1) begin
        trans_out_cnt_46 <= trans_out_cnt_46 + 16'h1;
    end
    else begin
        trans_out_cnt_46 <= trans_out_cnt_46;
    end
end

reg [15:0] trans_in_cnt_47;// for process grp_task_run_head_fu_11440.fixed_head_do_head_U0
always @(negedge dl_reset or posedge dl_clock) begin
    if (~dl_reset) begin
         trans_in_cnt_47 <= 16'h0;
    end
    else if (grp_task_run_head_fu_11440.fixed_head_do_head_U0.start_write == 1'b1) begin
        trans_in_cnt_47 <= trans_in_cnt_47 + 16'h1;
    end
    else begin
        trans_in_cnt_47 <= trans_in_cnt_47;
    end
end

reg [15:0] trans_out_cnt_47;// for process grp_task_run_head_fu_11440.fixed_head_do_head_U0
always @(negedge dl_reset or posedge dl_clock) begin
    if (~dl_reset) begin
         trans_out_cnt_47 <= 16'h0;
    end
    else if (grp_task_run_head_fu_11440.fixed_head_do_head_U0.ap_done == 1'b1 && grp_task_run_head_fu_11440.fixed_head_do_head_U0.ap_continue == 1'b1) begin
        trans_out_cnt_47 <= trans_out_cnt_47 + 16'h1;
    end
    else begin
        trans_out_cnt_47 <= trans_out_cnt_47;
    end
end

    // Process: grp_initial_overlap_wrapper_fu_5704.task_run_pe_U0
    vit_block_top_hls_deadlock_detect_unit #(74, 0, 1, 1) vit_block_top_hls_deadlock_detect_unit_0 (
        .reset(dl_reset),
        .clock(dl_clock),
        .proc_dep_vld_vec(proc_dep_vld_vec_0),
        .in_chan_dep_vld_vec(in_chan_dep_vld_vec_0),
        .in_chan_dep_data_vec(in_chan_dep_data_vec_0),
        .token_in_vec(token_in_vec_0),
        .dl_detect_in(dl_detect_out),
        .origin(origin[0]),
        .token_clear(token_clear),
        .out_chan_dep_vld_vec(out_chan_dep_vld_vec_0),
        .out_chan_dep_data(out_chan_dep_data_0),
        .token_out_vec(token_out_vec_0),
        .dl_detect_out(dl_in_vec[0]));

    assign proc_0_data_FIFO_blk[0] = 1'b0;
    assign proc_0_data_PIPO_blk[0] = 1'b0;
    assign proc_0_start_FIFO_blk[0] = 1'b0;
    assign proc_0_TLF_FIFO_blk[0] = 1'b0;
    assign proc_0_input_sync_blk[0] = 1'b0 | (grp_initial_overlap_wrapper_fu_5704.ap_sync_task_run_pe_U0_ap_ready & grp_initial_overlap_wrapper_fu_5704.task_run_pe_U0.ap_idle & ~grp_initial_overlap_wrapper_fu_5704.ap_sync_task_load_weights_U0_ap_ready);
    assign proc_0_output_sync_blk[0] = 1'b0 | (ap_done_reg_3 & grp_initial_overlap_wrapper_fu_5704.task_run_pe_U0.ap_done & ~grp_initial_overlap_wrapper_fu_5704.task_load_weights_U0.ap_done);
    assign proc_dep_vld_vec_0[0] = dl_detect_out ? proc_dep_vld_vec_0_reg[0] : (proc_0_data_FIFO_blk[0] | proc_0_data_PIPO_blk[0] | proc_0_start_FIFO_blk[0] | proc_0_TLF_FIFO_blk[0] | proc_0_input_sync_blk[0] | proc_0_output_sync_blk[0]);
    always @ (negedge dl_reset or posedge dl_clock) begin
        if (~dl_reset) begin
            proc_dep_vld_vec_0_reg <= 'b0;
        end
        else begin
            proc_dep_vld_vec_0_reg <= proc_dep_vld_vec_0;
        end
    end
    assign in_chan_dep_vld_vec_0[0] = dep_chan_vld_7_0;
    assign in_chan_dep_data_vec_0[73 : 0] = dep_chan_data_7_0;
    assign token_in_vec_0[0] = token_7_0;
    assign dep_chan_vld_0_7 = out_chan_dep_vld_vec_0[0];
    assign dep_chan_data_0_7 = out_chan_dep_data_0;
    assign token_0_7 = token_out_vec_0[0];

    // Process: grp_initial_overlap_wrapper_fu_5704.task_run_pe_U0.task_recv_img_U0
    vit_block_top_hls_deadlock_detect_unit #(74, 1, 2, 2) vit_block_top_hls_deadlock_detect_unit_1 (
        .reset(dl_reset),
        .clock(dl_clock),
        .proc_dep_vld_vec(proc_dep_vld_vec_1),
        .in_chan_dep_vld_vec(in_chan_dep_vld_vec_1),
        .in_chan_dep_data_vec(in_chan_dep_data_vec_1),
        .token_in_vec(token_in_vec_1),
        .dl_detect_in(dl_detect_out),
        .origin(origin[1]),
        .token_clear(token_clear),
        .out_chan_dep_vld_vec(out_chan_dep_vld_vec_1),
        .out_chan_dep_data(out_chan_dep_data_1),
        .token_out_vec(token_out_vec_1),
        .dl_detect_out(dl_in_vec[1]));

    assign proc_1_data_FIFO_blk[0] = 1'b0 | (~grp_initial_overlap_wrapper_fu_5704.task_run_pe_U0.task_recv_img_U0.img_sm_blk_n);
    assign proc_1_data_PIPO_blk[0] = 1'b0;
    assign proc_1_start_FIFO_blk[0] = 1'b0 | (~grp_initial_overlap_wrapper_fu_5704.task_run_pe_U0.start_for_fixed_patch_do_patch_embed_U0_U.if_full_n & grp_initial_overlap_wrapper_fu_5704.task_run_pe_U0.task_recv_img_U0.ap_start & ~grp_initial_overlap_wrapper_fu_5704.task_run_pe_U0.task_recv_img_U0.real_start & (trans_in_cnt_0 == trans_out_cnt_0) & ~grp_initial_overlap_wrapper_fu_5704.task_run_pe_U0.start_for_fixed_patch_do_patch_embed_U0_U.if_read);
    assign proc_1_TLF_FIFO_blk[0] = 1'b0;
    assign proc_1_input_sync_blk[0] = 1'b0;
    assign proc_1_output_sync_blk[0] = 1'b0;
    assign proc_dep_vld_vec_1[0] = dl_detect_out ? proc_dep_vld_vec_1_reg[0] : (proc_1_data_FIFO_blk[0] | proc_1_data_PIPO_blk[0] | proc_1_start_FIFO_blk[0] | proc_1_TLF_FIFO_blk[0] | proc_1_input_sync_blk[0] | proc_1_output_sync_blk[0]);
    assign proc_1_data_FIFO_blk[1] = 1'b0 | (~grp_initial_overlap_wrapper_fu_5704.task_run_pe_U0.task_recv_img_U0.img_sm_blk_n);
    assign proc_1_data_PIPO_blk[1] = 1'b0;
    assign proc_1_start_FIFO_blk[1] = 1'b0;
    assign proc_1_TLF_FIFO_blk[1] = 1'b0;
    assign proc_1_input_sync_blk[1] = 1'b0;
    assign proc_1_output_sync_blk[1] = 1'b0;
    assign proc_dep_vld_vec_1[1] = dl_detect_out ? proc_dep_vld_vec_1_reg[1] : (proc_1_data_FIFO_blk[1] | proc_1_data_PIPO_blk[1] | proc_1_start_FIFO_blk[1] | proc_1_TLF_FIFO_blk[1] | proc_1_input_sync_blk[1] | proc_1_output_sync_blk[1]);
    always @ (negedge dl_reset or posedge dl_clock) begin
        if (~dl_reset) begin
            proc_dep_vld_vec_1_reg <= 'b0;
        end
        else begin
            proc_dep_vld_vec_1_reg <= proc_dep_vld_vec_1;
        end
    end
    assign in_chan_dep_vld_vec_1[0] = dep_chan_vld_2_1;
    assign in_chan_dep_data_vec_1[73 : 0] = dep_chan_data_2_1;
    assign token_in_vec_1[0] = token_2_1;
    assign in_chan_dep_vld_vec_1[1] = dep_chan_vld_3_1;
    assign in_chan_dep_data_vec_1[147 : 74] = dep_chan_data_3_1;
    assign token_in_vec_1[1] = token_3_1;
    assign dep_chan_vld_1_2 = out_chan_dep_vld_vec_1[0];
    assign dep_chan_data_1_2 = out_chan_dep_data_1;
    assign token_1_2 = token_out_vec_1[0];
    assign dep_chan_vld_1_3 = out_chan_dep_vld_vec_1[1];
    assign dep_chan_data_1_3 = out_chan_dep_data_1;
    assign token_1_3 = token_out_vec_1[1];

    // Process: grp_initial_overlap_wrapper_fu_5704.task_run_pe_U0.fixed_patch_do_patch_embed_U0
    vit_block_top_hls_deadlock_detect_unit #(74, 2, 2, 2) vit_block_top_hls_deadlock_detect_unit_2 (
        .reset(dl_reset),
        .clock(dl_clock),
        .proc_dep_vld_vec(proc_dep_vld_vec_2),
        .in_chan_dep_vld_vec(in_chan_dep_vld_vec_2),
        .in_chan_dep_data_vec(in_chan_dep_data_vec_2),
        .token_in_vec(token_in_vec_2),
        .dl_detect_in(dl_detect_out),
        .origin(origin[2]),
        .token_clear(token_clear),
        .out_chan_dep_vld_vec(out_chan_dep_vld_vec_2),
        .out_chan_dep_data(out_chan_dep_data_2),
        .token_out_vec(token_out_vec_2),
        .dl_detect_out(dl_in_vec[2]));

    assign proc_2_data_FIFO_blk[0] = 1'b0 | (~grp_initial_overlap_wrapper_fu_5704.task_run_pe_U0.fixed_patch_do_patch_embed_U0.do_adapt_4_U0.img_sm_blk_n);
    assign proc_2_data_PIPO_blk[0] = 1'b0;
    assign proc_2_start_FIFO_blk[0] = 1'b0 | (~grp_initial_overlap_wrapper_fu_5704.task_run_pe_U0.start_for_fixed_patch_do_patch_embed_U0_U.if_empty_n & grp_initial_overlap_wrapper_fu_5704.task_run_pe_U0.fixed_patch_do_patch_embed_U0.ap_idle & ~grp_initial_overlap_wrapper_fu_5704.task_run_pe_U0.start_for_fixed_patch_do_patch_embed_U0_U.if_write);
    assign proc_2_TLF_FIFO_blk[0] = 1'b0;
    assign proc_2_input_sync_blk[0] = 1'b0;
    assign proc_2_output_sync_blk[0] = 1'b0;
    assign proc_dep_vld_vec_2[0] = dl_detect_out ? proc_dep_vld_vec_2_reg[0] : (proc_2_data_FIFO_blk[0] | proc_2_data_PIPO_blk[0] | proc_2_start_FIFO_blk[0] | proc_2_TLF_FIFO_blk[0] | proc_2_input_sync_blk[0] | proc_2_output_sync_blk[0]);
    assign proc_2_data_FIFO_blk[1] = 1'b0 | (~grp_initial_overlap_wrapper_fu_5704.task_run_pe_U0.fixed_patch_do_patch_embed_U0.do_adapt_9_1_U0.pe_out_sm_blk_n);
    assign proc_2_data_PIPO_blk[1] = 1'b0;
    assign proc_2_start_FIFO_blk[1] = 1'b0 | (~grp_initial_overlap_wrapper_fu_5704.task_run_pe_U0.start_for_task_write_pe_to_fm_U0_U.if_full_n & grp_initial_overlap_wrapper_fu_5704.task_run_pe_U0.fixed_patch_do_patch_embed_U0.ap_start & ~grp_initial_overlap_wrapper_fu_5704.task_run_pe_U0.fixed_patch_do_patch_embed_U0.real_start & (trans_in_cnt_3 == trans_out_cnt_3) & ~grp_initial_overlap_wrapper_fu_5704.task_run_pe_U0.start_for_task_write_pe_to_fm_U0_U.if_read);
    assign proc_2_TLF_FIFO_blk[1] = 1'b0;
    assign proc_2_input_sync_blk[1] = 1'b0;
    assign proc_2_output_sync_blk[1] = 1'b0;
    assign proc_dep_vld_vec_2[1] = dl_detect_out ? proc_dep_vld_vec_2_reg[1] : (proc_2_data_FIFO_blk[1] | proc_2_data_PIPO_blk[1] | proc_2_start_FIFO_blk[1] | proc_2_TLF_FIFO_blk[1] | proc_2_input_sync_blk[1] | proc_2_output_sync_blk[1]);
    always @ (negedge dl_reset or posedge dl_clock) begin
        if (~dl_reset) begin
            proc_dep_vld_vec_2_reg <= 'b0;
        end
        else begin
            proc_dep_vld_vec_2_reg <= proc_dep_vld_vec_2;
        end
    end
    assign in_chan_dep_vld_vec_2[0] = dep_chan_vld_1_2;
    assign in_chan_dep_data_vec_2[73 : 0] = dep_chan_data_1_2;
    assign token_in_vec_2[0] = token_1_2;
    assign in_chan_dep_vld_vec_2[1] = dep_chan_vld_6_2;
    assign in_chan_dep_data_vec_2[147 : 74] = dep_chan_data_6_2;
    assign token_in_vec_2[1] = token_6_2;
    assign dep_chan_vld_2_1 = out_chan_dep_vld_vec_2[0];
    assign dep_chan_data_2_1 = out_chan_dep_data_2;
    assign token_2_1 = token_out_vec_2[0];
    assign dep_chan_vld_2_6 = out_chan_dep_vld_vec_2[1];
    assign dep_chan_data_2_6 = out_chan_dep_data_2;
    assign token_2_6 = token_out_vec_2[1];

    // Process: grp_initial_overlap_wrapper_fu_5704.task_run_pe_U0.fixed_patch_do_patch_embed_U0.do_adapt_4_U0
    vit_block_top_hls_deadlock_detect_unit #(74, 3, 2, 2) vit_block_top_hls_deadlock_detect_unit_3 (
        .reset(dl_reset),
        .clock(dl_clock),
        .proc_dep_vld_vec(proc_dep_vld_vec_3),
        .in_chan_dep_vld_vec(in_chan_dep_vld_vec_3),
        .in_chan_dep_data_vec(in_chan_dep_data_vec_3),
        .token_in_vec(token_in_vec_3),
        .dl_detect_in(dl_detect_out),
        .origin(origin[3]),
        .token_clear(token_clear),
        .out_chan_dep_vld_vec(out_chan_dep_vld_vec_3),
        .out_chan_dep_data(out_chan_dep_data_3),
        .token_out_vec(token_out_vec_3),
        .dl_detect_out(dl_in_vec[3]));

    assign proc_3_data_FIFO_blk[0] = 1'b0 | (~grp_initial_overlap_wrapper_fu_5704.task_run_pe_U0.fixed_patch_do_patch_embed_U0.do_adapt_4_U0.img_sm_blk_n);
    assign proc_3_data_PIPO_blk[0] = 1'b0;
    assign proc_3_start_FIFO_blk[0] = 1'b0;
    assign proc_3_TLF_FIFO_blk[0] = 1'b0;
    assign proc_3_input_sync_blk[0] = 1'b0;
    assign proc_3_output_sync_blk[0] = 1'b0;
    assign proc_dep_vld_vec_3[0] = dl_detect_out ? proc_dep_vld_vec_3_reg[0] : (proc_3_data_FIFO_blk[0] | proc_3_data_PIPO_blk[0] | proc_3_start_FIFO_blk[0] | proc_3_TLF_FIFO_blk[0] | proc_3_input_sync_blk[0] | proc_3_output_sync_blk[0]);
    assign proc_3_data_FIFO_blk[1] = 1'b0 | (~grp_initial_overlap_wrapper_fu_5704.task_run_pe_U0.fixed_patch_do_patch_embed_U0.do_adapt_4_U0.adpt_sm_blk_n);
    assign proc_3_data_PIPO_blk[1] = 1'b0;
    assign proc_3_start_FIFO_blk[1] = 1'b0 | (~grp_initial_overlap_wrapper_fu_5704.task_run_pe_U0.fixed_patch_do_patch_embed_U0.start_for_fixed_patch_step2_mac_replace_shift_U0_U.if_full_n & grp_initial_overlap_wrapper_fu_5704.task_run_pe_U0.fixed_patch_do_patch_embed_U0.do_adapt_4_U0.ap_start & ~grp_initial_overlap_wrapper_fu_5704.task_run_pe_U0.fixed_patch_do_patch_embed_U0.do_adapt_4_U0.real_start & (trans_in_cnt_1 == trans_out_cnt_1) & ~grp_initial_overlap_wrapper_fu_5704.task_run_pe_U0.fixed_patch_do_patch_embed_U0.start_for_fixed_patch_step2_mac_replace_shift_U0_U.if_read);
    assign proc_3_TLF_FIFO_blk[1] = 1'b0;
    assign proc_3_input_sync_blk[1] = 1'b0;
    assign proc_3_output_sync_blk[1] = 1'b0;
    assign proc_dep_vld_vec_3[1] = dl_detect_out ? proc_dep_vld_vec_3_reg[1] : (proc_3_data_FIFO_blk[1] | proc_3_data_PIPO_blk[1] | proc_3_start_FIFO_blk[1] | proc_3_TLF_FIFO_blk[1] | proc_3_input_sync_blk[1] | proc_3_output_sync_blk[1]);
    always @ (negedge dl_reset or posedge dl_clock) begin
        if (~dl_reset) begin
            proc_dep_vld_vec_3_reg <= 'b0;
        end
        else begin
            proc_dep_vld_vec_3_reg <= proc_dep_vld_vec_3;
        end
    end
    assign in_chan_dep_vld_vec_3[0] = dep_chan_vld_1_3;
    assign in_chan_dep_data_vec_3[73 : 0] = dep_chan_data_1_3;
    assign token_in_vec_3[0] = token_1_3;
    assign in_chan_dep_vld_vec_3[1] = dep_chan_vld_4_3;
    assign in_chan_dep_data_vec_3[147 : 74] = dep_chan_data_4_3;
    assign token_in_vec_3[1] = token_4_3;
    assign dep_chan_vld_3_1 = out_chan_dep_vld_vec_3[0];
    assign dep_chan_data_3_1 = out_chan_dep_data_3;
    assign token_3_1 = token_out_vec_3[0];
    assign dep_chan_vld_3_4 = out_chan_dep_vld_vec_3[1];
    assign dep_chan_data_3_4 = out_chan_dep_data_3;
    assign token_3_4 = token_out_vec_3[1];

    // Process: grp_initial_overlap_wrapper_fu_5704.task_run_pe_U0.fixed_patch_do_patch_embed_U0.fixed_patch_step2_mac_replace_shift_U0
    vit_block_top_hls_deadlock_detect_unit #(74, 4, 2, 2) vit_block_top_hls_deadlock_detect_unit_4 (
        .reset(dl_reset),
        .clock(dl_clock),
        .proc_dep_vld_vec(proc_dep_vld_vec_4),
        .in_chan_dep_vld_vec(in_chan_dep_vld_vec_4),
        .in_chan_dep_data_vec(in_chan_dep_data_vec_4),
        .token_in_vec(token_in_vec_4),
        .dl_detect_in(dl_detect_out),
        .origin(origin[4]),
        .token_clear(token_clear),
        .out_chan_dep_vld_vec(out_chan_dep_vld_vec_4),
        .out_chan_dep_data(out_chan_dep_data_4),
        .token_out_vec(token_out_vec_4),
        .dl_detect_out(dl_in_vec[4]));

    assign proc_4_data_FIFO_blk[0] = 1'b0 | (~grp_initial_overlap_wrapper_fu_5704.task_run_pe_U0.fixed_patch_do_patch_embed_U0.fixed_patch_step2_mac_replace_shift_U0.grp_fixed_patch_step2_mac_replace_shift_Pipeline_CIT_LOOP_COT_LOOP_fu_790.adpt_sm_blk_n);
    assign proc_4_data_PIPO_blk[0] = 1'b0;
    assign proc_4_start_FIFO_blk[0] = 1'b0 | (~grp_initial_overlap_wrapper_fu_5704.task_run_pe_U0.fixed_patch_do_patch_embed_U0.start_for_fixed_patch_step2_mac_replace_shift_U0_U.if_empty_n & grp_initial_overlap_wrapper_fu_5704.task_run_pe_U0.fixed_patch_do_patch_embed_U0.fixed_patch_step2_mac_replace_shift_U0.ap_idle & ~grp_initial_overlap_wrapper_fu_5704.task_run_pe_U0.fixed_patch_do_patch_embed_U0.start_for_fixed_patch_step2_mac_replace_shift_U0_U.if_write);
    assign proc_4_TLF_FIFO_blk[0] = 1'b0;
    assign proc_4_input_sync_blk[0] = 1'b0;
    assign proc_4_output_sync_blk[0] = 1'b0;
    assign proc_dep_vld_vec_4[0] = dl_detect_out ? proc_dep_vld_vec_4_reg[0] : (proc_4_data_FIFO_blk[0] | proc_4_data_PIPO_blk[0] | proc_4_start_FIFO_blk[0] | proc_4_TLF_FIFO_blk[0] | proc_4_input_sync_blk[0] | proc_4_output_sync_blk[0]);
    assign proc_4_data_FIFO_blk[1] = 1'b0 | (~grp_initial_overlap_wrapper_fu_5704.task_run_pe_U0.fixed_patch_do_patch_embed_U0.fixed_patch_step2_mac_replace_shift_U0.grp_fixed_patch_step2_mac_replace_shift_Pipeline_WRITE_COT_LOOP_fu_1446.mac_sm_blk_n);
    assign proc_4_data_PIPO_blk[1] = 1'b0;
    assign proc_4_start_FIFO_blk[1] = 1'b0 | (~grp_initial_overlap_wrapper_fu_5704.task_run_pe_U0.fixed_patch_do_patch_embed_U0.start_for_do_adapt_9_1_U0_U.if_full_n & grp_initial_overlap_wrapper_fu_5704.task_run_pe_U0.fixed_patch_do_patch_embed_U0.fixed_patch_step2_mac_replace_shift_U0.ap_start & ~grp_initial_overlap_wrapper_fu_5704.task_run_pe_U0.fixed_patch_do_patch_embed_U0.fixed_patch_step2_mac_replace_shift_U0.real_start & (trans_in_cnt_2 == trans_out_cnt_2) & ~grp_initial_overlap_wrapper_fu_5704.task_run_pe_U0.fixed_patch_do_patch_embed_U0.start_for_do_adapt_9_1_U0_U.if_read);
    assign proc_4_TLF_FIFO_blk[1] = 1'b0;
    assign proc_4_input_sync_blk[1] = 1'b0;
    assign proc_4_output_sync_blk[1] = 1'b0;
    assign proc_dep_vld_vec_4[1] = dl_detect_out ? proc_dep_vld_vec_4_reg[1] : (proc_4_data_FIFO_blk[1] | proc_4_data_PIPO_blk[1] | proc_4_start_FIFO_blk[1] | proc_4_TLF_FIFO_blk[1] | proc_4_input_sync_blk[1] | proc_4_output_sync_blk[1]);
    always @ (negedge dl_reset or posedge dl_clock) begin
        if (~dl_reset) begin
            proc_dep_vld_vec_4_reg <= 'b0;
        end
        else begin
            proc_dep_vld_vec_4_reg <= proc_dep_vld_vec_4;
        end
    end
    assign in_chan_dep_vld_vec_4[0] = dep_chan_vld_3_4;
    assign in_chan_dep_data_vec_4[73 : 0] = dep_chan_data_3_4;
    assign token_in_vec_4[0] = token_3_4;
    assign in_chan_dep_vld_vec_4[1] = dep_chan_vld_5_4;
    assign in_chan_dep_data_vec_4[147 : 74] = dep_chan_data_5_4;
    assign token_in_vec_4[1] = token_5_4;
    assign dep_chan_vld_4_3 = out_chan_dep_vld_vec_4[0];
    assign dep_chan_data_4_3 = out_chan_dep_data_4;
    assign token_4_3 = token_out_vec_4[0];
    assign dep_chan_vld_4_5 = out_chan_dep_vld_vec_4[1];
    assign dep_chan_data_4_5 = out_chan_dep_data_4;
    assign token_4_5 = token_out_vec_4[1];

    // Process: grp_initial_overlap_wrapper_fu_5704.task_run_pe_U0.fixed_patch_do_patch_embed_U0.do_adapt_9_1_U0
    vit_block_top_hls_deadlock_detect_unit #(74, 5, 2, 2) vit_block_top_hls_deadlock_detect_unit_5 (
        .reset(dl_reset),
        .clock(dl_clock),
        .proc_dep_vld_vec(proc_dep_vld_vec_5),
        .in_chan_dep_vld_vec(in_chan_dep_vld_vec_5),
        .in_chan_dep_data_vec(in_chan_dep_data_vec_5),
        .token_in_vec(token_in_vec_5),
        .dl_detect_in(dl_detect_out),
        .origin(origin[5]),
        .token_clear(token_clear),
        .out_chan_dep_vld_vec(out_chan_dep_vld_vec_5),
        .out_chan_dep_data(out_chan_dep_data_5),
        .token_out_vec(token_out_vec_5),
        .dl_detect_out(dl_in_vec[5]));

    assign proc_5_data_FIFO_blk[0] = 1'b0 | (~grp_initial_overlap_wrapper_fu_5704.task_run_pe_U0.fixed_patch_do_patch_embed_U0.do_adapt_9_1_U0.mac_sm_blk_n);
    assign proc_5_data_PIPO_blk[0] = 1'b0;
    assign proc_5_start_FIFO_blk[0] = 1'b0 | (~grp_initial_overlap_wrapper_fu_5704.task_run_pe_U0.fixed_patch_do_patch_embed_U0.start_for_do_adapt_9_1_U0_U.if_empty_n & grp_initial_overlap_wrapper_fu_5704.task_run_pe_U0.fixed_patch_do_patch_embed_U0.do_adapt_9_1_U0.ap_idle & ~grp_initial_overlap_wrapper_fu_5704.task_run_pe_U0.fixed_patch_do_patch_embed_U0.start_for_do_adapt_9_1_U0_U.if_write);
    assign proc_5_TLF_FIFO_blk[0] = 1'b0;
    assign proc_5_input_sync_blk[0] = 1'b0;
    assign proc_5_output_sync_blk[0] = 1'b0;
    assign proc_dep_vld_vec_5[0] = dl_detect_out ? proc_dep_vld_vec_5_reg[0] : (proc_5_data_FIFO_blk[0] | proc_5_data_PIPO_blk[0] | proc_5_start_FIFO_blk[0] | proc_5_TLF_FIFO_blk[0] | proc_5_input_sync_blk[0] | proc_5_output_sync_blk[0]);
    assign proc_5_data_FIFO_blk[1] = 1'b0 | (~grp_initial_overlap_wrapper_fu_5704.task_run_pe_U0.fixed_patch_do_patch_embed_U0.do_adapt_9_1_U0.pe_out_sm_blk_n);
    assign proc_5_data_PIPO_blk[1] = 1'b0;
    assign proc_5_start_FIFO_blk[1] = 1'b0;
    assign proc_5_TLF_FIFO_blk[1] = 1'b0;
    assign proc_5_input_sync_blk[1] = 1'b0;
    assign proc_5_output_sync_blk[1] = 1'b0;
    assign proc_dep_vld_vec_5[1] = dl_detect_out ? proc_dep_vld_vec_5_reg[1] : (proc_5_data_FIFO_blk[1] | proc_5_data_PIPO_blk[1] | proc_5_start_FIFO_blk[1] | proc_5_TLF_FIFO_blk[1] | proc_5_input_sync_blk[1] | proc_5_output_sync_blk[1]);
    always @ (negedge dl_reset or posedge dl_clock) begin
        if (~dl_reset) begin
            proc_dep_vld_vec_5_reg <= 'b0;
        end
        else begin
            proc_dep_vld_vec_5_reg <= proc_dep_vld_vec_5;
        end
    end
    assign in_chan_dep_vld_vec_5[0] = dep_chan_vld_4_5;
    assign in_chan_dep_data_vec_5[73 : 0] = dep_chan_data_4_5;
    assign token_in_vec_5[0] = token_4_5;
    assign in_chan_dep_vld_vec_5[1] = dep_chan_vld_6_5;
    assign in_chan_dep_data_vec_5[147 : 74] = dep_chan_data_6_5;
    assign token_in_vec_5[1] = token_6_5;
    assign dep_chan_vld_5_4 = out_chan_dep_vld_vec_5[0];
    assign dep_chan_data_5_4 = out_chan_dep_data_5;
    assign token_5_4 = token_out_vec_5[0];
    assign dep_chan_vld_5_6 = out_chan_dep_vld_vec_5[1];
    assign dep_chan_data_5_6 = out_chan_dep_data_5;
    assign token_5_6 = token_out_vec_5[1];

    // Process: grp_initial_overlap_wrapper_fu_5704.task_run_pe_U0.task_write_pe_to_fm_U0
    vit_block_top_hls_deadlock_detect_unit #(74, 6, 2, 2) vit_block_top_hls_deadlock_detect_unit_6 (
        .reset(dl_reset),
        .clock(dl_clock),
        .proc_dep_vld_vec(proc_dep_vld_vec_6),
        .in_chan_dep_vld_vec(in_chan_dep_vld_vec_6),
        .in_chan_dep_data_vec(in_chan_dep_data_vec_6),
        .token_in_vec(token_in_vec_6),
        .dl_detect_in(dl_detect_out),
        .origin(origin[6]),
        .token_clear(token_clear),
        .out_chan_dep_vld_vec(out_chan_dep_vld_vec_6),
        .out_chan_dep_data(out_chan_dep_data_6),
        .token_out_vec(token_out_vec_6),
        .dl_detect_out(dl_in_vec[6]));

    assign proc_6_data_FIFO_blk[0] = 1'b0 | (~grp_initial_overlap_wrapper_fu_5704.task_run_pe_U0.task_write_pe_to_fm_U0.pe_out_sm_blk_n);
    assign proc_6_data_PIPO_blk[0] = 1'b0;
    assign proc_6_start_FIFO_blk[0] = 1'b0 | (~grp_initial_overlap_wrapper_fu_5704.task_run_pe_U0.start_for_task_write_pe_to_fm_U0_U.if_empty_n & grp_initial_overlap_wrapper_fu_5704.task_run_pe_U0.task_write_pe_to_fm_U0.ap_idle & ~grp_initial_overlap_wrapper_fu_5704.task_run_pe_U0.start_for_task_write_pe_to_fm_U0_U.if_write);
    assign proc_6_TLF_FIFO_blk[0] = 1'b0;
    assign proc_6_input_sync_blk[0] = 1'b0;
    assign proc_6_output_sync_blk[0] = 1'b0;
    assign proc_dep_vld_vec_6[0] = dl_detect_out ? proc_dep_vld_vec_6_reg[0] : (proc_6_data_FIFO_blk[0] | proc_6_data_PIPO_blk[0] | proc_6_start_FIFO_blk[0] | proc_6_TLF_FIFO_blk[0] | proc_6_input_sync_blk[0] | proc_6_output_sync_blk[0]);
    assign proc_6_data_FIFO_blk[1] = 1'b0 | (~grp_initial_overlap_wrapper_fu_5704.task_run_pe_U0.task_write_pe_to_fm_U0.pe_out_sm_blk_n);
    assign proc_6_data_PIPO_blk[1] = 1'b0;
    assign proc_6_start_FIFO_blk[1] = 1'b0;
    assign proc_6_TLF_FIFO_blk[1] = 1'b0;
    assign proc_6_input_sync_blk[1] = 1'b0;
    assign proc_6_output_sync_blk[1] = 1'b0;
    assign proc_dep_vld_vec_6[1] = dl_detect_out ? proc_dep_vld_vec_6_reg[1] : (proc_6_data_FIFO_blk[1] | proc_6_data_PIPO_blk[1] | proc_6_start_FIFO_blk[1] | proc_6_TLF_FIFO_blk[1] | proc_6_input_sync_blk[1] | proc_6_output_sync_blk[1]);
    always @ (negedge dl_reset or posedge dl_clock) begin
        if (~dl_reset) begin
            proc_dep_vld_vec_6_reg <= 'b0;
        end
        else begin
            proc_dep_vld_vec_6_reg <= proc_dep_vld_vec_6;
        end
    end
    assign in_chan_dep_vld_vec_6[0] = dep_chan_vld_2_6;
    assign in_chan_dep_data_vec_6[73 : 0] = dep_chan_data_2_6;
    assign token_in_vec_6[0] = token_2_6;
    assign in_chan_dep_vld_vec_6[1] = dep_chan_vld_5_6;
    assign in_chan_dep_data_vec_6[147 : 74] = dep_chan_data_5_6;
    assign token_in_vec_6[1] = token_5_6;
    assign dep_chan_vld_6_2 = out_chan_dep_vld_vec_6[0];
    assign dep_chan_data_6_2 = out_chan_dep_data_6;
    assign token_6_2 = token_out_vec_6[0];
    assign dep_chan_vld_6_5 = out_chan_dep_vld_vec_6[1];
    assign dep_chan_data_6_5 = out_chan_dep_data_6;
    assign token_6_5 = token_out_vec_6[1];

    // Process: grp_initial_overlap_wrapper_fu_5704.task_load_weights_U0
    vit_block_top_hls_deadlock_detect_unit #(74, 7, 1, 1) vit_block_top_hls_deadlock_detect_unit_7 (
        .reset(dl_reset),
        .clock(dl_clock),
        .proc_dep_vld_vec(proc_dep_vld_vec_7),
        .in_chan_dep_vld_vec(in_chan_dep_vld_vec_7),
        .in_chan_dep_data_vec(in_chan_dep_data_vec_7),
        .token_in_vec(token_in_vec_7),
        .dl_detect_in(dl_detect_out),
        .origin(origin[7]),
        .token_clear(token_clear),
        .out_chan_dep_vld_vec(out_chan_dep_vld_vec_7),
        .out_chan_dep_data(out_chan_dep_data_7),
        .token_out_vec(token_out_vec_7),
        .dl_detect_out(dl_in_vec[7]));

    assign proc_7_data_FIFO_blk[0] = 1'b0;
    assign proc_7_data_PIPO_blk[0] = 1'b0;
    assign proc_7_start_FIFO_blk[0] = 1'b0;
    assign proc_7_TLF_FIFO_blk[0] = 1'b0;
    assign proc_7_input_sync_blk[0] = 1'b0 | (grp_initial_overlap_wrapper_fu_5704.ap_sync_task_load_weights_U0_ap_ready & grp_initial_overlap_wrapper_fu_5704.task_load_weights_U0.ap_idle & ~grp_initial_overlap_wrapper_fu_5704.ap_sync_task_run_pe_U0_ap_ready);
    assign proc_7_output_sync_blk[0] = 1'b0 | (ap_done_reg_4 & grp_initial_overlap_wrapper_fu_5704.task_load_weights_U0.ap_done & ~grp_initial_overlap_wrapper_fu_5704.task_run_pe_U0.ap_done);
    assign proc_dep_vld_vec_7[0] = dl_detect_out ? proc_dep_vld_vec_7_reg[0] : (proc_7_data_FIFO_blk[0] | proc_7_data_PIPO_blk[0] | proc_7_start_FIFO_blk[0] | proc_7_TLF_FIFO_blk[0] | proc_7_input_sync_blk[0] | proc_7_output_sync_blk[0]);
    always @ (negedge dl_reset or posedge dl_clock) begin
        if (~dl_reset) begin
            proc_dep_vld_vec_7_reg <= 'b0;
        end
        else begin
            proc_dep_vld_vec_7_reg <= proc_dep_vld_vec_7;
        end
    end
    assign in_chan_dep_vld_vec_7[0] = dep_chan_vld_0_7;
    assign in_chan_dep_data_vec_7[73 : 0] = dep_chan_data_0_7;
    assign token_in_vec_7[0] = token_0_7;
    assign dep_chan_vld_7_0 = out_chan_dep_vld_vec_7[0];
    assign dep_chan_data_7_0 = out_chan_dep_data_7;
    assign token_7_0 = token_out_vec_7[0];

    // Process: grp_dataflow_wrapper_fu_6443.task_read_fm_split_U0
    vit_block_top_hls_deadlock_detect_unit #(74, 8, 2, 2) vit_block_top_hls_deadlock_detect_unit_8 (
        .reset(dl_reset),
        .clock(dl_clock),
        .proc_dep_vld_vec(proc_dep_vld_vec_8),
        .in_chan_dep_vld_vec(in_chan_dep_vld_vec_8),
        .in_chan_dep_data_vec(in_chan_dep_data_vec_8),
        .token_in_vec(token_in_vec_8),
        .dl_detect_in(dl_detect_out),
        .origin(origin[8]),
        .token_clear(token_clear),
        .out_chan_dep_vld_vec(out_chan_dep_vld_vec_8),
        .out_chan_dep_data(out_chan_dep_data_8),
        .token_out_vec(token_out_vec_8),
        .dl_detect_out(dl_in_vec[8]));

    assign proc_8_data_FIFO_blk[0] = 1'b0 | (~grp_dataflow_wrapper_fu_6443.task_read_fm_split_U0.i_stream_main_blk_n) | (~grp_dataflow_wrapper_fu_6443.task_read_fm_split_U0.i_stream_resi_blk_n);
    assign proc_8_data_PIPO_blk[0] = 1'b0;
    assign proc_8_start_FIFO_blk[0] = 1'b0;
    assign proc_8_TLF_FIFO_blk[0] = 1'b0;
    assign proc_8_input_sync_blk[0] = 1'b0;
    assign proc_8_output_sync_blk[0] = 1'b0;
    assign proc_dep_vld_vec_8[0] = dl_detect_out ? proc_dep_vld_vec_8_reg[0] : (proc_8_data_FIFO_blk[0] | proc_8_data_PIPO_blk[0] | proc_8_start_FIFO_blk[0] | proc_8_TLF_FIFO_blk[0] | proc_8_input_sync_blk[0] | proc_8_output_sync_blk[0]);
    assign proc_8_data_FIFO_blk[1] = 1'b0;
    assign proc_8_data_PIPO_blk[1] = 1'b0;
    assign proc_8_start_FIFO_blk[1] = 1'b0;
    assign proc_8_TLF_FIFO_blk[1] = 1'b0;
    assign proc_8_input_sync_blk[1] = 1'b0 | (grp_dataflow_wrapper_fu_6443.ap_sync_task_read_fm_split_U0_ap_ready & grp_dataflow_wrapper_fu_6443.task_read_fm_split_U0.ap_idle & ~grp_dataflow_wrapper_fu_6443.ap_sync_dataflow_wrapper_Block_entry_calc_weights_attn_weights_attn_scalars_rd_calc_weig_U0_ap_ready);
    assign proc_8_output_sync_blk[1] = 1'b0;
    assign proc_dep_vld_vec_8[1] = dl_detect_out ? proc_dep_vld_vec_8_reg[1] : (proc_8_data_FIFO_blk[1] | proc_8_data_PIPO_blk[1] | proc_8_start_FIFO_blk[1] | proc_8_TLF_FIFO_blk[1] | proc_8_input_sync_blk[1] | proc_8_output_sync_blk[1]);
    always @ (negedge dl_reset or posedge dl_clock) begin
        if (~dl_reset) begin
            proc_dep_vld_vec_8_reg <= 'b0;
        end
        else begin
            proc_dep_vld_vec_8_reg <= proc_dep_vld_vec_8;
        end
    end
    assign in_chan_dep_vld_vec_8[0] = dep_chan_vld_9_8;
    assign in_chan_dep_data_vec_8[73 : 0] = dep_chan_data_9_8;
    assign token_in_vec_8[0] = token_9_8;
    assign in_chan_dep_vld_vec_8[1] = dep_chan_vld_10_8;
    assign in_chan_dep_data_vec_8[147 : 74] = dep_chan_data_10_8;
    assign token_in_vec_8[1] = token_10_8;
    assign dep_chan_vld_8_10 = out_chan_dep_vld_vec_8[0];
    assign dep_chan_data_8_10 = out_chan_dep_data_8;
    assign token_8_10 = token_out_vec_8[0];
    assign dep_chan_vld_8_9 = out_chan_dep_vld_vec_8[1];
    assign dep_chan_data_8_9 = out_chan_dep_data_8;
    assign token_8_9 = token_out_vec_8[1];

    // Process: grp_dataflow_wrapper_fu_6443.dataflow_wrapper_Block_entry_calc_weights_attn_weights_attn_scalars_rd_calc_weig_U0
    vit_block_top_hls_deadlock_detect_unit #(74, 9, 4, 1) vit_block_top_hls_deadlock_detect_unit_9 (
        .reset(dl_reset),
        .clock(dl_clock),
        .proc_dep_vld_vec(proc_dep_vld_vec_9),
        .in_chan_dep_vld_vec(in_chan_dep_vld_vec_9),
        .in_chan_dep_data_vec(in_chan_dep_data_vec_9),
        .token_in_vec(token_in_vec_9),
        .dl_detect_in(dl_detect_out),
        .origin(origin[9]),
        .token_clear(token_clear),
        .out_chan_dep_vld_vec(out_chan_dep_vld_vec_9),
        .out_chan_dep_data(out_chan_dep_data_9),
        .token_out_vec(token_out_vec_9),
        .dl_detect_out(dl_in_vec[9]));

    assign proc_9_data_FIFO_blk[0] = 1'b0;
    assign proc_9_data_PIPO_blk[0] = 1'b0;
    assign proc_9_start_FIFO_blk[0] = 1'b0;
    assign proc_9_TLF_FIFO_blk[0] = 1'b0;
    assign proc_9_input_sync_blk[0] = 1'b0 | (grp_dataflow_wrapper_fu_6443.ap_sync_dataflow_wrapper_Block_entry_calc_weights_attn_weights_attn_scalars_rd_calc_weig_U0_ap_ready & grp_dataflow_wrapper_fu_6443.dataflow_wrapper_Block_entry_calc_weights_attn_weights_attn_scalars_rd_calc_weig_U0.ap_idle & ~grp_dataflow_wrapper_fu_6443.ap_sync_task_read_fm_split_U0_ap_ready);
    assign proc_9_output_sync_blk[0] = 1'b0;
    assign proc_dep_vld_vec_9[0] = dl_detect_out ? proc_dep_vld_vec_9_reg[0] : (proc_9_data_FIFO_blk[0] | proc_9_data_PIPO_blk[0] | proc_9_start_FIFO_blk[0] | proc_9_TLF_FIFO_blk[0] | proc_9_input_sync_blk[0] | proc_9_output_sync_blk[0]);
    always @ (negedge dl_reset or posedge dl_clock) begin
        if (~dl_reset) begin
            proc_dep_vld_vec_9_reg <= 'b0;
        end
        else begin
            proc_dep_vld_vec_9_reg <= proc_dep_vld_vec_9;
        end
    end
    assign in_chan_dep_vld_vec_9[0] = dep_chan_vld_8_9;
    assign in_chan_dep_data_vec_9[73 : 0] = dep_chan_data_8_9;
    assign token_in_vec_9[0] = token_8_9;
    assign in_chan_dep_vld_vec_9[1] = dep_chan_vld_10_9;
    assign in_chan_dep_data_vec_9[147 : 74] = dep_chan_data_10_9;
    assign token_in_vec_9[1] = token_10_9;
    assign in_chan_dep_vld_vec_9[2] = dep_chan_vld_48_9;
    assign in_chan_dep_data_vec_9[221 : 148] = dep_chan_data_48_9;
    assign token_in_vec_9[2] = token_48_9;
    assign in_chan_dep_vld_vec_9[3] = dep_chan_vld_66_9;
    assign in_chan_dep_data_vec_9[295 : 222] = dep_chan_data_66_9;
    assign token_in_vec_9[3] = token_66_9;
    assign dep_chan_vld_9_8 = out_chan_dep_vld_vec_9[0];
    assign dep_chan_data_9_8 = out_chan_dep_data_9;
    assign token_9_8 = token_out_vec_9[0];

    // Process: grp_dataflow_wrapper_fu_6443.task_compute_attn_U0
    vit_block_top_hls_deadlock_detect_unit #(74, 10, 2, 3) vit_block_top_hls_deadlock_detect_unit_10 (
        .reset(dl_reset),
        .clock(dl_clock),
        .proc_dep_vld_vec(proc_dep_vld_vec_10),
        .in_chan_dep_vld_vec(in_chan_dep_vld_vec_10),
        .in_chan_dep_data_vec(in_chan_dep_data_vec_10),
        .token_in_vec(token_in_vec_10),
        .dl_detect_in(dl_detect_out),
        .origin(origin[10]),
        .token_clear(token_clear),
        .out_chan_dep_vld_vec(out_chan_dep_vld_vec_10),
        .out_chan_dep_data(out_chan_dep_data_10),
        .token_out_vec(token_out_vec_10),
        .dl_detect_out(dl_in_vec[10]));

    assign proc_10_data_FIFO_blk[0] = 1'b0;
    assign proc_10_data_PIPO_blk[0] = 1'b0;
    assign proc_10_start_FIFO_blk[0] = 1'b0;
    assign proc_10_TLF_FIFO_blk[0] = 1'b0 | (~grp_dataflow_wrapper_fu_6443.calc_weights_attn_weights_attn_scalars_idx_val_loc_channel_U.if_empty_n & grp_dataflow_wrapper_fu_6443.task_compute_attn_U0.ap_idle & ~grp_dataflow_wrapper_fu_6443.calc_weights_attn_weights_attn_scalars_idx_val_loc_channel_U.if_write) | (~grp_dataflow_wrapper_fu_6443.calc_weights_attn_weights_attn_scalars_idx6_val_loc_channel_U.if_empty_n & grp_dataflow_wrapper_fu_6443.task_compute_attn_U0.ap_idle & ~grp_dataflow_wrapper_fu_6443.calc_weights_attn_weights_attn_scalars_idx6_val_loc_channel_U.if_write);
    assign proc_10_input_sync_blk[0] = 1'b0;
    assign proc_10_output_sync_blk[0] = 1'b0;
    assign proc_dep_vld_vec_10[0] = dl_detect_out ? proc_dep_vld_vec_10_reg[0] : (proc_10_data_FIFO_blk[0] | proc_10_data_PIPO_blk[0] | proc_10_start_FIFO_blk[0] | proc_10_TLF_FIFO_blk[0] | proc_10_input_sync_blk[0] | proc_10_output_sync_blk[0]);
    assign proc_10_data_FIFO_blk[1] = 1'b0 | (~grp_dataflow_wrapper_fu_6443.task_compute_attn_U0.grp_do_attn_1_fu_5150.do_layernorm_inter_token_1_U0.grp_do_layernorm_inter_token_1_Pipeline_WAVE_LOOP_CT_PIPELINE_LOOP_fu_138.i_stream_main_blk_n) | (~grp_dataflow_wrapper_fu_6443.task_compute_attn_U0.grp_do_attn_1_fu_5150.do_adapt_10_U0.i_stream_resi_blk_n);
    assign proc_10_data_PIPO_blk[1] = 1'b0;
    assign proc_10_start_FIFO_blk[1] = 1'b0;
    assign proc_10_TLF_FIFO_blk[1] = 1'b0;
    assign proc_10_input_sync_blk[1] = 1'b0;
    assign proc_10_output_sync_blk[1] = 1'b0;
    assign proc_dep_vld_vec_10[1] = dl_detect_out ? proc_dep_vld_vec_10_reg[1] : (proc_10_data_FIFO_blk[1] | proc_10_data_PIPO_blk[1] | proc_10_start_FIFO_blk[1] | proc_10_TLF_FIFO_blk[1] | proc_10_input_sync_blk[1] | proc_10_output_sync_blk[1]);
    assign proc_10_data_FIFO_blk[2] = 1'b0 | (~grp_dataflow_wrapper_fu_6443.task_compute_attn_U0.grp_do_attn_1_fu_5150.stream_merge_1_U0.grp_stream_merge_1_Pipeline_VITIS_LOOP_554_1_VITIS_LOOP_555_2_fu_34.mid_stream_int_blk_n);
    assign proc_10_data_PIPO_blk[2] = 1'b0;
    assign proc_10_start_FIFO_blk[2] = 1'b0 | (~grp_dataflow_wrapper_fu_6443.start_for_task_stream_cast_U0_U.if_full_n & grp_dataflow_wrapper_fu_6443.task_compute_attn_U0.ap_start & ~grp_dataflow_wrapper_fu_6443.task_compute_attn_U0.real_start & (trans_in_cnt_30 == trans_out_cnt_30) & ~grp_dataflow_wrapper_fu_6443.start_for_task_stream_cast_U0_U.if_read);
    assign proc_10_TLF_FIFO_blk[2] = 1'b0;
    assign proc_10_input_sync_blk[2] = 1'b0;
    assign proc_10_output_sync_blk[2] = 1'b0;
    assign proc_dep_vld_vec_10[2] = dl_detect_out ? proc_dep_vld_vec_10_reg[2] : (proc_10_data_FIFO_blk[2] | proc_10_data_PIPO_blk[2] | proc_10_start_FIFO_blk[2] | proc_10_TLF_FIFO_blk[2] | proc_10_input_sync_blk[2] | proc_10_output_sync_blk[2]);
    always @ (negedge dl_reset or posedge dl_clock) begin
        if (~dl_reset) begin
            proc_dep_vld_vec_10_reg <= 'b0;
        end
        else begin
            proc_dep_vld_vec_10_reg <= proc_dep_vld_vec_10;
        end
    end
    assign in_chan_dep_vld_vec_10[0] = dep_chan_vld_8_10;
    assign in_chan_dep_data_vec_10[73 : 0] = dep_chan_data_8_10;
    assign token_in_vec_10[0] = token_8_10;
    assign in_chan_dep_vld_vec_10[1] = dep_chan_vld_47_10;
    assign in_chan_dep_data_vec_10[147 : 74] = dep_chan_data_47_10;
    assign token_in_vec_10[1] = token_47_10;
    assign dep_chan_vld_10_9 = out_chan_dep_vld_vec_10[0];
    assign dep_chan_data_10_9 = out_chan_dep_data_10;
    assign token_10_9 = token_out_vec_10[0];
    assign dep_chan_vld_10_8 = out_chan_dep_vld_vec_10[1];
    assign dep_chan_data_10_8 = out_chan_dep_data_10;
    assign token_10_8 = token_out_vec_10[1];
    assign dep_chan_vld_10_47 = out_chan_dep_vld_vec_10[2];
    assign dep_chan_data_10_47 = out_chan_dep_data_10;
    assign token_10_47 = token_out_vec_10[2];

    // Process: grp_dataflow_wrapper_fu_6443.task_compute_attn_U0.grp_do_attn_1_fu_5150.do_adapt_10_U0
    vit_block_top_hls_deadlock_detect_unit #(74, 11, 2, 2) vit_block_top_hls_deadlock_detect_unit_11 (
        .reset(dl_reset),
        .clock(dl_clock),
        .proc_dep_vld_vec(proc_dep_vld_vec_11),
        .in_chan_dep_vld_vec(in_chan_dep_vld_vec_11),
        .in_chan_dep_data_vec(in_chan_dep_data_vec_11),
        .token_in_vec(token_in_vec_11),
        .dl_detect_in(dl_detect_out),
        .origin(origin[11]),
        .token_clear(token_clear),
        .out_chan_dep_vld_vec(out_chan_dep_vld_vec_11),
        .out_chan_dep_data(out_chan_dep_data_11),
        .token_out_vec(token_out_vec_11),
        .dl_detect_out(dl_in_vec[11]));

    assign proc_11_data_FIFO_blk[0] = 1'b0 | (~grp_dataflow_wrapper_fu_6443.task_compute_attn_U0.grp_do_attn_1_fu_5150.do_adapt_10_U0.resi_sm_blk_n);
    assign proc_11_data_PIPO_blk[0] = 1'b0;
    assign proc_11_start_FIFO_blk[0] = 1'b0 | (~grp_dataflow_wrapper_fu_6443.task_compute_attn_U0.grp_do_attn_1_fu_5150.start_for_do_adapt_7_U0_U.if_full_n & grp_dataflow_wrapper_fu_6443.task_compute_attn_U0.grp_do_attn_1_fu_5150.do_adapt_10_U0.ap_start & ~grp_dataflow_wrapper_fu_6443.task_compute_attn_U0.grp_do_attn_1_fu_5150.do_adapt_10_U0.real_start & (trans_in_cnt_4 == trans_out_cnt_4) & ~grp_dataflow_wrapper_fu_6443.task_compute_attn_U0.grp_do_attn_1_fu_5150.start_for_do_adapt_7_U0_U.if_read);
    assign proc_11_TLF_FIFO_blk[0] = 1'b0;
    assign proc_11_input_sync_blk[0] = 1'b0;
    assign proc_11_output_sync_blk[0] = 1'b0;
    assign proc_dep_vld_vec_11[0] = dl_detect_out ? proc_dep_vld_vec_11_reg[0] : (proc_11_data_FIFO_blk[0] | proc_11_data_PIPO_blk[0] | proc_11_start_FIFO_blk[0] | proc_11_TLF_FIFO_blk[0] | proc_11_input_sync_blk[0] | proc_11_output_sync_blk[0]);
    assign proc_11_data_FIFO_blk[1] = 1'b0;
    assign proc_11_data_PIPO_blk[1] = 1'b0;
    assign proc_11_start_FIFO_blk[1] = 1'b0;
    assign proc_11_TLF_FIFO_blk[1] = 1'b0;
    assign proc_11_input_sync_blk[1] = 1'b0 | (grp_dataflow_wrapper_fu_6443.task_compute_attn_U0.grp_do_attn_1_fu_5150.ap_sync_do_adapt_10_U0_ap_ready & grp_dataflow_wrapper_fu_6443.task_compute_attn_U0.grp_do_attn_1_fu_5150.do_adapt_10_U0.ap_idle & ~grp_dataflow_wrapper_fu_6443.task_compute_attn_U0.grp_do_attn_1_fu_5150.ap_sync_do_layernorm_inter_token_1_U0_ap_ready);
    assign proc_11_output_sync_blk[1] = 1'b0;
    assign proc_dep_vld_vec_11[1] = dl_detect_out ? proc_dep_vld_vec_11_reg[1] : (proc_11_data_FIFO_blk[1] | proc_11_data_PIPO_blk[1] | proc_11_start_FIFO_blk[1] | proc_11_TLF_FIFO_blk[1] | proc_11_input_sync_blk[1] | proc_11_output_sync_blk[1]);
    always @ (negedge dl_reset or posedge dl_clock) begin
        if (~dl_reset) begin
            proc_dep_vld_vec_11_reg <= 'b0;
        end
        else begin
            proc_dep_vld_vec_11_reg <= proc_dep_vld_vec_11;
        end
    end
    assign in_chan_dep_vld_vec_11[0] = dep_chan_vld_12_11;
    assign in_chan_dep_data_vec_11[73 : 0] = dep_chan_data_12_11;
    assign token_in_vec_11[0] = token_12_11;
    assign in_chan_dep_vld_vec_11[1] = dep_chan_vld_13_11;
    assign in_chan_dep_data_vec_11[147 : 74] = dep_chan_data_13_11;
    assign token_in_vec_11[1] = token_13_11;
    assign dep_chan_vld_11_12 = out_chan_dep_vld_vec_11[0];
    assign dep_chan_data_11_12 = out_chan_dep_data_11;
    assign token_11_12 = token_out_vec_11[0];
    assign dep_chan_vld_11_13 = out_chan_dep_vld_vec_11[1];
    assign dep_chan_data_11_13 = out_chan_dep_data_11;
    assign token_11_13 = token_out_vec_11[1];

    // Process: grp_dataflow_wrapper_fu_6443.task_compute_attn_U0.grp_do_attn_1_fu_5150.do_adapt_7_U0
    vit_block_top_hls_deadlock_detect_unit #(74, 12, 2, 2) vit_block_top_hls_deadlock_detect_unit_12 (
        .reset(dl_reset),
        .clock(dl_clock),
        .proc_dep_vld_vec(proc_dep_vld_vec_12),
        .in_chan_dep_vld_vec(in_chan_dep_vld_vec_12),
        .in_chan_dep_data_vec(in_chan_dep_data_vec_12),
        .token_in_vec(token_in_vec_12),
        .dl_detect_in(dl_detect_out),
        .origin(origin[12]),
        .token_clear(token_clear),
        .out_chan_dep_vld_vec(out_chan_dep_vld_vec_12),
        .out_chan_dep_data(out_chan_dep_data_12),
        .token_out_vec(token_out_vec_12),
        .dl_detect_out(dl_in_vec[12]));

    assign proc_12_data_FIFO_blk[0] = 1'b0 | (~grp_dataflow_wrapper_fu_6443.task_compute_attn_U0.grp_do_attn_1_fu_5150.do_adapt_7_U0.resi_sm_blk_n);
    assign proc_12_data_PIPO_blk[0] = 1'b0;
    assign proc_12_start_FIFO_blk[0] = 1'b0 | (~grp_dataflow_wrapper_fu_6443.task_compute_attn_U0.grp_do_attn_1_fu_5150.start_for_do_adapt_7_U0_U.if_empty_n & grp_dataflow_wrapper_fu_6443.task_compute_attn_U0.grp_do_attn_1_fu_5150.do_adapt_7_U0.ap_idle & ~grp_dataflow_wrapper_fu_6443.task_compute_attn_U0.grp_do_attn_1_fu_5150.start_for_do_adapt_7_U0_U.if_write);
    assign proc_12_TLF_FIFO_blk[0] = 1'b0;
    assign proc_12_input_sync_blk[0] = 1'b0;
    assign proc_12_output_sync_blk[0] = 1'b0;
    assign proc_dep_vld_vec_12[0] = dl_detect_out ? proc_dep_vld_vec_12_reg[0] : (proc_12_data_FIFO_blk[0] | proc_12_data_PIPO_blk[0] | proc_12_start_FIFO_blk[0] | proc_12_TLF_FIFO_blk[0] | proc_12_input_sync_blk[0] | proc_12_output_sync_blk[0]);
    assign proc_12_data_FIFO_blk[1] = 1'b0 | (~grp_dataflow_wrapper_fu_6443.task_compute_attn_U0.grp_do_attn_1_fu_5150.do_adapt_7_U0.resi_o_sm_blk_n);
    assign proc_12_data_PIPO_blk[1] = 1'b0;
    assign proc_12_start_FIFO_blk[1] = 1'b0 | (~grp_dataflow_wrapper_fu_6443.task_compute_attn_U0.grp_do_attn_1_fu_5150.start_for_stream_merge_1_U0_U.if_full_n & grp_dataflow_wrapper_fu_6443.task_compute_attn_U0.grp_do_attn_1_fu_5150.do_adapt_7_U0.ap_start & ~grp_dataflow_wrapper_fu_6443.task_compute_attn_U0.grp_do_attn_1_fu_5150.do_adapt_7_U0.real_start & (trans_in_cnt_29 == trans_out_cnt_29) & ~grp_dataflow_wrapper_fu_6443.task_compute_attn_U0.grp_do_attn_1_fu_5150.start_for_stream_merge_1_U0_U.if_read);
    assign proc_12_TLF_FIFO_blk[1] = 1'b0;
    assign proc_12_input_sync_blk[1] = 1'b0;
    assign proc_12_output_sync_blk[1] = 1'b0;
    assign proc_dep_vld_vec_12[1] = dl_detect_out ? proc_dep_vld_vec_12_reg[1] : (proc_12_data_FIFO_blk[1] | proc_12_data_PIPO_blk[1] | proc_12_start_FIFO_blk[1] | proc_12_TLF_FIFO_blk[1] | proc_12_input_sync_blk[1] | proc_12_output_sync_blk[1]);
    always @ (negedge dl_reset or posedge dl_clock) begin
        if (~dl_reset) begin
            proc_dep_vld_vec_12_reg <= 'b0;
        end
        else begin
            proc_dep_vld_vec_12_reg <= proc_dep_vld_vec_12;
        end
    end
    assign in_chan_dep_vld_vec_12[0] = dep_chan_vld_11_12;
    assign in_chan_dep_data_vec_12[73 : 0] = dep_chan_data_11_12;
    assign token_in_vec_12[0] = token_11_12;
    assign in_chan_dep_vld_vec_12[1] = dep_chan_vld_46_12;
    assign in_chan_dep_data_vec_12[147 : 74] = dep_chan_data_46_12;
    assign token_in_vec_12[1] = token_46_12;
    assign dep_chan_vld_12_11 = out_chan_dep_vld_vec_12[0];
    assign dep_chan_data_12_11 = out_chan_dep_data_12;
    assign token_12_11 = token_out_vec_12[0];
    assign dep_chan_vld_12_46 = out_chan_dep_vld_vec_12[1];
    assign dep_chan_data_12_46 = out_chan_dep_data_12;
    assign token_12_46 = token_out_vec_12[1];

    // Process: grp_dataflow_wrapper_fu_6443.task_compute_attn_U0.grp_do_attn_1_fu_5150.do_layernorm_inter_token_1_U0
    vit_block_top_hls_deadlock_detect_unit #(74, 13, 2, 2) vit_block_top_hls_deadlock_detect_unit_13 (
        .reset(dl_reset),
        .clock(dl_clock),
        .proc_dep_vld_vec(proc_dep_vld_vec_13),
        .in_chan_dep_vld_vec(in_chan_dep_vld_vec_13),
        .in_chan_dep_data_vec(in_chan_dep_data_vec_13),
        .token_in_vec(token_in_vec_13),
        .dl_detect_in(dl_detect_out),
        .origin(origin[13]),
        .token_clear(token_clear),
        .out_chan_dep_vld_vec(out_chan_dep_vld_vec_13),
        .out_chan_dep_data(out_chan_dep_data_13),
        .token_out_vec(token_out_vec_13),
        .dl_detect_out(dl_in_vec[13]));

    assign proc_13_data_FIFO_blk[0] = 1'b0 | (~grp_dataflow_wrapper_fu_6443.task_compute_attn_U0.grp_do_attn_1_fu_5150.do_layernorm_inter_token_1_U0.grp_do_layernorm_inter_token_1_Pipeline_WAVE_LOOP_CT_PIPELINE_LOOP_fu_138.lnq_sm_blk_n);
    assign proc_13_data_PIPO_blk[0] = 1'b0;
    assign proc_13_start_FIFO_blk[0] = 1'b0 | (~grp_dataflow_wrapper_fu_6443.task_compute_attn_U0.grp_do_attn_1_fu_5150.start_for_stream_copy3_U0_U.if_full_n & grp_dataflow_wrapper_fu_6443.task_compute_attn_U0.grp_do_attn_1_fu_5150.do_layernorm_inter_token_1_U0.ap_start & ~grp_dataflow_wrapper_fu_6443.task_compute_attn_U0.grp_do_attn_1_fu_5150.do_layernorm_inter_token_1_U0.real_start & (trans_in_cnt_5 == trans_out_cnt_5) & ~grp_dataflow_wrapper_fu_6443.task_compute_attn_U0.grp_do_attn_1_fu_5150.start_for_stream_copy3_U0_U.if_read);
    assign proc_13_TLF_FIFO_blk[0] = 1'b0;
    assign proc_13_input_sync_blk[0] = 1'b0;
    assign proc_13_output_sync_blk[0] = 1'b0;
    assign proc_dep_vld_vec_13[0] = dl_detect_out ? proc_dep_vld_vec_13_reg[0] : (proc_13_data_FIFO_blk[0] | proc_13_data_PIPO_blk[0] | proc_13_start_FIFO_blk[0] | proc_13_TLF_FIFO_blk[0] | proc_13_input_sync_blk[0] | proc_13_output_sync_blk[0]);
    assign proc_13_data_FIFO_blk[1] = 1'b0;
    assign proc_13_data_PIPO_blk[1] = 1'b0;
    assign proc_13_start_FIFO_blk[1] = 1'b0;
    assign proc_13_TLF_FIFO_blk[1] = 1'b0;
    assign proc_13_input_sync_blk[1] = 1'b0 | (grp_dataflow_wrapper_fu_6443.task_compute_attn_U0.grp_do_attn_1_fu_5150.ap_sync_do_layernorm_inter_token_1_U0_ap_ready & grp_dataflow_wrapper_fu_6443.task_compute_attn_U0.grp_do_attn_1_fu_5150.do_layernorm_inter_token_1_U0.ap_idle & ~grp_dataflow_wrapper_fu_6443.task_compute_attn_U0.grp_do_attn_1_fu_5150.ap_sync_do_adapt_10_U0_ap_ready);
    assign proc_13_output_sync_blk[1] = 1'b0;
    assign proc_dep_vld_vec_13[1] = dl_detect_out ? proc_dep_vld_vec_13_reg[1] : (proc_13_data_FIFO_blk[1] | proc_13_data_PIPO_blk[1] | proc_13_start_FIFO_blk[1] | proc_13_TLF_FIFO_blk[1] | proc_13_input_sync_blk[1] | proc_13_output_sync_blk[1]);
    always @ (negedge dl_reset or posedge dl_clock) begin
        if (~dl_reset) begin
            proc_dep_vld_vec_13_reg <= 'b0;
        end
        else begin
            proc_dep_vld_vec_13_reg <= proc_dep_vld_vec_13;
        end
    end
    assign in_chan_dep_vld_vec_13[0] = dep_chan_vld_11_13;
    assign in_chan_dep_data_vec_13[73 : 0] = dep_chan_data_11_13;
    assign token_in_vec_13[0] = token_11_13;
    assign in_chan_dep_vld_vec_13[1] = dep_chan_vld_14_13;
    assign in_chan_dep_data_vec_13[147 : 74] = dep_chan_data_14_13;
    assign token_in_vec_13[1] = token_14_13;
    assign dep_chan_vld_13_14 = out_chan_dep_vld_vec_13[0];
    assign dep_chan_data_13_14 = out_chan_dep_data_13;
    assign token_13_14 = token_out_vec_13[0];
    assign dep_chan_vld_13_11 = out_chan_dep_vld_vec_13[1];
    assign dep_chan_data_13_11 = out_chan_dep_data_13;
    assign token_13_11 = token_out_vec_13[1];

    // Process: grp_dataflow_wrapper_fu_6443.task_compute_attn_U0.grp_do_attn_1_fu_5150.stream_copy3_U0
    vit_block_top_hls_deadlock_detect_unit #(74, 14, 7, 7) vit_block_top_hls_deadlock_detect_unit_14 (
        .reset(dl_reset),
        .clock(dl_clock),
        .proc_dep_vld_vec(proc_dep_vld_vec_14),
        .in_chan_dep_vld_vec(in_chan_dep_vld_vec_14),
        .in_chan_dep_data_vec(in_chan_dep_data_vec_14),
        .token_in_vec(token_in_vec_14),
        .dl_detect_in(dl_detect_out),
        .origin(origin[14]),
        .token_clear(token_clear),
        .out_chan_dep_vld_vec(out_chan_dep_vld_vec_14),
        .out_chan_dep_data(out_chan_dep_data_14),
        .token_out_vec(token_out_vec_14),
        .dl_detect_out(dl_in_vec[14]));

    assign proc_14_data_FIFO_blk[0] = 1'b0 | (~grp_dataflow_wrapper_fu_6443.task_compute_attn_U0.grp_do_attn_1_fu_5150.stream_copy3_U0.lnq_sm_blk_n);
    assign proc_14_data_PIPO_blk[0] = 1'b0;
    assign proc_14_start_FIFO_blk[0] = 1'b0 | (~grp_dataflow_wrapper_fu_6443.task_compute_attn_U0.grp_do_attn_1_fu_5150.start_for_stream_copy3_U0_U.if_empty_n & grp_dataflow_wrapper_fu_6443.task_compute_attn_U0.grp_do_attn_1_fu_5150.stream_copy3_U0.ap_idle & ~grp_dataflow_wrapper_fu_6443.task_compute_attn_U0.grp_do_attn_1_fu_5150.start_for_stream_copy3_U0_U.if_write);
    assign proc_14_TLF_FIFO_blk[0] = 1'b0;
    assign proc_14_input_sync_blk[0] = 1'b0;
    assign proc_14_output_sync_blk[0] = 1'b0;
    assign proc_dep_vld_vec_14[0] = dl_detect_out ? proc_dep_vld_vec_14_reg[0] : (proc_14_data_FIFO_blk[0] | proc_14_data_PIPO_blk[0] | proc_14_start_FIFO_blk[0] | proc_14_TLF_FIFO_blk[0] | proc_14_input_sync_blk[0] | proc_14_output_sync_blk[0]);
    assign proc_14_data_FIFO_blk[1] = 1'b0 | (~grp_dataflow_wrapper_fu_6443.task_compute_attn_U0.grp_do_attn_1_fu_5150.stream_copy3_U0.lnq_sm_cp1_blk_n);
    assign proc_14_data_PIPO_blk[1] = 1'b0;
    assign proc_14_start_FIFO_blk[1] = 1'b0 | (~grp_dataflow_wrapper_fu_6443.task_compute_attn_U0.grp_do_attn_1_fu_5150.start_for_do_matmul_2_U0_U.if_full_n & grp_dataflow_wrapper_fu_6443.task_compute_attn_U0.grp_do_attn_1_fu_5150.stream_copy3_U0.ap_start & ~grp_dataflow_wrapper_fu_6443.task_compute_attn_U0.grp_do_attn_1_fu_5150.stream_copy3_U0.real_start & (trans_in_cnt_6 == trans_out_cnt_6) & ~grp_dataflow_wrapper_fu_6443.task_compute_attn_U0.grp_do_attn_1_fu_5150.start_for_do_matmul_2_U0_U.if_read);
    assign proc_14_TLF_FIFO_blk[1] = 1'b0;
    assign proc_14_input_sync_blk[1] = 1'b0;
    assign proc_14_output_sync_blk[1] = 1'b0;
    assign proc_dep_vld_vec_14[1] = dl_detect_out ? proc_dep_vld_vec_14_reg[1] : (proc_14_data_FIFO_blk[1] | proc_14_data_PIPO_blk[1] | proc_14_start_FIFO_blk[1] | proc_14_TLF_FIFO_blk[1] | proc_14_input_sync_blk[1] | proc_14_output_sync_blk[1]);
    assign proc_14_data_FIFO_blk[2] = 1'b0 | (~grp_dataflow_wrapper_fu_6443.task_compute_attn_U0.grp_do_attn_1_fu_5150.stream_copy3_U0.lnq_sm_cp1_blk_n);
    assign proc_14_data_PIPO_blk[2] = 1'b0;
    assign proc_14_start_FIFO_blk[2] = 1'b0;
    assign proc_14_TLF_FIFO_blk[2] = 1'b0;
    assign proc_14_input_sync_blk[2] = 1'b0;
    assign proc_14_output_sync_blk[2] = 1'b0;
    assign proc_dep_vld_vec_14[2] = dl_detect_out ? proc_dep_vld_vec_14_reg[2] : (proc_14_data_FIFO_blk[2] | proc_14_data_PIPO_blk[2] | proc_14_start_FIFO_blk[2] | proc_14_TLF_FIFO_blk[2] | proc_14_input_sync_blk[2] | proc_14_output_sync_blk[2]);
    assign proc_14_data_FIFO_blk[3] = 1'b0 | (~grp_dataflow_wrapper_fu_6443.task_compute_attn_U0.grp_do_attn_1_fu_5150.stream_copy3_U0.lnq_sm_cp2_blk_n);
    assign proc_14_data_PIPO_blk[3] = 1'b0;
    assign proc_14_start_FIFO_blk[3] = 1'b0 | (~grp_dataflow_wrapper_fu_6443.task_compute_attn_U0.grp_do_attn_1_fu_5150.start_for_do_matmul_2_1_U0_U.if_full_n & grp_dataflow_wrapper_fu_6443.task_compute_attn_U0.grp_do_attn_1_fu_5150.stream_copy3_U0.ap_start & ~grp_dataflow_wrapper_fu_6443.task_compute_attn_U0.grp_do_attn_1_fu_5150.stream_copy3_U0.real_start & (trans_in_cnt_6 == trans_out_cnt_6) & ~grp_dataflow_wrapper_fu_6443.task_compute_attn_U0.grp_do_attn_1_fu_5150.start_for_do_matmul_2_1_U0_U.if_read);
    assign proc_14_TLF_FIFO_blk[3] = 1'b0;
    assign proc_14_input_sync_blk[3] = 1'b0;
    assign proc_14_output_sync_blk[3] = 1'b0;
    assign proc_dep_vld_vec_14[3] = dl_detect_out ? proc_dep_vld_vec_14_reg[3] : (proc_14_data_FIFO_blk[3] | proc_14_data_PIPO_blk[3] | proc_14_start_FIFO_blk[3] | proc_14_TLF_FIFO_blk[3] | proc_14_input_sync_blk[3] | proc_14_output_sync_blk[3]);
    assign proc_14_data_FIFO_blk[4] = 1'b0 | (~grp_dataflow_wrapper_fu_6443.task_compute_attn_U0.grp_do_attn_1_fu_5150.stream_copy3_U0.lnq_sm_cp2_blk_n);
    assign proc_14_data_PIPO_blk[4] = 1'b0;
    assign proc_14_start_FIFO_blk[4] = 1'b0;
    assign proc_14_TLF_FIFO_blk[4] = 1'b0;
    assign proc_14_input_sync_blk[4] = 1'b0;
    assign proc_14_output_sync_blk[4] = 1'b0;
    assign proc_dep_vld_vec_14[4] = dl_detect_out ? proc_dep_vld_vec_14_reg[4] : (proc_14_data_FIFO_blk[4] | proc_14_data_PIPO_blk[4] | proc_14_start_FIFO_blk[4] | proc_14_TLF_FIFO_blk[4] | proc_14_input_sync_blk[4] | proc_14_output_sync_blk[4]);
    assign proc_14_data_FIFO_blk[5] = 1'b0 | (~grp_dataflow_wrapper_fu_6443.task_compute_attn_U0.grp_do_attn_1_fu_5150.stream_copy3_U0.lnq_sm_cp3_blk_n);
    assign proc_14_data_PIPO_blk[5] = 1'b0;
    assign proc_14_start_FIFO_blk[5] = 1'b0 | (~grp_dataflow_wrapper_fu_6443.task_compute_attn_U0.grp_do_attn_1_fu_5150.start_for_do_matmul_4_U0_U.if_full_n & grp_dataflow_wrapper_fu_6443.task_compute_attn_U0.grp_do_attn_1_fu_5150.stream_copy3_U0.ap_start & ~grp_dataflow_wrapper_fu_6443.task_compute_attn_U0.grp_do_attn_1_fu_5150.stream_copy3_U0.real_start & (trans_in_cnt_6 == trans_out_cnt_6) & ~grp_dataflow_wrapper_fu_6443.task_compute_attn_U0.grp_do_attn_1_fu_5150.start_for_do_matmul_4_U0_U.if_read);
    assign proc_14_TLF_FIFO_blk[5] = 1'b0;
    assign proc_14_input_sync_blk[5] = 1'b0;
    assign proc_14_output_sync_blk[5] = 1'b0;
    assign proc_dep_vld_vec_14[5] = dl_detect_out ? proc_dep_vld_vec_14_reg[5] : (proc_14_data_FIFO_blk[5] | proc_14_data_PIPO_blk[5] | proc_14_start_FIFO_blk[5] | proc_14_TLF_FIFO_blk[5] | proc_14_input_sync_blk[5] | proc_14_output_sync_blk[5]);
    assign proc_14_data_FIFO_blk[6] = 1'b0 | (~grp_dataflow_wrapper_fu_6443.task_compute_attn_U0.grp_do_attn_1_fu_5150.stream_copy3_U0.lnq_sm_cp3_blk_n);
    assign proc_14_data_PIPO_blk[6] = 1'b0;
    assign proc_14_start_FIFO_blk[6] = 1'b0;
    assign proc_14_TLF_FIFO_blk[6] = 1'b0;
    assign proc_14_input_sync_blk[6] = 1'b0;
    assign proc_14_output_sync_blk[6] = 1'b0;
    assign proc_dep_vld_vec_14[6] = dl_detect_out ? proc_dep_vld_vec_14_reg[6] : (proc_14_data_FIFO_blk[6] | proc_14_data_PIPO_blk[6] | proc_14_start_FIFO_blk[6] | proc_14_TLF_FIFO_blk[6] | proc_14_input_sync_blk[6] | proc_14_output_sync_blk[6]);
    always @ (negedge dl_reset or posedge dl_clock) begin
        if (~dl_reset) begin
            proc_dep_vld_vec_14_reg <= 'b0;
        end
        else begin
            proc_dep_vld_vec_14_reg <= proc_dep_vld_vec_14;
        end
    end
    assign in_chan_dep_vld_vec_14[0] = dep_chan_vld_13_14;
    assign in_chan_dep_data_vec_14[73 : 0] = dep_chan_data_13_14;
    assign token_in_vec_14[0] = token_13_14;
    assign in_chan_dep_vld_vec_14[1] = dep_chan_vld_15_14;
    assign in_chan_dep_data_vec_14[147 : 74] = dep_chan_data_15_14;
    assign token_in_vec_14[1] = token_15_14;
    assign in_chan_dep_vld_vec_14[2] = dep_chan_vld_16_14;
    assign in_chan_dep_data_vec_14[221 : 148] = dep_chan_data_16_14;
    assign token_in_vec_14[2] = token_16_14;
    assign in_chan_dep_vld_vec_14[3] = dep_chan_vld_20_14;
    assign in_chan_dep_data_vec_14[295 : 222] = dep_chan_data_20_14;
    assign token_in_vec_14[3] = token_20_14;
    assign in_chan_dep_vld_vec_14[4] = dep_chan_vld_21_14;
    assign in_chan_dep_data_vec_14[369 : 296] = dep_chan_data_21_14;
    assign token_in_vec_14[4] = token_21_14;
    assign in_chan_dep_vld_vec_14[5] = dep_chan_vld_25_14;
    assign in_chan_dep_data_vec_14[443 : 370] = dep_chan_data_25_14;
    assign token_in_vec_14[5] = token_25_14;
    assign in_chan_dep_vld_vec_14[6] = dep_chan_vld_26_14;
    assign in_chan_dep_data_vec_14[517 : 444] = dep_chan_data_26_14;
    assign token_in_vec_14[6] = token_26_14;
    assign dep_chan_vld_14_13 = out_chan_dep_vld_vec_14[0];
    assign dep_chan_data_14_13 = out_chan_dep_data_14;
    assign token_14_13 = token_out_vec_14[0];
    assign dep_chan_vld_14_15 = out_chan_dep_vld_vec_14[1];
    assign dep_chan_data_14_15 = out_chan_dep_data_14;
    assign token_14_15 = token_out_vec_14[1];
    assign dep_chan_vld_14_16 = out_chan_dep_vld_vec_14[2];
    assign dep_chan_data_14_16 = out_chan_dep_data_14;
    assign token_14_16 = token_out_vec_14[2];
    assign dep_chan_vld_14_20 = out_chan_dep_vld_vec_14[3];
    assign dep_chan_data_14_20 = out_chan_dep_data_14;
    assign token_14_20 = token_out_vec_14[3];
    assign dep_chan_vld_14_21 = out_chan_dep_vld_vec_14[4];
    assign dep_chan_data_14_21 = out_chan_dep_data_14;
    assign token_14_21 = token_out_vec_14[4];
    assign dep_chan_vld_14_25 = out_chan_dep_vld_vec_14[5];
    assign dep_chan_data_14_25 = out_chan_dep_data_14;
    assign token_14_25 = token_out_vec_14[5];
    assign dep_chan_vld_14_26 = out_chan_dep_vld_vec_14[6];
    assign dep_chan_data_14_26 = out_chan_dep_data_14;
    assign token_14_26 = token_out_vec_14[6];

    // Process: grp_dataflow_wrapper_fu_6443.task_compute_attn_U0.grp_do_attn_1_fu_5150.do_matmul_2_U0
    vit_block_top_hls_deadlock_detect_unit #(74, 15, 2, 2) vit_block_top_hls_deadlock_detect_unit_15 (
        .reset(dl_reset),
        .clock(dl_clock),
        .proc_dep_vld_vec(proc_dep_vld_vec_15),
        .in_chan_dep_vld_vec(in_chan_dep_vld_vec_15),
        .in_chan_dep_data_vec(in_chan_dep_data_vec_15),
        .token_in_vec(token_in_vec_15),
        .dl_detect_in(dl_detect_out),
        .origin(origin[15]),
        .token_clear(token_clear),
        .out_chan_dep_vld_vec(out_chan_dep_vld_vec_15),
        .out_chan_dep_data(out_chan_dep_data_15),
        .token_out_vec(token_out_vec_15),
        .dl_detect_out(dl_in_vec[15]));

    assign proc_15_data_FIFO_blk[0] = 1'b0 | (~grp_dataflow_wrapper_fu_6443.task_compute_attn_U0.grp_do_attn_1_fu_5150.do_matmul_2_U0.do_adapt_2_U0.lnq_sm_cp1_blk_n);
    assign proc_15_data_PIPO_blk[0] = 1'b0;
    assign proc_15_start_FIFO_blk[0] = 1'b0 | (~grp_dataflow_wrapper_fu_6443.task_compute_attn_U0.grp_do_attn_1_fu_5150.start_for_do_matmul_2_U0_U.if_empty_n & grp_dataflow_wrapper_fu_6443.task_compute_attn_U0.grp_do_attn_1_fu_5150.do_matmul_2_U0.ap_idle & ~grp_dataflow_wrapper_fu_6443.task_compute_attn_U0.grp_do_attn_1_fu_5150.start_for_do_matmul_2_U0_U.if_write);
    assign proc_15_TLF_FIFO_blk[0] = 1'b0;
    assign proc_15_input_sync_blk[0] = 1'b0;
    assign proc_15_output_sync_blk[0] = 1'b0;
    assign proc_dep_vld_vec_15[0] = dl_detect_out ? proc_dep_vld_vec_15_reg[0] : (proc_15_data_FIFO_blk[0] | proc_15_data_PIPO_blk[0] | proc_15_start_FIFO_blk[0] | proc_15_TLF_FIFO_blk[0] | proc_15_input_sync_blk[0] | proc_15_output_sync_blk[0]);
    assign proc_15_data_FIFO_blk[1] = 1'b0 | (~grp_dataflow_wrapper_fu_6443.task_compute_attn_U0.grp_do_attn_1_fu_5150.do_matmul_2_U0.do_adapt_11_U0.q_sm_blk_n);
    assign proc_15_data_PIPO_blk[1] = 1'b0;
    assign proc_15_start_FIFO_blk[1] = 1'b0 | (~grp_dataflow_wrapper_fu_6443.task_compute_attn_U0.grp_do_attn_1_fu_5150.start_for_do_quant_U0_U.if_full_n & grp_dataflow_wrapper_fu_6443.task_compute_attn_U0.grp_do_attn_1_fu_5150.do_matmul_2_U0.ap_start & ~grp_dataflow_wrapper_fu_6443.task_compute_attn_U0.grp_do_attn_1_fu_5150.do_matmul_2_U0.real_start & (trans_in_cnt_16 == trans_out_cnt_16) & ~grp_dataflow_wrapper_fu_6443.task_compute_attn_U0.grp_do_attn_1_fu_5150.start_for_do_quant_U0_U.if_read);
    assign proc_15_TLF_FIFO_blk[1] = 1'b0;
    assign proc_15_input_sync_blk[1] = 1'b0;
    assign proc_15_output_sync_blk[1] = 1'b0;
    assign proc_dep_vld_vec_15[1] = dl_detect_out ? proc_dep_vld_vec_15_reg[1] : (proc_15_data_FIFO_blk[1] | proc_15_data_PIPO_blk[1] | proc_15_start_FIFO_blk[1] | proc_15_TLF_FIFO_blk[1] | proc_15_input_sync_blk[1] | proc_15_output_sync_blk[1]);
    always @ (negedge dl_reset or posedge dl_clock) begin
        if (~dl_reset) begin
            proc_dep_vld_vec_15_reg <= 'b0;
        end
        else begin
            proc_dep_vld_vec_15_reg <= proc_dep_vld_vec_15;
        end
    end
    assign in_chan_dep_vld_vec_15[0] = dep_chan_vld_14_15;
    assign in_chan_dep_data_vec_15[73 : 0] = dep_chan_data_14_15;
    assign token_in_vec_15[0] = token_14_15;
    assign in_chan_dep_vld_vec_15[1] = dep_chan_vld_30_15;
    assign in_chan_dep_data_vec_15[147 : 74] = dep_chan_data_30_15;
    assign token_in_vec_15[1] = token_30_15;
    assign dep_chan_vld_15_14 = out_chan_dep_vld_vec_15[0];
    assign dep_chan_data_15_14 = out_chan_dep_data_15;
    assign token_15_14 = token_out_vec_15[0];
    assign dep_chan_vld_15_30 = out_chan_dep_vld_vec_15[1];
    assign dep_chan_data_15_30 = out_chan_dep_data_15;
    assign token_15_30 = token_out_vec_15[1];

    // Process: grp_dataflow_wrapper_fu_6443.task_compute_attn_U0.grp_do_attn_1_fu_5150.do_matmul_2_U0.do_adapt_2_U0
    vit_block_top_hls_deadlock_detect_unit #(74, 16, 2, 2) vit_block_top_hls_deadlock_detect_unit_16 (
        .reset(dl_reset),
        .clock(dl_clock),
        .proc_dep_vld_vec(proc_dep_vld_vec_16),
        .in_chan_dep_vld_vec(in_chan_dep_vld_vec_16),
        .in_chan_dep_data_vec(in_chan_dep_data_vec_16),
        .token_in_vec(token_in_vec_16),
        .dl_detect_in(dl_detect_out),
        .origin(origin[16]),
        .token_clear(token_clear),
        .out_chan_dep_vld_vec(out_chan_dep_vld_vec_16),
        .out_chan_dep_data(out_chan_dep_data_16),
        .token_out_vec(token_out_vec_16),
        .dl_detect_out(dl_in_vec[16]));

    assign proc_16_data_FIFO_blk[0] = 1'b0 | (~grp_dataflow_wrapper_fu_6443.task_compute_attn_U0.grp_do_attn_1_fu_5150.do_matmul_2_U0.do_adapt_2_U0.lnq_sm_cp1_blk_n);
    assign proc_16_data_PIPO_blk[0] = 1'b0;
    assign proc_16_start_FIFO_blk[0] = 1'b0;
    assign proc_16_TLF_FIFO_blk[0] = 1'b0;
    assign proc_16_input_sync_blk[0] = 1'b0;
    assign proc_16_output_sync_blk[0] = 1'b0;
    assign proc_dep_vld_vec_16[0] = dl_detect_out ? proc_dep_vld_vec_16_reg[0] : (proc_16_data_FIFO_blk[0] | proc_16_data_PIPO_blk[0] | proc_16_start_FIFO_blk[0] | proc_16_TLF_FIFO_blk[0] | proc_16_input_sync_blk[0] | proc_16_output_sync_blk[0]);
    assign proc_16_data_FIFO_blk[1] = 1'b0 | (~grp_dataflow_wrapper_fu_6443.task_compute_attn_U0.grp_do_attn_1_fu_5150.do_matmul_2_U0.do_adapt_2_U0.adpt_sm_blk_n);
    assign proc_16_data_PIPO_blk[1] = 1'b0;
    assign proc_16_start_FIFO_blk[1] = 1'b0 | (~grp_dataflow_wrapper_fu_6443.task_compute_attn_U0.grp_do_attn_1_fu_5150.do_matmul_2_U0.start_for_matmul_step1_cache_window_2_U0_U.if_full_n & grp_dataflow_wrapper_fu_6443.task_compute_attn_U0.grp_do_attn_1_fu_5150.do_matmul_2_U0.do_adapt_2_U0.ap_start & ~grp_dataflow_wrapper_fu_6443.task_compute_attn_U0.grp_do_attn_1_fu_5150.do_matmul_2_U0.do_adapt_2_U0.real_start & (trans_in_cnt_7 == trans_out_cnt_7) & ~grp_dataflow_wrapper_fu_6443.task_compute_attn_U0.grp_do_attn_1_fu_5150.do_matmul_2_U0.start_for_matmul_step1_cache_window_2_U0_U.if_read);
    assign proc_16_TLF_FIFO_blk[1] = 1'b0;
    assign proc_16_input_sync_blk[1] = 1'b0;
    assign proc_16_output_sync_blk[1] = 1'b0;
    assign proc_dep_vld_vec_16[1] = dl_detect_out ? proc_dep_vld_vec_16_reg[1] : (proc_16_data_FIFO_blk[1] | proc_16_data_PIPO_blk[1] | proc_16_start_FIFO_blk[1] | proc_16_TLF_FIFO_blk[1] | proc_16_input_sync_blk[1] | proc_16_output_sync_blk[1]);
    always @ (negedge dl_reset or posedge dl_clock) begin
        if (~dl_reset) begin
            proc_dep_vld_vec_16_reg <= 'b0;
        end
        else begin
            proc_dep_vld_vec_16_reg <= proc_dep_vld_vec_16;
        end
    end
    assign in_chan_dep_vld_vec_16[0] = dep_chan_vld_14_16;
    assign in_chan_dep_data_vec_16[73 : 0] = dep_chan_data_14_16;
    assign token_in_vec_16[0] = token_14_16;
    assign in_chan_dep_vld_vec_16[1] = dep_chan_vld_17_16;
    assign in_chan_dep_data_vec_16[147 : 74] = dep_chan_data_17_16;
    assign token_in_vec_16[1] = token_17_16;
    assign dep_chan_vld_16_14 = out_chan_dep_vld_vec_16[0];
    assign dep_chan_data_16_14 = out_chan_dep_data_16;
    assign token_16_14 = token_out_vec_16[0];
    assign dep_chan_vld_16_17 = out_chan_dep_vld_vec_16[1];
    assign dep_chan_data_16_17 = out_chan_dep_data_16;
    assign token_16_17 = token_out_vec_16[1];

    // Process: grp_dataflow_wrapper_fu_6443.task_compute_attn_U0.grp_do_attn_1_fu_5150.do_matmul_2_U0.matmul_step1_cache_window_2_U0
    vit_block_top_hls_deadlock_detect_unit #(74, 17, 2, 2) vit_block_top_hls_deadlock_detect_unit_17 (
        .reset(dl_reset),
        .clock(dl_clock),
        .proc_dep_vld_vec(proc_dep_vld_vec_17),
        .in_chan_dep_vld_vec(in_chan_dep_vld_vec_17),
        .in_chan_dep_data_vec(in_chan_dep_data_vec_17),
        .token_in_vec(token_in_vec_17),
        .dl_detect_in(dl_detect_out),
        .origin(origin[17]),
        .token_clear(token_clear),
        .out_chan_dep_vld_vec(out_chan_dep_vld_vec_17),
        .out_chan_dep_data(out_chan_dep_data_17),
        .token_out_vec(token_out_vec_17),
        .dl_detect_out(dl_in_vec[17]));

    assign proc_17_data_FIFO_blk[0] = 1'b0 | (~grp_dataflow_wrapper_fu_6443.task_compute_attn_U0.grp_do_attn_1_fu_5150.do_matmul_2_U0.matmul_step1_cache_window_2_U0.adpt_sm_blk_n);
    assign proc_17_data_PIPO_blk[0] = 1'b0;
    assign proc_17_start_FIFO_blk[0] = 1'b0 | (~grp_dataflow_wrapper_fu_6443.task_compute_attn_U0.grp_do_attn_1_fu_5150.do_matmul_2_U0.start_for_matmul_step1_cache_window_2_U0_U.if_empty_n & grp_dataflow_wrapper_fu_6443.task_compute_attn_U0.grp_do_attn_1_fu_5150.do_matmul_2_U0.matmul_step1_cache_window_2_U0.ap_idle & ~grp_dataflow_wrapper_fu_6443.task_compute_attn_U0.grp_do_attn_1_fu_5150.do_matmul_2_U0.start_for_matmul_step1_cache_window_2_U0_U.if_write);
    assign proc_17_TLF_FIFO_blk[0] = 1'b0;
    assign proc_17_input_sync_blk[0] = 1'b0;
    assign proc_17_output_sync_blk[0] = 1'b0;
    assign proc_dep_vld_vec_17[0] = dl_detect_out ? proc_dep_vld_vec_17_reg[0] : (proc_17_data_FIFO_blk[0] | proc_17_data_PIPO_blk[0] | proc_17_start_FIFO_blk[0] | proc_17_TLF_FIFO_blk[0] | proc_17_input_sync_blk[0] | proc_17_output_sync_blk[0]);
    assign proc_17_data_FIFO_blk[1] = 1'b0 | (~grp_dataflow_wrapper_fu_6443.task_compute_attn_U0.grp_do_attn_1_fu_5150.do_matmul_2_U0.matmul_step1_cache_window_2_U0.cache_window_sm_blk_n);
    assign proc_17_data_PIPO_blk[1] = 1'b0;
    assign proc_17_start_FIFO_blk[1] = 1'b0 | (~grp_dataflow_wrapper_fu_6443.task_compute_attn_U0.grp_do_attn_1_fu_5150.do_matmul_2_U0.start_for_matmul_step2_mac_2_U0_U.if_full_n & grp_dataflow_wrapper_fu_6443.task_compute_attn_U0.grp_do_attn_1_fu_5150.do_matmul_2_U0.matmul_step1_cache_window_2_U0.ap_start & ~grp_dataflow_wrapper_fu_6443.task_compute_attn_U0.grp_do_attn_1_fu_5150.do_matmul_2_U0.matmul_step1_cache_window_2_U0.real_start & (trans_in_cnt_8 == trans_out_cnt_8) & ~grp_dataflow_wrapper_fu_6443.task_compute_attn_U0.grp_do_attn_1_fu_5150.do_matmul_2_U0.start_for_matmul_step2_mac_2_U0_U.if_read);
    assign proc_17_TLF_FIFO_blk[1] = 1'b0;
    assign proc_17_input_sync_blk[1] = 1'b0;
    assign proc_17_output_sync_blk[1] = 1'b0;
    assign proc_dep_vld_vec_17[1] = dl_detect_out ? proc_dep_vld_vec_17_reg[1] : (proc_17_data_FIFO_blk[1] | proc_17_data_PIPO_blk[1] | proc_17_start_FIFO_blk[1] | proc_17_TLF_FIFO_blk[1] | proc_17_input_sync_blk[1] | proc_17_output_sync_blk[1]);
    always @ (negedge dl_reset or posedge dl_clock) begin
        if (~dl_reset) begin
            proc_dep_vld_vec_17_reg <= 'b0;
        end
        else begin
            proc_dep_vld_vec_17_reg <= proc_dep_vld_vec_17;
        end
    end
    assign in_chan_dep_vld_vec_17[0] = dep_chan_vld_16_17;
    assign in_chan_dep_data_vec_17[73 : 0] = dep_chan_data_16_17;
    assign token_in_vec_17[0] = token_16_17;
    assign in_chan_dep_vld_vec_17[1] = dep_chan_vld_18_17;
    assign in_chan_dep_data_vec_17[147 : 74] = dep_chan_data_18_17;
    assign token_in_vec_17[1] = token_18_17;
    assign dep_chan_vld_17_16 = out_chan_dep_vld_vec_17[0];
    assign dep_chan_data_17_16 = out_chan_dep_data_17;
    assign token_17_16 = token_out_vec_17[0];
    assign dep_chan_vld_17_18 = out_chan_dep_vld_vec_17[1];
    assign dep_chan_data_17_18 = out_chan_dep_data_17;
    assign token_17_18 = token_out_vec_17[1];

    // Process: grp_dataflow_wrapper_fu_6443.task_compute_attn_U0.grp_do_attn_1_fu_5150.do_matmul_2_U0.matmul_step2_mac_2_U0
    vit_block_top_hls_deadlock_detect_unit #(74, 18, 2, 2) vit_block_top_hls_deadlock_detect_unit_18 (
        .reset(dl_reset),
        .clock(dl_clock),
        .proc_dep_vld_vec(proc_dep_vld_vec_18),
        .in_chan_dep_vld_vec(in_chan_dep_vld_vec_18),
        .in_chan_dep_data_vec(in_chan_dep_data_vec_18),
        .token_in_vec(token_in_vec_18),
        .dl_detect_in(dl_detect_out),
        .origin(origin[18]),
        .token_clear(token_clear),
        .out_chan_dep_vld_vec(out_chan_dep_vld_vec_18),
        .out_chan_dep_data(out_chan_dep_data_18),
        .token_out_vec(token_out_vec_18),
        .dl_detect_out(dl_in_vec[18]));

    assign proc_18_data_FIFO_blk[0] = 1'b0 | (~grp_dataflow_wrapper_fu_6443.task_compute_attn_U0.grp_do_attn_1_fu_5150.do_matmul_2_U0.matmul_step2_mac_2_U0.cache_window_sm_blk_n);
    assign proc_18_data_PIPO_blk[0] = 1'b0;
    assign proc_18_start_FIFO_blk[0] = 1'b0 | (~grp_dataflow_wrapper_fu_6443.task_compute_attn_U0.grp_do_attn_1_fu_5150.do_matmul_2_U0.start_for_matmul_step2_mac_2_U0_U.if_empty_n & grp_dataflow_wrapper_fu_6443.task_compute_attn_U0.grp_do_attn_1_fu_5150.do_matmul_2_U0.matmul_step2_mac_2_U0.ap_idle & ~grp_dataflow_wrapper_fu_6443.task_compute_attn_U0.grp_do_attn_1_fu_5150.do_matmul_2_U0.start_for_matmul_step2_mac_2_U0_U.if_write);
    assign proc_18_TLF_FIFO_blk[0] = 1'b0;
    assign proc_18_input_sync_blk[0] = 1'b0;
    assign proc_18_output_sync_blk[0] = 1'b0;
    assign proc_dep_vld_vec_18[0] = dl_detect_out ? proc_dep_vld_vec_18_reg[0] : (proc_18_data_FIFO_blk[0] | proc_18_data_PIPO_blk[0] | proc_18_start_FIFO_blk[0] | proc_18_TLF_FIFO_blk[0] | proc_18_input_sync_blk[0] | proc_18_output_sync_blk[0]);
    assign proc_18_data_FIFO_blk[1] = 1'b0 | (~grp_dataflow_wrapper_fu_6443.task_compute_attn_U0.grp_do_attn_1_fu_5150.do_matmul_2_U0.matmul_step2_mac_2_U0.mac_sm_blk_n);
    assign proc_18_data_PIPO_blk[1] = 1'b0;
    assign proc_18_start_FIFO_blk[1] = 1'b0 | (~grp_dataflow_wrapper_fu_6443.task_compute_attn_U0.grp_do_attn_1_fu_5150.do_matmul_2_U0.start_for_do_adapt_11_U0_U.if_full_n & grp_dataflow_wrapper_fu_6443.task_compute_attn_U0.grp_do_attn_1_fu_5150.do_matmul_2_U0.matmul_step2_mac_2_U0.ap_start & ~grp_dataflow_wrapper_fu_6443.task_compute_attn_U0.grp_do_attn_1_fu_5150.do_matmul_2_U0.matmul_step2_mac_2_U0.real_start & (trans_in_cnt_9 == trans_out_cnt_9) & ~grp_dataflow_wrapper_fu_6443.task_compute_attn_U0.grp_do_attn_1_fu_5150.do_matmul_2_U0.start_for_do_adapt_11_U0_U.if_read);
    assign proc_18_TLF_FIFO_blk[1] = 1'b0;
    assign proc_18_input_sync_blk[1] = 1'b0;
    assign proc_18_output_sync_blk[1] = 1'b0;
    assign proc_dep_vld_vec_18[1] = dl_detect_out ? proc_dep_vld_vec_18_reg[1] : (proc_18_data_FIFO_blk[1] | proc_18_data_PIPO_blk[1] | proc_18_start_FIFO_blk[1] | proc_18_TLF_FIFO_blk[1] | proc_18_input_sync_blk[1] | proc_18_output_sync_blk[1]);
    always @ (negedge dl_reset or posedge dl_clock) begin
        if (~dl_reset) begin
            proc_dep_vld_vec_18_reg <= 'b0;
        end
        else begin
            proc_dep_vld_vec_18_reg <= proc_dep_vld_vec_18;
        end
    end
    assign in_chan_dep_vld_vec_18[0] = dep_chan_vld_17_18;
    assign in_chan_dep_data_vec_18[73 : 0] = dep_chan_data_17_18;
    assign token_in_vec_18[0] = token_17_18;
    assign in_chan_dep_vld_vec_18[1] = dep_chan_vld_19_18;
    assign in_chan_dep_data_vec_18[147 : 74] = dep_chan_data_19_18;
    assign token_in_vec_18[1] = token_19_18;
    assign dep_chan_vld_18_17 = out_chan_dep_vld_vec_18[0];
    assign dep_chan_data_18_17 = out_chan_dep_data_18;
    assign token_18_17 = token_out_vec_18[0];
    assign dep_chan_vld_18_19 = out_chan_dep_vld_vec_18[1];
    assign dep_chan_data_18_19 = out_chan_dep_data_18;
    assign token_18_19 = token_out_vec_18[1];

    // Process: grp_dataflow_wrapper_fu_6443.task_compute_attn_U0.grp_do_attn_1_fu_5150.do_matmul_2_U0.do_adapt_11_U0
    vit_block_top_hls_deadlock_detect_unit #(74, 19, 2, 2) vit_block_top_hls_deadlock_detect_unit_19 (
        .reset(dl_reset),
        .clock(dl_clock),
        .proc_dep_vld_vec(proc_dep_vld_vec_19),
        .in_chan_dep_vld_vec(in_chan_dep_vld_vec_19),
        .in_chan_dep_data_vec(in_chan_dep_data_vec_19),
        .token_in_vec(token_in_vec_19),
        .dl_detect_in(dl_detect_out),
        .origin(origin[19]),
        .token_clear(token_clear),
        .out_chan_dep_vld_vec(out_chan_dep_vld_vec_19),
        .out_chan_dep_data(out_chan_dep_data_19),
        .token_out_vec(token_out_vec_19),
        .dl_detect_out(dl_in_vec[19]));

    assign proc_19_data_FIFO_blk[0] = 1'b0 | (~grp_dataflow_wrapper_fu_6443.task_compute_attn_U0.grp_do_attn_1_fu_5150.do_matmul_2_U0.do_adapt_11_U0.mac_sm_blk_n);
    assign proc_19_data_PIPO_blk[0] = 1'b0;
    assign proc_19_start_FIFO_blk[0] = 1'b0 | (~grp_dataflow_wrapper_fu_6443.task_compute_attn_U0.grp_do_attn_1_fu_5150.do_matmul_2_U0.start_for_do_adapt_11_U0_U.if_empty_n & grp_dataflow_wrapper_fu_6443.task_compute_attn_U0.grp_do_attn_1_fu_5150.do_matmul_2_U0.do_adapt_11_U0.ap_idle & ~grp_dataflow_wrapper_fu_6443.task_compute_attn_U0.grp_do_attn_1_fu_5150.do_matmul_2_U0.start_for_do_adapt_11_U0_U.if_write);
    assign proc_19_TLF_FIFO_blk[0] = 1'b0;
    assign proc_19_input_sync_blk[0] = 1'b0;
    assign proc_19_output_sync_blk[0] = 1'b0;
    assign proc_dep_vld_vec_19[0] = dl_detect_out ? proc_dep_vld_vec_19_reg[0] : (proc_19_data_FIFO_blk[0] | proc_19_data_PIPO_blk[0] | proc_19_start_FIFO_blk[0] | proc_19_TLF_FIFO_blk[0] | proc_19_input_sync_blk[0] | proc_19_output_sync_blk[0]);
    assign proc_19_data_FIFO_blk[1] = 1'b0 | (~grp_dataflow_wrapper_fu_6443.task_compute_attn_U0.grp_do_attn_1_fu_5150.do_matmul_2_U0.do_adapt_11_U0.q_sm_blk_n);
    assign proc_19_data_PIPO_blk[1] = 1'b0;
    assign proc_19_start_FIFO_blk[1] = 1'b0;
    assign proc_19_TLF_FIFO_blk[1] = 1'b0;
    assign proc_19_input_sync_blk[1] = 1'b0;
    assign proc_19_output_sync_blk[1] = 1'b0;
    assign proc_dep_vld_vec_19[1] = dl_detect_out ? proc_dep_vld_vec_19_reg[1] : (proc_19_data_FIFO_blk[1] | proc_19_data_PIPO_blk[1] | proc_19_start_FIFO_blk[1] | proc_19_TLF_FIFO_blk[1] | proc_19_input_sync_blk[1] | proc_19_output_sync_blk[1]);
    always @ (negedge dl_reset or posedge dl_clock) begin
        if (~dl_reset) begin
            proc_dep_vld_vec_19_reg <= 'b0;
        end
        else begin
            proc_dep_vld_vec_19_reg <= proc_dep_vld_vec_19;
        end
    end
    assign in_chan_dep_vld_vec_19[0] = dep_chan_vld_18_19;
    assign in_chan_dep_data_vec_19[73 : 0] = dep_chan_data_18_19;
    assign token_in_vec_19[0] = token_18_19;
    assign in_chan_dep_vld_vec_19[1] = dep_chan_vld_30_19;
    assign in_chan_dep_data_vec_19[147 : 74] = dep_chan_data_30_19;
    assign token_in_vec_19[1] = token_30_19;
    assign dep_chan_vld_19_18 = out_chan_dep_vld_vec_19[0];
    assign dep_chan_data_19_18 = out_chan_dep_data_19;
    assign token_19_18 = token_out_vec_19[0];
    assign dep_chan_vld_19_30 = out_chan_dep_vld_vec_19[1];
    assign dep_chan_data_19_30 = out_chan_dep_data_19;
    assign token_19_30 = token_out_vec_19[1];

    // Process: grp_dataflow_wrapper_fu_6443.task_compute_attn_U0.grp_do_attn_1_fu_5150.do_matmul_2_1_U0
    vit_block_top_hls_deadlock_detect_unit #(74, 20, 2, 2) vit_block_top_hls_deadlock_detect_unit_20 (
        .reset(dl_reset),
        .clock(dl_clock),
        .proc_dep_vld_vec(proc_dep_vld_vec_20),
        .in_chan_dep_vld_vec(in_chan_dep_vld_vec_20),
        .in_chan_dep_data_vec(in_chan_dep_data_vec_20),
        .token_in_vec(token_in_vec_20),
        .dl_detect_in(dl_detect_out),
        .origin(origin[20]),
        .token_clear(token_clear),
        .out_chan_dep_vld_vec(out_chan_dep_vld_vec_20),
        .out_chan_dep_data(out_chan_dep_data_20),
        .token_out_vec(token_out_vec_20),
        .dl_detect_out(dl_in_vec[20]));

    assign proc_20_data_FIFO_blk[0] = 1'b0 | (~grp_dataflow_wrapper_fu_6443.task_compute_attn_U0.grp_do_attn_1_fu_5150.do_matmul_2_1_U0.do_adapt_9_U0.lnq_sm_cp2_blk_n);
    assign proc_20_data_PIPO_blk[0] = 1'b0;
    assign proc_20_start_FIFO_blk[0] = 1'b0 | (~grp_dataflow_wrapper_fu_6443.task_compute_attn_U0.grp_do_attn_1_fu_5150.start_for_do_matmul_2_1_U0_U.if_empty_n & grp_dataflow_wrapper_fu_6443.task_compute_attn_U0.grp_do_attn_1_fu_5150.do_matmul_2_1_U0.ap_idle & ~grp_dataflow_wrapper_fu_6443.task_compute_attn_U0.grp_do_attn_1_fu_5150.start_for_do_matmul_2_1_U0_U.if_write);
    assign proc_20_TLF_FIFO_blk[0] = 1'b0;
    assign proc_20_input_sync_blk[0] = 1'b0;
    assign proc_20_output_sync_blk[0] = 1'b0;
    assign proc_dep_vld_vec_20[0] = dl_detect_out ? proc_dep_vld_vec_20_reg[0] : (proc_20_data_FIFO_blk[0] | proc_20_data_PIPO_blk[0] | proc_20_start_FIFO_blk[0] | proc_20_TLF_FIFO_blk[0] | proc_20_input_sync_blk[0] | proc_20_output_sync_blk[0]);
    assign proc_20_data_FIFO_blk[1] = 1'b0 | (~grp_dataflow_wrapper_fu_6443.task_compute_attn_U0.grp_do_attn_1_fu_5150.do_matmul_2_1_U0.do_adapt_12_1_U0.k_sm_blk_n);
    assign proc_20_data_PIPO_blk[1] = 1'b0;
    assign proc_20_start_FIFO_blk[1] = 1'b0 | (~grp_dataflow_wrapper_fu_6443.task_compute_attn_U0.grp_do_attn_1_fu_5150.start_for_do_quant_3_U0_U.if_full_n & grp_dataflow_wrapper_fu_6443.task_compute_attn_U0.grp_do_attn_1_fu_5150.do_matmul_2_1_U0.ap_start & ~grp_dataflow_wrapper_fu_6443.task_compute_attn_U0.grp_do_attn_1_fu_5150.do_matmul_2_1_U0.real_start & (trans_in_cnt_17 == trans_out_cnt_17) & ~grp_dataflow_wrapper_fu_6443.task_compute_attn_U0.grp_do_attn_1_fu_5150.start_for_do_quant_3_U0_U.if_read);
    assign proc_20_TLF_FIFO_blk[1] = 1'b0;
    assign proc_20_input_sync_blk[1] = 1'b0;
    assign proc_20_output_sync_blk[1] = 1'b0;
    assign proc_dep_vld_vec_20[1] = dl_detect_out ? proc_dep_vld_vec_20_reg[1] : (proc_20_data_FIFO_blk[1] | proc_20_data_PIPO_blk[1] | proc_20_start_FIFO_blk[1] | proc_20_TLF_FIFO_blk[1] | proc_20_input_sync_blk[1] | proc_20_output_sync_blk[1]);
    always @ (negedge dl_reset or posedge dl_clock) begin
        if (~dl_reset) begin
            proc_dep_vld_vec_20_reg <= 'b0;
        end
        else begin
            proc_dep_vld_vec_20_reg <= proc_dep_vld_vec_20;
        end
    end
    assign in_chan_dep_vld_vec_20[0] = dep_chan_vld_14_20;
    assign in_chan_dep_data_vec_20[73 : 0] = dep_chan_data_14_20;
    assign token_in_vec_20[0] = token_14_20;
    assign in_chan_dep_vld_vec_20[1] = dep_chan_vld_31_20;
    assign in_chan_dep_data_vec_20[147 : 74] = dep_chan_data_31_20;
    assign token_in_vec_20[1] = token_31_20;
    assign dep_chan_vld_20_14 = out_chan_dep_vld_vec_20[0];
    assign dep_chan_data_20_14 = out_chan_dep_data_20;
    assign token_20_14 = token_out_vec_20[0];
    assign dep_chan_vld_20_31 = out_chan_dep_vld_vec_20[1];
    assign dep_chan_data_20_31 = out_chan_dep_data_20;
    assign token_20_31 = token_out_vec_20[1];

    // Process: grp_dataflow_wrapper_fu_6443.task_compute_attn_U0.grp_do_attn_1_fu_5150.do_matmul_2_1_U0.do_adapt_9_U0
    vit_block_top_hls_deadlock_detect_unit #(74, 21, 2, 2) vit_block_top_hls_deadlock_detect_unit_21 (
        .reset(dl_reset),
        .clock(dl_clock),
        .proc_dep_vld_vec(proc_dep_vld_vec_21),
        .in_chan_dep_vld_vec(in_chan_dep_vld_vec_21),
        .in_chan_dep_data_vec(in_chan_dep_data_vec_21),
        .token_in_vec(token_in_vec_21),
        .dl_detect_in(dl_detect_out),
        .origin(origin[21]),
        .token_clear(token_clear),
        .out_chan_dep_vld_vec(out_chan_dep_vld_vec_21),
        .out_chan_dep_data(out_chan_dep_data_21),
        .token_out_vec(token_out_vec_21),
        .dl_detect_out(dl_in_vec[21]));

    assign proc_21_data_FIFO_blk[0] = 1'b0 | (~grp_dataflow_wrapper_fu_6443.task_compute_attn_U0.grp_do_attn_1_fu_5150.do_matmul_2_1_U0.do_adapt_9_U0.lnq_sm_cp2_blk_n);
    assign proc_21_data_PIPO_blk[0] = 1'b0;
    assign proc_21_start_FIFO_blk[0] = 1'b0;
    assign proc_21_TLF_FIFO_blk[0] = 1'b0;
    assign proc_21_input_sync_blk[0] = 1'b0;
    assign proc_21_output_sync_blk[0] = 1'b0;
    assign proc_dep_vld_vec_21[0] = dl_detect_out ? proc_dep_vld_vec_21_reg[0] : (proc_21_data_FIFO_blk[0] | proc_21_data_PIPO_blk[0] | proc_21_start_FIFO_blk[0] | proc_21_TLF_FIFO_blk[0] | proc_21_input_sync_blk[0] | proc_21_output_sync_blk[0]);
    assign proc_21_data_FIFO_blk[1] = 1'b0 | (~grp_dataflow_wrapper_fu_6443.task_compute_attn_U0.grp_do_attn_1_fu_5150.do_matmul_2_1_U0.do_adapt_9_U0.adpt_sm_blk_n);
    assign proc_21_data_PIPO_blk[1] = 1'b0;
    assign proc_21_start_FIFO_blk[1] = 1'b0 | (~grp_dataflow_wrapper_fu_6443.task_compute_attn_U0.grp_do_attn_1_fu_5150.do_matmul_2_1_U0.start_for_matmul_step1_cache_window_10_U0_U.if_full_n & grp_dataflow_wrapper_fu_6443.task_compute_attn_U0.grp_do_attn_1_fu_5150.do_matmul_2_1_U0.do_adapt_9_U0.ap_start & ~grp_dataflow_wrapper_fu_6443.task_compute_attn_U0.grp_do_attn_1_fu_5150.do_matmul_2_1_U0.do_adapt_9_U0.real_start & (trans_in_cnt_10 == trans_out_cnt_10) & ~grp_dataflow_wrapper_fu_6443.task_compute_attn_U0.grp_do_attn_1_fu_5150.do_matmul_2_1_U0.start_for_matmul_step1_cache_window_10_U0_U.if_read);
    assign proc_21_TLF_FIFO_blk[1] = 1'b0;
    assign proc_21_input_sync_blk[1] = 1'b0;
    assign proc_21_output_sync_blk[1] = 1'b0;
    assign proc_dep_vld_vec_21[1] = dl_detect_out ? proc_dep_vld_vec_21_reg[1] : (proc_21_data_FIFO_blk[1] | proc_21_data_PIPO_blk[1] | proc_21_start_FIFO_blk[1] | proc_21_TLF_FIFO_blk[1] | proc_21_input_sync_blk[1] | proc_21_output_sync_blk[1]);
    always @ (negedge dl_reset or posedge dl_clock) begin
        if (~dl_reset) begin
            proc_dep_vld_vec_21_reg <= 'b0;
        end
        else begin
            proc_dep_vld_vec_21_reg <= proc_dep_vld_vec_21;
        end
    end
    assign in_chan_dep_vld_vec_21[0] = dep_chan_vld_14_21;
    assign in_chan_dep_data_vec_21[73 : 0] = dep_chan_data_14_21;
    assign token_in_vec_21[0] = token_14_21;
    assign in_chan_dep_vld_vec_21[1] = dep_chan_vld_22_21;
    assign in_chan_dep_data_vec_21[147 : 74] = dep_chan_data_22_21;
    assign token_in_vec_21[1] = token_22_21;
    assign dep_chan_vld_21_14 = out_chan_dep_vld_vec_21[0];
    assign dep_chan_data_21_14 = out_chan_dep_data_21;
    assign token_21_14 = token_out_vec_21[0];
    assign dep_chan_vld_21_22 = out_chan_dep_vld_vec_21[1];
    assign dep_chan_data_21_22 = out_chan_dep_data_21;
    assign token_21_22 = token_out_vec_21[1];

    // Process: grp_dataflow_wrapper_fu_6443.task_compute_attn_U0.grp_do_attn_1_fu_5150.do_matmul_2_1_U0.matmul_step1_cache_window_10_U0
    vit_block_top_hls_deadlock_detect_unit #(74, 22, 2, 2) vit_block_top_hls_deadlock_detect_unit_22 (
        .reset(dl_reset),
        .clock(dl_clock),
        .proc_dep_vld_vec(proc_dep_vld_vec_22),
        .in_chan_dep_vld_vec(in_chan_dep_vld_vec_22),
        .in_chan_dep_data_vec(in_chan_dep_data_vec_22),
        .token_in_vec(token_in_vec_22),
        .dl_detect_in(dl_detect_out),
        .origin(origin[22]),
        .token_clear(token_clear),
        .out_chan_dep_vld_vec(out_chan_dep_vld_vec_22),
        .out_chan_dep_data(out_chan_dep_data_22),
        .token_out_vec(token_out_vec_22),
        .dl_detect_out(dl_in_vec[22]));

    assign proc_22_data_FIFO_blk[0] = 1'b0 | (~grp_dataflow_wrapper_fu_6443.task_compute_attn_U0.grp_do_attn_1_fu_5150.do_matmul_2_1_U0.matmul_step1_cache_window_10_U0.adpt_sm_blk_n);
    assign proc_22_data_PIPO_blk[0] = 1'b0;
    assign proc_22_start_FIFO_blk[0] = 1'b0 | (~grp_dataflow_wrapper_fu_6443.task_compute_attn_U0.grp_do_attn_1_fu_5150.do_matmul_2_1_U0.start_for_matmul_step1_cache_window_10_U0_U.if_empty_n & grp_dataflow_wrapper_fu_6443.task_compute_attn_U0.grp_do_attn_1_fu_5150.do_matmul_2_1_U0.matmul_step1_cache_window_10_U0.ap_idle & ~grp_dataflow_wrapper_fu_6443.task_compute_attn_U0.grp_do_attn_1_fu_5150.do_matmul_2_1_U0.start_for_matmul_step1_cache_window_10_U0_U.if_write);
    assign proc_22_TLF_FIFO_blk[0] = 1'b0;
    assign proc_22_input_sync_blk[0] = 1'b0;
    assign proc_22_output_sync_blk[0] = 1'b0;
    assign proc_dep_vld_vec_22[0] = dl_detect_out ? proc_dep_vld_vec_22_reg[0] : (proc_22_data_FIFO_blk[0] | proc_22_data_PIPO_blk[0] | proc_22_start_FIFO_blk[0] | proc_22_TLF_FIFO_blk[0] | proc_22_input_sync_blk[0] | proc_22_output_sync_blk[0]);
    assign proc_22_data_FIFO_blk[1] = 1'b0 | (~grp_dataflow_wrapper_fu_6443.task_compute_attn_U0.grp_do_attn_1_fu_5150.do_matmul_2_1_U0.matmul_step1_cache_window_10_U0.cache_window_sm_blk_n);
    assign proc_22_data_PIPO_blk[1] = 1'b0;
    assign proc_22_start_FIFO_blk[1] = 1'b0 | (~grp_dataflow_wrapper_fu_6443.task_compute_attn_U0.grp_do_attn_1_fu_5150.do_matmul_2_1_U0.start_for_matmul_step2_mac_11_U0_U.if_full_n & grp_dataflow_wrapper_fu_6443.task_compute_attn_U0.grp_do_attn_1_fu_5150.do_matmul_2_1_U0.matmul_step1_cache_window_10_U0.ap_start & ~grp_dataflow_wrapper_fu_6443.task_compute_attn_U0.grp_do_attn_1_fu_5150.do_matmul_2_1_U0.matmul_step1_cache_window_10_U0.real_start & (trans_in_cnt_11 == trans_out_cnt_11) & ~grp_dataflow_wrapper_fu_6443.task_compute_attn_U0.grp_do_attn_1_fu_5150.do_matmul_2_1_U0.start_for_matmul_step2_mac_11_U0_U.if_read);
    assign proc_22_TLF_FIFO_blk[1] = 1'b0;
    assign proc_22_input_sync_blk[1] = 1'b0;
    assign proc_22_output_sync_blk[1] = 1'b0;
    assign proc_dep_vld_vec_22[1] = dl_detect_out ? proc_dep_vld_vec_22_reg[1] : (proc_22_data_FIFO_blk[1] | proc_22_data_PIPO_blk[1] | proc_22_start_FIFO_blk[1] | proc_22_TLF_FIFO_blk[1] | proc_22_input_sync_blk[1] | proc_22_output_sync_blk[1]);
    always @ (negedge dl_reset or posedge dl_clock) begin
        if (~dl_reset) begin
            proc_dep_vld_vec_22_reg <= 'b0;
        end
        else begin
            proc_dep_vld_vec_22_reg <= proc_dep_vld_vec_22;
        end
    end
    assign in_chan_dep_vld_vec_22[0] = dep_chan_vld_21_22;
    assign in_chan_dep_data_vec_22[73 : 0] = dep_chan_data_21_22;
    assign token_in_vec_22[0] = token_21_22;
    assign in_chan_dep_vld_vec_22[1] = dep_chan_vld_23_22;
    assign in_chan_dep_data_vec_22[147 : 74] = dep_chan_data_23_22;
    assign token_in_vec_22[1] = token_23_22;
    assign dep_chan_vld_22_21 = out_chan_dep_vld_vec_22[0];
    assign dep_chan_data_22_21 = out_chan_dep_data_22;
    assign token_22_21 = token_out_vec_22[0];
    assign dep_chan_vld_22_23 = out_chan_dep_vld_vec_22[1];
    assign dep_chan_data_22_23 = out_chan_dep_data_22;
    assign token_22_23 = token_out_vec_22[1];

    // Process: grp_dataflow_wrapper_fu_6443.task_compute_attn_U0.grp_do_attn_1_fu_5150.do_matmul_2_1_U0.matmul_step2_mac_11_U0
    vit_block_top_hls_deadlock_detect_unit #(74, 23, 2, 2) vit_block_top_hls_deadlock_detect_unit_23 (
        .reset(dl_reset),
        .clock(dl_clock),
        .proc_dep_vld_vec(proc_dep_vld_vec_23),
        .in_chan_dep_vld_vec(in_chan_dep_vld_vec_23),
        .in_chan_dep_data_vec(in_chan_dep_data_vec_23),
        .token_in_vec(token_in_vec_23),
        .dl_detect_in(dl_detect_out),
        .origin(origin[23]),
        .token_clear(token_clear),
        .out_chan_dep_vld_vec(out_chan_dep_vld_vec_23),
        .out_chan_dep_data(out_chan_dep_data_23),
        .token_out_vec(token_out_vec_23),
        .dl_detect_out(dl_in_vec[23]));

    assign proc_23_data_FIFO_blk[0] = 1'b0 | (~grp_dataflow_wrapper_fu_6443.task_compute_attn_U0.grp_do_attn_1_fu_5150.do_matmul_2_1_U0.matmul_step2_mac_11_U0.cache_window_sm_blk_n);
    assign proc_23_data_PIPO_blk[0] = 1'b0;
    assign proc_23_start_FIFO_blk[0] = 1'b0 | (~grp_dataflow_wrapper_fu_6443.task_compute_attn_U0.grp_do_attn_1_fu_5150.do_matmul_2_1_U0.start_for_matmul_step2_mac_11_U0_U.if_empty_n & grp_dataflow_wrapper_fu_6443.task_compute_attn_U0.grp_do_attn_1_fu_5150.do_matmul_2_1_U0.matmul_step2_mac_11_U0.ap_idle & ~grp_dataflow_wrapper_fu_6443.task_compute_attn_U0.grp_do_attn_1_fu_5150.do_matmul_2_1_U0.start_for_matmul_step2_mac_11_U0_U.if_write);
    assign proc_23_TLF_FIFO_blk[0] = 1'b0;
    assign proc_23_input_sync_blk[0] = 1'b0;
    assign proc_23_output_sync_blk[0] = 1'b0;
    assign proc_dep_vld_vec_23[0] = dl_detect_out ? proc_dep_vld_vec_23_reg[0] : (proc_23_data_FIFO_blk[0] | proc_23_data_PIPO_blk[0] | proc_23_start_FIFO_blk[0] | proc_23_TLF_FIFO_blk[0] | proc_23_input_sync_blk[0] | proc_23_output_sync_blk[0]);
    assign proc_23_data_FIFO_blk[1] = 1'b0 | (~grp_dataflow_wrapper_fu_6443.task_compute_attn_U0.grp_do_attn_1_fu_5150.do_matmul_2_1_U0.matmul_step2_mac_11_U0.mac_sm_blk_n);
    assign proc_23_data_PIPO_blk[1] = 1'b0;
    assign proc_23_start_FIFO_blk[1] = 1'b0 | (~grp_dataflow_wrapper_fu_6443.task_compute_attn_U0.grp_do_attn_1_fu_5150.do_matmul_2_1_U0.start_for_do_adapt_12_1_U0_U.if_full_n & grp_dataflow_wrapper_fu_6443.task_compute_attn_U0.grp_do_attn_1_fu_5150.do_matmul_2_1_U0.matmul_step2_mac_11_U0.ap_start & ~grp_dataflow_wrapper_fu_6443.task_compute_attn_U0.grp_do_attn_1_fu_5150.do_matmul_2_1_U0.matmul_step2_mac_11_U0.real_start & (trans_in_cnt_12 == trans_out_cnt_12) & ~grp_dataflow_wrapper_fu_6443.task_compute_attn_U0.grp_do_attn_1_fu_5150.do_matmul_2_1_U0.start_for_do_adapt_12_1_U0_U.if_read);
    assign proc_23_TLF_FIFO_blk[1] = 1'b0;
    assign proc_23_input_sync_blk[1] = 1'b0;
    assign proc_23_output_sync_blk[1] = 1'b0;
    assign proc_dep_vld_vec_23[1] = dl_detect_out ? proc_dep_vld_vec_23_reg[1] : (proc_23_data_FIFO_blk[1] | proc_23_data_PIPO_blk[1] | proc_23_start_FIFO_blk[1] | proc_23_TLF_FIFO_blk[1] | proc_23_input_sync_blk[1] | proc_23_output_sync_blk[1]);
    always @ (negedge dl_reset or posedge dl_clock) begin
        if (~dl_reset) begin
            proc_dep_vld_vec_23_reg <= 'b0;
        end
        else begin
            proc_dep_vld_vec_23_reg <= proc_dep_vld_vec_23;
        end
    end
    assign in_chan_dep_vld_vec_23[0] = dep_chan_vld_22_23;
    assign in_chan_dep_data_vec_23[73 : 0] = dep_chan_data_22_23;
    assign token_in_vec_23[0] = token_22_23;
    assign in_chan_dep_vld_vec_23[1] = dep_chan_vld_24_23;
    assign in_chan_dep_data_vec_23[147 : 74] = dep_chan_data_24_23;
    assign token_in_vec_23[1] = token_24_23;
    assign dep_chan_vld_23_22 = out_chan_dep_vld_vec_23[0];
    assign dep_chan_data_23_22 = out_chan_dep_data_23;
    assign token_23_22 = token_out_vec_23[0];
    assign dep_chan_vld_23_24 = out_chan_dep_vld_vec_23[1];
    assign dep_chan_data_23_24 = out_chan_dep_data_23;
    assign token_23_24 = token_out_vec_23[1];

    // Process: grp_dataflow_wrapper_fu_6443.task_compute_attn_U0.grp_do_attn_1_fu_5150.do_matmul_2_1_U0.do_adapt_12_1_U0
    vit_block_top_hls_deadlock_detect_unit #(74, 24, 2, 2) vit_block_top_hls_deadlock_detect_unit_24 (
        .reset(dl_reset),
        .clock(dl_clock),
        .proc_dep_vld_vec(proc_dep_vld_vec_24),
        .in_chan_dep_vld_vec(in_chan_dep_vld_vec_24),
        .in_chan_dep_data_vec(in_chan_dep_data_vec_24),
        .token_in_vec(token_in_vec_24),
        .dl_detect_in(dl_detect_out),
        .origin(origin[24]),
        .token_clear(token_clear),
        .out_chan_dep_vld_vec(out_chan_dep_vld_vec_24),
        .out_chan_dep_data(out_chan_dep_data_24),
        .token_out_vec(token_out_vec_24),
        .dl_detect_out(dl_in_vec[24]));

    assign proc_24_data_FIFO_blk[0] = 1'b0 | (~grp_dataflow_wrapper_fu_6443.task_compute_attn_U0.grp_do_attn_1_fu_5150.do_matmul_2_1_U0.do_adapt_12_1_U0.mac_sm_blk_n);
    assign proc_24_data_PIPO_blk[0] = 1'b0;
    assign proc_24_start_FIFO_blk[0] = 1'b0 | (~grp_dataflow_wrapper_fu_6443.task_compute_attn_U0.grp_do_attn_1_fu_5150.do_matmul_2_1_U0.start_for_do_adapt_12_1_U0_U.if_empty_n & grp_dataflow_wrapper_fu_6443.task_compute_attn_U0.grp_do_attn_1_fu_5150.do_matmul_2_1_U0.do_adapt_12_1_U0.ap_idle & ~grp_dataflow_wrapper_fu_6443.task_compute_attn_U0.grp_do_attn_1_fu_5150.do_matmul_2_1_U0.start_for_do_adapt_12_1_U0_U.if_write);
    assign proc_24_TLF_FIFO_blk[0] = 1'b0;
    assign proc_24_input_sync_blk[0] = 1'b0;
    assign proc_24_output_sync_blk[0] = 1'b0;
    assign proc_dep_vld_vec_24[0] = dl_detect_out ? proc_dep_vld_vec_24_reg[0] : (proc_24_data_FIFO_blk[0] | proc_24_data_PIPO_blk[0] | proc_24_start_FIFO_blk[0] | proc_24_TLF_FIFO_blk[0] | proc_24_input_sync_blk[0] | proc_24_output_sync_blk[0]);
    assign proc_24_data_FIFO_blk[1] = 1'b0 | (~grp_dataflow_wrapper_fu_6443.task_compute_attn_U0.grp_do_attn_1_fu_5150.do_matmul_2_1_U0.do_adapt_12_1_U0.k_sm_blk_n);
    assign proc_24_data_PIPO_blk[1] = 1'b0;
    assign proc_24_start_FIFO_blk[1] = 1'b0;
    assign proc_24_TLF_FIFO_blk[1] = 1'b0;
    assign proc_24_input_sync_blk[1] = 1'b0;
    assign proc_24_output_sync_blk[1] = 1'b0;
    assign proc_dep_vld_vec_24[1] = dl_detect_out ? proc_dep_vld_vec_24_reg[1] : (proc_24_data_FIFO_blk[1] | proc_24_data_PIPO_blk[1] | proc_24_start_FIFO_blk[1] | proc_24_TLF_FIFO_blk[1] | proc_24_input_sync_blk[1] | proc_24_output_sync_blk[1]);
    always @ (negedge dl_reset or posedge dl_clock) begin
        if (~dl_reset) begin
            proc_dep_vld_vec_24_reg <= 'b0;
        end
        else begin
            proc_dep_vld_vec_24_reg <= proc_dep_vld_vec_24;
        end
    end
    assign in_chan_dep_vld_vec_24[0] = dep_chan_vld_23_24;
    assign in_chan_dep_data_vec_24[73 : 0] = dep_chan_data_23_24;
    assign token_in_vec_24[0] = token_23_24;
    assign in_chan_dep_vld_vec_24[1] = dep_chan_vld_31_24;
    assign in_chan_dep_data_vec_24[147 : 74] = dep_chan_data_31_24;
    assign token_in_vec_24[1] = token_31_24;
    assign dep_chan_vld_24_23 = out_chan_dep_vld_vec_24[0];
    assign dep_chan_data_24_23 = out_chan_dep_data_24;
    assign token_24_23 = token_out_vec_24[0];
    assign dep_chan_vld_24_31 = out_chan_dep_vld_vec_24[1];
    assign dep_chan_data_24_31 = out_chan_dep_data_24;
    assign token_24_31 = token_out_vec_24[1];

    // Process: grp_dataflow_wrapper_fu_6443.task_compute_attn_U0.grp_do_attn_1_fu_5150.do_matmul_4_U0
    vit_block_top_hls_deadlock_detect_unit #(74, 25, 2, 2) vit_block_top_hls_deadlock_detect_unit_25 (
        .reset(dl_reset),
        .clock(dl_clock),
        .proc_dep_vld_vec(proc_dep_vld_vec_25),
        .in_chan_dep_vld_vec(in_chan_dep_vld_vec_25),
        .in_chan_dep_data_vec(in_chan_dep_data_vec_25),
        .token_in_vec(token_in_vec_25),
        .dl_detect_in(dl_detect_out),
        .origin(origin[25]),
        .token_clear(token_clear),
        .out_chan_dep_vld_vec(out_chan_dep_vld_vec_25),
        .out_chan_dep_data(out_chan_dep_data_25),
        .token_out_vec(token_out_vec_25),
        .dl_detect_out(dl_in_vec[25]));

    assign proc_25_data_FIFO_blk[0] = 1'b0 | (~grp_dataflow_wrapper_fu_6443.task_compute_attn_U0.grp_do_attn_1_fu_5150.do_matmul_4_U0.do_adapt_13_U0.lnq_sm_cp3_blk_n);
    assign proc_25_data_PIPO_blk[0] = 1'b0;
    assign proc_25_start_FIFO_blk[0] = 1'b0 | (~grp_dataflow_wrapper_fu_6443.task_compute_attn_U0.grp_do_attn_1_fu_5150.start_for_do_matmul_4_U0_U.if_empty_n & grp_dataflow_wrapper_fu_6443.task_compute_attn_U0.grp_do_attn_1_fu_5150.do_matmul_4_U0.ap_idle & ~grp_dataflow_wrapper_fu_6443.task_compute_attn_U0.grp_do_attn_1_fu_5150.start_for_do_matmul_4_U0_U.if_write);
    assign proc_25_TLF_FIFO_blk[0] = 1'b0;
    assign proc_25_input_sync_blk[0] = 1'b0;
    assign proc_25_output_sync_blk[0] = 1'b0;
    assign proc_dep_vld_vec_25[0] = dl_detect_out ? proc_dep_vld_vec_25_reg[0] : (proc_25_data_FIFO_blk[0] | proc_25_data_PIPO_blk[0] | proc_25_start_FIFO_blk[0] | proc_25_TLF_FIFO_blk[0] | proc_25_input_sync_blk[0] | proc_25_output_sync_blk[0]);
    assign proc_25_data_FIFO_blk[1] = 1'b0 | (~grp_dataflow_wrapper_fu_6443.task_compute_attn_U0.grp_do_attn_1_fu_5150.do_matmul_4_U0.do_adapt_13_1_U0.v_sm_blk_n);
    assign proc_25_data_PIPO_blk[1] = 1'b0;
    assign proc_25_start_FIFO_blk[1] = 1'b0 | (~grp_dataflow_wrapper_fu_6443.task_compute_attn_U0.grp_do_attn_1_fu_5150.start_for_do_quant_1_U0_U.if_full_n & grp_dataflow_wrapper_fu_6443.task_compute_attn_U0.grp_do_attn_1_fu_5150.do_matmul_4_U0.ap_start & ~grp_dataflow_wrapper_fu_6443.task_compute_attn_U0.grp_do_attn_1_fu_5150.do_matmul_4_U0.real_start & (trans_in_cnt_18 == trans_out_cnt_18) & ~grp_dataflow_wrapper_fu_6443.task_compute_attn_U0.grp_do_attn_1_fu_5150.start_for_do_quant_1_U0_U.if_read);
    assign proc_25_TLF_FIFO_blk[1] = 1'b0;
    assign proc_25_input_sync_blk[1] = 1'b0;
    assign proc_25_output_sync_blk[1] = 1'b0;
    assign proc_dep_vld_vec_25[1] = dl_detect_out ? proc_dep_vld_vec_25_reg[1] : (proc_25_data_FIFO_blk[1] | proc_25_data_PIPO_blk[1] | proc_25_start_FIFO_blk[1] | proc_25_TLF_FIFO_blk[1] | proc_25_input_sync_blk[1] | proc_25_output_sync_blk[1]);
    always @ (negedge dl_reset or posedge dl_clock) begin
        if (~dl_reset) begin
            proc_dep_vld_vec_25_reg <= 'b0;
        end
        else begin
            proc_dep_vld_vec_25_reg <= proc_dep_vld_vec_25;
        end
    end
    assign in_chan_dep_vld_vec_25[0] = dep_chan_vld_14_25;
    assign in_chan_dep_data_vec_25[73 : 0] = dep_chan_data_14_25;
    assign token_in_vec_25[0] = token_14_25;
    assign in_chan_dep_vld_vec_25[1] = dep_chan_vld_32_25;
    assign in_chan_dep_data_vec_25[147 : 74] = dep_chan_data_32_25;
    assign token_in_vec_25[1] = token_32_25;
    assign dep_chan_vld_25_14 = out_chan_dep_vld_vec_25[0];
    assign dep_chan_data_25_14 = out_chan_dep_data_25;
    assign token_25_14 = token_out_vec_25[0];
    assign dep_chan_vld_25_32 = out_chan_dep_vld_vec_25[1];
    assign dep_chan_data_25_32 = out_chan_dep_data_25;
    assign token_25_32 = token_out_vec_25[1];

    // Process: grp_dataflow_wrapper_fu_6443.task_compute_attn_U0.grp_do_attn_1_fu_5150.do_matmul_4_U0.do_adapt_13_U0
    vit_block_top_hls_deadlock_detect_unit #(74, 26, 2, 2) vit_block_top_hls_deadlock_detect_unit_26 (
        .reset(dl_reset),
        .clock(dl_clock),
        .proc_dep_vld_vec(proc_dep_vld_vec_26),
        .in_chan_dep_vld_vec(in_chan_dep_vld_vec_26),
        .in_chan_dep_data_vec(in_chan_dep_data_vec_26),
        .token_in_vec(token_in_vec_26),
        .dl_detect_in(dl_detect_out),
        .origin(origin[26]),
        .token_clear(token_clear),
        .out_chan_dep_vld_vec(out_chan_dep_vld_vec_26),
        .out_chan_dep_data(out_chan_dep_data_26),
        .token_out_vec(token_out_vec_26),
        .dl_detect_out(dl_in_vec[26]));

    assign proc_26_data_FIFO_blk[0] = 1'b0 | (~grp_dataflow_wrapper_fu_6443.task_compute_attn_U0.grp_do_attn_1_fu_5150.do_matmul_4_U0.do_adapt_13_U0.lnq_sm_cp3_blk_n);
    assign proc_26_data_PIPO_blk[0] = 1'b0;
    assign proc_26_start_FIFO_blk[0] = 1'b0;
    assign proc_26_TLF_FIFO_blk[0] = 1'b0;
    assign proc_26_input_sync_blk[0] = 1'b0;
    assign proc_26_output_sync_blk[0] = 1'b0;
    assign proc_dep_vld_vec_26[0] = dl_detect_out ? proc_dep_vld_vec_26_reg[0] : (proc_26_data_FIFO_blk[0] | proc_26_data_PIPO_blk[0] | proc_26_start_FIFO_blk[0] | proc_26_TLF_FIFO_blk[0] | proc_26_input_sync_blk[0] | proc_26_output_sync_blk[0]);
    assign proc_26_data_FIFO_blk[1] = 1'b0 | (~grp_dataflow_wrapper_fu_6443.task_compute_attn_U0.grp_do_attn_1_fu_5150.do_matmul_4_U0.do_adapt_13_U0.adpt_sm_blk_n);
    assign proc_26_data_PIPO_blk[1] = 1'b0;
    assign proc_26_start_FIFO_blk[1] = 1'b0 | (~grp_dataflow_wrapper_fu_6443.task_compute_attn_U0.grp_do_attn_1_fu_5150.do_matmul_4_U0.start_for_matmul_step1_cache_window_4_U0_U.if_full_n & grp_dataflow_wrapper_fu_6443.task_compute_attn_U0.grp_do_attn_1_fu_5150.do_matmul_4_U0.do_adapt_13_U0.ap_start & ~grp_dataflow_wrapper_fu_6443.task_compute_attn_U0.grp_do_attn_1_fu_5150.do_matmul_4_U0.do_adapt_13_U0.real_start & (trans_in_cnt_13 == trans_out_cnt_13) & ~grp_dataflow_wrapper_fu_6443.task_compute_attn_U0.grp_do_attn_1_fu_5150.do_matmul_4_U0.start_for_matmul_step1_cache_window_4_U0_U.if_read);
    assign proc_26_TLF_FIFO_blk[1] = 1'b0;
    assign proc_26_input_sync_blk[1] = 1'b0;
    assign proc_26_output_sync_blk[1] = 1'b0;
    assign proc_dep_vld_vec_26[1] = dl_detect_out ? proc_dep_vld_vec_26_reg[1] : (proc_26_data_FIFO_blk[1] | proc_26_data_PIPO_blk[1] | proc_26_start_FIFO_blk[1] | proc_26_TLF_FIFO_blk[1] | proc_26_input_sync_blk[1] | proc_26_output_sync_blk[1]);
    always @ (negedge dl_reset or posedge dl_clock) begin
        if (~dl_reset) begin
            proc_dep_vld_vec_26_reg <= 'b0;
        end
        else begin
            proc_dep_vld_vec_26_reg <= proc_dep_vld_vec_26;
        end
    end
    assign in_chan_dep_vld_vec_26[0] = dep_chan_vld_14_26;
    assign in_chan_dep_data_vec_26[73 : 0] = dep_chan_data_14_26;
    assign token_in_vec_26[0] = token_14_26;
    assign in_chan_dep_vld_vec_26[1] = dep_chan_vld_27_26;
    assign in_chan_dep_data_vec_26[147 : 74] = dep_chan_data_27_26;
    assign token_in_vec_26[1] = token_27_26;
    assign dep_chan_vld_26_14 = out_chan_dep_vld_vec_26[0];
    assign dep_chan_data_26_14 = out_chan_dep_data_26;
    assign token_26_14 = token_out_vec_26[0];
    assign dep_chan_vld_26_27 = out_chan_dep_vld_vec_26[1];
    assign dep_chan_data_26_27 = out_chan_dep_data_26;
    assign token_26_27 = token_out_vec_26[1];

    // Process: grp_dataflow_wrapper_fu_6443.task_compute_attn_U0.grp_do_attn_1_fu_5150.do_matmul_4_U0.matmul_step1_cache_window_4_U0
    vit_block_top_hls_deadlock_detect_unit #(74, 27, 2, 2) vit_block_top_hls_deadlock_detect_unit_27 (
        .reset(dl_reset),
        .clock(dl_clock),
        .proc_dep_vld_vec(proc_dep_vld_vec_27),
        .in_chan_dep_vld_vec(in_chan_dep_vld_vec_27),
        .in_chan_dep_data_vec(in_chan_dep_data_vec_27),
        .token_in_vec(token_in_vec_27),
        .dl_detect_in(dl_detect_out),
        .origin(origin[27]),
        .token_clear(token_clear),
        .out_chan_dep_vld_vec(out_chan_dep_vld_vec_27),
        .out_chan_dep_data(out_chan_dep_data_27),
        .token_out_vec(token_out_vec_27),
        .dl_detect_out(dl_in_vec[27]));

    assign proc_27_data_FIFO_blk[0] = 1'b0 | (~grp_dataflow_wrapper_fu_6443.task_compute_attn_U0.grp_do_attn_1_fu_5150.do_matmul_4_U0.matmul_step1_cache_window_4_U0.adpt_sm_blk_n);
    assign proc_27_data_PIPO_blk[0] = 1'b0;
    assign proc_27_start_FIFO_blk[0] = 1'b0 | (~grp_dataflow_wrapper_fu_6443.task_compute_attn_U0.grp_do_attn_1_fu_5150.do_matmul_4_U0.start_for_matmul_step1_cache_window_4_U0_U.if_empty_n & grp_dataflow_wrapper_fu_6443.task_compute_attn_U0.grp_do_attn_1_fu_5150.do_matmul_4_U0.matmul_step1_cache_window_4_U0.ap_idle & ~grp_dataflow_wrapper_fu_6443.task_compute_attn_U0.grp_do_attn_1_fu_5150.do_matmul_4_U0.start_for_matmul_step1_cache_window_4_U0_U.if_write);
    assign proc_27_TLF_FIFO_blk[0] = 1'b0;
    assign proc_27_input_sync_blk[0] = 1'b0;
    assign proc_27_output_sync_blk[0] = 1'b0;
    assign proc_dep_vld_vec_27[0] = dl_detect_out ? proc_dep_vld_vec_27_reg[0] : (proc_27_data_FIFO_blk[0] | proc_27_data_PIPO_blk[0] | proc_27_start_FIFO_blk[0] | proc_27_TLF_FIFO_blk[0] | proc_27_input_sync_blk[0] | proc_27_output_sync_blk[0]);
    assign proc_27_data_FIFO_blk[1] = 1'b0 | (~grp_dataflow_wrapper_fu_6443.task_compute_attn_U0.grp_do_attn_1_fu_5150.do_matmul_4_U0.matmul_step1_cache_window_4_U0.cache_window_sm_blk_n);
    assign proc_27_data_PIPO_blk[1] = 1'b0;
    assign proc_27_start_FIFO_blk[1] = 1'b0 | (~grp_dataflow_wrapper_fu_6443.task_compute_attn_U0.grp_do_attn_1_fu_5150.do_matmul_4_U0.start_for_matmul_step2_mac_4_U0_U.if_full_n & grp_dataflow_wrapper_fu_6443.task_compute_attn_U0.grp_do_attn_1_fu_5150.do_matmul_4_U0.matmul_step1_cache_window_4_U0.ap_start & ~grp_dataflow_wrapper_fu_6443.task_compute_attn_U0.grp_do_attn_1_fu_5150.do_matmul_4_U0.matmul_step1_cache_window_4_U0.real_start & (trans_in_cnt_14 == trans_out_cnt_14) & ~grp_dataflow_wrapper_fu_6443.task_compute_attn_U0.grp_do_attn_1_fu_5150.do_matmul_4_U0.start_for_matmul_step2_mac_4_U0_U.if_read);
    assign proc_27_TLF_FIFO_blk[1] = 1'b0;
    assign proc_27_input_sync_blk[1] = 1'b0;
    assign proc_27_output_sync_blk[1] = 1'b0;
    assign proc_dep_vld_vec_27[1] = dl_detect_out ? proc_dep_vld_vec_27_reg[1] : (proc_27_data_FIFO_blk[1] | proc_27_data_PIPO_blk[1] | proc_27_start_FIFO_blk[1] | proc_27_TLF_FIFO_blk[1] | proc_27_input_sync_blk[1] | proc_27_output_sync_blk[1]);
    always @ (negedge dl_reset or posedge dl_clock) begin
        if (~dl_reset) begin
            proc_dep_vld_vec_27_reg <= 'b0;
        end
        else begin
            proc_dep_vld_vec_27_reg <= proc_dep_vld_vec_27;
        end
    end
    assign in_chan_dep_vld_vec_27[0] = dep_chan_vld_26_27;
    assign in_chan_dep_data_vec_27[73 : 0] = dep_chan_data_26_27;
    assign token_in_vec_27[0] = token_26_27;
    assign in_chan_dep_vld_vec_27[1] = dep_chan_vld_28_27;
    assign in_chan_dep_data_vec_27[147 : 74] = dep_chan_data_28_27;
    assign token_in_vec_27[1] = token_28_27;
    assign dep_chan_vld_27_26 = out_chan_dep_vld_vec_27[0];
    assign dep_chan_data_27_26 = out_chan_dep_data_27;
    assign token_27_26 = token_out_vec_27[0];
    assign dep_chan_vld_27_28 = out_chan_dep_vld_vec_27[1];
    assign dep_chan_data_27_28 = out_chan_dep_data_27;
    assign token_27_28 = token_out_vec_27[1];

    // Process: grp_dataflow_wrapper_fu_6443.task_compute_attn_U0.grp_do_attn_1_fu_5150.do_matmul_4_U0.matmul_step2_mac_4_U0
    vit_block_top_hls_deadlock_detect_unit #(74, 28, 2, 2) vit_block_top_hls_deadlock_detect_unit_28 (
        .reset(dl_reset),
        .clock(dl_clock),
        .proc_dep_vld_vec(proc_dep_vld_vec_28),
        .in_chan_dep_vld_vec(in_chan_dep_vld_vec_28),
        .in_chan_dep_data_vec(in_chan_dep_data_vec_28),
        .token_in_vec(token_in_vec_28),
        .dl_detect_in(dl_detect_out),
        .origin(origin[28]),
        .token_clear(token_clear),
        .out_chan_dep_vld_vec(out_chan_dep_vld_vec_28),
        .out_chan_dep_data(out_chan_dep_data_28),
        .token_out_vec(token_out_vec_28),
        .dl_detect_out(dl_in_vec[28]));

    assign proc_28_data_FIFO_blk[0] = 1'b0 | (~grp_dataflow_wrapper_fu_6443.task_compute_attn_U0.grp_do_attn_1_fu_5150.do_matmul_4_U0.matmul_step2_mac_4_U0.cache_window_sm_blk_n);
    assign proc_28_data_PIPO_blk[0] = 1'b0;
    assign proc_28_start_FIFO_blk[0] = 1'b0 | (~grp_dataflow_wrapper_fu_6443.task_compute_attn_U0.grp_do_attn_1_fu_5150.do_matmul_4_U0.start_for_matmul_step2_mac_4_U0_U.if_empty_n & grp_dataflow_wrapper_fu_6443.task_compute_attn_U0.grp_do_attn_1_fu_5150.do_matmul_4_U0.matmul_step2_mac_4_U0.ap_idle & ~grp_dataflow_wrapper_fu_6443.task_compute_attn_U0.grp_do_attn_1_fu_5150.do_matmul_4_U0.start_for_matmul_step2_mac_4_U0_U.if_write);
    assign proc_28_TLF_FIFO_blk[0] = 1'b0;
    assign proc_28_input_sync_blk[0] = 1'b0;
    assign proc_28_output_sync_blk[0] = 1'b0;
    assign proc_dep_vld_vec_28[0] = dl_detect_out ? proc_dep_vld_vec_28_reg[0] : (proc_28_data_FIFO_blk[0] | proc_28_data_PIPO_blk[0] | proc_28_start_FIFO_blk[0] | proc_28_TLF_FIFO_blk[0] | proc_28_input_sync_blk[0] | proc_28_output_sync_blk[0]);
    assign proc_28_data_FIFO_blk[1] = 1'b0 | (~grp_dataflow_wrapper_fu_6443.task_compute_attn_U0.grp_do_attn_1_fu_5150.do_matmul_4_U0.matmul_step2_mac_4_U0.mac_sm_blk_n);
    assign proc_28_data_PIPO_blk[1] = 1'b0;
    assign proc_28_start_FIFO_blk[1] = 1'b0 | (~grp_dataflow_wrapper_fu_6443.task_compute_attn_U0.grp_do_attn_1_fu_5150.do_matmul_4_U0.start_for_do_adapt_13_1_U0_U.if_full_n & grp_dataflow_wrapper_fu_6443.task_compute_attn_U0.grp_do_attn_1_fu_5150.do_matmul_4_U0.matmul_step2_mac_4_U0.ap_start & ~grp_dataflow_wrapper_fu_6443.task_compute_attn_U0.grp_do_attn_1_fu_5150.do_matmul_4_U0.matmul_step2_mac_4_U0.real_start & (trans_in_cnt_15 == trans_out_cnt_15) & ~grp_dataflow_wrapper_fu_6443.task_compute_attn_U0.grp_do_attn_1_fu_5150.do_matmul_4_U0.start_for_do_adapt_13_1_U0_U.if_read);
    assign proc_28_TLF_FIFO_blk[1] = 1'b0;
    assign proc_28_input_sync_blk[1] = 1'b0;
    assign proc_28_output_sync_blk[1] = 1'b0;
    assign proc_dep_vld_vec_28[1] = dl_detect_out ? proc_dep_vld_vec_28_reg[1] : (proc_28_data_FIFO_blk[1] | proc_28_data_PIPO_blk[1] | proc_28_start_FIFO_blk[1] | proc_28_TLF_FIFO_blk[1] | proc_28_input_sync_blk[1] | proc_28_output_sync_blk[1]);
    always @ (negedge dl_reset or posedge dl_clock) begin
        if (~dl_reset) begin
            proc_dep_vld_vec_28_reg <= 'b0;
        end
        else begin
            proc_dep_vld_vec_28_reg <= proc_dep_vld_vec_28;
        end
    end
    assign in_chan_dep_vld_vec_28[0] = dep_chan_vld_27_28;
    assign in_chan_dep_data_vec_28[73 : 0] = dep_chan_data_27_28;
    assign token_in_vec_28[0] = token_27_28;
    assign in_chan_dep_vld_vec_28[1] = dep_chan_vld_29_28;
    assign in_chan_dep_data_vec_28[147 : 74] = dep_chan_data_29_28;
    assign token_in_vec_28[1] = token_29_28;
    assign dep_chan_vld_28_27 = out_chan_dep_vld_vec_28[0];
    assign dep_chan_data_28_27 = out_chan_dep_data_28;
    assign token_28_27 = token_out_vec_28[0];
    assign dep_chan_vld_28_29 = out_chan_dep_vld_vec_28[1];
    assign dep_chan_data_28_29 = out_chan_dep_data_28;
    assign token_28_29 = token_out_vec_28[1];

    // Process: grp_dataflow_wrapper_fu_6443.task_compute_attn_U0.grp_do_attn_1_fu_5150.do_matmul_4_U0.do_adapt_13_1_U0
    vit_block_top_hls_deadlock_detect_unit #(74, 29, 2, 2) vit_block_top_hls_deadlock_detect_unit_29 (
        .reset(dl_reset),
        .clock(dl_clock),
        .proc_dep_vld_vec(proc_dep_vld_vec_29),
        .in_chan_dep_vld_vec(in_chan_dep_vld_vec_29),
        .in_chan_dep_data_vec(in_chan_dep_data_vec_29),
        .token_in_vec(token_in_vec_29),
        .dl_detect_in(dl_detect_out),
        .origin(origin[29]),
        .token_clear(token_clear),
        .out_chan_dep_vld_vec(out_chan_dep_vld_vec_29),
        .out_chan_dep_data(out_chan_dep_data_29),
        .token_out_vec(token_out_vec_29),
        .dl_detect_out(dl_in_vec[29]));

    assign proc_29_data_FIFO_blk[0] = 1'b0 | (~grp_dataflow_wrapper_fu_6443.task_compute_attn_U0.grp_do_attn_1_fu_5150.do_matmul_4_U0.do_adapt_13_1_U0.mac_sm_blk_n);
    assign proc_29_data_PIPO_blk[0] = 1'b0;
    assign proc_29_start_FIFO_blk[0] = 1'b0 | (~grp_dataflow_wrapper_fu_6443.task_compute_attn_U0.grp_do_attn_1_fu_5150.do_matmul_4_U0.start_for_do_adapt_13_1_U0_U.if_empty_n & grp_dataflow_wrapper_fu_6443.task_compute_attn_U0.grp_do_attn_1_fu_5150.do_matmul_4_U0.do_adapt_13_1_U0.ap_idle & ~grp_dataflow_wrapper_fu_6443.task_compute_attn_U0.grp_do_attn_1_fu_5150.do_matmul_4_U0.start_for_do_adapt_13_1_U0_U.if_write);
    assign proc_29_TLF_FIFO_blk[0] = 1'b0;
    assign proc_29_input_sync_blk[0] = 1'b0;
    assign proc_29_output_sync_blk[0] = 1'b0;
    assign proc_dep_vld_vec_29[0] = dl_detect_out ? proc_dep_vld_vec_29_reg[0] : (proc_29_data_FIFO_blk[0] | proc_29_data_PIPO_blk[0] | proc_29_start_FIFO_blk[0] | proc_29_TLF_FIFO_blk[0] | proc_29_input_sync_blk[0] | proc_29_output_sync_blk[0]);
    assign proc_29_data_FIFO_blk[1] = 1'b0 | (~grp_dataflow_wrapper_fu_6443.task_compute_attn_U0.grp_do_attn_1_fu_5150.do_matmul_4_U0.do_adapt_13_1_U0.v_sm_blk_n);
    assign proc_29_data_PIPO_blk[1] = 1'b0;
    assign proc_29_start_FIFO_blk[1] = 1'b0;
    assign proc_29_TLF_FIFO_blk[1] = 1'b0;
    assign proc_29_input_sync_blk[1] = 1'b0;
    assign proc_29_output_sync_blk[1] = 1'b0;
    assign proc_dep_vld_vec_29[1] = dl_detect_out ? proc_dep_vld_vec_29_reg[1] : (proc_29_data_FIFO_blk[1] | proc_29_data_PIPO_blk[1] | proc_29_start_FIFO_blk[1] | proc_29_TLF_FIFO_blk[1] | proc_29_input_sync_blk[1] | proc_29_output_sync_blk[1]);
    always @ (negedge dl_reset or posedge dl_clock) begin
        if (~dl_reset) begin
            proc_dep_vld_vec_29_reg <= 'b0;
        end
        else begin
            proc_dep_vld_vec_29_reg <= proc_dep_vld_vec_29;
        end
    end
    assign in_chan_dep_vld_vec_29[0] = dep_chan_vld_28_29;
    assign in_chan_dep_data_vec_29[73 : 0] = dep_chan_data_28_29;
    assign token_in_vec_29[0] = token_28_29;
    assign in_chan_dep_vld_vec_29[1] = dep_chan_vld_32_29;
    assign in_chan_dep_data_vec_29[147 : 74] = dep_chan_data_32_29;
    assign token_in_vec_29[1] = token_32_29;
    assign dep_chan_vld_29_28 = out_chan_dep_vld_vec_29[0];
    assign dep_chan_data_29_28 = out_chan_dep_data_29;
    assign token_29_28 = token_out_vec_29[0];
    assign dep_chan_vld_29_32 = out_chan_dep_vld_vec_29[1];
    assign dep_chan_data_29_32 = out_chan_dep_data_29;
    assign token_29_32 = token_out_vec_29[1];

    // Process: grp_dataflow_wrapper_fu_6443.task_compute_attn_U0.grp_do_attn_1_fu_5150.do_quant_U0
    vit_block_top_hls_deadlock_detect_unit #(74, 30, 3, 3) vit_block_top_hls_deadlock_detect_unit_30 (
        .reset(dl_reset),
        .clock(dl_clock),
        .proc_dep_vld_vec(proc_dep_vld_vec_30),
        .in_chan_dep_vld_vec(in_chan_dep_vld_vec_30),
        .in_chan_dep_data_vec(in_chan_dep_data_vec_30),
        .token_in_vec(token_in_vec_30),
        .dl_detect_in(dl_detect_out),
        .origin(origin[30]),
        .token_clear(token_clear),
        .out_chan_dep_vld_vec(out_chan_dep_vld_vec_30),
        .out_chan_dep_data(out_chan_dep_data_30),
        .token_out_vec(token_out_vec_30),
        .dl_detect_out(dl_in_vec[30]));

    assign proc_30_data_FIFO_blk[0] = 1'b0 | (~grp_dataflow_wrapper_fu_6443.task_compute_attn_U0.grp_do_attn_1_fu_5150.do_quant_U0.grp_do_quant_Pipeline_TT_LOOP_CT_LOOP_fu_82.q_sm_blk_n);
    assign proc_30_data_PIPO_blk[0] = 1'b0;
    assign proc_30_start_FIFO_blk[0] = 1'b0 | (~grp_dataflow_wrapper_fu_6443.task_compute_attn_U0.grp_do_attn_1_fu_5150.start_for_do_quant_U0_U.if_empty_n & grp_dataflow_wrapper_fu_6443.task_compute_attn_U0.grp_do_attn_1_fu_5150.do_quant_U0.ap_idle & ~grp_dataflow_wrapper_fu_6443.task_compute_attn_U0.grp_do_attn_1_fu_5150.start_for_do_quant_U0_U.if_write);
    assign proc_30_TLF_FIFO_blk[0] = 1'b0;
    assign proc_30_input_sync_blk[0] = 1'b0;
    assign proc_30_output_sync_blk[0] = 1'b0;
    assign proc_dep_vld_vec_30[0] = dl_detect_out ? proc_dep_vld_vec_30_reg[0] : (proc_30_data_FIFO_blk[0] | proc_30_data_PIPO_blk[0] | proc_30_start_FIFO_blk[0] | proc_30_TLF_FIFO_blk[0] | proc_30_input_sync_blk[0] | proc_30_output_sync_blk[0]);
    assign proc_30_data_FIFO_blk[1] = 1'b0 | (~grp_dataflow_wrapper_fu_6443.task_compute_attn_U0.grp_do_attn_1_fu_5150.do_quant_U0.grp_do_quant_Pipeline_TT_LOOP_CT_LOOP_fu_82.q_sm_blk_n);
    assign proc_30_data_PIPO_blk[1] = 1'b0;
    assign proc_30_start_FIFO_blk[1] = 1'b0;
    assign proc_30_TLF_FIFO_blk[1] = 1'b0;
    assign proc_30_input_sync_blk[1] = 1'b0;
    assign proc_30_output_sync_blk[1] = 1'b0;
    assign proc_dep_vld_vec_30[1] = dl_detect_out ? proc_dep_vld_vec_30_reg[1] : (proc_30_data_FIFO_blk[1] | proc_30_data_PIPO_blk[1] | proc_30_start_FIFO_blk[1] | proc_30_TLF_FIFO_blk[1] | proc_30_input_sync_blk[1] | proc_30_output_sync_blk[1]);
    assign proc_30_data_FIFO_blk[2] = 1'b0 | (~grp_dataflow_wrapper_fu_6443.task_compute_attn_U0.grp_do_attn_1_fu_5150.do_quant_U0.grp_do_quant_Pipeline_TT_LOOP_CT_LOOP_fu_82.qq_sm_blk_n);
    assign proc_30_data_PIPO_blk[2] = 1'b0;
    assign proc_30_start_FIFO_blk[2] = 1'b0 | (~grp_dataflow_wrapper_fu_6443.task_compute_attn_U0.grp_do_attn_1_fu_5150.start_for_do_split_4_U0_U.if_full_n & grp_dataflow_wrapper_fu_6443.task_compute_attn_U0.grp_do_attn_1_fu_5150.do_quant_U0.ap_start & ~grp_dataflow_wrapper_fu_6443.task_compute_attn_U0.grp_do_attn_1_fu_5150.do_quant_U0.real_start & (trans_in_cnt_19 == trans_out_cnt_19) & ~grp_dataflow_wrapper_fu_6443.task_compute_attn_U0.grp_do_attn_1_fu_5150.start_for_do_split_4_U0_U.if_read);
    assign proc_30_TLF_FIFO_blk[2] = 1'b0;
    assign proc_30_input_sync_blk[2] = 1'b0;
    assign proc_30_output_sync_blk[2] = 1'b0;
    assign proc_dep_vld_vec_30[2] = dl_detect_out ? proc_dep_vld_vec_30_reg[2] : (proc_30_data_FIFO_blk[2] | proc_30_data_PIPO_blk[2] | proc_30_start_FIFO_blk[2] | proc_30_TLF_FIFO_blk[2] | proc_30_input_sync_blk[2] | proc_30_output_sync_blk[2]);
    always @ (negedge dl_reset or posedge dl_clock) begin
        if (~dl_reset) begin
            proc_dep_vld_vec_30_reg <= 'b0;
        end
        else begin
            proc_dep_vld_vec_30_reg <= proc_dep_vld_vec_30;
        end
    end
    assign in_chan_dep_vld_vec_30[0] = dep_chan_vld_15_30;
    assign in_chan_dep_data_vec_30[73 : 0] = dep_chan_data_15_30;
    assign token_in_vec_30[0] = token_15_30;
    assign in_chan_dep_vld_vec_30[1] = dep_chan_vld_19_30;
    assign in_chan_dep_data_vec_30[147 : 74] = dep_chan_data_19_30;
    assign token_in_vec_30[1] = token_19_30;
    assign in_chan_dep_vld_vec_30[2] = dep_chan_vld_33_30;
    assign in_chan_dep_data_vec_30[221 : 148] = dep_chan_data_33_30;
    assign token_in_vec_30[2] = token_33_30;
    assign dep_chan_vld_30_15 = out_chan_dep_vld_vec_30[0];
    assign dep_chan_data_30_15 = out_chan_dep_data_30;
    assign token_30_15 = token_out_vec_30[0];
    assign dep_chan_vld_30_19 = out_chan_dep_vld_vec_30[1];
    assign dep_chan_data_30_19 = out_chan_dep_data_30;
    assign token_30_19 = token_out_vec_30[1];
    assign dep_chan_vld_30_33 = out_chan_dep_vld_vec_30[2];
    assign dep_chan_data_30_33 = out_chan_dep_data_30;
    assign token_30_33 = token_out_vec_30[2];

    // Process: grp_dataflow_wrapper_fu_6443.task_compute_attn_U0.grp_do_attn_1_fu_5150.do_quant_3_U0
    vit_block_top_hls_deadlock_detect_unit #(74, 31, 3, 3) vit_block_top_hls_deadlock_detect_unit_31 (
        .reset(dl_reset),
        .clock(dl_clock),
        .proc_dep_vld_vec(proc_dep_vld_vec_31),
        .in_chan_dep_vld_vec(in_chan_dep_vld_vec_31),
        .in_chan_dep_data_vec(in_chan_dep_data_vec_31),
        .token_in_vec(token_in_vec_31),
        .dl_detect_in(dl_detect_out),
        .origin(origin[31]),
        .token_clear(token_clear),
        .out_chan_dep_vld_vec(out_chan_dep_vld_vec_31),
        .out_chan_dep_data(out_chan_dep_data_31),
        .token_out_vec(token_out_vec_31),
        .dl_detect_out(dl_in_vec[31]));

    assign proc_31_data_FIFO_blk[0] = 1'b0 | (~grp_dataflow_wrapper_fu_6443.task_compute_attn_U0.grp_do_attn_1_fu_5150.do_quant_3_U0.grp_do_quant_3_Pipeline_TT_LOOP_CT_LOOP_fu_82.k_sm_blk_n);
    assign proc_31_data_PIPO_blk[0] = 1'b0;
    assign proc_31_start_FIFO_blk[0] = 1'b0 | (~grp_dataflow_wrapper_fu_6443.task_compute_attn_U0.grp_do_attn_1_fu_5150.start_for_do_quant_3_U0_U.if_empty_n & grp_dataflow_wrapper_fu_6443.task_compute_attn_U0.grp_do_attn_1_fu_5150.do_quant_3_U0.ap_idle & ~grp_dataflow_wrapper_fu_6443.task_compute_attn_U0.grp_do_attn_1_fu_5150.start_for_do_quant_3_U0_U.if_write);
    assign proc_31_TLF_FIFO_blk[0] = 1'b0;
    assign proc_31_input_sync_blk[0] = 1'b0;
    assign proc_31_output_sync_blk[0] = 1'b0;
    assign proc_dep_vld_vec_31[0] = dl_detect_out ? proc_dep_vld_vec_31_reg[0] : (proc_31_data_FIFO_blk[0] | proc_31_data_PIPO_blk[0] | proc_31_start_FIFO_blk[0] | proc_31_TLF_FIFO_blk[0] | proc_31_input_sync_blk[0] | proc_31_output_sync_blk[0]);
    assign proc_31_data_FIFO_blk[1] = 1'b0 | (~grp_dataflow_wrapper_fu_6443.task_compute_attn_U0.grp_do_attn_1_fu_5150.do_quant_3_U0.grp_do_quant_3_Pipeline_TT_LOOP_CT_LOOP_fu_82.k_sm_blk_n);
    assign proc_31_data_PIPO_blk[1] = 1'b0;
    assign proc_31_start_FIFO_blk[1] = 1'b0;
    assign proc_31_TLF_FIFO_blk[1] = 1'b0;
    assign proc_31_input_sync_blk[1] = 1'b0;
    assign proc_31_output_sync_blk[1] = 1'b0;
    assign proc_dep_vld_vec_31[1] = dl_detect_out ? proc_dep_vld_vec_31_reg[1] : (proc_31_data_FIFO_blk[1] | proc_31_data_PIPO_blk[1] | proc_31_start_FIFO_blk[1] | proc_31_TLF_FIFO_blk[1] | proc_31_input_sync_blk[1] | proc_31_output_sync_blk[1]);
    assign proc_31_data_FIFO_blk[2] = 1'b0 | (~grp_dataflow_wrapper_fu_6443.task_compute_attn_U0.grp_do_attn_1_fu_5150.do_quant_3_U0.grp_do_quant_3_Pipeline_TT_LOOP_CT_LOOP_fu_82.kq_sm_blk_n);
    assign proc_31_data_PIPO_blk[2] = 1'b0;
    assign proc_31_start_FIFO_blk[2] = 1'b0 | (~grp_dataflow_wrapper_fu_6443.task_compute_attn_U0.grp_do_attn_1_fu_5150.start_for_do_split_5_U0_U.if_full_n & grp_dataflow_wrapper_fu_6443.task_compute_attn_U0.grp_do_attn_1_fu_5150.do_quant_3_U0.ap_start & ~grp_dataflow_wrapper_fu_6443.task_compute_attn_U0.grp_do_attn_1_fu_5150.do_quant_3_U0.real_start & (trans_in_cnt_20 == trans_out_cnt_20) & ~grp_dataflow_wrapper_fu_6443.task_compute_attn_U0.grp_do_attn_1_fu_5150.start_for_do_split_5_U0_U.if_read);
    assign proc_31_TLF_FIFO_blk[2] = 1'b0;
    assign proc_31_input_sync_blk[2] = 1'b0;
    assign proc_31_output_sync_blk[2] = 1'b0;
    assign proc_dep_vld_vec_31[2] = dl_detect_out ? proc_dep_vld_vec_31_reg[2] : (proc_31_data_FIFO_blk[2] | proc_31_data_PIPO_blk[2] | proc_31_start_FIFO_blk[2] | proc_31_TLF_FIFO_blk[2] | proc_31_input_sync_blk[2] | proc_31_output_sync_blk[2]);
    always @ (negedge dl_reset or posedge dl_clock) begin
        if (~dl_reset) begin
            proc_dep_vld_vec_31_reg <= 'b0;
        end
        else begin
            proc_dep_vld_vec_31_reg <= proc_dep_vld_vec_31;
        end
    end
    assign in_chan_dep_vld_vec_31[0] = dep_chan_vld_20_31;
    assign in_chan_dep_data_vec_31[73 : 0] = dep_chan_data_20_31;
    assign token_in_vec_31[0] = token_20_31;
    assign in_chan_dep_vld_vec_31[1] = dep_chan_vld_24_31;
    assign in_chan_dep_data_vec_31[147 : 74] = dep_chan_data_24_31;
    assign token_in_vec_31[1] = token_24_31;
    assign in_chan_dep_vld_vec_31[2] = dep_chan_vld_34_31;
    assign in_chan_dep_data_vec_31[221 : 148] = dep_chan_data_34_31;
    assign token_in_vec_31[2] = token_34_31;
    assign dep_chan_vld_31_20 = out_chan_dep_vld_vec_31[0];
    assign dep_chan_data_31_20 = out_chan_dep_data_31;
    assign token_31_20 = token_out_vec_31[0];
    assign dep_chan_vld_31_24 = out_chan_dep_vld_vec_31[1];
    assign dep_chan_data_31_24 = out_chan_dep_data_31;
    assign token_31_24 = token_out_vec_31[1];
    assign dep_chan_vld_31_34 = out_chan_dep_vld_vec_31[2];
    assign dep_chan_data_31_34 = out_chan_dep_data_31;
    assign token_31_34 = token_out_vec_31[2];

    // Process: grp_dataflow_wrapper_fu_6443.task_compute_attn_U0.grp_do_attn_1_fu_5150.do_quant_1_U0
    vit_block_top_hls_deadlock_detect_unit #(74, 32, 3, 3) vit_block_top_hls_deadlock_detect_unit_32 (
        .reset(dl_reset),
        .clock(dl_clock),
        .proc_dep_vld_vec(proc_dep_vld_vec_32),
        .in_chan_dep_vld_vec(in_chan_dep_vld_vec_32),
        .in_chan_dep_data_vec(in_chan_dep_data_vec_32),
        .token_in_vec(token_in_vec_32),
        .dl_detect_in(dl_detect_out),
        .origin(origin[32]),
        .token_clear(token_clear),
        .out_chan_dep_vld_vec(out_chan_dep_vld_vec_32),
        .out_chan_dep_data(out_chan_dep_data_32),
        .token_out_vec(token_out_vec_32),
        .dl_detect_out(dl_in_vec[32]));

    assign proc_32_data_FIFO_blk[0] = 1'b0 | (~grp_dataflow_wrapper_fu_6443.task_compute_attn_U0.grp_do_attn_1_fu_5150.do_quant_1_U0.grp_do_quant_1_Pipeline_TT_LOOP_CT_LOOP_fu_82.v_sm_blk_n);
    assign proc_32_data_PIPO_blk[0] = 1'b0;
    assign proc_32_start_FIFO_blk[0] = 1'b0 | (~grp_dataflow_wrapper_fu_6443.task_compute_attn_U0.grp_do_attn_1_fu_5150.start_for_do_quant_1_U0_U.if_empty_n & grp_dataflow_wrapper_fu_6443.task_compute_attn_U0.grp_do_attn_1_fu_5150.do_quant_1_U0.ap_idle & ~grp_dataflow_wrapper_fu_6443.task_compute_attn_U0.grp_do_attn_1_fu_5150.start_for_do_quant_1_U0_U.if_write);
    assign proc_32_TLF_FIFO_blk[0] = 1'b0;
    assign proc_32_input_sync_blk[0] = 1'b0;
    assign proc_32_output_sync_blk[0] = 1'b0;
    assign proc_dep_vld_vec_32[0] = dl_detect_out ? proc_dep_vld_vec_32_reg[0] : (proc_32_data_FIFO_blk[0] | proc_32_data_PIPO_blk[0] | proc_32_start_FIFO_blk[0] | proc_32_TLF_FIFO_blk[0] | proc_32_input_sync_blk[0] | proc_32_output_sync_blk[0]);
    assign proc_32_data_FIFO_blk[1] = 1'b0 | (~grp_dataflow_wrapper_fu_6443.task_compute_attn_U0.grp_do_attn_1_fu_5150.do_quant_1_U0.grp_do_quant_1_Pipeline_TT_LOOP_CT_LOOP_fu_82.v_sm_blk_n);
    assign proc_32_data_PIPO_blk[1] = 1'b0;
    assign proc_32_start_FIFO_blk[1] = 1'b0;
    assign proc_32_TLF_FIFO_blk[1] = 1'b0;
    assign proc_32_input_sync_blk[1] = 1'b0;
    assign proc_32_output_sync_blk[1] = 1'b0;
    assign proc_dep_vld_vec_32[1] = dl_detect_out ? proc_dep_vld_vec_32_reg[1] : (proc_32_data_FIFO_blk[1] | proc_32_data_PIPO_blk[1] | proc_32_start_FIFO_blk[1] | proc_32_TLF_FIFO_blk[1] | proc_32_input_sync_blk[1] | proc_32_output_sync_blk[1]);
    assign proc_32_data_FIFO_blk[2] = 1'b0 | (~grp_dataflow_wrapper_fu_6443.task_compute_attn_U0.grp_do_attn_1_fu_5150.do_quant_1_U0.grp_do_quant_1_Pipeline_TT_LOOP_CT_LOOP_fu_82.vq_sm_blk_n);
    assign proc_32_data_PIPO_blk[2] = 1'b0;
    assign proc_32_start_FIFO_blk[2] = 1'b0 | (~grp_dataflow_wrapper_fu_6443.task_compute_attn_U0.grp_do_attn_1_fu_5150.start_for_do_split_U0_U.if_full_n & grp_dataflow_wrapper_fu_6443.task_compute_attn_U0.grp_do_attn_1_fu_5150.do_quant_1_U0.ap_start & ~grp_dataflow_wrapper_fu_6443.task_compute_attn_U0.grp_do_attn_1_fu_5150.do_quant_1_U0.real_start & (trans_in_cnt_21 == trans_out_cnt_21) & ~grp_dataflow_wrapper_fu_6443.task_compute_attn_U0.grp_do_attn_1_fu_5150.start_for_do_split_U0_U.if_read);
    assign proc_32_TLF_FIFO_blk[2] = 1'b0;
    assign proc_32_input_sync_blk[2] = 1'b0;
    assign proc_32_output_sync_blk[2] = 1'b0;
    assign proc_dep_vld_vec_32[2] = dl_detect_out ? proc_dep_vld_vec_32_reg[2] : (proc_32_data_FIFO_blk[2] | proc_32_data_PIPO_blk[2] | proc_32_start_FIFO_blk[2] | proc_32_TLF_FIFO_blk[2] | proc_32_input_sync_blk[2] | proc_32_output_sync_blk[2]);
    always @ (negedge dl_reset or posedge dl_clock) begin
        if (~dl_reset) begin
            proc_dep_vld_vec_32_reg <= 'b0;
        end
        else begin
            proc_dep_vld_vec_32_reg <= proc_dep_vld_vec_32;
        end
    end
    assign in_chan_dep_vld_vec_32[0] = dep_chan_vld_25_32;
    assign in_chan_dep_data_vec_32[73 : 0] = dep_chan_data_25_32;
    assign token_in_vec_32[0] = token_25_32;
    assign in_chan_dep_vld_vec_32[1] = dep_chan_vld_29_32;
    assign in_chan_dep_data_vec_32[147 : 74] = dep_chan_data_29_32;
    assign token_in_vec_32[1] = token_29_32;
    assign in_chan_dep_vld_vec_32[2] = dep_chan_vld_35_32;
    assign in_chan_dep_data_vec_32[221 : 148] = dep_chan_data_35_32;
    assign token_in_vec_32[2] = token_35_32;
    assign dep_chan_vld_32_25 = out_chan_dep_vld_vec_32[0];
    assign dep_chan_data_32_25 = out_chan_dep_data_32;
    assign token_32_25 = token_out_vec_32[0];
    assign dep_chan_vld_32_29 = out_chan_dep_vld_vec_32[1];
    assign dep_chan_data_32_29 = out_chan_dep_data_32;
    assign token_32_29 = token_out_vec_32[1];
    assign dep_chan_vld_32_35 = out_chan_dep_vld_vec_32[2];
    assign dep_chan_data_32_35 = out_chan_dep_data_32;
    assign token_32_35 = token_out_vec_32[2];

    // Process: grp_dataflow_wrapper_fu_6443.task_compute_attn_U0.grp_do_attn_1_fu_5150.do_split_4_U0
    vit_block_top_hls_deadlock_detect_unit #(74, 33, 4, 4) vit_block_top_hls_deadlock_detect_unit_33 (
        .reset(dl_reset),
        .clock(dl_clock),
        .proc_dep_vld_vec(proc_dep_vld_vec_33),
        .in_chan_dep_vld_vec(in_chan_dep_vld_vec_33),
        .in_chan_dep_data_vec(in_chan_dep_data_vec_33),
        .token_in_vec(token_in_vec_33),
        .dl_detect_in(dl_detect_out),
        .origin(origin[33]),
        .token_clear(token_clear),
        .out_chan_dep_vld_vec(out_chan_dep_vld_vec_33),
        .out_chan_dep_data(out_chan_dep_data_33),
        .token_out_vec(token_out_vec_33),
        .dl_detect_out(dl_in_vec[33]));

    assign proc_33_data_FIFO_blk[0] = 1'b0 | (~grp_dataflow_wrapper_fu_6443.task_compute_attn_U0.grp_do_attn_1_fu_5150.do_split_4_U0.qq_sm_blk_n);
    assign proc_33_data_PIPO_blk[0] = 1'b0;
    assign proc_33_start_FIFO_blk[0] = 1'b0 | (~grp_dataflow_wrapper_fu_6443.task_compute_attn_U0.grp_do_attn_1_fu_5150.start_for_do_split_4_U0_U.if_empty_n & grp_dataflow_wrapper_fu_6443.task_compute_attn_U0.grp_do_attn_1_fu_5150.do_split_4_U0.ap_idle & ~grp_dataflow_wrapper_fu_6443.task_compute_attn_U0.grp_do_attn_1_fu_5150.start_for_do_split_4_U0_U.if_write);
    assign proc_33_TLF_FIFO_blk[0] = 1'b0;
    assign proc_33_input_sync_blk[0] = 1'b0;
    assign proc_33_output_sync_blk[0] = 1'b0;
    assign proc_dep_vld_vec_33[0] = dl_detect_out ? proc_dep_vld_vec_33_reg[0] : (proc_33_data_FIFO_blk[0] | proc_33_data_PIPO_blk[0] | proc_33_start_FIFO_blk[0] | proc_33_TLF_FIFO_blk[0] | proc_33_input_sync_blk[0] | proc_33_output_sync_blk[0]);
    assign proc_33_data_FIFO_blk[1] = 1'b0 | (~grp_dataflow_wrapper_fu_6443.task_compute_attn_U0.grp_do_attn_1_fu_5150.do_split_4_U0.qq_sm_head_0_blk_n);
    assign proc_33_data_PIPO_blk[1] = 1'b0;
    assign proc_33_start_FIFO_blk[1] = 1'b0 | (~grp_dataflow_wrapper_fu_6443.task_compute_attn_U0.grp_do_attn_1_fu_5150.start_for_do_attn_6_U0_U.if_full_n & grp_dataflow_wrapper_fu_6443.task_compute_attn_U0.grp_do_attn_1_fu_5150.do_split_4_U0.ap_start & ~grp_dataflow_wrapper_fu_6443.task_compute_attn_U0.grp_do_attn_1_fu_5150.do_split_4_U0.real_start & (trans_in_cnt_22 == trans_out_cnt_22) & ~grp_dataflow_wrapper_fu_6443.task_compute_attn_U0.grp_do_attn_1_fu_5150.start_for_do_attn_6_U0_U.if_read);
    assign proc_33_TLF_FIFO_blk[1] = 1'b0;
    assign proc_33_input_sync_blk[1] = 1'b0;
    assign proc_33_output_sync_blk[1] = 1'b0;
    assign proc_dep_vld_vec_33[1] = dl_detect_out ? proc_dep_vld_vec_33_reg[1] : (proc_33_data_FIFO_blk[1] | proc_33_data_PIPO_blk[1] | proc_33_start_FIFO_blk[1] | proc_33_TLF_FIFO_blk[1] | proc_33_input_sync_blk[1] | proc_33_output_sync_blk[1]);
    assign proc_33_data_FIFO_blk[2] = 1'b0 | (~grp_dataflow_wrapper_fu_6443.task_compute_attn_U0.grp_do_attn_1_fu_5150.do_split_4_U0.qq_sm_head_1_blk_n);
    assign proc_33_data_PIPO_blk[2] = 1'b0;
    assign proc_33_start_FIFO_blk[2] = 1'b0 | (~grp_dataflow_wrapper_fu_6443.task_compute_attn_U0.grp_do_attn_1_fu_5150.start_for_do_attn_7_U0_U.if_full_n & grp_dataflow_wrapper_fu_6443.task_compute_attn_U0.grp_do_attn_1_fu_5150.do_split_4_U0.ap_start & ~grp_dataflow_wrapper_fu_6443.task_compute_attn_U0.grp_do_attn_1_fu_5150.do_split_4_U0.real_start & (trans_in_cnt_22 == trans_out_cnt_22) & ~grp_dataflow_wrapper_fu_6443.task_compute_attn_U0.grp_do_attn_1_fu_5150.start_for_do_attn_7_U0_U.if_read);
    assign proc_33_TLF_FIFO_blk[2] = 1'b0;
    assign proc_33_input_sync_blk[2] = 1'b0;
    assign proc_33_output_sync_blk[2] = 1'b0;
    assign proc_dep_vld_vec_33[2] = dl_detect_out ? proc_dep_vld_vec_33_reg[2] : (proc_33_data_FIFO_blk[2] | proc_33_data_PIPO_blk[2] | proc_33_start_FIFO_blk[2] | proc_33_TLF_FIFO_blk[2] | proc_33_input_sync_blk[2] | proc_33_output_sync_blk[2]);
    assign proc_33_data_FIFO_blk[3] = 1'b0 | (~grp_dataflow_wrapper_fu_6443.task_compute_attn_U0.grp_do_attn_1_fu_5150.do_split_4_U0.qq_sm_head_2_blk_n);
    assign proc_33_data_PIPO_blk[3] = 1'b0;
    assign proc_33_start_FIFO_blk[3] = 1'b0 | (~grp_dataflow_wrapper_fu_6443.task_compute_attn_U0.grp_do_attn_1_fu_5150.start_for_do_attn_U0_U.if_full_n & grp_dataflow_wrapper_fu_6443.task_compute_attn_U0.grp_do_attn_1_fu_5150.do_split_4_U0.ap_start & ~grp_dataflow_wrapper_fu_6443.task_compute_attn_U0.grp_do_attn_1_fu_5150.do_split_4_U0.real_start & (trans_in_cnt_22 == trans_out_cnt_22) & ~grp_dataflow_wrapper_fu_6443.task_compute_attn_U0.grp_do_attn_1_fu_5150.start_for_do_attn_U0_U.if_read);
    assign proc_33_TLF_FIFO_blk[3] = 1'b0;
    assign proc_33_input_sync_blk[3] = 1'b0;
    assign proc_33_output_sync_blk[3] = 1'b0;
    assign proc_dep_vld_vec_33[3] = dl_detect_out ? proc_dep_vld_vec_33_reg[3] : (proc_33_data_FIFO_blk[3] | proc_33_data_PIPO_blk[3] | proc_33_start_FIFO_blk[3] | proc_33_TLF_FIFO_blk[3] | proc_33_input_sync_blk[3] | proc_33_output_sync_blk[3]);
    always @ (negedge dl_reset or posedge dl_clock) begin
        if (~dl_reset) begin
            proc_dep_vld_vec_33_reg <= 'b0;
        end
        else begin
            proc_dep_vld_vec_33_reg <= proc_dep_vld_vec_33;
        end
    end
    assign in_chan_dep_vld_vec_33[0] = dep_chan_vld_30_33;
    assign in_chan_dep_data_vec_33[73 : 0] = dep_chan_data_30_33;
    assign token_in_vec_33[0] = token_30_33;
    assign in_chan_dep_vld_vec_33[1] = dep_chan_vld_36_33;
    assign in_chan_dep_data_vec_33[147 : 74] = dep_chan_data_36_33;
    assign token_in_vec_33[1] = token_36_33;
    assign in_chan_dep_vld_vec_33[2] = dep_chan_vld_37_33;
    assign in_chan_dep_data_vec_33[221 : 148] = dep_chan_data_37_33;
    assign token_in_vec_33[2] = token_37_33;
    assign in_chan_dep_vld_vec_33[3] = dep_chan_vld_38_33;
    assign in_chan_dep_data_vec_33[295 : 222] = dep_chan_data_38_33;
    assign token_in_vec_33[3] = token_38_33;
    assign dep_chan_vld_33_30 = out_chan_dep_vld_vec_33[0];
    assign dep_chan_data_33_30 = out_chan_dep_data_33;
    assign token_33_30 = token_out_vec_33[0];
    assign dep_chan_vld_33_36 = out_chan_dep_vld_vec_33[1];
    assign dep_chan_data_33_36 = out_chan_dep_data_33;
    assign token_33_36 = token_out_vec_33[1];
    assign dep_chan_vld_33_37 = out_chan_dep_vld_vec_33[2];
    assign dep_chan_data_33_37 = out_chan_dep_data_33;
    assign token_33_37 = token_out_vec_33[2];
    assign dep_chan_vld_33_38 = out_chan_dep_vld_vec_33[3];
    assign dep_chan_data_33_38 = out_chan_dep_data_33;
    assign token_33_38 = token_out_vec_33[3];

    // Process: grp_dataflow_wrapper_fu_6443.task_compute_attn_U0.grp_do_attn_1_fu_5150.do_split_5_U0
    vit_block_top_hls_deadlock_detect_unit #(74, 34, 4, 4) vit_block_top_hls_deadlock_detect_unit_34 (
        .reset(dl_reset),
        .clock(dl_clock),
        .proc_dep_vld_vec(proc_dep_vld_vec_34),
        .in_chan_dep_vld_vec(in_chan_dep_vld_vec_34),
        .in_chan_dep_data_vec(in_chan_dep_data_vec_34),
        .token_in_vec(token_in_vec_34),
        .dl_detect_in(dl_detect_out),
        .origin(origin[34]),
        .token_clear(token_clear),
        .out_chan_dep_vld_vec(out_chan_dep_vld_vec_34),
        .out_chan_dep_data(out_chan_dep_data_34),
        .token_out_vec(token_out_vec_34),
        .dl_detect_out(dl_in_vec[34]));

    assign proc_34_data_FIFO_blk[0] = 1'b0 | (~grp_dataflow_wrapper_fu_6443.task_compute_attn_U0.grp_do_attn_1_fu_5150.do_split_5_U0.kq_sm_blk_n);
    assign proc_34_data_PIPO_blk[0] = 1'b0;
    assign proc_34_start_FIFO_blk[0] = 1'b0 | (~grp_dataflow_wrapper_fu_6443.task_compute_attn_U0.grp_do_attn_1_fu_5150.start_for_do_split_5_U0_U.if_empty_n & grp_dataflow_wrapper_fu_6443.task_compute_attn_U0.grp_do_attn_1_fu_5150.do_split_5_U0.ap_idle & ~grp_dataflow_wrapper_fu_6443.task_compute_attn_U0.grp_do_attn_1_fu_5150.start_for_do_split_5_U0_U.if_write);
    assign proc_34_TLF_FIFO_blk[0] = 1'b0;
    assign proc_34_input_sync_blk[0] = 1'b0;
    assign proc_34_output_sync_blk[0] = 1'b0;
    assign proc_dep_vld_vec_34[0] = dl_detect_out ? proc_dep_vld_vec_34_reg[0] : (proc_34_data_FIFO_blk[0] | proc_34_data_PIPO_blk[0] | proc_34_start_FIFO_blk[0] | proc_34_TLF_FIFO_blk[0] | proc_34_input_sync_blk[0] | proc_34_output_sync_blk[0]);
    assign proc_34_data_FIFO_blk[1] = 1'b0 | (~grp_dataflow_wrapper_fu_6443.task_compute_attn_U0.grp_do_attn_1_fu_5150.do_split_5_U0.kq_sm_head_0_blk_n);
    assign proc_34_data_PIPO_blk[1] = 1'b0;
    assign proc_34_start_FIFO_blk[1] = 1'b0;
    assign proc_34_TLF_FIFO_blk[1] = 1'b0;
    assign proc_34_input_sync_blk[1] = 1'b0;
    assign proc_34_output_sync_blk[1] = 1'b0;
    assign proc_dep_vld_vec_34[1] = dl_detect_out ? proc_dep_vld_vec_34_reg[1] : (proc_34_data_FIFO_blk[1] | proc_34_data_PIPO_blk[1] | proc_34_start_FIFO_blk[1] | proc_34_TLF_FIFO_blk[1] | proc_34_input_sync_blk[1] | proc_34_output_sync_blk[1]);
    assign proc_34_data_FIFO_blk[2] = 1'b0 | (~grp_dataflow_wrapper_fu_6443.task_compute_attn_U0.grp_do_attn_1_fu_5150.do_split_5_U0.kq_sm_head_1_blk_n);
    assign proc_34_data_PIPO_blk[2] = 1'b0;
    assign proc_34_start_FIFO_blk[2] = 1'b0;
    assign proc_34_TLF_FIFO_blk[2] = 1'b0;
    assign proc_34_input_sync_blk[2] = 1'b0;
    assign proc_34_output_sync_blk[2] = 1'b0;
    assign proc_dep_vld_vec_34[2] = dl_detect_out ? proc_dep_vld_vec_34_reg[2] : (proc_34_data_FIFO_blk[2] | proc_34_data_PIPO_blk[2] | proc_34_start_FIFO_blk[2] | proc_34_TLF_FIFO_blk[2] | proc_34_input_sync_blk[2] | proc_34_output_sync_blk[2]);
    assign proc_34_data_FIFO_blk[3] = 1'b0 | (~grp_dataflow_wrapper_fu_6443.task_compute_attn_U0.grp_do_attn_1_fu_5150.do_split_5_U0.kq_sm_head_2_blk_n);
    assign proc_34_data_PIPO_blk[3] = 1'b0;
    assign proc_34_start_FIFO_blk[3] = 1'b0;
    assign proc_34_TLF_FIFO_blk[3] = 1'b0;
    assign proc_34_input_sync_blk[3] = 1'b0;
    assign proc_34_output_sync_blk[3] = 1'b0;
    assign proc_dep_vld_vec_34[3] = dl_detect_out ? proc_dep_vld_vec_34_reg[3] : (proc_34_data_FIFO_blk[3] | proc_34_data_PIPO_blk[3] | proc_34_start_FIFO_blk[3] | proc_34_TLF_FIFO_blk[3] | proc_34_input_sync_blk[3] | proc_34_output_sync_blk[3]);
    always @ (negedge dl_reset or posedge dl_clock) begin
        if (~dl_reset) begin
            proc_dep_vld_vec_34_reg <= 'b0;
        end
        else begin
            proc_dep_vld_vec_34_reg <= proc_dep_vld_vec_34;
        end
    end
    assign in_chan_dep_vld_vec_34[0] = dep_chan_vld_31_34;
    assign in_chan_dep_data_vec_34[73 : 0] = dep_chan_data_31_34;
    assign token_in_vec_34[0] = token_31_34;
    assign in_chan_dep_vld_vec_34[1] = dep_chan_vld_36_34;
    assign in_chan_dep_data_vec_34[147 : 74] = dep_chan_data_36_34;
    assign token_in_vec_34[1] = token_36_34;
    assign in_chan_dep_vld_vec_34[2] = dep_chan_vld_37_34;
    assign in_chan_dep_data_vec_34[221 : 148] = dep_chan_data_37_34;
    assign token_in_vec_34[2] = token_37_34;
    assign in_chan_dep_vld_vec_34[3] = dep_chan_vld_38_34;
    assign in_chan_dep_data_vec_34[295 : 222] = dep_chan_data_38_34;
    assign token_in_vec_34[3] = token_38_34;
    assign dep_chan_vld_34_31 = out_chan_dep_vld_vec_34[0];
    assign dep_chan_data_34_31 = out_chan_dep_data_34;
    assign token_34_31 = token_out_vec_34[0];
    assign dep_chan_vld_34_36 = out_chan_dep_vld_vec_34[1];
    assign dep_chan_data_34_36 = out_chan_dep_data_34;
    assign token_34_36 = token_out_vec_34[1];
    assign dep_chan_vld_34_37 = out_chan_dep_vld_vec_34[2];
    assign dep_chan_data_34_37 = out_chan_dep_data_34;
    assign token_34_37 = token_out_vec_34[2];
    assign dep_chan_vld_34_38 = out_chan_dep_vld_vec_34[3];
    assign dep_chan_data_34_38 = out_chan_dep_data_34;
    assign token_34_38 = token_out_vec_34[3];

    // Process: grp_dataflow_wrapper_fu_6443.task_compute_attn_U0.grp_do_attn_1_fu_5150.do_split_U0
    vit_block_top_hls_deadlock_detect_unit #(74, 35, 4, 4) vit_block_top_hls_deadlock_detect_unit_35 (
        .reset(dl_reset),
        .clock(dl_clock),
        .proc_dep_vld_vec(proc_dep_vld_vec_35),
        .in_chan_dep_vld_vec(in_chan_dep_vld_vec_35),
        .in_chan_dep_data_vec(in_chan_dep_data_vec_35),
        .token_in_vec(token_in_vec_35),
        .dl_detect_in(dl_detect_out),
        .origin(origin[35]),
        .token_clear(token_clear),
        .out_chan_dep_vld_vec(out_chan_dep_vld_vec_35),
        .out_chan_dep_data(out_chan_dep_data_35),
        .token_out_vec(token_out_vec_35),
        .dl_detect_out(dl_in_vec[35]));

    assign proc_35_data_FIFO_blk[0] = 1'b0 | (~grp_dataflow_wrapper_fu_6443.task_compute_attn_U0.grp_do_attn_1_fu_5150.do_split_U0.vq_sm_blk_n);
    assign proc_35_data_PIPO_blk[0] = 1'b0;
    assign proc_35_start_FIFO_blk[0] = 1'b0 | (~grp_dataflow_wrapper_fu_6443.task_compute_attn_U0.grp_do_attn_1_fu_5150.start_for_do_split_U0_U.if_empty_n & grp_dataflow_wrapper_fu_6443.task_compute_attn_U0.grp_do_attn_1_fu_5150.do_split_U0.ap_idle & ~grp_dataflow_wrapper_fu_6443.task_compute_attn_U0.grp_do_attn_1_fu_5150.start_for_do_split_U0_U.if_write);
    assign proc_35_TLF_FIFO_blk[0] = 1'b0;
    assign proc_35_input_sync_blk[0] = 1'b0;
    assign proc_35_output_sync_blk[0] = 1'b0;
    assign proc_dep_vld_vec_35[0] = dl_detect_out ? proc_dep_vld_vec_35_reg[0] : (proc_35_data_FIFO_blk[0] | proc_35_data_PIPO_blk[0] | proc_35_start_FIFO_blk[0] | proc_35_TLF_FIFO_blk[0] | proc_35_input_sync_blk[0] | proc_35_output_sync_blk[0]);
    assign proc_35_data_FIFO_blk[1] = 1'b0 | (~grp_dataflow_wrapper_fu_6443.task_compute_attn_U0.grp_do_attn_1_fu_5150.do_split_U0.vq_sm_head_0_blk_n);
    assign proc_35_data_PIPO_blk[1] = 1'b0;
    assign proc_35_start_FIFO_blk[1] = 1'b0;
    assign proc_35_TLF_FIFO_blk[1] = 1'b0;
    assign proc_35_input_sync_blk[1] = 1'b0;
    assign proc_35_output_sync_blk[1] = 1'b0;
    assign proc_dep_vld_vec_35[1] = dl_detect_out ? proc_dep_vld_vec_35_reg[1] : (proc_35_data_FIFO_blk[1] | proc_35_data_PIPO_blk[1] | proc_35_start_FIFO_blk[1] | proc_35_TLF_FIFO_blk[1] | proc_35_input_sync_blk[1] | proc_35_output_sync_blk[1]);
    assign proc_35_data_FIFO_blk[2] = 1'b0 | (~grp_dataflow_wrapper_fu_6443.task_compute_attn_U0.grp_do_attn_1_fu_5150.do_split_U0.vq_sm_head_1_blk_n);
    assign proc_35_data_PIPO_blk[2] = 1'b0;
    assign proc_35_start_FIFO_blk[2] = 1'b0;
    assign proc_35_TLF_FIFO_blk[2] = 1'b0;
    assign proc_35_input_sync_blk[2] = 1'b0;
    assign proc_35_output_sync_blk[2] = 1'b0;
    assign proc_dep_vld_vec_35[2] = dl_detect_out ? proc_dep_vld_vec_35_reg[2] : (proc_35_data_FIFO_blk[2] | proc_35_data_PIPO_blk[2] | proc_35_start_FIFO_blk[2] | proc_35_TLF_FIFO_blk[2] | proc_35_input_sync_blk[2] | proc_35_output_sync_blk[2]);
    assign proc_35_data_FIFO_blk[3] = 1'b0 | (~grp_dataflow_wrapper_fu_6443.task_compute_attn_U0.grp_do_attn_1_fu_5150.do_split_U0.vq_sm_head_2_blk_n);
    assign proc_35_data_PIPO_blk[3] = 1'b0;
    assign proc_35_start_FIFO_blk[3] = 1'b0;
    assign proc_35_TLF_FIFO_blk[3] = 1'b0;
    assign proc_35_input_sync_blk[3] = 1'b0;
    assign proc_35_output_sync_blk[3] = 1'b0;
    assign proc_dep_vld_vec_35[3] = dl_detect_out ? proc_dep_vld_vec_35_reg[3] : (proc_35_data_FIFO_blk[3] | proc_35_data_PIPO_blk[3] | proc_35_start_FIFO_blk[3] | proc_35_TLF_FIFO_blk[3] | proc_35_input_sync_blk[3] | proc_35_output_sync_blk[3]);
    always @ (negedge dl_reset or posedge dl_clock) begin
        if (~dl_reset) begin
            proc_dep_vld_vec_35_reg <= 'b0;
        end
        else begin
            proc_dep_vld_vec_35_reg <= proc_dep_vld_vec_35;
        end
    end
    assign in_chan_dep_vld_vec_35[0] = dep_chan_vld_32_35;
    assign in_chan_dep_data_vec_35[73 : 0] = dep_chan_data_32_35;
    assign token_in_vec_35[0] = token_32_35;
    assign in_chan_dep_vld_vec_35[1] = dep_chan_vld_36_35;
    assign in_chan_dep_data_vec_35[147 : 74] = dep_chan_data_36_35;
    assign token_in_vec_35[1] = token_36_35;
    assign in_chan_dep_vld_vec_35[2] = dep_chan_vld_37_35;
    assign in_chan_dep_data_vec_35[221 : 148] = dep_chan_data_37_35;
    assign token_in_vec_35[2] = token_37_35;
    assign in_chan_dep_vld_vec_35[3] = dep_chan_vld_38_35;
    assign in_chan_dep_data_vec_35[295 : 222] = dep_chan_data_38_35;
    assign token_in_vec_35[3] = token_38_35;
    assign dep_chan_vld_35_32 = out_chan_dep_vld_vec_35[0];
    assign dep_chan_data_35_32 = out_chan_dep_data_35;
    assign token_35_32 = token_out_vec_35[0];
    assign dep_chan_vld_35_36 = out_chan_dep_vld_vec_35[1];
    assign dep_chan_data_35_36 = out_chan_dep_data_35;
    assign token_35_36 = token_out_vec_35[1];
    assign dep_chan_vld_35_37 = out_chan_dep_vld_vec_35[2];
    assign dep_chan_data_35_37 = out_chan_dep_data_35;
    assign token_35_37 = token_out_vec_35[2];
    assign dep_chan_vld_35_38 = out_chan_dep_vld_vec_35[3];
    assign dep_chan_data_35_38 = out_chan_dep_data_35;
    assign token_35_38 = token_out_vec_35[3];

    // Process: grp_dataflow_wrapper_fu_6443.task_compute_attn_U0.grp_do_attn_1_fu_5150.do_attn_6_U0
    vit_block_top_hls_deadlock_detect_unit #(74, 36, 4, 4) vit_block_top_hls_deadlock_detect_unit_36 (
        .reset(dl_reset),
        .clock(dl_clock),
        .proc_dep_vld_vec(proc_dep_vld_vec_36),
        .in_chan_dep_vld_vec(in_chan_dep_vld_vec_36),
        .in_chan_dep_data_vec(in_chan_dep_data_vec_36),
        .token_in_vec(token_in_vec_36),
        .dl_detect_in(dl_detect_out),
        .origin(origin[36]),
        .token_clear(token_clear),
        .out_chan_dep_vld_vec(out_chan_dep_vld_vec_36),
        .out_chan_dep_data(out_chan_dep_data_36),
        .token_out_vec(token_out_vec_36),
        .dl_detect_out(dl_in_vec[36]));

    assign proc_36_data_FIFO_blk[0] = 1'b0 | (~grp_dataflow_wrapper_fu_6443.task_compute_attn_U0.grp_do_attn_1_fu_5150.do_attn_6_U0.grp_do_attn_6_Pipeline_LOAD_LOOP_VITIS_LOOP_65_1_fu_1073.qq_sm_head_0_blk_n);
    assign proc_36_data_PIPO_blk[0] = 1'b0;
    assign proc_36_start_FIFO_blk[0] = 1'b0 | (~grp_dataflow_wrapper_fu_6443.task_compute_attn_U0.grp_do_attn_1_fu_5150.start_for_do_attn_6_U0_U.if_empty_n & grp_dataflow_wrapper_fu_6443.task_compute_attn_U0.grp_do_attn_1_fu_5150.do_attn_6_U0.ap_idle & ~grp_dataflow_wrapper_fu_6443.task_compute_attn_U0.grp_do_attn_1_fu_5150.start_for_do_attn_6_U0_U.if_write);
    assign proc_36_TLF_FIFO_blk[0] = 1'b0;
    assign proc_36_input_sync_blk[0] = 1'b0;
    assign proc_36_output_sync_blk[0] = 1'b0;
    assign proc_dep_vld_vec_36[0] = dl_detect_out ? proc_dep_vld_vec_36_reg[0] : (proc_36_data_FIFO_blk[0] | proc_36_data_PIPO_blk[0] | proc_36_start_FIFO_blk[0] | proc_36_TLF_FIFO_blk[0] | proc_36_input_sync_blk[0] | proc_36_output_sync_blk[0]);
    assign proc_36_data_FIFO_blk[1] = 1'b0 | (~grp_dataflow_wrapper_fu_6443.task_compute_attn_U0.grp_do_attn_1_fu_5150.do_attn_6_U0.grp_do_attn_6_Pipeline_LOAD_LOOP_VITIS_LOOP_65_1_fu_1073.kq_sm_head_0_blk_n);
    assign proc_36_data_PIPO_blk[1] = 1'b0;
    assign proc_36_start_FIFO_blk[1] = 1'b0;
    assign proc_36_TLF_FIFO_blk[1] = 1'b0;
    assign proc_36_input_sync_blk[1] = 1'b0;
    assign proc_36_output_sync_blk[1] = 1'b0;
    assign proc_dep_vld_vec_36[1] = dl_detect_out ? proc_dep_vld_vec_36_reg[1] : (proc_36_data_FIFO_blk[1] | proc_36_data_PIPO_blk[1] | proc_36_start_FIFO_blk[1] | proc_36_TLF_FIFO_blk[1] | proc_36_input_sync_blk[1] | proc_36_output_sync_blk[1]);
    assign proc_36_data_FIFO_blk[2] = 1'b0 | (~grp_dataflow_wrapper_fu_6443.task_compute_attn_U0.grp_do_attn_1_fu_5150.do_attn_6_U0.grp_do_attn_6_Pipeline_LOAD_LOOP_VITIS_LOOP_65_1_fu_1073.vq_sm_head_0_blk_n);
    assign proc_36_data_PIPO_blk[2] = 1'b0;
    assign proc_36_start_FIFO_blk[2] = 1'b0;
    assign proc_36_TLF_FIFO_blk[2] = 1'b0;
    assign proc_36_input_sync_blk[2] = 1'b0;
    assign proc_36_output_sync_blk[2] = 1'b0;
    assign proc_dep_vld_vec_36[2] = dl_detect_out ? proc_dep_vld_vec_36_reg[2] : (proc_36_data_FIFO_blk[2] | proc_36_data_PIPO_blk[2] | proc_36_start_FIFO_blk[2] | proc_36_TLF_FIFO_blk[2] | proc_36_input_sync_blk[2] | proc_36_output_sync_blk[2]);
    assign proc_36_data_FIFO_blk[3] = 1'b0 | (~grp_dataflow_wrapper_fu_6443.task_compute_attn_U0.grp_do_attn_1_fu_5150.do_attn_6_U0.grp_do_attn_6_Pipeline_WRITE_CT_LOOP_fu_1476.a_sm_head_0_blk_n);
    assign proc_36_data_PIPO_blk[3] = 1'b0;
    assign proc_36_start_FIFO_blk[3] = 1'b0 | (~grp_dataflow_wrapper_fu_6443.task_compute_attn_U0.grp_do_attn_1_fu_5150.start_for_do_merge_U0_U.if_full_n & grp_dataflow_wrapper_fu_6443.task_compute_attn_U0.grp_do_attn_1_fu_5150.do_attn_6_U0.ap_start & ~grp_dataflow_wrapper_fu_6443.task_compute_attn_U0.grp_do_attn_1_fu_5150.do_attn_6_U0.real_start & (trans_in_cnt_23 == trans_out_cnt_23) & ~grp_dataflow_wrapper_fu_6443.task_compute_attn_U0.grp_do_attn_1_fu_5150.start_for_do_merge_U0_U.if_read);
    assign proc_36_TLF_FIFO_blk[3] = 1'b0;
    assign proc_36_input_sync_blk[3] = 1'b0;
    assign proc_36_output_sync_blk[3] = 1'b0;
    assign proc_dep_vld_vec_36[3] = dl_detect_out ? proc_dep_vld_vec_36_reg[3] : (proc_36_data_FIFO_blk[3] | proc_36_data_PIPO_blk[3] | proc_36_start_FIFO_blk[3] | proc_36_TLF_FIFO_blk[3] | proc_36_input_sync_blk[3] | proc_36_output_sync_blk[3]);
    always @ (negedge dl_reset or posedge dl_clock) begin
        if (~dl_reset) begin
            proc_dep_vld_vec_36_reg <= 'b0;
        end
        else begin
            proc_dep_vld_vec_36_reg <= proc_dep_vld_vec_36;
        end
    end
    assign in_chan_dep_vld_vec_36[0] = dep_chan_vld_33_36;
    assign in_chan_dep_data_vec_36[73 : 0] = dep_chan_data_33_36;
    assign token_in_vec_36[0] = token_33_36;
    assign in_chan_dep_vld_vec_36[1] = dep_chan_vld_34_36;
    assign in_chan_dep_data_vec_36[147 : 74] = dep_chan_data_34_36;
    assign token_in_vec_36[1] = token_34_36;
    assign in_chan_dep_vld_vec_36[2] = dep_chan_vld_35_36;
    assign in_chan_dep_data_vec_36[221 : 148] = dep_chan_data_35_36;
    assign token_in_vec_36[2] = token_35_36;
    assign in_chan_dep_vld_vec_36[3] = dep_chan_vld_39_36;
    assign in_chan_dep_data_vec_36[295 : 222] = dep_chan_data_39_36;
    assign token_in_vec_36[3] = token_39_36;
    assign dep_chan_vld_36_33 = out_chan_dep_vld_vec_36[0];
    assign dep_chan_data_36_33 = out_chan_dep_data_36;
    assign token_36_33 = token_out_vec_36[0];
    assign dep_chan_vld_36_34 = out_chan_dep_vld_vec_36[1];
    assign dep_chan_data_36_34 = out_chan_dep_data_36;
    assign token_36_34 = token_out_vec_36[1];
    assign dep_chan_vld_36_35 = out_chan_dep_vld_vec_36[2];
    assign dep_chan_data_36_35 = out_chan_dep_data_36;
    assign token_36_35 = token_out_vec_36[2];
    assign dep_chan_vld_36_39 = out_chan_dep_vld_vec_36[3];
    assign dep_chan_data_36_39 = out_chan_dep_data_36;
    assign token_36_39 = token_out_vec_36[3];

    // Process: grp_dataflow_wrapper_fu_6443.task_compute_attn_U0.grp_do_attn_1_fu_5150.do_attn_7_U0
    vit_block_top_hls_deadlock_detect_unit #(74, 37, 4, 4) vit_block_top_hls_deadlock_detect_unit_37 (
        .reset(dl_reset),
        .clock(dl_clock),
        .proc_dep_vld_vec(proc_dep_vld_vec_37),
        .in_chan_dep_vld_vec(in_chan_dep_vld_vec_37),
        .in_chan_dep_data_vec(in_chan_dep_data_vec_37),
        .token_in_vec(token_in_vec_37),
        .dl_detect_in(dl_detect_out),
        .origin(origin[37]),
        .token_clear(token_clear),
        .out_chan_dep_vld_vec(out_chan_dep_vld_vec_37),
        .out_chan_dep_data(out_chan_dep_data_37),
        .token_out_vec(token_out_vec_37),
        .dl_detect_out(dl_in_vec[37]));

    assign proc_37_data_FIFO_blk[0] = 1'b0 | (~grp_dataflow_wrapper_fu_6443.task_compute_attn_U0.grp_do_attn_1_fu_5150.do_attn_7_U0.grp_do_attn_7_Pipeline_LOAD_LOOP_VITIS_LOOP_65_1_fu_1073.qq_sm_head_1_blk_n);
    assign proc_37_data_PIPO_blk[0] = 1'b0;
    assign proc_37_start_FIFO_blk[0] = 1'b0 | (~grp_dataflow_wrapper_fu_6443.task_compute_attn_U0.grp_do_attn_1_fu_5150.start_for_do_attn_7_U0_U.if_empty_n & grp_dataflow_wrapper_fu_6443.task_compute_attn_U0.grp_do_attn_1_fu_5150.do_attn_7_U0.ap_idle & ~grp_dataflow_wrapper_fu_6443.task_compute_attn_U0.grp_do_attn_1_fu_5150.start_for_do_attn_7_U0_U.if_write);
    assign proc_37_TLF_FIFO_blk[0] = 1'b0;
    assign proc_37_input_sync_blk[0] = 1'b0;
    assign proc_37_output_sync_blk[0] = 1'b0;
    assign proc_dep_vld_vec_37[0] = dl_detect_out ? proc_dep_vld_vec_37_reg[0] : (proc_37_data_FIFO_blk[0] | proc_37_data_PIPO_blk[0] | proc_37_start_FIFO_blk[0] | proc_37_TLF_FIFO_blk[0] | proc_37_input_sync_blk[0] | proc_37_output_sync_blk[0]);
    assign proc_37_data_FIFO_blk[1] = 1'b0 | (~grp_dataflow_wrapper_fu_6443.task_compute_attn_U0.grp_do_attn_1_fu_5150.do_attn_7_U0.grp_do_attn_7_Pipeline_LOAD_LOOP_VITIS_LOOP_65_1_fu_1073.kq_sm_head_1_blk_n);
    assign proc_37_data_PIPO_blk[1] = 1'b0;
    assign proc_37_start_FIFO_blk[1] = 1'b0;
    assign proc_37_TLF_FIFO_blk[1] = 1'b0;
    assign proc_37_input_sync_blk[1] = 1'b0;
    assign proc_37_output_sync_blk[1] = 1'b0;
    assign proc_dep_vld_vec_37[1] = dl_detect_out ? proc_dep_vld_vec_37_reg[1] : (proc_37_data_FIFO_blk[1] | proc_37_data_PIPO_blk[1] | proc_37_start_FIFO_blk[1] | proc_37_TLF_FIFO_blk[1] | proc_37_input_sync_blk[1] | proc_37_output_sync_blk[1]);
    assign proc_37_data_FIFO_blk[2] = 1'b0 | (~grp_dataflow_wrapper_fu_6443.task_compute_attn_U0.grp_do_attn_1_fu_5150.do_attn_7_U0.grp_do_attn_7_Pipeline_LOAD_LOOP_VITIS_LOOP_65_1_fu_1073.vq_sm_head_1_blk_n);
    assign proc_37_data_PIPO_blk[2] = 1'b0;
    assign proc_37_start_FIFO_blk[2] = 1'b0;
    assign proc_37_TLF_FIFO_blk[2] = 1'b0;
    assign proc_37_input_sync_blk[2] = 1'b0;
    assign proc_37_output_sync_blk[2] = 1'b0;
    assign proc_dep_vld_vec_37[2] = dl_detect_out ? proc_dep_vld_vec_37_reg[2] : (proc_37_data_FIFO_blk[2] | proc_37_data_PIPO_blk[2] | proc_37_start_FIFO_blk[2] | proc_37_TLF_FIFO_blk[2] | proc_37_input_sync_blk[2] | proc_37_output_sync_blk[2]);
    assign proc_37_data_FIFO_blk[3] = 1'b0 | (~grp_dataflow_wrapper_fu_6443.task_compute_attn_U0.grp_do_attn_1_fu_5150.do_attn_7_U0.grp_do_attn_7_Pipeline_WRITE_CT_LOOP_fu_1476.a_sm_head_1_blk_n);
    assign proc_37_data_PIPO_blk[3] = 1'b0;
    assign proc_37_start_FIFO_blk[3] = 1'b0;
    assign proc_37_TLF_FIFO_blk[3] = 1'b0;
    assign proc_37_input_sync_blk[3] = 1'b0;
    assign proc_37_output_sync_blk[3] = 1'b0;
    assign proc_dep_vld_vec_37[3] = dl_detect_out ? proc_dep_vld_vec_37_reg[3] : (proc_37_data_FIFO_blk[3] | proc_37_data_PIPO_blk[3] | proc_37_start_FIFO_blk[3] | proc_37_TLF_FIFO_blk[3] | proc_37_input_sync_blk[3] | proc_37_output_sync_blk[3]);
    always @ (negedge dl_reset or posedge dl_clock) begin
        if (~dl_reset) begin
            proc_dep_vld_vec_37_reg <= 'b0;
        end
        else begin
            proc_dep_vld_vec_37_reg <= proc_dep_vld_vec_37;
        end
    end
    assign in_chan_dep_vld_vec_37[0] = dep_chan_vld_33_37;
    assign in_chan_dep_data_vec_37[73 : 0] = dep_chan_data_33_37;
    assign token_in_vec_37[0] = token_33_37;
    assign in_chan_dep_vld_vec_37[1] = dep_chan_vld_34_37;
    assign in_chan_dep_data_vec_37[147 : 74] = dep_chan_data_34_37;
    assign token_in_vec_37[1] = token_34_37;
    assign in_chan_dep_vld_vec_37[2] = dep_chan_vld_35_37;
    assign in_chan_dep_data_vec_37[221 : 148] = dep_chan_data_35_37;
    assign token_in_vec_37[2] = token_35_37;
    assign in_chan_dep_vld_vec_37[3] = dep_chan_vld_39_37;
    assign in_chan_dep_data_vec_37[295 : 222] = dep_chan_data_39_37;
    assign token_in_vec_37[3] = token_39_37;
    assign dep_chan_vld_37_33 = out_chan_dep_vld_vec_37[0];
    assign dep_chan_data_37_33 = out_chan_dep_data_37;
    assign token_37_33 = token_out_vec_37[0];
    assign dep_chan_vld_37_34 = out_chan_dep_vld_vec_37[1];
    assign dep_chan_data_37_34 = out_chan_dep_data_37;
    assign token_37_34 = token_out_vec_37[1];
    assign dep_chan_vld_37_35 = out_chan_dep_vld_vec_37[2];
    assign dep_chan_data_37_35 = out_chan_dep_data_37;
    assign token_37_35 = token_out_vec_37[2];
    assign dep_chan_vld_37_39 = out_chan_dep_vld_vec_37[3];
    assign dep_chan_data_37_39 = out_chan_dep_data_37;
    assign token_37_39 = token_out_vec_37[3];

    // Process: grp_dataflow_wrapper_fu_6443.task_compute_attn_U0.grp_do_attn_1_fu_5150.do_attn_U0
    vit_block_top_hls_deadlock_detect_unit #(74, 38, 4, 4) vit_block_top_hls_deadlock_detect_unit_38 (
        .reset(dl_reset),
        .clock(dl_clock),
        .proc_dep_vld_vec(proc_dep_vld_vec_38),
        .in_chan_dep_vld_vec(in_chan_dep_vld_vec_38),
        .in_chan_dep_data_vec(in_chan_dep_data_vec_38),
        .token_in_vec(token_in_vec_38),
        .dl_detect_in(dl_detect_out),
        .origin(origin[38]),
        .token_clear(token_clear),
        .out_chan_dep_vld_vec(out_chan_dep_vld_vec_38),
        .out_chan_dep_data(out_chan_dep_data_38),
        .token_out_vec(token_out_vec_38),
        .dl_detect_out(dl_in_vec[38]));

    assign proc_38_data_FIFO_blk[0] = 1'b0 | (~grp_dataflow_wrapper_fu_6443.task_compute_attn_U0.grp_do_attn_1_fu_5150.do_attn_U0.grp_do_attn_Pipeline_LOAD_LOOP_VITIS_LOOP_65_1_fu_1073.qq_sm_head_2_blk_n);
    assign proc_38_data_PIPO_blk[0] = 1'b0;
    assign proc_38_start_FIFO_blk[0] = 1'b0 | (~grp_dataflow_wrapper_fu_6443.task_compute_attn_U0.grp_do_attn_1_fu_5150.start_for_do_attn_U0_U.if_empty_n & grp_dataflow_wrapper_fu_6443.task_compute_attn_U0.grp_do_attn_1_fu_5150.do_attn_U0.ap_idle & ~grp_dataflow_wrapper_fu_6443.task_compute_attn_U0.grp_do_attn_1_fu_5150.start_for_do_attn_U0_U.if_write);
    assign proc_38_TLF_FIFO_blk[0] = 1'b0;
    assign proc_38_input_sync_blk[0] = 1'b0;
    assign proc_38_output_sync_blk[0] = 1'b0;
    assign proc_dep_vld_vec_38[0] = dl_detect_out ? proc_dep_vld_vec_38_reg[0] : (proc_38_data_FIFO_blk[0] | proc_38_data_PIPO_blk[0] | proc_38_start_FIFO_blk[0] | proc_38_TLF_FIFO_blk[0] | proc_38_input_sync_blk[0] | proc_38_output_sync_blk[0]);
    assign proc_38_data_FIFO_blk[1] = 1'b0 | (~grp_dataflow_wrapper_fu_6443.task_compute_attn_U0.grp_do_attn_1_fu_5150.do_attn_U0.grp_do_attn_Pipeline_LOAD_LOOP_VITIS_LOOP_65_1_fu_1073.kq_sm_head_2_blk_n);
    assign proc_38_data_PIPO_blk[1] = 1'b0;
    assign proc_38_start_FIFO_blk[1] = 1'b0;
    assign proc_38_TLF_FIFO_blk[1] = 1'b0;
    assign proc_38_input_sync_blk[1] = 1'b0;
    assign proc_38_output_sync_blk[1] = 1'b0;
    assign proc_dep_vld_vec_38[1] = dl_detect_out ? proc_dep_vld_vec_38_reg[1] : (proc_38_data_FIFO_blk[1] | proc_38_data_PIPO_blk[1] | proc_38_start_FIFO_blk[1] | proc_38_TLF_FIFO_blk[1] | proc_38_input_sync_blk[1] | proc_38_output_sync_blk[1]);
    assign proc_38_data_FIFO_blk[2] = 1'b0 | (~grp_dataflow_wrapper_fu_6443.task_compute_attn_U0.grp_do_attn_1_fu_5150.do_attn_U0.grp_do_attn_Pipeline_LOAD_LOOP_VITIS_LOOP_65_1_fu_1073.vq_sm_head_2_blk_n);
    assign proc_38_data_PIPO_blk[2] = 1'b0;
    assign proc_38_start_FIFO_blk[2] = 1'b0;
    assign proc_38_TLF_FIFO_blk[2] = 1'b0;
    assign proc_38_input_sync_blk[2] = 1'b0;
    assign proc_38_output_sync_blk[2] = 1'b0;
    assign proc_dep_vld_vec_38[2] = dl_detect_out ? proc_dep_vld_vec_38_reg[2] : (proc_38_data_FIFO_blk[2] | proc_38_data_PIPO_blk[2] | proc_38_start_FIFO_blk[2] | proc_38_TLF_FIFO_blk[2] | proc_38_input_sync_blk[2] | proc_38_output_sync_blk[2]);
    assign proc_38_data_FIFO_blk[3] = 1'b0 | (~grp_dataflow_wrapper_fu_6443.task_compute_attn_U0.grp_do_attn_1_fu_5150.do_attn_U0.grp_do_attn_Pipeline_WRITE_CT_LOOP_fu_1476.a_sm_head_2_blk_n);
    assign proc_38_data_PIPO_blk[3] = 1'b0;
    assign proc_38_start_FIFO_blk[3] = 1'b0;
    assign proc_38_TLF_FIFO_blk[3] = 1'b0;
    assign proc_38_input_sync_blk[3] = 1'b0;
    assign proc_38_output_sync_blk[3] = 1'b0;
    assign proc_dep_vld_vec_38[3] = dl_detect_out ? proc_dep_vld_vec_38_reg[3] : (proc_38_data_FIFO_blk[3] | proc_38_data_PIPO_blk[3] | proc_38_start_FIFO_blk[3] | proc_38_TLF_FIFO_blk[3] | proc_38_input_sync_blk[3] | proc_38_output_sync_blk[3]);
    always @ (negedge dl_reset or posedge dl_clock) begin
        if (~dl_reset) begin
            proc_dep_vld_vec_38_reg <= 'b0;
        end
        else begin
            proc_dep_vld_vec_38_reg <= proc_dep_vld_vec_38;
        end
    end
    assign in_chan_dep_vld_vec_38[0] = dep_chan_vld_33_38;
    assign in_chan_dep_data_vec_38[73 : 0] = dep_chan_data_33_38;
    assign token_in_vec_38[0] = token_33_38;
    assign in_chan_dep_vld_vec_38[1] = dep_chan_vld_34_38;
    assign in_chan_dep_data_vec_38[147 : 74] = dep_chan_data_34_38;
    assign token_in_vec_38[1] = token_34_38;
    assign in_chan_dep_vld_vec_38[2] = dep_chan_vld_35_38;
    assign in_chan_dep_data_vec_38[221 : 148] = dep_chan_data_35_38;
    assign token_in_vec_38[2] = token_35_38;
    assign in_chan_dep_vld_vec_38[3] = dep_chan_vld_39_38;
    assign in_chan_dep_data_vec_38[295 : 222] = dep_chan_data_39_38;
    assign token_in_vec_38[3] = token_39_38;
    assign dep_chan_vld_38_33 = out_chan_dep_vld_vec_38[0];
    assign dep_chan_data_38_33 = out_chan_dep_data_38;
    assign token_38_33 = token_out_vec_38[0];
    assign dep_chan_vld_38_34 = out_chan_dep_vld_vec_38[1];
    assign dep_chan_data_38_34 = out_chan_dep_data_38;
    assign token_38_34 = token_out_vec_38[1];
    assign dep_chan_vld_38_35 = out_chan_dep_vld_vec_38[2];
    assign dep_chan_data_38_35 = out_chan_dep_data_38;
    assign token_38_35 = token_out_vec_38[2];
    assign dep_chan_vld_38_39 = out_chan_dep_vld_vec_38[3];
    assign dep_chan_data_38_39 = out_chan_dep_data_38;
    assign token_38_39 = token_out_vec_38[3];

    // Process: grp_dataflow_wrapper_fu_6443.task_compute_attn_U0.grp_do_attn_1_fu_5150.do_merge_U0
    vit_block_top_hls_deadlock_detect_unit #(74, 39, 4, 4) vit_block_top_hls_deadlock_detect_unit_39 (
        .reset(dl_reset),
        .clock(dl_clock),
        .proc_dep_vld_vec(proc_dep_vld_vec_39),
        .in_chan_dep_vld_vec(in_chan_dep_vld_vec_39),
        .in_chan_dep_data_vec(in_chan_dep_data_vec_39),
        .token_in_vec(token_in_vec_39),
        .dl_detect_in(dl_detect_out),
        .origin(origin[39]),
        .token_clear(token_clear),
        .out_chan_dep_vld_vec(out_chan_dep_vld_vec_39),
        .out_chan_dep_data(out_chan_dep_data_39),
        .token_out_vec(token_out_vec_39),
        .dl_detect_out(dl_in_vec[39]));

    assign proc_39_data_FIFO_blk[0] = 1'b0 | (~grp_dataflow_wrapper_fu_6443.task_compute_attn_U0.grp_do_attn_1_fu_5150.do_merge_U0.a_sm_head_0_blk_n);
    assign proc_39_data_PIPO_blk[0] = 1'b0;
    assign proc_39_start_FIFO_blk[0] = 1'b0 | (~grp_dataflow_wrapper_fu_6443.task_compute_attn_U0.grp_do_attn_1_fu_5150.start_for_do_merge_U0_U.if_empty_n & grp_dataflow_wrapper_fu_6443.task_compute_attn_U0.grp_do_attn_1_fu_5150.do_merge_U0.ap_idle & ~grp_dataflow_wrapper_fu_6443.task_compute_attn_U0.grp_do_attn_1_fu_5150.start_for_do_merge_U0_U.if_write);
    assign proc_39_TLF_FIFO_blk[0] = 1'b0;
    assign proc_39_input_sync_blk[0] = 1'b0;
    assign proc_39_output_sync_blk[0] = 1'b0;
    assign proc_dep_vld_vec_39[0] = dl_detect_out ? proc_dep_vld_vec_39_reg[0] : (proc_39_data_FIFO_blk[0] | proc_39_data_PIPO_blk[0] | proc_39_start_FIFO_blk[0] | proc_39_TLF_FIFO_blk[0] | proc_39_input_sync_blk[0] | proc_39_output_sync_blk[0]);
    assign proc_39_data_FIFO_blk[1] = 1'b0 | (~grp_dataflow_wrapper_fu_6443.task_compute_attn_U0.grp_do_attn_1_fu_5150.do_merge_U0.a_sm_head_1_blk_n);
    assign proc_39_data_PIPO_blk[1] = 1'b0;
    assign proc_39_start_FIFO_blk[1] = 1'b0;
    assign proc_39_TLF_FIFO_blk[1] = 1'b0;
    assign proc_39_input_sync_blk[1] = 1'b0;
    assign proc_39_output_sync_blk[1] = 1'b0;
    assign proc_dep_vld_vec_39[1] = dl_detect_out ? proc_dep_vld_vec_39_reg[1] : (proc_39_data_FIFO_blk[1] | proc_39_data_PIPO_blk[1] | proc_39_start_FIFO_blk[1] | proc_39_TLF_FIFO_blk[1] | proc_39_input_sync_blk[1] | proc_39_output_sync_blk[1]);
    assign proc_39_data_FIFO_blk[2] = 1'b0 | (~grp_dataflow_wrapper_fu_6443.task_compute_attn_U0.grp_do_attn_1_fu_5150.do_merge_U0.a_sm_head_2_blk_n);
    assign proc_39_data_PIPO_blk[2] = 1'b0;
    assign proc_39_start_FIFO_blk[2] = 1'b0;
    assign proc_39_TLF_FIFO_blk[2] = 1'b0;
    assign proc_39_input_sync_blk[2] = 1'b0;
    assign proc_39_output_sync_blk[2] = 1'b0;
    assign proc_dep_vld_vec_39[2] = dl_detect_out ? proc_dep_vld_vec_39_reg[2] : (proc_39_data_FIFO_blk[2] | proc_39_data_PIPO_blk[2] | proc_39_start_FIFO_blk[2] | proc_39_TLF_FIFO_blk[2] | proc_39_input_sync_blk[2] | proc_39_output_sync_blk[2]);
    assign proc_39_data_FIFO_blk[3] = 1'b0 | (~grp_dataflow_wrapper_fu_6443.task_compute_attn_U0.grp_do_attn_1_fu_5150.do_merge_U0.a_sm_blk_n);
    assign proc_39_data_PIPO_blk[3] = 1'b0;
    assign proc_39_start_FIFO_blk[3] = 1'b0 | (~grp_dataflow_wrapper_fu_6443.task_compute_attn_U0.grp_do_attn_1_fu_5150.start_for_do_quant_2_U0_U.if_full_n & grp_dataflow_wrapper_fu_6443.task_compute_attn_U0.grp_do_attn_1_fu_5150.do_merge_U0.ap_start & ~grp_dataflow_wrapper_fu_6443.task_compute_attn_U0.grp_do_attn_1_fu_5150.do_merge_U0.real_start & (trans_in_cnt_24 == trans_out_cnt_24) & ~grp_dataflow_wrapper_fu_6443.task_compute_attn_U0.grp_do_attn_1_fu_5150.start_for_do_quant_2_U0_U.if_read);
    assign proc_39_TLF_FIFO_blk[3] = 1'b0;
    assign proc_39_input_sync_blk[3] = 1'b0;
    assign proc_39_output_sync_blk[3] = 1'b0;
    assign proc_dep_vld_vec_39[3] = dl_detect_out ? proc_dep_vld_vec_39_reg[3] : (proc_39_data_FIFO_blk[3] | proc_39_data_PIPO_blk[3] | proc_39_start_FIFO_blk[3] | proc_39_TLF_FIFO_blk[3] | proc_39_input_sync_blk[3] | proc_39_output_sync_blk[3]);
    always @ (negedge dl_reset or posedge dl_clock) begin
        if (~dl_reset) begin
            proc_dep_vld_vec_39_reg <= 'b0;
        end
        else begin
            proc_dep_vld_vec_39_reg <= proc_dep_vld_vec_39;
        end
    end
    assign in_chan_dep_vld_vec_39[0] = dep_chan_vld_36_39;
    assign in_chan_dep_data_vec_39[73 : 0] = dep_chan_data_36_39;
    assign token_in_vec_39[0] = token_36_39;
    assign in_chan_dep_vld_vec_39[1] = dep_chan_vld_37_39;
    assign in_chan_dep_data_vec_39[147 : 74] = dep_chan_data_37_39;
    assign token_in_vec_39[1] = token_37_39;
    assign in_chan_dep_vld_vec_39[2] = dep_chan_vld_38_39;
    assign in_chan_dep_data_vec_39[221 : 148] = dep_chan_data_38_39;
    assign token_in_vec_39[2] = token_38_39;
    assign in_chan_dep_vld_vec_39[3] = dep_chan_vld_40_39;
    assign in_chan_dep_data_vec_39[295 : 222] = dep_chan_data_40_39;
    assign token_in_vec_39[3] = token_40_39;
    assign dep_chan_vld_39_36 = out_chan_dep_vld_vec_39[0];
    assign dep_chan_data_39_36 = out_chan_dep_data_39;
    assign token_39_36 = token_out_vec_39[0];
    assign dep_chan_vld_39_37 = out_chan_dep_vld_vec_39[1];
    assign dep_chan_data_39_37 = out_chan_dep_data_39;
    assign token_39_37 = token_out_vec_39[1];
    assign dep_chan_vld_39_38 = out_chan_dep_vld_vec_39[2];
    assign dep_chan_data_39_38 = out_chan_dep_data_39;
    assign token_39_38 = token_out_vec_39[2];
    assign dep_chan_vld_39_40 = out_chan_dep_vld_vec_39[3];
    assign dep_chan_data_39_40 = out_chan_dep_data_39;
    assign token_39_40 = token_out_vec_39[3];

    // Process: grp_dataflow_wrapper_fu_6443.task_compute_attn_U0.grp_do_attn_1_fu_5150.do_quant_2_U0
    vit_block_top_hls_deadlock_detect_unit #(74, 40, 3, 3) vit_block_top_hls_deadlock_detect_unit_40 (
        .reset(dl_reset),
        .clock(dl_clock),
        .proc_dep_vld_vec(proc_dep_vld_vec_40),
        .in_chan_dep_vld_vec(in_chan_dep_vld_vec_40),
        .in_chan_dep_data_vec(in_chan_dep_data_vec_40),
        .token_in_vec(token_in_vec_40),
        .dl_detect_in(dl_detect_out),
        .origin(origin[40]),
        .token_clear(token_clear),
        .out_chan_dep_vld_vec(out_chan_dep_vld_vec_40),
        .out_chan_dep_data(out_chan_dep_data_40),
        .token_out_vec(token_out_vec_40),
        .dl_detect_out(dl_in_vec[40]));

    assign proc_40_data_FIFO_blk[0] = 1'b0 | (~grp_dataflow_wrapper_fu_6443.task_compute_attn_U0.grp_do_attn_1_fu_5150.do_quant_2_U0.grp_do_quant_2_Pipeline_TT_LOOP_CT_LOOP_fu_82.a_sm_blk_n);
    assign proc_40_data_PIPO_blk[0] = 1'b0;
    assign proc_40_start_FIFO_blk[0] = 1'b0 | (~grp_dataflow_wrapper_fu_6443.task_compute_attn_U0.grp_do_attn_1_fu_5150.start_for_do_quant_2_U0_U.if_empty_n & grp_dataflow_wrapper_fu_6443.task_compute_attn_U0.grp_do_attn_1_fu_5150.do_quant_2_U0.ap_idle & ~grp_dataflow_wrapper_fu_6443.task_compute_attn_U0.grp_do_attn_1_fu_5150.start_for_do_quant_2_U0_U.if_write);
    assign proc_40_TLF_FIFO_blk[0] = 1'b0;
    assign proc_40_input_sync_blk[0] = 1'b0;
    assign proc_40_output_sync_blk[0] = 1'b0;
    assign proc_dep_vld_vec_40[0] = dl_detect_out ? proc_dep_vld_vec_40_reg[0] : (proc_40_data_FIFO_blk[0] | proc_40_data_PIPO_blk[0] | proc_40_start_FIFO_blk[0] | proc_40_TLF_FIFO_blk[0] | proc_40_input_sync_blk[0] | proc_40_output_sync_blk[0]);
    assign proc_40_data_FIFO_blk[1] = 1'b0 | (~grp_dataflow_wrapper_fu_6443.task_compute_attn_U0.grp_do_attn_1_fu_5150.do_quant_2_U0.grp_do_quant_2_Pipeline_TT_LOOP_CT_LOOP_fu_82.aq_sm_blk_n);
    assign proc_40_data_PIPO_blk[1] = 1'b0;
    assign proc_40_start_FIFO_blk[1] = 1'b0 | (~grp_dataflow_wrapper_fu_6443.task_compute_attn_U0.grp_do_attn_1_fu_5150.start_for_do_matmul_1_U0_U.if_full_n & grp_dataflow_wrapper_fu_6443.task_compute_attn_U0.grp_do_attn_1_fu_5150.do_quant_2_U0.ap_start & ~grp_dataflow_wrapper_fu_6443.task_compute_attn_U0.grp_do_attn_1_fu_5150.do_quant_2_U0.real_start & (trans_in_cnt_25 == trans_out_cnt_25) & ~grp_dataflow_wrapper_fu_6443.task_compute_attn_U0.grp_do_attn_1_fu_5150.start_for_do_matmul_1_U0_U.if_read);
    assign proc_40_TLF_FIFO_blk[1] = 1'b0;
    assign proc_40_input_sync_blk[1] = 1'b0;
    assign proc_40_output_sync_blk[1] = 1'b0;
    assign proc_dep_vld_vec_40[1] = dl_detect_out ? proc_dep_vld_vec_40_reg[1] : (proc_40_data_FIFO_blk[1] | proc_40_data_PIPO_blk[1] | proc_40_start_FIFO_blk[1] | proc_40_TLF_FIFO_blk[1] | proc_40_input_sync_blk[1] | proc_40_output_sync_blk[1]);
    assign proc_40_data_FIFO_blk[2] = 1'b0 | (~grp_dataflow_wrapper_fu_6443.task_compute_attn_U0.grp_do_attn_1_fu_5150.do_quant_2_U0.grp_do_quant_2_Pipeline_TT_LOOP_CT_LOOP_fu_82.aq_sm_blk_n);
    assign proc_40_data_PIPO_blk[2] = 1'b0;
    assign proc_40_start_FIFO_blk[2] = 1'b0;
    assign proc_40_TLF_FIFO_blk[2] = 1'b0;
    assign proc_40_input_sync_blk[2] = 1'b0;
    assign proc_40_output_sync_blk[2] = 1'b0;
    assign proc_dep_vld_vec_40[2] = dl_detect_out ? proc_dep_vld_vec_40_reg[2] : (proc_40_data_FIFO_blk[2] | proc_40_data_PIPO_blk[2] | proc_40_start_FIFO_blk[2] | proc_40_TLF_FIFO_blk[2] | proc_40_input_sync_blk[2] | proc_40_output_sync_blk[2]);
    always @ (negedge dl_reset or posedge dl_clock) begin
        if (~dl_reset) begin
            proc_dep_vld_vec_40_reg <= 'b0;
        end
        else begin
            proc_dep_vld_vec_40_reg <= proc_dep_vld_vec_40;
        end
    end
    assign in_chan_dep_vld_vec_40[0] = dep_chan_vld_39_40;
    assign in_chan_dep_data_vec_40[73 : 0] = dep_chan_data_39_40;
    assign token_in_vec_40[0] = token_39_40;
    assign in_chan_dep_vld_vec_40[1] = dep_chan_vld_41_40;
    assign in_chan_dep_data_vec_40[147 : 74] = dep_chan_data_41_40;
    assign token_in_vec_40[1] = token_41_40;
    assign in_chan_dep_vld_vec_40[2] = dep_chan_vld_42_40;
    assign in_chan_dep_data_vec_40[221 : 148] = dep_chan_data_42_40;
    assign token_in_vec_40[2] = token_42_40;
    assign dep_chan_vld_40_39 = out_chan_dep_vld_vec_40[0];
    assign dep_chan_data_40_39 = out_chan_dep_data_40;
    assign token_40_39 = token_out_vec_40[0];
    assign dep_chan_vld_40_41 = out_chan_dep_vld_vec_40[1];
    assign dep_chan_data_40_41 = out_chan_dep_data_40;
    assign token_40_41 = token_out_vec_40[1];
    assign dep_chan_vld_40_42 = out_chan_dep_vld_vec_40[2];
    assign dep_chan_data_40_42 = out_chan_dep_data_40;
    assign token_40_42 = token_out_vec_40[2];

    // Process: grp_dataflow_wrapper_fu_6443.task_compute_attn_U0.grp_do_attn_1_fu_5150.do_matmul_1_U0
    vit_block_top_hls_deadlock_detect_unit #(74, 41, 2, 2) vit_block_top_hls_deadlock_detect_unit_41 (
        .reset(dl_reset),
        .clock(dl_clock),
        .proc_dep_vld_vec(proc_dep_vld_vec_41),
        .in_chan_dep_vld_vec(in_chan_dep_vld_vec_41),
        .in_chan_dep_data_vec(in_chan_dep_data_vec_41),
        .token_in_vec(token_in_vec_41),
        .dl_detect_in(dl_detect_out),
        .origin(origin[41]),
        .token_clear(token_clear),
        .out_chan_dep_vld_vec(out_chan_dep_vld_vec_41),
        .out_chan_dep_data(out_chan_dep_data_41),
        .token_out_vec(token_out_vec_41),
        .dl_detect_out(dl_in_vec[41]));

    assign proc_41_data_FIFO_blk[0] = 1'b0 | (~grp_dataflow_wrapper_fu_6443.task_compute_attn_U0.grp_do_attn_1_fu_5150.do_matmul_1_U0.do_adapt_1_U0.aq_sm_blk_n);
    assign proc_41_data_PIPO_blk[0] = 1'b0;
    assign proc_41_start_FIFO_blk[0] = 1'b0 | (~grp_dataflow_wrapper_fu_6443.task_compute_attn_U0.grp_do_attn_1_fu_5150.start_for_do_matmul_1_U0_U.if_empty_n & grp_dataflow_wrapper_fu_6443.task_compute_attn_U0.grp_do_attn_1_fu_5150.do_matmul_1_U0.ap_idle & ~grp_dataflow_wrapper_fu_6443.task_compute_attn_U0.grp_do_attn_1_fu_5150.start_for_do_matmul_1_U0_U.if_write);
    assign proc_41_TLF_FIFO_blk[0] = 1'b0;
    assign proc_41_input_sync_blk[0] = 1'b0;
    assign proc_41_output_sync_blk[0] = 1'b0;
    assign proc_dep_vld_vec_41[0] = dl_detect_out ? proc_dep_vld_vec_41_reg[0] : (proc_41_data_FIFO_blk[0] | proc_41_data_PIPO_blk[0] | proc_41_start_FIFO_blk[0] | proc_41_TLF_FIFO_blk[0] | proc_41_input_sync_blk[0] | proc_41_output_sync_blk[0]);
    assign proc_41_data_FIFO_blk[1] = 1'b0 | (~grp_dataflow_wrapper_fu_6443.task_compute_attn_U0.grp_do_attn_1_fu_5150.do_matmul_1_U0.do_adapt_8_1_U0.o_sm_blk_n);
    assign proc_41_data_PIPO_blk[1] = 1'b0;
    assign proc_41_start_FIFO_blk[1] = 1'b0;
    assign proc_41_TLF_FIFO_blk[1] = 1'b0;
    assign proc_41_input_sync_blk[1] = 1'b0;
    assign proc_41_output_sync_blk[1] = 1'b0;
    assign proc_dep_vld_vec_41[1] = dl_detect_out ? proc_dep_vld_vec_41_reg[1] : (proc_41_data_FIFO_blk[1] | proc_41_data_PIPO_blk[1] | proc_41_start_FIFO_blk[1] | proc_41_TLF_FIFO_blk[1] | proc_41_input_sync_blk[1] | proc_41_output_sync_blk[1]);
    always @ (negedge dl_reset or posedge dl_clock) begin
        if (~dl_reset) begin
            proc_dep_vld_vec_41_reg <= 'b0;
        end
        else begin
            proc_dep_vld_vec_41_reg <= proc_dep_vld_vec_41;
        end
    end
    assign in_chan_dep_vld_vec_41[0] = dep_chan_vld_40_41;
    assign in_chan_dep_data_vec_41[73 : 0] = dep_chan_data_40_41;
    assign token_in_vec_41[0] = token_40_41;
    assign in_chan_dep_vld_vec_41[1] = dep_chan_vld_46_41;
    assign in_chan_dep_data_vec_41[147 : 74] = dep_chan_data_46_41;
    assign token_in_vec_41[1] = token_46_41;
    assign dep_chan_vld_41_40 = out_chan_dep_vld_vec_41[0];
    assign dep_chan_data_41_40 = out_chan_dep_data_41;
    assign token_41_40 = token_out_vec_41[0];
    assign dep_chan_vld_41_46 = out_chan_dep_vld_vec_41[1];
    assign dep_chan_data_41_46 = out_chan_dep_data_41;
    assign token_41_46 = token_out_vec_41[1];

    // Process: grp_dataflow_wrapper_fu_6443.task_compute_attn_U0.grp_do_attn_1_fu_5150.do_matmul_1_U0.do_adapt_1_U0
    vit_block_top_hls_deadlock_detect_unit #(74, 42, 2, 2) vit_block_top_hls_deadlock_detect_unit_42 (
        .reset(dl_reset),
        .clock(dl_clock),
        .proc_dep_vld_vec(proc_dep_vld_vec_42),
        .in_chan_dep_vld_vec(in_chan_dep_vld_vec_42),
        .in_chan_dep_data_vec(in_chan_dep_data_vec_42),
        .token_in_vec(token_in_vec_42),
        .dl_detect_in(dl_detect_out),
        .origin(origin[42]),
        .token_clear(token_clear),
        .out_chan_dep_vld_vec(out_chan_dep_vld_vec_42),
        .out_chan_dep_data(out_chan_dep_data_42),
        .token_out_vec(token_out_vec_42),
        .dl_detect_out(dl_in_vec[42]));

    assign proc_42_data_FIFO_blk[0] = 1'b0 | (~grp_dataflow_wrapper_fu_6443.task_compute_attn_U0.grp_do_attn_1_fu_5150.do_matmul_1_U0.do_adapt_1_U0.aq_sm_blk_n);
    assign proc_42_data_PIPO_blk[0] = 1'b0;
    assign proc_42_start_FIFO_blk[0] = 1'b0;
    assign proc_42_TLF_FIFO_blk[0] = 1'b0;
    assign proc_42_input_sync_blk[0] = 1'b0;
    assign proc_42_output_sync_blk[0] = 1'b0;
    assign proc_dep_vld_vec_42[0] = dl_detect_out ? proc_dep_vld_vec_42_reg[0] : (proc_42_data_FIFO_blk[0] | proc_42_data_PIPO_blk[0] | proc_42_start_FIFO_blk[0] | proc_42_TLF_FIFO_blk[0] | proc_42_input_sync_blk[0] | proc_42_output_sync_blk[0]);
    assign proc_42_data_FIFO_blk[1] = 1'b0 | (~grp_dataflow_wrapper_fu_6443.task_compute_attn_U0.grp_do_attn_1_fu_5150.do_matmul_1_U0.do_adapt_1_U0.adpt_sm_blk_n);
    assign proc_42_data_PIPO_blk[1] = 1'b0;
    assign proc_42_start_FIFO_blk[1] = 1'b0 | (~grp_dataflow_wrapper_fu_6443.task_compute_attn_U0.grp_do_attn_1_fu_5150.do_matmul_1_U0.start_for_matmul_step1_cache_window_1_U0_U.if_full_n & grp_dataflow_wrapper_fu_6443.task_compute_attn_U0.grp_do_attn_1_fu_5150.do_matmul_1_U0.do_adapt_1_U0.ap_start & ~grp_dataflow_wrapper_fu_6443.task_compute_attn_U0.grp_do_attn_1_fu_5150.do_matmul_1_U0.do_adapt_1_U0.real_start & (trans_in_cnt_26 == trans_out_cnt_26) & ~grp_dataflow_wrapper_fu_6443.task_compute_attn_U0.grp_do_attn_1_fu_5150.do_matmul_1_U0.start_for_matmul_step1_cache_window_1_U0_U.if_read);
    assign proc_42_TLF_FIFO_blk[1] = 1'b0;
    assign proc_42_input_sync_blk[1] = 1'b0;
    assign proc_42_output_sync_blk[1] = 1'b0;
    assign proc_dep_vld_vec_42[1] = dl_detect_out ? proc_dep_vld_vec_42_reg[1] : (proc_42_data_FIFO_blk[1] | proc_42_data_PIPO_blk[1] | proc_42_start_FIFO_blk[1] | proc_42_TLF_FIFO_blk[1] | proc_42_input_sync_blk[1] | proc_42_output_sync_blk[1]);
    always @ (negedge dl_reset or posedge dl_clock) begin
        if (~dl_reset) begin
            proc_dep_vld_vec_42_reg <= 'b0;
        end
        else begin
            proc_dep_vld_vec_42_reg <= proc_dep_vld_vec_42;
        end
    end
    assign in_chan_dep_vld_vec_42[0] = dep_chan_vld_40_42;
    assign in_chan_dep_data_vec_42[73 : 0] = dep_chan_data_40_42;
    assign token_in_vec_42[0] = token_40_42;
    assign in_chan_dep_vld_vec_42[1] = dep_chan_vld_43_42;
    assign in_chan_dep_data_vec_42[147 : 74] = dep_chan_data_43_42;
    assign token_in_vec_42[1] = token_43_42;
    assign dep_chan_vld_42_40 = out_chan_dep_vld_vec_42[0];
    assign dep_chan_data_42_40 = out_chan_dep_data_42;
    assign token_42_40 = token_out_vec_42[0];
    assign dep_chan_vld_42_43 = out_chan_dep_vld_vec_42[1];
    assign dep_chan_data_42_43 = out_chan_dep_data_42;
    assign token_42_43 = token_out_vec_42[1];

    // Process: grp_dataflow_wrapper_fu_6443.task_compute_attn_U0.grp_do_attn_1_fu_5150.do_matmul_1_U0.matmul_step1_cache_window_1_U0
    vit_block_top_hls_deadlock_detect_unit #(74, 43, 2, 2) vit_block_top_hls_deadlock_detect_unit_43 (
        .reset(dl_reset),
        .clock(dl_clock),
        .proc_dep_vld_vec(proc_dep_vld_vec_43),
        .in_chan_dep_vld_vec(in_chan_dep_vld_vec_43),
        .in_chan_dep_data_vec(in_chan_dep_data_vec_43),
        .token_in_vec(token_in_vec_43),
        .dl_detect_in(dl_detect_out),
        .origin(origin[43]),
        .token_clear(token_clear),
        .out_chan_dep_vld_vec(out_chan_dep_vld_vec_43),
        .out_chan_dep_data(out_chan_dep_data_43),
        .token_out_vec(token_out_vec_43),
        .dl_detect_out(dl_in_vec[43]));

    assign proc_43_data_FIFO_blk[0] = 1'b0 | (~grp_dataflow_wrapper_fu_6443.task_compute_attn_U0.grp_do_attn_1_fu_5150.do_matmul_1_U0.matmul_step1_cache_window_1_U0.adpt_sm_blk_n);
    assign proc_43_data_PIPO_blk[0] = 1'b0;
    assign proc_43_start_FIFO_blk[0] = 1'b0 | (~grp_dataflow_wrapper_fu_6443.task_compute_attn_U0.grp_do_attn_1_fu_5150.do_matmul_1_U0.start_for_matmul_step1_cache_window_1_U0_U.if_empty_n & grp_dataflow_wrapper_fu_6443.task_compute_attn_U0.grp_do_attn_1_fu_5150.do_matmul_1_U0.matmul_step1_cache_window_1_U0.ap_idle & ~grp_dataflow_wrapper_fu_6443.task_compute_attn_U0.grp_do_attn_1_fu_5150.do_matmul_1_U0.start_for_matmul_step1_cache_window_1_U0_U.if_write);
    assign proc_43_TLF_FIFO_blk[0] = 1'b0;
    assign proc_43_input_sync_blk[0] = 1'b0;
    assign proc_43_output_sync_blk[0] = 1'b0;
    assign proc_dep_vld_vec_43[0] = dl_detect_out ? proc_dep_vld_vec_43_reg[0] : (proc_43_data_FIFO_blk[0] | proc_43_data_PIPO_blk[0] | proc_43_start_FIFO_blk[0] | proc_43_TLF_FIFO_blk[0] | proc_43_input_sync_blk[0] | proc_43_output_sync_blk[0]);
    assign proc_43_data_FIFO_blk[1] = 1'b0 | (~grp_dataflow_wrapper_fu_6443.task_compute_attn_U0.grp_do_attn_1_fu_5150.do_matmul_1_U0.matmul_step1_cache_window_1_U0.cache_window_sm_blk_n);
    assign proc_43_data_PIPO_blk[1] = 1'b0;
    assign proc_43_start_FIFO_blk[1] = 1'b0 | (~grp_dataflow_wrapper_fu_6443.task_compute_attn_U0.grp_do_attn_1_fu_5150.do_matmul_1_U0.start_for_matmul_step2_mac_1_U0_U.if_full_n & grp_dataflow_wrapper_fu_6443.task_compute_attn_U0.grp_do_attn_1_fu_5150.do_matmul_1_U0.matmul_step1_cache_window_1_U0.ap_start & ~grp_dataflow_wrapper_fu_6443.task_compute_attn_U0.grp_do_attn_1_fu_5150.do_matmul_1_U0.matmul_step1_cache_window_1_U0.real_start & (trans_in_cnt_27 == trans_out_cnt_27) & ~grp_dataflow_wrapper_fu_6443.task_compute_attn_U0.grp_do_attn_1_fu_5150.do_matmul_1_U0.start_for_matmul_step2_mac_1_U0_U.if_read);
    assign proc_43_TLF_FIFO_blk[1] = 1'b0;
    assign proc_43_input_sync_blk[1] = 1'b0;
    assign proc_43_output_sync_blk[1] = 1'b0;
    assign proc_dep_vld_vec_43[1] = dl_detect_out ? proc_dep_vld_vec_43_reg[1] : (proc_43_data_FIFO_blk[1] | proc_43_data_PIPO_blk[1] | proc_43_start_FIFO_blk[1] | proc_43_TLF_FIFO_blk[1] | proc_43_input_sync_blk[1] | proc_43_output_sync_blk[1]);
    always @ (negedge dl_reset or posedge dl_clock) begin
        if (~dl_reset) begin
            proc_dep_vld_vec_43_reg <= 'b0;
        end
        else begin
            proc_dep_vld_vec_43_reg <= proc_dep_vld_vec_43;
        end
    end
    assign in_chan_dep_vld_vec_43[0] = dep_chan_vld_42_43;
    assign in_chan_dep_data_vec_43[73 : 0] = dep_chan_data_42_43;
    assign token_in_vec_43[0] = token_42_43;
    assign in_chan_dep_vld_vec_43[1] = dep_chan_vld_44_43;
    assign in_chan_dep_data_vec_43[147 : 74] = dep_chan_data_44_43;
    assign token_in_vec_43[1] = token_44_43;
    assign dep_chan_vld_43_42 = out_chan_dep_vld_vec_43[0];
    assign dep_chan_data_43_42 = out_chan_dep_data_43;
    assign token_43_42 = token_out_vec_43[0];
    assign dep_chan_vld_43_44 = out_chan_dep_vld_vec_43[1];
    assign dep_chan_data_43_44 = out_chan_dep_data_43;
    assign token_43_44 = token_out_vec_43[1];

    // Process: grp_dataflow_wrapper_fu_6443.task_compute_attn_U0.grp_do_attn_1_fu_5150.do_matmul_1_U0.matmul_step2_mac_1_U0
    vit_block_top_hls_deadlock_detect_unit #(74, 44, 2, 2) vit_block_top_hls_deadlock_detect_unit_44 (
        .reset(dl_reset),
        .clock(dl_clock),
        .proc_dep_vld_vec(proc_dep_vld_vec_44),
        .in_chan_dep_vld_vec(in_chan_dep_vld_vec_44),
        .in_chan_dep_data_vec(in_chan_dep_data_vec_44),
        .token_in_vec(token_in_vec_44),
        .dl_detect_in(dl_detect_out),
        .origin(origin[44]),
        .token_clear(token_clear),
        .out_chan_dep_vld_vec(out_chan_dep_vld_vec_44),
        .out_chan_dep_data(out_chan_dep_data_44),
        .token_out_vec(token_out_vec_44),
        .dl_detect_out(dl_in_vec[44]));

    assign proc_44_data_FIFO_blk[0] = 1'b0 | (~grp_dataflow_wrapper_fu_6443.task_compute_attn_U0.grp_do_attn_1_fu_5150.do_matmul_1_U0.matmul_step2_mac_1_U0.cache_window_sm_blk_n);
    assign proc_44_data_PIPO_blk[0] = 1'b0;
    assign proc_44_start_FIFO_blk[0] = 1'b0 | (~grp_dataflow_wrapper_fu_6443.task_compute_attn_U0.grp_do_attn_1_fu_5150.do_matmul_1_U0.start_for_matmul_step2_mac_1_U0_U.if_empty_n & grp_dataflow_wrapper_fu_6443.task_compute_attn_U0.grp_do_attn_1_fu_5150.do_matmul_1_U0.matmul_step2_mac_1_U0.ap_idle & ~grp_dataflow_wrapper_fu_6443.task_compute_attn_U0.grp_do_attn_1_fu_5150.do_matmul_1_U0.start_for_matmul_step2_mac_1_U0_U.if_write);
    assign proc_44_TLF_FIFO_blk[0] = 1'b0;
    assign proc_44_input_sync_blk[0] = 1'b0;
    assign proc_44_output_sync_blk[0] = 1'b0;
    assign proc_dep_vld_vec_44[0] = dl_detect_out ? proc_dep_vld_vec_44_reg[0] : (proc_44_data_FIFO_blk[0] | proc_44_data_PIPO_blk[0] | proc_44_start_FIFO_blk[0] | proc_44_TLF_FIFO_blk[0] | proc_44_input_sync_blk[0] | proc_44_output_sync_blk[0]);
    assign proc_44_data_FIFO_blk[1] = 1'b0 | (~grp_dataflow_wrapper_fu_6443.task_compute_attn_U0.grp_do_attn_1_fu_5150.do_matmul_1_U0.matmul_step2_mac_1_U0.mac_sm_blk_n);
    assign proc_44_data_PIPO_blk[1] = 1'b0;
    assign proc_44_start_FIFO_blk[1] = 1'b0 | (~grp_dataflow_wrapper_fu_6443.task_compute_attn_U0.grp_do_attn_1_fu_5150.do_matmul_1_U0.start_for_do_adapt_8_1_U0_U.if_full_n & grp_dataflow_wrapper_fu_6443.task_compute_attn_U0.grp_do_attn_1_fu_5150.do_matmul_1_U0.matmul_step2_mac_1_U0.ap_start & ~grp_dataflow_wrapper_fu_6443.task_compute_attn_U0.grp_do_attn_1_fu_5150.do_matmul_1_U0.matmul_step2_mac_1_U0.real_start & (trans_in_cnt_28 == trans_out_cnt_28) & ~grp_dataflow_wrapper_fu_6443.task_compute_attn_U0.grp_do_attn_1_fu_5150.do_matmul_1_U0.start_for_do_adapt_8_1_U0_U.if_read);
    assign proc_44_TLF_FIFO_blk[1] = 1'b0;
    assign proc_44_input_sync_blk[1] = 1'b0;
    assign proc_44_output_sync_blk[1] = 1'b0;
    assign proc_dep_vld_vec_44[1] = dl_detect_out ? proc_dep_vld_vec_44_reg[1] : (proc_44_data_FIFO_blk[1] | proc_44_data_PIPO_blk[1] | proc_44_start_FIFO_blk[1] | proc_44_TLF_FIFO_blk[1] | proc_44_input_sync_blk[1] | proc_44_output_sync_blk[1]);
    always @ (negedge dl_reset or posedge dl_clock) begin
        if (~dl_reset) begin
            proc_dep_vld_vec_44_reg <= 'b0;
        end
        else begin
            proc_dep_vld_vec_44_reg <= proc_dep_vld_vec_44;
        end
    end
    assign in_chan_dep_vld_vec_44[0] = dep_chan_vld_43_44;
    assign in_chan_dep_data_vec_44[73 : 0] = dep_chan_data_43_44;
    assign token_in_vec_44[0] = token_43_44;
    assign in_chan_dep_vld_vec_44[1] = dep_chan_vld_45_44;
    assign in_chan_dep_data_vec_44[147 : 74] = dep_chan_data_45_44;
    assign token_in_vec_44[1] = token_45_44;
    assign dep_chan_vld_44_43 = out_chan_dep_vld_vec_44[0];
    assign dep_chan_data_44_43 = out_chan_dep_data_44;
    assign token_44_43 = token_out_vec_44[0];
    assign dep_chan_vld_44_45 = out_chan_dep_vld_vec_44[1];
    assign dep_chan_data_44_45 = out_chan_dep_data_44;
    assign token_44_45 = token_out_vec_44[1];

    // Process: grp_dataflow_wrapper_fu_6443.task_compute_attn_U0.grp_do_attn_1_fu_5150.do_matmul_1_U0.do_adapt_8_1_U0
    vit_block_top_hls_deadlock_detect_unit #(74, 45, 2, 2) vit_block_top_hls_deadlock_detect_unit_45 (
        .reset(dl_reset),
        .clock(dl_clock),
        .proc_dep_vld_vec(proc_dep_vld_vec_45),
        .in_chan_dep_vld_vec(in_chan_dep_vld_vec_45),
        .in_chan_dep_data_vec(in_chan_dep_data_vec_45),
        .token_in_vec(token_in_vec_45),
        .dl_detect_in(dl_detect_out),
        .origin(origin[45]),
        .token_clear(token_clear),
        .out_chan_dep_vld_vec(out_chan_dep_vld_vec_45),
        .out_chan_dep_data(out_chan_dep_data_45),
        .token_out_vec(token_out_vec_45),
        .dl_detect_out(dl_in_vec[45]));

    assign proc_45_data_FIFO_blk[0] = 1'b0 | (~grp_dataflow_wrapper_fu_6443.task_compute_attn_U0.grp_do_attn_1_fu_5150.do_matmul_1_U0.do_adapt_8_1_U0.mac_sm_blk_n);
    assign proc_45_data_PIPO_blk[0] = 1'b0;
    assign proc_45_start_FIFO_blk[0] = 1'b0 | (~grp_dataflow_wrapper_fu_6443.task_compute_attn_U0.grp_do_attn_1_fu_5150.do_matmul_1_U0.start_for_do_adapt_8_1_U0_U.if_empty_n & grp_dataflow_wrapper_fu_6443.task_compute_attn_U0.grp_do_attn_1_fu_5150.do_matmul_1_U0.do_adapt_8_1_U0.ap_idle & ~grp_dataflow_wrapper_fu_6443.task_compute_attn_U0.grp_do_attn_1_fu_5150.do_matmul_1_U0.start_for_do_adapt_8_1_U0_U.if_write);
    assign proc_45_TLF_FIFO_blk[0] = 1'b0;
    assign proc_45_input_sync_blk[0] = 1'b0;
    assign proc_45_output_sync_blk[0] = 1'b0;
    assign proc_dep_vld_vec_45[0] = dl_detect_out ? proc_dep_vld_vec_45_reg[0] : (proc_45_data_FIFO_blk[0] | proc_45_data_PIPO_blk[0] | proc_45_start_FIFO_blk[0] | proc_45_TLF_FIFO_blk[0] | proc_45_input_sync_blk[0] | proc_45_output_sync_blk[0]);
    assign proc_45_data_FIFO_blk[1] = 1'b0 | (~grp_dataflow_wrapper_fu_6443.task_compute_attn_U0.grp_do_attn_1_fu_5150.do_matmul_1_U0.do_adapt_8_1_U0.o_sm_blk_n);
    assign proc_45_data_PIPO_blk[1] = 1'b0;
    assign proc_45_start_FIFO_blk[1] = 1'b0;
    assign proc_45_TLF_FIFO_blk[1] = 1'b0;
    assign proc_45_input_sync_blk[1] = 1'b0;
    assign proc_45_output_sync_blk[1] = 1'b0;
    assign proc_dep_vld_vec_45[1] = dl_detect_out ? proc_dep_vld_vec_45_reg[1] : (proc_45_data_FIFO_blk[1] | proc_45_data_PIPO_blk[1] | proc_45_start_FIFO_blk[1] | proc_45_TLF_FIFO_blk[1] | proc_45_input_sync_blk[1] | proc_45_output_sync_blk[1]);
    always @ (negedge dl_reset or posedge dl_clock) begin
        if (~dl_reset) begin
            proc_dep_vld_vec_45_reg <= 'b0;
        end
        else begin
            proc_dep_vld_vec_45_reg <= proc_dep_vld_vec_45;
        end
    end
    assign in_chan_dep_vld_vec_45[0] = dep_chan_vld_44_45;
    assign in_chan_dep_data_vec_45[73 : 0] = dep_chan_data_44_45;
    assign token_in_vec_45[0] = token_44_45;
    assign in_chan_dep_vld_vec_45[1] = dep_chan_vld_46_45;
    assign in_chan_dep_data_vec_45[147 : 74] = dep_chan_data_46_45;
    assign token_in_vec_45[1] = token_46_45;
    assign dep_chan_vld_45_44 = out_chan_dep_vld_vec_45[0];
    assign dep_chan_data_45_44 = out_chan_dep_data_45;
    assign token_45_44 = token_out_vec_45[0];
    assign dep_chan_vld_45_46 = out_chan_dep_vld_vec_45[1];
    assign dep_chan_data_45_46 = out_chan_dep_data_45;
    assign token_45_46 = token_out_vec_45[1];

    // Process: grp_dataflow_wrapper_fu_6443.task_compute_attn_U0.grp_do_attn_1_fu_5150.stream_merge_1_U0
    vit_block_top_hls_deadlock_detect_unit #(74, 46, 3, 3) vit_block_top_hls_deadlock_detect_unit_46 (
        .reset(dl_reset),
        .clock(dl_clock),
        .proc_dep_vld_vec(proc_dep_vld_vec_46),
        .in_chan_dep_vld_vec(in_chan_dep_vld_vec_46),
        .in_chan_dep_data_vec(in_chan_dep_data_vec_46),
        .token_in_vec(token_in_vec_46),
        .dl_detect_in(dl_detect_out),
        .origin(origin[46]),
        .token_clear(token_clear),
        .out_chan_dep_vld_vec(out_chan_dep_vld_vec_46),
        .out_chan_dep_data(out_chan_dep_data_46),
        .token_out_vec(token_out_vec_46),
        .dl_detect_out(dl_in_vec[46]));

    assign proc_46_data_FIFO_blk[0] = 1'b0 | (~grp_dataflow_wrapper_fu_6443.task_compute_attn_U0.grp_do_attn_1_fu_5150.stream_merge_1_U0.grp_stream_merge_1_Pipeline_VITIS_LOOP_554_1_VITIS_LOOP_555_2_fu_34.resi_o_sm_blk_n);
    assign proc_46_data_PIPO_blk[0] = 1'b0;
    assign proc_46_start_FIFO_blk[0] = 1'b0 | (~grp_dataflow_wrapper_fu_6443.task_compute_attn_U0.grp_do_attn_1_fu_5150.start_for_stream_merge_1_U0_U.if_empty_n & grp_dataflow_wrapper_fu_6443.task_compute_attn_U0.grp_do_attn_1_fu_5150.stream_merge_1_U0.ap_idle & ~grp_dataflow_wrapper_fu_6443.task_compute_attn_U0.grp_do_attn_1_fu_5150.start_for_stream_merge_1_U0_U.if_write);
    assign proc_46_TLF_FIFO_blk[0] = 1'b0;
    assign proc_46_input_sync_blk[0] = 1'b0;
    assign proc_46_output_sync_blk[0] = 1'b0;
    assign proc_dep_vld_vec_46[0] = dl_detect_out ? proc_dep_vld_vec_46_reg[0] : (proc_46_data_FIFO_blk[0] | proc_46_data_PIPO_blk[0] | proc_46_start_FIFO_blk[0] | proc_46_TLF_FIFO_blk[0] | proc_46_input_sync_blk[0] | proc_46_output_sync_blk[0]);
    assign proc_46_data_FIFO_blk[1] = 1'b0 | (~grp_dataflow_wrapper_fu_6443.task_compute_attn_U0.grp_do_attn_1_fu_5150.stream_merge_1_U0.grp_stream_merge_1_Pipeline_VITIS_LOOP_554_1_VITIS_LOOP_555_2_fu_34.o_sm_blk_n);
    assign proc_46_data_PIPO_blk[1] = 1'b0;
    assign proc_46_start_FIFO_blk[1] = 1'b0;
    assign proc_46_TLF_FIFO_blk[1] = 1'b0;
    assign proc_46_input_sync_blk[1] = 1'b0;
    assign proc_46_output_sync_blk[1] = 1'b0;
    assign proc_dep_vld_vec_46[1] = dl_detect_out ? proc_dep_vld_vec_46_reg[1] : (proc_46_data_FIFO_blk[1] | proc_46_data_PIPO_blk[1] | proc_46_start_FIFO_blk[1] | proc_46_TLF_FIFO_blk[1] | proc_46_input_sync_blk[1] | proc_46_output_sync_blk[1]);
    assign proc_46_data_FIFO_blk[2] = 1'b0 | (~grp_dataflow_wrapper_fu_6443.task_compute_attn_U0.grp_do_attn_1_fu_5150.stream_merge_1_U0.grp_stream_merge_1_Pipeline_VITIS_LOOP_554_1_VITIS_LOOP_555_2_fu_34.o_sm_blk_n);
    assign proc_46_data_PIPO_blk[2] = 1'b0;
    assign proc_46_start_FIFO_blk[2] = 1'b0;
    assign proc_46_TLF_FIFO_blk[2] = 1'b0;
    assign proc_46_input_sync_blk[2] = 1'b0;
    assign proc_46_output_sync_blk[2] = 1'b0;
    assign proc_dep_vld_vec_46[2] = dl_detect_out ? proc_dep_vld_vec_46_reg[2] : (proc_46_data_FIFO_blk[2] | proc_46_data_PIPO_blk[2] | proc_46_start_FIFO_blk[2] | proc_46_TLF_FIFO_blk[2] | proc_46_input_sync_blk[2] | proc_46_output_sync_blk[2]);
    always @ (negedge dl_reset or posedge dl_clock) begin
        if (~dl_reset) begin
            proc_dep_vld_vec_46_reg <= 'b0;
        end
        else begin
            proc_dep_vld_vec_46_reg <= proc_dep_vld_vec_46;
        end
    end
    assign in_chan_dep_vld_vec_46[0] = dep_chan_vld_12_46;
    assign in_chan_dep_data_vec_46[73 : 0] = dep_chan_data_12_46;
    assign token_in_vec_46[0] = token_12_46;
    assign in_chan_dep_vld_vec_46[1] = dep_chan_vld_41_46;
    assign in_chan_dep_data_vec_46[147 : 74] = dep_chan_data_41_46;
    assign token_in_vec_46[1] = token_41_46;
    assign in_chan_dep_vld_vec_46[2] = dep_chan_vld_45_46;
    assign in_chan_dep_data_vec_46[221 : 148] = dep_chan_data_45_46;
    assign token_in_vec_46[2] = token_45_46;
    assign dep_chan_vld_46_12 = out_chan_dep_vld_vec_46[0];
    assign dep_chan_data_46_12 = out_chan_dep_data_46;
    assign token_46_12 = token_out_vec_46[0];
    assign dep_chan_vld_46_41 = out_chan_dep_vld_vec_46[1];
    assign dep_chan_data_46_41 = out_chan_dep_data_46;
    assign token_46_41 = token_out_vec_46[1];
    assign dep_chan_vld_46_45 = out_chan_dep_vld_vec_46[2];
    assign dep_chan_data_46_45 = out_chan_dep_data_46;
    assign token_46_45 = token_out_vec_46[2];

    // Process: grp_dataflow_wrapper_fu_6443.task_stream_cast_U0
    vit_block_top_hls_deadlock_detect_unit #(74, 47, 2, 2) vit_block_top_hls_deadlock_detect_unit_47 (
        .reset(dl_reset),
        .clock(dl_clock),
        .proc_dep_vld_vec(proc_dep_vld_vec_47),
        .in_chan_dep_vld_vec(in_chan_dep_vld_vec_47),
        .in_chan_dep_data_vec(in_chan_dep_data_vec_47),
        .token_in_vec(token_in_vec_47),
        .dl_detect_in(dl_detect_out),
        .origin(origin[47]),
        .token_clear(token_clear),
        .out_chan_dep_vld_vec(out_chan_dep_vld_vec_47),
        .out_chan_dep_data(out_chan_dep_data_47),
        .token_out_vec(token_out_vec_47),
        .dl_detect_out(dl_in_vec[47]));

    assign proc_47_data_FIFO_blk[0] = 1'b0 | (~grp_dataflow_wrapper_fu_6443.task_stream_cast_U0.mid_stream_int_blk_n);
    assign proc_47_data_PIPO_blk[0] = 1'b0;
    assign proc_47_start_FIFO_blk[0] = 1'b0 | (~grp_dataflow_wrapper_fu_6443.start_for_task_stream_cast_U0_U.if_empty_n & grp_dataflow_wrapper_fu_6443.task_stream_cast_U0.ap_idle & ~grp_dataflow_wrapper_fu_6443.start_for_task_stream_cast_U0_U.if_write);
    assign proc_47_TLF_FIFO_blk[0] = 1'b0;
    assign proc_47_input_sync_blk[0] = 1'b0;
    assign proc_47_output_sync_blk[0] = 1'b0;
    assign proc_dep_vld_vec_47[0] = dl_detect_out ? proc_dep_vld_vec_47_reg[0] : (proc_47_data_FIFO_blk[0] | proc_47_data_PIPO_blk[0] | proc_47_start_FIFO_blk[0] | proc_47_TLF_FIFO_blk[0] | proc_47_input_sync_blk[0] | proc_47_output_sync_blk[0]);
    assign proc_47_data_FIFO_blk[1] = 1'b0 | (~grp_dataflow_wrapper_fu_6443.task_stream_cast_U0.mlp_in_stream_blk_n);
    assign proc_47_data_PIPO_blk[1] = 1'b0;
    assign proc_47_start_FIFO_blk[1] = 1'b0;
    assign proc_47_TLF_FIFO_blk[1] = 1'b0;
    assign proc_47_input_sync_blk[1] = 1'b0;
    assign proc_47_output_sync_blk[1] = 1'b0;
    assign proc_dep_vld_vec_47[1] = dl_detect_out ? proc_dep_vld_vec_47_reg[1] : (proc_47_data_FIFO_blk[1] | proc_47_data_PIPO_blk[1] | proc_47_start_FIFO_blk[1] | proc_47_TLF_FIFO_blk[1] | proc_47_input_sync_blk[1] | proc_47_output_sync_blk[1]);
    always @ (negedge dl_reset or posedge dl_clock) begin
        if (~dl_reset) begin
            proc_dep_vld_vec_47_reg <= 'b0;
        end
        else begin
            proc_dep_vld_vec_47_reg <= proc_dep_vld_vec_47;
        end
    end
    assign in_chan_dep_vld_vec_47[0] = dep_chan_vld_10_47;
    assign in_chan_dep_data_vec_47[73 : 0] = dep_chan_data_10_47;
    assign token_in_vec_47[0] = token_10_47;
    assign in_chan_dep_vld_vec_47[1] = dep_chan_vld_48_47;
    assign in_chan_dep_data_vec_47[147 : 74] = dep_chan_data_48_47;
    assign token_in_vec_47[1] = token_48_47;
    assign dep_chan_vld_47_10 = out_chan_dep_vld_vec_47[0];
    assign dep_chan_data_47_10 = out_chan_dep_data_47;
    assign token_47_10 = token_out_vec_47[0];
    assign dep_chan_vld_47_48 = out_chan_dep_vld_vec_47[1];
    assign dep_chan_data_47_48 = out_chan_dep_data_47;
    assign token_47_48 = token_out_vec_47[1];

    // Process: grp_dataflow_wrapper_fu_6443.task_compute_mlp_U0
    vit_block_top_hls_deadlock_detect_unit #(74, 48, 2, 3) vit_block_top_hls_deadlock_detect_unit_48 (
        .reset(dl_reset),
        .clock(dl_clock),
        .proc_dep_vld_vec(proc_dep_vld_vec_48),
        .in_chan_dep_vld_vec(in_chan_dep_vld_vec_48),
        .in_chan_dep_data_vec(in_chan_dep_data_vec_48),
        .token_in_vec(token_in_vec_48),
        .dl_detect_in(dl_detect_out),
        .origin(origin[48]),
        .token_clear(token_clear),
        .out_chan_dep_vld_vec(out_chan_dep_vld_vec_48),
        .out_chan_dep_data(out_chan_dep_data_48),
        .token_out_vec(token_out_vec_48),
        .dl_detect_out(dl_in_vec[48]));

    assign proc_48_data_FIFO_blk[0] = 1'b0;
    assign proc_48_data_PIPO_blk[0] = 1'b0;
    assign proc_48_start_FIFO_blk[0] = 1'b0;
    assign proc_48_TLF_FIFO_blk[0] = 1'b0 | (~grp_dataflow_wrapper_fu_6443.calc_weights_mlp_weights_mlp_scalars_idx_val_loc_channel_U.if_empty_n & grp_dataflow_wrapper_fu_6443.task_compute_mlp_U0.ap_idle & ~grp_dataflow_wrapper_fu_6443.calc_weights_mlp_weights_mlp_scalars_idx_val_loc_channel_U.if_write) | (~grp_dataflow_wrapper_fu_6443.calc_weights_mlp_weights_mlp_scalars_idx7_val_loc_channel_U.if_empty_n & grp_dataflow_wrapper_fu_6443.task_compute_mlp_U0.ap_idle & ~grp_dataflow_wrapper_fu_6443.calc_weights_mlp_weights_mlp_scalars_idx7_val_loc_channel_U.if_write);
    assign proc_48_input_sync_blk[0] = 1'b0;
    assign proc_48_output_sync_blk[0] = 1'b0;
    assign proc_dep_vld_vec_48[0] = dl_detect_out ? proc_dep_vld_vec_48_reg[0] : (proc_48_data_FIFO_blk[0] | proc_48_data_PIPO_blk[0] | proc_48_start_FIFO_blk[0] | proc_48_TLF_FIFO_blk[0] | proc_48_input_sync_blk[0] | proc_48_output_sync_blk[0]);
    assign proc_48_data_FIFO_blk[1] = 1'b0 | (~grp_dataflow_wrapper_fu_6443.task_compute_mlp_U0.grp_do_mlp_fu_4710.stream_copy_U0.mlp_in_stream_blk_n);
    assign proc_48_data_PIPO_blk[1] = 1'b0;
    assign proc_48_start_FIFO_blk[1] = 1'b0;
    assign proc_48_TLF_FIFO_blk[1] = 1'b0;
    assign proc_48_input_sync_blk[1] = 1'b0;
    assign proc_48_output_sync_blk[1] = 1'b0;
    assign proc_dep_vld_vec_48[1] = dl_detect_out ? proc_dep_vld_vec_48_reg[1] : (proc_48_data_FIFO_blk[1] | proc_48_data_PIPO_blk[1] | proc_48_start_FIFO_blk[1] | proc_48_TLF_FIFO_blk[1] | proc_48_input_sync_blk[1] | proc_48_output_sync_blk[1]);
    assign proc_48_data_FIFO_blk[2] = 1'b0 | (~grp_dataflow_wrapper_fu_6443.task_compute_mlp_U0.grp_do_mlp_fu_4710.stream_merge_U0.grp_stream_merge_Pipeline_VITIS_LOOP_393_1_VITIS_LOOP_394_2_fu_34.o_stream_int_blk_n);
    assign proc_48_data_PIPO_blk[2] = 1'b0;
    assign proc_48_start_FIFO_blk[2] = 1'b0 | (~grp_dataflow_wrapper_fu_6443.start_for_task_write_fm_U0_U.if_full_n & grp_dataflow_wrapper_fu_6443.task_compute_mlp_U0.ap_start & ~grp_dataflow_wrapper_fu_6443.task_compute_mlp_U0.real_start & (trans_in_cnt_43 == trans_out_cnt_43) & ~grp_dataflow_wrapper_fu_6443.start_for_task_write_fm_U0_U.if_read);
    assign proc_48_TLF_FIFO_blk[2] = 1'b0;
    assign proc_48_input_sync_blk[2] = 1'b0;
    assign proc_48_output_sync_blk[2] = 1'b0;
    assign proc_dep_vld_vec_48[2] = dl_detect_out ? proc_dep_vld_vec_48_reg[2] : (proc_48_data_FIFO_blk[2] | proc_48_data_PIPO_blk[2] | proc_48_start_FIFO_blk[2] | proc_48_TLF_FIFO_blk[2] | proc_48_input_sync_blk[2] | proc_48_output_sync_blk[2]);
    always @ (negedge dl_reset or posedge dl_clock) begin
        if (~dl_reset) begin
            proc_dep_vld_vec_48_reg <= 'b0;
        end
        else begin
            proc_dep_vld_vec_48_reg <= proc_dep_vld_vec_48;
        end
    end
    assign in_chan_dep_vld_vec_48[0] = dep_chan_vld_47_48;
    assign in_chan_dep_data_vec_48[73 : 0] = dep_chan_data_47_48;
    assign token_in_vec_48[0] = token_47_48;
    assign in_chan_dep_vld_vec_48[1] = dep_chan_vld_65_48;
    assign in_chan_dep_data_vec_48[147 : 74] = dep_chan_data_65_48;
    assign token_in_vec_48[1] = token_65_48;
    assign dep_chan_vld_48_9 = out_chan_dep_vld_vec_48[0];
    assign dep_chan_data_48_9 = out_chan_dep_data_48;
    assign token_48_9 = token_out_vec_48[0];
    assign dep_chan_vld_48_47 = out_chan_dep_vld_vec_48[1];
    assign dep_chan_data_48_47 = out_chan_dep_data_48;
    assign token_48_47 = token_out_vec_48[1];
    assign dep_chan_vld_48_65 = out_chan_dep_vld_vec_48[2];
    assign dep_chan_data_48_65 = out_chan_dep_data_48;
    assign token_48_65 = token_out_vec_48[2];

    // Process: grp_dataflow_wrapper_fu_6443.task_compute_mlp_U0.grp_do_mlp_fu_4710.stream_copy_U0
    vit_block_top_hls_deadlock_detect_unit #(74, 49, 2, 2) vit_block_top_hls_deadlock_detect_unit_49 (
        .reset(dl_reset),
        .clock(dl_clock),
        .proc_dep_vld_vec(proc_dep_vld_vec_49),
        .in_chan_dep_vld_vec(in_chan_dep_vld_vec_49),
        .in_chan_dep_data_vec(in_chan_dep_data_vec_49),
        .token_in_vec(token_in_vec_49),
        .dl_detect_in(dl_detect_out),
        .origin(origin[49]),
        .token_clear(token_clear),
        .out_chan_dep_vld_vec(out_chan_dep_vld_vec_49),
        .out_chan_dep_data(out_chan_dep_data_49),
        .token_out_vec(token_out_vec_49),
        .dl_detect_out(dl_in_vec[49]));

    assign proc_49_data_FIFO_blk[0] = 1'b0 | (~grp_dataflow_wrapper_fu_6443.task_compute_mlp_U0.grp_do_mlp_fu_4710.stream_copy_U0.main_sm_blk_n);
    assign proc_49_data_PIPO_blk[0] = 1'b0;
    assign proc_49_start_FIFO_blk[0] = 1'b0 | (~grp_dataflow_wrapper_fu_6443.task_compute_mlp_U0.grp_do_mlp_fu_4710.start_for_do_layernorm_inter_token_U0_U.if_full_n & grp_dataflow_wrapper_fu_6443.task_compute_mlp_U0.grp_do_mlp_fu_4710.stream_copy_U0.ap_start & ~grp_dataflow_wrapper_fu_6443.task_compute_mlp_U0.grp_do_mlp_fu_4710.stream_copy_U0.real_start & (trans_in_cnt_31 == trans_out_cnt_31) & ~grp_dataflow_wrapper_fu_6443.task_compute_mlp_U0.grp_do_mlp_fu_4710.start_for_do_layernorm_inter_token_U0_U.if_read);
    assign proc_49_TLF_FIFO_blk[0] = 1'b0;
    assign proc_49_input_sync_blk[0] = 1'b0;
    assign proc_49_output_sync_blk[0] = 1'b0;
    assign proc_dep_vld_vec_49[0] = dl_detect_out ? proc_dep_vld_vec_49_reg[0] : (proc_49_data_FIFO_blk[0] | proc_49_data_PIPO_blk[0] | proc_49_start_FIFO_blk[0] | proc_49_TLF_FIFO_blk[0] | proc_49_input_sync_blk[0] | proc_49_output_sync_blk[0]);
    assign proc_49_data_FIFO_blk[1] = 1'b0 | (~grp_dataflow_wrapper_fu_6443.task_compute_mlp_U0.grp_do_mlp_fu_4710.stream_copy_U0.resi_i_sm_blk_n);
    assign proc_49_data_PIPO_blk[1] = 1'b0;
    assign proc_49_start_FIFO_blk[1] = 1'b0 | (~grp_dataflow_wrapper_fu_6443.task_compute_mlp_U0.grp_do_mlp_fu_4710.start_for_do_adapt_6_U0_U.if_full_n & grp_dataflow_wrapper_fu_6443.task_compute_mlp_U0.grp_do_mlp_fu_4710.stream_copy_U0.ap_start & ~grp_dataflow_wrapper_fu_6443.task_compute_mlp_U0.grp_do_mlp_fu_4710.stream_copy_U0.real_start & (trans_in_cnt_31 == trans_out_cnt_31) & ~grp_dataflow_wrapper_fu_6443.task_compute_mlp_U0.grp_do_mlp_fu_4710.start_for_do_adapt_6_U0_U.if_read);
    assign proc_49_TLF_FIFO_blk[1] = 1'b0;
    assign proc_49_input_sync_blk[1] = 1'b0;
    assign proc_49_output_sync_blk[1] = 1'b0;
    assign proc_dep_vld_vec_49[1] = dl_detect_out ? proc_dep_vld_vec_49_reg[1] : (proc_49_data_FIFO_blk[1] | proc_49_data_PIPO_blk[1] | proc_49_start_FIFO_blk[1] | proc_49_TLF_FIFO_blk[1] | proc_49_input_sync_blk[1] | proc_49_output_sync_blk[1]);
    always @ (negedge dl_reset or posedge dl_clock) begin
        if (~dl_reset) begin
            proc_dep_vld_vec_49_reg <= 'b0;
        end
        else begin
            proc_dep_vld_vec_49_reg <= proc_dep_vld_vec_49;
        end
    end
    assign in_chan_dep_vld_vec_49[0] = dep_chan_vld_50_49;
    assign in_chan_dep_data_vec_49[73 : 0] = dep_chan_data_50_49;
    assign token_in_vec_49[0] = token_50_49;
    assign in_chan_dep_vld_vec_49[1] = dep_chan_vld_52_49;
    assign in_chan_dep_data_vec_49[147 : 74] = dep_chan_data_52_49;
    assign token_in_vec_49[1] = token_52_49;
    assign dep_chan_vld_49_52 = out_chan_dep_vld_vec_49[0];
    assign dep_chan_data_49_52 = out_chan_dep_data_49;
    assign token_49_52 = token_out_vec_49[0];
    assign dep_chan_vld_49_50 = out_chan_dep_vld_vec_49[1];
    assign dep_chan_data_49_50 = out_chan_dep_data_49;
    assign token_49_50 = token_out_vec_49[1];

    // Process: grp_dataflow_wrapper_fu_6443.task_compute_mlp_U0.grp_do_mlp_fu_4710.do_adapt_6_U0
    vit_block_top_hls_deadlock_detect_unit #(74, 50, 2, 2) vit_block_top_hls_deadlock_detect_unit_50 (
        .reset(dl_reset),
        .clock(dl_clock),
        .proc_dep_vld_vec(proc_dep_vld_vec_50),
        .in_chan_dep_vld_vec(in_chan_dep_vld_vec_50),
        .in_chan_dep_data_vec(in_chan_dep_data_vec_50),
        .token_in_vec(token_in_vec_50),
        .dl_detect_in(dl_detect_out),
        .origin(origin[50]),
        .token_clear(token_clear),
        .out_chan_dep_vld_vec(out_chan_dep_vld_vec_50),
        .out_chan_dep_data(out_chan_dep_data_50),
        .token_out_vec(token_out_vec_50),
        .dl_detect_out(dl_in_vec[50]));

    assign proc_50_data_FIFO_blk[0] = 1'b0 | (~grp_dataflow_wrapper_fu_6443.task_compute_mlp_U0.grp_do_mlp_fu_4710.do_adapt_6_U0.resi_i_sm_blk_n);
    assign proc_50_data_PIPO_blk[0] = 1'b0;
    assign proc_50_start_FIFO_blk[0] = 1'b0 | (~grp_dataflow_wrapper_fu_6443.task_compute_mlp_U0.grp_do_mlp_fu_4710.start_for_do_adapt_6_U0_U.if_empty_n & grp_dataflow_wrapper_fu_6443.task_compute_mlp_U0.grp_do_mlp_fu_4710.do_adapt_6_U0.ap_idle & ~grp_dataflow_wrapper_fu_6443.task_compute_mlp_U0.grp_do_mlp_fu_4710.start_for_do_adapt_6_U0_U.if_write);
    assign proc_50_TLF_FIFO_blk[0] = 1'b0;
    assign proc_50_input_sync_blk[0] = 1'b0;
    assign proc_50_output_sync_blk[0] = 1'b0;
    assign proc_dep_vld_vec_50[0] = dl_detect_out ? proc_dep_vld_vec_50_reg[0] : (proc_50_data_FIFO_blk[0] | proc_50_data_PIPO_blk[0] | proc_50_start_FIFO_blk[0] | proc_50_TLF_FIFO_blk[0] | proc_50_input_sync_blk[0] | proc_50_output_sync_blk[0]);
    assign proc_50_data_FIFO_blk[1] = 1'b0 | (~grp_dataflow_wrapper_fu_6443.task_compute_mlp_U0.grp_do_mlp_fu_4710.do_adapt_6_U0.resi_sm_blk_n);
    assign proc_50_data_PIPO_blk[1] = 1'b0;
    assign proc_50_start_FIFO_blk[1] = 1'b0 | (~grp_dataflow_wrapper_fu_6443.task_compute_mlp_U0.grp_do_mlp_fu_4710.start_for_do_adapt_5_U0_U.if_full_n & grp_dataflow_wrapper_fu_6443.task_compute_mlp_U0.grp_do_mlp_fu_4710.do_adapt_6_U0.ap_start & ~grp_dataflow_wrapper_fu_6443.task_compute_mlp_U0.grp_do_mlp_fu_4710.do_adapt_6_U0.real_start & (trans_in_cnt_32 == trans_out_cnt_32) & ~grp_dataflow_wrapper_fu_6443.task_compute_mlp_U0.grp_do_mlp_fu_4710.start_for_do_adapt_5_U0_U.if_read);
    assign proc_50_TLF_FIFO_blk[1] = 1'b0;
    assign proc_50_input_sync_blk[1] = 1'b0;
    assign proc_50_output_sync_blk[1] = 1'b0;
    assign proc_dep_vld_vec_50[1] = dl_detect_out ? proc_dep_vld_vec_50_reg[1] : (proc_50_data_FIFO_blk[1] | proc_50_data_PIPO_blk[1] | proc_50_start_FIFO_blk[1] | proc_50_TLF_FIFO_blk[1] | proc_50_input_sync_blk[1] | proc_50_output_sync_blk[1]);
    always @ (negedge dl_reset or posedge dl_clock) begin
        if (~dl_reset) begin
            proc_dep_vld_vec_50_reg <= 'b0;
        end
        else begin
            proc_dep_vld_vec_50_reg <= proc_dep_vld_vec_50;
        end
    end
    assign in_chan_dep_vld_vec_50[0] = dep_chan_vld_49_50;
    assign in_chan_dep_data_vec_50[73 : 0] = dep_chan_data_49_50;
    assign token_in_vec_50[0] = token_49_50;
    assign in_chan_dep_vld_vec_50[1] = dep_chan_vld_51_50;
    assign in_chan_dep_data_vec_50[147 : 74] = dep_chan_data_51_50;
    assign token_in_vec_50[1] = token_51_50;
    assign dep_chan_vld_50_49 = out_chan_dep_vld_vec_50[0];
    assign dep_chan_data_50_49 = out_chan_dep_data_50;
    assign token_50_49 = token_out_vec_50[0];
    assign dep_chan_vld_50_51 = out_chan_dep_vld_vec_50[1];
    assign dep_chan_data_50_51 = out_chan_dep_data_50;
    assign token_50_51 = token_out_vec_50[1];

    // Process: grp_dataflow_wrapper_fu_6443.task_compute_mlp_U0.grp_do_mlp_fu_4710.do_adapt_5_U0
    vit_block_top_hls_deadlock_detect_unit #(74, 51, 2, 2) vit_block_top_hls_deadlock_detect_unit_51 (
        .reset(dl_reset),
        .clock(dl_clock),
        .proc_dep_vld_vec(proc_dep_vld_vec_51),
        .in_chan_dep_vld_vec(in_chan_dep_vld_vec_51),
        .in_chan_dep_data_vec(in_chan_dep_data_vec_51),
        .token_in_vec(token_in_vec_51),
        .dl_detect_in(dl_detect_out),
        .origin(origin[51]),
        .token_clear(token_clear),
        .out_chan_dep_vld_vec(out_chan_dep_vld_vec_51),
        .out_chan_dep_data(out_chan_dep_data_51),
        .token_out_vec(token_out_vec_51),
        .dl_detect_out(dl_in_vec[51]));

    assign proc_51_data_FIFO_blk[0] = 1'b0 | (~grp_dataflow_wrapper_fu_6443.task_compute_mlp_U0.grp_do_mlp_fu_4710.do_adapt_5_U0.resi_sm_blk_n);
    assign proc_51_data_PIPO_blk[0] = 1'b0;
    assign proc_51_start_FIFO_blk[0] = 1'b0 | (~grp_dataflow_wrapper_fu_6443.task_compute_mlp_U0.grp_do_mlp_fu_4710.start_for_do_adapt_5_U0_U.if_empty_n & grp_dataflow_wrapper_fu_6443.task_compute_mlp_U0.grp_do_mlp_fu_4710.do_adapt_5_U0.ap_idle & ~grp_dataflow_wrapper_fu_6443.task_compute_mlp_U0.grp_do_mlp_fu_4710.start_for_do_adapt_5_U0_U.if_write);
    assign proc_51_TLF_FIFO_blk[0] = 1'b0;
    assign proc_51_input_sync_blk[0] = 1'b0;
    assign proc_51_output_sync_blk[0] = 1'b0;
    assign proc_dep_vld_vec_51[0] = dl_detect_out ? proc_dep_vld_vec_51_reg[0] : (proc_51_data_FIFO_blk[0] | proc_51_data_PIPO_blk[0] | proc_51_start_FIFO_blk[0] | proc_51_TLF_FIFO_blk[0] | proc_51_input_sync_blk[0] | proc_51_output_sync_blk[0]);
    assign proc_51_data_FIFO_blk[1] = 1'b0 | (~grp_dataflow_wrapper_fu_6443.task_compute_mlp_U0.grp_do_mlp_fu_4710.do_adapt_5_U0.resi_o_sm_blk_n);
    assign proc_51_data_PIPO_blk[1] = 1'b0;
    assign proc_51_start_FIFO_blk[1] = 1'b0 | (~grp_dataflow_wrapper_fu_6443.task_compute_mlp_U0.grp_do_mlp_fu_4710.start_for_stream_merge_U0_U.if_full_n & grp_dataflow_wrapper_fu_6443.task_compute_mlp_U0.grp_do_mlp_fu_4710.do_adapt_5_U0.ap_start & ~grp_dataflow_wrapper_fu_6443.task_compute_mlp_U0.grp_do_mlp_fu_4710.do_adapt_5_U0.real_start & (trans_in_cnt_42 == trans_out_cnt_42) & ~grp_dataflow_wrapper_fu_6443.task_compute_mlp_U0.grp_do_mlp_fu_4710.start_for_stream_merge_U0_U.if_read);
    assign proc_51_TLF_FIFO_blk[1] = 1'b0;
    assign proc_51_input_sync_blk[1] = 1'b0;
    assign proc_51_output_sync_blk[1] = 1'b0;
    assign proc_dep_vld_vec_51[1] = dl_detect_out ? proc_dep_vld_vec_51_reg[1] : (proc_51_data_FIFO_blk[1] | proc_51_data_PIPO_blk[1] | proc_51_start_FIFO_blk[1] | proc_51_TLF_FIFO_blk[1] | proc_51_input_sync_blk[1] | proc_51_output_sync_blk[1]);
    always @ (negedge dl_reset or posedge dl_clock) begin
        if (~dl_reset) begin
            proc_dep_vld_vec_51_reg <= 'b0;
        end
        else begin
            proc_dep_vld_vec_51_reg <= proc_dep_vld_vec_51;
        end
    end
    assign in_chan_dep_vld_vec_51[0] = dep_chan_vld_50_51;
    assign in_chan_dep_data_vec_51[73 : 0] = dep_chan_data_50_51;
    assign token_in_vec_51[0] = token_50_51;
    assign in_chan_dep_vld_vec_51[1] = dep_chan_vld_64_51;
    assign in_chan_dep_data_vec_51[147 : 74] = dep_chan_data_64_51;
    assign token_in_vec_51[1] = token_64_51;
    assign dep_chan_vld_51_50 = out_chan_dep_vld_vec_51[0];
    assign dep_chan_data_51_50 = out_chan_dep_data_51;
    assign token_51_50 = token_out_vec_51[0];
    assign dep_chan_vld_51_64 = out_chan_dep_vld_vec_51[1];
    assign dep_chan_data_51_64 = out_chan_dep_data_51;
    assign token_51_64 = token_out_vec_51[1];

    // Process: grp_dataflow_wrapper_fu_6443.task_compute_mlp_U0.grp_do_mlp_fu_4710.do_layernorm_inter_token_U0
    vit_block_top_hls_deadlock_detect_unit #(74, 52, 3, 3) vit_block_top_hls_deadlock_detect_unit_52 (
        .reset(dl_reset),
        .clock(dl_clock),
        .proc_dep_vld_vec(proc_dep_vld_vec_52),
        .in_chan_dep_vld_vec(in_chan_dep_vld_vec_52),
        .in_chan_dep_data_vec(in_chan_dep_data_vec_52),
        .token_in_vec(token_in_vec_52),
        .dl_detect_in(dl_detect_out),
        .origin(origin[52]),
        .token_clear(token_clear),
        .out_chan_dep_vld_vec(out_chan_dep_vld_vec_52),
        .out_chan_dep_data(out_chan_dep_data_52),
        .token_out_vec(token_out_vec_52),
        .dl_detect_out(dl_in_vec[52]));

    assign proc_52_data_FIFO_blk[0] = 1'b0 | (~grp_dataflow_wrapper_fu_6443.task_compute_mlp_U0.grp_do_mlp_fu_4710.do_layernorm_inter_token_U0.grp_do_layernorm_inter_token_Pipeline_WAVE_LOOP_CT_PIPELINE_LOOP_fu_138.main_sm_blk_n);
    assign proc_52_data_PIPO_blk[0] = 1'b0;
    assign proc_52_start_FIFO_blk[0] = 1'b0 | (~grp_dataflow_wrapper_fu_6443.task_compute_mlp_U0.grp_do_mlp_fu_4710.start_for_do_layernorm_inter_token_U0_U.if_empty_n & grp_dataflow_wrapper_fu_6443.task_compute_mlp_U0.grp_do_mlp_fu_4710.do_layernorm_inter_token_U0.ap_idle & ~grp_dataflow_wrapper_fu_6443.task_compute_mlp_U0.grp_do_mlp_fu_4710.start_for_do_layernorm_inter_token_U0_U.if_write);
    assign proc_52_TLF_FIFO_blk[0] = 1'b0;
    assign proc_52_input_sync_blk[0] = 1'b0;
    assign proc_52_output_sync_blk[0] = 1'b0;
    assign proc_dep_vld_vec_52[0] = dl_detect_out ? proc_dep_vld_vec_52_reg[0] : (proc_52_data_FIFO_blk[0] | proc_52_data_PIPO_blk[0] | proc_52_start_FIFO_blk[0] | proc_52_TLF_FIFO_blk[0] | proc_52_input_sync_blk[0] | proc_52_output_sync_blk[0]);
    assign proc_52_data_FIFO_blk[1] = 1'b0 | (~grp_dataflow_wrapper_fu_6443.task_compute_mlp_U0.grp_do_mlp_fu_4710.do_layernorm_inter_token_U0.grp_do_layernorm_inter_token_Pipeline_WAVE_LOOP_CT_PIPELINE_LOOP_fu_138.ln_sm_blk_n);
    assign proc_52_data_PIPO_blk[1] = 1'b0;
    assign proc_52_start_FIFO_blk[1] = 1'b0 | (~grp_dataflow_wrapper_fu_6443.task_compute_mlp_U0.grp_do_mlp_fu_4710.start_for_do_matmul_3_U0_U.if_full_n & grp_dataflow_wrapper_fu_6443.task_compute_mlp_U0.grp_do_mlp_fu_4710.do_layernorm_inter_token_U0.ap_start & ~grp_dataflow_wrapper_fu_6443.task_compute_mlp_U0.grp_do_mlp_fu_4710.do_layernorm_inter_token_U0.real_start & (trans_in_cnt_33 == trans_out_cnt_33) & ~grp_dataflow_wrapper_fu_6443.task_compute_mlp_U0.grp_do_mlp_fu_4710.start_for_do_matmul_3_U0_U.if_read);
    assign proc_52_TLF_FIFO_blk[1] = 1'b0;
    assign proc_52_input_sync_blk[1] = 1'b0;
    assign proc_52_output_sync_blk[1] = 1'b0;
    assign proc_dep_vld_vec_52[1] = dl_detect_out ? proc_dep_vld_vec_52_reg[1] : (proc_52_data_FIFO_blk[1] | proc_52_data_PIPO_blk[1] | proc_52_start_FIFO_blk[1] | proc_52_TLF_FIFO_blk[1] | proc_52_input_sync_blk[1] | proc_52_output_sync_blk[1]);
    assign proc_52_data_FIFO_blk[2] = 1'b0 | (~grp_dataflow_wrapper_fu_6443.task_compute_mlp_U0.grp_do_mlp_fu_4710.do_layernorm_inter_token_U0.grp_do_layernorm_inter_token_Pipeline_WAVE_LOOP_CT_PIPELINE_LOOP_fu_138.ln_sm_blk_n);
    assign proc_52_data_PIPO_blk[2] = 1'b0;
    assign proc_52_start_FIFO_blk[2] = 1'b0;
    assign proc_52_TLF_FIFO_blk[2] = 1'b0;
    assign proc_52_input_sync_blk[2] = 1'b0;
    assign proc_52_output_sync_blk[2] = 1'b0;
    assign proc_dep_vld_vec_52[2] = dl_detect_out ? proc_dep_vld_vec_52_reg[2] : (proc_52_data_FIFO_blk[2] | proc_52_data_PIPO_blk[2] | proc_52_start_FIFO_blk[2] | proc_52_TLF_FIFO_blk[2] | proc_52_input_sync_blk[2] | proc_52_output_sync_blk[2]);
    always @ (negedge dl_reset or posedge dl_clock) begin
        if (~dl_reset) begin
            proc_dep_vld_vec_52_reg <= 'b0;
        end
        else begin
            proc_dep_vld_vec_52_reg <= proc_dep_vld_vec_52;
        end
    end
    assign in_chan_dep_vld_vec_52[0] = dep_chan_vld_49_52;
    assign in_chan_dep_data_vec_52[73 : 0] = dep_chan_data_49_52;
    assign token_in_vec_52[0] = token_49_52;
    assign in_chan_dep_vld_vec_52[1] = dep_chan_vld_53_52;
    assign in_chan_dep_data_vec_52[147 : 74] = dep_chan_data_53_52;
    assign token_in_vec_52[1] = token_53_52;
    assign in_chan_dep_vld_vec_52[2] = dep_chan_vld_54_52;
    assign in_chan_dep_data_vec_52[221 : 148] = dep_chan_data_54_52;
    assign token_in_vec_52[2] = token_54_52;
    assign dep_chan_vld_52_49 = out_chan_dep_vld_vec_52[0];
    assign dep_chan_data_52_49 = out_chan_dep_data_52;
    assign token_52_49 = token_out_vec_52[0];
    assign dep_chan_vld_52_53 = out_chan_dep_vld_vec_52[1];
    assign dep_chan_data_52_53 = out_chan_dep_data_52;
    assign token_52_53 = token_out_vec_52[1];
    assign dep_chan_vld_52_54 = out_chan_dep_vld_vec_52[2];
    assign dep_chan_data_52_54 = out_chan_dep_data_52;
    assign token_52_54 = token_out_vec_52[2];

    // Process: grp_dataflow_wrapper_fu_6443.task_compute_mlp_U0.grp_do_mlp_fu_4710.do_matmul_3_U0
    vit_block_top_hls_deadlock_detect_unit #(74, 53, 2, 2) vit_block_top_hls_deadlock_detect_unit_53 (
        .reset(dl_reset),
        .clock(dl_clock),
        .proc_dep_vld_vec(proc_dep_vld_vec_53),
        .in_chan_dep_vld_vec(in_chan_dep_vld_vec_53),
        .in_chan_dep_data_vec(in_chan_dep_data_vec_53),
        .token_in_vec(token_in_vec_53),
        .dl_detect_in(dl_detect_out),
        .origin(origin[53]),
        .token_clear(token_clear),
        .out_chan_dep_vld_vec(out_chan_dep_vld_vec_53),
        .out_chan_dep_data(out_chan_dep_data_53),
        .token_out_vec(token_out_vec_53),
        .dl_detect_out(dl_in_vec[53]));

    assign proc_53_data_FIFO_blk[0] = 1'b0 | (~grp_dataflow_wrapper_fu_6443.task_compute_mlp_U0.grp_do_mlp_fu_4710.do_matmul_3_U0.do_adapt_1_1_U0.ln_sm_blk_n);
    assign proc_53_data_PIPO_blk[0] = 1'b0;
    assign proc_53_start_FIFO_blk[0] = 1'b0 | (~grp_dataflow_wrapper_fu_6443.task_compute_mlp_U0.grp_do_mlp_fu_4710.start_for_do_matmul_3_U0_U.if_empty_n & grp_dataflow_wrapper_fu_6443.task_compute_mlp_U0.grp_do_mlp_fu_4710.do_matmul_3_U0.ap_idle & ~grp_dataflow_wrapper_fu_6443.task_compute_mlp_U0.grp_do_mlp_fu_4710.start_for_do_matmul_3_U0_U.if_write);
    assign proc_53_TLF_FIFO_blk[0] = 1'b0;
    assign proc_53_input_sync_blk[0] = 1'b0;
    assign proc_53_output_sync_blk[0] = 1'b0;
    assign proc_dep_vld_vec_53[0] = dl_detect_out ? proc_dep_vld_vec_53_reg[0] : (proc_53_data_FIFO_blk[0] | proc_53_data_PIPO_blk[0] | proc_53_start_FIFO_blk[0] | proc_53_TLF_FIFO_blk[0] | proc_53_input_sync_blk[0] | proc_53_output_sync_blk[0]);
    assign proc_53_data_FIFO_blk[1] = 1'b0 | (~grp_dataflow_wrapper_fu_6443.task_compute_mlp_U0.grp_do_mlp_fu_4710.do_matmul_3_U0.do_adapt_12_U0.m1_sm_blk_n);
    assign proc_53_data_PIPO_blk[1] = 1'b0;
    assign proc_53_start_FIFO_blk[1] = 1'b0 | (~grp_dataflow_wrapper_fu_6443.task_compute_mlp_U0.grp_do_mlp_fu_4710.start_for_do_gelu_U0_U.if_full_n & grp_dataflow_wrapper_fu_6443.task_compute_mlp_U0.grp_do_mlp_fu_4710.do_matmul_3_U0.ap_start & ~grp_dataflow_wrapper_fu_6443.task_compute_mlp_U0.grp_do_mlp_fu_4710.do_matmul_3_U0.real_start & (trans_in_cnt_37 == trans_out_cnt_37) & ~grp_dataflow_wrapper_fu_6443.task_compute_mlp_U0.grp_do_mlp_fu_4710.start_for_do_gelu_U0_U.if_read);
    assign proc_53_TLF_FIFO_blk[1] = 1'b0;
    assign proc_53_input_sync_blk[1] = 1'b0;
    assign proc_53_output_sync_blk[1] = 1'b0;
    assign proc_dep_vld_vec_53[1] = dl_detect_out ? proc_dep_vld_vec_53_reg[1] : (proc_53_data_FIFO_blk[1] | proc_53_data_PIPO_blk[1] | proc_53_start_FIFO_blk[1] | proc_53_TLF_FIFO_blk[1] | proc_53_input_sync_blk[1] | proc_53_output_sync_blk[1]);
    always @ (negedge dl_reset or posedge dl_clock) begin
        if (~dl_reset) begin
            proc_dep_vld_vec_53_reg <= 'b0;
        end
        else begin
            proc_dep_vld_vec_53_reg <= proc_dep_vld_vec_53;
        end
    end
    assign in_chan_dep_vld_vec_53[0] = dep_chan_vld_52_53;
    assign in_chan_dep_data_vec_53[73 : 0] = dep_chan_data_52_53;
    assign token_in_vec_53[0] = token_52_53;
    assign in_chan_dep_vld_vec_53[1] = dep_chan_vld_58_53;
    assign in_chan_dep_data_vec_53[147 : 74] = dep_chan_data_58_53;
    assign token_in_vec_53[1] = token_58_53;
    assign dep_chan_vld_53_52 = out_chan_dep_vld_vec_53[0];
    assign dep_chan_data_53_52 = out_chan_dep_data_53;
    assign token_53_52 = token_out_vec_53[0];
    assign dep_chan_vld_53_58 = out_chan_dep_vld_vec_53[1];
    assign dep_chan_data_53_58 = out_chan_dep_data_53;
    assign token_53_58 = token_out_vec_53[1];

    // Process: grp_dataflow_wrapper_fu_6443.task_compute_mlp_U0.grp_do_mlp_fu_4710.do_matmul_3_U0.do_adapt_1_1_U0
    vit_block_top_hls_deadlock_detect_unit #(74, 54, 2, 2) vit_block_top_hls_deadlock_detect_unit_54 (
        .reset(dl_reset),
        .clock(dl_clock),
        .proc_dep_vld_vec(proc_dep_vld_vec_54),
        .in_chan_dep_vld_vec(in_chan_dep_vld_vec_54),
        .in_chan_dep_data_vec(in_chan_dep_data_vec_54),
        .token_in_vec(token_in_vec_54),
        .dl_detect_in(dl_detect_out),
        .origin(origin[54]),
        .token_clear(token_clear),
        .out_chan_dep_vld_vec(out_chan_dep_vld_vec_54),
        .out_chan_dep_data(out_chan_dep_data_54),
        .token_out_vec(token_out_vec_54),
        .dl_detect_out(dl_in_vec[54]));

    assign proc_54_data_FIFO_blk[0] = 1'b0 | (~grp_dataflow_wrapper_fu_6443.task_compute_mlp_U0.grp_do_mlp_fu_4710.do_matmul_3_U0.do_adapt_1_1_U0.ln_sm_blk_n);
    assign proc_54_data_PIPO_blk[0] = 1'b0;
    assign proc_54_start_FIFO_blk[0] = 1'b0;
    assign proc_54_TLF_FIFO_blk[0] = 1'b0;
    assign proc_54_input_sync_blk[0] = 1'b0;
    assign proc_54_output_sync_blk[0] = 1'b0;
    assign proc_dep_vld_vec_54[0] = dl_detect_out ? proc_dep_vld_vec_54_reg[0] : (proc_54_data_FIFO_blk[0] | proc_54_data_PIPO_blk[0] | proc_54_start_FIFO_blk[0] | proc_54_TLF_FIFO_blk[0] | proc_54_input_sync_blk[0] | proc_54_output_sync_blk[0]);
    assign proc_54_data_FIFO_blk[1] = 1'b0 | (~grp_dataflow_wrapper_fu_6443.task_compute_mlp_U0.grp_do_mlp_fu_4710.do_matmul_3_U0.do_adapt_1_1_U0.adpt_sm_blk_n);
    assign proc_54_data_PIPO_blk[1] = 1'b0;
    assign proc_54_start_FIFO_blk[1] = 1'b0 | (~grp_dataflow_wrapper_fu_6443.task_compute_mlp_U0.grp_do_mlp_fu_4710.do_matmul_3_U0.start_for_matmul_step1_cache_window_3_U0_U.if_full_n & grp_dataflow_wrapper_fu_6443.task_compute_mlp_U0.grp_do_mlp_fu_4710.do_matmul_3_U0.do_adapt_1_1_U0.ap_start & ~grp_dataflow_wrapper_fu_6443.task_compute_mlp_U0.grp_do_mlp_fu_4710.do_matmul_3_U0.do_adapt_1_1_U0.real_start & (trans_in_cnt_34 == trans_out_cnt_34) & ~grp_dataflow_wrapper_fu_6443.task_compute_mlp_U0.grp_do_mlp_fu_4710.do_matmul_3_U0.start_for_matmul_step1_cache_window_3_U0_U.if_read);
    assign proc_54_TLF_FIFO_blk[1] = 1'b0;
    assign proc_54_input_sync_blk[1] = 1'b0;
    assign proc_54_output_sync_blk[1] = 1'b0;
    assign proc_dep_vld_vec_54[1] = dl_detect_out ? proc_dep_vld_vec_54_reg[1] : (proc_54_data_FIFO_blk[1] | proc_54_data_PIPO_blk[1] | proc_54_start_FIFO_blk[1] | proc_54_TLF_FIFO_blk[1] | proc_54_input_sync_blk[1] | proc_54_output_sync_blk[1]);
    always @ (negedge dl_reset or posedge dl_clock) begin
        if (~dl_reset) begin
            proc_dep_vld_vec_54_reg <= 'b0;
        end
        else begin
            proc_dep_vld_vec_54_reg <= proc_dep_vld_vec_54;
        end
    end
    assign in_chan_dep_vld_vec_54[0] = dep_chan_vld_52_54;
    assign in_chan_dep_data_vec_54[73 : 0] = dep_chan_data_52_54;
    assign token_in_vec_54[0] = token_52_54;
    assign in_chan_dep_vld_vec_54[1] = dep_chan_vld_55_54;
    assign in_chan_dep_data_vec_54[147 : 74] = dep_chan_data_55_54;
    assign token_in_vec_54[1] = token_55_54;
    assign dep_chan_vld_54_52 = out_chan_dep_vld_vec_54[0];
    assign dep_chan_data_54_52 = out_chan_dep_data_54;
    assign token_54_52 = token_out_vec_54[0];
    assign dep_chan_vld_54_55 = out_chan_dep_vld_vec_54[1];
    assign dep_chan_data_54_55 = out_chan_dep_data_54;
    assign token_54_55 = token_out_vec_54[1];

    // Process: grp_dataflow_wrapper_fu_6443.task_compute_mlp_U0.grp_do_mlp_fu_4710.do_matmul_3_U0.matmul_step1_cache_window_3_U0
    vit_block_top_hls_deadlock_detect_unit #(74, 55, 2, 2) vit_block_top_hls_deadlock_detect_unit_55 (
        .reset(dl_reset),
        .clock(dl_clock),
        .proc_dep_vld_vec(proc_dep_vld_vec_55),
        .in_chan_dep_vld_vec(in_chan_dep_vld_vec_55),
        .in_chan_dep_data_vec(in_chan_dep_data_vec_55),
        .token_in_vec(token_in_vec_55),
        .dl_detect_in(dl_detect_out),
        .origin(origin[55]),
        .token_clear(token_clear),
        .out_chan_dep_vld_vec(out_chan_dep_vld_vec_55),
        .out_chan_dep_data(out_chan_dep_data_55),
        .token_out_vec(token_out_vec_55),
        .dl_detect_out(dl_in_vec[55]));

    assign proc_55_data_FIFO_blk[0] = 1'b0 | (~grp_dataflow_wrapper_fu_6443.task_compute_mlp_U0.grp_do_mlp_fu_4710.do_matmul_3_U0.matmul_step1_cache_window_3_U0.adpt_sm_blk_n);
    assign proc_55_data_PIPO_blk[0] = 1'b0;
    assign proc_55_start_FIFO_blk[0] = 1'b0 | (~grp_dataflow_wrapper_fu_6443.task_compute_mlp_U0.grp_do_mlp_fu_4710.do_matmul_3_U0.start_for_matmul_step1_cache_window_3_U0_U.if_empty_n & grp_dataflow_wrapper_fu_6443.task_compute_mlp_U0.grp_do_mlp_fu_4710.do_matmul_3_U0.matmul_step1_cache_window_3_U0.ap_idle & ~grp_dataflow_wrapper_fu_6443.task_compute_mlp_U0.grp_do_mlp_fu_4710.do_matmul_3_U0.start_for_matmul_step1_cache_window_3_U0_U.if_write);
    assign proc_55_TLF_FIFO_blk[0] = 1'b0;
    assign proc_55_input_sync_blk[0] = 1'b0;
    assign proc_55_output_sync_blk[0] = 1'b0;
    assign proc_dep_vld_vec_55[0] = dl_detect_out ? proc_dep_vld_vec_55_reg[0] : (proc_55_data_FIFO_blk[0] | proc_55_data_PIPO_blk[0] | proc_55_start_FIFO_blk[0] | proc_55_TLF_FIFO_blk[0] | proc_55_input_sync_blk[0] | proc_55_output_sync_blk[0]);
    assign proc_55_data_FIFO_blk[1] = 1'b0 | (~grp_dataflow_wrapper_fu_6443.task_compute_mlp_U0.grp_do_mlp_fu_4710.do_matmul_3_U0.matmul_step1_cache_window_3_U0.cache_window_sm_blk_n);
    assign proc_55_data_PIPO_blk[1] = 1'b0;
    assign proc_55_start_FIFO_blk[1] = 1'b0 | (~grp_dataflow_wrapper_fu_6443.task_compute_mlp_U0.grp_do_mlp_fu_4710.do_matmul_3_U0.start_for_matmul_step2_mac_3_U0_U.if_full_n & grp_dataflow_wrapper_fu_6443.task_compute_mlp_U0.grp_do_mlp_fu_4710.do_matmul_3_U0.matmul_step1_cache_window_3_U0.ap_start & ~grp_dataflow_wrapper_fu_6443.task_compute_mlp_U0.grp_do_mlp_fu_4710.do_matmul_3_U0.matmul_step1_cache_window_3_U0.real_start & (trans_in_cnt_35 == trans_out_cnt_35) & ~grp_dataflow_wrapper_fu_6443.task_compute_mlp_U0.grp_do_mlp_fu_4710.do_matmul_3_U0.start_for_matmul_step2_mac_3_U0_U.if_read);
    assign proc_55_TLF_FIFO_blk[1] = 1'b0;
    assign proc_55_input_sync_blk[1] = 1'b0;
    assign proc_55_output_sync_blk[1] = 1'b0;
    assign proc_dep_vld_vec_55[1] = dl_detect_out ? proc_dep_vld_vec_55_reg[1] : (proc_55_data_FIFO_blk[1] | proc_55_data_PIPO_blk[1] | proc_55_start_FIFO_blk[1] | proc_55_TLF_FIFO_blk[1] | proc_55_input_sync_blk[1] | proc_55_output_sync_blk[1]);
    always @ (negedge dl_reset or posedge dl_clock) begin
        if (~dl_reset) begin
            proc_dep_vld_vec_55_reg <= 'b0;
        end
        else begin
            proc_dep_vld_vec_55_reg <= proc_dep_vld_vec_55;
        end
    end
    assign in_chan_dep_vld_vec_55[0] = dep_chan_vld_54_55;
    assign in_chan_dep_data_vec_55[73 : 0] = dep_chan_data_54_55;
    assign token_in_vec_55[0] = token_54_55;
    assign in_chan_dep_vld_vec_55[1] = dep_chan_vld_56_55;
    assign in_chan_dep_data_vec_55[147 : 74] = dep_chan_data_56_55;
    assign token_in_vec_55[1] = token_56_55;
    assign dep_chan_vld_55_54 = out_chan_dep_vld_vec_55[0];
    assign dep_chan_data_55_54 = out_chan_dep_data_55;
    assign token_55_54 = token_out_vec_55[0];
    assign dep_chan_vld_55_56 = out_chan_dep_vld_vec_55[1];
    assign dep_chan_data_55_56 = out_chan_dep_data_55;
    assign token_55_56 = token_out_vec_55[1];

    // Process: grp_dataflow_wrapper_fu_6443.task_compute_mlp_U0.grp_do_mlp_fu_4710.do_matmul_3_U0.matmul_step2_mac_3_U0
    vit_block_top_hls_deadlock_detect_unit #(74, 56, 2, 2) vit_block_top_hls_deadlock_detect_unit_56 (
        .reset(dl_reset),
        .clock(dl_clock),
        .proc_dep_vld_vec(proc_dep_vld_vec_56),
        .in_chan_dep_vld_vec(in_chan_dep_vld_vec_56),
        .in_chan_dep_data_vec(in_chan_dep_data_vec_56),
        .token_in_vec(token_in_vec_56),
        .dl_detect_in(dl_detect_out),
        .origin(origin[56]),
        .token_clear(token_clear),
        .out_chan_dep_vld_vec(out_chan_dep_vld_vec_56),
        .out_chan_dep_data(out_chan_dep_data_56),
        .token_out_vec(token_out_vec_56),
        .dl_detect_out(dl_in_vec[56]));

    assign proc_56_data_FIFO_blk[0] = 1'b0 | (~grp_dataflow_wrapper_fu_6443.task_compute_mlp_U0.grp_do_mlp_fu_4710.do_matmul_3_U0.matmul_step2_mac_3_U0.cache_window_sm_blk_n);
    assign proc_56_data_PIPO_blk[0] = 1'b0;
    assign proc_56_start_FIFO_blk[0] = 1'b0 | (~grp_dataflow_wrapper_fu_6443.task_compute_mlp_U0.grp_do_mlp_fu_4710.do_matmul_3_U0.start_for_matmul_step2_mac_3_U0_U.if_empty_n & grp_dataflow_wrapper_fu_6443.task_compute_mlp_U0.grp_do_mlp_fu_4710.do_matmul_3_U0.matmul_step2_mac_3_U0.ap_idle & ~grp_dataflow_wrapper_fu_6443.task_compute_mlp_U0.grp_do_mlp_fu_4710.do_matmul_3_U0.start_for_matmul_step2_mac_3_U0_U.if_write);
    assign proc_56_TLF_FIFO_blk[0] = 1'b0;
    assign proc_56_input_sync_blk[0] = 1'b0;
    assign proc_56_output_sync_blk[0] = 1'b0;
    assign proc_dep_vld_vec_56[0] = dl_detect_out ? proc_dep_vld_vec_56_reg[0] : (proc_56_data_FIFO_blk[0] | proc_56_data_PIPO_blk[0] | proc_56_start_FIFO_blk[0] | proc_56_TLF_FIFO_blk[0] | proc_56_input_sync_blk[0] | proc_56_output_sync_blk[0]);
    assign proc_56_data_FIFO_blk[1] = 1'b0 | (~grp_dataflow_wrapper_fu_6443.task_compute_mlp_U0.grp_do_mlp_fu_4710.do_matmul_3_U0.matmul_step2_mac_3_U0.mac_sm_blk_n);
    assign proc_56_data_PIPO_blk[1] = 1'b0;
    assign proc_56_start_FIFO_blk[1] = 1'b0 | (~grp_dataflow_wrapper_fu_6443.task_compute_mlp_U0.grp_do_mlp_fu_4710.do_matmul_3_U0.start_for_do_adapt_12_U0_U.if_full_n & grp_dataflow_wrapper_fu_6443.task_compute_mlp_U0.grp_do_mlp_fu_4710.do_matmul_3_U0.matmul_step2_mac_3_U0.ap_start & ~grp_dataflow_wrapper_fu_6443.task_compute_mlp_U0.grp_do_mlp_fu_4710.do_matmul_3_U0.matmul_step2_mac_3_U0.real_start & (trans_in_cnt_36 == trans_out_cnt_36) & ~grp_dataflow_wrapper_fu_6443.task_compute_mlp_U0.grp_do_mlp_fu_4710.do_matmul_3_U0.start_for_do_adapt_12_U0_U.if_read);
    assign proc_56_TLF_FIFO_blk[1] = 1'b0;
    assign proc_56_input_sync_blk[1] = 1'b0;
    assign proc_56_output_sync_blk[1] = 1'b0;
    assign proc_dep_vld_vec_56[1] = dl_detect_out ? proc_dep_vld_vec_56_reg[1] : (proc_56_data_FIFO_blk[1] | proc_56_data_PIPO_blk[1] | proc_56_start_FIFO_blk[1] | proc_56_TLF_FIFO_blk[1] | proc_56_input_sync_blk[1] | proc_56_output_sync_blk[1]);
    always @ (negedge dl_reset or posedge dl_clock) begin
        if (~dl_reset) begin
            proc_dep_vld_vec_56_reg <= 'b0;
        end
        else begin
            proc_dep_vld_vec_56_reg <= proc_dep_vld_vec_56;
        end
    end
    assign in_chan_dep_vld_vec_56[0] = dep_chan_vld_55_56;
    assign in_chan_dep_data_vec_56[73 : 0] = dep_chan_data_55_56;
    assign token_in_vec_56[0] = token_55_56;
    assign in_chan_dep_vld_vec_56[1] = dep_chan_vld_57_56;
    assign in_chan_dep_data_vec_56[147 : 74] = dep_chan_data_57_56;
    assign token_in_vec_56[1] = token_57_56;
    assign dep_chan_vld_56_55 = out_chan_dep_vld_vec_56[0];
    assign dep_chan_data_56_55 = out_chan_dep_data_56;
    assign token_56_55 = token_out_vec_56[0];
    assign dep_chan_vld_56_57 = out_chan_dep_vld_vec_56[1];
    assign dep_chan_data_56_57 = out_chan_dep_data_56;
    assign token_56_57 = token_out_vec_56[1];

    // Process: grp_dataflow_wrapper_fu_6443.task_compute_mlp_U0.grp_do_mlp_fu_4710.do_matmul_3_U0.do_adapt_12_U0
    vit_block_top_hls_deadlock_detect_unit #(74, 57, 2, 2) vit_block_top_hls_deadlock_detect_unit_57 (
        .reset(dl_reset),
        .clock(dl_clock),
        .proc_dep_vld_vec(proc_dep_vld_vec_57),
        .in_chan_dep_vld_vec(in_chan_dep_vld_vec_57),
        .in_chan_dep_data_vec(in_chan_dep_data_vec_57),
        .token_in_vec(token_in_vec_57),
        .dl_detect_in(dl_detect_out),
        .origin(origin[57]),
        .token_clear(token_clear),
        .out_chan_dep_vld_vec(out_chan_dep_vld_vec_57),
        .out_chan_dep_data(out_chan_dep_data_57),
        .token_out_vec(token_out_vec_57),
        .dl_detect_out(dl_in_vec[57]));

    assign proc_57_data_FIFO_blk[0] = 1'b0 | (~grp_dataflow_wrapper_fu_6443.task_compute_mlp_U0.grp_do_mlp_fu_4710.do_matmul_3_U0.do_adapt_12_U0.mac_sm_blk_n);
    assign proc_57_data_PIPO_blk[0] = 1'b0;
    assign proc_57_start_FIFO_blk[0] = 1'b0 | (~grp_dataflow_wrapper_fu_6443.task_compute_mlp_U0.grp_do_mlp_fu_4710.do_matmul_3_U0.start_for_do_adapt_12_U0_U.if_empty_n & grp_dataflow_wrapper_fu_6443.task_compute_mlp_U0.grp_do_mlp_fu_4710.do_matmul_3_U0.do_adapt_12_U0.ap_idle & ~grp_dataflow_wrapper_fu_6443.task_compute_mlp_U0.grp_do_mlp_fu_4710.do_matmul_3_U0.start_for_do_adapt_12_U0_U.if_write);
    assign proc_57_TLF_FIFO_blk[0] = 1'b0;
    assign proc_57_input_sync_blk[0] = 1'b0;
    assign proc_57_output_sync_blk[0] = 1'b0;
    assign proc_dep_vld_vec_57[0] = dl_detect_out ? proc_dep_vld_vec_57_reg[0] : (proc_57_data_FIFO_blk[0] | proc_57_data_PIPO_blk[0] | proc_57_start_FIFO_blk[0] | proc_57_TLF_FIFO_blk[0] | proc_57_input_sync_blk[0] | proc_57_output_sync_blk[0]);
    assign proc_57_data_FIFO_blk[1] = 1'b0 | (~grp_dataflow_wrapper_fu_6443.task_compute_mlp_U0.grp_do_mlp_fu_4710.do_matmul_3_U0.do_adapt_12_U0.m1_sm_blk_n);
    assign proc_57_data_PIPO_blk[1] = 1'b0;
    assign proc_57_start_FIFO_blk[1] = 1'b0;
    assign proc_57_TLF_FIFO_blk[1] = 1'b0;
    assign proc_57_input_sync_blk[1] = 1'b0;
    assign proc_57_output_sync_blk[1] = 1'b0;
    assign proc_dep_vld_vec_57[1] = dl_detect_out ? proc_dep_vld_vec_57_reg[1] : (proc_57_data_FIFO_blk[1] | proc_57_data_PIPO_blk[1] | proc_57_start_FIFO_blk[1] | proc_57_TLF_FIFO_blk[1] | proc_57_input_sync_blk[1] | proc_57_output_sync_blk[1]);
    always @ (negedge dl_reset or posedge dl_clock) begin
        if (~dl_reset) begin
            proc_dep_vld_vec_57_reg <= 'b0;
        end
        else begin
            proc_dep_vld_vec_57_reg <= proc_dep_vld_vec_57;
        end
    end
    assign in_chan_dep_vld_vec_57[0] = dep_chan_vld_56_57;
    assign in_chan_dep_data_vec_57[73 : 0] = dep_chan_data_56_57;
    assign token_in_vec_57[0] = token_56_57;
    assign in_chan_dep_vld_vec_57[1] = dep_chan_vld_58_57;
    assign in_chan_dep_data_vec_57[147 : 74] = dep_chan_data_58_57;
    assign token_in_vec_57[1] = token_58_57;
    assign dep_chan_vld_57_56 = out_chan_dep_vld_vec_57[0];
    assign dep_chan_data_57_56 = out_chan_dep_data_57;
    assign token_57_56 = token_out_vec_57[0];
    assign dep_chan_vld_57_58 = out_chan_dep_vld_vec_57[1];
    assign dep_chan_data_57_58 = out_chan_dep_data_57;
    assign token_57_58 = token_out_vec_57[1];

    // Process: grp_dataflow_wrapper_fu_6443.task_compute_mlp_U0.grp_do_mlp_fu_4710.do_gelu_U0
    vit_block_top_hls_deadlock_detect_unit #(74, 58, 4, 4) vit_block_top_hls_deadlock_detect_unit_58 (
        .reset(dl_reset),
        .clock(dl_clock),
        .proc_dep_vld_vec(proc_dep_vld_vec_58),
        .in_chan_dep_vld_vec(in_chan_dep_vld_vec_58),
        .in_chan_dep_data_vec(in_chan_dep_data_vec_58),
        .token_in_vec(token_in_vec_58),
        .dl_detect_in(dl_detect_out),
        .origin(origin[58]),
        .token_clear(token_clear),
        .out_chan_dep_vld_vec(out_chan_dep_vld_vec_58),
        .out_chan_dep_data(out_chan_dep_data_58),
        .token_out_vec(token_out_vec_58),
        .dl_detect_out(dl_in_vec[58]));

    assign proc_58_data_FIFO_blk[0] = 1'b0 | (~grp_dataflow_wrapper_fu_6443.task_compute_mlp_U0.grp_do_mlp_fu_4710.do_gelu_U0.grp_do_gelu_Pipeline_TT_LOOP_CT_LOOP_fu_206.m1_sm_blk_n);
    assign proc_58_data_PIPO_blk[0] = 1'b0;
    assign proc_58_start_FIFO_blk[0] = 1'b0 | (~grp_dataflow_wrapper_fu_6443.task_compute_mlp_U0.grp_do_mlp_fu_4710.start_for_do_gelu_U0_U.if_empty_n & grp_dataflow_wrapper_fu_6443.task_compute_mlp_U0.grp_do_mlp_fu_4710.do_gelu_U0.ap_idle & ~grp_dataflow_wrapper_fu_6443.task_compute_mlp_U0.grp_do_mlp_fu_4710.start_for_do_gelu_U0_U.if_write);
    assign proc_58_TLF_FIFO_blk[0] = 1'b0;
    assign proc_58_input_sync_blk[0] = 1'b0;
    assign proc_58_output_sync_blk[0] = 1'b0;
    assign proc_dep_vld_vec_58[0] = dl_detect_out ? proc_dep_vld_vec_58_reg[0] : (proc_58_data_FIFO_blk[0] | proc_58_data_PIPO_blk[0] | proc_58_start_FIFO_blk[0] | proc_58_TLF_FIFO_blk[0] | proc_58_input_sync_blk[0] | proc_58_output_sync_blk[0]);
    assign proc_58_data_FIFO_blk[1] = 1'b0 | (~grp_dataflow_wrapper_fu_6443.task_compute_mlp_U0.grp_do_mlp_fu_4710.do_gelu_U0.grp_do_gelu_Pipeline_TT_LOOP_CT_LOOP_fu_206.m1_sm_blk_n);
    assign proc_58_data_PIPO_blk[1] = 1'b0;
    assign proc_58_start_FIFO_blk[1] = 1'b0;
    assign proc_58_TLF_FIFO_blk[1] = 1'b0;
    assign proc_58_input_sync_blk[1] = 1'b0;
    assign proc_58_output_sync_blk[1] = 1'b0;
    assign proc_dep_vld_vec_58[1] = dl_detect_out ? proc_dep_vld_vec_58_reg[1] : (proc_58_data_FIFO_blk[1] | proc_58_data_PIPO_blk[1] | proc_58_start_FIFO_blk[1] | proc_58_TLF_FIFO_blk[1] | proc_58_input_sync_blk[1] | proc_58_output_sync_blk[1]);
    assign proc_58_data_FIFO_blk[2] = 1'b0 | (~grp_dataflow_wrapper_fu_6443.task_compute_mlp_U0.grp_do_mlp_fu_4710.do_gelu_U0.grp_do_gelu_Pipeline_TT_LOOP_CT_LOOP_fu_206.ge_sm_blk_n);
    assign proc_58_data_PIPO_blk[2] = 1'b0;
    assign proc_58_start_FIFO_blk[2] = 1'b0 | (~grp_dataflow_wrapper_fu_6443.task_compute_mlp_U0.grp_do_mlp_fu_4710.start_for_do_matmul_U0_U.if_full_n & grp_dataflow_wrapper_fu_6443.task_compute_mlp_U0.grp_do_mlp_fu_4710.do_gelu_U0.ap_start & ~grp_dataflow_wrapper_fu_6443.task_compute_mlp_U0.grp_do_mlp_fu_4710.do_gelu_U0.real_start & (trans_in_cnt_38 == trans_out_cnt_38) & ~grp_dataflow_wrapper_fu_6443.task_compute_mlp_U0.grp_do_mlp_fu_4710.start_for_do_matmul_U0_U.if_read);
    assign proc_58_TLF_FIFO_blk[2] = 1'b0;
    assign proc_58_input_sync_blk[2] = 1'b0;
    assign proc_58_output_sync_blk[2] = 1'b0;
    assign proc_dep_vld_vec_58[2] = dl_detect_out ? proc_dep_vld_vec_58_reg[2] : (proc_58_data_FIFO_blk[2] | proc_58_data_PIPO_blk[2] | proc_58_start_FIFO_blk[2] | proc_58_TLF_FIFO_blk[2] | proc_58_input_sync_blk[2] | proc_58_output_sync_blk[2]);
    assign proc_58_data_FIFO_blk[3] = 1'b0 | (~grp_dataflow_wrapper_fu_6443.task_compute_mlp_U0.grp_do_mlp_fu_4710.do_gelu_U0.grp_do_gelu_Pipeline_TT_LOOP_CT_LOOP_fu_206.ge_sm_blk_n);
    assign proc_58_data_PIPO_blk[3] = 1'b0;
    assign proc_58_start_FIFO_blk[3] = 1'b0;
    assign proc_58_TLF_FIFO_blk[3] = 1'b0;
    assign proc_58_input_sync_blk[3] = 1'b0;
    assign proc_58_output_sync_blk[3] = 1'b0;
    assign proc_dep_vld_vec_58[3] = dl_detect_out ? proc_dep_vld_vec_58_reg[3] : (proc_58_data_FIFO_blk[3] | proc_58_data_PIPO_blk[3] | proc_58_start_FIFO_blk[3] | proc_58_TLF_FIFO_blk[3] | proc_58_input_sync_blk[3] | proc_58_output_sync_blk[3]);
    always @ (negedge dl_reset or posedge dl_clock) begin
        if (~dl_reset) begin
            proc_dep_vld_vec_58_reg <= 'b0;
        end
        else begin
            proc_dep_vld_vec_58_reg <= proc_dep_vld_vec_58;
        end
    end
    assign in_chan_dep_vld_vec_58[0] = dep_chan_vld_53_58;
    assign in_chan_dep_data_vec_58[73 : 0] = dep_chan_data_53_58;
    assign token_in_vec_58[0] = token_53_58;
    assign in_chan_dep_vld_vec_58[1] = dep_chan_vld_57_58;
    assign in_chan_dep_data_vec_58[147 : 74] = dep_chan_data_57_58;
    assign token_in_vec_58[1] = token_57_58;
    assign in_chan_dep_vld_vec_58[2] = dep_chan_vld_59_58;
    assign in_chan_dep_data_vec_58[221 : 148] = dep_chan_data_59_58;
    assign token_in_vec_58[2] = token_59_58;
    assign in_chan_dep_vld_vec_58[3] = dep_chan_vld_60_58;
    assign in_chan_dep_data_vec_58[295 : 222] = dep_chan_data_60_58;
    assign token_in_vec_58[3] = token_60_58;
    assign dep_chan_vld_58_53 = out_chan_dep_vld_vec_58[0];
    assign dep_chan_data_58_53 = out_chan_dep_data_58;
    assign token_58_53 = token_out_vec_58[0];
    assign dep_chan_vld_58_57 = out_chan_dep_vld_vec_58[1];
    assign dep_chan_data_58_57 = out_chan_dep_data_58;
    assign token_58_57 = token_out_vec_58[1];
    assign dep_chan_vld_58_59 = out_chan_dep_vld_vec_58[2];
    assign dep_chan_data_58_59 = out_chan_dep_data_58;
    assign token_58_59 = token_out_vec_58[2];
    assign dep_chan_vld_58_60 = out_chan_dep_vld_vec_58[3];
    assign dep_chan_data_58_60 = out_chan_dep_data_58;
    assign token_58_60 = token_out_vec_58[3];

    // Process: grp_dataflow_wrapper_fu_6443.task_compute_mlp_U0.grp_do_mlp_fu_4710.do_matmul_U0
    vit_block_top_hls_deadlock_detect_unit #(74, 59, 2, 2) vit_block_top_hls_deadlock_detect_unit_59 (
        .reset(dl_reset),
        .clock(dl_clock),
        .proc_dep_vld_vec(proc_dep_vld_vec_59),
        .in_chan_dep_vld_vec(in_chan_dep_vld_vec_59),
        .in_chan_dep_data_vec(in_chan_dep_data_vec_59),
        .token_in_vec(token_in_vec_59),
        .dl_detect_in(dl_detect_out),
        .origin(origin[59]),
        .token_clear(token_clear),
        .out_chan_dep_vld_vec(out_chan_dep_vld_vec_59),
        .out_chan_dep_data(out_chan_dep_data_59),
        .token_out_vec(token_out_vec_59),
        .dl_detect_out(dl_in_vec[59]));

    assign proc_59_data_FIFO_blk[0] = 1'b0 | (~grp_dataflow_wrapper_fu_6443.task_compute_mlp_U0.grp_do_mlp_fu_4710.do_matmul_U0.do_adapt_U0.ge_sm_blk_n);
    assign proc_59_data_PIPO_blk[0] = 1'b0;
    assign proc_59_start_FIFO_blk[0] = 1'b0 | (~grp_dataflow_wrapper_fu_6443.task_compute_mlp_U0.grp_do_mlp_fu_4710.start_for_do_matmul_U0_U.if_empty_n & grp_dataflow_wrapper_fu_6443.task_compute_mlp_U0.grp_do_mlp_fu_4710.do_matmul_U0.ap_idle & ~grp_dataflow_wrapper_fu_6443.task_compute_mlp_U0.grp_do_mlp_fu_4710.start_for_do_matmul_U0_U.if_write);
    assign proc_59_TLF_FIFO_blk[0] = 1'b0;
    assign proc_59_input_sync_blk[0] = 1'b0;
    assign proc_59_output_sync_blk[0] = 1'b0;
    assign proc_dep_vld_vec_59[0] = dl_detect_out ? proc_dep_vld_vec_59_reg[0] : (proc_59_data_FIFO_blk[0] | proc_59_data_PIPO_blk[0] | proc_59_start_FIFO_blk[0] | proc_59_TLF_FIFO_blk[0] | proc_59_input_sync_blk[0] | proc_59_output_sync_blk[0]);
    assign proc_59_data_FIFO_blk[1] = 1'b0 | (~grp_dataflow_wrapper_fu_6443.task_compute_mlp_U0.grp_do_mlp_fu_4710.do_matmul_U0.do_adapt_8_U0.m2_sm_blk_n);
    assign proc_59_data_PIPO_blk[1] = 1'b0;
    assign proc_59_start_FIFO_blk[1] = 1'b0;
    assign proc_59_TLF_FIFO_blk[1] = 1'b0;
    assign proc_59_input_sync_blk[1] = 1'b0;
    assign proc_59_output_sync_blk[1] = 1'b0;
    assign proc_dep_vld_vec_59[1] = dl_detect_out ? proc_dep_vld_vec_59_reg[1] : (proc_59_data_FIFO_blk[1] | proc_59_data_PIPO_blk[1] | proc_59_start_FIFO_blk[1] | proc_59_TLF_FIFO_blk[1] | proc_59_input_sync_blk[1] | proc_59_output_sync_blk[1]);
    always @ (negedge dl_reset or posedge dl_clock) begin
        if (~dl_reset) begin
            proc_dep_vld_vec_59_reg <= 'b0;
        end
        else begin
            proc_dep_vld_vec_59_reg <= proc_dep_vld_vec_59;
        end
    end
    assign in_chan_dep_vld_vec_59[0] = dep_chan_vld_58_59;
    assign in_chan_dep_data_vec_59[73 : 0] = dep_chan_data_58_59;
    assign token_in_vec_59[0] = token_58_59;
    assign in_chan_dep_vld_vec_59[1] = dep_chan_vld_64_59;
    assign in_chan_dep_data_vec_59[147 : 74] = dep_chan_data_64_59;
    assign token_in_vec_59[1] = token_64_59;
    assign dep_chan_vld_59_58 = out_chan_dep_vld_vec_59[0];
    assign dep_chan_data_59_58 = out_chan_dep_data_59;
    assign token_59_58 = token_out_vec_59[0];
    assign dep_chan_vld_59_64 = out_chan_dep_vld_vec_59[1];
    assign dep_chan_data_59_64 = out_chan_dep_data_59;
    assign token_59_64 = token_out_vec_59[1];

    // Process: grp_dataflow_wrapper_fu_6443.task_compute_mlp_U0.grp_do_mlp_fu_4710.do_matmul_U0.do_adapt_U0
    vit_block_top_hls_deadlock_detect_unit #(74, 60, 2, 2) vit_block_top_hls_deadlock_detect_unit_60 (
        .reset(dl_reset),
        .clock(dl_clock),
        .proc_dep_vld_vec(proc_dep_vld_vec_60),
        .in_chan_dep_vld_vec(in_chan_dep_vld_vec_60),
        .in_chan_dep_data_vec(in_chan_dep_data_vec_60),
        .token_in_vec(token_in_vec_60),
        .dl_detect_in(dl_detect_out),
        .origin(origin[60]),
        .token_clear(token_clear),
        .out_chan_dep_vld_vec(out_chan_dep_vld_vec_60),
        .out_chan_dep_data(out_chan_dep_data_60),
        .token_out_vec(token_out_vec_60),
        .dl_detect_out(dl_in_vec[60]));

    assign proc_60_data_FIFO_blk[0] = 1'b0 | (~grp_dataflow_wrapper_fu_6443.task_compute_mlp_U0.grp_do_mlp_fu_4710.do_matmul_U0.do_adapt_U0.ge_sm_blk_n);
    assign proc_60_data_PIPO_blk[0] = 1'b0;
    assign proc_60_start_FIFO_blk[0] = 1'b0;
    assign proc_60_TLF_FIFO_blk[0] = 1'b0;
    assign proc_60_input_sync_blk[0] = 1'b0;
    assign proc_60_output_sync_blk[0] = 1'b0;
    assign proc_dep_vld_vec_60[0] = dl_detect_out ? proc_dep_vld_vec_60_reg[0] : (proc_60_data_FIFO_blk[0] | proc_60_data_PIPO_blk[0] | proc_60_start_FIFO_blk[0] | proc_60_TLF_FIFO_blk[0] | proc_60_input_sync_blk[0] | proc_60_output_sync_blk[0]);
    assign proc_60_data_FIFO_blk[1] = 1'b0 | (~grp_dataflow_wrapper_fu_6443.task_compute_mlp_U0.grp_do_mlp_fu_4710.do_matmul_U0.do_adapt_U0.adpt_sm_blk_n);
    assign proc_60_data_PIPO_blk[1] = 1'b0;
    assign proc_60_start_FIFO_blk[1] = 1'b0 | (~grp_dataflow_wrapper_fu_6443.task_compute_mlp_U0.grp_do_mlp_fu_4710.do_matmul_U0.start_for_matmul_step1_cache_window_U0_U.if_full_n & grp_dataflow_wrapper_fu_6443.task_compute_mlp_U0.grp_do_mlp_fu_4710.do_matmul_U0.do_adapt_U0.ap_start & ~grp_dataflow_wrapper_fu_6443.task_compute_mlp_U0.grp_do_mlp_fu_4710.do_matmul_U0.do_adapt_U0.real_start & (trans_in_cnt_39 == trans_out_cnt_39) & ~grp_dataflow_wrapper_fu_6443.task_compute_mlp_U0.grp_do_mlp_fu_4710.do_matmul_U0.start_for_matmul_step1_cache_window_U0_U.if_read);
    assign proc_60_TLF_FIFO_blk[1] = 1'b0;
    assign proc_60_input_sync_blk[1] = 1'b0;
    assign proc_60_output_sync_blk[1] = 1'b0;
    assign proc_dep_vld_vec_60[1] = dl_detect_out ? proc_dep_vld_vec_60_reg[1] : (proc_60_data_FIFO_blk[1] | proc_60_data_PIPO_blk[1] | proc_60_start_FIFO_blk[1] | proc_60_TLF_FIFO_blk[1] | proc_60_input_sync_blk[1] | proc_60_output_sync_blk[1]);
    always @ (negedge dl_reset or posedge dl_clock) begin
        if (~dl_reset) begin
            proc_dep_vld_vec_60_reg <= 'b0;
        end
        else begin
            proc_dep_vld_vec_60_reg <= proc_dep_vld_vec_60;
        end
    end
    assign in_chan_dep_vld_vec_60[0] = dep_chan_vld_58_60;
    assign in_chan_dep_data_vec_60[73 : 0] = dep_chan_data_58_60;
    assign token_in_vec_60[0] = token_58_60;
    assign in_chan_dep_vld_vec_60[1] = dep_chan_vld_61_60;
    assign in_chan_dep_data_vec_60[147 : 74] = dep_chan_data_61_60;
    assign token_in_vec_60[1] = token_61_60;
    assign dep_chan_vld_60_58 = out_chan_dep_vld_vec_60[0];
    assign dep_chan_data_60_58 = out_chan_dep_data_60;
    assign token_60_58 = token_out_vec_60[0];
    assign dep_chan_vld_60_61 = out_chan_dep_vld_vec_60[1];
    assign dep_chan_data_60_61 = out_chan_dep_data_60;
    assign token_60_61 = token_out_vec_60[1];

    // Process: grp_dataflow_wrapper_fu_6443.task_compute_mlp_U0.grp_do_mlp_fu_4710.do_matmul_U0.matmul_step1_cache_window_U0
    vit_block_top_hls_deadlock_detect_unit #(74, 61, 2, 2) vit_block_top_hls_deadlock_detect_unit_61 (
        .reset(dl_reset),
        .clock(dl_clock),
        .proc_dep_vld_vec(proc_dep_vld_vec_61),
        .in_chan_dep_vld_vec(in_chan_dep_vld_vec_61),
        .in_chan_dep_data_vec(in_chan_dep_data_vec_61),
        .token_in_vec(token_in_vec_61),
        .dl_detect_in(dl_detect_out),
        .origin(origin[61]),
        .token_clear(token_clear),
        .out_chan_dep_vld_vec(out_chan_dep_vld_vec_61),
        .out_chan_dep_data(out_chan_dep_data_61),
        .token_out_vec(token_out_vec_61),
        .dl_detect_out(dl_in_vec[61]));

    assign proc_61_data_FIFO_blk[0] = 1'b0 | (~grp_dataflow_wrapper_fu_6443.task_compute_mlp_U0.grp_do_mlp_fu_4710.do_matmul_U0.matmul_step1_cache_window_U0.adpt_sm_blk_n);
    assign proc_61_data_PIPO_blk[0] = 1'b0;
    assign proc_61_start_FIFO_blk[0] = 1'b0 | (~grp_dataflow_wrapper_fu_6443.task_compute_mlp_U0.grp_do_mlp_fu_4710.do_matmul_U0.start_for_matmul_step1_cache_window_U0_U.if_empty_n & grp_dataflow_wrapper_fu_6443.task_compute_mlp_U0.grp_do_mlp_fu_4710.do_matmul_U0.matmul_step1_cache_window_U0.ap_idle & ~grp_dataflow_wrapper_fu_6443.task_compute_mlp_U0.grp_do_mlp_fu_4710.do_matmul_U0.start_for_matmul_step1_cache_window_U0_U.if_write);
    assign proc_61_TLF_FIFO_blk[0] = 1'b0;
    assign proc_61_input_sync_blk[0] = 1'b0;
    assign proc_61_output_sync_blk[0] = 1'b0;
    assign proc_dep_vld_vec_61[0] = dl_detect_out ? proc_dep_vld_vec_61_reg[0] : (proc_61_data_FIFO_blk[0] | proc_61_data_PIPO_blk[0] | proc_61_start_FIFO_blk[0] | proc_61_TLF_FIFO_blk[0] | proc_61_input_sync_blk[0] | proc_61_output_sync_blk[0]);
    assign proc_61_data_FIFO_blk[1] = 1'b0 | (~grp_dataflow_wrapper_fu_6443.task_compute_mlp_U0.grp_do_mlp_fu_4710.do_matmul_U0.matmul_step1_cache_window_U0.cache_window_sm_blk_n);
    assign proc_61_data_PIPO_blk[1] = 1'b0;
    assign proc_61_start_FIFO_blk[1] = 1'b0 | (~grp_dataflow_wrapper_fu_6443.task_compute_mlp_U0.grp_do_mlp_fu_4710.do_matmul_U0.start_for_matmul_step2_mac_U0_U.if_full_n & grp_dataflow_wrapper_fu_6443.task_compute_mlp_U0.grp_do_mlp_fu_4710.do_matmul_U0.matmul_step1_cache_window_U0.ap_start & ~grp_dataflow_wrapper_fu_6443.task_compute_mlp_U0.grp_do_mlp_fu_4710.do_matmul_U0.matmul_step1_cache_window_U0.real_start & (trans_in_cnt_40 == trans_out_cnt_40) & ~grp_dataflow_wrapper_fu_6443.task_compute_mlp_U0.grp_do_mlp_fu_4710.do_matmul_U0.start_for_matmul_step2_mac_U0_U.if_read);
    assign proc_61_TLF_FIFO_blk[1] = 1'b0;
    assign proc_61_input_sync_blk[1] = 1'b0;
    assign proc_61_output_sync_blk[1] = 1'b0;
    assign proc_dep_vld_vec_61[1] = dl_detect_out ? proc_dep_vld_vec_61_reg[1] : (proc_61_data_FIFO_blk[1] | proc_61_data_PIPO_blk[1] | proc_61_start_FIFO_blk[1] | proc_61_TLF_FIFO_blk[1] | proc_61_input_sync_blk[1] | proc_61_output_sync_blk[1]);
    always @ (negedge dl_reset or posedge dl_clock) begin
        if (~dl_reset) begin
            proc_dep_vld_vec_61_reg <= 'b0;
        end
        else begin
            proc_dep_vld_vec_61_reg <= proc_dep_vld_vec_61;
        end
    end
    assign in_chan_dep_vld_vec_61[0] = dep_chan_vld_60_61;
    assign in_chan_dep_data_vec_61[73 : 0] = dep_chan_data_60_61;
    assign token_in_vec_61[0] = token_60_61;
    assign in_chan_dep_vld_vec_61[1] = dep_chan_vld_62_61;
    assign in_chan_dep_data_vec_61[147 : 74] = dep_chan_data_62_61;
    assign token_in_vec_61[1] = token_62_61;
    assign dep_chan_vld_61_60 = out_chan_dep_vld_vec_61[0];
    assign dep_chan_data_61_60 = out_chan_dep_data_61;
    assign token_61_60 = token_out_vec_61[0];
    assign dep_chan_vld_61_62 = out_chan_dep_vld_vec_61[1];
    assign dep_chan_data_61_62 = out_chan_dep_data_61;
    assign token_61_62 = token_out_vec_61[1];

    // Process: grp_dataflow_wrapper_fu_6443.task_compute_mlp_U0.grp_do_mlp_fu_4710.do_matmul_U0.matmul_step2_mac_U0
    vit_block_top_hls_deadlock_detect_unit #(74, 62, 2, 2) vit_block_top_hls_deadlock_detect_unit_62 (
        .reset(dl_reset),
        .clock(dl_clock),
        .proc_dep_vld_vec(proc_dep_vld_vec_62),
        .in_chan_dep_vld_vec(in_chan_dep_vld_vec_62),
        .in_chan_dep_data_vec(in_chan_dep_data_vec_62),
        .token_in_vec(token_in_vec_62),
        .dl_detect_in(dl_detect_out),
        .origin(origin[62]),
        .token_clear(token_clear),
        .out_chan_dep_vld_vec(out_chan_dep_vld_vec_62),
        .out_chan_dep_data(out_chan_dep_data_62),
        .token_out_vec(token_out_vec_62),
        .dl_detect_out(dl_in_vec[62]));

    assign proc_62_data_FIFO_blk[0] = 1'b0 | (~grp_dataflow_wrapper_fu_6443.task_compute_mlp_U0.grp_do_mlp_fu_4710.do_matmul_U0.matmul_step2_mac_U0.cache_window_sm_blk_n);
    assign proc_62_data_PIPO_blk[0] = 1'b0;
    assign proc_62_start_FIFO_blk[0] = 1'b0 | (~grp_dataflow_wrapper_fu_6443.task_compute_mlp_U0.grp_do_mlp_fu_4710.do_matmul_U0.start_for_matmul_step2_mac_U0_U.if_empty_n & grp_dataflow_wrapper_fu_6443.task_compute_mlp_U0.grp_do_mlp_fu_4710.do_matmul_U0.matmul_step2_mac_U0.ap_idle & ~grp_dataflow_wrapper_fu_6443.task_compute_mlp_U0.grp_do_mlp_fu_4710.do_matmul_U0.start_for_matmul_step2_mac_U0_U.if_write);
    assign proc_62_TLF_FIFO_blk[0] = 1'b0;
    assign proc_62_input_sync_blk[0] = 1'b0;
    assign proc_62_output_sync_blk[0] = 1'b0;
    assign proc_dep_vld_vec_62[0] = dl_detect_out ? proc_dep_vld_vec_62_reg[0] : (proc_62_data_FIFO_blk[0] | proc_62_data_PIPO_blk[0] | proc_62_start_FIFO_blk[0] | proc_62_TLF_FIFO_blk[0] | proc_62_input_sync_blk[0] | proc_62_output_sync_blk[0]);
    assign proc_62_data_FIFO_blk[1] = 1'b0 | (~grp_dataflow_wrapper_fu_6443.task_compute_mlp_U0.grp_do_mlp_fu_4710.do_matmul_U0.matmul_step2_mac_U0.mac_sm_blk_n);
    assign proc_62_data_PIPO_blk[1] = 1'b0;
    assign proc_62_start_FIFO_blk[1] = 1'b0 | (~grp_dataflow_wrapper_fu_6443.task_compute_mlp_U0.grp_do_mlp_fu_4710.do_matmul_U0.start_for_do_adapt_8_U0_U.if_full_n & grp_dataflow_wrapper_fu_6443.task_compute_mlp_U0.grp_do_mlp_fu_4710.do_matmul_U0.matmul_step2_mac_U0.ap_start & ~grp_dataflow_wrapper_fu_6443.task_compute_mlp_U0.grp_do_mlp_fu_4710.do_matmul_U0.matmul_step2_mac_U0.real_start & (trans_in_cnt_41 == trans_out_cnt_41) & ~grp_dataflow_wrapper_fu_6443.task_compute_mlp_U0.grp_do_mlp_fu_4710.do_matmul_U0.start_for_do_adapt_8_U0_U.if_read);
    assign proc_62_TLF_FIFO_blk[1] = 1'b0;
    assign proc_62_input_sync_blk[1] = 1'b0;
    assign proc_62_output_sync_blk[1] = 1'b0;
    assign proc_dep_vld_vec_62[1] = dl_detect_out ? proc_dep_vld_vec_62_reg[1] : (proc_62_data_FIFO_blk[1] | proc_62_data_PIPO_blk[1] | proc_62_start_FIFO_blk[1] | proc_62_TLF_FIFO_blk[1] | proc_62_input_sync_blk[1] | proc_62_output_sync_blk[1]);
    always @ (negedge dl_reset or posedge dl_clock) begin
        if (~dl_reset) begin
            proc_dep_vld_vec_62_reg <= 'b0;
        end
        else begin
            proc_dep_vld_vec_62_reg <= proc_dep_vld_vec_62;
        end
    end
    assign in_chan_dep_vld_vec_62[0] = dep_chan_vld_61_62;
    assign in_chan_dep_data_vec_62[73 : 0] = dep_chan_data_61_62;
    assign token_in_vec_62[0] = token_61_62;
    assign in_chan_dep_vld_vec_62[1] = dep_chan_vld_63_62;
    assign in_chan_dep_data_vec_62[147 : 74] = dep_chan_data_63_62;
    assign token_in_vec_62[1] = token_63_62;
    assign dep_chan_vld_62_61 = out_chan_dep_vld_vec_62[0];
    assign dep_chan_data_62_61 = out_chan_dep_data_62;
    assign token_62_61 = token_out_vec_62[0];
    assign dep_chan_vld_62_63 = out_chan_dep_vld_vec_62[1];
    assign dep_chan_data_62_63 = out_chan_dep_data_62;
    assign token_62_63 = token_out_vec_62[1];

    // Process: grp_dataflow_wrapper_fu_6443.task_compute_mlp_U0.grp_do_mlp_fu_4710.do_matmul_U0.do_adapt_8_U0
    vit_block_top_hls_deadlock_detect_unit #(74, 63, 2, 2) vit_block_top_hls_deadlock_detect_unit_63 (
        .reset(dl_reset),
        .clock(dl_clock),
        .proc_dep_vld_vec(proc_dep_vld_vec_63),
        .in_chan_dep_vld_vec(in_chan_dep_vld_vec_63),
        .in_chan_dep_data_vec(in_chan_dep_data_vec_63),
        .token_in_vec(token_in_vec_63),
        .dl_detect_in(dl_detect_out),
        .origin(origin[63]),
        .token_clear(token_clear),
        .out_chan_dep_vld_vec(out_chan_dep_vld_vec_63),
        .out_chan_dep_data(out_chan_dep_data_63),
        .token_out_vec(token_out_vec_63),
        .dl_detect_out(dl_in_vec[63]));

    assign proc_63_data_FIFO_blk[0] = 1'b0 | (~grp_dataflow_wrapper_fu_6443.task_compute_mlp_U0.grp_do_mlp_fu_4710.do_matmul_U0.do_adapt_8_U0.mac_sm_blk_n);
    assign proc_63_data_PIPO_blk[0] = 1'b0;
    assign proc_63_start_FIFO_blk[0] = 1'b0 | (~grp_dataflow_wrapper_fu_6443.task_compute_mlp_U0.grp_do_mlp_fu_4710.do_matmul_U0.start_for_do_adapt_8_U0_U.if_empty_n & grp_dataflow_wrapper_fu_6443.task_compute_mlp_U0.grp_do_mlp_fu_4710.do_matmul_U0.do_adapt_8_U0.ap_idle & ~grp_dataflow_wrapper_fu_6443.task_compute_mlp_U0.grp_do_mlp_fu_4710.do_matmul_U0.start_for_do_adapt_8_U0_U.if_write);
    assign proc_63_TLF_FIFO_blk[0] = 1'b0;
    assign proc_63_input_sync_blk[0] = 1'b0;
    assign proc_63_output_sync_blk[0] = 1'b0;
    assign proc_dep_vld_vec_63[0] = dl_detect_out ? proc_dep_vld_vec_63_reg[0] : (proc_63_data_FIFO_blk[0] | proc_63_data_PIPO_blk[0] | proc_63_start_FIFO_blk[0] | proc_63_TLF_FIFO_blk[0] | proc_63_input_sync_blk[0] | proc_63_output_sync_blk[0]);
    assign proc_63_data_FIFO_blk[1] = 1'b0 | (~grp_dataflow_wrapper_fu_6443.task_compute_mlp_U0.grp_do_mlp_fu_4710.do_matmul_U0.do_adapt_8_U0.m2_sm_blk_n);
    assign proc_63_data_PIPO_blk[1] = 1'b0;
    assign proc_63_start_FIFO_blk[1] = 1'b0;
    assign proc_63_TLF_FIFO_blk[1] = 1'b0;
    assign proc_63_input_sync_blk[1] = 1'b0;
    assign proc_63_output_sync_blk[1] = 1'b0;
    assign proc_dep_vld_vec_63[1] = dl_detect_out ? proc_dep_vld_vec_63_reg[1] : (proc_63_data_FIFO_blk[1] | proc_63_data_PIPO_blk[1] | proc_63_start_FIFO_blk[1] | proc_63_TLF_FIFO_blk[1] | proc_63_input_sync_blk[1] | proc_63_output_sync_blk[1]);
    always @ (negedge dl_reset or posedge dl_clock) begin
        if (~dl_reset) begin
            proc_dep_vld_vec_63_reg <= 'b0;
        end
        else begin
            proc_dep_vld_vec_63_reg <= proc_dep_vld_vec_63;
        end
    end
    assign in_chan_dep_vld_vec_63[0] = dep_chan_vld_62_63;
    assign in_chan_dep_data_vec_63[73 : 0] = dep_chan_data_62_63;
    assign token_in_vec_63[0] = token_62_63;
    assign in_chan_dep_vld_vec_63[1] = dep_chan_vld_64_63;
    assign in_chan_dep_data_vec_63[147 : 74] = dep_chan_data_64_63;
    assign token_in_vec_63[1] = token_64_63;
    assign dep_chan_vld_63_62 = out_chan_dep_vld_vec_63[0];
    assign dep_chan_data_63_62 = out_chan_dep_data_63;
    assign token_63_62 = token_out_vec_63[0];
    assign dep_chan_vld_63_64 = out_chan_dep_vld_vec_63[1];
    assign dep_chan_data_63_64 = out_chan_dep_data_63;
    assign token_63_64 = token_out_vec_63[1];

    // Process: grp_dataflow_wrapper_fu_6443.task_compute_mlp_U0.grp_do_mlp_fu_4710.stream_merge_U0
    vit_block_top_hls_deadlock_detect_unit #(74, 64, 3, 3) vit_block_top_hls_deadlock_detect_unit_64 (
        .reset(dl_reset),
        .clock(dl_clock),
        .proc_dep_vld_vec(proc_dep_vld_vec_64),
        .in_chan_dep_vld_vec(in_chan_dep_vld_vec_64),
        .in_chan_dep_data_vec(in_chan_dep_data_vec_64),
        .token_in_vec(token_in_vec_64),
        .dl_detect_in(dl_detect_out),
        .origin(origin[64]),
        .token_clear(token_clear),
        .out_chan_dep_vld_vec(out_chan_dep_vld_vec_64),
        .out_chan_dep_data(out_chan_dep_data_64),
        .token_out_vec(token_out_vec_64),
        .dl_detect_out(dl_in_vec[64]));

    assign proc_64_data_FIFO_blk[0] = 1'b0 | (~grp_dataflow_wrapper_fu_6443.task_compute_mlp_U0.grp_do_mlp_fu_4710.stream_merge_U0.grp_stream_merge_Pipeline_VITIS_LOOP_393_1_VITIS_LOOP_394_2_fu_34.resi_o_sm_blk_n);
    assign proc_64_data_PIPO_blk[0] = 1'b0;
    assign proc_64_start_FIFO_blk[0] = 1'b0 | (~grp_dataflow_wrapper_fu_6443.task_compute_mlp_U0.grp_do_mlp_fu_4710.start_for_stream_merge_U0_U.if_empty_n & grp_dataflow_wrapper_fu_6443.task_compute_mlp_U0.grp_do_mlp_fu_4710.stream_merge_U0.ap_idle & ~grp_dataflow_wrapper_fu_6443.task_compute_mlp_U0.grp_do_mlp_fu_4710.start_for_stream_merge_U0_U.if_write);
    assign proc_64_TLF_FIFO_blk[0] = 1'b0;
    assign proc_64_input_sync_blk[0] = 1'b0;
    assign proc_64_output_sync_blk[0] = 1'b0;
    assign proc_dep_vld_vec_64[0] = dl_detect_out ? proc_dep_vld_vec_64_reg[0] : (proc_64_data_FIFO_blk[0] | proc_64_data_PIPO_blk[0] | proc_64_start_FIFO_blk[0] | proc_64_TLF_FIFO_blk[0] | proc_64_input_sync_blk[0] | proc_64_output_sync_blk[0]);
    assign proc_64_data_FIFO_blk[1] = 1'b0 | (~grp_dataflow_wrapper_fu_6443.task_compute_mlp_U0.grp_do_mlp_fu_4710.stream_merge_U0.grp_stream_merge_Pipeline_VITIS_LOOP_393_1_VITIS_LOOP_394_2_fu_34.m2_sm_blk_n);
    assign proc_64_data_PIPO_blk[1] = 1'b0;
    assign proc_64_start_FIFO_blk[1] = 1'b0;
    assign proc_64_TLF_FIFO_blk[1] = 1'b0;
    assign proc_64_input_sync_blk[1] = 1'b0;
    assign proc_64_output_sync_blk[1] = 1'b0;
    assign proc_dep_vld_vec_64[1] = dl_detect_out ? proc_dep_vld_vec_64_reg[1] : (proc_64_data_FIFO_blk[1] | proc_64_data_PIPO_blk[1] | proc_64_start_FIFO_blk[1] | proc_64_TLF_FIFO_blk[1] | proc_64_input_sync_blk[1] | proc_64_output_sync_blk[1]);
    assign proc_64_data_FIFO_blk[2] = 1'b0 | (~grp_dataflow_wrapper_fu_6443.task_compute_mlp_U0.grp_do_mlp_fu_4710.stream_merge_U0.grp_stream_merge_Pipeline_VITIS_LOOP_393_1_VITIS_LOOP_394_2_fu_34.m2_sm_blk_n);
    assign proc_64_data_PIPO_blk[2] = 1'b0;
    assign proc_64_start_FIFO_blk[2] = 1'b0;
    assign proc_64_TLF_FIFO_blk[2] = 1'b0;
    assign proc_64_input_sync_blk[2] = 1'b0;
    assign proc_64_output_sync_blk[2] = 1'b0;
    assign proc_dep_vld_vec_64[2] = dl_detect_out ? proc_dep_vld_vec_64_reg[2] : (proc_64_data_FIFO_blk[2] | proc_64_data_PIPO_blk[2] | proc_64_start_FIFO_blk[2] | proc_64_TLF_FIFO_blk[2] | proc_64_input_sync_blk[2] | proc_64_output_sync_blk[2]);
    always @ (negedge dl_reset or posedge dl_clock) begin
        if (~dl_reset) begin
            proc_dep_vld_vec_64_reg <= 'b0;
        end
        else begin
            proc_dep_vld_vec_64_reg <= proc_dep_vld_vec_64;
        end
    end
    assign in_chan_dep_vld_vec_64[0] = dep_chan_vld_51_64;
    assign in_chan_dep_data_vec_64[73 : 0] = dep_chan_data_51_64;
    assign token_in_vec_64[0] = token_51_64;
    assign in_chan_dep_vld_vec_64[1] = dep_chan_vld_59_64;
    assign in_chan_dep_data_vec_64[147 : 74] = dep_chan_data_59_64;
    assign token_in_vec_64[1] = token_59_64;
    assign in_chan_dep_vld_vec_64[2] = dep_chan_vld_63_64;
    assign in_chan_dep_data_vec_64[221 : 148] = dep_chan_data_63_64;
    assign token_in_vec_64[2] = token_63_64;
    assign dep_chan_vld_64_51 = out_chan_dep_vld_vec_64[0];
    assign dep_chan_data_64_51 = out_chan_dep_data_64;
    assign token_64_51 = token_out_vec_64[0];
    assign dep_chan_vld_64_59 = out_chan_dep_vld_vec_64[1];
    assign dep_chan_data_64_59 = out_chan_dep_data_64;
    assign token_64_59 = token_out_vec_64[1];
    assign dep_chan_vld_64_63 = out_chan_dep_vld_vec_64[2];
    assign dep_chan_data_64_63 = out_chan_dep_data_64;
    assign token_64_63 = token_out_vec_64[2];

    // Process: grp_dataflow_wrapper_fu_6443.task_write_fm_U0
    vit_block_top_hls_deadlock_detect_unit #(74, 65, 2, 2) vit_block_top_hls_deadlock_detect_unit_65 (
        .reset(dl_reset),
        .clock(dl_clock),
        .proc_dep_vld_vec(proc_dep_vld_vec_65),
        .in_chan_dep_vld_vec(in_chan_dep_vld_vec_65),
        .in_chan_dep_data_vec(in_chan_dep_data_vec_65),
        .token_in_vec(token_in_vec_65),
        .dl_detect_in(dl_detect_out),
        .origin(origin[65]),
        .token_clear(token_clear),
        .out_chan_dep_vld_vec(out_chan_dep_vld_vec_65),
        .out_chan_dep_data(out_chan_dep_data_65),
        .token_out_vec(token_out_vec_65),
        .dl_detect_out(dl_in_vec[65]));

    assign proc_65_data_FIFO_blk[0] = 1'b0 | (~grp_dataflow_wrapper_fu_6443.task_write_fm_U0.o_stream_int_blk_n);
    assign proc_65_data_PIPO_blk[0] = 1'b0;
    assign proc_65_start_FIFO_blk[0] = 1'b0 | (~grp_dataflow_wrapper_fu_6443.start_for_task_write_fm_U0_U.if_empty_n & grp_dataflow_wrapper_fu_6443.task_write_fm_U0.ap_idle & ~grp_dataflow_wrapper_fu_6443.start_for_task_write_fm_U0_U.if_write);
    assign proc_65_TLF_FIFO_blk[0] = 1'b0;
    assign proc_65_input_sync_blk[0] = 1'b0;
    assign proc_65_output_sync_blk[0] = 1'b0;
    assign proc_dep_vld_vec_65[0] = dl_detect_out ? proc_dep_vld_vec_65_reg[0] : (proc_65_data_FIFO_blk[0] | proc_65_data_PIPO_blk[0] | proc_65_start_FIFO_blk[0] | proc_65_TLF_FIFO_blk[0] | proc_65_input_sync_blk[0] | proc_65_output_sync_blk[0]);
    assign proc_65_data_FIFO_blk[1] = 1'b0;
    assign proc_65_data_PIPO_blk[1] = 1'b0;
    assign proc_65_start_FIFO_blk[1] = 1'b0;
    assign proc_65_TLF_FIFO_blk[1] = 1'b0;
    assign proc_65_input_sync_blk[1] = 1'b0;
    assign proc_65_output_sync_blk[1] = 1'b0 | (ap_done_reg_5 & grp_dataflow_wrapper_fu_6443.task_write_fm_U0.ap_done & ~grp_dataflow_wrapper_fu_6443.task_load_weights_14_U0.ap_done);
    assign proc_dep_vld_vec_65[1] = dl_detect_out ? proc_dep_vld_vec_65_reg[1] : (proc_65_data_FIFO_blk[1] | proc_65_data_PIPO_blk[1] | proc_65_start_FIFO_blk[1] | proc_65_TLF_FIFO_blk[1] | proc_65_input_sync_blk[1] | proc_65_output_sync_blk[1]);
    always @ (negedge dl_reset or posedge dl_clock) begin
        if (~dl_reset) begin
            proc_dep_vld_vec_65_reg <= 'b0;
        end
        else begin
            proc_dep_vld_vec_65_reg <= proc_dep_vld_vec_65;
        end
    end
    assign in_chan_dep_vld_vec_65[0] = dep_chan_vld_48_65;
    assign in_chan_dep_data_vec_65[73 : 0] = dep_chan_data_48_65;
    assign token_in_vec_65[0] = token_48_65;
    assign in_chan_dep_vld_vec_65[1] = dep_chan_vld_66_65;
    assign in_chan_dep_data_vec_65[147 : 74] = dep_chan_data_66_65;
    assign token_in_vec_65[1] = token_66_65;
    assign dep_chan_vld_65_48 = out_chan_dep_vld_vec_65[0];
    assign dep_chan_data_65_48 = out_chan_dep_data_65;
    assign token_65_48 = token_out_vec_65[0];
    assign dep_chan_vld_65_66 = out_chan_dep_vld_vec_65[1];
    assign dep_chan_data_65_66 = out_chan_dep_data_65;
    assign token_65_66 = token_out_vec_65[1];

    // Process: grp_dataflow_wrapper_fu_6443.task_load_weights_14_U0
    vit_block_top_hls_deadlock_detect_unit #(74, 66, 1, 2) vit_block_top_hls_deadlock_detect_unit_66 (
        .reset(dl_reset),
        .clock(dl_clock),
        .proc_dep_vld_vec(proc_dep_vld_vec_66),
        .in_chan_dep_vld_vec(in_chan_dep_vld_vec_66),
        .in_chan_dep_data_vec(in_chan_dep_data_vec_66),
        .token_in_vec(token_in_vec_66),
        .dl_detect_in(dl_detect_out),
        .origin(origin[66]),
        .token_clear(token_clear),
        .out_chan_dep_vld_vec(out_chan_dep_vld_vec_66),
        .out_chan_dep_data(out_chan_dep_data_66),
        .token_out_vec(token_out_vec_66),
        .dl_detect_out(dl_in_vec[66]));

    assign proc_66_data_FIFO_blk[0] = 1'b0;
    assign proc_66_data_PIPO_blk[0] = 1'b0;
    assign proc_66_start_FIFO_blk[0] = 1'b0;
    assign proc_66_TLF_FIFO_blk[0] = 1'b0 | (~grp_dataflow_wrapper_fu_6443.add_loc_channel_U.if_empty_n & grp_dataflow_wrapper_fu_6443.task_load_weights_14_U0.ap_idle & ~grp_dataflow_wrapper_fu_6443.add_loc_channel_U.if_write);
    assign proc_66_input_sync_blk[0] = 1'b0;
    assign proc_66_output_sync_blk[0] = 1'b0;
    assign proc_dep_vld_vec_66[0] = dl_detect_out ? proc_dep_vld_vec_66_reg[0] : (proc_66_data_FIFO_blk[0] | proc_66_data_PIPO_blk[0] | proc_66_start_FIFO_blk[0] | proc_66_TLF_FIFO_blk[0] | proc_66_input_sync_blk[0] | proc_66_output_sync_blk[0]);
    assign proc_66_data_FIFO_blk[1] = 1'b0;
    assign proc_66_data_PIPO_blk[1] = 1'b0;
    assign proc_66_start_FIFO_blk[1] = 1'b0;
    assign proc_66_TLF_FIFO_blk[1] = 1'b0;
    assign proc_66_input_sync_blk[1] = 1'b0;
    assign proc_66_output_sync_blk[1] = 1'b0 | (ap_done_reg_2 & grp_dataflow_wrapper_fu_6443.task_load_weights_14_U0.ap_done & ~grp_dataflow_wrapper_fu_6443.task_write_fm_U0.ap_done);
    assign proc_dep_vld_vec_66[1] = dl_detect_out ? proc_dep_vld_vec_66_reg[1] : (proc_66_data_FIFO_blk[1] | proc_66_data_PIPO_blk[1] | proc_66_start_FIFO_blk[1] | proc_66_TLF_FIFO_blk[1] | proc_66_input_sync_blk[1] | proc_66_output_sync_blk[1]);
    always @ (negedge dl_reset or posedge dl_clock) begin
        if (~dl_reset) begin
            proc_dep_vld_vec_66_reg <= 'b0;
        end
        else begin
            proc_dep_vld_vec_66_reg <= proc_dep_vld_vec_66;
        end
    end
    assign in_chan_dep_vld_vec_66[0] = dep_chan_vld_65_66;
    assign in_chan_dep_data_vec_66[73 : 0] = dep_chan_data_65_66;
    assign token_in_vec_66[0] = token_65_66;
    assign dep_chan_vld_66_9 = out_chan_dep_vld_vec_66[0];
    assign dep_chan_data_66_9 = out_chan_dep_data_66;
    assign token_66_9 = token_out_vec_66[0];
    assign dep_chan_vld_66_65 = out_chan_dep_vld_vec_66[1];
    assign dep_chan_data_66_65 = out_chan_dep_data_66;
    assign token_66_65 = token_out_vec_66[1];

    // Process: grp_task_run_head_fu_11440.task_read_cls_fm_U0
    vit_block_top_hls_deadlock_detect_unit #(74, 67, 2, 2) vit_block_top_hls_deadlock_detect_unit_67 (
        .reset(dl_reset),
        .clock(dl_clock),
        .proc_dep_vld_vec(proc_dep_vld_vec_67),
        .in_chan_dep_vld_vec(in_chan_dep_vld_vec_67),
        .in_chan_dep_data_vec(in_chan_dep_data_vec_67),
        .token_in_vec(token_in_vec_67),
        .dl_detect_in(dl_detect_out),
        .origin(origin[67]),
        .token_clear(token_clear),
        .out_chan_dep_vld_vec(out_chan_dep_vld_vec_67),
        .out_chan_dep_data(out_chan_dep_data_67),
        .token_out_vec(token_out_vec_67),
        .dl_detect_out(dl_in_vec[67]));

    assign proc_67_data_FIFO_blk[0] = 1'b0 | (~grp_task_run_head_fu_11440.task_read_cls_fm_U0.head_in_sm_blk_n);
    assign proc_67_data_PIPO_blk[0] = 1'b0;
    assign proc_67_start_FIFO_blk[0] = 1'b0 | (~grp_task_run_head_fu_11440.start_for_fixed_head_do_head_U0_U.if_full_n & grp_task_run_head_fu_11440.task_read_cls_fm_U0.ap_start & ~grp_task_run_head_fu_11440.task_read_cls_fm_U0.real_start & (trans_in_cnt_44 == trans_out_cnt_44) & ~grp_task_run_head_fu_11440.start_for_fixed_head_do_head_U0_U.if_read);
    assign proc_67_TLF_FIFO_blk[0] = 1'b0;
    assign proc_67_input_sync_blk[0] = 1'b0;
    assign proc_67_output_sync_blk[0] = 1'b0;
    assign proc_dep_vld_vec_67[0] = dl_detect_out ? proc_dep_vld_vec_67_reg[0] : (proc_67_data_FIFO_blk[0] | proc_67_data_PIPO_blk[0] | proc_67_start_FIFO_blk[0] | proc_67_TLF_FIFO_blk[0] | proc_67_input_sync_blk[0] | proc_67_output_sync_blk[0]);
    assign proc_67_data_FIFO_blk[1] = 1'b0 | (~grp_task_run_head_fu_11440.task_read_cls_fm_U0.head_in_sm_blk_n);
    assign proc_67_data_PIPO_blk[1] = 1'b0;
    assign proc_67_start_FIFO_blk[1] = 1'b0;
    assign proc_67_TLF_FIFO_blk[1] = 1'b0;
    assign proc_67_input_sync_blk[1] = 1'b0;
    assign proc_67_output_sync_blk[1] = 1'b0;
    assign proc_dep_vld_vec_67[1] = dl_detect_out ? proc_dep_vld_vec_67_reg[1] : (proc_67_data_FIFO_blk[1] | proc_67_data_PIPO_blk[1] | proc_67_start_FIFO_blk[1] | proc_67_TLF_FIFO_blk[1] | proc_67_input_sync_blk[1] | proc_67_output_sync_blk[1]);
    always @ (negedge dl_reset or posedge dl_clock) begin
        if (~dl_reset) begin
            proc_dep_vld_vec_67_reg <= 'b0;
        end
        else begin
            proc_dep_vld_vec_67_reg <= proc_dep_vld_vec_67;
        end
    end
    assign in_chan_dep_vld_vec_67[0] = dep_chan_vld_68_67;
    assign in_chan_dep_data_vec_67[73 : 0] = dep_chan_data_68_67;
    assign token_in_vec_67[0] = token_68_67;
    assign in_chan_dep_vld_vec_67[1] = dep_chan_vld_69_67;
    assign in_chan_dep_data_vec_67[147 : 74] = dep_chan_data_69_67;
    assign token_in_vec_67[1] = token_69_67;
    assign dep_chan_vld_67_68 = out_chan_dep_vld_vec_67[0];
    assign dep_chan_data_67_68 = out_chan_dep_data_67;
    assign token_67_68 = token_out_vec_67[0];
    assign dep_chan_vld_67_69 = out_chan_dep_vld_vec_67[1];
    assign dep_chan_data_67_69 = out_chan_dep_data_67;
    assign token_67_69 = token_out_vec_67[1];

    // Process: grp_task_run_head_fu_11440.fixed_head_do_head_U0
    vit_block_top_hls_deadlock_detect_unit #(74, 68, 2, 2) vit_block_top_hls_deadlock_detect_unit_68 (
        .reset(dl_reset),
        .clock(dl_clock),
        .proc_dep_vld_vec(proc_dep_vld_vec_68),
        .in_chan_dep_vld_vec(in_chan_dep_vld_vec_68),
        .in_chan_dep_data_vec(in_chan_dep_data_vec_68),
        .token_in_vec(token_in_vec_68),
        .dl_detect_in(dl_detect_out),
        .origin(origin[68]),
        .token_clear(token_clear),
        .out_chan_dep_vld_vec(out_chan_dep_vld_vec_68),
        .out_chan_dep_data(out_chan_dep_data_68),
        .token_out_vec(token_out_vec_68),
        .dl_detect_out(dl_in_vec[68]));

    assign proc_68_data_FIFO_blk[0] = 1'b0 | (~grp_task_run_head_fu_11440.fixed_head_do_head_U0.fixed_head_layernorm_U0.head_in_sm_blk_n);
    assign proc_68_data_PIPO_blk[0] = 1'b0;
    assign proc_68_start_FIFO_blk[0] = 1'b0 | (~grp_task_run_head_fu_11440.start_for_fixed_head_do_head_U0_U.if_empty_n & grp_task_run_head_fu_11440.fixed_head_do_head_U0.ap_idle & ~grp_task_run_head_fu_11440.start_for_fixed_head_do_head_U0_U.if_write);
    assign proc_68_TLF_FIFO_blk[0] = 1'b0;
    assign proc_68_input_sync_blk[0] = 1'b0;
    assign proc_68_output_sync_blk[0] = 1'b0;
    assign proc_dep_vld_vec_68[0] = dl_detect_out ? proc_dep_vld_vec_68_reg[0] : (proc_68_data_FIFO_blk[0] | proc_68_data_PIPO_blk[0] | proc_68_start_FIFO_blk[0] | proc_68_TLF_FIFO_blk[0] | proc_68_input_sync_blk[0] | proc_68_output_sync_blk[0]);
    assign proc_68_data_FIFO_blk[1] = 1'b0 | (~grp_task_run_head_fu_11440.fixed_head_do_head_U0.fixed_head_matmul_U0.do_adapt_3_U0.head_out_sm_blk_n);
    assign proc_68_data_PIPO_blk[1] = 1'b0;
    assign proc_68_start_FIFO_blk[1] = 1'b0 | (~grp_task_run_head_fu_11440.start_for_task_write_logits_U0_U.if_full_n & grp_task_run_head_fu_11440.fixed_head_do_head_U0.ap_start & ~grp_task_run_head_fu_11440.fixed_head_do_head_U0.real_start & (trans_in_cnt_47 == trans_out_cnt_47) & ~grp_task_run_head_fu_11440.start_for_task_write_logits_U0_U.if_read);
    assign proc_68_TLF_FIFO_blk[1] = 1'b0;
    assign proc_68_input_sync_blk[1] = 1'b0;
    assign proc_68_output_sync_blk[1] = 1'b0;
    assign proc_dep_vld_vec_68[1] = dl_detect_out ? proc_dep_vld_vec_68_reg[1] : (proc_68_data_FIFO_blk[1] | proc_68_data_PIPO_blk[1] | proc_68_start_FIFO_blk[1] | proc_68_TLF_FIFO_blk[1] | proc_68_input_sync_blk[1] | proc_68_output_sync_blk[1]);
    always @ (negedge dl_reset or posedge dl_clock) begin
        if (~dl_reset) begin
            proc_dep_vld_vec_68_reg <= 'b0;
        end
        else begin
            proc_dep_vld_vec_68_reg <= proc_dep_vld_vec_68;
        end
    end
    assign in_chan_dep_vld_vec_68[0] = dep_chan_vld_67_68;
    assign in_chan_dep_data_vec_68[73 : 0] = dep_chan_data_67_68;
    assign token_in_vec_68[0] = token_67_68;
    assign in_chan_dep_vld_vec_68[1] = dep_chan_vld_73_68;
    assign in_chan_dep_data_vec_68[147 : 74] = dep_chan_data_73_68;
    assign token_in_vec_68[1] = token_73_68;
    assign dep_chan_vld_68_67 = out_chan_dep_vld_vec_68[0];
    assign dep_chan_data_68_67 = out_chan_dep_data_68;
    assign token_68_67 = token_out_vec_68[0];
    assign dep_chan_vld_68_73 = out_chan_dep_vld_vec_68[1];
    assign dep_chan_data_68_73 = out_chan_dep_data_68;
    assign token_68_73 = token_out_vec_68[1];

    // Process: grp_task_run_head_fu_11440.fixed_head_do_head_U0.fixed_head_layernorm_U0
    vit_block_top_hls_deadlock_detect_unit #(74, 69, 3, 3) vit_block_top_hls_deadlock_detect_unit_69 (
        .reset(dl_reset),
        .clock(dl_clock),
        .proc_dep_vld_vec(proc_dep_vld_vec_69),
        .in_chan_dep_vld_vec(in_chan_dep_vld_vec_69),
        .in_chan_dep_data_vec(in_chan_dep_data_vec_69),
        .token_in_vec(token_in_vec_69),
        .dl_detect_in(dl_detect_out),
        .origin(origin[69]),
        .token_clear(token_clear),
        .out_chan_dep_vld_vec(out_chan_dep_vld_vec_69),
        .out_chan_dep_data(out_chan_dep_data_69),
        .token_out_vec(token_out_vec_69),
        .dl_detect_out(dl_in_vec[69]));

    assign proc_69_data_FIFO_blk[0] = 1'b0 | (~grp_task_run_head_fu_11440.fixed_head_do_head_U0.fixed_head_layernorm_U0.head_in_sm_blk_n);
    assign proc_69_data_PIPO_blk[0] = 1'b0;
    assign proc_69_start_FIFO_blk[0] = 1'b0;
    assign proc_69_TLF_FIFO_blk[0] = 1'b0;
    assign proc_69_input_sync_blk[0] = 1'b0;
    assign proc_69_output_sync_blk[0] = 1'b0;
    assign proc_dep_vld_vec_69[0] = dl_detect_out ? proc_dep_vld_vec_69_reg[0] : (proc_69_data_FIFO_blk[0] | proc_69_data_PIPO_blk[0] | proc_69_start_FIFO_blk[0] | proc_69_TLF_FIFO_blk[0] | proc_69_input_sync_blk[0] | proc_69_output_sync_blk[0]);
    assign proc_69_data_FIFO_blk[1] = 1'b0 | (~grp_task_run_head_fu_11440.fixed_head_do_head_U0.fixed_head_layernorm_U0.ln_sm_blk_n);
    assign proc_69_data_PIPO_blk[1] = 1'b0;
    assign proc_69_start_FIFO_blk[1] = 1'b0 | (~grp_task_run_head_fu_11440.fixed_head_do_head_U0.start_for_fixed_head_matmul_U0_U.if_full_n & grp_task_run_head_fu_11440.fixed_head_do_head_U0.fixed_head_layernorm_U0.ap_start & ~grp_task_run_head_fu_11440.fixed_head_do_head_U0.fixed_head_layernorm_U0.real_start & (trans_in_cnt_45 == trans_out_cnt_45) & ~grp_task_run_head_fu_11440.fixed_head_do_head_U0.start_for_fixed_head_matmul_U0_U.if_read);
    assign proc_69_TLF_FIFO_blk[1] = 1'b0;
    assign proc_69_input_sync_blk[1] = 1'b0;
    assign proc_69_output_sync_blk[1] = 1'b0;
    assign proc_dep_vld_vec_69[1] = dl_detect_out ? proc_dep_vld_vec_69_reg[1] : (proc_69_data_FIFO_blk[1] | proc_69_data_PIPO_blk[1] | proc_69_start_FIFO_blk[1] | proc_69_TLF_FIFO_blk[1] | proc_69_input_sync_blk[1] | proc_69_output_sync_blk[1]);
    assign proc_69_data_FIFO_blk[2] = 1'b0 | (~grp_task_run_head_fu_11440.fixed_head_do_head_U0.fixed_head_layernorm_U0.ln_sm_blk_n);
    assign proc_69_data_PIPO_blk[2] = 1'b0;
    assign proc_69_start_FIFO_blk[2] = 1'b0;
    assign proc_69_TLF_FIFO_blk[2] = 1'b0;
    assign proc_69_input_sync_blk[2] = 1'b0;
    assign proc_69_output_sync_blk[2] = 1'b0;
    assign proc_dep_vld_vec_69[2] = dl_detect_out ? proc_dep_vld_vec_69_reg[2] : (proc_69_data_FIFO_blk[2] | proc_69_data_PIPO_blk[2] | proc_69_start_FIFO_blk[2] | proc_69_TLF_FIFO_blk[2] | proc_69_input_sync_blk[2] | proc_69_output_sync_blk[2]);
    always @ (negedge dl_reset or posedge dl_clock) begin
        if (~dl_reset) begin
            proc_dep_vld_vec_69_reg <= 'b0;
        end
        else begin
            proc_dep_vld_vec_69_reg <= proc_dep_vld_vec_69;
        end
    end
    assign in_chan_dep_vld_vec_69[0] = dep_chan_vld_67_69;
    assign in_chan_dep_data_vec_69[73 : 0] = dep_chan_data_67_69;
    assign token_in_vec_69[0] = token_67_69;
    assign in_chan_dep_vld_vec_69[1] = dep_chan_vld_70_69;
    assign in_chan_dep_data_vec_69[147 : 74] = dep_chan_data_70_69;
    assign token_in_vec_69[1] = token_70_69;
    assign in_chan_dep_vld_vec_69[2] = dep_chan_vld_71_69;
    assign in_chan_dep_data_vec_69[221 : 148] = dep_chan_data_71_69;
    assign token_in_vec_69[2] = token_71_69;
    assign dep_chan_vld_69_67 = out_chan_dep_vld_vec_69[0];
    assign dep_chan_data_69_67 = out_chan_dep_data_69;
    assign token_69_67 = token_out_vec_69[0];
    assign dep_chan_vld_69_70 = out_chan_dep_vld_vec_69[1];
    assign dep_chan_data_69_70 = out_chan_dep_data_69;
    assign token_69_70 = token_out_vec_69[1];
    assign dep_chan_vld_69_71 = out_chan_dep_vld_vec_69[2];
    assign dep_chan_data_69_71 = out_chan_dep_data_69;
    assign token_69_71 = token_out_vec_69[2];

    // Process: grp_task_run_head_fu_11440.fixed_head_do_head_U0.fixed_head_matmul_U0
    vit_block_top_hls_deadlock_detect_unit #(74, 70, 2, 2) vit_block_top_hls_deadlock_detect_unit_70 (
        .reset(dl_reset),
        .clock(dl_clock),
        .proc_dep_vld_vec(proc_dep_vld_vec_70),
        .in_chan_dep_vld_vec(in_chan_dep_vld_vec_70),
        .in_chan_dep_data_vec(in_chan_dep_data_vec_70),
        .token_in_vec(token_in_vec_70),
        .dl_detect_in(dl_detect_out),
        .origin(origin[70]),
        .token_clear(token_clear),
        .out_chan_dep_vld_vec(out_chan_dep_vld_vec_70),
        .out_chan_dep_data(out_chan_dep_data_70),
        .token_out_vec(token_out_vec_70),
        .dl_detect_out(dl_in_vec[70]));

    assign proc_70_data_FIFO_blk[0] = 1'b0 | (~grp_task_run_head_fu_11440.fixed_head_do_head_U0.fixed_head_matmul_U0.fixed_head_matmul_core_U0.grp_fixed_head_matmul_core_Pipeline_READ_LOOP_fu_50.ln_sm_blk_n);
    assign proc_70_data_PIPO_blk[0] = 1'b0;
    assign proc_70_start_FIFO_blk[0] = 1'b0 | (~grp_task_run_head_fu_11440.fixed_head_do_head_U0.start_for_fixed_head_matmul_U0_U.if_empty_n & grp_task_run_head_fu_11440.fixed_head_do_head_U0.fixed_head_matmul_U0.ap_idle & ~grp_task_run_head_fu_11440.fixed_head_do_head_U0.start_for_fixed_head_matmul_U0_U.if_write);
    assign proc_70_TLF_FIFO_blk[0] = 1'b0;
    assign proc_70_input_sync_blk[0] = 1'b0;
    assign proc_70_output_sync_blk[0] = 1'b0;
    assign proc_dep_vld_vec_70[0] = dl_detect_out ? proc_dep_vld_vec_70_reg[0] : (proc_70_data_FIFO_blk[0] | proc_70_data_PIPO_blk[0] | proc_70_start_FIFO_blk[0] | proc_70_TLF_FIFO_blk[0] | proc_70_input_sync_blk[0] | proc_70_output_sync_blk[0]);
    assign proc_70_data_FIFO_blk[1] = 1'b0 | (~grp_task_run_head_fu_11440.fixed_head_do_head_U0.fixed_head_matmul_U0.do_adapt_3_U0.head_out_sm_blk_n);
    assign proc_70_data_PIPO_blk[1] = 1'b0;
    assign proc_70_start_FIFO_blk[1] = 1'b0;
    assign proc_70_TLF_FIFO_blk[1] = 1'b0;
    assign proc_70_input_sync_blk[1] = 1'b0;
    assign proc_70_output_sync_blk[1] = 1'b0;
    assign proc_dep_vld_vec_70[1] = dl_detect_out ? proc_dep_vld_vec_70_reg[1] : (proc_70_data_FIFO_blk[1] | proc_70_data_PIPO_blk[1] | proc_70_start_FIFO_blk[1] | proc_70_TLF_FIFO_blk[1] | proc_70_input_sync_blk[1] | proc_70_output_sync_blk[1]);
    always @ (negedge dl_reset or posedge dl_clock) begin
        if (~dl_reset) begin
            proc_dep_vld_vec_70_reg <= 'b0;
        end
        else begin
            proc_dep_vld_vec_70_reg <= proc_dep_vld_vec_70;
        end
    end
    assign in_chan_dep_vld_vec_70[0] = dep_chan_vld_69_70;
    assign in_chan_dep_data_vec_70[73 : 0] = dep_chan_data_69_70;
    assign token_in_vec_70[0] = token_69_70;
    assign in_chan_dep_vld_vec_70[1] = dep_chan_vld_73_70;
    assign in_chan_dep_data_vec_70[147 : 74] = dep_chan_data_73_70;
    assign token_in_vec_70[1] = token_73_70;
    assign dep_chan_vld_70_69 = out_chan_dep_vld_vec_70[0];
    assign dep_chan_data_70_69 = out_chan_dep_data_70;
    assign token_70_69 = token_out_vec_70[0];
    assign dep_chan_vld_70_73 = out_chan_dep_vld_vec_70[1];
    assign dep_chan_data_70_73 = out_chan_dep_data_70;
    assign token_70_73 = token_out_vec_70[1];

    // Process: grp_task_run_head_fu_11440.fixed_head_do_head_U0.fixed_head_matmul_U0.fixed_head_matmul_core_U0
    vit_block_top_hls_deadlock_detect_unit #(74, 71, 2, 2) vit_block_top_hls_deadlock_detect_unit_71 (
        .reset(dl_reset),
        .clock(dl_clock),
        .proc_dep_vld_vec(proc_dep_vld_vec_71),
        .in_chan_dep_vld_vec(in_chan_dep_vld_vec_71),
        .in_chan_dep_data_vec(in_chan_dep_data_vec_71),
        .token_in_vec(token_in_vec_71),
        .dl_detect_in(dl_detect_out),
        .origin(origin[71]),
        .token_clear(token_clear),
        .out_chan_dep_vld_vec(out_chan_dep_vld_vec_71),
        .out_chan_dep_data(out_chan_dep_data_71),
        .token_out_vec(token_out_vec_71),
        .dl_detect_out(dl_in_vec[71]));

    assign proc_71_data_FIFO_blk[0] = 1'b0 | (~grp_task_run_head_fu_11440.fixed_head_do_head_U0.fixed_head_matmul_U0.fixed_head_matmul_core_U0.grp_fixed_head_matmul_core_Pipeline_READ_LOOP_fu_50.ln_sm_blk_n);
    assign proc_71_data_PIPO_blk[0] = 1'b0;
    assign proc_71_start_FIFO_blk[0] = 1'b0;
    assign proc_71_TLF_FIFO_blk[0] = 1'b0;
    assign proc_71_input_sync_blk[0] = 1'b0;
    assign proc_71_output_sync_blk[0] = 1'b0;
    assign proc_dep_vld_vec_71[0] = dl_detect_out ? proc_dep_vld_vec_71_reg[0] : (proc_71_data_FIFO_blk[0] | proc_71_data_PIPO_blk[0] | proc_71_start_FIFO_blk[0] | proc_71_TLF_FIFO_blk[0] | proc_71_input_sync_blk[0] | proc_71_output_sync_blk[0]);
    assign proc_71_data_FIFO_blk[1] = 1'b0 | (~grp_task_run_head_fu_11440.fixed_head_do_head_U0.fixed_head_matmul_U0.fixed_head_matmul_core_U0.grp_fixed_head_matmul_core_Pipeline_COT_LOOP_CIT_LOOP_fu_58.mac_sm_blk_n);
    assign proc_71_data_PIPO_blk[1] = 1'b0;
    assign proc_71_start_FIFO_blk[1] = 1'b0 | (~grp_task_run_head_fu_11440.fixed_head_do_head_U0.fixed_head_matmul_U0.start_for_do_adapt_3_U0_U.if_full_n & grp_task_run_head_fu_11440.fixed_head_do_head_U0.fixed_head_matmul_U0.fixed_head_matmul_core_U0.ap_start & ~grp_task_run_head_fu_11440.fixed_head_do_head_U0.fixed_head_matmul_U0.fixed_head_matmul_core_U0.real_start & (trans_in_cnt_46 == trans_out_cnt_46) & ~grp_task_run_head_fu_11440.fixed_head_do_head_U0.fixed_head_matmul_U0.start_for_do_adapt_3_U0_U.if_read);
    assign proc_71_TLF_FIFO_blk[1] = 1'b0;
    assign proc_71_input_sync_blk[1] = 1'b0;
    assign proc_71_output_sync_blk[1] = 1'b0;
    assign proc_dep_vld_vec_71[1] = dl_detect_out ? proc_dep_vld_vec_71_reg[1] : (proc_71_data_FIFO_blk[1] | proc_71_data_PIPO_blk[1] | proc_71_start_FIFO_blk[1] | proc_71_TLF_FIFO_blk[1] | proc_71_input_sync_blk[1] | proc_71_output_sync_blk[1]);
    always @ (negedge dl_reset or posedge dl_clock) begin
        if (~dl_reset) begin
            proc_dep_vld_vec_71_reg <= 'b0;
        end
        else begin
            proc_dep_vld_vec_71_reg <= proc_dep_vld_vec_71;
        end
    end
    assign in_chan_dep_vld_vec_71[0] = dep_chan_vld_69_71;
    assign in_chan_dep_data_vec_71[73 : 0] = dep_chan_data_69_71;
    assign token_in_vec_71[0] = token_69_71;
    assign in_chan_dep_vld_vec_71[1] = dep_chan_vld_72_71;
    assign in_chan_dep_data_vec_71[147 : 74] = dep_chan_data_72_71;
    assign token_in_vec_71[1] = token_72_71;
    assign dep_chan_vld_71_69 = out_chan_dep_vld_vec_71[0];
    assign dep_chan_data_71_69 = out_chan_dep_data_71;
    assign token_71_69 = token_out_vec_71[0];
    assign dep_chan_vld_71_72 = out_chan_dep_vld_vec_71[1];
    assign dep_chan_data_71_72 = out_chan_dep_data_71;
    assign token_71_72 = token_out_vec_71[1];

    // Process: grp_task_run_head_fu_11440.fixed_head_do_head_U0.fixed_head_matmul_U0.do_adapt_3_U0
    vit_block_top_hls_deadlock_detect_unit #(74, 72, 2, 2) vit_block_top_hls_deadlock_detect_unit_72 (
        .reset(dl_reset),
        .clock(dl_clock),
        .proc_dep_vld_vec(proc_dep_vld_vec_72),
        .in_chan_dep_vld_vec(in_chan_dep_vld_vec_72),
        .in_chan_dep_data_vec(in_chan_dep_data_vec_72),
        .token_in_vec(token_in_vec_72),
        .dl_detect_in(dl_detect_out),
        .origin(origin[72]),
        .token_clear(token_clear),
        .out_chan_dep_vld_vec(out_chan_dep_vld_vec_72),
        .out_chan_dep_data(out_chan_dep_data_72),
        .token_out_vec(token_out_vec_72),
        .dl_detect_out(dl_in_vec[72]));

    assign proc_72_data_FIFO_blk[0] = 1'b0 | (~grp_task_run_head_fu_11440.fixed_head_do_head_U0.fixed_head_matmul_U0.do_adapt_3_U0.mac_sm_blk_n);
    assign proc_72_data_PIPO_blk[0] = 1'b0;
    assign proc_72_start_FIFO_blk[0] = 1'b0 | (~grp_task_run_head_fu_11440.fixed_head_do_head_U0.fixed_head_matmul_U0.start_for_do_adapt_3_U0_U.if_empty_n & grp_task_run_head_fu_11440.fixed_head_do_head_U0.fixed_head_matmul_U0.do_adapt_3_U0.ap_idle & ~grp_task_run_head_fu_11440.fixed_head_do_head_U0.fixed_head_matmul_U0.start_for_do_adapt_3_U0_U.if_write);
    assign proc_72_TLF_FIFO_blk[0] = 1'b0;
    assign proc_72_input_sync_blk[0] = 1'b0;
    assign proc_72_output_sync_blk[0] = 1'b0;
    assign proc_dep_vld_vec_72[0] = dl_detect_out ? proc_dep_vld_vec_72_reg[0] : (proc_72_data_FIFO_blk[0] | proc_72_data_PIPO_blk[0] | proc_72_start_FIFO_blk[0] | proc_72_TLF_FIFO_blk[0] | proc_72_input_sync_blk[0] | proc_72_output_sync_blk[0]);
    assign proc_72_data_FIFO_blk[1] = 1'b0 | (~grp_task_run_head_fu_11440.fixed_head_do_head_U0.fixed_head_matmul_U0.do_adapt_3_U0.head_out_sm_blk_n);
    assign proc_72_data_PIPO_blk[1] = 1'b0;
    assign proc_72_start_FIFO_blk[1] = 1'b0;
    assign proc_72_TLF_FIFO_blk[1] = 1'b0;
    assign proc_72_input_sync_blk[1] = 1'b0;
    assign proc_72_output_sync_blk[1] = 1'b0;
    assign proc_dep_vld_vec_72[1] = dl_detect_out ? proc_dep_vld_vec_72_reg[1] : (proc_72_data_FIFO_blk[1] | proc_72_data_PIPO_blk[1] | proc_72_start_FIFO_blk[1] | proc_72_TLF_FIFO_blk[1] | proc_72_input_sync_blk[1] | proc_72_output_sync_blk[1]);
    always @ (negedge dl_reset or posedge dl_clock) begin
        if (~dl_reset) begin
            proc_dep_vld_vec_72_reg <= 'b0;
        end
        else begin
            proc_dep_vld_vec_72_reg <= proc_dep_vld_vec_72;
        end
    end
    assign in_chan_dep_vld_vec_72[0] = dep_chan_vld_71_72;
    assign in_chan_dep_data_vec_72[73 : 0] = dep_chan_data_71_72;
    assign token_in_vec_72[0] = token_71_72;
    assign in_chan_dep_vld_vec_72[1] = dep_chan_vld_73_72;
    assign in_chan_dep_data_vec_72[147 : 74] = dep_chan_data_73_72;
    assign token_in_vec_72[1] = token_73_72;
    assign dep_chan_vld_72_71 = out_chan_dep_vld_vec_72[0];
    assign dep_chan_data_72_71 = out_chan_dep_data_72;
    assign token_72_71 = token_out_vec_72[0];
    assign dep_chan_vld_72_73 = out_chan_dep_vld_vec_72[1];
    assign dep_chan_data_72_73 = out_chan_dep_data_72;
    assign token_72_73 = token_out_vec_72[1];

    // Process: grp_task_run_head_fu_11440.task_write_logits_U0
    vit_block_top_hls_deadlock_detect_unit #(74, 73, 3, 3) vit_block_top_hls_deadlock_detect_unit_73 (
        .reset(dl_reset),
        .clock(dl_clock),
        .proc_dep_vld_vec(proc_dep_vld_vec_73),
        .in_chan_dep_vld_vec(in_chan_dep_vld_vec_73),
        .in_chan_dep_data_vec(in_chan_dep_data_vec_73),
        .token_in_vec(token_in_vec_73),
        .dl_detect_in(dl_detect_out),
        .origin(origin[73]),
        .token_clear(token_clear),
        .out_chan_dep_vld_vec(out_chan_dep_vld_vec_73),
        .out_chan_dep_data(out_chan_dep_data_73),
        .token_out_vec(token_out_vec_73),
        .dl_detect_out(dl_in_vec[73]));

    assign proc_73_data_FIFO_blk[0] = 1'b0 | (~grp_task_run_head_fu_11440.task_write_logits_U0.head_out_sm_blk_n);
    assign proc_73_data_PIPO_blk[0] = 1'b0;
    assign proc_73_start_FIFO_blk[0] = 1'b0 | (~grp_task_run_head_fu_11440.start_for_task_write_logits_U0_U.if_empty_n & grp_task_run_head_fu_11440.task_write_logits_U0.ap_idle & ~grp_task_run_head_fu_11440.start_for_task_write_logits_U0_U.if_write);
    assign proc_73_TLF_FIFO_blk[0] = 1'b0;
    assign proc_73_input_sync_blk[0] = 1'b0;
    assign proc_73_output_sync_blk[0] = 1'b0;
    assign proc_dep_vld_vec_73[0] = dl_detect_out ? proc_dep_vld_vec_73_reg[0] : (proc_73_data_FIFO_blk[0] | proc_73_data_PIPO_blk[0] | proc_73_start_FIFO_blk[0] | proc_73_TLF_FIFO_blk[0] | proc_73_input_sync_blk[0] | proc_73_output_sync_blk[0]);
    assign proc_73_data_FIFO_blk[1] = 1'b0 | (~grp_task_run_head_fu_11440.task_write_logits_U0.head_out_sm_blk_n);
    assign proc_73_data_PIPO_blk[1] = 1'b0;
    assign proc_73_start_FIFO_blk[1] = 1'b0;
    assign proc_73_TLF_FIFO_blk[1] = 1'b0;
    assign proc_73_input_sync_blk[1] = 1'b0;
    assign proc_73_output_sync_blk[1] = 1'b0;
    assign proc_dep_vld_vec_73[1] = dl_detect_out ? proc_dep_vld_vec_73_reg[1] : (proc_73_data_FIFO_blk[1] | proc_73_data_PIPO_blk[1] | proc_73_start_FIFO_blk[1] | proc_73_TLF_FIFO_blk[1] | proc_73_input_sync_blk[1] | proc_73_output_sync_blk[1]);
    assign proc_73_data_FIFO_blk[2] = 1'b0 | (~grp_task_run_head_fu_11440.task_write_logits_U0.head_out_sm_blk_n);
    assign proc_73_data_PIPO_blk[2] = 1'b0;
    assign proc_73_start_FIFO_blk[2] = 1'b0;
    assign proc_73_TLF_FIFO_blk[2] = 1'b0;
    assign proc_73_input_sync_blk[2] = 1'b0;
    assign proc_73_output_sync_blk[2] = 1'b0;
    assign proc_dep_vld_vec_73[2] = dl_detect_out ? proc_dep_vld_vec_73_reg[2] : (proc_73_data_FIFO_blk[2] | proc_73_data_PIPO_blk[2] | proc_73_start_FIFO_blk[2] | proc_73_TLF_FIFO_blk[2] | proc_73_input_sync_blk[2] | proc_73_output_sync_blk[2]);
    always @ (negedge dl_reset or posedge dl_clock) begin
        if (~dl_reset) begin
            proc_dep_vld_vec_73_reg <= 'b0;
        end
        else begin
            proc_dep_vld_vec_73_reg <= proc_dep_vld_vec_73;
        end
    end
    assign in_chan_dep_vld_vec_73[0] = dep_chan_vld_68_73;
    assign in_chan_dep_data_vec_73[73 : 0] = dep_chan_data_68_73;
    assign token_in_vec_73[0] = token_68_73;
    assign in_chan_dep_vld_vec_73[1] = dep_chan_vld_70_73;
    assign in_chan_dep_data_vec_73[147 : 74] = dep_chan_data_70_73;
    assign token_in_vec_73[1] = token_70_73;
    assign in_chan_dep_vld_vec_73[2] = dep_chan_vld_72_73;
    assign in_chan_dep_data_vec_73[221 : 148] = dep_chan_data_72_73;
    assign token_in_vec_73[2] = token_72_73;
    assign dep_chan_vld_73_68 = out_chan_dep_vld_vec_73[0];
    assign dep_chan_data_73_68 = out_chan_dep_data_73;
    assign token_73_68 = token_out_vec_73[0];
    assign dep_chan_vld_73_70 = out_chan_dep_vld_vec_73[1];
    assign dep_chan_data_73_70 = out_chan_dep_data_73;
    assign token_73_70 = token_out_vec_73[1];
    assign dep_chan_vld_73_72 = out_chan_dep_vld_vec_73[2];
    assign dep_chan_data_73_72 = out_chan_dep_data_73;
    assign token_73_72 = token_out_vec_73[2];


`include "vit_block_top_hls_deadlock_report_unit.vh"
