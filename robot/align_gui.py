#!/usr/bin/env python3
"""
GUI for Simple ArUco Alignment Tool
Optimized for Raspberry Pi 5 with touchscreen support
"""

import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'src'))

import tkinter as tk
from tkinter import ttk, messagebox
import cv2
import numpy as np
import time
import json
import threading
from PIL import Image, ImageTk
from dataclasses import dataclass, asdict
from typing import Optional, Dict, Tuple
import queue

# Import alignment components from align_simple.py
from align_simple import SimpleArUcoDetector, AlignConfig, SimpleAligner, HARDWARE_AVAILABLE

class AlignmentGUI:
    """GUI for ArUco marker alignment."""
    
    def __init__(self, root):
        self.root = root
        self.root.title("BevBot ArUco Alignment")
        
        # Set window size (good for Pi touchscreen)
        self.root.geometry("800x480")
        
        # State
        self.aligner = None
        self.is_aligning = False
        self.is_searching = False
        self.alignment_thread = None
        self.frame_queue = queue.Queue(maxsize=2)
        self.running = True
        self.current_markers = {}
        
        # Configuration
        self.config = AlignConfig()
        
        # Saved positions
        self.saved_positions = self.load_positions()
        
        # Setup GUI
        self.setup_gui()
        
        # Initialize aligner
        self.init_aligner()
        
        # Start video feed
        self.update_video()
        
        # Handle window closing
        self.root.protocol("WM_DELETE_WINDOW", self.on_closing)
        
    def setup_gui(self):
        """Setup GUI components."""
        # Use notebook for tabs
        notebook = ttk.Notebook(self.root)
        notebook.pack(fill='both', expand=True)
        
        # Tab 1: Main Control
        self.control_tab = ttk.Frame(notebook)
        notebook.add(self.control_tab, text="Control")
        self.setup_control_tab()
        
        # Tab 2: Settings
        self.settings_tab = ttk.Frame(notebook)
        notebook.add(self.settings_tab, text="Settings")
        self.setup_settings_tab()
        
        # Tab 3: Positions
        self.positions_tab = ttk.Frame(notebook)
        notebook.add(self.positions_tab, text="Positions")
        self.setup_positions_tab()
        
    def setup_control_tab(self):
        """Setup main control tab."""
        # Main container
        main_frame = ttk.Frame(self.control_tab)
        main_frame.pack(fill='both', expand=True, padx=5, pady=5)
        
        # Left side - Video feed
        video_frame = ttk.LabelFrame(main_frame, text="Camera Feed")
        video_frame.pack(side='left', fill='both', expand=True, padx=(0, 5))
        
        # Video label (640x360 for performance)
        self.video_label = ttk.Label(video_frame)
        self.video_label.pack(padx=5, pady=5)
        
        # Marker info overlay
        self.marker_info_label = ttk.Label(video_frame, text="No markers detected", 
                                          font=('Arial', 10))
        self.marker_info_label.pack()
        
        # Right side - Controls
        control_frame = ttk.Frame(main_frame)
        control_frame.pack(side='right', fill='y', padx=(5, 0))
        
        # Target selection
        target_frame = ttk.LabelFrame(control_frame, text="Target")
        target_frame.pack(fill='x', pady=(0, 10))
        
        ttk.Label(target_frame, text="Marker ID:").grid(row=0, column=0, sticky='w', padx=5)
        self.marker_id_var = tk.IntVar(value=1)
        marker_spin = ttk.Spinbox(target_frame, from_=0, to=50, 
                                  textvariable=self.marker_id_var, width=10)
        marker_spin.grid(row=0, column=1, padx=5, pady=5)
        
        ttk.Label(target_frame, text="Distance (cm):").grid(row=1, column=0, sticky='w', padx=5)
        self.distance_var = tk.IntVar(value=30)
        distance_scale = ttk.Scale(target_frame, from_=10, to=100, 
                                   variable=self.distance_var, orient='horizontal', length=150)
        distance_scale.grid(row=1, column=1, padx=5, pady=5)
        self.distance_label = ttk.Label(target_frame, text="30 cm")
        self.distance_label.grid(row=1, column=2, padx=5)
        distance_scale.config(command=lambda v: self.distance_label.config(text=f"{int(float(v))} cm"))
        
        # Quick distance buttons
        quick_frame = ttk.Frame(target_frame)
        quick_frame.grid(row=2, column=0, columnspan=3, pady=5)
        
        for dist in [20, 30, 50, 75]:
            ttk.Button(quick_frame, text=f"{dist}cm", width=6,
                      command=lambda d=dist: self.distance_var.set(d)).pack(side='left', padx=2)
        
        # Control buttons
        button_frame = ttk.LabelFrame(control_frame, text="Actions")
        button_frame.pack(fill='x', pady=(0, 10))
        
        self.align_btn = ttk.Button(button_frame, text="Start Alignment", 
                                   command=self.toggle_alignment)
        self.align_btn.pack(fill='x', padx=5, pady=5)
        
        self.search_btn = ttk.Button(button_frame, text="Search Marker", 
                                    command=self.search_marker)
        self.search_btn.pack(fill='x', padx=5, pady=5)
        
        ttk.Button(button_frame, text="STOP", command=self.emergency_stop,
                  style='Emergency.TButton').pack(fill='x', padx=5, pady=5)
        
        # Style for emergency button
        style = ttk.Style()
        style.configure('Emergency.TButton', foreground='red')
        
        # Status frame
        status_frame = ttk.LabelFrame(control_frame, text="Status")
        status_frame.pack(fill='both', expand=True)
        
        self.status_text = tk.Text(status_frame, height=8, width=30, font=('Arial', 9))
        self.status_text.pack(padx=5, pady=5)
        
        # Progress
        self.progress = ttk.Progressbar(control_frame, mode='indeterminate')
        self.progress.pack(fill='x', pady=5)
        
    def setup_settings_tab(self):
        """Setup settings tab."""
        settings_frame = ttk.Frame(self.settings_tab)
        settings_frame.pack(fill='both', expand=True, padx=10, pady=10)
        
        # Control parameters
        control_frame = ttk.LabelFrame(settings_frame, text="Control Parameters")
        control_frame.pack(fill='x', pady=(0, 10))
        
        # Tolerances
        ttk.Label(control_frame, text="X Tolerance (pixels):").grid(row=0, column=0, sticky='w', padx=5)
        self.tol_x_var = tk.IntVar(value=self.config.tolerance_x_pixels)
        ttk.Scale(control_frame, from_=5, to=50, variable=self.tol_x_var, 
                 orient='horizontal', length=150).grid(row=0, column=1, padx=5, pady=5)
        self.tol_x_label = ttk.Label(control_frame, text=f"{self.config.tolerance_x_pixels} px")
        self.tol_x_label.grid(row=0, column=2)
        self.tol_x_var.trace('w', lambda *args: self.tol_x_label.config(text=f"{self.tol_x_var.get()} px"))
        
        ttk.Label(control_frame, text="Distance Tolerance (cm):").grid(row=1, column=0, sticky='w', padx=5)
        self.tol_dist_var = tk.IntVar(value=int(self.config.tolerance_distance_cm))
        ttk.Scale(control_frame, from_=1, to=10, variable=self.tol_dist_var,
                 orient='horizontal', length=150).grid(row=1, column=1, padx=5, pady=5)
        self.tol_dist_label = ttk.Label(control_frame, text=f"{self.config.tolerance_distance_cm} cm")
        self.tol_dist_label.grid(row=1, column=2)
        self.tol_dist_var.trace('w', lambda *args: self.tol_dist_label.config(text=f"{self.tol_dist_var.get()} cm"))
        
        # Speed settings
        speed_frame = ttk.LabelFrame(settings_frame, text="Speed Settings")
        speed_frame.pack(fill='x', pady=(0, 10))
        
        ttk.Label(speed_frame, text="Max Speed:").grid(row=0, column=0, sticky='w', padx=5)
        self.max_speed_var = tk.IntVar(value=self.config.max_speed)
        ttk.Scale(speed_frame, from_=20, to=60, variable=self.max_speed_var,
                 orient='horizontal', length=150).grid(row=0, column=1, padx=5, pady=5)
        ttk.Label(speed_frame, textvariable=self.max_speed_var).grid(row=0, column=2)
        
        ttk.Label(speed_frame, text="Search Speed:").grid(row=1, column=0, sticky='w', padx=5)
        self.search_speed_var = tk.IntVar(value=self.config.search_speed)
        ttk.Scale(speed_frame, from_=10, to=40, variable=self.search_speed_var,
                 orient='horizontal', length=150).grid(row=1, column=1, padx=5, pady=5)
        ttk.Label(speed_frame, textvariable=self.search_speed_var).grid(row=1, column=2)
        
        # PID gains
        pid_frame = ttk.LabelFrame(settings_frame, text="PID Gains")
        pid_frame.pack(fill='x', pady=(0, 10))
        
        ttk.Label(pid_frame, text="X Proportional:").grid(row=0, column=0, sticky='w', padx=5)
        self.kp_x_var = tk.DoubleVar(value=self.config.kp_x)
        ttk.Scale(pid_frame, from_=0.05, to=0.5, variable=self.kp_x_var,
                 orient='horizontal', length=150).grid(row=0, column=1, padx=5, pady=5)
        self.kp_x_label = ttk.Label(pid_frame, text=f"{self.config.kp_x:.2f}")
        self.kp_x_label.grid(row=0, column=2)
        self.kp_x_var.trace('w', lambda *args: self.kp_x_label.config(text=f"{self.kp_x_var.get():.2f}"))
        
        ttk.Label(pid_frame, text="Distance Proportional:").grid(row=1, column=0, sticky='w', padx=5)
        self.kp_dist_var = tk.DoubleVar(value=self.config.kp_distance)
        ttk.Scale(pid_frame, from_=0.5, to=3.0, variable=self.kp_dist_var,
                 orient='horizontal', length=150).grid(row=1, column=1, padx=5, pady=5)
        self.kp_dist_label = ttk.Label(pid_frame, text=f"{self.config.kp_distance:.2f}")
        self.kp_dist_label.grid(row=1, column=2)
        self.kp_dist_var.trace('w', lambda *args: self.kp_dist_label.config(text=f"{self.kp_dist_var.get():.2f}"))
        
        # Apply button
        ttk.Button(settings_frame, text="Apply Settings", 
                  command=self.apply_settings).pack(pady=10)
        
    def setup_positions_tab(self):
        """Setup saved positions tab."""
        positions_frame = ttk.Frame(self.positions_tab)
        positions_frame.pack(fill='both', expand=True, padx=10, pady=10)
        
        # Saved positions list
        list_frame = ttk.LabelFrame(positions_frame, text="Saved Positions")
        list_frame.pack(fill='both', expand=True, pady=(0, 10))
        
        # Listbox with scrollbar
        scrollbar = ttk.Scrollbar(list_frame)
        scrollbar.pack(side='right', fill='y')
        
        self.positions_listbox = tk.Listbox(list_frame, yscrollcommand=scrollbar.set)
        self.positions_listbox.pack(side='left', fill='both', expand=True)
        scrollbar.config(command=self.positions_listbox.yview)
        
        # Buttons
        button_frame = ttk.Frame(positions_frame)
        button_frame.pack(fill='x')
        
        ttk.Button(button_frame, text="Save Current", 
                  command=self.save_current_position).pack(side='left', padx=5)
        ttk.Button(button_frame, text="Load Selected", 
                  command=self.load_selected_position).pack(side='left', padx=5)
        ttk.Button(button_frame, text="Delete Selected", 
                  command=self.delete_selected_position).pack(side='left', padx=5)
        ttk.Button(button_frame, text="Refresh", 
                  command=self.refresh_positions_list).pack(side='left', padx=5)
        
        # Refresh list
        self.refresh_positions_list()
        
    def init_aligner(self):
        """Initialize the aligner."""
        try:
            self.aligner = SimpleAligner(self.config)
            self.update_status("Aligner initialized", "success")
            
            if not HARDWARE_AVAILABLE:
                self.update_status("Running in simulation mode", "warning")
                
        except Exception as e:
            self.update_status(f"Failed to initialize: {e}", "error")
            messagebox.showerror("Initialization Error", 
                               f"Failed to initialize aligner:\n{e}")
            
    def update_video(self):
        """Update video feed."""
        if self.aligner and self.aligner.camera and self.running:
            try:
                # Capture frame
                frame, _ = self.aligner.camera.capture_frame()
                
                if frame is not None:
                    # Detect markers
                    markers = self.aligner.detector.detect_markers(frame)
                    self.current_markers = markers
                    
                    # Draw markers
                    frame = self.aligner.detector.draw_markers(frame, markers)
                    
                    # Draw target crosshair
                    h, w = frame.shape[:2]
                    target_x = int(self.config.target_x_ratio * w)
                    cv2.drawMarker(frame, (target_x, h//2), (0, 255, 0), 
                                  cv2.MARKER_CROSS, 20, 2)
                    
                    # Draw tolerance zone
                    tol_x = self.config.tolerance_x_pixels
                    cv2.rectangle(frame, (target_x - tol_x, h//2 - 50),
                                 (target_x + tol_x, h//2 + 50), (0, 255, 0), 1)
                    
                    # Resize for display (640x360 for performance)
                    display_frame = cv2.resize(frame, (640, 360))
                    
                    # Convert to RGB and create PhotoImage
                    frame_rgb = cv2.cvtColor(display_frame, cv2.COLOR_BGR2RGB)
                    img = Image.fromarray(frame_rgb)
                    photo = ImageTk.PhotoImage(image=img)
                    
                    # Update label
                    self.video_label.config(image=photo)
                    self.video_label.image = photo
                    
                    # Update marker info
                    if markers:
                        info = f"Detected markers: {list(markers.keys())}"
                        target_id = self.marker_id_var.get()
                        if target_id in markers:
                            m = markers[target_id]
                            info += f"\nTarget {target_id}: {m['distance']:.1f}cm"
                    else:
                        info = "No markers detected"
                    self.marker_info_label.config(text=info)
                    
            except Exception as e:
                print(f"Video update error: {e}")
                
        # Schedule next update
        self.root.after(50, self.update_video)  # 20 FPS
        
    def toggle_alignment(self):
        """Start or stop alignment."""
        if self.is_aligning:
            self.stop_alignment()
        else:
            self.start_alignment()
            
    def start_alignment(self):
        """Start alignment process."""
        if not self.aligner:
            messagebox.showerror("Error", "Aligner not initialized")
            return
            
        self.is_aligning = True
        self.align_btn.config(text="Stop Alignment")
        self.progress.start()
        
        # Update config
        self.apply_settings()
        
        # Get target
        marker_id = self.marker_id_var.get()
        self.config.target_distance_cm = float(self.distance_var.get())
        
        # Start alignment in thread
        self.alignment_thread = threading.Thread(
            target=self._alignment_worker,
            args=(marker_id,)
        )
        self.alignment_thread.start()
        
    def _alignment_worker(self, marker_id):
        """Worker thread for alignment."""
        try:
            self.update_status(f"Aligning with marker {marker_id}...", "info")
            success = self.aligner.align_with_marker(marker_id)
            
            if success:
                self.update_status(f"Successfully aligned with marker {marker_id}!", "success")
            else:
                self.update_status(f"Failed to align with marker {marker_id}", "error")
                
        except Exception as e:
            self.update_status(f"Alignment error: {e}", "error")
            
        finally:
            self.is_aligning = False
            self.root.after(0, self._alignment_done)
            
    def _alignment_done(self):
        """Called when alignment is done."""
        self.align_btn.config(text="Start Alignment")
        self.progress.stop()
        
    def stop_alignment(self):
        """Stop alignment."""
        self.is_aligning = False
        if self.aligner:
            self.aligner.stop()
        self.update_status("Alignment stopped", "warning")
        
    def search_marker(self):
        """Search for marker."""
        if self.is_searching or not self.aligner:
            return
            
        self.is_searching = True
        self.search_btn.config(text="Stop Search")
        
        marker_id = self.marker_id_var.get()
        
        def search_worker():
            try:
                self.update_status(f"Searching for marker {marker_id}...", "info")
                found = self.aligner.search_marker(marker_id)
                
                if found:
                    self.update_status(f"Found marker {marker_id}!", "success")
                else:
                    self.update_status(f"Marker {marker_id} not found", "warning")
                    
            finally:
                self.is_searching = False
                self.root.after(0, lambda: self.search_btn.config(text="Search Marker"))
                
        threading.Thread(target=search_worker).start()
        
    def emergency_stop(self):
        """Emergency stop."""
        self.stop_alignment()
        if self.aligner:
            self.aligner.stop()
        self.update_status("EMERGENCY STOP", "error")
        
    def apply_settings(self):
        """Apply settings to config."""
        self.config.tolerance_x_pixels = self.tol_x_var.get()
        self.config.tolerance_distance_cm = float(self.tol_dist_var.get())
        self.config.max_speed = self.max_speed_var.get()
        self.config.search_speed = self.search_speed_var.get()
        self.config.kp_x = self.kp_x_var.get()
        self.config.kp_distance = self.kp_dist_var.get()
        
        if self.aligner:
            self.aligner.config = self.config
            
        self.update_status("Settings applied", "success")
        
    def save_current_position(self):
        """Save current position."""
        marker_id = self.marker_id_var.get()
        
        if marker_id not in self.current_markers:
            messagebox.showwarning("No Marker", f"Marker {marker_id} not visible")
            return
            
        name = f"Position_{marker_id}_{int(time.time())}"
        
        position = {
            'marker_id': marker_id,
            'name': name,
            'distance_cm': self.current_markers[marker_id]['distance'],
            'x_position': self.current_markers[marker_id]['center'][0],
            'timestamp': time.strftime('%Y-%m-%d %H:%M:%S')
        }
        
        self.saved_positions[name] = position
        self.save_positions()
        self.refresh_positions_list()
        self.update_status(f"Saved position: {name}", "success")
        
    def load_selected_position(self):
        """Load selected position."""
        selection = self.positions_listbox.curselection()
        if not selection:
            messagebox.showwarning("No Selection", "Please select a position to load")
            return
            
        name = self.positions_listbox.get(selection[0])
        position = self.saved_positions.get(name)
        
        if position:
            self.marker_id_var.set(position['marker_id'])
            self.distance_var.set(int(position['distance_cm']))
            self.update_status(f"Loaded position: {name}", "success")
            
    def delete_selected_position(self):
        """Delete selected position."""
        selection = self.positions_listbox.curselection()
        if not selection:
            return
            
        name = self.positions_listbox.get(selection[0])
        if name in self.saved_positions:
            del self.saved_positions[name]
            self.save_positions()
            self.refresh_positions_list()
            self.update_status(f"Deleted position: {name}", "info")
            
    def refresh_positions_list(self):
        """Refresh positions listbox."""
        self.positions_listbox.delete(0, tk.END)
        for name in self.saved_positions.keys():
            self.positions_listbox.insert(tk.END, name)
            
    def load_positions(self):
        """Load saved positions from file."""
        try:
            with open('saved_positions_gui.json', 'r') as f:
                return json.load(f)
        except:
            return {}
            
    def save_positions(self):
        """Save positions to file."""
        try:
            with open('saved_positions_gui.json', 'w') as f:
                json.dump(self.saved_positions, f, indent=2)
        except Exception as e:
            print(f"Failed to save positions: {e}")
            
    def update_status(self, message, level="info"):
        """Update status display."""
        timestamp = time.strftime("%H:%M:%S")
        
        # Color coding
        colors = {
            'info': 'black',
            'success': 'green',
            'warning': 'orange',
            'error': 'red'
        }
        
        # Insert message
        self.status_text.insert('1.0', f"[{timestamp}] {message}\n")
        
        # Limit to last 10 messages
        lines = self.status_text.get('1.0', tk.END).split('\n')
        if len(lines) > 11:
            self.status_text.delete('11.0', tk.END)
            
    def on_closing(self):
        """Handle window closing."""
        self.running = False
        self.stop_alignment()
        
        if self.aligner:
            self.aligner.cleanup()
            
        self.root.destroy()

def main():
    """Main entry point."""
    root = tk.Tk()
    app = AlignmentGUI(root)
    root.mainloop()

if __name__ == "__main__":
    main()