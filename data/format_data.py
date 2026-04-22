import json
import glob
import os
import sys

def calculate_means(data_dict):
    if not data_dict:
        return {}
    result_format = {}
    for key, val in data_dict.items():
        # 1. PRÍPAD: Ak je hodnota vnorený slovník (kategórie stateful/stateless)
        if isinstance(val, dict):
            result_format[key] = val

        # 2. PRÍPAD: Ak je to zoznam list jedneho z nasledujucich (P50, P90, P99)
        elif isinstance(val, list) and len(val) > 0 and key in ['P50_api', 'P90_api', 'P99_api']:
            result_format[key] = val
            print(f"Not calculating mean for {key} because it's a list percenile")

        # 3. PRÍPAD: Ak je to jednoduchý zoznam čísel (GenericPrometheus)
        elif isinstance(val, list) and len(val) > 0:
            result_format[key] = sum(val) / len(val)
        else:
            result_format[key] = None
    return result_format

if len(sys.argv) > 1:
    distro = sys.argv[1]
    print(f"Running analysis on {distro}")
else:
    print("No variable provided!")
    exit(100)

target_dir = f"{distro}_reports"


# process generic queries
prom_data = {}
pattern = "GenericPrometheusQuery*.json"
file_pattern = os.path.join(target_dir, pattern)
files = glob.glob(file_pattern)

for file_path in files:
    with open(file_path, 'r') as f:
        try:
            content = json.load(f)
            
            metrics = content['dataItems'][0]['data']
            
            for key, value in metrics.items():
                if key not in prom_data:
                    prom_data[key] = []
                prom_data[key].append(value)
            
        except (KeyError, IndexError, json.JSONDecodeError) as e:
            print(f"Skipping {file_path} due to error: {e}")

# process statefulpodstartup
pod_data = {}
pattern = "State*PodStartup*.json"
file_pattern = os.path.join(target_dir, pattern)
files = glob.glob(file_pattern)

for file_path in files:
    filename = os.path.basename(file_path).lower()
    category = "stateful" if "stateful" in filename else "stateless"
    category += "_small" if "small" in filename else "_big"

    if category not in pod_data:
        pod_data[category] = {}

    with open(file_path, 'r') as f:
        try:
            content = json.load(f)
            tmp_dict = {}
            for item in content['dataItems']:
                metric_name = item['labels']['Metric']
                data = item['data']
                
                values_tuple = (
                    data['Perc50'],
                    data['Perc90'],
                    data['Perc99']
                )

                if values_tuple == (0, 0, 0):
                    # there was an occurence of faulty tests showing wrong information, maybe 
                    raise KeyError("Values cannot be equal to 0 => faulty test")
                
                tmp_dict[metric_name] = values_tuple

            for metric_name in tmp_dict.keys():
                if metric_name not in pod_data[category]:
                    pod_data[category][metric_name] = []

                pod_data[category][metric_name].append(tmp_dict[metric_name])
            
        except (KeyError, IndexError, json.JSONDecodeError) as e:
            print(f"Skipping {file_path} due to error: {e}")

prom_formatted = calculate_means(prom_data)
# pod_means = calculate_means(pod_data)

summary_data = {
    "distro": distro,
    "prometheus": prom_formatted,
    "pod_startup": pod_data
}

output_filename = f"summary_{distro}.json"
with open(output_filename, "w") as f:
    json.dump(summary_data, f, indent=4)
