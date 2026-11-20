
import numpy as np
import pandas as pd

from sklearn.ensemble import GradientBoostingRegressor
from sklearn.metrics import mean_absolute_error

from statsmodels.tsa.statespace.sarimax import SARIMAX


# One week of hourly observations
SEASONAL_PERIOD = 168


def calculate_mae(actual, predicted):
    """
    Calculate Mean Absolute Error.
    """

    return mean_absolute_error(actual, predicted)

def seasonal_naive_forecast(series, test_index):
    """
    Predict patient arrivals using the same hour
    from the previous week.

    168 hours = 7 days * 24 hours.
    """

    predictions = series.shift(SEASONAL_PERIOD)

    return predictions.loc[test_index]

def prepare_calendar_features(df):
    """
    Generate calendar features for Gradient Boosting.
    """

    features = pd.DataFrame(index=df.index)

    features["hour"] = df["timestamp"].dt.hour
    features["weekday"] = df["timestamp"].dt.dayofweek
    features["month"] = df["timestamp"].dt.month

    features["is_public_holiday"] = (
        df["is_public_holiday"].astype(int)
    )

    return features

def forecast_ed(df, test_size=0.20):
    """
    Train and compare ED forecasting models.

    Models:
        1. Seasonal Naive
        2. Seasonal ARIMA
        3. Gradient Boosting

    Uses the latest 20% as test data.

    Returns:
        Dictionary containing:
        - actual values
        - predictions
        - MAE scores
        - selected model
    """

    df = df.copy()

    df["timestamp"] = pd.to_datetime(df["timestamp"])

    df = df.sort_values("timestamp").reset_index(drop=True)

    if len(df) <= SEASONAL_PERIOD * 2:
        raise ValueError(
            "At least two weeks of hourly data are required."
        )

    if df["count"].isna().any():
        raise ValueError(
            "Missing patient counts must be resolved before forecasting."
        )

    if not 0 < test_size < 1:
        raise ValueError("test_size must be between 0 and 1.")

    # Time-ordered 80/20 split
    split_index = int(len(df) * (1 - test_size))

    train = df.iloc[:split_index]
    test = df.iloc[split_index:]

    train_series = train["count"].astype(float)
    test_series = test["count"].astype(float)

    # Use continuous hourly indexing for time-series models
    full_series = pd.Series(
        df["count"].astype(float).values,
        index=pd.DatetimeIndex(df["timestamp"])
    )

    test_index = pd.DatetimeIndex(test["timestamp"])

    predictions = {}
    mae_scores = {}

    # 1. Seasonal Naive
    naive_predictions = seasonal_naive_forecast(
        full_series,
        test_index
    )

    naive_predictions = naive_predictions.clip(lower=0)

    predictions["Seasonal Naive"] = naive_predictions

    mae_scores["Seasonal Naive"] = calculate_mae(
        test_series,
        naive_predictions
    )

    # 2. Seasonal ARIMA
    arima_model = SARIMAX(
        train_series,
        order=(1, 0, 1),
        seasonal_order=(1, 0, 0, SEASONAL_PERIOD),
        enforce_stationarity=False,
        enforce_invertibility=False
    )

    arima_result = arima_model.fit(disp=False)

    arima_predictions = arima_result.forecast(
        steps=len(test)
    )

    arima_predictions = pd.Series(
        np.maximum(arima_predictions.values, 0),
        index=test_index
    )

    predictions["Seasonal ARIMA"] = arima_predictions

    mae_scores["Seasonal ARIMA"] = calculate_mae(
        test_series,
        arima_predictions
    )

    # 3. Gradient Boosting
    X = prepare_calendar_features(df)
    y = df["count"].astype(float)

    X_train = X.iloc[:split_index]
    X_test = X.iloc[split_index:]

    y_train = y.iloc[:split_index]

    gb_model = GradientBoostingRegressor(
        n_estimators=100,
        learning_rate=0.05,
        max_depth=3,
        random_state=42
    )

    gb_model.fit(X_train, y_train)

    gb_predictions = gb_model.predict(X_test)

    gb_predictions = pd.Series(
        np.maximum(gb_predictions, 0),
        index=test_index
    )

    predictions["Gradient Boosting"] = gb_predictions

    mae_scores["Gradient Boosting"] = calculate_mae(
        test_series,
        gb_predictions
    )

    # Compare models
    baseline_mae = mae_scores["Seasonal Naive"]

    # Only adopt a complex model if it beats the baseline
    better_models = {
        name: score
        for name, score in mae_scores.items()
        if name != "Seasonal Naive"
        and score < baseline_mae
    }

    if better_models:
        selected_model = min(
            better_models,
            key=better_models.get
        )
    else:
        selected_model = "Seasonal Naive"

    return {
        "actual": test_series.reset_index(drop=True),
        "predictions": predictions,
        "mae_scores": mae_scores,
        "selected_model": selected_model,
        "baseline_mae": baseline_mae
    }
