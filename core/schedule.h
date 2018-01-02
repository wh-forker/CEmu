#ifndef SCHEDULE_H
#define SCHEDULE_H

#ifdef __cplusplus
extern "C" {
#endif

#include <stdint.h>
#include <stdbool.h>
#include <stdio.h>

enum clock_id { CLOCK_CPU, CLOCK_48M, CLOCK_24M, CLOCK_12M, CLOCK_6M, CLOCK_32K,
                CLOCK_1, CLOCK_NUM_ITEMS };

enum sched_item_id {
    SCHED_SECOND,

    SCHED_THROTTLE,
    SCHED_KEYPAD,
    SCHED_LCD,
    SCHED_RTC,
    SCHED_OSTIMER,
    SCHED_TIMER1,
    SCHED_TIMER2,
    SCHED_TIMER3,
    SCHED_WATCHDOG,

    SCHED_FIRST_EVENT = SCHED_THROTTLE,
    SCHED_LAST_EVENT = SCHED_WATCHDOG,

    SCHED_LCD_DMA,
    SCHED_USB_DMA,

    SCHED_FIRST_DMA = SCHED_LCD_DMA,
    SCHED_LAST_DMA = SCHED_USB_DMA,

    SCHED_NUM_ITEMS
};

struct sched_item {
    enum clock_id clock;
    int second; /* -1 = disabled */
    uint32_t tick;
    uint32_t cputick;
    union sched_callback {
        void (*event)(enum sched_item_id id);
        uint8_t (*dma)(enum sched_item_id id);
    } callback;
};

typedef struct sched_state {
    struct sched_item items[SCHED_NUM_ITEMS];
    uint32_t clockRates[CLOCK_NUM_ITEMS];
    struct sched_event {
        enum sched_item_id next;
    } event;
    struct sched_dma {
        enum sched_item_id next;
    } dma;
} sched_state_t;

/* Global SCHED state */
extern sched_state_t sched;

/* Available Functions */
void sched_reset(void);
void sched_process_pending_events(void);
void sched_clear(enum sched_item_id id);
void sched_set(enum sched_item_id id, uint64_t ticks);
void sched_repeat(enum sched_item_id id, uint64_t ticks);
void sched_repeat_relative(enum sched_item_id id, enum sched_item_id base_id, uint64_t ticks);
void sched_set_clocks(enum clock_id count, uint32_t *new_rates);

void dma_delay(uint8_t pendingAccessDelay);

uint64_t event_next_cycle(enum sched_item_id id);
uint64_t event_ticks_remaining(enum sched_item_id id);

/* Save/Restore */
bool sched_restore(FILE *image);
bool sched_save(FILE *image);

#ifdef __cplusplus
}
#endif

#endif
