from datetime import datetime, time, timedelta

LECTURE_SLOT_START = time(hour=9, minute=30)
LECTURE_DURATION_MINUTES = 45
LECTURE_SLOT_COUNT = 5

def build_lecture_slots():
    slots = []
    current_start = datetime.combine(datetime.today(), LECTURE_SLOT_START)
    for index in range(LECTURE_SLOT_COUNT):
        current_end = current_start + timedelta(minutes=LECTURE_DURATION_MINUTES)
        slots.append(
            {
                "index": index,
                "label": f"Lecture {index + 1}",
                "start_time": current_start.time().replace(second=0, microsecond=0),
                "end_time": current_end.time().replace(second=0, microsecond=0),
            }
        )
        current_start = current_end
    return slots


LECTURE_SLOTS = build_lecture_slots()
