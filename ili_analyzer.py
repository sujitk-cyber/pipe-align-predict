import pandas as pd
import numpy as np
import sys

def load_data(filepath):
    """
    Loads ILI data from a CSV file.
    Expects standard columns but handles missing ones gracefully.
    """
    try:
        df = pd.read_csv(filepath)
        # Normalize column names to lowercase/stripped for consistency
        df.columns = [c.strip().lower().replace(' ', '_') for c in df.columns]
        return df
    except Exception as e:
        print(f"Error loading {filepath}: {e}")
        sys.exit(1)

def parse_clock(clock_str):
    """
    Parses clock position string (e.g. "4:30") to degrees (0-360).
    Returns None if parsing fails.
    """
    try:
        if isinstance(clock_str, (int, float)):
             return float(clock_str) % 360 # Assume degrees if number
        
        parts = str(clock_str).split(':')
        if len(parts) == 2:
            h = int(parts[0])
            m = int(parts[1])
            # 12:00 is 0 degrees (top), 3:00 is 90, 6:00 is 180
            return (h % 12) * 30 + (m / 60) * 30
    except:
        pass
    return None

def align_runs(df1, df2):
    """
    Aligns df2 to df1 based on the first common reference point (e.g. Girth Weld).
    Returns the aligned df2 and the calculated offset.
    """
    print("\n--- Alignment Step ---")
    
    # Simple strategy: Align based on the first Girth Weld found in both datasets
    # In a real scenario, you'd match multiple welds.
    
    weld1 = df1[df1['feature_type'].str.contains('weld', case=False, na=False)].iloc[0] if not df1[df1['feature_type'].str.contains('weld', case=False, na=False)].empty else None
    weld2 = df2[df2['feature_type'].str.contains('weld', case=False, na=False)].iloc[0] if not df2[df2['feature_type'].str.contains('weld', case=False, na=False)].empty else None
    
    offset = 0.0
    
    if weld1 is not None and weld2 is not None:
        offset = weld1['distance'] - weld2['distance']
        print(f"Aligning based on first weld found:")
        print(f"  Run 1 Weld @ {weld1['distance']:.2f} ft (ID: {weld1.get('feature_id', '?')})")
        print(f"  Run 2 Weld @ {weld2['distance']:.2f} ft (ID: {weld2.get('feature_id', '?')})")
        print(f"  Calculated Offset (Run1 - Run2): {offset:.4f} ft")
    else:
        print("Warning: Could not find welds in both runs to align. Assuming 0 offset.")

    # Apply offset
    df2_aligned = df2.copy()
    df2_aligned['distance'] = df2_aligned['distance'] + offset
    df2_aligned['original_distance'] = df2['distance'] # Keep original for reference
    
    return df2_aligned, offset

def get_clock_diff(c1, c2):
    """
    Returns the shortest angular difference between two clock positions (degrees).
    """
    d1 = parse_clock(c1)
    d2 = parse_clock(c2)
    
    if d1 is None or d2 is None:
        return 999 # Large diff if unknown
    
    diff = abs(d1 - d2)
    return min(diff, 360 - diff)

def match_anomalies(df1, df2_aligned):
    """
    Matches anomalies between Run 1 and Aligned Run 2.
    """
    print("\n--- Matching Step ---")
    
    matches = []
    unmatched_run1 = []
    
    # Keep track of which Run 2 indices have been matched to avoid duplicates
    matched_indices_run2 = set()
    
    # Configuration
    DIST_THRESHOLD = 10.0 # ft
    CLOCK_THRESHOLD = 30.0 # degrees (~1 hour)
    
    # Filter for anomalies only (exclude welds for growth analysis, usually)
    # But user wants to match everything or just anomalies? 
    # Prompt implies anomalies but mentions "feature matches". 
    # Let's focus on "Metal Loss" and "Dent" generally, or just everything that isn't a weld?
    # For now, let's try to match everything but give preference to same type.
    
    anomalies_run1 = df1.to_dict('records')
    anomalies_run2 = df2_aligned.to_dict('records')
    
    # Add index to run2 records for easy tracking
    for i, rec in enumerate(anomalies_run2):
        rec['_orig_index'] = i

    for f1 in anomalies_run1:
        # Find candidates in Run 2
        candidates = []
        
        for f2 in anomalies_run2:
            if f2['_orig_index'] in matched_indices_run2:
                continue
                
            dist_diff = abs(f1['distance'] - f2['distance'])
            
            if dist_diff > DIST_THRESHOLD:
                continue
            
            # Check orientation (must match ID/OD)
            # Normalize to uppercase and check equality. strict match?
            o1 = str(f1.get('orientation', '')).upper()
            o2 = str(f2.get('orientation', '')).upper()
            if o1 and o2 and o1 != o2:
                continue # Orientation mismatch
                
            # Score match
            # Priority 1: Feature Type Match
            type_match = f1.get('feature_type') == f2.get('feature_type')
            
            # Priority 2: Clock Position Match
            clock_diff = get_clock_diff(f1.get('clock_position'), f2.get('clock_position'))
            
            # Priority 3: Distance Proximity
            
            if clock_diff > CLOCK_THRESHOLD:
                continue
            
            # Simple scoring: lower is better
            # We penalty type mismatch heavily
            type_penalty = 0 if type_match else 100
            
            score = (dist_diff * 1.0) + (clock_diff / 30.0) + type_penalty
            
            candidates.append((score, f2))
        
        if candidates:
            # Pick best match
            candidates.sort(key=lambda x: x[0])
            best_score, best_match = candidates[0]
            
            # Create match record
            matches.append({
                'run1': f1,
                'run2': best_match,
                'score': best_score
            })
            matched_indices_run2.add(best_match['_orig_index'])
            # print(f"Matched {f1.get('feature_id')} with {best_match.get('feature_id')} (Score: {best_score:.2f})")
        else:
            unmatched_run1.append(f1)
            
    # Find unmatched Run 2
    unmatched_run2 = [f2 for f2 in anomalies_run2 if f2['_orig_index'] not in matched_indices_run2]
    
    print(f"Total Matches Found: {len(matches)}")
    print(f"Unmatched in Run 1: {len(unmatched_run1)}")
    print(f"Unmatched in Run 2: {len(unmatched_run2)}")
    
    return matches, unmatched_run1, unmatched_run2

def calculate_growth(matches, years_interval=8.0):
    """
    Calculates growth rates for matched anomalies.
    """
    results = []
    
    for m in matches:
        r1 = m['run1']
        r2 = m['run2']
        
        # Only calculate growth for growing features (Metal Loss)
        # Skip dents or welds for growth calc usually, but calculating delta is harmless
        
        d1 = r1.get('depth_percent', 0) or 0
        d2 = r2.get('depth_percent', 0) or 0
        
        l1 = r1.get('length', 0) or 0
        l2 = r2.get('length', 0) or 0
        
        w1 = r1.get('width', 0) or 0
        w2 = r2.get('width', 0) or 0
        
        growth_depth = (d2 - d1) / years_interval
        growth_length = (l2 - l1) / years_interval
        growth_width = (w2 - w1) / years_interval
        
        results.append({
            'feature_id_run1': r1.get('feature_id'),
            'feature_id_run2': r2.get('feature_id'),
            'distance_run1': r1.get('distance'),
            'distance_run2_aligned': r2.get('distance'),
            'feature_type': r1.get('feature_type'),
            'depth_run1': d1,
            'depth_run2': d2,
            'depth_growth_rate_per_year': round(growth_depth, 3),
            'length_growth_rate_per_year': round(growth_length, 3),
            'width_growth_rate_per_year': round(growth_width, 3),
            'years_interval': years_interval
        })
        
    return pd.DataFrame(results)

def main():
    print("Starting ILI Analyzer...")
    
    # 1. Load Data
    try:
        df1 = load_data('run1.csv')
        df2 = load_data('run2.csv')
    except Exception:
        print("Could not find run1.csv or run2.csv. Please run generate_test_data.py first.")
        return

    print(f"Loaded Run 1: {len(df1)} rows")
    print(f"Loaded Run 2: {len(df2)} rows")
    
    # 2. Align Runs
    df2_aligned, offset = align_runs(df1, df2)
    
    # 3. Match Anomalies
    matches, unmatched_r1, unmatched_r2 = match_anomalies(df1, df2_aligned)
    
    # 4. Calculate Growth
    # Assuming 8 years interval as per prompt example, or derive from data if dates existed
    growth_df = calculate_growth(matches, years_interval=8.0)
    
    # 5. Output Results
    if not growth_df.empty:
        growth_df.to_csv('matched_anomalies.csv', index=False)
        print("Saved matched_anomalies.csv")
        
        # Print sample
        print("\nSample Matched Output:")
        print(growth_df[['feature_id_run1', 'feature_id_run2', 'depth_run1', 'depth_run2', 'depth_growth_rate_per_year']].head())
    
    if unmatched_r1:
        pd.DataFrame(unmatched_r1).to_csv('unmatched_run1.csv', index=False)
        print(f"Saved unmatched_run1.csv ({len(unmatched_r1)} records)")
        
    if unmatched_r2:
        # Remove internal helper key
        for r in unmatched_r2:
            if '_orig_index' in r: del r['_orig_index']
            
        pd.DataFrame(unmatched_r2).to_csv('unmatched_run2.csv', index=False)
        print(f"Saved unmatched_run2.csv ({len(unmatched_r2)} records)")

if __name__ == "__main__":
    main()
