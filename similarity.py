"""
Compare experiment runs using cosine similarity on feature vectors.
"""

import argparse
import json
import os
import sys

import numpy as np
import pandas as pd


GALLERY_PATH = "data/gallery.json"


def extract_vector(df):
    # basically everything i thought was worth comparing between runs
    features = {
        "mean_temp": df["temp_c"].mean(),
        "std_temp": df["temp_c"].std(),
        "min_temp": df["temp_c"].min(),
        "max_temp": df["temp_c"].max(),
        "temp_range": df["temp_c"].max() - df["temp_c"].min(),

        "mean_rh": df["humidity"].mean(),
        "std_rh": df["humidity"].std(),
        "min_rh": df["humidity"].min(),
        "max_rh": df["humidity"].max(),
        "rh_range": df["humidity"].max() - df["humidity"].min(),

        "mean_dew_point": df["dew_point"].mean(),
        "mean_dew_margin": df["dew_margin"].mean(),
        "min_dew_margin": df["dew_margin"].min(),

        "mean_temp_volatility": df["temp_volatility"].mean(),
        "max_temp_volatility": df["temp_volatility"].max(),
        "mean_rh_volatility": df["rh_volatility"].mean(),
        "max_rh_volatility": df["rh_volatility"].max(),

        "excursion_count": float(df["excursion"].sum()),
        "excursion_fraction": df["excursion"].mean(),

        "mean_risk": df["risk_score"].mean(),
        "max_risk": df["risk_score"].max(),
        "total_risk_dosage": df["risk_dosage"].iloc[-1],
    }

    return features


def features_to_array(features):
    keys = sorted(features.keys())  # sorted so order is always consistent
    return np.array([features[k] for k in keys]), keys


def cosine_sim(a, b):
    na, nb = np.linalg.norm(a), np.linalg.norm(b)
    if na < 1e-9 or nb < 1e-9:
        return 0.0
    return float(np.dot(a, b) / (na * nb))


def l2_dist(a, b):
    return float(np.linalg.norm(a - b))


def load_gallery():
    if os.path.exists(GALLERY_PATH):
        with open(GALLERY_PATH) as f:
            return json.load(f)
    return []


def save_gallery(gallery):
    os.makedirs(os.path.dirname(GALLERY_PATH) or "data", exist_ok=True)
    with open(GALLERY_PATH, "w") as f:
        json.dump(gallery, f, indent=2)


def register_run(csv_path, label=None):
    df = pd.read_csv(csv_path)
    features = extract_vector(df)

    gallery = load_gallery()

    entry = {
        "label": label or os.path.basename(csv_path),
        "csv_path": csv_path,
        "features": features,
        "n_readings": len(df),
        "duration_s": int(df["elapsed_s"].iloc[-1]),
    }

    for existing in gallery:
        if existing["csv_path"] == csv_path:
            print(f"Already registered: {csv_path}")
            return

    gallery.append(entry)
    save_gallery(gallery)
    print(f"Registered: {label or csv_path}")
    print(f"  Readings: {len(df)}, Duration: {entry['duration_s']}s")
    print(f"  Gallery now has {len(gallery)} run(s)")


def compare_run(csv_path):
    gallery = load_gallery()
    if not gallery:
        print("gallery empty, register some runs first")
        return

    df = pd.read_csv(csv_path)
    query_features = extract_vector(df)
    query_vec, keys = features_to_array(query_features)

    results = []
    for entry in gallery:
        entry_vec, _ = features_to_array(entry["features"])
        sim = cosine_sim(query_vec, entry_vec)
        dist = l2_dist(query_vec, entry_vec)
        results.append((sim, dist, entry))

    results.sort(key=lambda x: x[0], reverse=True)

    print(f"\nComparing: {os.path.basename(csv_path)}")
    print(f"Against {len(gallery)} registered run(s)\n")
    print(f"{'Rank':<6} {'Similarity':<12} {'Distance':<12} {'Label':<30} {'Readings'}")
    print("-" * 78)

    for rank, (sim, dist, entry) in enumerate(results, 1):
        marker = ""
        # these thresholds are kinda arbitrary but they work ok in practice
        if sim > 0.999:
            marker = " << MATCH"
        elif sim > 0.99:
            marker = " << very similar"
        elif sim > 0.95:
            marker = " << similar"

        print(f"  {rank:<4} {sim:<12.4f} {dist:<12.2f} {entry['label']:<30} {entry['n_readings']}{marker}")

    if results:
        best_sim, _, best_entry = results[0]
        if best_sim < 0.999:
            print(f"\n--- Differences from best match ({best_entry['label']}) ---")
            best_features = best_entry["features"]
            diffs = []
            for key in sorted(query_features.keys()):
                qv = query_features[key]
                bv = best_features[key]
                if abs(bv) > 1e-9:
                    pct = abs(qv - bv) / abs(bv) * 100
                else:
                    pct = abs(qv - bv) * 100
                diffs.append((pct, key, qv, bv))

            diffs.sort(reverse=True)
            for pct, key, qv, bv in diffs[:5]:
                print(f"  {key:<25} query={qv:>8.2f}  best={bv:>8.2f}  diff={pct:.1f}%")


def diff_runs(csv_a, csv_b):
    df_a = pd.read_csv(csv_a)
    df_b = pd.read_csv(csv_b)
    feat_a = extract_vector(df_a)
    feat_b = extract_vector(df_b)

    vec_a, keys = features_to_array(feat_a)
    vec_b, _ = features_to_array(feat_b)

    sim = cosine_sim(vec_a, vec_b)
    dist = l2_dist(vec_a, vec_b)

    print(f"\nComparing two runs:")
    print(f"  A: {os.path.basename(csv_a)} ({len(df_a)} readings)")
    print(f"  B: {os.path.basename(csv_b)} ({len(df_b)} readings)")
    print(f"\n  cosine sim: {sim:.4f}  l2 dist: {dist:.2f}")

    print(f"\n{'Feature':<25} {'Run A':>10} {'Run B':>10} {'Diff%':>8}")
    print("-" * 58)

    diffs = []
    for key in sorted(feat_a.keys()):
        va = feat_a[key]
        vb = feat_b[key]
        if abs(vb) > 1e-9:
            pct = abs(va - vb) / abs(vb) * 100
        else:
            pct = abs(va - vb) * 100
        diffs.append((pct, key, va, vb))

    diffs.sort(reverse=True)
    for pct, key, va, vb in diffs:
        print(f"  {key:<25} {va:>8.2f}   {vb:>8.2f}   {pct:>6.1f}%")


def list_gallery():
    gallery = load_gallery()
    if not gallery:
        print("Gallery is empty.")
        return

    print(f"\nRegistered runs ({len(gallery)}):\n")
    print(f"{'#':<4} {'Label':<30} {'Readings':<10} {'Duration':<10} {'Mean T':<8} {'Mean RH':<8} {'Risk'}")
    print("-" * 85)

    for i, entry in enumerate(gallery, 1):
        f = entry["features"]
        print(f"  {i:<2} {entry['label']:<30} {entry['n_readings']:<10} "
              f"{entry['duration_s']:<10} {f['mean_temp']:<8.1f} "
              f"{f['mean_rh']:<8.1f} {f['mean_risk']:.3f}")


def main():
    parser = argparse.ArgumentParser()
    sub = parser.add_subparsers(dest="command")

    reg = sub.add_parser("register")
    reg.add_argument("input")
    reg.add_argument("--label")

    cmp = sub.add_parser("compare")
    cmp.add_argument("input")

    dif = sub.add_parser("diff")
    dif.add_argument("file_a")
    dif.add_argument("file_b")

    sub.add_parser("list")

    args = parser.parse_args()

    if args.command == "register":
        register_run(args.input, args.label)
    elif args.command == "compare":
        compare_run(args.input)
    elif args.command == "diff":
        diff_runs(args.file_a, args.file_b)
    elif args.command == "list":
        list_gallery()
    else:
        parser.print_help()


if __name__ == "__main__":
    main()
