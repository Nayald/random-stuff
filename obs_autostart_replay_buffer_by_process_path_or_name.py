import obspython as S
import psutil
from pathlib import Path


def start_replay_buffer():
    #print("start replay buffer")
    S.obs_frontend_replay_buffer_start()


def stop_replay_buffer():
    #print("stop replay buffer")
    S.obs_frontend_replay_buffer_stop()


def monitor_processes():
    found = False
    for p in psutil.process_iter(("exe", "name")):
        try:
            parents = Path(p.info["exe"]).parents
            if any(path in parents for path in paths):
                #print(f"{process.name()} in path list")
                found = True
                break

            if p.info["name"] in names:
                #print(f"{process.name()} is in name list")
                found = True
                break
        except:
            continue

    if found:
        #print(f"at least one process matches")
        start_replay_buffer()
    else:
        #print(f"no process matches")
        stop_replay_buffer()


paths = []
names = []
def script_update(props):
    global paths
    global names
    interval = S.obs_data_get_double(props, "interval")
    #print(f"Interval is set to {interval} seconds")
    paths = [Path(e) for e in map(str.strip, S.obs_data_get_string(props, "path_list").split(";")) if e]
    #print(f"Path list is", paths)
    names = [e for e in  map(str.strip, S.obs_data_get_string(props, "exe_list").split(";")) if e]
    #print(f"name list is", names)
    S.timer_remove(monitor_processes)
    if S.obs_data_get_bool(props, "enable"):
        S.timer_add(monitor_processes, int(1000 * interval))
    else:
        stop_replay_buffer()


def script_description():
    return ("A script that monitors running processes to enable/disable the replay buffer for those contained in specified directories or with "
            "explicitly given names")


def script_properties():
    props = S.obs_properties_create()
    S.obs_properties_add_bool(props, "enable", "Enable")
    S.obs_properties_add_float(props, "interval", "Refresh interval (in seconds):", 0.1, 3600, 0.1)
    paths = S.obs_properties_add_text(props, "path_list", "List of paths:", S.OBS_TEXT_DEFAULT)
    S.obs_property_set_long_description(paths, "A semicolon ( ; ) separated list of parent paths. The script will check if any the command lines of "
                                               "the running processes have a parent in the list.")
    names = S.obs_properties_add_text(props, "exe_list", "List of names:", S.OBS_TEXT_DEFAULT)
    S.obs_property_set_long_description(names, "A semicolon ( ; ) separated list of process names. The script will check if any of the names of the "
                                               "running processes are in the list.")
    return props


def script_defaults(props):
    S.obs_data_set_default_double(props, "interval", 2.5)
    S.obs_data_set_default_string(props, "path_list", "")
    S.obs_data_set_default_string(props, "exe_list", "")


def script_unload():
    stop_replay_buffer()
