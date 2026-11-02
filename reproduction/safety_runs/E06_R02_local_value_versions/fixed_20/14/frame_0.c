static av_always_inline int check_intra_mode(VP9Context *s, int mode,
                                             uint8_t **a,
                                             uint8_t *dst_edge,
                                             ptrdiff_t stride_edge,
                                             uint8_t *dst_inner,
                                             ptrdiff_t stride_inner,
                                             uint8_t *l, int col, int x, int w,
                                             int row, int y, enum TxfmMode tx,
                                             int p)
{
    int have_top   = row > 0 || y > 0;
    int have_left  = col > s->tiling.tile_col_start || x > 0;
    int have_right = x < w - 1;
    static const uint8_t mode_conv[10][2 /* have_left */][2 /* have_top */] = {
        [VERT_PRED]            = { { DC_127_PRED,          VERT_PRED            },
                                   { DC_127_PRED,          VERT_PRED            } },
        [HOR_PRED]             = { { DC_129_PRED,          DC_129_PRED          },
                                   { HOR_PRED,             HOR_PRED             } },
        [DC_PRED]              = { { DC_128_PRED,          TOP_DC_PRED          },
                                   { LEFT_DC_PRED,         DC_PRED              } },
        [DIAG_DOWN_LEFT_PRED]  = { { DC_127_PRED,          DIAG_DOWN_LEFT_PRED  },
                                   { DC_127_PRED,          DIAG_DOWN_LEFT_PRED  } },
        [DIAG_DOWN_RIGHT_PRED] = { { DIAG_DOWN_RIGHT_PRED, DIAG_DOWN_RIGHT_PRED },
                                   { DIAG_DOWN_RIGHT_PRED, DIAG_DOWN_RIGHT_PRED } },
        [VERT_RIGHT_PRED]      = { { VERT_RIGHT_PRED,      VERT_RIGHT_PRED      },
                                   { VERT_RIGHT_PRED,      VERT_RIGHT_PRED      } },
        [HOR_DOWN_PRED]        = { { HOR_DOWN_PRED,        HOR_DOWN_PRED        },
                                   { HOR_DOWN_PRED,        HOR_DOWN_PRED        } },
        [VERT_LEFT_PRED]       = { { DC_127_PRED,          VERT_LEFT_PRED       },
                                   { DC_127_PRED,          VERT_LEFT_PRED       } },
        [HOR_UP_PRED]          = { { DC_129_PRED,          DC_129_PRED          },
                                   { HOR_UP_PRED,          HOR_UP_PRED          } },
        [TM_VP8_PRED]          = { { DC_129_PRED,          VERT_PRED            },
                                   { HOR_PRED,             TM_VP8_PRED          } },
    };
    static const struct {
        uint8_t needs_left:1;
        uint8_t needs_top:1;
        uint8_t needs_topleft:1;
        uint8_t needs_topright:1;
    } edges[N_INTRA_PRED_MODES] = {
        [VERT_PRED]            = { .needs_top  = 1 },
        [HOR_PRED]             = { .needs_left = 1 },
        [DC_PRED]              = { .needs_top  = 1, .needs_left = 1 },
        [DIAG_DOWN_LEFT_PRED]  = { .needs_top  = 1, .needs_topright = 1 },
        [DIAG_DOWN_RIGHT_PRED] = { .needs_left = 1, .needs_top = 1,
                                   .needs_topleft = 1 },
        [VERT_RIGHT_PRED]      = { .needs_left = 1, .needs_top = 1,
                                   .needs_topleft = 1 },
        [HOR_DOWN_PRED]        = { .needs_left = 1, .needs_top = 1,
                                   .needs_topleft = 1 },
        [VERT_LEFT_PRED]       = { .needs_top  = 1, .needs_topright = 1 },
        [HOR_UP_PRED]          = { .needs_left = 1 },
        [TM_VP8_PRED]          = { .needs_left = 1, .needs_top = 1,
                                   .needs_topleft = 1 },
        [LEFT_DC_PRED]         = { .needs_left = 1 },
        [TOP_DC_PRED]          = { .needs_top  = 1 },
        [DC_128_PRED]          = { 0 },
        [DC_127_PRED]          = { 0 },
        [DC_129_PRED]          = { 0 }
    };

    av_assert2(mode >= 0 && mode < 10);
    mode = mode_conv[mode][have_left][have_top];
    if (edges[mode].needs_top) {
        uint8_t *top = NULL, *topleft = NULL;
        int n_px_need = 4 << tx, n_px_have = (((s->cols - col) << !p) - x) * 4;
        int n_px_need_tr = 0;

        if (tx == TX_4X4 && edges[mode].needs_topright && have_right)
            n_px_need_tr = 4;

        // if top of sb64-row, use s->intra_pred_data[] instead of
        // dst[-stride] for intra prediction (it contains pre- instead of
        // post-loopfilter data)
        if (have_top) {
            top = !(row & 7) && !y ?
                  s->intra_pred_data[p] + col * (8 >> !!p) + x * 4 :
                  y == 0 ? &dst_edge[-stride_edge] : &dst_inner[-stride_inner];
            if (have_left)
                topleft = !(row & 7) && !y ?
                          s->intra_pred_data[p] + col * (8 >> !!p) + x * 4 :
                          y == 0 || x == 0 ? &dst_edge[-stride_edge] :
                          &dst_inner[-stride_inner];
        }

        if (have_top &&
            (!edges[mode].needs_topleft || (have_left && top == topleft)) &&
            (tx != TX_4X4 || !edges[mode].needs_topright || have_right) &&
            n_px_need + n_px_need_tr <= n_px_have) {
            *a = top;
        } else {
            if (have_top) {
                if (n_px_need <= n_px_have) {
                    memcpy(*a, top, n_px_need);
                } else {
                    memcpy(*a, top, n_px_have);
                    memset(&(*a)[n_px_have], (*a)[n_px_have - 1],
                           n_px_need - n_px_have);
                }
            } else {
                memset(*a, 127, n_px_need);
            }
            if (edges[mode].needs_topleft) {
                if (have_left && have_top)
                    (*a)[-1] = topleft[-1];
                else
                    (*a)[-1] = have_top ? 129 : 127;
            }
            if (tx == TX_4X4 && edges[mode].needs_topright) {
                if (have_top && have_right &&
                    n_px_need + n_px_need_tr <= n_px_have) {
                    memcpy(&(*a)[4], &top[4], 4);
                } else {
                    memset(&(*a)[4], (*a)[3], 4);
                }
            }
        }
    }
    if (edges[mode].needs_left) {
        if (have_left) {
            int i;
            int n_px_need = 4 << tx;
            int n_px_have = (((s->rows - row) << !p) - y) * 4;
            uint8_t *dst     = x == 0 ? dst_edge : dst_inner;
            ptrdiff_t stride = x == 0 ? stride_edge : stride_inner;

            if (n_px_need <= n_px_have) {
                for (i = 0; i < n_px_need; i++)
                    l[i] = dst[i * stride - 1];
            } else {
                for (i = 0; i < n_px_have; i++)
                    l[i] = dst[i * stride - 1];
                memset(&l[i], l[i - 1], n_px_need - n_px_have);
            }
        } else {
            memset(l, 129, 4 << tx);
        }
    }

    return mode;
}