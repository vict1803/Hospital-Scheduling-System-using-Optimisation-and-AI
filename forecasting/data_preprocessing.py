
import pandas as pd

def load_patient_data(
    file_path,
    timestamp_col="timestamp",
    count_col="count"
):
    """
    Load patient demand data from a CSV file.

    Expected columns:
        timestamp: date and time of the observation
        count: number of patients

    Returns:
        Cleaned DataFrame with timestamp and count.
    """

    df = pd.read_csv(file_path)

    # Check required columns
    required_columns = [timestamp_col, count_col]

    for column in required_columns:
        if column not in df.columns:
            raise ValueError(
                f"Missing required column: {column}"
            )

    # Keep only timestamp and patient count
    df = df[[timestamp_col, count_col]].copy()

    # Convert timestamp into datetime format
    df[timestamp_col] = pd.to_datetime(
        df[timestamp_col],
        errors="coerce"
    )

    # Reject invalid timestamps
    if df[timestamp_col].isna().any():
        raise ValueError(
            "Invalid timestamps found in the dataset."
        )

    # Convert patient counts into numeric values
    df[count_col] = pd.to_numeric(
        df[count_col],
        errors="coerce"
    )

    if df[count_col].isna().any():
        raise ValueError(
            "Invalid patient counts found."
        )

    if (df[count_col] < 0).any():
        raise ValueError(
            "Patient counts cannot be negative."
        )

    # Remove duplicate rows
    df = df.drop_duplicates()

    # Sort observations chronologically
    df = df.sort_values(timestamp_col)

    # Handle duplicate timestamps by keeping the first observation
    df = df.drop_duplicates(
        subset=[timestamp_col],
        keep="first"
    )

    df = df.rename(
        columns={
            timestamp_col: "timestamp",
            count_col: "count"
        }
    )
    return df.reset_index(drop=True)

def preprocess_hourly_data(df):
    """
    Preprocess hourly ED patient arrival data.

    - Sort timestamps
    - Fill missing hours with zero when the gap is
      no longer than one day
    - Flag gaps longer than one day
    - Generate calendar features

    Returns:
        cleaned DataFrame
        list of large gaps
    """

    df = df.copy()
    df["timestamp"] = pd.to_datetime(df["timestamp"])
    df = df.sort_values("timestamp")
    df = df.set_index("timestamp")

    # Ensure hourly timestamps
    if not (df.index.minute == 0).all():
        raise ValueError(
            "Hourly timestamps must be aligned to the hour."
        )
    if df.index.has_duplicates:
        raise ValueError(
            "Duplicate timestamps must be resolved first."
        )

    # Create complete hourly index
    full_index = pd.date_range(
        start=df.index.min(),
        end=df.index.max(),
        freq="h"
    )

    # Identify missing timestamps
    missing_timestamps = full_index.difference(df.index)

    # Find consecutive missing-hour groups
    missing_series = pd.Series(
        missing_timestamps,
        index=missing_timestamps
    )

    large_gaps = []

    if len(missing_timestamps) > 0:
        groups = (
            missing_series.diff()
            .ne(pd.Timedelta(hours=1))
            .cumsum()
        )
        for _, group in missing_series.groupby(groups):
            gap_start = group.iloc[0]
            gap_end = group.iloc[-1]
            missing_hours = len(group)
            if missing_hours > 24:
                large_gaps.append({
                    "start": gap_start,
                    "end": gap_end,
                    "missing_hours": missing_hours
                })

    # Reindex to include missing timestamps
    df = df.reindex(full_index)

    # Fill only missing hours that are not part of large gaps
    for timestamp in missing_timestamps:

        # Find the consecutive missing group containing this timestamp
        previous = timestamp - pd.Timedelta(hours=1)
        following = timestamp + pd.Timedelta(hours=1)

        # Determine whether this timestamp belongs to a large gap
        belongs_to_large_gap = any(
            gap["start"] <= timestamp <= gap["end"]
            for gap in large_gaps
        )

        if not belongs_to_large_gap:
            df.loc[timestamp, "count"] = 0

    df.index.name = "timestamp"
    df = df.reset_index()

    # Calendar features for Gradient Boosting
    df["hour"] = df["timestamp"].dt.hour
    df["weekday"] = df["timestamp"].dt.dayofweek
    df["month"] = df["timestamp"].dt.month

    # Use an existing public-holiday flag if provided.
    # Otherwise default to False until holiday dates are supplied.
    if "is_public_holiday" not in df.columns:
        df["is_public_holiday"] = False

    df["is_public_holiday"] = (
        df["is_public_holiday"]
        .fillna(False)
        .astype(bool)
    )
    return df, large_gaps


def preprocess_daily_icu_data(df):
    """
    Prepare ICU daily census data.
    Expected columns:
        date
        census
    Returns:
        Cleaned daily ICU census DataFrame.
    """

    df = df.copy()

    df["date"] = pd.to_datetime(
        df["date"],
        errors="coerce"
    )

    if df["date"].isna().any():
        raise ValueError("Invalid ICU dates found.")

    df["census"] = pd.to_numeric(
        df["census"],
        errors="coerce"
    )

    if df["census"].isna().any():
        raise ValueError("Invalid ICU census values.")

    if (df["census"] < 0).any():
        raise ValueError("ICU occupancy cannot be negative.")

    df = df.drop_duplicates()

    df = df.drop_duplicates(
        subset=["date"],
        keep="first"
    )

    df = df.sort_values("date")

    return df.reset_index(drop=True)
