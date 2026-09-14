"""
This script processes and visualizes NTC temperature data from AMAC modules
undergoing thermal cycling. It evaluates temperature stability across multiple
measurements, isolating "warm" and "cold" states (separated based on the even and odd indeces,
since there is no exact temperature which would separate these values) to calculate 
thermal swings. 

Additionally, it correlates these thermal metrics with the physical glue 
thickness of the modules (Powerboard and Hybrid) and chuck number (on which the sensor 
was measured) to identify performance trends.

Data Filtering & Quality Control:
    - Transient Trimming: Discards the first two and last three measurements 
      of a sequence to remove startup/shutdown thermal anomalies and outliers
      for chuck_summary and glue_thickness_summary and module_plot_differences.
    - 20-Degree difference: Ignores specific sensors where the temperature 
      swing (Cold - Warm) (module_plot_differences) is less than 20°C, filtering 
      failed cycles.
    - Missing Data Handling: Safely skips plotting specific sensors if their 
      underlying physical glue measurements are 'None', preserving the rest.

Inputs:

    SOURCE_JSON = "filtered_summary.json"

    1. filtered_summary.json : Contains parsed AMAC NTC temperature data 
                               (NTCpb, NTCx, NTCy) over ~10 thermal cycles.

Outputs:
    All generated visualizations are saved within a master 'Thermal_analysis' 
    directory, categorized into subfolders:
    
    - /module_plots_global       : Individual cycle plots for every module.
    - /chuck_summary             : Aggregated thermal performance by test Chuck.
    - /glue_thickness_summary    : Scatter plots correlating Temperature vs. Glue thickness.
    - /module_plots_differences  : Bar and Violin plots showing the Delta-T 
                                    (Cold - Warm) spread and oscillation density.
"""

import json
import sys
import matplotlib
matplotlib.use('Agg') 
import matplotlib.pyplot as plt
from pathlib import Path
import statistics
import numpy as np
from typing import Dict, Any
from matplotlib.ticker import FormatStrFormatter

def get_chuck_id(stream_val: Any, chuck_map: Dict[str, Any]) -> str:
    """
    Maps raw stream values to specific Chuck IDs.
    """
    try:
        s = int(stream_val)
        for chuck_name, chuck_data in chuck_map.items():
            if s in chuck_data.get("daq_stream", []):
                return chuck_name
    except:
        pass
    return "Unknown"

def load_glue_data(summary_path: str) -> Dict[str, Dict[str, float]]:
    """
    Loads glue thickness data from JSON and maps it to module components.
    """
    glue_t: Dict[str, Dict[str, float]] = {}
    path = Path(summary_path)

    if path.exists():
        with open(path, 'r') as f:
            data = json.load(f)
            for entry in data:
                sn = entry.get("SN_module")

                if sn and sn not in glue_t:
                    glue_t[sn] = {
                        'abc': entry.get('Hybrid_Glue'),
                        'pb': entry.get('PB_Glue'),
                        'pb_5': entry.get('PB_Glue_5'),
                        'abc_4l': entry.get('Hybrid_Glue_L'),
                        'abc_4r': entry.get('Hybrid_Glue_R')
                    }
    return glue_t

def plot_with_index_splitting(json_file: str, glue_t: Dict[str, Any], base_out_dir: str, chuck_map: Dict[str, Any], trim_start: int, trim_end: int) -> None:
    """
    Plots individual sensor temperatures split into warm and cold values for each cycle.
    """
    source_path = Path(json_file)
    output_dir = Path(base_out_dir) / "module_plots_global"
    output_dir.mkdir(parents=True, exist_ok=True)

    if not source_path.exists():
        print(f"Error: {json_file} not found.")
        return

    with open(source_path, 'r') as f:
        data_list = json.load(f)

    processed_count = 0

    for entry in data_list:
        sn = entry.get("SN_module", "Unknown")
        run = entry.get("runNumber", "N/A")
        raw_stream = entry.get("chuck", "N/A")
        chuck_label = get_chuck_id(raw_stream, chuck_map)

        g_info = glue_t.get(sn, {})
        pb_g = g_info.get('pb')
        abc_g = g_info.get('abc')
        pb_g_5 = g_info.get('pb_5')
        abc_g_4l = g_info.get('abc_4l')
        abc_g_4r = g_info.get('abc_4r')

        glue_parts_pb = []
        glue_parts_hybrid = []

        if isinstance(pb_g, (int, float)):
            glue_parts_pb.append(f"PB={pb_g:.1f} μm")

        #if isinstance(pb_g_5, (int, float)):
            #glue_parts_pb.append(f"PB_5={pb_g_5:.1f} μm")

        if isinstance(abc_g, (int, float)):
            glue_parts_hybrid.append(f"Hybrid={abc_g:.1f} μm")

        if isinstance(abc_g_4l, (int, float)):
            glue_parts_hybrid.append(f"Hybrid_L={abc_g_4l:.1f} μm")

        if isinstance(abc_g_4r, (int, float)):
            glue_parts_hybrid.append(f"Hybrid_R={abc_g_4r:.1f} μm")

        glue_title = " | ".join([
            ", ".join(glue_parts_pb),
            ", ".join(glue_parts_hybrid)
        ])

        glue_title = f"{glue_title}" if glue_title else "N/A"
        
        sensors = [
            ("AMAC_NTCpb", "Powerboard (NTCpb)"),
            ("AMAC_NTCx", "Hybrid L (NTCx)"),
            ("AMAC_NTCy", "Hybrid R (NTCy)")
        ]

        all_cold_vals, all_warm_vals = [], []

        for key, label in sensors:
            values = entry.get(key, [])
            if len(values) >= 2:
                all_warm_vals.extend([val for idx, val in enumerate(values) if idx % 2 == 0 or idx == 23])
                all_cold_vals.extend([val for idx, val in enumerate(values) if idx % 2 != 0 and idx != 23])

        cold_ylim = (min(all_cold_vals) - 1, max(all_cold_vals) + 1) if all_cold_vals else (0, 1)
        warm_ylim = (min(all_warm_vals) - 1, max(all_warm_vals) + 1) if all_warm_vals else (0, 1)

        fig, axes = plt.subplots(3, 2, figsize=(18, 18), sharex=True)
        fig.subplots_adjust(wspace=0.25)
        fig.suptitle(f"Module: {sn}\nRun: {run} | Chuck: {chuck_label} \nGlue: {glue_title}", fontsize=22, fontweight='bold')

        for i, (key, label) in enumerate(sensors):
            values = entry.get(key, [])
            if len(values) < 2:
                continue

            warm_vals = [val for j, val in enumerate(values) if j % 2 == 0 or j == 23]
            cold_vals = [val for j, val in enumerate(values) if j % 2 != 0 and j != 23]

            for col, (data, color, state) in enumerate([(cold_vals, 'tab:blue', 'Cold'), (warm_vals, 'tab:red', 'Warm')]):
                ax = axes[i, col]
                
            
                if trim_end == 0:
                    trimmed_data = data[trim_start:]
                elif trim_end < 0:
                    trimmed_data = data[trim_start:trim_end]  
                else:
                    trimmed_data = data[trim_start:-trim_end] 

                
                if len(trimmed_data) == 0:
                    trimmed_data = data
                    
                mean_val = statistics.mean(trimmed_data)
                indices = range(len(data))
                
                ax.vlines(indices, ymin=mean_val, ymax=data, color=color, alpha=0.4)
                ax.plot(indices, data, marker='o', color=color, linestyle='None')
                ax.tick_params(axis='both', labelsize=14)
                ax.axhline(mean_val, color='black', linestyle='--', linewidth=1.5, label="Mean Temp of Trimmed Data" if i == 0 and col == 0 else None)
                ax.annotate(
                    f'{mean_val:.2f}',
                    xy=(1, mean_val),
                    xycoords=('axes fraction', 'data'),
                    xytext=(8, 0),
                    textcoords='offset points',
                    ha='left',
                    va='center',
                    fontsize=12,
                    fontweight='bold',
                    color='black'
                )
                ax.set_title(f"{label} - {state} Cycles", fontsize=18)
                ax.grid(True, axis='y', alpha=0.3)
                ax.yaxis.set_major_formatter(FormatStrFormatter('%.1f'))

                if col == 0:
                    ax.set_ylabel("Temp (°C)", fontsize=16)
                if i == 2:
                    ax.set_xlabel("Cycle",fontsize=16)

                if state == 'Cold':
                    ax.set_ylim(cold_ylim)
                else:
                    ax.set_ylim(warm_ylim)

        fig.legend(loc='upper right', fontsize=16)
        save_path = output_dir / f"{chuck_label}_{sn}_Run{run}.png"

        plt.savefig(
            save_path,
            dpi=120,
            bbox_inches='tight'
        )
        plt.close(fig)

        processed_count += 1

    print(f"Individual module plots: {processed_count} plots created.")

def plot_summary_by_chuck(json_file: str, base_out_dir: str, chuck_map: Dict[str, Any], trim_start: int, trim_end: int) -> None:
    """
    Aggregates temperature metrics by Chuck ID and plots summaries.
    """
    source_path = Path(json_file)
    output_dir = Path(base_out_dir) / "chuck_summary"
    output_dir.mkdir(parents=True, exist_ok=True)
    
    if not source_path.exists():
        print(f"Error: {json_file} not found.")
        return

    with open(source_path, 'r') as f:
        data_list = json.load(f)

    chuck_data = {ch_id: {"Labels":[],
                             "pb_w": [], "pb_c": [], "pb_w_err": [], "pb_c_err": [],
                             "nx_w": [], "nx_c": [], "nx_w_err": [], "nx_c_err": [],
                             "ny_w": [], "ny_c": [], "ny_w_err": [], "ny_c_err": []} for ch_id in chuck_map.keys()}
    
    cold_bounds = []
    warm_bounds = []

    for entry in data_list:
        sn = entry.get("SN_module", "Unknown")
        run = entry.get("runNumber", "N/A")
        chuck_label = get_chuck_id(entry.get("chuck"), chuck_map)
        
        if chuck_label == "Unknown":
            continue

        sensors = [("AMAC_NTCpb", "pb"), ("AMAC_NTCx", "nx"), ("AMAC_NTCy", "ny")]
        chuck_data[chuck_label]["Labels"].append(f"{sn} (R:{run})")

        for (key, short_name) in sensors:
            values = entry.get(key, [])
            if len(values) < 3: 
                continue

            filtered = values[trim_start:trim_end if trim_end != 0 else None]

            cold_vals = [val for i, val in enumerate(filtered) if i % 2 != 0]
            warm_vals = [val for i, val in enumerate(filtered) if i % 2 == 0]
            
            if not cold_vals or not warm_vals:
                continue

            c_mean = statistics.mean(cold_vals)
            w_mean = statistics.mean(warm_vals)
            c_err = statistics.stdev(cold_vals) if len(cold_vals) > 1 else 0
            w_err = statistics.stdev(warm_vals) if len(warm_vals) > 1 else 0

            chuck_data[chuck_label][f"{short_name}_c"].append(c_mean)
            chuck_data[chuck_label][f"{short_name}_w"].append(w_mean)
            chuck_data[chuck_label][f"{short_name}_c_err"].append(c_err)
            chuck_data[chuck_label][f"{short_name}_w_err"].append(w_err)

            cold_bounds.extend([c_mean - c_err, c_mean + c_err])
            warm_bounds.extend([w_mean - w_err, w_mean + w_err])

    summary_keys = [
        ("pb", "Powerboard (NTCpb)"), 
        ("nx", "Hybrid L (NTCx)"), 
        ("ny", "Hybrid R (NTCy)")
    ]
    
    c_min, c_max = (min(cold_bounds), max(cold_bounds)) if cold_bounds else (0, 1)
    cold_ylim = (c_min - (c_max - c_min or 1) * 0.1, c_max + (c_max - c_min or 1) * 0.1)

    w_min, w_max = (min(warm_bounds), max(warm_bounds)) if warm_bounds else (0, 1)
    warm_ylim = (w_min - (w_max - w_min or 1) * 0.1, w_max + (w_max - w_min or 1) * 0.1)

    processed_chucks = 0

    for ch_id, data in chuck_data.items():
        if not data["Labels"]: 
            continue

        fig_s, axes_s = plt.subplots(3, 2, figsize=(18, 18), sharex=True)
        fig_s.subplots_adjust(
                right=0.70,   
                top=0.92,
                wspace=0.20,
                hspace=0.30
            )
        fig_s.suptitle(f"Chuck Summary: {ch_id}", fontsize=22, fontweight='bold')

        x_indices = range(len(data["Labels"]))

        for i, (prefix, label) in enumerate(summary_keys):
            for col, (state, color, state_name) in enumerate([("c", "tab:blue", "Cold"), ("w", "tab:red", "Warm")]):
                ax = axes_s[i, col]

                ax.set_ylim(cold_ylim if state == "c" else warm_ylim)

                y_vals = data[f"{prefix}_{state}"]
                y_errs = data[f"{prefix}_{state}_err"]
                ax.errorbar(
                    x_indices,
                    y_vals,
                    yerr=y_errs,
                    fmt='o',
                    color=color,
                    ecolor='gray',
                    capsize=3,
                    label='Module Avg' if i == 0 and col == 0 else None,
                    zorder=3
                )
                
                if y_vals:
                    m_of_m = statistics.mean(y_vals)
                    ax.axhline(m_of_m, color='black', linestyle='--', alpha=0.6, label="Mean Temp" if i == 0 and col == 0 else None)
                    
                    ax.annotate(
                        f'{m_of_m:.2f}',
                        xy=(1, m_of_m),
                        xycoords=('axes fraction', 'data'),
                        xytext=(8, 0),
                        textcoords='offset points',
                        ha='left',
                        va='center',
                        fontsize=12,
                        fontweight='bold',
                        color='black'
                    )
                ax.tick_params(axis='both', labelsize=14)    
                ax.set_title(f"{label} - {state_name}", fontsize=16)
                ax.grid(True, alpha=0.3)
                if col == 0:
                    ax.set_ylabel("Temp (°C)", fontsize=16)
                
                if i == 2:
                    ax.set_xticks(x_indices)
                    # Removed names on x axis and set shared label
                    ax.set_xticklabels([])
                    ax.set_xlabel("Module SN (run)", fontsize=16)

        handles, labels = axes_s[0, 0].get_legend_handles_labels()

        fig_s.legend(
            handles,
            labels,
            loc='upper right',
            bbox_to_anchor=(0.98, 0.98),
            fontsize=16
        )
        plt.tight_layout()
        plt.savefig(output_dir / f"Summary_{ch_id}.png", dpi=150)
        plt.close(fig_s)

        processed_chucks += 1

    fig_all, axes_all = plt.subplots(3, 2, figsize=(20, 18), sharex=True)
    fig_all.subplots_adjust(
        right=0.70,   
        top=0.85,
        wspace=0.20,
        hspace=0.30
    )
    fig_all.suptitle("Global Comparison Across All Chucks", fontsize=22, fontweight='bold')
    
    markers = {ch_id: ch_data.get("marker", "x") for ch_id, ch_data in chuck_map.items()}

    for i, (prefix, label) in enumerate(summary_keys):
        for col, (state, state_name) in enumerate([("c", "Cold"), ("w", "Warm")]):
            ax = axes_all[i, col]

            ax.set_ylim(cold_ylim if state == "c" else warm_ylim)

            all_means_for_this_plot = []

            for ch_id, d in chuck_data.items():
                if d["Labels"]:
                    y_vals = d[f"{prefix}_{state}"]
                    y_errs = d[f"{prefix}_{state}_err"]
                    ax.errorbar(
                        d["Labels"], 
                        y_vals,
                        yerr=y_errs,
                        marker=markers.get(ch_id, 'x'), 
                        linestyle='', 
                        label=ch_id, 
                        markersize=8, 
                        capsize=3,     
                        alpha=0.7,
                        zorder=3
                    )
                    all_means_for_this_plot.extend([v for v in y_vals if v != 0])
        
            if all_means_for_this_plot:
                global_mean = statistics.mean(all_means_for_this_plot)
                global_sd = statistics.stdev(all_means_for_this_plot) if len(all_means_for_this_plot) > 1 else 0
                ax.axhline(global_mean, color='black', linestyle='--', linewidth=2, alpha=0.8, label="Mean Temp" if i == 0 and col == 0 else None)
                ax.axhspan( 
                    global_mean - global_sd, 
                    global_mean + global_sd, 
                    color='gray', alpha=0.15, label='Total Pop. ±1 SD', zorder=1)

                ax.annotate(
                    f'{global_mean:.2f}',
                    xy=(1, global_mean),
                    xycoords=('axes fraction', 'data'),
                    xytext=(8, 0),
                    textcoords='offset points',
                    ha='left',
                    va='center',
                    fontsize=12,
                    fontweight='bold',
                    color='black'
                )
            ax.tick_params(axis='both', labelsize=14)    
            ax.set_title(f"{label} - {state_name}", fontsize=16)
            ax.grid(True, which='both', linestyle='--', alpha=0.3)

            if col == 0:
                ax.set_ylabel("Temp (°C)", fontsize=16)
                
            if i == 2:
                ax.set_xticklabels([])
                ax.set_xlabel("Module SN (Run)", fontsize=16)
                ax.tick_params(axis='x', rotation=0)
    handles, labels = [], []
    for ax in fig_all.axes:
        for h, l in zip(*ax.get_legend_handles_labels()):
            if l not in labels:
                handles.append(h)
                labels.append(l)

    
    leg = fig_all.legend(
        handles,
        labels,
        loc='upper right',
        bbox_to_anchor=(0.99, 0.98),
        fontsize=16
    )

    leg.get_title().set_fontsize(16)
    leg.get_title().set_fontweight('bold')

    plt.tight_layout(rect=[0, 0, 0.88, 0.95])

    plt.savefig(
        output_dir / "Global_Chuck_Comparison.png",
        dpi=150,
        bbox_inches='tight'
    )
    plt.close(fig_all)

    print(f"Finished, {processed_chucks} chuck summaries created.")

def plot_by_glue_thickness(json_file: str, glue_t: Dict[str, Any], base_out_dir: str, chuck_map: Dict[str, Any], trim_start: int, trim_end: int) -> None:
    """
    Correlates temperature metrics with glue thickness.
    """
    source_path = Path(json_file)
    output_dir = Path(base_out_dir) / "glue_thickness_summary"
    output_dir.mkdir(parents=True, exist_ok=True)

    if not source_path.exists():
        print(f"Error: {json_file} not found.")
        return

    with open(source_path, 'r') as f:
        data_list = json.load(f)

    corr_data_general = {
        "pb": {"g": [], "c": [], "w": [], "c_err": [], "w_err": [], "snsr": [], "chuck": []},
        "nx": {"g": [], "c": [], "w": [], "c_err": [], "w_err": [], "snsr": [], "chuck": []},
        "ny": {"g": [], "c": [], "w": [], "c_err": [], "w_err": [], "snsr": [], "chuck": []}
    }
    
    corr_data_split = {
        "pb": {"g": [], "c": [], "w": [], "c_err": [], "w_err": [], "snsr": [], "chuck": []},
        "nx": {"g": [], "c": [], "w": [], "c_err": [], "w_err": [], "snsr": [], "chuck": []},
        "ny": {"g": [], "c": [], "w": [], "c_err": [], "w_err": [], "snsr": [], "chuck": []}
    }

    pb_comp_data_general = {
        "pb_avg": {"g": [], "c": [], "w": [], "c_err": [], "w_err": [], "snsr": []},
        "pb_5": {"g": [], "c": [], "w": [], "c_err": [], "w_err": [], "snsr": []}
    }

    pb_comp_data_split = {
        "pb_avg": {"g": [], "c": [], "w": [], "c_err": [], "w_err": [], "snsr": []},
        "pb_5": {"g": [], "c": [], "w": [], "c_err": [], "w_err": [], "snsr": []}
    }

    cold_bounds, warm_bounds = [], []

    for entry in data_list:
        sn = entry.get("SN_module", "Unknown")
        run = entry.get("runNumber", "N/A")
        chuck_label = get_chuck_id(entry.get("chuck", "N/A"), chuck_map)
        
        g_info = glue_t.get(sn, {})

        has_split = g_info.get('abc_4l') is not None or g_info.get('abc_4r') is not None

        pb_g = g_info.get('pb')

        if has_split:
            nx_g = g_info.get('abc_4l')
            ny_g = g_info.get('abc_4r')
            target_data = corr_data_split
            target_pb_comp = pb_comp_data_split
        else:
            nx_g = g_info.get('abc')
            ny_g = g_info.get('abc')
            target_data = corr_data_general
            target_pb_comp = pb_comp_data_general

        sensors = [("AMAC_NTCpb", "pb", pb_g), ("AMAC_NTCx", "nx", nx_g), ("AMAC_NTCy", "ny", ny_g)]

        for (key, short, g_val) in sensors:
            vals = entry.get(key, [])
            if len(vals) < 3 or not isinstance(g_val, (int, float)): 
                continue
            
            trimmed = vals[trim_start:trim_end if trim_end < 0 else (-trim_end if trim_end > 0 else None)]
            cold_vals = [val for i, val in enumerate(trimmed) if i % 2 != 0]
            warm_vals = [val for i, val in enumerate(trimmed) if i % 2 == 0]
            
            if not cold_vals or not warm_vals: continue

            c_mean, w_mean = statistics.mean(cold_vals), statistics.mean(warm_vals)
            c_err = statistics.stdev(cold_vals) if len(cold_vals) > 1 else 0
            w_err = statistics.stdev(warm_vals) if len(warm_vals) > 1 else 0

            target_data[short]["snsr"].append(f"{sn} (R:{run})")
            target_data[short]["g"].append(g_val)
            target_data[short]["chuck"].append(chuck_label)
            target_data[short]["c"].append(c_mean)
            target_data[short]["w"].append(w_mean)
            target_data[short]["c_err"].append(c_err)
            target_data[short]["w_err"].append(w_err)
            
            cold_bounds.extend([c_mean - c_err, c_mean + c_err])
            warm_bounds.extend([w_mean - w_err, w_mean + w_err])

        for short_key, raw_g_val in [("pb_avg", g_info.get('pb')), ("pb_5", g_info.get('pb_5'))]:
            vals = entry.get("AMAC_NTCpb", [])
            if len(vals) < 3 or not isinstance(raw_g_val, (int, float)): continue
            
            trimmed = vals[trim_start:trim_end if trim_end < 0 else (-trim_end if trim_end > 0 else None)]
            c_v = [val for i, val in enumerate(trimmed) if i % 2 != 0]
            w_v = [val for i, val in enumerate(trimmed) if i % 2 == 0]
            if not c_v or not w_v: continue

            target_pb_comp[short_key]["snsr"].append(f"{sn} (R:{run})")
            target_pb_comp[short_key]["g"].append(raw_g_val)
            target_pb_comp[short_key]["c"].append(statistics.mean(c_v))
            target_pb_comp[short_key]["w"].append(statistics.mean(w_v))
            target_pb_comp[short_key]["c_err"].append(statistics.stdev(c_v) if len(c_v) > 1 else 0)
            target_pb_comp[short_key]["w_err"].append(statistics.stdev(w_v) if len(w_v) > 1 else 0)

    c_min, c_max = (min(cold_bounds), max(cold_bounds)) if cold_bounds else (0, 1)
    cold_ylim = (c_min - (c_max - c_min or 1) * 0.1, c_max + (c_max - c_min or 1) * 0.1)

    w_min, w_max = (min(warm_bounds), max(warm_bounds)) if warm_bounds else (0, 1)
    warm_ylim = (w_min - (w_max - w_min or 1) * 0.1, w_max + (w_max - w_min or 1) * 0.1)
    
    chuck_markers = {ch_id: ch_data.get("marker", "x") for ch_id, ch_data in chuck_map.items()}

    plot_configs = [
        ("1", corr_data_general, "PB & Hybrid"),
        ("2", corr_data_split, "PB & Hybrid L/R")
    ]

    s_labels = [("pb", "Powerboard (NTCpb)"), ("nx", "Hybrid L (NTCx)"), ("ny", "Hybrid r (NTCy)")]

    for file_suffix, dataset, title_suffix in plot_configs:
        if not any(dataset[k]["g"] for k in ["pb", "nx", "ny"]):
            continue

        fig_g, axes_g = plt.subplots(3, 2, figsize=(22, 18), sharex=False)
        fig_g.suptitle(f"Temperature vs. Glue Thickness", fontsize=22, fontweight='bold')

        for i, (short, label) in enumerate(s_labels):
            d = dataset[short]
            if not d["g"]: continue

            unique_sns = list(dict.fromkeys(d["snsr"]))
            colors = plt.cm.tab20(np.linspace(0, 1, len(unique_sns)))
            sn_to_color = dict(zip(unique_sns, colors))

            for col, state in enumerate(["c", "w"]):
                ax = axes_g[i, col]
                ax.set_ylim(cold_ylim if state == "c" else warm_ylim)
                y_vals, y_errs, gs = np.array(d[state]), np.array(d[f"{state}_err"]), np.array(d["g"])

                for s_name in unique_sns:
                    idx = [j for j, val in enumerate(d["snsr"]) if val == s_name]
                    ax.errorbar(gs[idx], y_vals[idx], yerr=y_errs[idx], fmt='o', color=sn_to_color[s_name], label=s_name, markersize=10, capsize=4, alpha=0.8)

                global_avg = np.mean(y_vals)
                ax.axhline(global_avg, color='black', linestyle='--', alpha=0.6, label="Global Mean" if i == 0 and col == 0 else None)
                ax.annotate(f'{global_avg:.2f}', xy=(1, global_avg), xycoords=('axes fraction', 'data'),
                            xytext=(8, 0), textcoords='offset points', ha='left', va='center', fontsize=12, fontweight='bold', color='black')
                
                ax.tick_params(axis='both', labelsize=14)
                ax.set_title(f"{label} - {'Cold' if state=='c' else 'Warm'} State", fontsize=16)
                ax.grid(True, linestyle=':', alpha=0.6)

                if col == 0: ax.set_ylabel("Avg Temp (°C)", fontsize=16)
                if i == 2: ax.set_xlabel("Glue Thickness (μm)", fontsize=16)

        handles, labels = [], []
        for ax in fig_g.axes:
            for h, l in zip(*ax.get_legend_handles_labels()):
                if l not in labels:
                    handles.append(h)
                    labels.append(l)

        fig_g.subplots_adjust(right=0.80)
        leg_g = fig_g.legend(handles, labels, loc='center left', bbox_to_anchor=(0.86, 0.5), fontsize=14, title="Module SN")
        leg_g.get_title().set_fontweight('bold')
        
        plt.savefig(output_dir / f"Glue_Thermal_Correlation_Overall_{file_suffix}.png", dpi=150, bbox_inches='tight')
        plt.close(fig_g)

        fig_c, axes_c = plt.subplots(3, 2, figsize=(22, 18), sharex=False)
        fig_c.suptitle(f"Thermal Performance vs. Glue Thickness (By Chuck)", fontsize=22, fontweight='bold')

        for i, (short, label) in enumerate(s_labels):
            d = dataset[short]
            if not d["g"]: continue

            gs, chucks = np.array(d["g"]), np.array(d["chuck"])

            for col, state in enumerate(["c", "w"]):
                ax = axes_c[i, col]
                ax.set_ylim(cold_ylim if state == "c" else warm_ylim)
                y_vals, y_errs = np.array(d[state]), np.array(d[f"{state}_err"])

                for ch in sorted(list(set(chucks))):
                    idx = np.where(chucks == ch)[0]
                    ax.errorbar(gs[idx], y_vals[idx], yerr=y_errs[idx], fmt=chuck_markers.get(ch, 'x'), label=f"{ch} Modules", markersize=12, capsize=4, alpha=0.7, linestyle='None')
                
                global_avg = np.mean(y_vals)
                ax.axhline(global_avg, color='black', linestyle='--', alpha=0.6, label="Global Mean" if i == 0 and col == 0 else None)
                ax.annotate(f'{global_avg:.2f}', xy=(1, global_avg), xycoords=('axes fraction', 'data'),
                            xytext=(8, 0), textcoords='offset points', ha='left', va='center', fontsize=12, fontweight='bold', color='black')
                
                ax.tick_params(axis='both', labelsize=14)
                ax.set_title(f"{label} - {'Cold' if state=='c' else 'Warm'} State", fontsize=16)
                ax.grid(True, linestyle=':', alpha=0.6)

                if col == 0: ax.set_ylabel("Avg Temp (°C)", fontsize=16)
                if i == 2: ax.set_xlabel("Glue Thickness (μm)", fontsize=16)

        handles_c, labels_c = [], []
        for ax in fig_c.axes:
            for h, l in zip(*ax.get_legend_handles_labels()):
                if l not in labels_c:
                    handles_c.append(h)
                    labels_c.append(l)

        fig_c.subplots_adjust(right=0.80)
        leg_c = fig_c.legend(handles_c, labels_c, loc='center left', bbox_to_anchor=(0.86, 0.5), fontsize=16, title="Chuck ID")
        leg_c.get_title().set_fontweight('bold')

        plt.savefig(output_dir / f"Glue_Thermal_By_Chuck_{file_suffix}.png", dpi=150, bbox_inches='tight')
        plt.close(fig_c)

    comp_sensors = [("pb_avg", "Avg PB Glue"), ("pb_5", "PB_5 Glue")]
    
    pb_plot_configs = [
        ("1", pb_comp_data_general),
        ("2", pb_comp_data_split)
    ]

    for file_suffix, pb_dataset in pb_plot_configs:
 
        if not any(pb_dataset[k]["g"] for k in ["pb_avg", "pb_5"]):
            continue
            
        fig_comp, axes_comp = plt.subplots(2, 2, figsize=(22, 12), sharex=False)
        fig_comp.suptitle("Powerboard Glue Comparison: Avg vs PB5", fontsize=22, fontweight='bold')
        has_comp_data = False

        for i, (short, label) in enumerate(comp_sensors):
            d = pb_dataset[short]
            
            if not d["g"]: 
                for col, state in enumerate(["c", "w"]):
                    ax = axes_comp[i, col]
                    ax.text(0.5, 0.5, "No Data Available", ha='center', va='center', fontsize=16, color='gray')
                    ax.set_title(f"{label} - {'Cold' if state=='c' else 'Warm'} State", fontsize=16)
                    ax.set_xticks([])
                    ax.set_yticks([])
                continue
            
            has_comp_data = True
            unique_sns = list(dict.fromkeys(d["snsr"]))
            colors = plt.cm.tab20(np.linspace(0, 1, max(len(unique_sns), 1)))
            sn_to_color = dict(zip(unique_sns, colors))

            for col, state in enumerate(["c", "w"]):
                ax = axes_comp[i, col]
                ax.set_ylim(cold_ylim if state == "c" else warm_ylim)
                y_vals, y_errs, gs = np.array(d[state]), np.array(d[f"{state}_err"]), np.array(d["g"])

                for s_name in unique_sns:
                    idx = [j for j, val in enumerate(d["snsr"]) if val == s_name]
                    ax.errorbar(gs[idx], y_vals[idx], yerr=y_errs[idx], fmt='o', color=sn_to_color[s_name], label=s_name, markersize=10, capsize=4, alpha=0.8)

                global_avg = np.mean(y_vals)
                ax.axhline(global_avg, color='black', linestyle='--', alpha=0.6, label="Global Mean" if i == 0 and col == 0 else None)
                ax.annotate(f'{global_avg:.2f}', xy=(1, global_avg), xycoords=('axes fraction', 'data'),
                            xytext=(8, 0), textcoords='offset points', ha='left', va='center', fontsize=12, fontweight='bold', color='black')

                ax.tick_params(axis='both', labelsize=14)
                ax.set_title(f"{label} - {'Cold' if state=='c' else 'Warm'} State", fontsize=16)
                ax.grid(True, linestyle=':', alpha=0.6)
                
                if i == 1: ax.set_xlabel("Glue Thickness (μm)", fontsize=16)
                if col == 0: ax.set_ylabel("Avg Temp (°C)", fontsize=16)

        if has_comp_data:
            handles_comp, labels_comp = [], []
            for ax in axes_comp.flatten():
                for h, l in zip(*ax.get_legend_handles_labels()):
                    if l not in labels_comp and l != "No Data Available":
                        handles_comp.append(h)
                        labels_comp.append(l)

            fig_comp.subplots_adjust(right=0.80)
            leg_comp = fig_comp.legend(handles_comp, labels_comp, loc='center left', bbox_to_anchor=(0.86, 0.5), fontsize=14, title="Module SN")
            leg_comp.get_title().set_fontweight('bold')
            plt.savefig(output_dir / f"Glue_Thermal_PB_Comparison_Overall_{file_suffix}.png", dpi=150, bbox_inches='tight')
        plt.close(fig_comp)

def plot_warm_cold_differences(json_file: str, glue_t: Dict[str, Any], base_out_dir: str, chuck_map: Dict[str, Any], trim_start: int, trim_end: int, min_swing: int) -> None:
    """
    Calculates and plots the absolute difference between adjacent warm and cold cycles.
    """
    source_path = Path(json_file)
    output_dir = Path(base_out_dir) / "module_plots_differences"
    output_dir.mkdir(parents=True, exist_ok=True)

    if not source_path.exists():
        print(f"Error: {json_file} not found.")
        return

    with open(source_path, 'r') as f:
        data_list = json.load(f)

    sensors = [
            ("AMAC_NTCpb", "Powerboard (NTCpb)"),
            ("AMAC_NTCx", "Hybrid L (NTCx)"),
            ("AMAC_NTCy", "Hybrid R (NTCy)")
        ]

    all_global_diffs = []    
    parsed_modules_data = []    

    for entry in data_list:
        sn = entry.get("SN_module", "Unknown")
        run = entry.get("runNumber", "N/A")
        raw_stream = entry.get("chuck", "N/A")
        chuck_label = get_chuck_id(raw_stream, chuck_map)

        g_info = glue_t.get(sn, {})
        pb_g = g_info.get('pb')
        abc_g = g_info.get('abc')
        pb_g_5 = g_info.get('pb_5')
        abc_g_4l = g_info.get('abc_4l')
        abc_g_4r = g_info.get('abc_4r')

        glue_parts_pb = []
        glue_parts_hybrid = []

        if isinstance(pb_g, (int, float)):
            glue_parts_pb.append(f"PB={pb_g:.1f} μm")

        if isinstance(abc_g, (int, float)):
            glue_parts_hybrid.append(f"Hybrid={abc_g:.1f} μm")

        if isinstance(abc_g_4l, (int, float)):
            glue_parts_hybrid.append(f"Hybrid_L={abc_g_4l:.1f} μm")

        if isinstance(abc_g_4r, (int, float)):
            glue_parts_hybrid.append(f"Hybrid_R={abc_g_4r:.1f} μm")

        pb_str = ", ".join(glue_parts_pb)
        hybrid_str = ", ".join(glue_parts_hybrid)
        
        joined_title = " | ".join(filter(None, [pb_str, hybrid_str]))
        glue_title = joined_title if joined_title else ""
        
        module_diffs = {}
        has_data = False
        
        for key, label in sensors:
            values = entry.get(key, [])
            if len(values) > 2:
                trimmed = values[trim_start:trim_end if trim_end < 0 else (-trim_end if trim_end > 0 else None)]
            else:
                trimmed = []

            valid_diffs = []
            skipped_count = 0

            for idx in range(0, len(trimmed) - 1, 2):
                delta = trimmed[idx] - trimmed[idx + 1]
                abs_delta = np.abs(delta)

                if abs_delta >= min_swing:
                    valid_diffs.append(abs_delta)
                else:
                    skipped_count += 1
            
            if not valid_diffs:
                continue
            
            all_global_diffs.extend(valid_diffs)
            module_diffs[key] = {'diffs': valid_diffs, 'skipped': skipped_count}
            if valid_diffs: has_data = True
        
        if has_data:
            parsed_modules_data.append({
                "sn": sn, "run": run, "chuck_label": chuck_label, 
                "glue_title": glue_title, "module_diffs": module_diffs
            })

    if not all_global_diffs:
        print("No difference data found to plot.")
        return
    
    for mod in parsed_modules_data:
        # Collect all difference values across all sensors for this module
        mod_all_diffs = []
        for key, _ in sensors:
            d_list = mod['module_diffs'].get(key, {}).get('diffs', [])
            mod_all_diffs.extend(d_list)

        if not mod_all_diffs:
            continue

        # Base the scaling and padding on the lowest and highest value for this module
        mod_min = min(mod_all_diffs)
        mod_max = max(mod_all_diffs)
        mod_range = mod_max - mod_min
        padding = mod_range * 0.25 if mod_range > 0 else 2.0
        
        y_bottom = max(0, mod_min - padding)
        y_top = mod_max + padding

        fig, axes = plt.subplots(3, 1, figsize=(12, 16), sharex=True, sharey=True)
        fig.suptitle(f"Thermal Swing (Between Cold and Warm State in One Cycle)\nModule: {mod['sn']} | Run: {mod['run']} | Chuck: {mod['chuck_label']}\nGlue: {mod['glue_title']}", fontsize=20, fontweight='bold')

        if isinstance(axes, np.ndarray):
            axes = axes.flatten()
        elif not isinstance(axes, list):
            axes = [axes]

        for i, (key, label) in enumerate(sensors):
            ax = axes[i]
            sensor_dict = mod['module_diffs'].get(key, {})
            data = sensor_dict.get('diffs', [])
            skipped = sensor_dict.get('skipped', 0)
            
            if not data:
                ax.set_title(f"{label} - No Data", fontsize=16, pad=15)
                ax.axis('off')
                continue
                
            mean_val = sum(data) / len(data)
            indices = range(len(data))

            ax.bar(indices, data, color='purple', alpha=0.7, edgecolor='black', width=0.6)
            ax.axhline(mean_val, color='black', linestyle='--', linewidth=1.5, 
                       label='Mean Difference' if i == 0 else None)
            
            ax.annotate(
                f'{mean_val:.2f}',
                xy=(1, mean_val),
                xycoords=('axes fraction', 'data'),
                xytext=(8, 0),
                textcoords='offset points',
                ha='left',
                va='center',
                fontsize=12,
                fontweight='bold',
                color='black'
            )
            ax.tick_params(axis='both', labelsize=14)
            
            title_text = f"{label} - Cycle Temp Difference"
            title_color = 'black'
            if skipped > 0:
                title_text += f"  [{skipped} cycle(s) omitted, diff < {min_swing}°C]"
                title_color = 'darkred'   
                
            ax.set_title(title_text, color=title_color, fontsize=16, pad=15)
            ax.grid(True, axis='both', alpha=0.3)
            ax.set_ylim(y_bottom, y_top)

            ax.set_ylabel("$\\Delta$ Temp (°C)", fontsize=16)
            if i == 2:
                ax.set_xlabel("Cycle Pair", fontsize=16)
                ax.set_xticks(indices)
                ax.set_xticklabels([f"{idx+1}" for idx in indices])
                
        handles, labels = [], []
        for ax in axes:
            for h, l in zip(*ax.get_legend_handles_labels()):
                if l not in labels:
                    handles.append(h)
                    labels.append(l)

        fig.legend(handles, labels, loc='center left', bbox_to_anchor=(0.86, 0.5), fontsize=14)
        
        fig.tight_layout(rect=[0, 0, 0.85, 0.93], h_pad=3.0)
        
        plot_path = output_dir / f"{mod['sn']}_Diffs_Run{mod['run']}.png"
        fig.savefig(plot_path, dpi=150, bbox_inches='tight')
        plt.close(fig)

def plot_difference_spread_vs_glue(json_file: str, glue_t: Dict[str, Any], base_out_dir: str, trim_start: int, trim_end: int, min_seq: int, min_swing: int) -> None:
    """Correlates the magnitude and spread (standard deviation) of thermal swings with glue thickness.
    Split into '1' (general hybrid glue) and '2' (4L/4R split locations) figures, with fixed legend spacing and layout padding.
    """

    source_path = Path(json_file)
    output_dir = Path(base_out_dir) / "module_plots_differences"
    output_dir.mkdir(parents=True, exist_ok=True)

    if not source_path.exists():
        print(f"Error: {json_file} not found.")
        return

    with open(source_path, 'r') as f:
        data_list = json.load(f)

    # Separate dictionaries for General vs Split modules
    plot_data_general = {
        "pb": {"g": [], "mean_diff": [], "std_diff": [], "snsr": []},
        "nx": {"g": [], "mean_diff": [], "std_diff": [], "snsr": []},
        "ny": {"g": [], "mean_diff": [], "std_diff": [], "snsr": []}
    }
    
    plot_data_split = {
        "pb": {"g": [], "mean_diff": [], "std_diff": [], "snsr": []},
        "nx": {"g": [], "mean_diff": [], "std_diff": [], "snsr": []},
        "ny": {"g": [], "mean_diff": [], "std_diff": [], "snsr": []}
    }

    for entry in data_list:
        sn = entry.get("SN_module", "Unknown")
        run = entry.get("runNumber", "N/A")
        
        g_info = glue_t.get(sn, {})
        has_split = g_info.get('abc_4l') is not None or g_info.get('abc_4r') is not None
        
        pb_g = g_info.get('pb')
        if has_split:
            nx_g = g_info.get('abc_4l')
            ny_g = g_info.get('abc_4r')
            target_data = plot_data_split
        else:
            nx_g = g_info.get('abc')
            ny_g = g_info.get('abc')
            target_data = plot_data_general

        sensor_mapping = [
            ("AMAC_NTCpb", "pb", pb_g),
            ("AMAC_NTCx", "nx", nx_g),
            ("AMAC_NTCy", "ny", ny_g)
        ]

        for (key, short, g_val) in sensor_mapping:
            if not isinstance(g_val, (int, float)):
                continue

            values = entry.get(key, [])
            if len(values) >= min_seq:
                sliced_values = values[trim_start:trim_end if trim_end < 0 else (-trim_end if trim_end > 0 else None)]
            else:
                continue

            diffs = []
            for idx in range(0, len(sliced_values) - 1, 2):
                delta = sliced_values[idx] - sliced_values[idx + 1]
                abs_delta = abs(delta)
                if abs_delta >= min_swing:
                    diffs.append(abs_delta)

            if len(diffs) > 1:
                mean_d = statistics.mean(diffs)
                std_d = statistics.stdev(diffs)
                
                target_data[short]["g"].append(g_val)
                target_data[short]["mean_diff"].append(mean_d)
                target_data[short]["std_diff"].append(std_d)
                target_data[short]["snsr"].append(f"{sn} (R:{run})")

    configs = [
        ("1", plot_data_general, "PB & Hybrid"),
        ("2", plot_data_split, "PB & Hybrid L/r")
    ]

    for file_suffix, plot_data, title_suffix in configs:
        if not any(plot_data[k]["g"] for k in ["pb", "nx", "ny"]):
            continue

        fig, axes = plt.subplots(3, 2, figsize=(22, 18), sharex=False)
        fig.suptitle(f"Thermal Swing & Oscillation Spread vs. Glue Thickness", fontsize=22, fontweight='bold')

        sensors_config = [
            ("pb", "Powerboard (NTCpb)"),
            ("nx", "Hybrid L (NTCx)"),
            ("ny", "Hybrid r (NTCy)")
        ]

        for i, (short, label) in enumerate(sensors_config):
            d = plot_data[short]
            if not d["g"]: continue

            gs = np.array(d["g"])
            means = np.array(d["mean_diff"])
            stds = np.array(d["std_diff"])
            snsrs = d["snsr"]
            
            unique_sns = list(dict.fromkeys(snsrs))
            colors = plt.cm.tab20(np.linspace(0, 1, max(len(unique_sns), 1)))
            sn_to_color = dict(zip(unique_sns, colors))

            ax_left = axes[i, 0]
            ax_right = axes[i, 1]

            for s_name in unique_sns:
                idx = [j for j, val in enumerate(snsrs) if val == s_name]
                ax_left.errorbar(gs[idx], means[idx], yerr=stds[idx], fmt='o',
                                 color=sn_to_color[s_name], label=s_name,
                                 markersize=10, capsize=4, alpha=0.8)
                
                ax_right.plot(gs[idx], stds[idx], 'o', color=sn_to_color[s_name],
                              markersize=10, alpha=0.8)

            if len(means) > 0:
                global_mean_val = np.mean(means)
                ax_left.axhline(global_mean_val, color='black', linestyle='--', alpha=0.6,
                                label="Global Mean" if i == 0 else None)
                ax_left.annotate(
                    f'{global_mean_val:.2f}',
                    xy=(1, global_mean_val),
                    xycoords=('axes fraction', 'data'),
                    xytext=(8, 0),
                    textcoords='offset points',
                    ha='left',
                    va='center',
                    fontsize=12,
                    fontweight='bold',
                    color='black'
                )

            ax_left.set_title(f"{label} - Mean $\\Delta$T (with Spread Error)", fontsize=16, pad=12)
            ax_left.grid(True, linestyle=':', alpha=0.6)
            ax_left.set_ylabel("Mean $\\Delta$ Temp (°C)", fontsize=16)
            if i == 2:
                ax_left.set_xlabel("Glue Thickness (μm)", fontsize=16)
            ax_left.tick_params(axis='both', labelsize=14)
            
            ax_right.set_title(f"{label} - Oscillation Spread (Std Dev)", fontsize=16, pad=12)
            ax_right.grid(True, linestyle=':', alpha=0.6)
            ax_right.set_ylabel("Spread (Std Dev °C)", fontsize=16)
            if i == 2:
                ax_right.set_xlabel("Glue Thickness (μm)", fontsize=16)
            ax_right.tick_params(axis='both', labelsize=12)

        handles, labels = [], []
        for ax in axes.flatten():
            for h, l in zip(*ax.get_legend_handles_labels()):
                if l not in labels:
                    handles.append(h)
                    labels.append(l)

        # Shift layout left to accommodate legend without overlapping data, and add space for subtitles/titles
        fig.subplots_adjust(right=0.82)
        leg = fig.legend(handles, labels, loc='center left', bbox_to_anchor=(0.83, 0.5), fontsize=14, title="Module SN")
        leg.get_title().set_fontsize(16)
        leg.get_title().set_fontweight('bold')

        plt.tight_layout(rect=[0, 0, 0.82, 0.94], h_pad=3.5)
        
        plt.savefig(output_dir / f"Glue_vs_Difference_Spread_{file_suffix}.png", dpi=150, bbox_inches='tight')
        plt.close(fig)

def plot_summary_ordered_by_run(json_file: str, base_out_dir: str, chuck_map: Dict[str, Any], trim_start: int, trim_end: int) -> None:
    """
    Aggregates temperature metrics across all modules and plots global summaries
    ordered chronologically or numerically by their run number.
    """
    source_path = Path(json_file)
    output_dir = Path(base_out_dir) / "chuck_summary"
    output_dir.mkdir(parents=True, exist_ok=True)
    
    if not source_path.exists():
        print(f"Error: {json_file} not found.")
        return

    with open(source_path, 'r') as f:
        data_list = json.load(f)

    # Sort data entries globally by runNumber (safely casting to int, falling back to 0 if missing/invalid)
    def get_run_val(entry):
        try:
            return int(entry.get("runNumber", 0))
        except (ValueError, TypeError):
            return 0

    sorted_data_list = sorted(data_list, key=get_run_val)

    # Structures to hold globally aggregated data ordered by run
    global_run_data = {
        "Labels": [],
        "Chucks": [],
        "pb_w": [], "pb_c": [], "pb_w_err": [], "pb_c_err": [],
        "nx_w": [], "nx_c": [], "nx_w_err": [], "nx_c_err": [],
        "ny_w": [], "ny_c": [], "ny_w_err": [], "ny_c_err": []
    }
    
    cold_bounds = []
    warm_bounds = []

    for entry in sorted_data_list:
        sn = entry.get("SN_module", "Unknown")
        run = entry.get("runNumber", "N/A")
        chuck_label = get_chuck_id(entry.get("chuck"), chuck_map)
        
        sensors = [("AMAC_NTCpb", "pb"), ("AMAC_NTCx", "nx"), ("AMAC_NTCy", "ny")]
        global_run_data["Labels"].append(f"R:{run} ({sn})")
        global_run_data["Chucks"].append(chuck_label)

        for (key, short_name) in sensors:
            values = entry.get(key, [])
            if len(values) < 3: 
                # Append defaults if sensor data is missing to keep array alignment
                global_run_data[f"{short_name}_c"].append(0)
                global_run_data[f"{short_name}_w"].append(0)
                global_run_data[f"{short_name}_c_err"].append(0)
                global_run_data[f"{short_name}_w_err"].append(0)
                continue

            filtered = values[trim_start:trim_end if trim_end != 0 else None]

            cold_vals = [val for i, val in enumerate(filtered) if i % 2 != 0]
            warm_vals = [val for i, val in enumerate(filtered) if i % 2 == 0]
            
            if not cold_vals or not warm_vals:
                global_run_data[f"{short_name}_c"].append(0)
                global_run_data[f"{short_name}_w"].append(0)
                global_run_data[f"{short_name}_c_err"].append(0)
                global_run_data[f"{short_name}_w_err"].append(0)
                continue

            c_mean = statistics.mean(cold_vals)
            w_mean = statistics.mean(warm_vals)
            c_err = statistics.stdev(cold_vals) if len(cold_vals) > 1 else 0
            w_err = statistics.stdev(warm_vals) if len(warm_vals) > 1 else 0

            global_run_data[f"{short_name}_c"].append(c_mean)
            global_run_data[f"{short_name}_w"].append(w_mean)
            global_run_data[f"{short_name}_c_err"].append(c_err)
            global_run_data[f"{short_name}_w_err"].append(w_err)

            cold_bounds.extend([c_mean - c_err, c_mean + c_err])
            warm_bounds.extend([w_mean - w_err, w_mean + w_err])

    if not global_run_data["Labels"]:
        print("No valid data found for run-ordered summary plot.")
        return

    summary_keys = [
        ("pb", "Powerboard (NTCpb)"), 
        ("nx", "Hybrid L (NTCx)"), 
        ("ny", "Hybrid r (NTCy)")
    ]
    
    c_min, c_max = (min(cold_bounds), max(cold_bounds)) if cold_bounds else (0, 1)
    cold_ylim = (c_min - (c_max - c_min or 1) * 0.1, c_max + (c_max - c_min or 1) * 0.1)

    w_min, w_max = (min(warm_bounds), max(warm_bounds)) if warm_bounds else (0, 1)
    warm_ylim = (w_min - (w_max - w_min or 1) * 0.1, w_max + (w_max - w_min or 1) * 0.1)

    fig_run, axes_run = plt.subplots(3, 2, figsize=(22, 18), sharex=True)
    fig_run.subplots_adjust(
        right=0.75,    
        top=0.88,
        wspace=0.20,
        hspace=0.30
    )
    fig_run.suptitle("Global Comparison Ordered by Run Number", fontsize=22, fontweight='bold')
    
    markers = {ch_id: ch_data.get("marker", "x") for ch_id, ch_data in chuck_map.items()}
    x_indices = range(len(global_run_data["Labels"]))

    for i, (prefix, label) in enumerate(summary_keys):
        for col, (state, state_name) in enumerate([("c", "Cold"), ("w", "Warm")]):
            ax = axes_run[i, col]
            ax.set_ylim(cold_ylim if state == "c" else warm_ylim)

            y_vals = global_run_data[f"{prefix}_{state}"]
            y_errs = global_run_data[f"{prefix}_{state}_err"]
            chucks = global_run_data["Chucks"]

            # Plot point-by-point to accurately map marker shapes to individual Chuck IDs
            unique_chucks = sorted(list(set(chucks)))
            for ch in unique_chucks:
                idx = [j for j, c in enumerate(chucks) if c == ch]
                sub_x = [x_indices[j] for j in idx]
                sub_y = [y_vals[j] for j in idx]
                sub_err = [y_errs[j] for j in idx]
                
                ax.errorbar(
                    sub_x, sub_y, yerr=sub_err,
                    marker=markers.get(ch, 'x'), 
                    linestyle='', 
                    label=f"Chuck {ch}", 
                    markersize=9, 
                    capsize=3,     
                    alpha=0.8,
                    zorder=3
                )

            all_means_for_plot = [v for v in y_vals if v != 0]
            if all_means_for_plot:
                global_mean = statistics.mean(all_means_for_plot)
                global_sd = statistics.stdev(all_means_for_plot) if len(all_means_for_plot) > 1 else 0
                
                ax.axhline(global_mean, color='black', linestyle='--', linewidth=2, alpha=0.8, label="Mean Temp" if i == 0 and col == 0 else None)
                ax.axhspan( 
                    global_mean - global_sd, 
                    global_mean + global_sd, 
                    color='gray', alpha=0.15, label='Total Pop. ±1 SD', zorder=1
                )

                ax.annotate(
                    f'{global_mean:.2f}',
                    xy=(1, global_mean),
                    xycoords=('axes fraction', 'data'),
                    xytext=(8, 0),
                    textcoords='offset points',
                    ha='left',
                    va='center',
                    fontsize=12,
                    fontweight='bold',
                    color='black'
                )

            ax.tick_params(axis='both', labelsize=14)    
            ax.set_title(f"{label} - {state_name}", fontsize=16)
            ax.grid(True, which='both', linestyle='--', alpha=0.3)

            if col == 0:
                ax.set_ylabel("Temp (°C)", fontsize=16)
                
            if i == 2:
                ax.set_xticks(x_indices)
                ax.set_xticklabels("")
                ax.set_xlabel("Run Number & Module SN", fontsize=16)

    handles, labels = [], []
    for ax in fig_run.axes:
        for h, l in zip(*ax.get_legend_handles_labels()):
            if l not in labels:
                handles.append(h)
                labels.append(l)

    leg = fig_run.legend(
        handles, labels, 
        loc='center left', 
        bbox_to_anchor=(0.77, 0.5), 
        fontsize=14, 
        title="Legend"
    )
    leg.get_title().set_fontsize(16)
    leg.get_title().set_fontweight('bold')

    plt.savefig(
        output_dir / "Global_Run_Ordered_Comparison.png", 
        dpi=150, 
        bbox_inches='tight'
    )
    plt.close(fig_run)

    print("Run-ordered global summary plot created successfully.")

if __name__ == "__main__":
    CONFIG_FILE = "config_TC.json"
    
    # Load configuration
    try:
        with open(CONFIG_FILE, 'r') as f:
            config = json.load(f)
    except Exception as e:
        print(f"Error loading config file: {e}")
        sys.exit(1)

    # Extract configuration variables exactly matching the provided JSON
    SOURCE_JSON = config.get("SOURCE_JSON", "filtered_summary.json")
    BASE_OUT_DIR = config.get("BASE_OUT_DIR", "Thermal_analysis")
    
    filtering_params = config.get("FILTERING", {})
    TRIM_START = filtering_params.get("trim_start", 2)
    TRIM_END = filtering_params.get("trim_end", -4)
    MIN_SEQ = filtering_params.get("min_seq_length", 6)
    MIN_SWING = filtering_params.get("min_temp_swing", 20)
    
    CHUCK_MAPPING = config.get("CHUCKS", {})

    glue_map = load_glue_data(SOURCE_JSON)
    
    plot_with_index_splitting(SOURCE_JSON, glue_map, BASE_OUT_DIR, CHUCK_MAPPING, TRIM_START, TRIM_END)
    
    plot_summary_by_chuck(SOURCE_JSON, BASE_OUT_DIR, CHUCK_MAPPING, TRIM_START, TRIM_END)

    plot_by_glue_thickness(SOURCE_JSON, glue_map, BASE_OUT_DIR, CHUCK_MAPPING, TRIM_START, TRIM_END)

    plot_warm_cold_differences(SOURCE_JSON, glue_map, BASE_OUT_DIR, CHUCK_MAPPING, TRIM_START, TRIM_END, MIN_SWING)

    plot_difference_spread_vs_glue(SOURCE_JSON, glue_map, BASE_OUT_DIR, TRIM_START, TRIM_END, MIN_SEQ, MIN_SWING)

    plot_summary_ordered_by_run(SOURCE_JSON, BASE_OUT_DIR, CHUCK_MAPPING, TRIM_START, TRIM_END)
    
    print(f"All tasks complete. Outputs saved to '{BASE_OUT_DIR}'.")