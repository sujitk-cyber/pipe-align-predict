import pandas as pd
import numpy as np
import random

def generate_ili_data(filename, start_dist=100.0, end_dist=1000.0, num_anomalies=50, drift=0.0):
    """
    Generates synthetic ILI data for a pipeline run.
    """
    data = []
    
    # Generate some girth welds as reference points
    weld_dist = start_dist
    weld_spacing = 40.0 # ft
    weld_id_counter = 1
    
    while weld_dist < end_dist:
        # Add some random jitter to weld distance for realism, plus systematic drift
        actual_dist = weld_dist + random.uniform(-0.1, 0.1) + drift
        
        data.append({
            'feature_id': f'W-{weld_id_counter}',
            'distance': round(actual_dist, 2),
            'clock_position': '12:00', # Welds often logged at 12:00 or 0
            'feature_type': 'Girth Weld',
            'orientation': 'OD',
            'depth_percent': 0,
            'length': 0,
            'width': 0,
            'wall_thickness': 0.250
        })
        
        weld_id_counter += 1
        weld_dist += weld_spacing

    # Generate anomalies
    for i in range(num_anomalies):
        # Random location
        dist = random.uniform(start_dist, end_dist)
        actual_dist = dist + drift # Apply systematic drift
        
        # Random clock position
        hour = random.randint(1, 12)
        minute = random.choice(['00', '15', '30', '45'])
        clock = f"{hour}:{minute}"
        
        # Feature type
        ftype = random.choice(['External Metal Loss', 'Internal Metal Loss', 'Dent'])
        orientation = 'OD' if 'External' in ftype or 'Dent' in ftype else 'ID'
        
        depth = round(random.uniform(5.0, 40.0), 1)
        length = round(random.uniform(0.5, 5.0), 2)
        width = round(random.uniform(0.5, 5.0), 2)
        
        data.append({
            'feature_id': f'A-{i+1}',
            'distance': round(actual_dist, 2),
            'clock_position': clock,
            'feature_type': ftype,
            'orientation': orientation,
            'depth_percent': depth,
            'length': length,
            'width': width,
            'wall_thickness': 0.250
        })
        
    df = pd.DataFrame(data)
    # Sort by distance
    df = df.sort_values('distance').reset_index(drop=True)
    
    # Save to CSV
    df.to_csv(filename, index=False)
    print(f"Generated {filename} with {len(df)} rows.")

def main():
    # Run 1: Baseline
    generate_ili_data('run1.csv', start_dist=100.0, end_dist=2000.0, num_anomalies=50, drift=0.0)
    
    # Run 2: Follow-up (e.g., 8 years later)
    # Add a systematic drift of +5.5 ft to simulate odometer error/wheel slippage
    # Modifying the 'drift' parameter effectively shifts all distances
    # Also we will assume some corrosion growth, but for simplicity in generation, 
    # we'll just generate fresh random anomalies for now. 
    # To truly test matching, we ideally want *some* persistent anomalies.
    
    # Let's manually create Run 2 based on Run 1 to ensure matches exist
    df1 = pd.read_csv('run1.csv')
    
    run2_data = []
    
    drift = 5.5 # systematic shift
    growth_years = 8.0
    
    for _, row in df1.iterrows():
        # Keep Girth Welds
        if row['feature_type'] == 'Girth Weld':
             new_row = row.to_dict()
             new_row['distance'] = row['distance'] + drift + random.uniform(-0.05, 0.05)
             new_row['feature_id'] = row['feature_id'].replace('W-', 'W2-') # New ID convention for Run 2
             run2_data.append(new_row)
             continue
             
        # For anomalies, let's keep 70% of them, delete 30% (repaired or missed), and add some new ones
        if random.random() < 0.7:
            new_row = row.to_dict()
            # Distance drift + measurement error
            new_row['distance'] = row['distance'] + drift + random.uniform(-0.5, 0.5)
            
            # Growth
            if 'Metal Loss' in row['feature_type']:
                growth = random.uniform(0.0, 10.0) # 0 to 10% growth
                new_row['depth_percent'] = min(99, row['depth_percent'] + growth)
                new_row['length'] += random.uniform(0, 0.5)
                new_row['width'] += random.uniform(0, 0.5)
                
            new_row['feature_id'] =  f"B-{random.randint(1000, 9999)}" # New IDs
            run2_data.append(new_row)
            
    # Add some NEW anomalies in Run 2
    for i in range(15):
        dist = random.uniform(100.0, 2000.0) + drift
        clock = f"{random.randint(1,12)}:00"
        run2_data.append({
            'feature_id': f'New-{i}',
            'distance': round(dist, 2),
            'clock_position': clock,
            'feature_type': 'External Metal Loss',
            'orientation': 'OD',
            'depth_percent': round(random.uniform(10, 20), 1),
            'length': 1.0,
            'width': 1.0,
            'wall_thickness': 0.250
        })

    df2 = pd.DataFrame(run2_data)
    df2 = df2.sort_values('distance').reset_index(drop=True)
    df2.to_csv('run2.csv', index=False)
    print(f"Generated run2.csv with {len(df2)} rows (derived from run1 with drift and growth).")

if __name__ == "__main__":
    main()
