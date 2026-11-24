/* SPDX-License-Identifier: MIT */
#include <assert.h>
#include <stdbool.h>
#include <stdint.h>
#include <string.h>
#define ASSERT assert
#define BREAK_TO_DEBUGGER() assert(0)
#define DC_LOG_ERROR(...) do { (void)dc; assert(0); } while (0)
#define CSC_TEMPERATURE_MATRIX_SIZE 12
enum { TF_TYPE_PREDEFINED, TF_TYPE_DISTRIBUTED_POINTS, TF_TYPE_BYPASS, TF_TYPE_HWPWL };
enum dc_transfer_func_predefined { TRANSFER_FUNCTION_UNITY, TRANSFER_FUNCTION_PQ };
enum { GRAPHICS_GAMUT_ADJUST_TYPE_BYPASS, GRAPHICS_GAMUT_ADJUST_TYPE_SW,
 MPCC_MCM_FIRST_GAMUT_REMAP, MPCC_MCM_SECOND_GAMUT_REMAP, MPCC_OGAM_GAMUT_REMAP,
 MPCC_MOVABLE_CM_LOCATION_BEFORE };
enum { MCM_LUT_1DLUT, MCM_LUT_SHAPER, MCM_LUT_3DLUT,
 CM_LUT_SIZE_NONE, CM_LUT_SIZE_999, CM_LUT_SIZE_171717 };
struct pwl_params { int value; };
struct transfer { int type; enum dc_transfer_func_predefined tf; struct pwl_params pwl; };
struct gamut { bool enable_remap; int matrix[12]; };
struct tetrahedral { bool use_tetrahedral_9, use_12bits; };
struct lut3d { struct { struct { unsigned initialized; } bits; } state; struct tetrahedral lut_3d; };
struct dc_3dlut_dma { int size,format; uint64_t addr; };
struct dc_plane_cm { struct transfer shaper_func,blend_func;
 union { struct lut3d lut3d_func; struct dc_3dlut_dma lut3d_dma; };
 struct { struct { bool shaper_enable,lut3d_enable,blend_enable,lut3d_dma_enable,rmcm_enable; } bits; } flags; };
struct dc;
struct context { struct dc *dc; };
struct dc_plane_state { struct context *ctx; struct transfer in_transfer_func; struct gamut gamut_remap_matrix;
 struct dc_plane_cm cm; bool scaling_linearity; int format; };
struct dc_stream_state { struct context *ctx; struct transfer out_transfer_func,*func_shaper;
 struct lut3d *lut3d_func; struct gamut gamut_remap_matrix; bool dv_standard; };
struct mpc_grph_gamut_adjustment { int gamut_adjust_type,mpcc_gamut_remap_block_id,temperature_matrix[12]; };
union mcm_lut_params { const struct pwl_params *pwl; const struct tetrahedral *lut3d; };
struct mpc;
struct mpc_funcs {
 void (*set_gamut_remap)(struct mpc*,int,struct mpc_grph_gamut_adjustment*);
 void (*get_lut_mode)(struct mpc*,int,int,bool*,bool*);
 void (*program_lut_mode)(struct mpc*,int,bool,bool,int,int);
 void (*populate_lut)(struct mpc*,int,const union mcm_lut_params*,bool,int);
 void (*program_lut_read_write_control)(struct mpc*,int,bool,int,int);
 void (*update_3dlut_fast_load_select)(struct mpc*,int,int);
 bool (*program_shaper)(struct mpc*,const struct pwl_params*,int);
 bool (*program_3dlut)(struct mpc*,const struct tetrahedral*,int);
 void (*set_movable_cm_location)(struct mpc*,int,int);
 void (*set_output_gamma)(struct mpc*,int,const struct pwl_params*);
};
struct mpc { struct mpc_funcs *funcs; struct pwl_params blender_params; };
struct dpp;
struct dpp_funcs { void (*dpp_set_pre_degam)(struct dpp*,enum dc_transfer_func_predefined);
 void (*dpp_set_pregam_state)(struct dpp*,enum dc_transfer_func_predefined,bool,bool);
 void (*dpp_program_gamcor_lut)(struct dpp*,const struct pwl_params*); };
struct dpp { struct context *ctx; struct dpp_funcs *funcs; struct pwl_params regamma_params,shaper_params,degamma_params; };
struct hubp;
struct hubp_funcs { void (*hubp_program_3dlut_fl_config)(struct hubp*,const struct dc_3dlut_dma*);
 void (*hubp_program_3dlut_fl_crossbar)(struct hubp*,int);
 void (*hubp_program_3dlut_fl_addr)(struct hubp*,const uint64_t*);
 void (*hubp_enable_3dlut_fl)(struct hubp*,bool); };
struct hubp { struct context *ctx; struct hubp_funcs *funcs; int inst; };
struct program_gamut_remap_params { struct mpc *mpc; int mpcc_id;
 const struct dc_stream_state *stream; const struct dc_plane_state *plane; bool is_top_pipe; };
struct set_output_transfer_func_params { struct dpp *dpp; struct mpc *mpc; int mpcc_id;
 bool is_top_pipe; const struct dc_stream_state *stream; };
enum { MAX_RMCM_INST = 2, RMCM_MPCC_ID_UNKNOWN = -2, RMCM_MPCC_ID_NONE = -1,
 RMCM_FL_HUBP_IDX_NONE = -1 };
struct rmcm;
struct rmcm_funcs {
 void (*update_3dlut_fast_load_select)(struct rmcm *, int, int);
 void (*connect_mpcc)(struct rmcm *, int, int);
};
struct rmcm { struct rmcm_funcs *funcs; int inst, mpcc_id; };
struct set_input_transfer_func_params {
 struct dc *dc; struct dpp *dpp; struct hubp *hubp,*primary_hubp; struct mpc *mpc;
 struct dc_stream_state *stream; struct dc_plane_state *plane_state; struct rmcm *rmcm;
 int mpcc_id;
};
struct dce_hwseq { struct {
 bool (*set_mcm_luts)(struct dc*,struct dpp*,struct hubp*,struct hubp*,struct mpc*,int,
                      struct dc_stream_state*,struct dc_plane_state*);
 bool (*set_rmcm_luts)(struct set_input_transfer_func_params*);
 void (*disable_mcm_luts)(struct mpc*,int);
 void (*disable_rmcm_luts)(struct dc*,struct rmcm*,struct hubp*,int);
 } funcs; };
struct dc { struct { struct rmcm *rmcm[MAX_RMCM_INST]; struct { int num_rmcm; } *res_cap; } *res_pool;
 struct dce_hwseq *hwseq; };
static int expected_pipe;
static struct { int gamut[6],pre; bool lut[3],fast,ogam,igam; unsigned rmcm_writes; } trace;
static void gamut(struct mpc*m,int id,struct mpc_grph_gamut_adjustment*a)
{ assert(id==expected_pipe); trace.gamut[a->mpcc_gamut_remap_block_id]=a->gamut_adjust_type; }
static void get_lut(struct mpc*m,int which,int id,bool*enabled,bool*bank)
{ assert(id==expected_pipe); *enabled=trace.lut[which]; *bank=true; }
static void mode(struct mpc*m,int which,bool enabled,bool bank,int size,int id)
{ assert(id==expected_pipe); trace.lut[which]=enabled; }
static void populate(struct mpc*m,int which,const union mcm_lut_params *p,bool bank,int id)
{ assert(id==expected_pipe && trace.lut[which] && p->pwl); }
static void location(struct mpc*m,int loc,int id){ assert(id==expected_pipe && loc==MPCC_MOVABLE_CM_LOCATION_BEFORE); }
static void fast(struct hubp*h,bool enabled){ assert(h->inst==expected_pipe); trace.fast=enabled; }
static void ogam(struct mpc*m,int id,const struct pwl_params*p){ assert(id==expected_pipe); trace.ogam=p!=NULL; }
static void pre(struct dpp*d,enum dc_transfer_func_predefined tf){ trace.pre=tf; }
static void igam(struct dpp*d,const struct pwl_params*p){ trace.igam=p!=NULL; }
static bool cm3_helper_translate_curve_to_hw_format(struct context*c,const struct transfer*t,struct pwl_params*p,bool s){ return true; }
static bool cm3_helper_translate_curve_to_degamma_hw_format(const struct transfer*t,struct pwl_params*p){ return true; }
static void cm_helper_translate_curve_to_hw_format(struct context*c,const struct transfer*t,struct pwl_params*p,bool s){}
static bool is_source_pixel_format_linear(int format) { return false; }
static void connect_rmcm(struct rmcm *rmcm,int inst,int mpcc_id)
{ assert(inst==rmcm->inst); rmcm->mpcc_id=mpcc_id; }
@@RMCM_CLEANUP@@
static bool dcn42_set_rmcm_luts(struct set_input_transfer_func_params *params)
{
 @@RMCM_ADMISSION@@
 /* Reaching this point would program registers. */
 ++trace.rmcm_writes;
 return true;
}
@@FUNCTIONS@@
int main(void)
{
 struct mpc_funcs mf={.set_gamut_remap=gamut,.get_lut_mode=get_lut,.program_lut_mode=mode,
  .populate_lut=populate,.set_movable_cm_location=location,.set_output_gamma=ogam};
 struct mpc mpc={.funcs=&mf};
 struct dpp_funcs df={.dpp_set_pre_degam=pre,.dpp_program_gamcor_lut=igam};
 struct hubp_funcs hf={.hubp_enable_3dlut_fl=fast};
 struct rmcm_funcs rf={.connect_mpcc=connect_rmcm};
 struct rmcm rmcm={.funcs=&rf},other={.funcs=&rf,.inst=1,.mpcc_id=7};
 typeof(*((struct dc*)0)->res_pool->res_cap) caps={.num_rmcm=MAX_RMCM_INST};
 typeof(*((struct dc*)0)->res_pool) pool={.rmcm={&rmcm,&other},.res_cap=&caps};
 struct dce_hwseq hws={0}; struct dc dc={.res_pool=&pool,.hwseq=&hws}; struct context ctx={&dc};
 struct dpp dpp={.ctx=&ctx,.funcs=&df}; struct hubp hubp={.ctx=&ctx,.funcs=&hf};
 struct dc_plane_state plane={.ctx=&ctx}; struct dc_stream_state stream={.ctx=&ctx};
 struct program_gamut_remap_params gc={&mpc,0,&stream,&plane,true};
 struct set_output_transfer_func_params otf={&dpp,&mpc,0,true,&stream};
 struct set_input_transfer_func_params itf={.dc=&dc,.dpp=&dpp,.hubp=&hubp,.primary_hubp=&hubp,
  .mpc=&mpc,.stream=&stream,.plane_state=&plane};
 typeof(hws.funcs.set_mcm_luts) routes[]={dcn401_set_mcm_luts,dcn42_set_mcm_luts};
 for (unsigned i=0;i<2;++i) {
  hws.funcs.set_mcm_luts=routes[i];
  hws.funcs.set_rmcm_luts=i ? dcn42_set_rmcm_luts : NULL;
  hws.funcs.disable_rmcm_luts=i ? dcn42_disable_rmcm_luts : NULL;
  hws.funcs.disable_mcm_luts=i ? dcn42_disable_mcm_luts : NULL;
  for (expected_pipe=0;expected_pipe<4;++expected_pipe) {
   hubp.inst=gc.mpcc_id=otf.mpcc_id=itf.mpcc_id=expected_pipe;
   stream.dv_standard=false;
   plane.in_transfer_func.type=plane.cm.shaper_func.type=plane.cm.blend_func.type=TF_TYPE_HWPWL;
   plane.cm.flags.bits.shaper_enable=plane.cm.flags.bits.blend_enable=plane.cm.flags.bits.lut3d_enable=true;
   plane.cm.lut3d_func.state.bits.initialized=1;
   stream.out_transfer_func.type=TF_TYPE_HWPWL;
   plane.gamut_remap_matrix.enable_remap=stream.gamut_remap_matrix.enable_remap=true;
   dcn401_program_gamut_remap(&gc);
   assert(dcn32_set_input_transfer_func(&itf));
   dcn401_set_output_transfer_func(&otf);
   assert(trace.lut[0] && trace.lut[1] && trace.lut[2] && trace.igam && trace.ogam);
   assert(trace.gamut[MPCC_MCM_FIRST_GAMUT_REMAP]==GRAPHICS_GAMUT_ADJUST_TYPE_SW);
   assert(trace.gamut[MPCC_OGAM_GAMUT_REMAP]==GRAPHICS_GAMUT_ADJUST_TYPE_SW);
   plane.cm.flags.bits.rmcm_enable=i != 0;
   plane.cm.flags.bits.lut3d_dma_enable=true;
   plane.cm.lut3d_dma=(struct dc_3dlut_dma){.addr=0x12340000};
   assert(dcn32_set_input_transfer_func(&itf));
   assert(!trace.rmcm_writes && trace.fast==(i == 0));
   rmcm.mpcc_id=expected_pipe;
   stream.dv_standard=true;
   plane.cm=(struct dc_plane_cm){.shaper_func={.type=TF_TYPE_BYPASS},.blend_func={.type=TF_TYPE_BYPASS}};
   plane.in_transfer_func.type=stream.out_transfer_func.type=TF_TYPE_BYPASS;
   plane.gamut_remap_matrix.enable_remap=stream.gamut_remap_matrix.enable_remap=false;
   dcn401_program_gamut_remap(&gc);
   assert(dcn32_set_input_transfer_func(&itf));
   dcn401_set_output_transfer_func(&otf);
   assert(!trace.lut[0] && !trace.lut[1] && !trace.lut[2] && !trace.fast && !trace.igam && !trace.ogam);
   assert(trace.pre==TRANSFER_FUNCTION_UNITY && !trace.rmcm_writes);
   assert(other.mpcc_id==7);
   if (i) assert(rmcm.mpcc_id==RMCM_MPCC_ID_NONE);
   assert(trace.gamut[MPCC_MCM_FIRST_GAMUT_REMAP]==GRAPHICS_GAMUT_ADJUST_TYPE_BYPASS);
   assert(trace.gamut[MPCC_MCM_SECOND_GAMUT_REMAP]==GRAPHICS_GAMUT_ADJUST_TYPE_BYPASS);
   assert(trace.gamut[MPCC_OGAM_GAMUT_REMAP]==GRAPHICS_GAMUT_ADJUST_TYPE_BYPASS);
  }
 }
}
