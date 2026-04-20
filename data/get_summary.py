import json
import glob
import matplotlib.pyplot as plt
import seaborn as sns
import pandas as pd

def load_summaries():
    all_summaries = []
    # Nájde všetky súbory začínajúce na summary_
    for file_path in glob.glob("summary_*.json"):
        print(file_path)
        with open(file_path, 'r') as f:
            all_summaries.append(json.load(f))
    return all_summaries

def plot_everything(summaries):
    sns.set_theme(style="whitegrid")
    
    # --- 1. ZHROMAŽDENIE VŠETKÝCH DÁT ---
    rows_prom = []
    rows_startup = []

    for s in summaries:
        distro = s['distro']
        
        # Spracovanie Prometheus metrík (všetky kľúče v 'prometheus')
        prom = s.get('prometheus', {})
        for metric_name, value in prom.items():
            rows_prom.append({
                'Distro': distro,
                'Metric': metric_name,
                'Value': value
            })
            
        # Spracovanie Startup metrík (všetky kategórie a metriky)
        pod = s.get('pod_startup', {})
        for category, metrics in pod.items():
            for m_name, values in metrics.items():
                # values je [P50, P90, P99]
                for i, p_label in enumerate(['P50', 'P90', 'P99']):
                    rows_startup.append({
                        'Distro': distro,
                        'Typ': category.capitalize(),
                        'Metric': m_name,
                        'Percentile': p_label,
                        'Value': values[i]
                    })

    df_prom = pd.DataFrame(rows_prom)
    df_startup = pd.DataFrame(rows_startup)

    # --- 2. GRAF: VŠETKY PROMETHEUS METRIKY ---
    # Vytvorí mriežku grafov (jeden pre každú metriku: CPU, RAM, Disk, Net...)
    g_prom = sns.catplot(
        data=df_prom, x='Distro', y='Value', col='Metric',
        kind='bar', col_wrap=3, sharey=False, palette='magma', height=4
    )
    g_prom.set_titles("{col_name}")
    g_prom.fig.subplots_adjust(top=0.9)
    g_prom.fig.suptitle('Kompletné systémové metriky (Prometheus)', fontsize=16)
    g_prom.savefig('all_prometheus_metrics.png', dpi=300)

    # --- 3. GRAF: VŠETKY STARTUP LATENCIE (P50 vs P99) ---
    # Porovnáme P50 a P99 pre každú fázu (pod_startup, schedule_to_run, atď.)
    # Filtrujeme len P50 a P99, aby graf nebol preplnený (P90 je zvyčajne v strede)
    df_startup_filtered = df_startup[df_startup['Percentile'].isin(['P50', 'P99'])]
    
    g_pod = sns.catplot(
        data=df_startup_filtered, x='Distro', y='Value', 
        hue='Percentile', col='Metric', row='Typ',
        kind='bar', sharey=False, palette='viridis', height=4, aspect=1.2
    )
    g_pod.set_axis_labels("", "Čas (ms)")
    g_pod.set_titles("{row_name}: {col_name}")
    g_pod.fig.subplots_adjust(top=0.92)
    g_pod.fig.suptitle('Kompletná analýza latencií (P50 vs P99)', fontsize=18)
    g_pod.savefig('all_startup_latencies.png', dpi=300)

    plt.show()

data = load_summaries()
plot_everything(data)