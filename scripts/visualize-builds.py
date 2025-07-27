#!/usr/bin/env python3
# pylint: disable=invalid-name

from utils import get_config_from_generator

HOURS = 24


def generate_days():
    DAYS = 7
    return {day: {hour: [] for hour in range(HOURS)} for day in range(DAYS)}


def populate_days(days):
    config = get_config_from_generator()
    for tree in config['tree_schedules']:
        name = tree['name']

        schedule = tree['schedule'].split(' ')
        schedule_days = tuple(map(int, schedule[-1].split(',')))
        schedule_hours = tuple(map(int, schedule[1].split(',')))

        # Roughly estimate how many hours each build runs, rounded up to nearest whole hour
        if 'android' in name or 'tip' in name:
            DURATION = 2
        elif 'mainline' in name or 'stable' in name:
            DURATION = 5
        elif 'next' in name:
            DURATION = 6
        else:  # older stable
            DURATION = 4

        for day in schedule_days:
            for hour in schedule_hours:
                for running_hour in range(hour, hour + DURATION):
                    loop_day = day
                    loop_hour = running_hour
                    # handle builds crossing a day
                    if loop_hour >= 24:
                        loop_day += 1
                        loop_hour -= 24
                    # handle late night Sunday build crossing over to Monday
                    if loop_day > 6:
                        loop_day -= 6
                    days[loop_day][loop_hour].append(name)


def visualize_data(days):
    CELL_WIDTH = 5
    CRON_TO_DAY = {
        0: 'Sunday',
        1: 'Monday',
        2: 'Tuesday',
        3: 'Wednesday',
        4: 'Thursday',
        5: 'Friday',
        6: 'Saturday',
    }
    DIVIDE = ' | '
    END = '   |'
    BLANK_DAY = ' ' * 12
    BLANK_ROW = f"{DIVIDE}{BLANK_DAY}{DIVIDE}{' ' * HOURS * CELL_WIDTH}{END}"
    HORIZONTAL_BORDER = ' ' + '-' * (len(BLANK_ROW) - 1)

    print(HORIZONTAL_BORDER)
    print(BLANK_ROW)

    for day, hours in days.items():
        row = [f"{CRON_TO_DAY[day]:^12}"]

        values = []
        for builds in hours.values():
            values.append(f"{len(builds):{CELL_WIDTH}}")
        row.append(''.join(values))

        print(f"{DIVIDE}{DIVIDE.join(row)}{END}")
        print(BLANK_ROW)

    print(HORIZONTAL_BORDER)

    print(f"{DIVIDE}{BLANK_DAY}{DIVIDE}    0", end='')
    for val in (val for val in range(1, HOURS) if val % 3 == 0):
        print(f"{val:{3 * CELL_WIDTH}}", end='')
    print(f"{' ' * 10}{END}")

    print(HORIZONTAL_BORDER)


def main():
    days = generate_days()
    populate_days(days)
    visualize_data(days)


if __name__ == '__main__':
    main()
