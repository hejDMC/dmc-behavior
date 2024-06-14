def get_habi_task():
    p_r = input("2afc task (no assumes gonogo/detection)? y/n:")
    while True:
        if p_r == 'y':
            task = '2afc'
            break
        elif p_r == 'n':
            task = 'gonogo'
            break
        else:
            print("please enter 'y' or 'n'")
        p_r = input("2afc task (no assumes gonogo/detection)? y/n:")
    return task

def habi_time_limit():
    '''
    Function to set the day of habituation and return the time limit (day 1: 15 min; day 2: 30 min; day 3: 60 min)
    to automatically terminate the script
    :return: habi_day: int
    :return: time_limit: int
    '''

    question_str = "what day of habituation is it (1/2/3)?:"
    habi_day = int(input(question_str))
    while True:
        if habi_day == 1:
            time_limit = 15  # min
            break
        elif habi_day == 2:
            time_limit = 30  # min
            break
        elif habi_day == 3:
            time_limit = 45  # min
            break
        else:
            print("please enter only the int (1, 2 or 3)")
        habi_day = input(question_str)

    return habi_day, time_limit