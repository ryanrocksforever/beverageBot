#!/usr/bin/env python3
"""Generate ArUco markers for BevBot locations and export to PDF."""

import cv2
import numpy as np
from typing import Dict, Tuple
import argparse
import logging
from reportlab.pdfgen import canvas
from reportlab.lib.pagesizes import letter
from reportlab.lib.units import inch
from reportlab.lib import colors
import tempfile
import os

# Setup logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

# BevBot location mappings
BEVBOT_LOCATIONS = {
    1: "Home Base/Resting position",
    2: "Fridge side/Open position", 
    3: "Fridge pickup/Close in position",
    4: "Couch/Dropoff 1",
    5: "Outside/Dropoff 2"
}

# ArUco dictionary mapping
ARUCO_DICTS = {
    "DICT_4X4_50": cv2.aruco.DICT_4X4_50,
    "DICT_4X4_100": cv2.aruco.DICT_4X4_100,
    "DICT_4X4_250": cv2.aruco.DICT_4X4_250,
    "DICT_4X4_1000": cv2.aruco.DICT_4X4_1000,
    "DICT_5X5_50": cv2.aruco.DICT_5X5_50,
    "DICT_5X5_100": cv2.aruco.DICT_5X5_100,
    "DICT_5X5_250": cv2.aruco.DICT_5X5_250,
    "DICT_5X5_1000": cv2.aruco.DICT_5X5_1000,
    "DICT_6X6_50": cv2.aruco.DICT_6X6_50,
    "DICT_6X6_100": cv2.aruco.DICT_6X6_100,
    "DICT_6X6_250": cv2.aruco.DICT_6X6_250,
    "DICT_6X6_1000": cv2.aruco.DICT_6X6_1000,
}

class ArucoMarkerGenerator:
    """Generate ArUco markers for BevBot locations."""
    
    def __init__(self, dict_name: str = "DICT_4X4_50", marker_size_pixels: int = 200):
        """Initialize ArUco marker generator.
        
        Args:
            dict_name: ArUco dictionary name
            marker_size_pixels: Size of each marker in pixels
        """
        if dict_name not in ARUCO_DICTS:
            raise ValueError(f"Unknown ArUco dictionary: {dict_name}. Available: {list(ARUCO_DICTS.keys())}")
            
        self.dict_name = dict_name
        # Use newer OpenCV ArUco API (4.7+) with fallback to older API
        try:
            # New API (OpenCV 4.7+)
            self.aruco_dict = cv2.aruco.getPredefinedDictionary(ARUCO_DICTS[dict_name])
        except AttributeError:
            # Fallback to older API
            self.aruco_dict = cv2.aruco.Dictionary_get(ARUCO_DICTS[dict_name])
        self.marker_size_pixels = marker_size_pixels
        
        logger.info(f"ArUco marker generator initialized with {dict_name}")
        
    def generate_marker(self, marker_id: int) -> np.ndarray:
        """Generate a single ArUco marker.
        
        Args:
            marker_id: ID of the marker to generate
            
        Returns:
            Marker image as numpy array (grayscale)
        """
        marker_img = np.zeros((self.marker_size_pixels, self.marker_size_pixels), dtype=np.uint8)
        marker_img = cv2.aruco.drawMarker(self.aruco_dict, marker_id, self.marker_size_pixels, marker_img, 1)
        return marker_img
        
    def save_marker_png(self, marker_id: int, output_path: str) -> None:
        """Save a single marker as PNG file.
        
        Args:
            marker_id: ID of the marker to generate
            output_path: Path to save the PNG file
        """
        marker_img = self.generate_marker(marker_id)
        cv2.imwrite(output_path, marker_img)
        logger.info(f"Marker {marker_id} saved to {output_path}")
        
    def generate_pdf(self, output_path: str, 
                     marker_size_inches: float = 2.0,
                     include_border: bool = True) -> None:
        """Generate PDF with all BevBot location markers.
        
        Args:
            output_path: Path to save the PDF file
            marker_size_inches: Size of each marker in inches
            include_border: Add border around markers for easier cutting
        """
        # Create PDF canvas
        page_width, page_height = letter  # 8.5 x 11 inches
        c = canvas.Canvas(output_path, pagesize=letter)
        
        # Calculate layout
        markers_per_row = 2
        markers_per_col = 3
        
        # Calculate spacing
        usable_width = page_width - 1.0 * inch  # 0.5 inch margin on each side
        usable_height = page_height - 1.5 * inch  # 0.75 inch margin top/bottom
        
        marker_spacing_x = usable_width / markers_per_row
        marker_spacing_y = usable_height / markers_per_col
        
        # Convert marker size to points (72 points per inch)
        marker_size_points = marker_size_inches * 72
        
        # Title
        c.setFont("Helvetica-Bold", 16)
        c.drawString(50, page_height - 50, "BevBot ArUco Markers")
        c.setFont("Helvetica", 10)
        c.drawString(50, page_height - 70, f"Dictionary: {self.dict_name}")
        c.drawString(50, page_height - 85, f"Marker Size: {marker_size_inches}\" x {marker_size_inches}\"")
        
        # Generate and place markers
        for i, (marker_id, location) in enumerate(BEVBOT_LOCATIONS.items()):
            # Calculate position
            row = i // markers_per_row
            col = i % markers_per_row
            
            x = 0.5 * inch + col * marker_spacing_x + (marker_spacing_x - marker_size_points) / 2
            y = page_height - 1.25 * inch - row * marker_spacing_y - marker_size_points
            
            # Generate marker image
            marker_img = self.generate_marker(marker_id)
            
            # Save marker to temporary PNG file
            with tempfile.NamedTemporaryFile(suffix=".png", delete=False) as temp_file:
                temp_path = temp_file.name
                cv2.imwrite(temp_path, marker_img)
                
                # Draw marker on PDF
                c.drawImage(temp_path, x, y, width=marker_size_points, height=marker_size_points)
                
                # Clean up temporary file
                os.unlink(temp_path)
                
            # Add border if requested
            if include_border:
                border_margin = 5  # points
                c.setStrokeColor(colors.black)
                c.setLineWidth(0.5)
                c.rect(x - border_margin, y - border_margin, 
                      marker_size_points + 2 * border_margin, 
                      marker_size_points + 2 * border_margin)
                
            # Add label below marker
            label_y = y - 20
            c.setFont("Helvetica-Bold", 10)
            c.drawString(x, label_y, f"ID: {marker_id}")
            c.setFont("Helvetica", 8)
            
            # Wrap long location names
            location_lines = self._wrap_text(location, 25)
            for j, line in enumerate(location_lines):
                c.drawString(x, label_y - 12 - j * 10, line)
                
        # Add instructions at bottom
        instructions_y = 50
        c.setFont("Helvetica", 9)
        c.drawString(50, instructions_y, "Instructions:")
        c.drawString(70, instructions_y - 15, "1. Print on standard 8.5\" x 11\" paper")
        c.drawString(70, instructions_y - 30, "2. Cut along border lines if present")
        c.drawString(70, instructions_y - 45, "3. Mount markers at corresponding locations")
        
        # Save PDF
        c.save()
        logger.info(f"PDF with {len(BEVBOT_LOCATIONS)} markers saved to {output_path}")
        
    def _wrap_text(self, text: str, max_length: int) -> list:
        """Wrap text to fit within specified length."""
        words = text.split()
        lines = []
        current_line = ""
        
        for word in words:
            if len(current_line + " " + word) <= max_length:
                if current_line:
                    current_line += " " + word
                else:
                    current_line = word
            else:
                if current_line:
                    lines.append(current_line)
                current_line = word
                
        if current_line:
            lines.append(current_line)
            
        return lines

def main():
    """Main function with argument parsing."""
    parser = argparse.ArgumentParser(description="Generate ArUco markers for BevBot locations")
    parser.add_argument("--dict", default="DICT_4X4_50",
                       choices=list(ARUCO_DICTS.keys()),
                       help="ArUco dictionary to use (default: DICT_4X4_50)")
    parser.add_argument("--output", default="bevbot_markers.pdf",
                       help="Output PDF filename (default: bevbot_markers.pdf)")
    parser.add_argument("--marker-size", type=float, default=2.0,
                       help="Marker size in inches (default: 2.0)")
    parser.add_argument("--pixel-size", type=int, default=400,
                       help="Marker resolution in pixels (default: 400)")
    parser.add_argument("--no-border", action="store_true",
                       help="Don't add cutting borders around markers")
    parser.add_argument("--list-locations", action="store_true",
                       help="List all marker locations and exit")
    
    args = parser.parse_args()
    
    # List locations if requested
    if args.list_locations:
        print("BevBot ArUco Marker Locations:")
        print("=" * 40)
        for marker_id, location in BEVBOT_LOCATIONS.items():
            print(f"ID {marker_id:2d}: {location}")
        return
        
    try:
        # Create generator
        generator = ArucoMarkerGenerator(
            dict_name=args.dict,
            marker_size_pixels=args.pixel_size
        )
        
        # Generate PDF
        generator.generate_pdf(
            output_path=args.output,
            marker_size_inches=args.marker_size,
            include_border=not args.no_border
        )
        
        print(f"✓ ArUco markers PDF generated: {args.output}")
        print(f"  Dictionary: {args.dict}")
        print(f"  Marker size: {args.marker_size}\" x {args.marker_size}\"")
        print(f"  Locations: {len(BEVBOT_LOCATIONS)} markers")
        
    except Exception as e:
        logger.error(f"Failed to generate markers: {e}")
        return 1
        
    return 0

if __name__ == "__main__":
    exit(main())