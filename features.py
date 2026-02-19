"""
Takes raw sensor CSV and adds derived columns for the visualiser.
"""

import argparse
import sys

import numpy as np
import pandas as pd


# magnus formula constants, looked these up
A, B = 17.27, 237.7

def dew_point(temp_c, rh):
    alpha = (A * temp_c) / (B + temp_c) + np.log(rh / 100.0)
    return (B * alpha) / (A - alpha)


def compute_features(df, window=6):
    df["dew_point"] = dew_point(df["temp_c"], df["humidity"])
    df["dew_margin"] = df["temp_c"] - df["dew_point"]

    # rolling std to see how jumpy readings are
    df["temp_volatility"] = df["temp_c"].rolling(window, min_periods=1).std().fillna(0)
    df["rh_volatility"] = df["humidity"].rolling(window, min_periods=1).std().fillna(0)

    # 60% rh or within 3deg of dew point = bad news
    df["excursion"] = ((df["humidity"] > 60) | (df["dew_margin"] < 3)).astype(int)
    df["risk_score"] = (1.0 / df["dew_margin"].clip(lower=0.5)).clip(upper=2.0)
    df["risk_dosage"] = df["risk_score"].cumsum()  # accumulated over time

    return df


def summarize(df):
    dur = df["elapsed_s"].iloc[-1]
    print(f"\n  {len(df)} readings over {dur}s")
    print(f"  temp:  {df['temp_c'].min():.1f}–{df['temp_c'].max():.1f} °C")
    print(f"  rh:    {df['humidity'].min():.0f}–{df['humidity'].max():.0f}%")
    print(f"  dew margin min: {df['dew_margin'].min():.1f} °C")
    print(f"  excursions: {df['excursion'].sum()}, mean risk: {df['risk_score'].mean():.3f}")
    print()


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("input")
    parser.add_argument("-o", "--output", default=None)
    args = parser.parse_args()

    df = pd.read_csv(args.input)
    if "temp_c" not in df.columns or "humidity" not in df.columns:
        print("need temp_c and humidity columns")
        sys.exit(1)

    df = compute_features(df)
    summarize(df)

    out = args.output or args.input.replace(".csv", "_features.csv")
    df.to_csv(out, index=False)
    print(f"saved to {out}")


if __name__ == "__main__":
    main()
