import sys
import os
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from flask import Flask, request, jsonify
import joblib
import numpy as np
import json
import pandas as pd
from sklearn.ensemble import RandomForestClassifier, RandomForestRegressor

app = Flask(__name__)

# Load models and data with proper paths
model_dir = os.path.join(os.path.dirname(__file__), '..', 'models')

try:
    crop_model = joblib.load(os.path.join(model_dir, 'crop_model.pkl'))
    yield_model = joblib.load(os.path.join(model_dir, 'yield_model.pkl'))
    label_encoder = joblib.load(os.path.join(model_dir, 'label_encoder.pkl'))
    
    with open(os.path.join(model_dir, 'ideal_ranges.json'), 'r') as f:
        ideal_ranges = json.load(f)
    
    print("Models loaded successfully!")
except Exception as e:
    print(f"Error loading models: {e}")
    crop_model = None
    yield_model = None
    label_encoder = None
    ideal_ranges = None

# Feature columns
FEATURE_COLUMNS = ['nitrogen', 'phosphorus', 'potassium', 'temperature', 'humidity', 'ph', 'rainfall']

def validate_input_data(data, required_fields):
    """Validate input data"""
    missing_fields = [field for field in required_fields if field not in data]
    if missing_fields:
        return False, f"Missing required fields: {missing_fields}"
    
    try:
        for field in required_fields:
            if field != 'crop':
                float(data[field])
    except (ValueError, TypeError):
        return False, f"Invalid data type for field: {field}"
    
    return True, "Valid"

def categorize_parameter(value, ideal_min, ideal_max, tolerance=0.1):
    """Categorize parameter as LOW, OPTIMAL, or HIGH"""
    range_size = ideal_max - ideal_min
    lower_threshold = ideal_min - (range_size * tolerance)
    upper_threshold = ideal_max + (range_size * tolerance)
    
    if value < lower_threshold:
        return "LOW"
    elif value > upper_threshold:
        return "HIGH"
    else:
        return "OPTIMAL"

@app.route('/', methods=['GET'])
def home():
    """API Home endpoint"""
    return jsonify({
        "message": "Crop Recommendation and Yield Analysis API",
        "version": "1.0.0",
        "endpoints": {
            "/predict-crop": "POST - Predict recommended crops based on soil parameters",
            "/analyze-crop": "POST - Analyze soil parameters for a specific crop",
            "/predict-yield": "POST - Predict yield for a specific crop and soil conditions",
            "/health": "GET - Health check endpoint",
            "/crops": "GET - Get list of available crops"
        }
    })

@app.route('/predict-crop', methods=['POST'])
def predict_crop():
    """Predict recommended crops based on soil parameters"""
    try:
        if crop_model is None:
            return jsonify({"error": "Model not loaded"}), 500
        
        data = request.get_json()
        
        # Validate input
        is_valid, message = validate_input_data(data, FEATURE_COLUMNS)
        if not is_valid:
            return jsonify({"error": message}), 400
        
        # Prepare features
        features = np.array([[
            data['nitrogen'], data['phosphorus'], data['potassium'],
            data['temperature'], data['humidity'], data['ph'], data['rainfall']
        ]])
        
        # Get prediction probabilities
        probabilities = crop_model.predict_proba(features)[0]
        classes = crop_model.classes_
        
        # Sort by probability and get top 3
        sorted_indices = np.argsort(probabilities)[::-1]
        top_3_indices = sorted_indices[:3]
        
        recommended_crops = [classes[i] for i in top_3_indices]
        confidence = [float(probabilities[i]) for i in top_3_indices]
        
        return jsonify({
            "recommended_crops": recommended_crops,
            "confidence": confidence
        })
    
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.route('/analyze-crop', methods=['POST'])
def analyze_crop():
    """Analyze soil parameters for a specific crop"""
    try:
        if ideal_ranges is None:
            return jsonify({"error": "Ideal ranges data not loaded"}), 500
        
        data = request.get_json()
        
        # Validate input
        required_fields = ['crop'] + FEATURE_COLUMNS
        is_valid, message = validate_input_data(data, required_fields)
        if not is_valid:
            return jsonify({"error": message}), 400
        
        crop = data['crop'].lower()
        
        # Check if crop exists in ideal ranges
        if crop not in ideal_ranges:
            available_crops = list(ideal_ranges.keys())
            return jsonify({
                "error": f"Crop '{crop}' not found in database",
                "available_crops": available_crops
            }), 400
        
        crop_ranges = ideal_ranges[crop]
        analysis = {}
        
        # Analyze each parameter
        for feature in FEATURE_COLUMNS:
            value = float(data[feature])
            ideal_min = crop_ranges[feature]['min']
            ideal_max = crop_ranges[feature]['max']
            
            analysis[feature] = categorize_parameter(value, ideal_min, ideal_max)
        
        return jsonify({
            "analysis": analysis,
            "crop": crop,
            "ideal_ranges": crop_ranges
        })
    
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.route('/predict-yield', methods=['POST'])
def predict_yield():
    """Predict yield for a specific crop and soil parameters"""
    try:
        if yield_model is None or label_encoder is None:
            return jsonify({"error": "Yield model not loaded"}), 500
        
        data = request.get_json()
        
        # Validate input
        required_fields = ['crop'] + FEATURE_COLUMNS
        is_valid, message = validate_input_data(data, required_fields)
        if not is_valid:
            return jsonify({"error": message}), 400
        
        crop = data['crop'].lower()
        
        # Check if crop exists in label encoder
        if crop not in label_encoder.classes_:
            available_crops = list(label_encoder.classes_)
            return jsonify({
                "error": f"Crop '{crop}' not found in database",
                "available_crops": available_crops
            }), 400
        
        # Encode crop
        crop_encoded = label_encoder.transform([crop])[0]
        
        # Prepare features (soil parameters + encoded crop)
        features = np.array([[
            data['nitrogen'], data['phosphorus'], data['potassium'],
            data['temperature'], data['humidity'], data['ph'], data['rainfall'],
            crop_encoded
        ]])
        
        # Predict yield
        predicted_yield = yield_model.predict(features)[0]
        
        return jsonify({
            "predicted_yield": round(float(predicted_yield), 2),
            "crop": crop,
            "unit": "kg/hectare"
        })
    
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.route('/health', methods=['GET'])
def health_check():
    """Health check endpoint"""
    model_status = {
        "crop_model": crop_model is not None,
        "yield_model": yield_model is not None,
        "label_encoder": label_encoder is not None,
        "ideal_ranges": ideal_ranges is not None
    }
    
    return jsonify({
        "status": "healthy" if all(model_status.values()) else "unhealthy",
        "models": model_status
    })

@app.route('/crops', methods=['GET'])
def get_available_crops():
    """Get list of available crops"""
    if ideal_ranges is None:
        return jsonify({"error": "Data not loaded"}), 500
    
    return jsonify({
        "available_crops": list(ideal_ranges.keys()),
        "total_crops": len(ideal_ranges)
    })

@app.errorhandler(404)
def not_found(error):
    return jsonify({"error": "Endpoint not found"}), 404

@app.errorhandler(405)
def method_not_allowed(error):
    return jsonify({"error": "Method not allowed"}), 405

@app.errorhandler(500)
def internal_error(error):
    return jsonify({"error": "Internal server error"}), 500

# Vercel expects the app to be named 'app'
if __name__ == '__main__':
    app.run(debug=True)