import trimesh
import numpy as np
import os
import shutil
from pathlib import Path
import psutil
import triangle

def process_stl(config):
    """Main processing function that takes a config dictionary"""
    try:
        print("Starting STL processing...")
        
        # Set the triangulation engine explicitly
        trimesh.constants.triangulator = 'triangle'
        
        # Validate height axis
        print("Validating configuration...")
        if config['height_axis'].lower() not in ['x', 'y', 'z']:
            raise ValueError("height_axis must be 'x', 'y', or 'z'")
        
        print(f"Loading STL file: {config['input_file']}")
        mesh = trimesh.load(config['input_file'])
        print(f"STL loaded successfully. Original size: {mesh.bounds}")
        
        print("Calculating scaling factors...")
        # Add more print statements throughout the process
        
        print(f"Memory usage: {psutil.Process().memory_info().rss / 1024 / 1024:.2f} MB")
        
        # Validate height axis
        if config['height_axis'].lower() not in ['x', 'y', 'z']:
            raise ValueError("height_axis must be 'x', 'y', or 'z'")
        
        print(f"Creating output directory...")
        output_dir = get_output_dir(config)
        if os.path.exists(output_dir):
            shutil.rmtree(output_dir)
        os.makedirs(output_dir)
        
        print(f"Loading and scaling model to {config['target_height_feet']} feet along {config['height_axis']}-axis...")
        scaled_model = scale_stl_to_height(config)
        
        print(f"Starting mesh splitting (max size per piece: {get_max_size(config)}mm)...")
        split_mesh(scaled_model, output_dir, config=config)
        print("Splitting complete!")
        
        # Print summary
        piece_count = len([f for f in os.listdir(output_dir) if f.endswith('.stl')])
        print(f"\nSummary:")
        print(f"- Input file: {config['input_file']}")
        print(f"- Target height: {config['target_height_feet']} feet")
        print(f"- Height axis: {config['height_axis']}")
        print(f"- Printer bed size: {config['printer_bed_size']}mm")
        print(f"- Safety margin: {config['safety_margin']}mm")
        print(f"- Total pieces: {piece_count}")
        print(f"- Output directory: {output_dir}")
        
        return output_dir
        
    except Exception as e:
        print(f"Error in process_stl: {str(e)}")
        raise

def get_max_size(config):
    return config['printer_bed_size'] - config['safety_margin']

def get_target_height_mm(config):
    return config['target_height_feet'] * 304.8  # Convert feet to mm

def get_output_dir(config):
    base_name = Path(config['input_file']).stem
    output_dir_name = f"{base_name}_{config['target_height_feet']}ft_{config['height_axis']}_height"
    return os.path.join(config['output_base_dir'], output_dir_name)

def get_axis_index(axis_letter):
    return {'x': 0, 'y': 1, 'z': 2}[axis_letter.lower()]

# Update your existing functions to accept config parameter
def scale_stl_to_height(config):
    mesh = trimesh.load_mesh(config['input_file'])
    height_axis = get_axis_index(config['height_axis'])
    current_height = mesh.bounds[1][height_axis] - mesh.bounds[0][height_axis]
    scale_factor = get_target_height_mm(config) / current_height
    mesh.apply_scale(scale_factor)
    return mesh

# Your existing split_mesh function remains largely the same
def split_mesh(mesh, output_dir, piece_number=0, config=None):
    try:
        # Check if piece fits within build volume
        dims = mesh.bounds[1] - mesh.bounds[0]
        
        # Get max size from config
        max_size = config['printer_bed_size'] - config['safety_margin']
        
        # Only split if a dimension is significantly larger than the max size
        if max(dims) > max_size:
            # Find largest dimension
            axis = np.argmax(dims)
            
            # Calculate cut position
            mid_point = (mesh.bounds[1][axis] + mesh.bounds[0][axis]) / 2
            
            # Create cutting plane
            plane_normal = np.zeros(3)
            plane_normal[axis] = 1
            plane_origin = np.zeros(3)
            plane_origin[axis] = mid_point
            
            # Split the mesh
            first_half = mesh.slice_plane(
                plane_origin=plane_origin,
                plane_normal=plane_normal,
                cap=True
            )
            
            second_half = mesh.slice_plane(
                plane_origin=plane_origin,
                plane_normal=[-x for x in plane_normal],
                cap=True
            )
            
            # Process both halves
            if first_half is not None:
                piece_number = split_mesh(first_half, output_dir, piece_number, config)
            
            if second_half is not None:
                piece_number = split_mesh(second_half, output_dir, piece_number, config)
            
            return piece_number
        else:
            # Save this piece as it's within the target size
            filename = os.path.join(output_dir, f'piece_{piece_number}.stl')
            mesh.export(filename)
            print(f"Saved {filename} with dimensions {dims}")
            return piece_number + 1
            
    except Exception as e:
        print(f"Error in split_mesh: {str(e)}")
        return piece_number + 1

# This allows the script to still run standalone if needed
if __name__ == "__main__":
    # Default configuration for standalone use
    CONFIG = {
        'target_height_feet': 2,
        'printer_bed_size': 300,
        'safety_margin': 5,
        'input_file': "Baby_Yoda_Christmas_Ornament_-_Full.stl",
        'height_axis': 'z',
        'output_base_dir': r"F:\Homebrew\Big Stuff"
    }
    process_stl(CONFIG)
