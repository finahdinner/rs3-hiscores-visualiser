import json
import os
import sys
import pandas as pd
import bar_chart_race as bcr
from datetime import datetime, timedelta


if os.environ.get("DEBUG") == "false": # if in production
    debug_prefix = ""
else:
    debug_prefix = "TEST_"

BAR_RACE_VIDEOS_DIR = f"{debug_prefix}bar_races"
RAW_DATA_DIR_PATH = f"{debug_prefix}raw_scraped_data2"
HELPER_FILES_DIR_PATH = "helper_files"


def get_full_file_path(raw_data_dir_path, file_name):
    return os.path.join(os.path.dirname(__file__), raw_data_dir_path, file_name) # absolute path to the json file


def get_data_from_json_file(full_file_path) -> dict|None:
    if ".json" not in os.path.basename(full_file_path):
        return
    with open(full_file_path, "r", encoding="utf-8") as f:
        file_content = f.read()
        file_content_dict = json.loads(file_content)
    return file_content_dict


def organise_dict_data(file_content_dict):    
    if file_content_dict["data"]: # if not an empty list
        hiscores_data = {}
        for hiscores_item in file_content_dict["data"]:
            skill_name = hiscores_item["skill"]["skill"]
            skill_data = json.loads(hiscores_item["skill_data"]) # convert json str into list 
            hiscores_data[skill_name] = skill_data
    else:
        hiscores_data = {}
    # append all the data corresponding to this timestamp, to all_organised_data
    file_data = {
        "timestamp": file_content_dict["timestamp"],
        "hiscores": hiscores_data
    }
    return file_data


def sort_all_data_by_date(all_file_data):
    return sorted(all_file_data, key=lambda file_data: file_data["timestamp"])


def get_unique_users_per_skill(data: list[dict]) -> dict:
    unique_skills = list(data[0]["hiscores"].keys())
    unique_users_per_skill = {skill: set() for skill in unique_skills} # dict of key:set pairs

    for data_point in data:
        for skill in unique_skills:
            try:
                for user in data_point["hiscores"][skill]:
                    unique_users_per_skill[skill].add(user["name"])
            except KeyError:
                pass
    
    # print(unique_users_per_skill)
    # for k, v in unique_users_per_skill.items():
    #     print(f"{k}: {len(v)} users")

    return unique_users_per_skill


def create_df(data: list[dict], unique_users_per_skill: dict, skill: str, use_each_n=None, bars_visible=10) -> pd.DataFrame:
    """
    Produce a dataframe to be used for the bar race video
    index: date
    column for each unique player. each row is their xp at a given time
    their xp for each row is 0 unless they are recorded in the hiscores at that time
    """
    unique_players = unique_users_per_skill[skill]
    # print(unique_players)
    df = pd.DataFrame(
        data=None,
        columns=list(unique_players)
    )

    # iterate through the data points and determine if I want to use a certain data point
    # based on the timestamp and the increment i specified
    # if the data is empty for whatever reason, just duplicate the values from the last point
    # for each data point I want to add a new row with the values given by the hiscores data
    # add it with the index specified by the timestamp

    def is_valid_frame(frame_num, num_frames):
        """ determine if a given frame number is valid, given the value of use_each_n given to create_df"""
        return (use_each_n is None) or (frame_num % use_each_n == 0) or (iter_count == num_frames-1)


    lowest_visible_xp = 1 # start at 1 so lowest_visible_xp-1 = 0
    # max_visible_xp = 0
    for iter_count, data_point in enumerate(data):

        if not is_valid_frame(iter_count, num_frames=len(data)):
            continue

        new_row = {player:lowest_visible_xp-1 for player in df.columns}
        # check through the gathered data and add any matching xp values
        this_date = datetime.strptime(data_point["timestamp"], "%Y-%m-%d %H:%M:%S")
        try:
            this_hiscores_data = data_point["hiscores"][skill]
        except KeyError: # if no data, skip this data_point
            continue

        for player in this_hiscores_data:
            xp_int = int(player["score"].replace(",",""))
            new_row[player["name"]] = xp_int
            # if player["rank"] == str(bars_visible):
            #     lowest_visible_xp = xp_int
            # if player["rank"] == "1":
            #     max_visible_xp = xp_int

        # increase each value by a little bit to keep the bars moving
        increase_amt = 137
        new_row = {k:(v+increase_amt) for k, v in new_row.items()}
        sorted_xp_values_desc = sorted(new_row.values(), reverse=True)
        lowest_visible_xp = sorted_xp_values_desc[bars_visible]
        # print(lowest_visible_xp)
        # max_visible_xp = sorted_xp_values_desc[0]

        # add the row to the main dataframe
        new_row_df = pd.DataFrame(data=new_row, index=[this_date])
        # print(new_row_df.iloc[-1]["Glue"])

        df = pd.concat([df, new_row_df])

        print(this_date)

    # Convert all columns to numeric dtype
    for col in df.columns:
        df[col] = pd.to_numeric(df[col], errors='coerce')

    print(df)
    return df


def get_xp_per_level(xp_per_level_file_path) -> dict:
    import csv
    with open(xp_per_level_file_path, "r", encoding='utf-8-sig') as f:
        reader = csv.DictReader(f)
        xp_per_level = {}
        for row in reader:
            xp_per_level[row["Level"]] = int(row["XP"].replace(",",""))
    return xp_per_level


def create_bar_race(df, bars_visible, race_started_at, steps_per_period):
    """
    Create a bar chart race from the dataframe given
    """
    # get xp values per level
    xp_per_level = get_xp_per_level(os.path.join(HELPER_FILES_DIR_PATH, "xp_per_level.csv"))

    def get_level_from_xp(xp) -> int:
        xp_per_level = get_xp_per_level(os.path.join(HELPER_FILES_DIR_PATH, "xp_per_level.csv"))
        level = 1
        for level_compare, xp_compare in enumerate(sorted(xp_per_level.values()), 1):
            if xp_compare > xp:
                level = level_compare - 1
                break
        return level

    
    def get_time_since_start(start_time: datetime, curr_time: datetime) -> str:
        td: timedelta = curr_time - start_time
        td_days, seconds_in_hours = divmod(td.total_seconds(), (24*3600))
        td_days = int(td_days)
        td_hours = int(seconds_in_hours / 3600)

        since_str = "Since Release"

        if td_days > 1:
            days_str = f"{td_days} Days & "
        elif td_days == 1:
            days_str = f"{td_days} Day & "
        else:
            days_str = ""

        if td_hours == 1:
            hours_str = f"{td_hours} Hour "
        else:
            hours_str = f"{td_hours} Hours "

        return days_str + hours_str + since_str

    # hours_tracker is used to display, eg, "10 Hours Since Release" on the video
    hours_tracker = []
    for i in range(df.shape[0]): # for each row in the df
        time_str = get_time_since_start(start_time=race_started_at,curr_time=df.index[i])
        for _ in range(steps_per_period):
            hours_tracker.append(time_str)
    hours_tracker = iter(hours_tracker) # so I can use the next() keyword on it

    def period_summary(values, ranks):
        highest_xp = values.nlargest(1).values[0]
        highest_level = get_level_from_xp(highest_xp)
        sum_of_visible_xp = f"{values.nlargest(bars_visible).sum():,.0f}"
        # time_since_release = get_time_since_start(start_time=race_started_at, curr_time=values.index)
        return {
            'x': .98,
            'y': .12,
            'ha': 'right',
            'va': 'center',
            'size': '30',
            'color': 'mediumblue',
            's': f"""{next(hours_tracker)}
                    Highest Level: {highest_level}
                    Top {bars_visible} Combined XP: {sum_of_visible_xp}"""
        }


    time_now = datetime.strftime(datetime.now(), "%Y-%m-%d_%H_%M_%S")
    bcr.bar_chart_race(
        df,
        filename=os.path.join(BAR_RACE_VIDEOS_DIR, f"bar_race_{time_now}.mp4"),
        figsize=(16,9),
        n_bars=10,
        dpi=120,
        interpolate_period=True,
        period_length=200,
        steps_per_period=steps_per_period, # fps = steps_per_period * 10 (default fps is 20, aka steps_per_period is 10)
        filter_column_colors=True,
        shared_fontdict={'family': 'RuneScape Bold Font', 'weight': 'bold', 'color': 'black'},
        bar_label_size=24,
        tick_label_size=18,
        period_label={'x': .70, 'y': .25, 'ha': 'right', 'va': 'center', 'size': '30', 'color': 'dimgray'},
        period_fmt='%Y-%m-%d -- %H:%I %p',
        # period_summary_func=lambda v, r: {
        #     'x': .70,
        #     'y': .15,
        #     'ha': 'right',
        #     'va': 'center',
        #     's': f"""Highest level: {v.nlargest(1)}\n
        #             Total value: {v.nlargest(10).sum():,.0f}"""
        # }
        period_summary_func=period_summary
    )


def main():
    import time
    t1 = time.time()    
    all_file_data = []
    for file_name in os.listdir(RAW_DATA_DIR_PATH):
        if ".json" not in file_name:
            continue
        full_file_path = get_full_file_path(raw_data_dir_path=RAW_DATA_DIR_PATH, file_name=file_name)
        data_dict = get_data_from_json_file(full_file_path)
        data_dict_organised = organise_dict_data(data_dict) if data_dict else data_dict
        all_file_data.append(data_dict_organised)
    all_sorted_data = sort_all_data_by_date(all_file_data)
    unique_users_per_skill = get_unique_users_per_skill(all_sorted_data)
    bars_visible = 10
    df = create_df(
        data=all_sorted_data,
        unique_users_per_skill=unique_users_per_skill,
        skill="necromancy",
        use_each_n=None,
        bars_visible=bars_visible
    )
    # df_transposed = df
    # df_transposed = df.transpose()
    # df_transposed.to_csv("df2.csv") # for Flourish
    necromancy_release_time = datetime.strptime("2023-08-07 12-00-00", "%Y-%m-%d %H-%M-%S")
    print(necromancy_release_time)
    bar_race_video = create_bar_race(df, bars_visible=bars_visible, race_started_at=necromancy_release_time, steps_per_period=6)
    print(time.time() - t1)

    # df = create_df(all_sorted_data)
    # print(df)

    # import pprint
    # for item in all_sorted_data:
    #     pprint.pprint(item)
    #     print()
    #     print()
    # print(len(all_sorted_data))





if __name__ == "__main__":
    main()
    


"""
all_file_data = [
    {
        "timestamp": <timestamp>,
        "hiscores": [
            <skill1>: {
            
            },
            <skill2>: {
            
            }
        ]
    },
    {
        "timestamp": <timestamp>,
        "hiscores": [
            <skill1>: {
            
            },
            <skill2>: {
            
            }
        ]
    },
]
"""

# def get_dict_size(obj):
#     size = sys.getsizeof(obj)
    
#     if isinstance(obj, dict):
#         for value in obj.values():
#             size += get_dict_size(value)
#     elif isinstance(obj, list) or isinstance(obj, tuple):
#         for item in obj:
#             size += get_dict_size(item)
#     elif isinstance(obj, str):
#         size += sys.getsizeof(obj)
    
#     return size

# print(get_dict_size((all_file_data)))