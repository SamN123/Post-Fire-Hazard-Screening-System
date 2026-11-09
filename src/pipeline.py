from pathlib import Path
import numpy as np
import rasterio
from rasterio.warp import transform_bounds
from rasterio.vrt import WarpedVRT
from rasterio.enums import Resampling
from rasterio.warp import reproject
from rasterio.transform import from_origin
from rasterio.windows import from_bounds, transform as window_transform
import math
import matplotlib.pyplot as plt
from matplotlib.colors import ListedColormap, BoundaryNorm
from matplotlib.patches import Patch
from scipy.ndimage import label, gaussian_filter
from matplotlib.patches import Patch
from matplotlib.colors import LinearSegmentedColormap

# ==================================================
# STEP 1: Find and Inspect GIS Datasets
# ==================================================

# Locate project folders
project_dir = Path(__file__).resolve().parent.parent
elevation_dir = project_dir / "Elevation"
wildfire_dir = project_dir / "Wildfires"

# # Find elevation and MTBS burn severity files
# elevation_files = sorted(elevation_dir.rglob("*.tif"))
# wildfire_files = sorted(wildfire_dir.rglob("*dnbr6.tif"))

# print("Elevation files found:", len(elevation_files))
# print("Wildfire files found:", len(wildfire_files))

# # Display geographic information for each raster
# for file in elevation_files + wildfire_files:
#     with rasterio.open(file) as dataset:
#         print("\nFile:", file.name)
#         print("Coordinate system:", dataset.crs)
#         print("Dimensions:", dataset.width, "x", dataset.height)
#         print("Resolution:", dataset.res)
#         print("Bounds:", dataset.bounds)
#         print("NoData:", dataset.nodata)


# # ==================================================
# # STEP 2: Check Geographic Overlap
# # ==================================================

# print("\n--- Geographic Overlap Check ---")

# # Check each wildfire against the available elevation raster
# with rasterio.open(elevation_files[0]) as dem:
#     dem_bounds = dem.bounds
#     dem_crs = dem.crs

#     for fire_file in wildfire_files:
#         with rasterio.open(fire_file) as fire:

#             # Convert wildfire bounds to the DEM coordinate system
#             fire_bounds = transform_bounds(
#                 fire.crs,
#                 dem_crs,
#                 *fire.bounds,
#                 densify_pts=21
#             )

#             # Check whether the two geographic areas intersect
#             overlaps = (
#                 fire_bounds[0] < dem_bounds.right
#                 and fire_bounds[2] > dem_bounds.left
#                 and fire_bounds[1] < dem_bounds.top
#                 and fire_bounds[3] > dem_bounds.bottom
#             )

#             # Check whether the DEM contains the full wildfire extent
#             fully_covered = (
#                 fire_bounds[0] >= dem_bounds.left
#                 and fire_bounds[1] >= dem_bounds.bottom
#                 and fire_bounds[2] <= dem_bounds.right
#                 and fire_bounds[3] <= dem_bounds.top
#             )

#             print(f"\nWildfire: {fire_file.name}")
#             print("Overlaps elevation:", overlaps)
#             print("Entire bounding box covered:", fully_covered)

# # ==================================================
# # STEP 3: Check Valid Elevation Coverage
# # ==================================================

# print("\n--- Elevation Coverage Check ---")

# with rasterio.open(elevation_files[0]) as dem:

#     for fire_file in wildfire_files:
#         with rasterio.open(fire_file) as fire:

#             # Temporarily match the DEM to the wildfire grid
#             with WarpedVRT(
#                 dem,
#                 crs=fire.crs,
#                 transform=fire.transform,
#                 width=fire.width,
#                 height=fire.height,
#                 resampling=Resampling.nearest
#             ) as aligned_dem:

#                 # Read elevation and burn severity masks
#                 elevation_valid = aligned_dem.read_masks(1) > 0
#                 wildfire_valid = fire.read_masks(1) > 0

#                 # Count wildfire pixels with valid elevation
#                 total_pixels = np.count_nonzero(wildfire_valid)

#                 covered_pixels = np.count_nonzero(
#                     wildfire_valid & elevation_valid
#                 )

#                 missing_pixels = total_pixels - covered_pixels

#                 coverage = (
#                     covered_pixels / total_pixels * 100
#                     if total_pixels > 0 else 0
#                 )

#                 print(f"\nWildfire: {fire_file.name}")
#                 print("Valid wildfire pixels:", total_pixels)
#                 print("Pixels with elevation:", covered_pixels)
#                 print("Missing elevation pixels:", missing_pixels)
#                 print(f"Elevation coverage: {coverage:.2f}%")

# ==================================================
# STEP 4: Inspect MTBS Burn Severity Classes
# ==================================================

# print("\n--- MTBS Burn Severity Classes ---")

# for fire_file in wildfire_files:
#     with rasterio.open(fire_file) as fire:

#         # Read burn severity values and exclude NoData
#         burn_data = fire.read(1, masked=True)
#         values, counts = np.unique(
#             burn_data.compressed(),
#             return_counts=True
#         )

#         print(f"\nWildfire: {fire_file.name}")

#         for value, count in zip(values, counts):
#             print(f"Class {value}: {count} pixels")

# ==================================================
# STEP 5: Reproject Elevation Data for Garden
# ==================================================

# Create folder for generated rasters
results_dir = project_dir / "Results"
results_dir.mkdir(exist_ok=True)

# Select Garden wildfire for initial testing
# garden_file = next(
#     file for file in wildfire_files
#     if "ca35531118648" in file.name
# )

# with rasterio.open(garden_file) as fire, rasterio.open(elevation_files[0]) as dem:

#     # Add a 100 meter margin for later slope calculations
#     margin = 100
#     left = fire.bounds.left - margin
#     bottom = fire.bounds.bottom - margin
#     right = fire.bounds.right + margin
#     top = fire.bounds.top + margin

#     # Create a 10 meter projected grid covering Garden
#     resolution = 10
#     width = math.ceil((right - left) / resolution)
#     height = math.ceil((top - bottom) / resolution)
#     target_transform = from_origin(left, top, resolution, resolution)

#     # Allocate the output elevation array
#     elevation = np.full(
#         (height, width),
#         np.nan,
#         dtype=np.float32
#     )

#     # Reproject elevation into Garden's coordinate system
#     reproject(
#         source=rasterio.band(dem, 1),
#         destination=elevation,
#         src_transform=dem.transform,
#         src_crs=dem.crs,
#         src_nodata=dem.nodata,
#         dst_transform=target_transform,
#         dst_crs=fire.crs,
#         dst_nodata=np.nan,
#         resampling=Resampling.bilinear
#     )

#     # Save the projected elevation raster
#     output_file = results_dir / "garden_elevation_10m.tif"

#     with rasterio.open(
#         output_file,
#         "w",
#         driver="GTiff",
#         height=height,
#         width=width,
#         count=1,
#         dtype="float32",
#         crs=fire.crs,
#         transform=target_transform,
#         nodata=np.nan
#     ) as output:
#         output.write(elevation, 1)

#     # Check the projected raster
#     valid = np.isfinite(elevation)

#     print("\n--- Garden Elevation Reprojection ---")
#     print("Output:", output_file.name)
#     print("Coordinate system:", fire.crs)
#     print("Dimensions:", width, "x", height)
#     print("Resolution:", resolution, "meters")
#     print("Valid elevation pixels:", np.count_nonzero(valid))
#     print("Missing elevation pixels:", np.count_nonzero(~valid))
#     print("Elevation range:", np.nanmin(elevation), "to", np.nanmax(elevation))

# ==================================================
# STEP 6: Calculate Terrain Slope
# ==================================================

# elevation_file = results_dir / "garden_elevation_10m.tif"
# slope_file = results_dir / "garden_slope_10m.tif"

# with rasterio.open(elevation_file) as dem:
#     elevation = dem.read(1, masked=True).filled(np.nan)

#     # Pixel spacing in meters
#     dx, dy = dem.res

#     # Calculate elevation changes using a 3x3 neighborhood
#     z1 = elevation[:-2, :-2]
#     z2 = elevation[:-2, 1:-1]
#     z3 = elevation[:-2, 2:]
#     z4 = elevation[1:-1, :-2]
#     z6 = elevation[1:-1, 2:]
#     z7 = elevation[2:, :-2]
#     z8 = elevation[2:, 1:-1]
#     z9 = elevation[2:, 2:]

#     # Horn's method: horizontal and vertical elevation gradients
#     dz_dx = ((z3 + 2*z6 + z9) - (z1 + 2*z4 + z7)) / (8 * dx)
#     dz_dy = ((z7 + 2*z8 + z9) - (z1 + 2*z2 + z3)) / (8 * dy)

#     # Convert the combined gradient into slope degrees
#     slope_center = np.degrees(
#         np.arctan(np.sqrt(dz_dx**2 + dz_dy**2))
#     )

#     # Leave outer edge undefined because neighbors are missing
#     slope = np.full(elevation.shape, np.nan, dtype=np.float32)
#     slope[1:-1, 1:-1] = slope_center

#     # Exclude pixels with invalid center elevations
#     slope[~np.isfinite(elevation)] = np.nan

#     # Save slope with the same geographic grid as the elevation raster
#     profile = dem.profile.copy()
#     profile.update(dtype="float32", nodata=np.nan, compress="lzw")

#     with rasterio.open(slope_file, "w", **profile) as output:
#         output.write(slope, 1)

#     # Check the calculated slope values
#     valid = np.isfinite(slope)

#     print("\n--- Garden Terrain Slope ---")
#     print("Output:", slope_file.name)
#     print("Coordinate system:", dem.crs)
#     print("Dimensions:", dem.width, "x", dem.height)
#     print("Resolution:", dem.res)
#     print("Valid slope pixels:", np.count_nonzero(valid))
#     print("Missing slope pixels:", np.count_nonzero(~valid))
#     print(f"Minimum slope: {np.nanmin(slope):.2f} degrees")
#     print(f"Maximum slope: {np.nanmax(slope):.2f} degrees")
#     print(f"Average slope: {np.nanmean(slope):.2f} degrees")

# ==================================================
# STEP 7: Visualize Garden Terrain Slope
# ==================================================

# slope_file = results_dir / "garden_slope_10m.tif"
# map_file = results_dir / "garden_slope_map.png"

# with rasterio.open(slope_file) as src:
#     slope = src.read(1, masked=True)

#     # Display slope using its real geographic coordinates
#     bounds = src.bounds

#     plt.figure(figsize=(9, 8))

#     plt.imshow(
#         slope,
#         cmap="terrain",
#         extent=[bounds.left, bounds.right, bounds.bottom, bounds.top],
#         origin="upper",
#         vmin=0,
#         vmax=65
#     )

#     plt.colorbar(label="Slope (degrees)")
#     plt.title("Garden Wildfire Area - Terrain Slope")
#     plt.xlabel("UTM Easting (meters)")
#     plt.ylabel("UTM Northing (meters)")

#     plt.tight_layout()
#     plt.savefig(map_file, dpi=200)
#     plt.show()

#     print("\n--- Garden Slope Map ---")
#     print("Map saved:", map_file.name)

# ==================================================
# STEP 8: Align Slope with the MTBS Grid
# ==================================================

# Find Garden's MTBS raster
# garden_file = next(
#     file for file in wildfire_dir.rglob("*dnbr6.tif")
#     if "ca35531118648" in file.name
# )

# slope_file = results_dir / "garden_slope_10m.tif"
# output_file = results_dir / "garden_slope_30m.tif"

# with rasterio.open(garden_file) as fire, rasterio.open(slope_file) as src:

#     # Create an array matching Garden's MTBS dimensions
#     aligned_slope = np.full(
#         (fire.height, fire.width),
#         np.nan,
#         dtype=np.float32
#     )

#     # Average 10m slope measurements onto the 30m wildfire grid
#     reproject(
#         source=rasterio.band(src, 1),
#         destination=aligned_slope,
#         src_transform=src.transform,
#         src_crs=src.crs,
#         src_nodata=src.nodata,
#         dst_transform=fire.transform,
#         dst_crs=fire.crs,
#         dst_nodata=np.nan,
#         resampling=Resampling.average
#     )

#     # Check that the grids have identical geographic positioning
#     assert src.crs == fire.crs
#     assert aligned_slope.shape == (fire.height, fire.width)

#     # Check slope coverage for valid wildfire pixels
#     burn_valid = fire.read_masks(1) > 0
#     missing = burn_valid & ~np.isfinite(aligned_slope)

#     print("\n--- Garden Slope Alignment ---")
#     print("MTBS dimensions:", fire.width, "x", fire.height)
#     print("Aligned slope dimensions:", aligned_slope.shape[1], "x", aligned_slope.shape[0])
#     print("Coordinate system:", fire.crs)
#     print("Missing slope pixels inside wildfire:", np.count_nonzero(missing))

#     # Stop if any valid wildfire pixel has no slope
#     if np.any(missing):
#         raise ValueError("Missing slope data inside the wildfire area.")

#     # Save the aligned slope using the exact MTBS grid
#     profile = fire.profile.copy()
#     profile.update(
#         dtype="float32",
#         nodata=np.nan,
#         compress="lzw"
#     )

#     with rasterio.open(output_file, "w", **profile) as dst:
#         dst.write(aligned_slope, 1)

# # Reopen the output to verify the saved geographic metadata
# with rasterio.open(garden_file) as fire, rasterio.open(output_file) as aligned:
#     assert aligned.crs == fire.crs
#     assert aligned.transform.almost_equals(fire.transform)
#     assert aligned.width == fire.width
#     assert aligned.height == fire.height

#     print("Saved raster grid matches MTBS: True")
#     print("Output:", output_file.name)

# ==================================================
# STEP 9: Validate Slope Averaging
# ==================================================

# slope_10m_file = results_dir / "garden_slope_10m.tif"
# slope_30m_file = results_dir / "garden_slope_30m.tif"

# with rasterio.open(slope_10m_file) as fine, \
#      rasterio.open(slope_30m_file) as coarse:

#     slope_10m = fine.read(1)
#     slope_30m = coarse.read(1)

#     # Check selected pixels across the Garden grid
#     test_pixels = [(50, 100), (100, 150), (200, 250)]

#     print("\n--- Slope Alignment Validation ---")

#     for row, col in test_pixels:

#         # Find the geographic center of the 30m pixel
#         x, y = coarse.xy(row, col)

#         # Locate that point in the 10m grid
#         fine_row, fine_col = fine.index(x, y)

#         # Extract the nine 10m pixels around that center
#         block = slope_10m[
#             fine_row - 1:fine_row + 2,
#             fine_col - 1:fine_col + 2
#         ]

#         manual_average = np.nanmean(block)
#         aligned_value = slope_30m[row, col]

#         difference = abs(manual_average - aligned_value)

#         print(f"\nPixel ({row}, {col})")
#         print(f"10m average: {manual_average:.4f} degrees")
#         print(f"30m raster: {aligned_value:.4f} degrees")
#         print(f"Difference: {difference:.6f} degrees")

#         if difference > 0.001:
#             raise ValueError("Slope averaging validation failed.")

#     print("\nAll selected slope averages match.")

# ==================================================
# STEP 10: Visualize MTBS and Slope Alignment
# ==================================================

# garden_file = next(
#     file for file in wildfire_dir.rglob("*dnbr6.tif")
#     if "ca35531118648" in file.name
# )

# slope_file = results_dir / "garden_slope_30m.tif"
# map_file = results_dir / "garden_alignment_check.png"

# with rasterio.open(garden_file) as fire, rasterio.open(slope_file) as src:

#     # Read burn severity and slope values
#     burn = fire.read(1, masked=True)
#     slope = src.read(1, masked=True)

#     # Confirm both rasters use the same geographic grid
#     assert fire.crs == src.crs
#     assert fire.transform.almost_equals(src.transform)
#     assert burn.shape == slope.shape

#     # Highlight moderate and high burn severity
#     severe_burn = np.ma.masked_where(
#         ~np.isin(burn, [3, 4]),
#         burn
#     )

#     bounds = fire.bounds
#     extent = [bounds.left, bounds.right, bounds.bottom, bounds.top]

#     plt.figure(figsize=(10, 8))

#     # Display terrain slope as the background
#     plt.imshow(
#         slope,
#         cmap="terrain",
#         extent=extent,
#         origin="upper",
#         vmin=0,
#         vmax=65
#     )

#     plt.colorbar(label="Slope (degrees)")

#     # Overlay moderate and high burn severity in red
#     # Show moderate and high burn severity in solid red
#     plt.imshow(
#     severe_burn,
#     cmap="Reds",
#     extent=extent,
#     origin="upper",
#     alpha=0.9,
#     vmin=1,
#     vmax=4
# )

#     plt.title("Garden Wildfire - Burn Severity and Slope Alignment")
#     plt.xlabel("UTM Easting (meters)")
#     plt.ylabel("UTM Northing (meters)")

#     plt.tight_layout()
#     plt.savefig(map_file, dpi=200)
#     plt.show()

#     print("\n--- Garden Alignment Map ---")
#     print("Map saved:", map_file.name)
#     print("Geographic grids match: True")

# ==================================================
# STEP 11: Identify Erosion Hotspots
# ==================================================

# garden_file = next(
#     file for file in wildfire_dir.rglob("*dnbr6.tif")
#     if "ca35531118648" in file.name
# )

# slope_file = results_dir / "garden_slope_30m.tif"
# output_file = results_dir / "garden_hotspots.tif"

# with rasterio.open(garden_file) as fire, rasterio.open(slope_file) as src:

#     # Verify both datasets use the same geographic grid
#     assert fire.crs == src.crs
#     assert fire.transform.almost_equals(src.transform)
#     assert fire.shape == src.shape

#     burn = fire.read(1)
#     slope = src.read(1)

#     # Identify pixels with moderate or high burn severity
#     severe_burn = np.isin(burn, [3, 4])

#     # Identify pixels with slopes of at least 23 degrees
#     steep_slope = slope >= 23

#     # A hotspot must meet both conditions
#     hotspots = severe_burn & steep_slope

#     # Store results: 1 = hotspot, 0 = not hotspot, 255 = no data
#     hotspot_data = np.zeros(burn.shape, dtype=np.uint8)

#     valid = (fire.read_masks(1) > 0) & np.isfinite(slope)

#     hotspot_data[hotspots & valid] = 1
#     hotspot_data[~valid] = 255

#     # Save the classifications using the MTBS geographic grid
#     profile = fire.profile.copy()
#     profile.update(
#         dtype="uint8",
#         nodata=255,
#         compress="lzw"
#     )

#     with rasterio.open(output_file, "w", **profile) as dst:
#         dst.write(hotspot_data, 1)

#     print("\n--- Garden Hotspot Classification ---")
#     print("Valid pixels:", np.count_nonzero(valid))
#     print("Moderate/high burn pixels:", np.count_nonzero(severe_burn & valid))
#     print("Pixels with slope >= 23 degrees:", np.count_nonzero(steep_slope & valid))
#     print("Potential hotspot pixels:", np.count_nonzero(hotspot_data == 1))
#     print("Output:", output_file.name)

# ==================================================
# STEP 12: Generate Hotspot Map
# ==================================================

# hotspot_file = results_dir / "garden_hotspots.tif"
# slope_file = results_dir / "garden_slope_30m.tif"
# map_file = results_dir / "garden_hotspot_map.png"

# with rasterio.open(hotspot_file) as src, rasterio.open(slope_file) as terrain:

#     assert src.crs == terrain.crs
#     assert src.transform.almost_equals(terrain.transform)
#     assert src.shape == terrain.shape

#     hotspot_data = src.read(1)
#     slope = terrain.read(1, masked=True)

#     # Hide all pixels except confirmed screening matches
#     hotspots = np.ma.masked_where(hotspot_data != 1, hotspot_data)

#     bounds = src.bounds
#     extent = [bounds.left, bounds.right, bounds.bottom, bounds.top]

#     plt.figure(figsize=(10, 8))

#     # Terrain slope background
#     plt.imshow(
#         slope,
#         cmap="terrain",
#         extent=extent,
#         origin="upper",
#         vmin=0,
#         vmax=65
#     )

#     plt.colorbar(label="Slope (degrees)")

#     # Highlight potential hotspots in solid red
#     plt.imshow(
#         hotspots,
#         cmap=ListedColormap(["red"]),
#         extent=extent,
#         origin="upper",
#         interpolation="nearest"
#     )

#     plt.legend(
#         handles=[Patch(color="red", label="Potential erosion hotspot")],
#         loc="upper right"
#     )

#     plt.title("Garden Wildfire - Potential Erosion Hotspots")
#     plt.xlabel("UTM Easting (meters)")
#     plt.ylabel("UTM Northing (meters)")

#     plt.tight_layout()
#     plt.savefig(map_file, dpi=200)
#     plt.show()

#     print("\n--- Garden Hotspot Map ---")
#     print("Hotspot pixels:", np.count_nonzero(hotspot_data == 1))
#     print("Map saved:", map_file.name)

# ==================================================
# STEP 13: Generate Smoothed Hotspot Map
# ==================================================

def generate_smoothed_hotspot_map(hotspot_file, slope_file, map_file, wildfire_name):
    """Create a hotspot visualization from aligned hotspot and slope rasters."""
    hotspot_file = Path(hotspot_file)
    slope_file = Path(slope_file)
    map_file = Path(map_file)
    map_file.parent.mkdir(parents=True, exist_ok=True)

    with rasterio.open(hotspot_file) as src, rasterio.open(slope_file) as terrain:

        # Check that both rasters use the same geographic grid
        assert src.crs == terrain.crs
        assert src.transform.almost_equals(terrain.transform)
        assert src.shape == terrain.shape

        hotspot_data = src.read(1)
        slope = terrain.read(1, masked=True)

        # Identify hotspot pixels
        hotspot_mask = hotspot_data == 1

        # Group neighboring hotspot pixels into connected regions
        clusters, cluster_count = label(
            hotspot_mask,
            structure=np.ones((3, 3))
        )

        # Smooth hotspot boundaries for visualization only
        smooth_mask = gaussian_filter(
            hotspot_mask.astype(float),
            sigma=1.0
        )

        # Get geographic boundaries
        bounds = src.bounds
        extent = [bounds.left, bounds.right, bounds.bottom, bounds.top]

       # Distinct terrain colors that contrast with red hotspots
        terrain_colors = [
        "#2166AC",  # 0°: Deep blue
        "#67A9CF",  # Gentle slopes: light blue
        "#1A9850",  # Moderate slopes: green
        "#A6D96A",  # Steeper slopes: light green
        "#FEE08B"   # Very steep slopes: golden yellow
    ]

        terrain_cmap = LinearSegmentedColormap.from_list(
        "terrain_contrast",
        terrain_colors
    )

        plt.figure(figsize=(10, 8))

        # Display terrain slope using muted earth tones
        plt.imshow(
            slope,
            cmap=terrain_cmap,
            extent=extent,
            origin="upper",
            vmin=0,
            vmax=65
        )

        plt.colorbar(label="Slope (degrees)")

        # Draw smoothed hotspot regions in red
        plt.contourf(
            smooth_mask,
            levels=[0.25, 1.0],
            colors=["red"],
            alpha=0.65,
            extent=extent,
            origin="upper"
        )

        # Add darker outlines around hotspot regions
        plt.contour(
            smooth_mask,
            levels=[0.25],
            colors=["darkred"],
            linewidths=0.8,
            extent=extent,
            origin="upper"
        )

        # Add legend
        plt.legend(
            handles=[Patch(color="red", label="Hotspot Region")],
            loc="upper right"
        )

        plt.title(f"{wildfire_name} - Potential Erosion Hotspots")
        plt.xlabel("UTM Easting (meters)")
        plt.ylabel("UTM Northing (meters)")

        plt.tight_layout()
        plt.savefig(map_file, dpi=200)
        plt.show()

        print("\n--- Smoothed Garden Hotspot Map ---")
        print("Original hotspot pixels:", np.count_nonzero(hotspot_mask))
        print("Connected hotspot regions:", cluster_count)
        print("Map saved:", map_file.name)


if __name__ == "__main__":
    # Existing Garden test. Other wildfires can use this function with their own files.
    generate_smoothed_hotspot_map(
        results_dir / "garden_hotspots.tif",
        results_dir / "garden_slope_30m.tif",
        results_dir / "garden_hotspot_map_smooth.png",
        "Garden Wildfire"
    )

# ==================================================
# STEP 14: Calculate Hotspot Statistics
# ==================================================

# hotspot_file = results_dir / "garden_hotspots.tif"
# slope_file = results_dir / "garden_slope_30m.tif"

# with rasterio.open(hotspot_file) as src, rasterio.open(slope_file) as terrain:

#     # Confirm both rasters use the same geographic grid
#     assert src.crs == terrain.crs
#     assert src.transform.almost_equals(terrain.transform)
#     assert src.shape == terrain.shape

#     hotspot_data = src.read(1)
#     slope = terrain.read(1)

#     # Identify valid pixels and hotspots
#     valid = hotspot_data != 255
#     hotspots = hotspot_data == 1

#     # Calculate area using the raster's pixel dimensions
#     pixel_area = abs(src.transform.a * src.transform.e)
#     acres_per_pixel = pixel_area / 4046.8564224

#     valid_pixels = np.count_nonzero(valid)
#     hotspot_pixels = np.count_nonzero(hotspots)

#     total_acres = valid_pixels * acres_per_pixel
#     hotspot_acres = hotspot_pixels * acres_per_pixel

#     hotspot_percent = (hotspot_pixels / valid_pixels) * 100

#     # Calculate slope statistics for hotspot pixels only
#     hotspot_slopes = slope[hotspots]

#     average_slope = np.mean(hotspot_slopes)
#     maximum_slope = np.max(hotspot_slopes)

#     # Group touching hotspot pixels into connected regions
#     clusters, cluster_count = label(
#         hotspots,
#         structure=np.ones((3, 3))
#     )

#     # Count pixels in each cluster, excluding background (0)
#     cluster_sizes = np.bincount(clusters.ravel())[1:]

#     largest_cluster_pixels = np.max(cluster_sizes)
#     largest_cluster_acres = largest_cluster_pixels * acres_per_pixel

#     print("\n--- Garden Hotspot Statistics ---")
#     print(f"Total analyzed area: {total_acres:.2f} acres")
#     print(f"Potential hotspot area: {hotspot_acres:.2f} acres")
#     print(f"Hotspot coverage: {hotspot_percent:.2f}%")
#     print(f"Average hotspot slope: {average_slope:.2f} degrees")
#     print(f"Maximum hotspot slope: {maximum_slope:.2f} degrees")
#     print(f"Connected hotspot clusters: {cluster_count}")
#     print(f"Largest hotspot cluster: {largest_cluster_acres:.2f} acres")  

# ==================================================
# STEP 15: Generate Garden Burn Severity Map
# ==================================================

# Find Garden's original MTBS file
# garden_file = next(
#     file for file in wildfire_dir.rglob("*dnbr6.tif")
#     if "ca35531118648" in file.name
# )

# slope_file = results_dir / "garden_slope_30m.tif"
# map_file = results_dir / "garden_burn_severity_map.png"

# with rasterio.open(garden_file) as fire, rasterio.open(slope_file) as terrain:

#     # Read burn severity and terrain slope
#     burn = fire.read(1, masked=True)
#     slope = terrain.read(1, masked=True)

#     # Confirm both rasters use the same geographic grid
#     assert fire.crs == terrain.crs
#     assert fire.transform.almost_equals(terrain.transform)
#     assert fire.shape == terrain.shape

#     # Group classes 5 and 6 as other classifications
#     burn_map = burn.copy()
#     burn_map[np.isin(burn_map, [5, 6])] = 5

#     # Get geographic boundaries
#     bounds = fire.bounds
#     extent = [bounds.left, bounds.right, bounds.bottom, bounds.top]

#     # Blue-gray terrain background
#     terrain_colors = [
#         "#DCE8F0",  # Flat terrain
#         "#B4C9D8",  # Gentle slopes
#         "#87A9BF",  # Moderate slopes
#         "#5E829C",  # Steep slopes
#         "#365B76"   # Very steep slopes
#     ]

#     terrain_cmap = LinearSegmentedColormap.from_list(
#         "blue_gray_terrain",
#         terrain_colors
#     )

#     # Burn severity classification colors
#     burn_colors = [
#         "#A6D96A",  # 1: Unburned to low
#         "#FEE08B",  # 2: Low severity
#         "#F29E4C",  # 3: Moderate severity
#         "#D62828",  # 4: High severity
#         "#A0A0A0"   # 5/6: Other classification
#     ]

#     burn_cmap = ListedColormap(burn_colors)
#     burn_cmap.set_bad((0, 0, 0, 0))

#     burn_norm = BoundaryNorm(
#         np.arange(0.5, 6.5, 1),
#         burn_cmap.N
#     )

#     plt.figure(figsize=(10, 8))

#     # Display terrain slope as the background
#     plt.imshow(
#         slope,
#         cmap=terrain_cmap,
#         extent=extent,
#         origin="upper",
#         vmin=0,
#         vmax=65
#     )

#     # Overlay burn severity using solid classification colors
#     plt.imshow(
#         burn_map,
#         cmap=burn_cmap,
#         norm=burn_norm,
#         extent=extent,
#         origin="upper",
#         interpolation="nearest",
#         alpha=1.0
#     )

#     # Create the discrete burn severity legend
#     labels = [
#         "Unburned to low",
#         "Low severity",
#         "Moderate severity",
#         "High severity",
#         "Other classification"
#     ]

#     legend_items = [
#         Patch(color=burn_colors[i], label=labels[i])
#         for i in range(5)
#     ]

#     plt.legend(
#         handles=legend_items,
#         loc="upper right",
#         fontsize=9
#     )

#     plt.title("Garden Wildfire - MTBS Burn Severity")
#     plt.xlabel("UTM Easting (meters)")
#     plt.ylabel("UTM Northing (meters)")

#     plt.tight_layout()
#     plt.savefig(map_file, dpi=200)
#     plt.show()

#     # Print original burn severity counts
#     values, counts = np.unique(
#         burn.compressed(),
#         return_counts=True
#     )

#     print("\n--- Garden Burn Severity Map ---")

#     for value, count in zip(values, counts):
#         print(f"Class {value}: {count} pixels")

#     print("Map saved:", map_file.name)