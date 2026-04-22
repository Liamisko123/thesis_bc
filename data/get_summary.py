import json
import glob
import matplotlib.pyplot as plt
import seaborn as sns
import pandas as pd
import numpy as np

K3SCOLOR = "#ce9e3e" # Orange-ish yellow
K0SCOLOR = "#1f77b4" # Blue
MICROK8SCOLOR = "#ff2d2d" # Red

DISTRO_PALETTE = {
    'k0s': K0SCOLOR,
    'k3s': K3SCOLOR,
    'microk8s': MICROK8SCOLOR
}

def load_summaries():
    all_summaries = []
    # Nájde všetky súbory začínajúce na summary_
    for file_path in glob.glob("summary_*.json"):
        print(f"Opening file at file_path: {file_path}")
        with open(file_path, 'r') as f:
            all_summaries.append(json.load(f))
    return all_summaries

def plot_radar_chart(summaries):
    # 1. Define the metrics we want to compare
    metrics = [
        'avg_cpu_system_old', 'avg_mem', 'avg_context_switches', 
        'avg_disk_latency', 'avg_hardware_interrupts', 'avg_disk_space'
    ]

    labels = [
        'AVG CPU System Utilization', 'AVG Memory Utilization', 'AVG Context Switches', 
        'AVG Disk Latency', 'AVG Hardware Interrupts', 'AVG Disk Space Used'
    ]
    
    # 2. Extract the MEAN of the 100 samples for each distro
    radar_data = []
    for s in summaries:
        distro_name = s['distro']
        prom = s.get('prometheus', {})
        
        row = {'Distro': distro_name}
        for m in metrics:
            val = prom.get(m, 0)
            # If it's a list (your 100 samples), take the average. If float, use as is.
            row[m] = np.mean(val) if isinstance(val, list) else val
        radar_data.append(row)
    
    df = pd.DataFrame(radar_data).set_index('Distro')
    
    # 3. Normalization (Scale 0 to 1) 
    # This ensures "8000 switches" and "0.7 CPU" both fit on the same chart
    df_norm = df / df.max() 
    
    # 4. Set up Radar Chart geometry
    num_vars = len(labels)
    angles = np.linspace(0, 2 * np.pi, num_vars, endpoint=False).tolist()
    
    # Close the loop for the chart
    angles += angles[:1]
    
    fig, ax = plt.subplots(figsize=(8, 8), subplot_kw=dict(polar=True))
    
    # 5. Plot each distro
    colors = [K0SCOLOR, K3SCOLOR, MICROK8SCOLOR]
    for i, (distro, row) in enumerate(df_norm.iterrows()):
        values = row.values.flatten().tolist()
        values += values[:1] # Close the loop
        
        ax.plot(angles, values, linewidth=2, label=distro, color=colors[i % len(colors)])
        ax.fill(angles, values, alpha=0.1, color=colors[i % len(colors)])

    # Add labels
    ax.set_theta_offset(np.pi / 2)
    ax.set_theta_direction(-1)
    ax.set_xticks(angles[:-1])
    ax.set_xticklabels(labels)
    
    # Add legend and title
    plt.legend(loc='upper right', bbox_to_anchor=(1.3, 1.1))
    plt.savefig('radar_performance_comparison.png', dpi=300, bbox_inches='tight')
    print("Radar chart saved as 'radar_performance_comparison.png'")

def plot_stacked_cpu_workload(summaries):
    rows = []
    for s in summaries:
        distro = s['distro']
        prom = s.get('prometheus', {})
        
        # Taking the mean of your 100 benchmark runs
        # Since avg_cpu is total utilization (0-1), 
        # and avg_cpu_system is system utilization (0-1).
        total_val = prom.get('avg_cpu', 0)
        sys_val = prom.get('avg_cpu_system', 0)
        
        avg_total = np.mean(total_val) if isinstance(total_val, list) else total_val
        avg_system = np.mean(sys_val) if isinstance(sys_val, list) else sys_val
        
        # User workload is what's left after accounting for the 'K8s tax'
        avg_user = avg_total - avg_system
        
        rows.append({
            'Distro': distro,
            'User Workload': avg_user,
            'System Overhead': avg_system
        })

    df = pd.DataFrame(rows).set_index('Distro')

    # Plotting
    # Using academic-friendly colors (Teal for User, Burnt Orange for System)
    ax = df.plot(kind='bar', stacked=True, figsize=(10, 6), color=['#66c2a5', '#fc8d62'])
    
    # plt.title('Normalized CPU Workload Distribution (User vs System)', fontsize=14)
    plt.ylabel('Normalized CPU Usage (0.0 - 1.0)', fontsize=12)
    plt.xlabel('Distribution', fontsize=12)
    plt.legend(title="CPU Component", frameon=True)
    plt.xticks(rotation=0)
    plt.ylim(0, 1.0) # Utilization baseline
    plt.grid(axis='y', linestyle='--', alpha=0.5)

    # --- THE LABELING LOGIC ---
    for i, (idx, row) in enumerate(df.iterrows()):
        user_val = row['User Workload']
        sys_val = row['System Overhead']
        total = user_val + sys_val

        # 1. Label the "User Workload" (bottom segment)
        if user_val > 0.05: # Only label if big enough to see
            ax.text(i, user_val / 2, f'{user_val:.3f}', 
                    ha='center', va='center', color='white', fontweight='bold')

        # 2. Label the "System Overhead" (top segment)
        if sys_val > 0.05:
            ax.text(i, user_val + (sys_val / 2), f'{sys_val:.3f}', 
                    ha='center', va='center', color='white', fontweight='bold')

        # 3. Label the TOTAL on top of the bar
        ax.text(i, total + 0.02, f'Total: {total:.3f}', 
                ha='center', va='bottom', color='black', fontsize=10, fontweight='bold')

    plt.savefig('stacked_cpu_normalized.png', dpi=300, bbox_inches='tight')
    print("Chart saved as 'stacked_cpu_normalized.png'")

def plot_psi_comparison(summaries):
    rows = []
    metric_map = {
        'avg_stall_cpu': 'CPU Stall',
        'avg_stall_mem': 'Memory Stall',
        'avg_stall_io': 'I/O Stall'
    }

    for s in summaries:
        distro = s['distro']
        prom = s.get('prometheus', {})
        
        for key, label in metric_map.items():
            val = prom.get(key, 0)
            mean_val = np.mean(val) if isinstance(val, list) else val
            
            # CONVERSION: Multiply ratio by 100 to get Percentage
            percentage_val = mean_val * 100
            
            rows.append({
                'Distro': distro,
                'Metric': label,
                'Value': percentage_val
            })

    df = pd.DataFrame(rows)

    plt.figure(figsize=(12, 7))
    sns.set_theme(style="whitegrid")

    ax = sns.barplot(data=df, x='Metric', y='Value', hue='Distro', palette=DISTRO_PALETTE)

    # plt.title('System Resource Pressure (PSI) Comparison', fontsize=15, pad=20)
    plt.ylabel('Stall Time Percentage (%)', fontsize=12) # Clarified Label
    plt.xlabel('Resource Type', fontsize=12)
    plt.ylim(0, 100) # Sets the scale to percentage
    plt.legend(title='Distribution', loc='upper right')

    for p in ax.patches:
        if p.get_height() > 0:
            ax.annotate(f'{p.get_height():.3f}%', 
                        (p.get_x() + p.get_width() / 2., p.get_height()),
                        ha='center', va='bottom', fontsize=9, xytext=(0, 5),
                        textcoords='offset points', fontweight='bold')

    plt.tight_layout()
    plt.savefig('psi_comparison_percentage.png', dpi=300)

def plot_grouped_io_metrics(summaries):
    # 1. Prepare the data structure
    nodes = [f'pi{i}' for i in range(1, 6)]
    metrics_to_track = ['avg_cpu_iowait', 'avg_disk_latency']
    rows = []

    for s in summaries:
        distro = s['distro']
        prom = s.get('prometheus', {})
        for node in nodes:
            for m_base in metrics_to_track:
                key = f'{m_base}_{node}'
                val = prom.get(key, 0)
                mean_val = np.mean(val) if isinstance(val, list) else val
                
                rows.append({
                    'Distro': distro,
                    'Node': node.upper(),
                    'Metric': 'I/O Wait' if 'iowait' in m_base else 'Disk Latency (s)',
                    'Value': mean_val
                })

    df = pd.DataFrame(rows)

    # --- IMAGE 1: CPU I/O WAIT ---
    plt.figure(figsize=(12, 6))
    ax1 = sns.barplot(data=df[df['Metric'] == 'I/O Wait'], x='Node', y='Value', 
                      hue='Distro', palette=DISTRO_PALETTE)
    # plt.title('CPU I/O Wait Comparison per Node', fontsize=14)
    plt.ylabel('Utilization (0.000 - 1.000)', fontsize=12)
    plt.grid(axis='y', linestyle='--', alpha=0.3)
    plt.legend(title="Distribution", loc='upper left')
    
    # Add 3-decimal labels
    for p in ax1.patches:
        if p.get_height() > 0:
            ax1.annotate(f'{p.get_height():.3f}', 
                         (p.get_x() + p.get_width() / 2., p.get_height()),
                         ha='center', va='bottom', fontsize=9, xytext=(0, 3),
                         textcoords='offset points', fontweight='bold')
    
    plt.tight_layout()
    plt.savefig('io_wait_per_node.png', dpi=300)
    print("Saved: io_wait_per_node.png")


    # --- IMAGE 2: DISK LATENCY ---
    plt.figure(figsize=(12, 6))
    ax2 = sns.barplot(data=df[df['Metric'] == 'Disk Latency (s)'], x='Node', y='Value', 
                      hue='Distro', palette=DISTRO_PALETTE)
    # plt.title('Disk Latency Comparison per Node', fontsize=14)
    plt.ylabel('Latency (Seconds)', fontsize=12)
    plt.grid(axis='y', linestyle='--', alpha=0.3)
    plt.legend(title="Distribution", loc='upper left')

    # Add 3-decimal labels
    for p in ax2.patches:
        if p.get_height() > 0:
            ax2.annotate(f'{p.get_height():.3f}', 
                         (p.get_x() + p.get_width() / 2., p.get_height()),
                         ha='center', va='bottom', fontsize=9, xytext=(0, 3),
                         textcoords='offset points', fontweight='bold')

    plt.tight_layout()
    plt.savefig('disk_latency_per_node.png', dpi=300)
    print("Saved: disk_latency_per_node.png")

def plot_dual_axis_network(summaries):
    rows = []
    for s in summaries:
        distro = s['distro']
        prom = s.get('prometheus', {})
        
        # Extract and calculate mean from the 100-run lists
        retrans = prom.get('avg_net_retransmission', 0)
        total_net = prom.get('sum_net_total', 0)
        
        avg_retrans = np.mean(retrans) if isinstance(retrans, list) else retrans
        avg_total = np.mean(total_net) if isinstance(total_net, list) else total_net
        
        rows.append({
            'Distro': distro,
            'Retransmission': avg_retrans,
            'Total Traffic': avg_total
        })

    df = pd.DataFrame(rows)
    
    fig, ax1 = plt.subplots(figsize=(11, 7))

    # Define X positions
    x = np.arange(len(df['Distro']))
    width = 0.35 # Width of the bars

    # --- LEFT AXIS: Retransmission (Reliability) ---
    color_retrans = '#3498db' # Professional Blue
    rects1 = ax1.bar(x - width/2, df['Retransmission'], width, 
                     label='Retransmission Rate', color=color_retrans, alpha=0.7)
    
    ax1.set_xlabel('Kubernetes Distribution', fontsize=12)
    ax1.set_ylabel('Avg. Retransmission Rate (0.000 - 1.000)', color=color_retrans, fontsize=12)
    ax1.tick_params(axis='y', labelcolor=color_retrans)
    ax1.set_xticks(x)
    ax1.set_xticklabels(df['Distro'])
    ax1.grid(axis='y', linestyle='--', alpha=0.3)

    # --- RIGHT AXIS: Total Traffic (Throughput) ---
    ax2 = ax1.twinx()
    color_total = '#e67e22' # Professional Orange
    rects2 = ax2.bar(x + width/2, df['Total Traffic'], width, 
                     label='Total Network Traffic', color=color_total, alpha=0.7)
    
    ax2.set_ylabel('Sum Net Total Traffic', color=color_total, fontsize=12)
    ax2.tick_params(axis='y', labelcolor=color_total)

    # Function to add 3-decimal point labels
    def add_labels(rects, ax, color, offset_side):
        for rect in rects:
            height = rect.get_height()
            ax.annotate(f'{height:.3f}',
                        xy=(rect.get_x() + rect.get_width() / 2, height),
                        xytext=(0, 5), # 5 points vertical offset
                        textcoords="offset points",
                        ha='center', va='bottom', fontsize=9, 
                        color=color, fontweight='bold')

    add_labels(rects1, ax1, color_retrans, -1)
    add_labels(rects2, ax2, color_total, 1)

    # plt.title('Network Analysis: Packet Retransmission vs. Total Throughput', fontsize=15, pad=25)
    
    # Combined legend for both axes
    lines, labels = ax1.get_legend_handles_labels()
    lines2, labels2 = ax2.get_legend_handles_labels()
    ax1.legend(lines + lines2, labels + labels2, loc='upper left', frameon=True)

    fig.tight_layout()
    plt.savefig('network_dual_axis_3dp.png', dpi=300)
    print("Dual axis network chart saved as 'network_dual_axis_3dp.png'")

def plot_grouped_net_total_pi(summaries):
    rows = []
    nodes = [f'pi{i}' for i in range(1, 6)]
    
    for s in summaries:
        distro = s['distro']
        prom = s.get('prometheus', {})
        
        for node in nodes:
            key = f'sum_net_total_{node}'
            val = prom.get(key, 0)
            # Calculate mean of the 100 runs
            mean_val = np.mean(val) if isinstance(val, list) else val
            
            rows.append({
                'Distro': distro,
                'Node': node.upper(),
                'Value': mean_val
            })
            
    df = pd.DataFrame(rows)
    
    plt.figure(figsize=(12, 7))
    ax = sns.barplot(data=df, x='Node', y='Value', hue='Distro', palette=DISTRO_PALETTE)
    
    plt.title('Total Network Traffic Volume per Node', fontsize=14)
    plt.ylabel('Aggregate Traffic (Normalized)', fontsize=12)
    plt.xlabel('Cluster Node', fontsize=12)
    plt.grid(axis='y', linestyle='--', alpha=0.3)
    plt.legend(title='Distribution', loc='upper right')

    # Add labels with 3 decimal points
    for p in ax.patches:
        if p.get_height() > 0:
            ax.annotate(f'{p.get_height():.3f}', 
                        (p.get_x() + p.get_width() / 2., p.get_height()),
                        ha='center', va='bottom', fontsize=9, xytext=(0, 3),
                        textcoords='offset points', fontweight='bold')

    plt.tight_layout()
    plt.savefig('net_total_per_node.png', dpi=300)
    print("Grouped network chart saved.")

def plot_api_latency_boxplot(summaries):
    rows = []
    # Mapping the JSON keys to readable labels
    percentile_map = {
        'P50_api': 'P50',
        'P90_api': 'P90',
        'P99_api': 'P99'
    }
    
    for s in summaries:
        distro = s['distro']
        prom = s.get('prometheus', {})
        
        for key, label in percentile_map.items():
            vals = prom.get(key, [])
            # We assume these are the lists of 100 runs
            for v in vals:
                rows.append({
                    'Distro': distro,
                    'Percentile': label,
                    'Latency (ms)': v * 1000  # Convert to ms
                })

    df = pd.DataFrame(rows)

    plt.figure(figsize=(12, 8))
    sns.set_theme(style="whitegrid")
    
    # Create the boxplot
    ax = sns.boxplot(
        data=df, 
        x='Distro', 
        y='Latency (ms)', 
        hue='Percentile', 
        palette='Set2',
        showfliers=True # This shows the 'dots' (outliers) which are important for P99
    )
    
    # plt.title('API Server Latency Stability (100 Runs)', fontsize=15, pad=20)
    plt.ylabel('Latency (Milliseconds)', fontsize=12)
    plt.xlabel('Distribution', fontsize=12)
    plt.legend(title='Percentile', loc='upper right')

    plt.savefig('api_latency_boxplot.png', dpi=300, bbox_inches='tight')
    print("API Latency Box Plot saved as 'api_latency_boxplot.png'")

def plot_pod_lifecycle_boxplots(summaries):
    """
    Two figures: one for StatefulSet, one for Deployment.
    Each is a 2x3 grid:
      rows    = load size (High Load top, Low Load bottom)
      columns = lifecycle stage (Create->Scheduled | Scheduled->Running | Running->Ready)
    schedule_to_watch is omitted (redundant sum of the two middle stages).
    Each box = one distro, hue = percentile (P50/P90/P99) shaded light to dark.
    """
    import matplotlib.colors as mcolors
    import matplotlib.patches as mpatches
 
    STAGES = [
        ('create_to_schedule', 'Create -> Scheduled'),
        ('schedule_to_run',    'Scheduled -> Running'),
        ('run_to_watch',       'Running -> Ready'),
    ]
    PERCENTILE_IDX = {'P50': 0, 'P90': 1, 'P99': 2}
    SHADE = {'P50': 0.0, 'P90': 0.35, 'P99': 0.60}
 
    def tint(hex_color, factor):
        r, g, b = mcolors.to_rgb(hex_color)
        return mcolors.to_hex((r + (1-r)*factor, g + (1-g)*factor, b + (1-b)*factor))
 
    def build_df(summaries, group_key, stage_key):
        rows = []
        for s in summaries:
            distro = s['distro']
            vals = s.get('pod_startup', {}).get(group_key, {}).get(stage_key, [])
            for triplet in vals:
                for pct, idx in PERCENTILE_IDX.items():
                    rows.append({'Distribution': distro, 'Percentile': pct,
                                 'Latency (ms)': triplet[idx]})
        return pd.DataFrame(rows)
 
    def draw_ax(ax, df, title, show_ylabel):
        distros = sorted(df['Distribution'].unique())
        df = df.copy()
        df['Distro_Pct'] = df['Distribution'] + '_' + df['Percentile']
        palette   = {f'{d}_{p}': tint(DISTRO_PALETTE.get(d, '#888'), SHADE[p])
                     for d in distros for p in ['P50', 'P90', 'P99']}
        hue_order = [f'{d}_{p}' for d in distros for p in ['P50', 'P90', 'P99']]
        sns.boxplot(data=df, x='Distribution', y='Latency (ms)',
                    hue='Distro_Pct', palette=palette, hue_order=hue_order,
                    showfliers=True, linewidth=0.7,
                    flierprops=dict(marker='o', markersize=2, alpha=0.5), ax=ax)
        ax.set_title(title, fontsize=11, fontweight='bold', pad=5)
        ax.set_xlabel('')
        ax.set_ylabel('Latency (ms)' if show_ylabel else '')
        ax.tick_params(axis='x', labelsize=10)
        ax.grid(axis='y', linestyle='--', alpha=0.4)
        ax.get_legend().remove()
 
    sns.set_theme(style='whitegrid', font_scale=1.05)
 
    WORKLOADS = [
        ('stateful',  'StatefulSet Pod Lifecycle Latency'),
        ('stateless', 'Deployment Pod Lifecycle Latency'),
    ]
 
    for wtype, fig_title in WORKLOADS:
        fig, axes = plt.subplots(3, 2, figsize=(10, 14))
        fig.suptitle(fig_title, fontsize=14, fontweight='bold', y=1.01)
 
        for col_idx, size in enumerate(['big', 'small']):
            group_key = f'{wtype}_{size}'
            col_label = 'Big Load (pi1..4)' if size == 'big' else 'Small Load (pi5)'
            for row_idx, (stage_key, stage_label) in enumerate(STAGES):
                ax = axes[row_idx][col_idx]
                df = build_df(summaries, group_key, stage_key)
                if df.empty:
                    ax.set_visible(False)
                    continue
                # Column header on top row only
                title = f'{col_label}\n{stage_label}' if row_idx == 0 else stage_label
                draw_ax(ax, df, title, show_ylabel=(col_idx == 0))
 
        # Shared legend
        import matplotlib.patches as mpatches
        handles = [
            mpatches.Patch(color=tint(DISTRO_PALETTE[d], SHADE[p]), label=f'{d} {p}')
            for d in sorted(DISTRO_PALETTE) for p in ['P50', 'P90', 'P99']
        ]
        fig.legend(handles=handles, title='Distribution / Percentile',
                   loc='lower center', bbox_to_anchor=(0.5, -0.04),
                   fontsize=9, frameon=True, ncols=9)
 
        plt.tight_layout()
        fname = f'pod_lifecycle_{wtype}.png'
        plt.savefig(fname, dpi=300, bbox_inches='tight')
        print(f"Saved: {fname}")
        plt.close()

data = load_summaries()
# plot_radar_chart(data)
# plot_stacked_cpu_workload(data)
plot_psi_comparison(data)
# plot_grouped_io_metrics(data)
# plot_dual_axis_network(data)
# plot_grouped_net_total_pi(data)
# plot_api_latency_boxplot(data)
# plot_pod_lifecycle_boxplots(data)
