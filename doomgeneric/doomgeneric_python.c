/*
 * doomgeneric_python.c
 * Platform backend for doomgeneric that exposes the engine to Python via ctypes.
 * Implements the 6 required DG_* callbacks as stubs, plus exports DG_PushKey
 * so Python can inject keyboard events.
 *
 * Build: see Makefile.python
 * Usage: see bsdoom.py
 */

#include "doomgeneric.h"
#include "doomkeys.h"

#include <stdio.h>
#include <stdint.h>
#include <string.h>
#include <time.h>
#include <unistd.h>

/* ── frame-ready flag (polled by BombSquad tick) ─────────────────────────── */
int bs_frame_ready = 0;

/* ── input queue ─────────────────────────────────────────────────────────── */

#define KEY_QUEUE_SIZE 64

typedef struct {
    int           pressed;
    unsigned char key;
} KeyEvent;

static KeyEvent s_key_queue[KEY_QUEUE_SIZE];
static int      s_key_head = 0;   /* write index (Python side) */
static int      s_key_tail = 0;   /* read index  (DOOM side)   */

/*
 * DG_PushKey — called from Python to inject a key event.
 * pressed: 1 = key down, 0 = key up
 * key:     doomkeys.h constant (e.g. KEY_ENTER = 0x0d)
 */
void DG_PushKey(int pressed, unsigned char key)
{
    int next = (s_key_head + 1) % KEY_QUEUE_SIZE;
    if (next == s_key_tail) return; /* queue full, drop */
    s_key_queue[s_key_head].pressed = pressed;
    s_key_queue[s_key_head].key     = key;
    s_key_head = next;
}

/*
 * bs_add_key — called from BombSquad to inject a key event.
 * key:     doomkeys.h constant
 * pressed: 1 = key down, 0 = key up
 * (note: argument order matches the BombSquad plugin's call convention)
 */
void bs_add_key(unsigned char key, int pressed)
{
    DG_PushKey(pressed, key);
}

/* ── required DG_* callbacks ─────────────────────────────────────────────── */

void DG_Init(void)
{
    /* nothing to initialise — no window, no audio device */
    fprintf(stderr, "[dg] DG_Init called\n");
    fflush(stderr);
}

/*
 * DG_DrawFrame — called by I_FinishUpdate after it has finished blitting
 * I_VideoBuffer → DG_ScreenBuffer.  At this point DG_ScreenBuffer contains
 * a valid RGBA8888 640×400 frame.  We do nothing here; Python reads
 * DG_ScreenBuffer directly after doomgeneric_Tick() returns.
 */
void DG_DrawFrame(void)
{
    bs_frame_ready = 1;   /* signal BombSquad tick that a new frame is ready */
}

void DG_SleepMs(uint32_t ms)
{
    struct timespec ts;
    ts.tv_sec  = ms / 1000;
    ts.tv_nsec = (ms % 1000) * 1000000L;
    nanosleep(&ts, NULL);
}

uint32_t DG_GetTicksMs(void)
{
    struct timespec ts;
    clock_gettime(CLOCK_MONOTONIC, &ts);
    return (uint32_t)(ts.tv_sec * 1000 + ts.tv_nsec / 1000000);
}

/*
 * DG_GetKey — called by DOOM's input polling.
 * Returns 1 and fills *pressed/*key if an event is waiting, else 0.
 */
int DG_GetKey(int *pressed, unsigned char *key)
{
    if (s_key_tail == s_key_head) return 0;
    *pressed = s_key_queue[s_key_tail].pressed;
    *key     = s_key_queue[s_key_tail].key;
    s_key_tail = (s_key_tail + 1) % KEY_QUEUE_SIZE;
    return 1;
}

void DG_SetWindowTitle(const char *title)
{
    fprintf(stderr, "[dg] window title: %s\n", title);
    fflush(stderr);
}
