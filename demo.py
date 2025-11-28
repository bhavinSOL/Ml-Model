import pandas as pd
import numpy as np
import joblib
from sklearn.preprocessing import LabelEncoder
from sklearn.ensemble import RandomForestClassifier
import os

# Ensure models directory exists
os.makedirs("models", exist_ok=True)

# Load your existing dataset
df = pd.read_csv("Crop_recommendation_with_fertilizer.csv")

# Features: soil + crop
X = df.drop("fertilizer_recommendation", axis=1)
y = df["fertilizer_recommendation"]   # Already has detailed NPK info

# Encode crop labels (if string)
if X["label"].dtype == "object":
    crop_encoder = LabelEncoder()
    X["label"] = crop_encoder.fit_transform(X["label"])
    joblib.dump(crop_encoder, "models/crop_encoder.pkl")

# Encode fertilizer labels
fertilizer_encoder = LabelEncoder()
y_encoded = fertilizer_encoder.fit_transform(y)

# Train fertilizer model
fertilizer_model = RandomForestClassifier(n_estimators=200, random_state=42)
fertilizer_model.fit(X, y_encoded)

# Save model + encoder
joblib.dump(fertilizer_model, "models/fertilizer_model.pkl")
joblib.dump(fertilizer_encoder, "models/fertilizer_encoder.pkl")

print("✅ Fertilizer model trained successfully and saved in 'models/'")
