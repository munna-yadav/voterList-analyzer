import os
from typing import Dict, List, Optional, Tuple

import pandas as pd


# Default base directory for voter Excel files.
# Priority:
# 1. If VOTER_DATA_DIR env var is set, use that.
# 2. Else, if your local absolute path exists, use it (local-only).
# 3. Else, if a `data/` folder exists in the repo, use that (for hosted/sample data).
# 4. Else, fall back to the repo root (municipality folders directly in repo).
_DEFAULT_LOCAL_DIR = "/home/munna/Downloads/Matdata Namawali"
_REPO_ROOT = os.path.dirname(__file__)

_env_dir = os.getenv("VOTER_DATA_DIR")
if _env_dir:
    BASE_DIR = _env_dir
elif os.path.isdir(_DEFAULT_LOCAL_DIR):
    BASE_DIR = _DEFAULT_LOCAL_DIR
elif os.path.isdir(os.path.join(_REPO_ROOT, "data")):
    BASE_DIR = os.path.join(_REPO_ROOT, "data")
else:
    BASE_DIR = _REPO_ROOT


# Default mapping based on observed Nepali headers in the Excel files.
# You can extend this if other municipalities use slightly different labels.
DEFAULT_COLUMN_MAPPING: Dict[str, str] = {
    # logical_name: actual_column_header
    "serial_no": "सि.नं.",
    "voter_no": "मतदाता नं",
    "name": "मतदाताको नाम",
    "age": "उमेर(वर्ष)",
    "gender": "लिङ्ग",
    "spouse_name": "पति/पत्नीको नाम",
    "parent_name": "पिता/माताको नाम",
    "details": "मतदाता विवरण",
}


def _normalize_ward_name(filename: str) -> str:
    """
    Try to extract a clean ward identifier from a filename like:
    - 'ward_01.xlsx'
    - 'ward-01.xlsx'
    - 'ward no_1.xlsx'
    - 'ward no _2.xlsx'
    Returns a string ward number (e.g. '1', '2', '3') or the original
    filename stem on failure.
    """
    name = os.path.splitext(os.path.basename(filename))[0].lower()
    for token in ["ward", "no", "_", "-", " "]:
        name = name.replace(token, " ")
    parts = [p for p in name.split() if p.isdigit()]
    if parts:
        # Remove leading zeros
        return str(int(parts[0]))
    return os.path.splitext(os.path.basename(filename))[0]


def _discover_excel_files(base_dir: str) -> List[Tuple[str, str]]:
    """
    Walk BASE_DIR and return list of (municipality_name, absolute_excel_path).
    Assumes each immediate subdirectory under base_dir is a municipality
    containing ward-level Excel files.
    """
    files: List[Tuple[str, str]] = []
    for entry in sorted(os.listdir(base_dir)):
        muni_path = os.path.join(base_dir, entry)
        if not os.path.isdir(muni_path):
            continue
        municipality = entry
        for fname in sorted(os.listdir(muni_path)):
            if not fname.lower().endswith(".xlsx"):
                continue
            files.append((municipality, os.path.join(muni_path, fname)))
    return files


def load_all_voters(
    base_dir: str = BASE_DIR,
    column_mapping: Optional[Dict[str, str]] = None,
) -> pd.DataFrame:
    """
    Load all Excel files and sheets into a single DataFrame.

    Parameters
    ----------
    base_dir:
        Root directory containing municipality subfolders.
    column_mapping:
        Optional mapping of expected logical fields to actual column
        names in the Excel files, e.g.:
        {
            "voter_id": "मतदाता क्रम सं.",
            "name": "नाम",
            "age": "उमेर",
            "dob": "जन्म मिति",
            "gender": "लिङ्ग",
            "caste": "जात",
            "address": "ठेगाना",
        }
        If provided, these logical keys will be standardized in the
        returned DataFrame.

    Returns
    -------
    pd.DataFrame
        Combined DataFrame with at least:
        - municipality
        - ward
        - booth  (sheet name)
        Plus all original columns, and standardized columns where mapping exists.
    """
    if column_mapping is None:
        column_mapping = DEFAULT_COLUMN_MAPPING

    excel_files = _discover_excel_files(base_dir)
    frames: List[pd.DataFrame] = []

    for municipality, path in excel_files:
        try:
            xls = pd.ExcelFile(path, engine="openpyxl")
        except Exception as exc:
            print(f"Failed to open {path}: {exc}")
            continue

        ward = _normalize_ward_name(path)

        for sheet_name in xls.sheet_names:
            try:
                # Many of these sheets have header rows after some empty rows.
                # We scan for the first row that looks like it contains our known
                # Nepali headers, then use it as the header row.
                tmp = pd.read_excel(
                    xls, sheet_name=sheet_name, header=None, dtype=str
                )
            except Exception as exc:
                print(f"Failed to read sheet {sheet_name} in {path}: {exc}")
                continue

            if tmp.empty:
                continue

            header_row_idx = None
            header_values = set(column_mapping.values())
            for idx in range(len(tmp)):
                row_values = {str(v).strip() for v in tmp.iloc[idx].tolist()}
                # If at least 3 known headers appear in this row, treat it as header.
                if len(row_values & header_values) >= 3:
                    header_row_idx = idx
                    break

            if header_row_idx is None:
                # Fallback to default header=0 if we cannot detect it
                df = pd.read_excel(xls, sheet_name=sheet_name, dtype=str)
            else:
                df = pd.read_excel(
                    xls,
                    sheet_name=sheet_name,
                    header=header_row_idx,
                    dtype=str,
                )

            if df.empty:
                continue

            df["municipality"] = municipality
            df["ward"] = ward
            df["booth"] = sheet_name

            # Apply column mapping to create standardized logical fields
            for logical_name, actual_col in column_mapping.items():
                if actual_col in df.columns:
                    df[logical_name] = df[actual_col]

            frames.append(df)

    if not frames:
        return pd.DataFrame()

    combined = pd.concat(frames, ignore_index=True)

    # Basic cleanup: strip whitespace in object columns
    for col in combined.select_dtypes(include=["object"]).columns:
        combined[col] = combined[col].astype(str).str.strip()

    # If both dob and age exist, prefer numeric age
    if "dob" in combined.columns and "age" not in combined.columns:
        # Age derivation from DOB is data-format dependent; leave as-is for now.
        pass

    return combined


def add_derived_fields(df: pd.DataFrame) -> pd.DataFrame:
    """
    Add derived / normalized fields useful for analytics.
    This function is conservative because we don't yet know the exact schema.
    """
    result = df.copy()

    # Derive surname/thar from full voter name: last word is treated as surname.
    # Example: "अकलेश कुमार गुप्ता" -> "गुप्ता"
    if "name" in result.columns:
        name_series = result["name"].astype(str).str.strip()
        result["surname"] = (
            name_series.str.split().str[-1].where(name_series.ne(""), None)
        )

    # Normalize gender if present in a few common English/Nepali forms
    if "gender" in result.columns:
        g = result["gender"].astype(str).str.lower()
        result["gender_norm"] = g.replace(
            {
                "m": "Male",
                "male": "Male",
                "f": "Female",
                "female": "Female",
                "पुरुष": "Male",
                "महिला": "Female",
            }
        )

    # Simple age banding if age column exists and is numeric-like
    if "age" in result.columns:
        age_numeric = pd.to_numeric(result["age"], errors="coerce")
        bins = [0, 25, 35, 45, 60, 200]
        labels = ["18-25", "26-35", "36-45", "46-60", "60+"]
        result["age_band"] = pd.cut(age_numeric, bins=bins, labels=labels, right=True)

    # Create a convenient location key
    for col in ["municipality", "ward", "booth"]:
        if col not in result.columns:
            result[col] = ""
    result["location_key"] = (
        result["municipality"].astype(str)
        + " - वडा "
        + result["ward"].astype(str)
        + " - "
        + result["booth"].astype(str)
    )

    return result


if __name__ == "__main__":
    # Quick manual test helper
    voters = load_all_voters()
    voters = add_derived_fields(voters)
    print(voters.head())
    print("Total voters loaded:", len(voters))

