import streamlit as st
import pandas as pd
import altair as alt

# ----------------------
# App configuration
# ----------------------
st.set_page_config(
    page_title="🩺 Florence Nightingale Mortality Insights Dashboard",
    layout="wide"
)

# ----------------------
# Helpers: column normalization & detection
# ----------------------
def normalize_columns(df: pd.DataFrame) -> pd.DataFrame:
    df = df.copy()
    df.columns = df.columns.str.strip().str.lower().str.replace(" ", "_")
    return df

def find_first(df_cols, candidates):
    """
    Return first matching column name found in df_cols from candidates list, or None.
    """
    for c in candidates:
        if c in df_cols:
            return c
    return None

@st.cache_data
def load_data(path="yearly_deaths_by_clinic.csv"):
    df = pd.read_csv(path)
    df = normalize_columns(df)

    # map common variants
    year_col = find_first(df.columns, ["year", "yr"])
    death_col = find_first(df.columns, ["deaths", "death", "deaths_count", "death_count"])
    birth_col = find_first(df.columns, ["births", "birth", "birth_count", "births_count"])
    clinic_col = find_first(df.columns, ["clinic", "hospital", "place", "location"])

    # convert types if present
    if year_col:
        df[year_col] = pd.to_numeric(df[year_col], errors="coerce").astype("Int64")
    if death_col:
        df[death_col] = pd.to_numeric(df[death_col], errors="coerce")
    if birth_col:
        df[birth_col] = pd.to_numeric(df[birth_col], errors="coerce")

    # attach metadata to df for later reference by the app
    df.attrs["cols_map"] = {
        "year": year_col,
        "deaths": death_col,
        "births": birth_col,
        "clinic": clinic_col
    }

    return df

# ----------------------
# App header
# ----------------------
st.title("🩺 Florence Nightingale Mortality Insights Dashboard")
st.markdown(
    """
    *Description:* This app visualizes trends in yearly deaths across clinics/hospitals.
    Use the controls on the left to filter the years or clinics.
    (Code assisted by ChatGPT — see comments in app.py.)
    """
)

# ----------------------
# Load and inspect data
# ----------------------
try:
    df = load_data()
except FileNotFoundError:
    st.error("CSV yearly_deaths_by_clinic.csv not found. Put it in the repo root and redeploy.")
    st.stop()

cols_map = df.attrs.get("cols_map", {})
YEAR_COL = cols_map.get("year")
DEATHS_COL = cols_map.get("deaths")
BIRTHS_COL = cols_map.get("births")
CLINIC_COL = cols_map.get("clinic")

# If required column missing, inform user
if not YEAR_COL or not DEATHS_COL:
    st.error(
        "Required columns not found. CSV needs at least a Year column and a Deaths column. "
        f"Detected columns: {list(df.columns)}"
    )
    st.stop()

# If clinic column missing, create a placeholder 'clinic' so app still works
if not CLINIC_COL:
    df["clinic_placeholder"] = "All"
    CLINIC_COL = "clinic_placeholder"

# Rename to standard internal names to simplify downstream code
df = df.rename(columns={YEAR_COL: "year", DEATHS_COL: "deaths", CLINIC_COL: "clinic"})
if BIRTHS_COL:
    df = df.rename(columns={BIRTHS_COL: "births"})

# Ensure types
df["year"] = pd.to_numeric(df["year"], errors="coerce").astype("Int64")
df["deaths"] = pd.to_numeric(df["deaths"], errors="coerce")
if "births" in df.columns:
    df["births"] = pd.to_numeric(df["births"], errors="coerce")

# show a short preview
st.markdown("## Raw Data Preview")
st.dataframe(df.head(20))

# ----------------------
# Sidebar filters
# ----------------------
st.sidebar.header("Filters")
min_year = int(df["year"].min())
max_year = int(df["year"].max())

year_range = st.sidebar.slider("Select year range", min_year, max_year, (min_year, max_year), step=1)

clinic_list = sorted(df["clinic"].dropna().unique().tolist())
selected_clinics = st.sidebar.multiselect("Select clinic(s)", options=clinic_list, default=clinic_list[:3])

agg_option = st.sidebar.selectbox("Aggregation", options=["Sum", "Mean"], index=0)
agg_func = "sum" if agg_option == "Sum" else "mean"

# ----------------------
# Filter data
# ----------------------
filtered = df[(df["year"] >= year_range[0]) & (df["year"] <= year_range[1])]
if selected_clinics:
    filtered = filtered[filtered["clinic"].isin(selected_clinics)]

# ----------------------
# Charts
# ----------------------
# Time-series of deaths
deaths_by_year = filtered.groupby("year")["deaths"].agg(agg_func).reset_index()
line = alt.Chart(deaths_by_year).mark_line(point=True).encode(
    x=alt.X("year:O", title="Year"),
    y=alt.Y("deaths:Q", title=f"Deaths ({agg_option.lower()})"),
    tooltip=["year", "deaths"]
).properties(title="Trend: Deaths by Year", width=700, height=350)

# births vs deaths if births present
comparison_chart = None
if "births" in filtered.columns:
    comp = filtered.groupby("year")[["deaths", "births"]].agg(agg_func).reset_index().melt("year", var_name="metric", value_name="count")
    comparison_chart = alt.Chart(comp).mark_bar().encode(
        x=alt.X("year:O", title="Year"),
        y=alt.Y("count:Q", title=f"Count ({agg_option.lower()})"),
        color="metric:N",
        tooltip=["year", "metric", "count"]
    ).properties(title="Births vs Deaths by Year", width=700, height=350)

# deaths by clinic
clinic_agg = filtered.groupby("clinic")["deaths"].agg(agg_func).reset_index().sort_values("deaths", ascending=False)
bar = alt.Chart(clinic_agg).mark_bar().encode(
    x=alt.X("deaths:Q", title=f"Deaths ({agg_option.lower()})"),
    y=alt.Y("clinic:N", sort='-x', title="Clinic"),
    tooltip=["clinic", "deaths"]
).properties(title="Deaths by Clinic (selected range)", width=500, height=350)

# ----------------------
# Layout
# ----------------------
col1, col2 = st.columns([2, 1])

with col1:
    st.altair_chart(line, use_container_width=True)
    if comparison_chart:
        st.altair_chart(comparison_chart, use_container_width=True)

with col2:
    st.altair_chart(bar, use_container_width=True)
    st.subheader("Summary statistics")
    total_deaths = filtered["deaths"].agg(agg_func)
    st.metric(label="Deaths (aggregated)", value=f"{total_deaths:.0f}")
    if "births" in filtered.columns:
        total_births = filtered["births"].agg(agg_func)
        st.metric(label="Births (aggregated)", value=f"{total_births:.0f}")

# ----------------------
# Findings
# ----------------------
st.markdown("### Findings")
st.markdown(
    """
    From the selected range and clinics, we observe the overall trend of deaths across years. 
    Use the year range and clinic selector to examine whether deaths increase or decrease for specific hospitals. 
    (This short summary was assisted by ChatGPT.)
    """
)

# ----------------------
# Data preview and download
# ----------------------
with st.expander("Show filtered data"):
    st.dataframe(filtered.reset_index(drop=True))

csv = filtered.to_csv(index=False)
st.download_button("Download filtered data as CSV", data=csv, file_name="filtered_yearly_deaths.csv", mime="text/csv")

# ----------------------
# Footer note
# ----------------------
st.markdown("*Notes:* The app automatically normalizes column names (e.g., Clinic → clinic).")
