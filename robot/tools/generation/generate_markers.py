#!/usr/bin/env python3
"""
ArUco Marker Generation Tool
Generates printable ArUco markers for robot navigation
"""

import cv2
import numpy as np
from reportlab.lib.pagesizes import letter, A4
from reportlab.pdfgen import canvas
from reportlab.lib.units import inch, cm
import argparse
import os

def generate_marker(marker_id, size=200, dictionary=cv2.aruco.DICT_4X4_50):
    """Generate a single ArUco marker."""
    aruco_dict = cv2.aruco.Dictionary_get(dictionary)
    marker_image = np.zeros((size, size), dtype=np.uint8)
    marker_image = cv2.aruco.drawMarker(aruco_dict, marker_id, size, marker_image, 1)
    return marker_image

def save_marker_image(marker_id, output_dir="markers", size=200):
    """Save marker as PNG image."""
    os.makedirs(output_dir, exist_ok=True)
    marker = generate_marker(marker_id, size)
    filename = os.path.join(output_dir, f"marker_{marker_id}.png")
    cv2.imwrite(filename, marker)
    print(f"Saved marker {marker_id} to {filename}")
    return filename

def create_marker_pdf(marker_ids, output_file="markers.pdf", marker_size_cm=10):
    """Create PDF with multiple ArUco markers."""
    c = canvas.Canvas(output_file, pagesize=A4)
    width, height = A4
    
    # Calculate marker size in points
    marker_size_pts = marker_size_cm * cm
    padding = 1 * cm
    
    # Calculate grid layout
    markers_per_row = int((width - 2 * padding) / (marker_size_pts + padding))
    markers_per_col = int((height - 2 * padding) / (marker_size_pts + padding))
    
    marker_index = 0
    
    for page in range((len(marker_ids) - 1) // (markers_per_row * markers_per_col) + 1):
        if page > 0:
            c.showPage()
        
        # Draw header
        c.setFont("Helvetica-Bold", 16)
        c.drawString(padding, height - padding, "BevBot ArUco Markers")
        c.setFont("Helvetica", 10)
        c.drawString(padding, height - padding - 20, f"Size: {marker_size_cm}cm x {marker_size_cm}cm")
        
        # Draw markers
        for row in range(markers_per_col):
            for col in range(markers_per_row):
                if marker_index >= len(marker_ids):
                    break
                
                marker_id = marker_ids[marker_index]
                
                # Generate and save marker image
                marker_file = save_marker_image(marker_id, size=500)
                
                # Calculate position
                x = padding + col * (marker_size_pts + padding)
                y = height - padding - 60 - (row + 1) * (marker_size_pts + padding)
                
                # Draw marker
                c.drawImage(marker_file, x, y, marker_size_pts, marker_size_pts)
                
                # Draw marker ID
                c.setFont("Helvetica", 12)
                c.drawString(x, y - 15, f"ID: {marker_id}")
                
                # Draw cutting guides
                c.setStrokeColorRGB(0.8, 0.8, 0.8)
                c.setDash([2, 2])
                c.rect(x - 5, y - 5, marker_size_pts + 10, marker_size_pts + 10)
                c.setDash([])
                
                marker_index += 1
    
    c.save()
    print(f"\nCreated PDF: {output_file}")
    print(f"Total markers: {len(marker_ids)}")
    print(f"Marker size: {marker_size_cm}cm x {marker_size_cm}cm")

def generate_marker_set(preset="navigation"):
    """Generate a preset set of markers."""
    presets = {
        "navigation": {
            "ids": [0, 1, 2, 3, 4, 5, 6, 7, 8, 9],
            "names": ["Home", "Fridge", "Inside Fridge", "Couch", "Kitchen", 
                     "Living Room", "Hallway", "Bedroom", "Bathroom", "Garage"],
            "description": "Basic navigation markers for home robot"
        },
        "beverage": {
            "ids": [1, 2, 3],
            "names": ["Fridge Door", "Inside Fridge", "Couch"],
            "description": "Markers for beverage delivery routine"
        },
        "test": {
            "ids": [0, 1, 2, 3, 4],
            "names": ["Test0", "Test1", "Test2", "Test3", "Test4"],
            "description": "Test markers for development"
        },
        "full": {
            "ids": list(range(20)),
            "names": [f"Marker_{i}" for i in range(20)],
            "description": "Full set of 20 markers"
        }
    }
    
    if preset not in presets:
        print(f"Unknown preset: {preset}")
        print(f"Available presets: {', '.join(presets.keys())}")
        return None
    
    return presets[preset]

def main():
    """Main entry point."""
    parser = argparse.ArgumentParser(description='ArUco Marker Generation Tool')
    parser.add_argument('--ids', type=int, nargs='+',
                       help='Marker IDs to generate')
    parser.add_argument('--preset', type=str, default='navigation',
                       choices=['navigation', 'beverage', 'test', 'full'],
                       help='Use a preset marker set')
    parser.add_argument('--size', type=int, default=10,
                       help='Marker size in centimeters')
    parser.add_argument('--output', type=str, default='markers.pdf',
                       help='Output PDF filename')
    parser.add_argument('--images', action='store_true',
                       help='Also save individual PNG images')
    parser.add_argument('--info', type=str,
                       help='Generate info sheet for preset')
    
    args = parser.parse_args()
    
    # Get marker IDs
    if args.ids:
        marker_ids = args.ids
        print(f"Generating custom markers: {marker_ids}")
    else:
        preset = generate_marker_set(args.preset)
        if not preset:
            return 1
        marker_ids = preset['ids']
        print(f"Generating preset '{args.preset}': {preset['description']}")
        print(f"Markers: {marker_ids}")
    
    # Generate PDF
    create_marker_pdf(marker_ids, args.output, args.size)
    
    # Generate info sheet if requested
    if args.info and args.preset:
        preset = generate_marker_set(args.preset)
        info_file = args.info if args.info.endswith('.txt') else f"{args.info}.txt"
        with open(info_file, 'w') as f:
            f.write(f"BevBot ArUco Marker Set: {args.preset}\n")
            f.write("=" * 50 + "\n\n")
            f.write(f"Description: {preset['description']}\n")
            f.write(f"Marker Size: {args.size}cm x {args.size}cm\n\n")
            f.write("Marker Assignments:\n")
            f.write("-" * 30 + "\n")
            for i, marker_id in enumerate(preset['ids']):
                name = preset['names'][i] if i < len(preset['names']) else f"Marker_{marker_id}"
                f.write(f"ID {marker_id:3d}: {name}\n")
        print(f"Created info sheet: {info_file}")
    
    print("\n✓ Marker generation complete!")
    print("Print the PDF on white paper for best results")
    print("Mount markers at robot camera height when possible")
    
    return 0

if __name__ == "__main__":
    import sys
    sys.exit(main())