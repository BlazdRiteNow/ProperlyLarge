import trimesh
import numpy as np
import os
import math

def create_connector(radius, height, is_hole=False):
    # Creates a cylindrical peg connector
    # For holes, we make it slightly larger to ensure proper boolean operation
    if is_hole:
        radius *= 1.01  # Add 1% tolerance for holes
    cylinder = trimesh.creation.cylinder(radius=radius, height=height)
    # Ensure the mesh is watertight
    cylinder.fill_holes()
    cylinder.remove_degenerate_faces()
    cylinder.remove_duplicate_faces()
    return cylinder

def slice_stl_with_connectors(stl_path, output_dir, bed_size, target_height, connector_radius=5, connector_height=10):
    mesh = trimesh.load_mesh(stl_path)
    
    # Calculate scale factor and apply scaling
    original_height = mesh.bounds[1][2] - mesh.bounds[0][2]
    scale_factor = (target_height * 304.8) / original_height
    scaled_mesh = mesh.copy()
    scaled_mesh.apply_scale(scale_factor)
    
    # Store original volume for validation
    original_volume = scaled_mesh.volume
    print(f"Original scaled volume: {original_volume}")
    
    # Center the mesh
    scaled_mesh.vertices -= scaled_mesh.bounds[0]
    mesh_size = scaled_mesh.bounds[1] - scaled_mesh.bounds[0]
    
    def analyze_cross_sections(mesh, axis, samples=20):
        """Analyze cross-sectional areas to find natural division points"""
        min_val = mesh.bounds[0][axis]
        max_val = mesh.bounds[1][axis]
        areas = []
        positions = np.linspace(min_val, max_val, samples)
        
        for pos in positions:
            # Create a cutting plane
            plane_normal = np.zeros(3)
            plane_normal[axis] = 1
            plane_origin = np.zeros(3)
            plane_origin[axis] = pos
            
            # Get cross section
            section = mesh.section(plane_normal=plane_normal,
                                 plane_origin=plane_origin)
            
            if section is not None:
                # Convert 3D path to 2D and calculate area
                section_2D, _ = section.to_planar()
                if section_2D is not None:
                    areas.append((pos, abs(section_2D.area)))
            else:
                areas.append((pos, 0))
        
        return areas
    
    # Analyze cross sections in each axis
    x_sections = analyze_cross_sections(scaled_mesh, 0)
    y_sections = analyze_cross_sections(scaled_mesh, 1)
    z_sections = analyze_cross_sections(scaled_mesh, 2)
    
    def find_optimal_cuts(sections, max_size):
        """Find optimal cutting planes based on cross-sectional analysis"""
        cuts = []
        current_pos = 0
        while current_pos < mesh_size[0]:
            # Find local minimum in cross-sectional area
            section_window = [s for s in sections if current_pos <= s[0] <= current_pos + max_size]
            if not section_window:
                break
                
            # Find local minimum within the window
            min_area_pos = min(section_window, key=lambda x: x[1])[0]
            cuts.append(min_area_pos)
            current_pos = min_area_pos + max_size/4  # Overlap slightly to ensure coverage
            
        return cuts
    
    # Get optimal cutting planes
    x_cuts = find_optimal_cuts(x_sections, bed_size)
    y_cuts = find_optimal_cuts(y_sections, bed_size)
    z_cuts = find_optimal_cuts(z_sections, bed_size)
    
    print(f"Optimal cutting planes:")
    print(f"X: {x_cuts}")
    print(f"Y: {y_cuts}")
    print(f"Z: {z_cuts}")
    
    # Store all sliced parts for validation
    sliced_parts = []
    total_sliced_volume = 0
    
    # Slice using optimal cutting planes
    for i in range(len(x_cuts)-1):
        for j in range(len(y_cuts)-1):
            for k in range(len(z_cuts)-1):
                min_bound = np.array([x_cuts[i], y_cuts[j], z_cuts[k]])
                max_bound = np.array([x_cuts[i+1], y_cuts[j+1], z_cuts[k+1]])
                
                # Create bounding box
                box_size = max_bound - min_bound
                box = trimesh.creation.box(extents=box_size)
                box.apply_translation(min_bound + box_size/2)
                
                try:
                    # Slice the part
                    sliced_part = trimesh.boolean.intersection([scaled_mesh, box])
                    
                    if not sliced_part.is_empty:
                        total_sliced_volume += sliced_part.volume
                        sliced_parts.append({
                            'mesh': sliced_part,
                            'position': (i, j, k),
                            'bounds': (min_bound, max_bound)
                        })
                
                except Exception as e:
                    print(f"Error processing section: {str(e)}")
    
    # Validate total volume (allowing for small numerical errors)
    volume_ratio = total_sliced_volume / original_volume
    print(f"Volume ratio (sliced/original): {volume_ratio}")
    
    if abs(1 - volume_ratio) > 0.01:  # 1% tolerance
        print("WARNING: Significant volume loss detected!")
        print(f"Original volume: {original_volume}")
        print(f"Total sliced volume: {total_sliced_volume}")
        print("Some parts may be missing. Adjusting slice parameters...")
        return False
    
    # Check for gaps between parts
    def check_adjacent_parts(parts):
        for part in parts:
            pos = part['position']
            bounds = part['bounds']
            
            # Check each direction for adjacent parts
            directions = [
                (1, 0, 0), (-1, 0, 0),  # X axis
                (0, 1, 0), (0, -1, 0),  # Y axis
                (0, 0, 1), (0, 0, -1)   # Z axis
            ]
            
            for dx, dy, dz in directions:
                adjacent_pos = (pos[0] + dx, pos[1] + dy, pos[2] + dz)
                if not any(p['position'] == adjacent_pos for p in parts):
                    # Check if there should be a part here
                    test_point = bounds[1] if any(d > 0 for d in (dx, dy, dz)) else bounds[0]
                    if scaled_mesh.contains([test_point]):
                        print(f"WARNING: Missing adjacent part at position {adjacent_pos}")
                        return False
        return True
    
    if not check_adjacent_parts(sliced_parts):
        print("Gaps detected between parts. Adjusting slice parameters...")
        return False
    
    # If validation passes, export the parts
    part_counter = 0
    for part in sliced_parts:
        part_file_path = os.path.join(output_dir, f"part_{part_counter}.stl")
        part['mesh'].export(part_file_path)
        print(f"Saved part {part_counter} to {part_file_path}")
        part_counter += 1
    
    print(f"Total parts saved: {part_counter}")
    print("All parts validated successfully!")
    return True

# Example usage with validation loop
def slice_with_validation(stl_path, output_dir, bed_size, target_height, max_attempts=3):
    attempt = 1
    while attempt <= max_attempts:
        print(f"\nAttempt {attempt} of {max_attempts}")
        if slice_stl_with_connectors(stl_path, output_dir, bed_size, target_height):
            print("Slicing completed successfully!")
            break
        attempt += 1
        # Adjust parameters for next attempt if needed
        bed_size *= 0.95  # Slightly reduce bed size to try different cut positions
    
    if attempt > max_attempts:
        print("Failed to find valid slicing solution after maximum attempts")

# Example usage:
stl_path = r"E:\iCloud Files\iCloudDrive\3D Printer\Things\Cubone Dog Mask - 2839481\files\Cubone_Skull_XY_Printable_for_Dog.stl"
output_dir = r"F:\Homebrew\Make It Big\output"
bed_size = 180  # Printer bed size in mm
target_height = .75  # Desired height in feet

slice_with_validation(stl_path, output_dir, bed_size, target_height)
