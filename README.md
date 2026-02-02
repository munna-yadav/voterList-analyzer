## Voter Analytics Dashboard (Matdata Namawali)

Python + Streamlit dashboard for analyzing voter lists of multiple municipalities/wards in Nepal.

### 1. Prerequisites

- Python 3.10+ installed
- Excel voter files already placed under `Matdata Namawali` exactly as you have them:
  - Each subfolder = municipality (e.g. `suwarna`, `Devtal`, `KaraiyaMai`).
  - Each `.xlsx` file = ward.
  - Each sheet inside a file = booth / polling center.

### 2. Setup (one time)

From the `Matdata Namawali` folder:

```bash
cd "/home/munna/Downloads/Matdata Namawali"
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

### 3. Run the dashboard

From the same folder, with the virtual environment activated:

```bash
cd "/home/munna/Downloads/Matdata Namawali"
source .venv/bin/activate
streamlit run app.py
```

Your browser should open automatically. If not, open the URL shown in the terminal (usually `http://localhost:8501`).

### 4. How the data is loaded

- All municipality folders under `Matdata Namawali` are scanned automatically.
- Every Excel file (`.xlsx`) inside each municipality folder is treated as a ward file.
- Every sheet in each Excel file is treated as a polling booth.
- The loader:
  - Detects the real table header row (e.g. row with `सि.नं.`, `मतदाता नं`, `मतदाताको नाम`, `उमेर(वर्ष)`, `लिङ्ग`).
  - Standardizes helpful columns such as:
    - `serial_no` (सि.नं.)
    - `voter_no` (मतदाता नं)
    - `name` (मतदाताको नाम)
    - `age` (उमेर(वर्ष))
    - `gender` (लिङ्ग)
    - `spouse_name` (पति/पत्नीको नाम)
    - `parent_name` (पिता/माताको नाम)
  - Adds location info:
    - `municipality`
    - `ward`
    - `booth`

### 5. Using the dashboard

- **Filters (left sidebar)**:
  - Municipality → Ward → Booth cascading selection (or leave as “सबै” for all).
  - Age range slider (if age is available).
  - Gender multi-select.
  - Caste multi-select (if any caste column is present).
- **Top section**:
  - Total voters in current filter.
  - Gender distribution chart.
  - Age distribution chart.
- **Middle section**:
  - Caste-wise counts (bar chart) if caste column exists.
  - Ranked list of municipality/ward/booth combinations by number of voters.
- **Bottom section**:
  - Detailed voter table (serial number, voter number, name, age, gender, location).
  - Button to download the filtered table as CSV (UTF-8, ready for Excel).

### 6. Notes / Customization

- If any municipality uses slightly different column headers for name/age/gender, you can update `DEFAULT_COLUMN_MAPPING` in `load_data.py`.
- All data stays on your laptop; nothing is sent to the internet.
- You can create different filter presets (e.g. “youth voters” or “women in specific wards”) by choosing filters and downloading the CSV lists for field teams.

