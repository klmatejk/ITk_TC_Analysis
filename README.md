
## 1. Data Extraction (`data_filter.py`)
This script searches a specified source directory for JSON measurement files, copies matching files into an isolation folder, and validates the NTC temperature arrays. 

**Configuration File:** `config_filter.json`
* **`SOURCE_DIR` / `ISOLATION_DIR`**: Defines where to look for data in SN20USEM20000083_20260423_1645_MODULE_IV_AMAC_TC.json format and where to copy matched files.
* **`KEYWORD`**: Keyword in the name of the file with test data.
* **`GLUE_JSON`**: JSON file with average glue thicknesses under Hybrids and Powerboards.
Expected `GLUE_JSON` Format (`glue_thickness_summary.json`):
The glue summary file should be structured as a JSON array of objects containing component identifiers and respective thickness metrics, e.g.:
```json
[
    {
        "component": "20USEM40000240",
        "L_avg_HYBRID_GLUE_THICKNESS_ABC": 126.9375,
        "R_avg_HYBRID_GLUE_THICKNESS_ABC": 402.75,
        "avg_HYBRID_GLUE_THICKNESS_ABC": null,
        "avg_PB_GLUE_THICKNESS": 153.3,
        "avg_PB_GLUE_THICKNESS_5": 128.0
    }
]
* **`VALIDATION`**: Sets the strict rules for NTC arrays. The script will only accept data if the array length exactly matches `ntc_array_length` and all temperature values fall between `min_temp` and `max_temp`.

**Output:** `filtered_summary.json` (A consolidated file containing sensor metadata, thermal data, and physical glue thickness data).

---

## 2. Thermal Analysis (`TC_analysis.py`)
This script processes the consolidated summary to evaluate temperature stability, calculate thermal swings (Cold vs. Warm), and correlate thermal performance with physical glue thickness and test chucks. 

**Configuration File:** `config_TC.json`
* **`FILTERING`**: 
  * `trim_start` / `trim_end`: Discards startup/shutdown thermal deviations.
  * `min_seq_length`: Skips modules that crashed or lack enough data points.
  * `min_temp_swing`: Filters out specific cycles where the delta-T is below the threshold (e.g., failed cycles < 20°C).
* **`CHUCKS`**: Maps test rigs to the data `daq_stream` and assigns custom `marker` shapes for the plots.

**Output:** A master `Thermal_analysis` directory containing visualizations categorized into:
* Individual module cycle plots
* Temperature differences per chuck summaries
* Glue thickness and temperature correlation
* Thermal swing difference distributions

---

## Usage
1. Ensure your input files (like `glue_thickness_summary.json` and raw data (SN20USEM20000083_20260423_1645_MODULE_IV_AMAC_TC.json) are in place.
2. Edit **`config_filter.json`** and **`config_TC.json`** to match your current test parameters.
3. Run the data_filter.py and then TC_analysis.py

