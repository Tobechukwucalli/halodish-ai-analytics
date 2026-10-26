from pathlib import Path
import json
import re

import pandas as pd
import streamlit as st
import plotly.express as px


# ============================================================
# PAGE CONFIGURATION
# ============================================================

st.set_page_config(
    page_title="HaloDish AI Analytic Dashboard",
    page_icon="🍽️",
    layout="wide"
)


# ============================================================
# DASHBOARD TITLE
# ============================================================

st.title("🍽️ HaloDish AI Analytic Dashboard")


# ============================================================
# DATA LOCATION
# ============================================================

BASE_DIR = Path(__file__).resolve().parent
DATA_DIR = BASE_DIR / "Data"


# ============================================================
# LOAD DATASETS
# ============================================================

logs = pd.read_csv(
    DATA_DIR / "dineout_logs_202609170953.csv.gz"
)

spot_logs = pd.read_csv(
    DATA_DIR / "tourist_spot_logs.csv", low_memory=False
)

restaurants = pd.read_csv(
    DATA_DIR / "restaurant_sheet.csv"
)

# Use the uploaded tourist dataset when present; retain the original filename as a fallback.
tourist_file = DATA_DIR / "Tourist_Data_Updated.csv"
if not tourist_file.exists():
    tourist_file = DATA_DIR / "tourist_extracted_data.csv"

tourists = pd.read_csv(tourist_file)

restaurant_views_data = pd.read_csv(
    DATA_DIR / "restaurant_views_4digit_matched.csv"
)


# ============================================================
# DATA LOADING CONFIRMATION
# ============================================================

st.success("All datasets loaded successfully!")


# ============================================================
# PREPARE CREATED_AT
# ============================================================

restaurant_views_data["created_at"] = pd.to_datetime(
    restaurant_views_data["created_at"],
    errors="coerce"
)

restaurant_views_data = restaurant_views_data[
    restaurant_views_data["created_at"].notna()
].copy()


# ============================================================
# CREATE DATE AND TIME FIELDS
# ============================================================

restaurant_views_data["view_date"] = (
    restaurant_views_data["created_at"].dt.date
)

restaurant_views_data["view_hour"] = (
    restaurant_views_data["created_at"].dt.hour
)

restaurant_views_data["view_day"] = (
    restaurant_views_data["created_at"].dt.day_name()
)

restaurant_views_data["view_time"] = (
    restaurant_views_data["created_at"].dt.strftime("%H:%M:%S")
)


# ============================================================
# KEY PERFORMANCE INDICATORS
# ============================================================

col1, col2, col3, col4 = st.columns(4)

col1.metric(
    "Total Events",
    f"{len(logs):,}"
)

col2.metric(
    "Restaurants",
    f"{len(restaurants):,}"
)

col3.metric(
    "Tourist Records",
    f"{len(tourists):,}"
)

col4.metric(
    "Restaurant Views",
    f"{len(restaurant_views_data):,}"
)


# ============================================================
# MOST VIEWED TOURIST SPOTS — within the HaloDish AI dashboard
# ============================================================

st.divider()
st.header("🗾 Most Viewed Tourist Spots")
st.write(
    "Tourist-spot analytics are integrated into HaloDish AI. "
    "Individual view events from tourist_spot_logs.csv are matched to "
    "Tourist_Data_Updated.csv using the numeric tourist-spot ID."
)

required_log_cols = {"event_type", "event_action", "created_at"}
required_lookup_cols = {"Name", "slug_data"}
missing_log_cols = required_log_cols - set(spot_logs.columns)
missing_lookup_cols = required_lookup_cols - set(tourists.columns)

if missing_log_cols:
    st.warning(
        "Tourist-spot analytics could not run. Missing column(s) in "
        f"tourist_spot_logs.csv: {', '.join(sorted(missing_log_cols))}."
    )
elif missing_lookup_cols:
    st.warning(
        "Tourist-spot analytics could not run. The tourist lookup file needs "
        f"these column(s): {', '.join(sorted(missing_lookup_cols))}."
    )
else:
    # Normalize the lookup IDs; slug_data is the numeric ID (e.g. 2051).
    tourist_lookup = tourists[["Name", "slug_data"]].copy()
    tourist_lookup["tourist_spot_id"] = (
        tourist_lookup["slug_data"]
        .astype("string")
        .str.extract(r"(\d+)", expand=False)
    )
    tourist_lookup["Name"] = tourist_lookup["Name"].astype("string").str.strip()
    tourist_lookup = (
        tourist_lookup.dropna(subset=["tourist_spot_id", "Name"])
        .drop_duplicates(subset=["tourist_spot_id"], keep="first")
    )

    # Count only event_type=view entries that contain an individual
    # tourist_spot_id. Collection views and unrelated events are excluded.
    tourist_views = spot_logs.loc[
        spot_logs["event_type"].astype("string").str.strip().str.lower().eq("view")
    ].copy()

    def extract_tourist_spot_id(value):
        if pd.isna(value):
            return pd.NA
        try:
            parsed = json.loads(str(value))
            if isinstance(parsed, dict) and parsed.get("tourist_spot_id") is not None:
                return str(parsed["tourist_spot_id"]).strip()
        except (json.JSONDecodeError, TypeError, ValueError):
            pass
        match = re.search(r'"tourist_spot_id"\s*:\s*"?(\d+)"?', str(value))
        return match.group(1) if match else pd.NA

    tourist_views["tourist_spot_id"] = (
        tourist_views["event_action"].map(extract_tourist_spot_id).astype("string")
    )
    tourist_views = tourist_views.dropna(subset=["tourist_spot_id"]).copy()
    tourist_views["tourist_spot_id"] = (
        tourist_views["tourist_spot_id"].str.extract(r"(\d+)", expand=False)
    )
    tourist_views = tourist_views.dropna(subset=["tourist_spot_id"]).copy()
    tourist_views["created_at"] = pd.to_datetime(
        tourist_views["created_at"], errors="coerce", utc=True
    )
    tourist_views = tourist_views.dropna(subset=["created_at"]).copy()

    tourist_views = tourist_views.merge(
        tourist_lookup[["tourist_spot_id", "Name"]],
        on="tourist_spot_id",
        how="left",
    )
    tourist_views["Name"] = tourist_views["Name"].fillna(
        "Unknown tourist spot (ID " + tourist_views["tourist_spot_id"] + ")"
    )

    if tourist_views.empty:
        st.info(
            "No individual tourist-spot view records were found. Confirm that "
            "event_action contains values such as {\"tourist_spot_id\": \"2051\"}."
        )
    else:
        tourist_views["view_date"] = tourist_views["created_at"].dt.date
        tourist_views["view_hour"] = tourist_views["created_at"].dt.hour
        tourist_views["view_day"] = tourist_views["created_at"].dt.day_name()
        tourist_views["view_time"] = tourist_views["created_at"].dt.strftime("%H:%M:%S")

        min_tourist_date = tourist_views["view_date"].min()
        max_tourist_date = tourist_views["view_date"].max()
        tourist_date_range = st.date_input(
            "Tourist-spot viewing date range",
            value=(min_tourist_date, max_tourist_date),
            min_value=min_tourist_date,
            max_value=max_tourist_date,
            key="tourist_view_date_range",
        )

        filtered_tourist_views = tourist_views.copy()
        if isinstance(tourist_date_range, (tuple, list)) and len(tourist_date_range) == 2:
            tourist_start, tourist_end = tourist_date_range
            filtered_tourist_views = filtered_tourist_views[
                filtered_tourist_views["view_date"].between(tourist_start, tourist_end)
            ].copy()

        tourist_counts = (
            filtered_tourist_views.groupby(
                ["tourist_spot_id", "Name"], dropna=False
            )
            .size()
            .reset_index(name="views")
            .sort_values("views", ascending=False)
        )

        total_tourist_views = len(filtered_tourist_views)
        unique_tourist_spots = filtered_tourist_views["tourist_spot_id"].nunique()
        unique_viewers = (
            filtered_tourist_views["ip_address"].nunique()
            if "ip_address" in filtered_tourist_views.columns else None
        )

        kpi_cols = st.columns(4)
        kpi_cols[0].metric("Total Tourist-Spot Views", f"{total_tourist_views:,}")
        kpi_cols[1].metric("Unique Tourist Spots Viewed", f"{unique_tourist_spots:,}")
        kpi_cols[2].metric(
            "Most Viewed Tourist Spot",
            str(tourist_counts.iloc[0]["Name"]) if not tourist_counts.empty else "N/A",
        )
        if unique_viewers is not None:
            kpi_cols[3].metric("Unique IP Addresses", f"{unique_viewers:,}")
        else:
            kpi_cols[3].metric("Unique IP Addresses", "Not available")

        top_n = st.slider(
            "Number of tourist spots to display",
            min_value=5,
            max_value=30,
            value=10,
            key="tourist_top_n",
        )
        top_tourist_spots = tourist_counts.head(top_n).copy()

        chart_left, chart_right = st.columns(2)
        with chart_left:
            if not top_tourist_spots.empty:
                fig_tourist_top = px.bar(
                    top_tourist_spots.sort_values("views"),
                    x="views",
                    y="Name",
                    orientation="h",
                    text="views",
                    hover_data={"tourist_spot_id": True, "views": True},
                    title=f"Top {len(top_tourist_spots)} Most Viewed Tourist Spots",
                    labels={"views": "View Events", "Name": "Tourist Spot"},
                )
                fig_tourist_top.update_traces(
                    texttemplate="%{text:,}", textposition="outside"
                )
                fig_tourist_top.update_layout(
                    height=max(450, 32 * len(top_tourist_spots)),
                    yaxis_title="Tourist Spot",
                    xaxis_title="Number of Views",
                )
                st.plotly_chart(fig_tourist_top, use_container_width=True)

        with chart_right:
            if not top_tourist_spots.empty:
                fig_tourist_share = px.pie(
                    top_tourist_spots,
                    names="Name",
                    values="views",
                    hole=0.45,
                    title="View Share Among Top Tourist Spots",
                )
                fig_tourist_share.update_layout(height=500)
                st.plotly_chart(fig_tourist_share, use_container_width=True)

        # View activity over time: daily, hourly, and day-of-week.
        st.subheader("📅 Tourist-Spot Views Over Time")
        tourist_time_mode = st.selectbox(
            "Tourist-spot time analysis",
            ["Daily", "Hourly", "Day of Week"],
            key="tourist_time_mode",
        )

        if tourist_time_mode == "Daily":
            time_data = (
                filtered_tourist_views.groupby("view_date")
                .size().reset_index(name="views")
            )
            time_data["view_date"] = pd.to_datetime(time_data["view_date"])
            fig_tourist_time = px.line(
                time_data, x="view_date", y="views", markers=True,
                title="Tourist-Spot Views by Date",
                labels={"view_date": "Date", "views": "View Events"},
            )
        elif tourist_time_mode == "Hourly":
            time_data = (
                filtered_tourist_views.groupby("view_hour")
                .size().reset_index(name="views")
            )
            time_data["hour_label"] = time_data["view_hour"].map(
                lambda hour: f"{int(hour):02d}:00"
            )
            fig_tourist_time = px.bar(
                time_data, x="hour_label", y="views", text="views",
                title="Tourist-Spot Views by Hour",
                labels={"hour_label": "Hour of Day", "views": "View Events"},
            )
            fig_tourist_time.update_traces(
                texttemplate="%{text:,}", textposition="outside"
            )
        else:
            day_order = [
                "Monday", "Tuesday", "Wednesday", "Thursday",
                "Friday", "Saturday", "Sunday",
            ]
            time_data = (
                filtered_tourist_views.groupby("view_day")
                .size().reindex(day_order, fill_value=0)
                .rename("views").reset_index()
            )
            time_data = time_data.rename(columns={"index": "view_day"})
            fig_tourist_time = px.bar(
                time_data, x="view_day", y="views", text="views",
                title="Tourist-Spot Views by Day of Week",
                labels={"view_day": "Day", "views": "View Events"},
            )
            fig_tourist_time.update_traces(
                texttemplate="%{text:,}", textposition="outside"
            )

        fig_tourist_time.update_layout(height=450)
        st.plotly_chart(fig_tourist_time, use_container_width=True)

        # Compare trends for the five most-viewed spots.
        st.subheader("📈 Popular Tourist Spots Over Time")
        trend_spots = tourist_counts.head(5)["tourist_spot_id"].tolist()
        tourist_trend_data = filtered_tourist_views[
            filtered_tourist_views["tourist_spot_id"].isin(trend_spots)
        ].copy()
        if not tourist_trend_data.empty:
            tourist_trend_daily = (
                tourist_trend_data.groupby(["view_date", "Name"])
                .size().reset_index(name="views")
            )
            tourist_trend_daily["view_date"] = pd.to_datetime(
                tourist_trend_daily["view_date"]
            )
            fig_tourist_trend = px.line(
                tourist_trend_daily, x="view_date", y="views", color="Name",
                markers=True, title="Daily Views for the Top Five Tourist Spots",
                labels={"view_date": "Date", "views": "View Events", "Name": "Tourist Spot"},
            )
            fig_tourist_trend.update_layout(height=500)
            st.plotly_chart(fig_tourist_trend, use_container_width=True)

        # Optional geographic/user context from fields already in the log.
        if "user_location" in filtered_tourist_views.columns:
            location_counts = (
                filtered_tourist_views["user_location"].fillna("Unknown")
                .replace("", "Unknown").value_counts()
                .head(15).rename_axis("user_location")
                .reset_index(name="views")
            )
            if location_counts["user_location"].ne("Unknown").any():
                st.subheader("🌏 Tourist-Spot Views by Recorded User Location")
                fig_locations = px.bar(
                    location_counts.sort_values("views"),
                    x="views", y="user_location", orientation="h",
                    title="Top Recorded User Locations",
                    labels={"user_location": "Recorded Location", "views": "View Events"},
                )
                fig_locations.update_layout(height=450)
                st.plotly_chart(fig_locations, use_container_width=True)

        with st.expander("View tourist-spot lookup and detailed view records"):
            st.markdown("**Tourist-spot view counts**")
            st.dataframe(
                tourist_counts.rename(columns={
                    "tourist_spot_id": "Tourist Spot ID",
                    "Name": "Tourist Spot",
                    "views": "View Events",
                }),
                use_container_width=True,
                hide_index=True,
            )
            st.markdown("**Individual view records**")
            record_cols = [
                col for col in [
                    "created_at", "tourist_spot_id", "Name", "event_type",
                    "event_action", "ip_address", "user_location", "user_id_id",
                ]
                if col in filtered_tourist_views.columns
            ]
            st.dataframe(
                filtered_tourist_views[record_cols].sort_values(
                    "created_at", ascending=False
                ),
                use_container_width=True,
                hide_index=True,
            )

# MOST VIEWED RESTAURANTS
# ============================================================

st.divider()

st.header("🍽️ Most Viewed Restaurants")

st.write(
    "This visualization shows the restaurants receiving the "
    "highest number of customer restaurant-view events."
)


# ============================================================
# DATE FILTER
# ============================================================

min_date = restaurant_views_data["view_date"].min()
max_date = restaurant_views_data["view_date"].max()

date_range = st.date_input(
    "Select viewing date range",
    value=(min_date, max_date),
    min_value=min_date,
    max_value=max_date
)


if isinstance(date_range, tuple) and len(date_range) == 2:

    start_date = date_range[0]
    end_date = date_range[1]

    filtered_views = restaurant_views_data[
        (restaurant_views_data["view_date"] >= start_date)
        & (restaurant_views_data["view_date"] <= end_date)
    ].copy()

else:

    start_date = min_date
    end_date = max_date

    filtered_views = restaurant_views_data.copy()


# ============================================================
# NUMBER OF RESTAURANTS TO DISPLAY
# ============================================================

number_of_restaurants = st.slider(
    "Number of restaurants to display",
    min_value=5,
    max_value=30,
    value=10
)


# ============================================================
# COUNT RESTAURANT VIEWS
# ============================================================

restaurant_views = (
    filtered_views
    .groupby(
        ["restaurant_code", "Name"],
        dropna=False
    )
    .size()
    .reset_index(name="views")
)

restaurant_views = restaurant_views.sort_values(
    "views",
    ascending=False
)

top_restaurants = restaurant_views.head(
    number_of_restaurants
)


# ============================================================
# MOST VIEWED RESTAURANTS BAR CHART
# ============================================================

fig = px.bar(
    top_restaurants.sort_values("views"),
    x="views",
    y="Name",
    orientation="h",
    text="views",
    title=(
        f"Top {number_of_restaurants} Most Viewed Restaurants "
        f"({start_date} to {end_date})"
    ),
    labels={
        "views": "Number of Views",
        "Name": "Restaurant"
    }
)

fig.update_traces(
    texttemplate="%{text:,}",
    textposition="outside"
)

fig.update_layout(
    height=600,
    xaxis_title="Number of Views",
    yaxis_title="Restaurant"
)

st.plotly_chart(
    fig,
    use_container_width=True
)


# ============================================================
# RESTAURANT VIEWS OVER TIME
# ============================================================

st.divider()

st.header("📅 Restaurant Views Over Time")

st.write(
    "Track when customers viewed restaurants and identify "
    "periods of high restaurant discovery activity."
)


# ============================================================
# TIME GRANULARITY
# ============================================================

time_granularity = st.selectbox(
    "Select time analysis",
    [
        "Daily",
        "Hourly",
        "Day of Week"
    ]
)


# ============================================================
# DAILY VIEW TREND
# ============================================================

if time_granularity == "Daily":

    daily_views = (
        filtered_views
        .groupby("view_date")
        .size()
        .reset_index(name="views")
    )

    daily_views["view_date"] = pd.to_datetime(
        daily_views["view_date"]
    )

    fig_time = px.line(
        daily_views,
        x="view_date",
        y="views",
        markers=True,
        title="Restaurant Views by Date",
        labels={
            "view_date": "Date",
            "views": "Number of Restaurant Views"
        }
    )

    fig_time.update_layout(
        height=500
    )

    st.plotly_chart(
        fig_time,
        use_container_width=True
    )


# ============================================================
# HOURLY VIEW TREND
# ============================================================

elif time_granularity == "Hourly":

    hourly_views = (
        filtered_views
        .groupby("view_hour")
        .size()
        .reset_index(name="views")
    )

    hourly_views["hour_label"] = (
        hourly_views["view_hour"]
        .astype(str)
        .str.zfill(2)
        + ":00"
    )

    fig_time = px.bar(
        hourly_views,
        x="hour_label",
        y="views",
        text="views",
        title="Restaurant Views by Hour of Day",
        labels={
            "hour_label": "Time of Day",
            "views": "Number of Restaurant Views"
        }
    )

    fig_time.update_traces(
        texttemplate="%{text:,}",
        textposition="outside"
    )

    fig_time.update_layout(
        height=500
    )

    st.plotly_chart(
        fig_time,
        use_container_width=True
    )


# ============================================================
# DAY OF WEEK ANALYSIS
# ============================================================

elif time_granularity == "Day of Week":

    day_order = [
        "Monday",
        "Tuesday",
        "Wednesday",
        "Thursday",
        "Friday",
        "Saturday",
        "Sunday"
    ]

    weekday_views = (
        filtered_views
        .groupby("view_day")
        .size()
        .reset_index(name="views")
    )

    weekday_views["view_day"] = pd.Categorical(
        weekday_views["view_day"],
        categories=day_order,
        ordered=True
    )

    weekday_views = weekday_views.sort_values(
        "view_day"
    )

    fig_time = px.bar(
        weekday_views,
        x="view_day",
        y="views",
        text="views",
        title="Restaurant Views by Day of Week",
        labels={
            "view_day": "Day",
            "views": "Number of Restaurant Views"
        }
    )

    fig_time.update_traces(
        texttemplate="%{text:,}",
        textposition="outside"
    )

    fig_time.update_layout(
        height=500
    )

    st.plotly_chart(
        fig_time,
        use_container_width=True
    )


# ============================================================
# TOP RESTAURANTS OVER TIME
# ============================================================

st.divider()

st.header("📈 Most Viewed Restaurants Over Time")

st.write(
    "Compare how the most viewed restaurants perform over "
    "the selected period."
)


top_codes = top_restaurants[
    "restaurant_code"
].tolist()


top_restaurant_trend = filtered_views[
    filtered_views["restaurant_code"].isin(top_codes)
].copy()


restaurant_daily = (
    top_restaurant_trend
    .groupby(
        ["view_date", "Name"]
    )
    .size()
    .reset_index(name="views")
)


restaurant_daily["view_date"] = pd.to_datetime(
    restaurant_daily["view_date"]
)


fig_restaurant_trend = px.line(
    restaurant_daily,
    x="view_date",
    y="views",
    color="Name",
    markers=True,
    title="Restaurant View Trends Over Time",
    labels={
        "view_date": "Date",
        "views": "Number of Views",
        "Name": "Restaurant"
    }
)

fig_restaurant_trend.update_layout(
    height=600
)

st.plotly_chart(
    fig_restaurant_trend,
    use_container_width=True
)


# ============================================================
# VIEW DATA TABLE
# ============================================================

st.divider()

st.header("📋 Restaurant View Records")

st.write(
    "Detailed restaurant-view records including restaurant name, "
    "restaurant code, viewing date and viewing time."
)


display_columns = [
    "restaurant_code",
    "Name",
    "created_at",
    "view_date",
    "view_hour",
    "view_day",
    "event_type"
]

st.dataframe(
    filtered_views[display_columns]
    .sort_values("created_at", ascending=False),
    use_container_width=True,
    hide_index=True
)