import trimesh
import numpy as np
import os
import math

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

def find_optimal_cuts(sections, max_size, mesh_size):
    """Find optimal cutting planes based on cross-sectional analysis"""
    cuts = [0]  # Always start with 0
    
    # Calculate minimum number of required cuts
    min_cuts = math.ceil(mesh_size / max_size)
    target_size = mesh_size / min_cuts
    
    print(f"Minimum cuts needed: {min_cuts}, target size per piece: {target_size:.2f}")
    
    current_pos = 0
    while current_pos < mesh_size:
        # Calculate ideal next position
        ideal_next_pos = min(current_pos + target_size, mesh_size)
        
        # Look for good cutting point near ideal position
        search_start = ideal_next_pos - (target_size * 0.2)  # Look back 20%
        search_end = min(ideal_next_pos + (target_size * 0.2), mesh_size)  # Look forward 20%
        
        # Find sections within search window
        section_window = [s for s in sections if search_start <= s[0] <= search_end]
        
        if not section_window:
            # If no good cutting point found, use ideal position
            next_cut = ideal_next_pos
        else:
            # Find local minimum within the window
            next_cut = min(section_window, key=lambda x: x[1])[0]
        
        if next_cut > current_pos:
            cuts.append(next_cut)
        current_pos = next_cut
    
    # Ensure we have the end point
    if cuts[-1] < mesh_size:
        cuts.append(mesh_size)
    
    print(f"Generated {len(cuts)-1} cuts, creating {len(cuts)-1} pieces")
    print(f"Cut positions: {[f'{c:.2f}' for c in cuts]}")
    
    return cuts

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
    
    # Center the mesh
    scaled_mesh.vertices -= scaled_mesh.bounds[0]
    mesh_size = scaled_mesh.bounds[1] - scaled_mesh.bounds[0]
    
    print(f"Mesh size after centering: {mesh_size}")
    
    # Find extremity points
    vertices = scaled_mesh.vertices
    z_threshold = np.percentile(vertices[:, 2], 98)
    extremity_points = vertices[vertices[:, 2] > z_threshold]
    
    print(f"Found {len(extremity_points)} extremity points above {z_threshold}")
    
    # Analyze cross sections but with fewer samples to find major divisions
    x_sections = analyze_cross_sections(scaled_mesh, 0, samples=10)
    y_sections = analyze_cross_sections(scaled_mesh, 1, samples=10)
    z_sections = analyze_cross_sections(scaled_mesh, 2, samples=10)
    
    # Enforce bed size constraints with some margin
    max_dimension = bed_size * 0.95  # Leave 5% margin for safety
    
    # Prioritize cutting along the axis that requires the most divisions
    dims = [mesh_size[0], mesh_size[1], mesh_size[2]]
    required_cuts = [math.ceil(dim / max_dimension) for dim in dims]
    
    print(f"Required minimum cuts per axis: X={required_cuts[0]}, Y={required_cuts[1]}, Z={required_cuts[2]}")
    
    # Only cut along axes that need it
    x_cuts = find_optimal_cuts(x_sections, max_dimension, mesh_size[0]) if required_cuts[0] > 1 else [0, mesh_size[0]]
    y_cuts = find_optimal_cuts(y_sections, max_dimension, mesh_size[1]) if required_cuts[1] > 1 else [0, mesh_size[1]]
    z_cuts = find_optimal_cuts(z_sections, max_dimension, mesh_size[2]) if required_cuts[2] > 1 else [0, mesh_size[2]]
    
    print(f"Optimal cutting planes:")
    print(f"X: {x_cuts}")
    print(f"Y: {y_cuts}")
    print(f"Z: {z_cuts}")
    
    # Validate maximum piece sizes
    max_x = max(x_cuts[i+1] - x_cuts[i] for i in range(len(x_cuts)-1))
    max_y = max(y_cuts[i+1] - y_cuts[i] for i in range(len(y_cuts)-1))
    max_z = max(z_cuts[i+1] - z_cuts[i] for i in range(len(z_cuts)-1))
    
    print(f"Maximum piece dimensions: {max_x:.1f} x {max_y:.1f} x {max_z:.1f}")
    
    if max_x > max_dimension or max_y > max_dimension or max_z > max_dimension:
        print(f"ERROR: Piece size exceeds bed size constraint of {max_dimension}")
        return False
    
    # Adjust volume threshold for validation
    volume_threshold = original_volume * 0.001  # 0.1% of total volume for small parts
    extremity_volume_threshold = original_volume * 0.0001  # Even smaller threshold for extremity parts
    
    sliced_parts = []
    total_sliced_volume = 0
    
    # Slice using optimal cutting planes
    for i in range(len(x_cuts)-1):
        for j in range(len(y_cuts)-1):
            for k in range(len(z_cuts)-1):
                min_bound = np.array([x_cuts[i], y_cuts[j], z_cuts[k]])
                max_bound = np.array([x_cuts[i+1], y_cuts[j+1], z_cuts[k+1]])
                
                try:
                    # Create bounding box for this section
                    box_size = max_bound - min_bound
                    box_center = min_bound + (box_size / 2)
                    box = trimesh.creation.box(extents=box_size)
                    box.apply_translation(box_center)
                    
                    # Slice the part
                    sliced_part = trimesh.boolean.intersection([scaled_mesh, box])
                    
                    if not sliced_part.is_empty:
                        has_extremity = any(all(min_bound <= point) and all(point <= max_bound) 
                                          for point in extremity_points)
                        
                        # Use appropriate volume threshold
                        current_threshold = (extremity_volume_threshold if has_extremity 
                                          else volume_threshold)
                        
                        if sliced_part.volume > current_threshold or has_extremity:
                            total_sliced_volume += sliced_part.volume
                            sliced_parts.append({
                                'mesh': sliced_part,
                                'position': (i, j, k),
                                'bounds': (min_bound, max_bound),
                                'has_extremity': has_extremity,
                                'volume': sliced_part.volume
                            })
                            print(f"Found valid part at {i},{j},{k}" + 
                                  (f" (contains extremity, vol={sliced_part.volume:.2f})" 
                                   if has_extremity else f" (vol={sliced_part.volume:.2f})"))
                
                except Exception as e:
                    print(f"Error processing section {i},{j},{k}: {str(e)}")
    
    # Volume validation
    volume_ratio = total_sliced_volume / original_volume
    print(f"Volume ratio (sliced/original): {volume_ratio:.4f}")
    
    if abs(1 - volume_ratio) > 0.01:  # 1% tolerance
        print("WARNING: Significant volume loss detected!")
        print(f"Original volume: {original_volume:.2f}")
        print(f"Total sliced volume: {total_sliced_volume:.2f}")
        print(f"Missing volume: {original_volume - total_sliced_volume:.2f}")
        return False
    
    # Export validated parts
    for idx, part in enumerate(sliced_parts):
        part_file_path = os.path.join(output_dir, f"part_{idx}.stl")
        part['mesh'].export(part_file_path)
        print(f"Saved part {idx} to {part_file_path}" +
              (" (contains extremity)" if part['has_extremity'] else ""))
    
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
stl_path = r"E:\iCloud Files\iCloudDrive\3D Printer\Things\Champagne Bottle (1_18 scale) - 2740717\files\champagne.stl"
output_dir = r"F:\Homebrew\Make It Big\output"
bed_size = 300  # Printer bed size in mm
target_height = 2  # Desired height in feet

slice_with_validation(stl_path, output_dir, bed_size, target_height)
