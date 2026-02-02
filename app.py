import os

import pandas as pd
import streamlit as st

from load_data import BASE_DIR, add_derived_fields, load_all_voters


st.set_page_config(
    page_title="मतदाता विश्लेषण ड्यासबोर्ड",
    layout="wide",
)


LABELS_NP = {
    "title": "मतदाता विश्लेषण ड्यासबोर्ड",
    "sidebar_title": "फिल्टर",
    "municipality": "नगरपालिका",
    "ward": "वडा",
    "booth": "मतदान केन्द्र",
    "age": "उमेर",
    "age_band": "उमेर समूह",
    "gender": "लिङ्ग",
    "caste": "जात/थर (यदि उपलब्ध)",
    "total_voters": "कुल मतदाता",
    "gender_dist": "लिङ्ग अनुसार मतदाता",
    "age_dist": "उमेर वितरण",
    "caste_dist": "जात अनुसार मतदाता",
    "location_rank": "स्थान अनुसार लक्षित मतदाता",
    "table_title": "विस्तृत मतदाता सूची",
    "download": "डाउनलोड (CSV)",
}


def compute_data_version(base_dir: str = BASE_DIR) -> float:
    """
    Return a number that changes whenever any Excel voter file
    in BASE_DIR is modified or a new one is added.
    Used to invalidate Streamlit cache automatically.
    """
    latest_mtime = 0.0
    for root, _, files in os.walk(base_dir):
        for fname in files:
            if not fname.lower().endswith(".xlsx"):
                continue
            path = os.path.join(root, fname)
            try:
                mtime = os.path.getmtime(path)
            except OSError:
                continue
            if mtime > latest_mtime:
                latest_mtime = mtime
    return latest_mtime


@st.cache_data(show_spinner=True)
def load_cached_data(data_version: float) -> pd.DataFrame:
    # data_version is only used so that cache refreshes when files change.
    _ = data_version
    df = load_all_voters(BASE_DIR)
    df = add_derived_fields(df)
    return df


def build_sidebar(df: pd.DataFrame) -> pd.DataFrame:
    st.sidebar.header(LABELS_NP["sidebar_title"])

    muni_options = sorted(df["municipality"].dropna().unique().tolist())
    muni = st.sidebar.selectbox(LABELS_NP["municipality"], options=["सबै"] + muni_options)

    filtered = df.copy()
    if muni != "सबै":
        filtered = filtered[filtered["municipality"] == muni]

    ward_options = sorted(filtered["ward"].dropna().unique().tolist())
    ward = st.sidebar.selectbox(LABELS_NP["ward"], options=["सबै"] + ward_options)
    if ward != "सबै":
        filtered = filtered[filtered["ward"] == ward]

    booth_options = sorted(filtered["booth"].dropna().unique().tolist())
    booth = st.sidebar.selectbox(LABELS_NP["booth"], options=["सबै"] + booth_options)
    if booth != "सबै":
        filtered = filtered[filtered["booth"] == booth]

    # Age filter
    if "age" in filtered.columns:
        age_numeric = pd.to_numeric(filtered["age"], errors="coerce")
        min_age = int(age_numeric.min()) if age_numeric.notna().any() else 18
        max_age = int(age_numeric.max()) if age_numeric.notna().any() else 100
        age_min, age_max = st.sidebar.slider(
            LABELS_NP["age"],
            min_value=min_age,
            max_value=max_age,
            value=(min_age, max_age),
        )
        mask_age = age_numeric.between(age_min, age_max)
        filtered = filtered[mask_age]

    # Gender filter
    gender_col = "gender_norm" if "gender_norm" in filtered.columns else "gender"
    if gender_col in filtered.columns:
        genders = sorted(filtered[gender_col].dropna().unique().tolist())
        selected_genders = st.sidebar.multiselect(
            LABELS_NP["gender"],
            options=genders,
            default=genders,
        )
        if selected_genders:
            filtered = filtered[filtered[gender_col].isin(selected_genders)]

    # Caste / surname filter:
    # Prefer derived surname from voter name; if not available, fall back to any जात/थर column.
    caste_col = None
    if "surname" in filtered.columns:
        caste_col = "surname"
    else:
        caste_candidates = [
            c
            for c in filtered.columns
            if ("जात" in c)
            or ("थर" in c)
            or ("caste" in c.lower())
        ]
        caste_col = caste_candidates[0] if caste_candidates else None

    if caste_col:
        castes = sorted(filtered[caste_col].dropna().unique().tolist())
        selected_castes = st.sidebar.multiselect(
            LABELS_NP["caste"],
            options=castes,
            default=castes,
        )
        if selected_castes:
            filtered = filtered[filtered[caste_col].isin(selected_castes)]

    return filtered


def main() -> None:
    st.title(LABELS_NP["title"])

    # This changes whenever any .xlsx file under BASE_DIR is touched,
    # so Streamlit will reload the data automatically.
    data_version = compute_data_version()
    df = load_cached_data(data_version)
    if df.empty:
        st.warning("कुनै पनि मतदाता डेटा भेटिएन। कृपया Excel फोल्डर जाँच गर्नुहोस्।")
        return

    filtered = build_sidebar(df)

    # Top metrics
    col1, col2, col3 = st.columns(3)
    with col1:
        st.metric(LABELS_NP["total_voters"], f"{len(filtered):,}")

    gender_col = "gender_norm" if "gender_norm" in filtered.columns else "gender"
    if gender_col in filtered.columns:
        gender_counts = filtered[gender_col].value_counts()
        with col2:
            st.subheader(LABELS_NP["gender_dist"])
            st.bar_chart(gender_counts)

    if "age" in filtered.columns:
        age_numeric = pd.to_numeric(filtered["age"], errors="coerce")
        with col3:
            st.subheader(LABELS_NP["age_dist"])
            if "age_band" in filtered.columns:
                age_band_counts = filtered["age_band"].value_counts().sort_index()
                st.bar_chart(age_band_counts)
            else:
                # Fallback: simple bar chart of raw ages
                st.bar_chart(age_numeric.dropna())

    # Middle section: caste/surname distribution + location ranking
    st.markdown("---")
    left, right = st.columns(2)

    caste_col = None
    if "surname" in filtered.columns:
        caste_col = "surname"
    else:
        caste_candidates = [
            c
            for c in filtered.columns
            if ("जात" in c)
            or ("थर" in c)
            or ("caste" in c.lower())
        ]
        caste_col = caste_candidates[0] if caste_candidates else None

    if caste_col:
        with left:
            st.subheader(LABELS_NP["caste_dist"])
            caste_counts = filtered[caste_col].value_counts().head(15)
            st.bar_chart(caste_counts)

    with right:
        st.subheader(LABELS_NP["location_rank"])
        loc_counts = (
            filtered.groupby(["municipality", "ward", "booth"])
            .size()
            .reset_index(name="count")
            .sort_values("count", ascending=False)
            .head(20)
        )
        st.dataframe(loc_counts, use_container_width=True)

    # Bottom: detailed voter table
    st.markdown("---")
    st.subheader(LABELS_NP["table_title"])

    display_cols = []
    for col in [
        "serial_no",
        "voter_no",
        "name",
        "age",
        "gender",
        "surname",
        "spouse_name",
        "parent_name",
        "municipality",
        "ward",
        "booth",
    ]:
        if col in filtered.columns:
            display_cols.append(col)

    table = filtered[display_cols] if display_cols else filtered
    st.dataframe(table, use_container_width=True, height=400)

    csv = table.to_csv(index=False).encode("utf-8-sig")
    st.download_button(
        label=LABELS_NP["download"],
        data=csv,
        file_name="voters_filtered.csv",
        mime="text/csv",
    )


if __name__ == "__main__":
    main()

