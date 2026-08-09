#!/usr/bin/env python3
import os

from flask import Flask, jsonify, render_template, request
from src.exception.exception import CustomException
from src.logging.logger import logging
from src.pipeline.prediction_pipeline import CustomData, PredictionPipeline

app = Flask(__name__)

ARTIFACTS_FOLDER = "model-bundle/latest"  # Path to the folder containing model artifacts

try:
    logging.info("Initializing PredictionPipeline...")
    predictor = PredictionPipeline()
    logging.info("PredictionPipeline initialized successfully")
except CustomException as e:
    logging.error(f"Failed to initialize prediction pipeline: {e}")
    predictor = None


@app.route("/")
def home():
    return render_template("index.html")


@app.route("/health")
def health():
    model_info = {
        "model_loaded": predictor is not None,
        "bundle_dir": predictor.bundle_dir if predictor else None,
        "model_version": predictor.model_version if predictor else None,
        "bundle_exists": os.path.exists(predictor.bundle_dir) if predictor else False,
    }
    if predictor and os.path.exists(predictor.bundle_dir):
        model_info["bundle_files"] = os.listdir(predictor.bundle_dir)
    if predictor and predictor.metrics:
        model_info["metrics"] = predictor.metrics
    return jsonify(model_info)


@app.route("/predict", methods=["POST"])
def predict():
    try:
        if predictor is None:
            return jsonify({"error": "Prediction model not available"}), 500

        form_data = request.form.to_dict()
        input_df = CustomData(form_data, label_encoders=predictor.encoder).get_data_as_dataframe()

        prediction = predictor.predict(input_df)

        return render_template("results.html", prediction=prediction[0], input_data=form_data)
    except CustomException as e:
        logging.error(f"Prediction error: {e}")
        return jsonify({"error": str(e)}), 500


@app.route("/api/predict", methods=["POST"])
def api_predict():
    try:
        if predictor is None:
            return jsonify({"error": "Prediction model not available"}), 500

        data = request.get_json()
        input_df = CustomData(data, label_encoders=predictor.encoder).get_data_as_dataframe()

        prediction = predictor.predict(input_df)

        return jsonify({"prediction": float(prediction[0]), "status": "success"})
    except CustomException as e:
        logging.error(f"API prediction error: {e}")
        return jsonify({"error": str(e)}), 500


if __name__ == "__main__":
    app.run(debug=True, host="0.0.0.0", port=8080)
