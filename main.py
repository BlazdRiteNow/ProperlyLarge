import trimesh
import numpy as np
import os
import shutil
from pathlib import Path

# Configuration
CONFIG = {
    'target_height_feet': 2,    # Desired height in feet
    'printer_bed_size': 300,    # Printer bed size in mm
    'safety_margin': 0,         # Safety margin in mm
    'input_file': r"E:\iCloud Files\iCloudDrive\3D Printer\Things\Monkey_Butler_Ring_Holder_3703834\files\MonkeyButler.stl",
    'height_axis': 'z',         # Which axis to apply height scaling to ('x', 'y', or 'z')
    'output_base_dir': r"F:\Homebrew\Big Stuff"  # Base directory for all outputs
}

def get_max_size():
    return CONFIG['printer_bed_size'] - CONFIG['safety_margin']

def get_target_height_mm():
    return CONFIG['target_height_feet'] * 304.8  # Convert feet to mm

def get_output_dir():
    base_name = Path(CONFIG['input_file']).stem
    output_dir_name = f"{base_name}_{CONFIG['target_height_feet']}ft_{CONFIG['height_axis']}_height"
    return os.path.join(CONFIG['output_base_dir'], output_dir_name)

def get_axis_index(axis_letter):
    return {'x': 0, 'y': 1, 'z': 2}[axis_letter.lower()]

def scale_stl_to_height(input_file, target_height_mm):
    mesh = trimesh.load_mesh(input_file)
    
    # Get the height along the specified axis
    height_axis = get_axis_index(CONFIG['height_axis'])
    current_height = mesh.bounds[1][height_axis] - mesh.bounds[0][height_axis]
    
    # Calculate and apply scale factor
    scale_factor = target_height_mm / current_height
    mesh.apply_scale(scale_factor)
    return mesh

def split_mesh(mesh, output_dir, piece_number=0, max_size=None):
    if max_size is None:
        max_size = get_max_size()
        
    try:
        # Check if piece fits within build volume
        dims = mesh.bounds[1] - mesh.bounds[0]
        
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
                piece_number = split_mesh(first_half, output_dir, piece_number)
            
            if second_half is not None:
                piece_number = split_mesh(second_half, output_dir, piece_number)
            
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

def main():
    try:
        # Validate height axis
        if CONFIG['height_axis'].lower() not in ['x', 'y', 'z']:
            raise ValueError("height_axis must be 'x', 'y', or 'z'")
        
        # Create output directory
        output_dir = get_output_dir()
        if os.path.exists(output_dir):
            shutil.rmtree(output_dir)
        os.makedirs(output_dir)
        
        # Load and scale model
        print(f"Loading and scaling model to {CONFIG['target_height_feet']} feet along {CONFIG['height_axis']}-axis...")
        scaled_model = scale_stl_to_height(CONFIG['input_file'], get_target_height_mm())
        
        print(f"Starting mesh splitting (max size per piece: {get_max_size()}mm)...")
        split_mesh(scaled_model, output_dir)
        print("Splitting complete!")
        
        # Print summary
        piece_count = len([f for f in os.listdir(output_dir) if f.endswith('.stl')])
        print(f"\nSummary:")
        print(f"- Input file: {CONFIG['input_file']}")
        print(f"- Target height: {CONFIG['target_height_feet']} feet")
        print(f"- Height axis: {CONFIG['height_axis']}")
        print(f"- Printer bed size: {CONFIG['printer_bed_size']}mm")
        print(f"- Safety margin: {CONFIG['safety_margin']}mm")
        print(f"- Total pieces: {piece_count}")
        print(f"- Output directory: {output_dir}")
        
    except Exception as e:
        print(f"Error in main: {str(e)}")

if __name__ == "__main__":
    main()
