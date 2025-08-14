#!/usr/bin/env python3
# pylint: disable=invalid-name

import argparse
import csv
import sys
from utils import get_config_from_generator

HOURS = 24

CRON_TO_DAY = {
    0: "Sunday",
    1: "Monday",
    2: "Tuesday",
    3: "Wednesday",
    4: "Thursday",
    5: "Friday",
    6: "Saturday",
}


def generate_days():
    DAYS = 7
    return {day: {hour: [] for hour in range(HOURS)} for day in range(DAYS)}


def populate_days(days):
    config = get_config_from_generator()
    for tree in config["tree_schedules"]:
        name = tree["name"]

        schedule = tree["schedule"].split(" ")
        schedule_days = tuple(map(int, schedule[-1].split(",")))
        schedule_hours = tuple(map(int, schedule[1].split(",")))

        # Roughly estimate how many hours each build runs, rounded up to nearest whole hour
        duration = 4  # assume older stable
        if "android" in name or "tip" in name:
            duration = 2
        elif "mainline" in name or "stable" in name:
            duration = 5
        elif "next" in name:
            duration = 6

        for day in schedule_days:
            for hour in schedule_hours:
                for running_hour in range(hour, hour + duration):
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
    DIVIDE = " | "
    END = "   |"
    BLANK_DAY = " " * 12
    BLANK_ROW = f"{DIVIDE}{BLANK_DAY}{DIVIDE}{' ' * HOURS * CELL_WIDTH}{END}"
    HORIZONTAL_BORDER = " " + "-" * (len(BLANK_ROW) - 1)

    print(HORIZONTAL_BORDER)
    print(BLANK_ROW)

    for day, hours in days.items():
        row = [f"{CRON_TO_DAY[day]:^12}"]

        values = []
        for builds in hours.values():
            values.append(f"{len(builds):{CELL_WIDTH}}")
        row.append("".join(values))

        print(f"{DIVIDE}{DIVIDE.join(row)}{END}")
        print(BLANK_ROW)

    print(HORIZONTAL_BORDER)

    print(f"{DIVIDE}{BLANK_DAY}{DIVIDE}    0", end="")
    for val in (val for val in range(1, HOURS) if val % 3 == 0):
        print(f"{val:{3 * CELL_WIDTH}}", end="")
    print(f"{' ' * 10}{END}")

    print(HORIZONTAL_BORDER)


def output_csv(days, output_file=None):
    output = output_file if output_file else sys.stdout
    writer = csv.writer(output)

    header = ["Day"] + [str(hour) for hour in range(HOURS)]
    writer.writerow(header)

    for day, hours in days.items():
        row = [CRON_TO_DAY[day]]
        for hour in range(HOURS):
            row.append(len(hours[hour]))
        writer.writerow(row)


def output_pretty_table(days, output_file=None):
    output = output_file if output_file else sys.stdout

    header_cells = ["Day"] + [f"{hour:2d}" for hour in range(HOURS)]
    col_widths = [max(10, len(cell)) for cell in header_cells]

    for day, hours in days.items():
        col_widths[0] = max(col_widths[0], len(CRON_TO_DAY[day]))
        for hour in range(HOURS):
            col_widths[hour + 1] = max(col_widths[hour + 1],
                                       len(str(len(hours[hour]))))

    top_border = "┌" + "┬".join("─" * width for width in col_widths) + "┐"
    print(top_border, file=output)

    header_row = ("│" +
                  "│".join(f"{cell:^{width}}"
                           for cell, width in zip(header_cells, col_widths)) +
                  "│")
    print(header_row, file=output)
    header_sep = "├" + "┼".join("─" * width for width in col_widths) + "┤"
    print(header_sep, file=output)

    for day, hours in days.items():
        row_cells = [CRON_TO_DAY[day]
                     ] + [str(len(hours[hour])) for hour in range(HOURS)]
        data_row = ("│" +
                    "│".join(f"{cell:^{width}}"
                             for cell, width in zip(row_cells, col_widths)) +
                    "│")
        print(data_row, file=output)

    # Bottom border
    bottom_border = "└" + "┴".join("─" * width for width in col_widths) + "┘"
    print(bottom_border, file=output)


def parse_args():
    parser = argparse.ArgumentParser(
        description="Visualize build distribution across days and hours")
    parser.add_argument(
        "--format",
        choices=["table", "csv", "pretty"],
        default="pretty",
        help="Output format (default: pretty)",
    )
    parser.add_argument("--output",
                        "-o",
                        type=str,
                        help="Output file (default: stdout)")
    return parser.parse_args()


def main():
    args = parse_args()

    days = generate_days()
    populate_days(days)

    output_file = None
    if args.output:
        # pylint: disable-next=consider-using-with
        output_file = open(  # noqa: SIM115
            args.output, "w", encoding="utf-8", newline="")

    try:
        if args.format == "csv":
            output_csv(days, output_file)
        elif args.format == "pretty":
            output_pretty_table(days, output_file)
        # regular table
        elif output_file:
            # evil hack so I don't have to rewrite visualize_data() prints
            original_stdout = sys.stdout
            sys.stdout = output_file
            visualize_data(days)
            sys.stdout = original_stdout
        else:
            visualize_data(days)
    finally:
        if output_file:
            output_file.close()


if __name__ == "__main__":
    main()
