""" 
This script searches a specified source directory for JSON files containing 
a specific keyword (e.g. AMAC). It copies matching files to an isolation folder, then 
processes those files to validate and extract NTC temperature data based on configured
parameters.

It outputs a consolidated JSON containing:
    - Sensor metadata (Module SN, Date, Run, Chuck)
    - Thermal data (NTCpb, NTCx, NTCy)
    - Physical data (PB_Glue, Hybrid_Glue)

    DATA FLOW MAPPING:
    1. Reads configuration from config.json
    2. Searches all folders inside SOURCE_DIR
    3. ISOLATION: Copies matched files into ISOLATION_DIR
    4. EXTRACTION: Reads the files from ISOLATION_DIR
    5. FINAL DESTINATION: Saves filtered data to OUTPUT_JSON
"""

import json
import shutil
import sys
from pathlib import Path
from typing import Dict, Any, List

def extract_json_by_keyword(source_dir: str, dest_dir: str, keyword: str) -> int:
    """
    Searches for JSON files containing a specific keyword and copies them to a destination.
    """
    source_path = Path(source_dir).resolve()
    dest_path = Path(dest_dir).resolve()

    dest_path.mkdir(parents=True, exist_ok=True)
    count = 0

    for file_path in source_path.rglob("*.json"):
        if not file_path.is_file():
            continue

        has_keyword = keyword.lower() in file_path.name.lower()

        if has_keyword:
            if dest_path in file_path.parents:
                continue
                
            shutil.copy2(file_path, dest_path / file_path.name)
            count += 1

    print(f"File copy to {dest_dir} complete. {count} files with keyword {keyword} handled.\n")
    return count

def load_glue_mapping(glue_path: str) -> Dict[str, Dict[str, Any]]:
    """
    Loads glue thickness data from JSON and creates a lookup dictionary by Module SN.
    """
    glue_map: Dict[str, Dict[str, Any]] = {}
    path = Path(glue_path)
    
    if path.exists():
        try:
            with open(path, 'r') as f:
                data = json.load(f)
                for item in data:
                    sn = item.get('component')
                    if sn:
                        glue_map[sn] = {
                            'pb_glue': item.get('avg_PB_GLUE_THICKNESS'),
                            'abc_glue': item.get('avg_HYBRID_GLUE_THICKNESS_ABC'),
                            'pb_glue_5': item.get('avg_PB_GLUE_THICKNESS_5'),
                            '4R_abc_glue': item.get('R_avg_HYBRID_GLUE_THICKNESS_ABC'),
                            '4L_abc_glue': item.get('L_avg_HYBRID_GLUE_THICKNESS_ABC')
                        }
            print(f"Successfully loaded glue map for {len(glue_map)} modules.")
        except Exception as e:
            print(f"Warning: Failed to parse glue JSON: {e}")
    else:
        print(f"Warning: Glue file '{glue_path}' not found. Glue values will be null.")
        
    return glue_map

def process_extracted_data(source_dir: str, glue_file: str, output_file: str, ntc_len: int, min_temp: int, max_temp: int) -> None:
    """
    Reads JSON files from a directory, validates arrays based on config parameters, and extracts them.
    """
    source_path = Path(source_dir)
    out_path = Path(output_file)

    if not source_path.exists():
        print(f"Error: Folder '{source_path}' not found.")
        return
    
    glue_map = load_glue_mapping(glue_file)

    extracted_results: List[Dict[str, Any]] = []
    skipped_count = 0
    
    for file_path in source_path.glob("*.json"):
        try:
            with open(file_path, 'r') as f:
                data = json.load(f)

            props = data.get("properties", {})
            dcs = props.get("DCS", {})
            det_info = props.get("det_info", {})

            ntc_pb = dcs.get("AMAC_NTCpb")
            ntc_x = dcs.get("AMAC_NTCx")
            ntc_y = dcs.get("AMAC_NTCy")

            # Validation using dynamic parameters
            valid_pb = isinstance(ntc_pb, list) and len(ntc_pb) == ntc_len and all(min_temp <= v <= max_temp for v in ntc_pb)
            valid_x = isinstance(ntc_x, list) and len(ntc_x) == ntc_len and all(min_temp <= v <= max_temp for v in ntc_x)
            valid_y = isinstance(ntc_y, list) and len(ntc_y) == ntc_len and all(min_temp <= v <= max_temp for v in ntc_y)


            if not (valid_pb and valid_x and valid_y):
                skipped_count += 1
                continue

            sn_module = data.get("component", "Unknown")
            module_glue = glue_map.get(sn_module, {}) 

            entry = {
                "source_file": file_path.name,
                "SN_module": sn_module,
                "date": data.get("date"),
                "runNumber": data.get("runNumber"),
                "chuck": det_info.get("daq_stream"),
                "PB_Glue": module_glue.get("pb_glue"),          
                "Hybrid_Glue": module_glue.get("abc_glue"),
                "PB_Glue_5": module_glue.get("pb_glue_5"),          
                "Hybrid_Glue_R": module_glue.get("4R_abc_glue"),
                "Hybrid_Glue_L": module_glue.get("4L_abc_glue"),     
                "AMAC_NTCpb": ntc_pb,
                "AMAC_NTCx": ntc_x,
                "AMAC_NTCy": ntc_y
            }
            
            extracted_results.append(entry)
            
        except Exception as e:
            print(f"Skipping {file_path.name} due to error: {e}")

    with open(out_path, 'w') as out_f:
        json.dump(extracted_results, out_f, indent=4)
    
    print(f"Processed {len(extracted_results)} files.")
    print(f"Filtered out {skipped_count} files that failed validation.")

if __name__ == "__main__":
    
    CONFIG_FILE = "config_filter.json"
    
    try:
        with open(CONFIG_FILE, 'r') as f:
            config = json.load(f)
    except FileNotFoundError:
        print(f"Configuration file '{CONFIG_FILE}' not found.")
        print("Please create 'config_filter.json' in the same directory as this script.")
        sys.exit(1)
    except json.JSONDecodeError as e:
        print(f"Invalid JSON format in '{CONFIG_FILE}': {e}")
        sys.exit(1)

    # Extract configuration variables
    SOURCE_DIR = config.get("SOURCE_DIR", "./merged_results")
    ISOLATION_DIR = config.get("ISOLATION_DIR", "./AMAC_files")
    KEYWORD = config.get("KEYWORD", "AMAC")
    GLUE_JSON = config.get("GLUE_JSON", "glue_thickness_summary.json")
    OUTPUT_JSON = config.get("OUTPUT_JSON", "filtered_summary.json")
    
    validation_params = config.get("VALIDATION", {})
    NTC_LEN = validation_params.get("ntc_array_length", 24)
    MIN_TEMP = validation_params.get("min_temp", -55)
    MAX_TEMP = validation_params.get("max_temp", 55)

    # Run execution pipeline
    files_copied = extract_json_by_keyword(
        source_dir=SOURCE_DIR, 
        dest_dir=ISOLATION_DIR, 
        keyword=KEYWORD
    )

    if files_copied > 0 or Path(ISOLATION_DIR).exists():
        process_extracted_data(
            source_dir=ISOLATION_DIR,
            glue_file=GLUE_JSON, 
            output_file=OUTPUT_JSON,
            ntc_len=NTC_LEN,
            min_temp=MIN_TEMP,
            max_temp=MAX_TEMP
        )
    else:
        print("No files were copied")