#include "xvit_block_top.h"

XVit_block_top_Config XVit_block_top_ConfigTable[] __attribute__ ((section (".drvcfg_sec"))) = {

	{
		"xlnx,vit-block-top-1.0", /* compatible */
		0xa0010000,
		0xa0020000 /* reg */
	},
	 {
		 NULL
	}
};