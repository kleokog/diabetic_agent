"""
Image analysis for blood sugar charts using computer vision
"""

import cv2
import numpy as np
import pytesseract
import easyocr
from PIL import Image
import re
from datetime import datetime, timedelta
from typing import List, Dict, Tuple, Optional
import matplotlib.pyplot as plt
import pandas as pd

from .models import BloodSugarLevel


class BloodSugarChartAnalyzer:
    """Analyzes blood sugar charts from images"""
    
    def __init__(self):
        self.ocr_reader = easyocr.Reader(['en'])
        self.target_range = (70, 180)  # mg/dL - can be customized per user
    
    def extract_blood_sugar_data(self, image_path: str) -> List[BloodSugarLevel]:
        """
        Extract blood sugar data from chart image
        
        Args:
            image_path: Path to the blood sugar chart image
            
        Returns:
            List of BloodSugarLevel objects
        """
        # Load and preprocess image
        image = cv2.imread(image_path)
        if image is None:
            raise ValueError(f"Could not load image from {image_path}")
        
        # Preprocess image for better OCR
        processed_image = self._preprocess_image(image)
        
        # Extract text using OCR
        text_data = self._extract_text(processed_image)
        
        # Parse blood sugar values and timestamps
        blood_sugar_data = self._parse_blood_sugar_data(text_data)
        
        return blood_sugar_data
    
    def _preprocess_image(self, image: np.ndarray) -> np.ndarray:
        """Preprocess image for better OCR results"""
        # Convert to grayscale
        gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)
        
        # Apply Gaussian blur to reduce noise
        blurred = cv2.GaussianBlur(gray, (5, 5), 0)
        
        # Apply adaptive thresholding
        thresh = cv2.adaptiveThreshold(
            blurred, 255, cv2.ADAPTIVE_THRESH_GAUSSIAN_C, cv2.THRESH_BINARY, 11, 2
        )
        
        # Morphological operations to clean up
        kernel = np.ones((2, 2), np.uint8)
        cleaned = cv2.morphologyEx(thresh, cv2.MORPH_CLOSE, kernel)
        
        return cleaned
    
    def _extract_text(self, image: np.ndarray) -> str:
        """Extract text from image using OCR"""
        # Use EasyOCR for better accuracy
        results = self.ocr_reader.readtext(image)
        
        # Combine all text
        text = " ".join([result[1] for result in results])
        
        return text
    
    def _parse_blood_sugar_data(self, text: str) -> List[BloodSugarLevel]:
        """Parse blood sugar data from extracted text"""
        blood_sugar_data = []
        
        # Regular expressions for different patterns
        patterns = [
            r'(\d{1,2}:\d{2})\s*(\d{2,3})',  # Time:Value format
            r'(\d{1,2}/\d{1,2})\s*(\d{2,3})',  # Date:Value format
            r'(\d{2,3})\s*mg/dl',  # Value mg/dl format
            r'(\d{2,3})\s*mg/dL',  # Value mg/dL format
        ]
        
        # Extract timestamps and values
        for pattern in patterns:
            matches = re.findall(pattern, text, re.IGNORECASE)
            for match in matches:
                if len(match) == 2:
                    timestamp_str, value_str = match
                    try:
                        value = float(value_str)
                        timestamp = self._parse_timestamp(timestamp_str)
                        
                        if 50 <= value <= 500:  # Reasonable blood sugar range
                            blood_sugar_data.append(BloodSugarLevel(
                                timestamp=timestamp,
                                value=value,
                                measurement_type="chart_analysis",
                                notes="Extracted from chart image"
                            ))
                    except (ValueError, TypeError):
                        continue
        
        # If no structured data found, try to extract just numbers
        if not blood_sugar_data:
            numbers = re.findall(r'\b(\d{2,3})\b', text)
            for i, number in enumerate(numbers):
                value = float(number)
                if 50 <= value <= 500:
                    # Create timestamp based on current time minus some hours
                    timestamp = datetime.now() - timedelta(hours=i*2)
                    blood_sugar_data.append(BloodSugarLevel(
                        timestamp=timestamp,
                        value=value,
                        measurement_type="chart_analysis",
                        notes="Extracted from chart image"
                    ))
        
        return blood_sugar_data
    
    def _parse_timestamp(self, timestamp_str: str) -> datetime:
        """Parse timestamp from various formats"""
        try:
            # Try HH:MM format
            if ':' in timestamp_str:
                time_parts = timestamp_str.split(':')
                hour = int(time_parts[0])
                minute = int(time_parts[1])
                return datetime.now().replace(hour=hour, minute=minute, second=0, microsecond=0)
            
            # Try MM/DD format
            elif '/' in timestamp_str:
                date_parts = timestamp_str.split('/')
                month = int(date_parts[0])
                day = int(date_parts[1])
                return datetime.now().replace(month=month, day=day, hour=12, minute=0, second=0, microsecond=0)
            
            # Default to current time
            return datetime.now()
            
        except (ValueError, IndexError):
            return datetime.now()
    
    def analyze_chart_patterns(self, blood_sugar_data: List[BloodSugarLevel]) -> Dict[str, any]:
        """Analyze patterns in blood sugar data"""
        if not blood_sugar_data:
            return {"error": "No blood sugar data to analyze"}
        
        # Convert to DataFrame for analysis
        df = pd.DataFrame([{
            'timestamp': bs.timestamp,
            'value': bs.value,
            'hour': bs.timestamp.hour
        } for bs in blood_sugar_data])
        
        analysis = {
            'total_readings': len(blood_sugar_data),
            'average_blood_sugar': df['value'].mean(),
            'min_blood_sugar': df['value'].min(),
            'max_blood_sugar': df['value'].max(),
            'std_deviation': df['value'].std(),
            'time_in_range': self._calculate_time_in_range(df['value']),
            'patterns': self._identify_patterns(df),
            'recommendations': self._generate_recommendations(df)
        }
        
        return analysis
    
    def _calculate_time_in_range(self, values: pd.Series) -> float:
        """Calculate percentage of time in target range"""
        in_range = ((values >= self.target_range[0]) & (values <= self.target_range[1])).sum()
        return (in_range / len(values)) * 100
    
    def _identify_patterns(self, df: pd.DataFrame) -> List[str]:
        """Identify patterns in blood sugar data"""
        patterns = []
        
        # Check for high morning readings
        morning_values = df[df['hour'].between(6, 10)]['value']
        if not morning_values.empty and morning_values.mean() > 140:
            patterns.append("High morning blood sugar (Dawn phenomenon)")
        
        # Check for post-meal spikes
        post_meal_values = df[df['hour'].between(12, 16)]['value']
        if not post_meal_values.empty and post_meal_values.mean() > 180:
            patterns.append("Post-meal blood sugar spikes")
        
        # Check for nighttime lows
        night_values = df[df['hour'].between(22, 6)]['value']
        if not night_values.empty and night_values.mean() < 70:
            patterns.append("Nighttime hypoglycemia")
        
        # Check for high variability
        if df['value'].std() > 50:
            patterns.append("High blood sugar variability")
        
        return patterns
    
    def _generate_recommendations(self, df: pd.DataFrame) -> List[str]:
        """Generate recommendations based on analysis"""
        recommendations = []
        
        avg_bs = df['value'].mean()
        std_bs = df['value'].std()
        
        if avg_bs > 180:
            recommendations.append("Consider adjusting insulin dosage or meal timing")
            recommendations.append("Focus on low-carb meals and regular exercise")
        elif avg_bs < 70:
            recommendations.append("Monitor for hypoglycemia and consider reducing insulin")
            recommendations.append("Keep glucose tablets or snacks available")
        
        if std_bs > 50:
            recommendations.append("Work on consistent meal timing and insulin administration")
            recommendations.append("Consider continuous glucose monitoring")
        
        if df['value'].max() > 300:
            recommendations.append("Seek immediate medical attention for very high readings")
        
        return recommendations
    
    def visualize_blood_sugar_trends(self, blood_sugar_data: List[BloodSugarLevel], 
                                   save_path: Optional[str] = None) -> None:
        """Create visualization of blood sugar trends"""
        if not blood_sugar_data:
            return
        
        # Prepare data
        timestamps = [bs.timestamp for bs in blood_sugar_data]
        values = [bs.value for bs in blood_sugar_data]
        
        # Create plot
        plt.figure(figsize=(12, 6))
        plt.plot(timestamps, values, 'b-o', linewidth=2, markersize=4)
        
        # Add target range
        plt.axhspan(self.target_range[0], self.target_range[1], 
                   alpha=0.3, color='green', label='Target Range')
        
        # Add critical levels
        plt.axhline(y=70, color='red', linestyle='--', alpha=0.7, label='Hypoglycemia')
        plt.axhline(y=180, color='orange', linestyle='--', alpha=0.7, label='Hyperglycemia')
        
        plt.title('Blood Sugar Trends', fontsize=16, fontweight='bold')
        plt.xlabel('Time', fontsize=12)
        plt.ylabel('Blood Sugar (mg/dL)', fontsize=12)
        plt.legend()
        plt.grid(True, alpha=0.3)
        plt.xticks(rotation=45)
        plt.tight_layout()
        
        if save_path:
            plt.savefig(save_path, dpi=300, bbox_inches='tight')
        else:
            plt.show()
        
        plt.close()

