import json
import os
from datetime import datetime

def save_landmark_to_json(handedness, landmarks, label=None, output_path='data/landmarks_data.json'):   
    data_point = {
        "timestamp": datetime.utcnow().isoformat(),
        "handedness": handedness,
        "landmarks": [{"x": lm.x, "y": lm.y, "z": lm.z} for lm in landmarks],
        "label": label or "undefined"
    }

    if os.path.exists(output_path):
        with open(output_path, 'r+', encoding='utf-8') as f:
            try:
                data = json.load(f)
            except json.JSONDecodeError:
                data = []
            data.append(data_point)
            f.seek(0)
            json.dump(data, f, indent=2)
    else:
        with open(output_path, 'w', encoding='utf-8') as f:
            json.dump([data_point], f, indent=2)