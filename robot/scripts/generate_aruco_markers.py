#!/usr/bin/env python3
"""Generate ArUco markers for printing."""

import cv2
import numpy as np
import argparse
import os

def generate_aruco_marker(marker_id: int, size: int = 200, 
                         dictionary: int = cv2.aruco.DICT_4X4_50):
    """Generate a single ArUco marker.
    
    Args:
        marker_id: ID of the marker to generate
        size: Size of the marker in pixels
        dictionary: ArUco dictionary to use
        
    Returns:
        Marker image as numpy array
    """
    aruco_dict = cv2.aruco.Dictionary_get(dictionary)
    marker_img = np.zeros((size, size), dtype=np.uint8)
    marker_img = cv2.aruco.drawMarker(aruco_dict, marker_id, size, marker_img, 1)
    return marker_img

def create_marker_sheet(marker_ids: list, markers_per_row: int = 3,
                       marker_size: int = 200, padding: int = 50):
    """Create a sheet with multiple markers for printing.
    
    Args:
        marker_ids: List of marker IDs to include
        markers_per_row: Number of markers per row
        marker_size: Size of each marker in pixels
        padding: Padding between markers
        
    Returns:
        Sheet image as numpy array
    """
    num_markers = len(marker_ids)
    num_rows = (num_markers + markers_per_row - 1) // markers_per_row
    
    # Calculate sheet size
    sheet_width = markers_per_row * marker_size + (markers_per_row + 1) * padding
    sheet_height = num_rows * marker_size + (num_rows + 1) * padding
    
    # Create white sheet
    sheet = np.ones((sheet_height, sheet_width), dtype=np.uint8) * 255
    
    # Place markers
    for idx, marker_id in enumerate(marker_ids):
        row = idx // markers_per_row
        col = idx % markers_per_row
        
        # Generate marker
        marker = generate_aruco_marker(marker_id, marker_size)
        
        # Calculate position
        x = col * marker_size + (col + 1) * padding
        y = row * marker_size + (row + 1) * padding
        
        # Place marker on sheet
        sheet[y:y+marker_size, x:x+marker_size] = marker
        
        # Add ID label
        label_y = y + marker_size + 20
        cv2.putText(sheet, f"ID: {marker_id}", (x, label_y),
                   cv2.FONT_HERSHEY_SIMPLEX, 0.6, 0, 2)
    
    return sheet

def main():
    parser = argparse.ArgumentParser(description='Generate ArUco markers for printing')
    parser.add_argument('--ids', type=str, default='0,1,2,3,4,5',
                       help='Comma-separated list of marker IDs (default: 0,1,2,3,4,5)')
    parser.add_argument('--size', type=int, default=200,
                       help='Size of each marker in pixels (default: 200)')
    parser.add_argument('--output', type=str, default='aruco_markers.png',
                       help='Output filename (default: aruco_markers.png)')
    parser.add_argument('--single', action='store_true',
                       help='Generate single markers instead of sheet')
    parser.add_argument('--dict', type=str, default='4X4_50',
                       help='ArUco dictionary (4X4_50, 4X4_100, 5X5_50, etc.)')
    
    args = parser.parse_args()
    
    # Parse marker IDs
    marker_ids = [int(id_str.strip()) for id_str in args.ids.split(',')]
    
    # Get dictionary
    dict_mapping = {
        '4X4_50': cv2.aruco.DICT_4X4_50,
        '4X4_100': cv2.aruco.DICT_4X4_100,
        '4X4_250': cv2.aruco.DICT_4X4_250,
        '4X4_1000': cv2.aruco.DICT_4X4_1000,
        '5X5_50': cv2.aruco.DICT_5X5_50,
        '5X5_100': cv2.aruco.DICT_5X5_100,
        '5X5_250': cv2.aruco.DICT_5X5_250,
        '5X5_1000': cv2.aruco.DICT_5X5_1000,
    }
    
    if args.dict not in dict_mapping:
        print(f"Error: Unknown dictionary {args.dict}")
        print(f"Available: {', '.join(dict_mapping.keys())}")
        return 1
    
    dictionary = dict_mapping[args.dict]
    
    if args.single:
        # Generate individual marker files
        for marker_id in marker_ids:
            marker = generate_aruco_marker(marker_id, args.size, dictionary)
            
            # Add white border for printing
            bordered = cv2.copyMakeBorder(marker, 50, 50, 50, 50,
                                         cv2.BORDER_CONSTANT, value=255)
            
            # Add ID label
            cv2.putText(bordered, f"ArUco ID: {marker_id} ({args.dict})",
                       (60, 30), cv2.FONT_HERSHEY_SIMPLEX, 0.8, 0, 2)
            
            filename = f"aruco_marker_{marker_id}.png"
            cv2.imwrite(filename, bordered)
            print(f"Generated {filename}")
    else:
        # Generate sheet
        sheet = create_marker_sheet(marker_ids, marker_size=args.size)
        
        # Add title
        cv2.putText(sheet, f"ArUco Markers ({args.dict} dictionary)",
                   (50, 30), cv2.FONT_HERSHEY_SIMPLEX, 1, 0, 2)
        
        cv2.imwrite(args.output, sheet)
        print(f"Generated {args.output}")
        print(f"Contains {len(marker_ids)} markers: {marker_ids}")
        print("")
        print("Printing instructions:")
        print("1. Print at 100% scale (no scaling)")
        print("2. For 10cm markers, scale appropriately when printing")
        print("3. Mount on flat, rigid surface for best detection")
    
    return 0

if __name__ == "__main__":
    exit(main())