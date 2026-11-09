"""Reusable post-fire hotspot screening pipeline.

Run this file in VS Code and select a wildfire from the numbered menu.

Requires numpy, rasterio, scipy, and matplotlib.
"""
from pathlib import Path
import math

import matplotlib
matplotlib.use('Agg')  # Save images without opening windows (GUI-friendly).
import matplotlib.pyplot as plt
from matplotlib.colors import ListedColormap, BoundaryNorm, LinearSegmentedColormap
from matplotlib.patches import Patch
import numpy as np
import rasterio
from rasterio.enums import Resampling
from rasterio.transform import from_origin
from rasterio.warp import reproject, transform_bounds
from scipy.ndimage import gaussian_filter, label

PROJECT_DIR = Path(__file__).resolve().parent.parent


def validate_inputs(wildfire_file, elevation_file):
    """Check that files exist, have valid spatial metadata and intersect."""
    for file in (wildfire_file, elevation_file):
        if not file.is_file():
            raise FileNotFoundError(f"Raster not found: {file}")
    with rasterio.open(wildfire_file) as fire, rasterio.open(elevation_file) as dem:
        if not fire.crs or not dem.crs:
            raise ValueError('Both rasters must have a coordinate reference system.')
        if fire.crs.is_geographic:
            raise ValueError('MTBS raster must use a projected CRS in meters for area and slope calculations.')
        if str(fire.crs.linear_units).lower() not in ('metre', 'meter', 'metres', 'meters'):
            raise ValueError('MTBS CRS must use meters; check raster units before processing.')
        if fire.count < 1 or dem.count < 1:
            raise ValueError('Both rasters must have at least one band.')
        dem_bounds = transform_bounds(dem.crs, fire.crs, *dem.bounds, densify_pts=21)
        f = fire.bounds
        overlaps = (dem_bounds[0] < f.right and dem_bounds[2] > f.left
                    and dem_bounds[1] < f.top and dem_bounds[3] > f.bottom)
        if not overlaps:
            raise ValueError('The elevation raster does not overlap the selected wildfire.')
        if not np.any(fire.read_masks(1)):
            raise ValueError('The wildfire raster has no valid pixels.')


def prepare_elevation(wildfire_file, elevation_file, output_file, resolution=10, margin=100):
    """Reproject DEM onto a 10 m grid with a margin for slope calculations."""
    with rasterio.open(wildfire_file) as fire, rasterio.open(elevation_file) as dem:
        left, bottom = fire.bounds.left - margin, fire.bounds.bottom - margin
        right, top = fire.bounds.right + margin, fire.bounds.top + margin
        width = math.ceil((right - left) / resolution)
        height = math.ceil((top - bottom) / resolution)
        transform = from_origin(left, top, resolution, resolution)
        elevation = np.full((height, width), np.nan, dtype=np.float32)
        reproject(source=rasterio.band(dem, 1), destination=elevation,
                  src_transform=dem.transform, src_crs=dem.crs, src_nodata=dem.nodata,
                  dst_transform=transform, dst_crs=fire.crs, dst_nodata=np.nan,
                  resampling=Resampling.bilinear)
        if not np.isfinite(elevation).any():
            raise ValueError('No valid elevation values after reprojection.')
        profile = fire.profile.copy()
        profile.update(driver='GTiff', height=height, width=width, count=1,
                       dtype='float32', crs=fire.crs, transform=transform,
                       nodata=np.nan, compress='lzw')
        with rasterio.open(output_file, 'w', **profile) as dst:
            dst.write(elevation, 1)


def calculate_slope(elevation_file, output_file):
    """Horn 3x3 slope in degrees; same calculation as the original pipeline."""
    with rasterio.open(elevation_file) as dem:
        elevation = dem.read(1, masked=True).filled(np.nan)
        dx, dy = dem.res
        z1, z2, z3 = elevation[:-2, :-2], elevation[:-2, 1:-1], elevation[:-2, 2:]
        z4, z6 = elevation[1:-1, :-2], elevation[1:-1, 2:]
        z7, z8, z9 = elevation[2:, :-2], elevation[2:, 1:-1], elevation[2:, 2:]
        dz_dx = ((z3 + 2*z6 + z9) - (z1 + 2*z4 + z7)) / (8 * dx)
        dz_dy = ((z7 + 2*z8 + z9) - (z1 + 2*z2 + z3)) / (8 * dy)
        center = np.degrees(np.arctan(np.sqrt(dz_dx**2 + dz_dy**2)))
        slope = np.full(elevation.shape, np.nan, dtype=np.float32)
        slope[1:-1, 1:-1] = center
        slope[~np.isfinite(elevation)] = np.nan
        profile = dem.profile.copy()
        profile.update(dtype='float32', nodata=np.nan, compress='lzw')
        with rasterio.open(output_file, 'w', **profile) as dst:
            dst.write(slope, 1)


def align_slope(wildfire_file, slope_file, output_file):
    """Average 10 m slope onto the exact wildfire grid and verify coverage."""
    with rasterio.open(wildfire_file) as fire, rasterio.open(slope_file) as src:
        aligned = np.full((fire.height, fire.width), np.nan, dtype=np.float32)
        reproject(source=rasterio.band(src, 1), destination=aligned,
                  src_transform=src.transform, src_crs=src.crs, src_nodata=src.nodata,
                  dst_transform=fire.transform, dst_crs=fire.crs, dst_nodata=np.nan,
                  resampling=Resampling.average)
        valid_burn = fire.read_masks(1) > 0
        # This is intentionally strict, as in the original Step 8.
        missing = valid_burn & ~np.isfinite(aligned)
        if np.any(missing):
            raise ValueError(f'Missing slope for {np.count_nonzero(missing)} valid wildfire pixels. '
                             'Check elevation coverage; do not treat these pixels as safe.')
        profile = fire.profile.copy()
        profile.update(dtype='float32', nodata=np.nan, compress='lzw')
        with rasterio.open(output_file, 'w', **profile) as dst:
            dst.write(aligned, 1)
    with rasterio.open(wildfire_file) as fire, rasterio.open(output_file) as saved:
        assert saved.crs == fire.crs
        assert saved.transform.almost_equals(fire.transform)
        assert saved.shape == fire.shape


def classify_hotspots(wildfire_file, slope_file, output_file, slope_threshold=23):
    """Class 3/4 AND slope >= threshold; 255 represents NoData."""
    with rasterio.open(wildfire_file) as fire, rasterio.open(slope_file) as terrain:
        if fire.crs != terrain.crs or not fire.transform.almost_equals(terrain.transform) or fire.shape != terrain.shape:
            raise ValueError('Burn severity and slope grids do not match.')
        burn, slope = fire.read(1), terrain.read(1)
        valid = (fire.read_masks(1) > 0) & np.isfinite(slope)
        hotspots = np.isin(burn, [3, 4]) & (slope >= slope_threshold)
        data = np.zeros(burn.shape, dtype=np.uint8)
        data[hotspots & valid] = 1
        data[~valid] = 255
        profile = fire.profile.copy()
        profile.update(dtype='uint8', nodata=255, compress='lzw')
        with rasterio.open(output_file, 'w', **profile) as dst:
            dst.write(data, 1)


def calculate_statistics(hotspot_file, slope_file):
    """Use the original pixel-area and 8-connected-region statistics."""
    with rasterio.open(hotspot_file) as src, rasterio.open(slope_file) as terrain:
        if src.crs != terrain.crs or not src.transform.almost_equals(terrain.transform) or src.shape != terrain.shape:
            raise ValueError('Hotspot and slope grids do not match.')
        data, slope = src.read(1), terrain.read(1)
        valid, hotspots = data != 255, data == 1
        pixel_area = abs(src.transform.a * src.transform.e)
        acres_per_pixel = pixel_area / 4046.8564224
        valid_count, hotspot_count = np.count_nonzero(valid), np.count_nonzero(hotspots)
        if valid_count == 0:
            raise ValueError('No valid pixels available for statistics.')
        clusters, cluster_count = label(hotspots, structure=np.ones((3, 3)))
        cluster_sizes = np.bincount(clusters.ravel())[1:]
        return {
            'valid_pixels': int(valid_count),
            'hotspot_pixels': int(hotspot_count),
            'analyzed_acres': float(valid_count * acres_per_pixel),
            'hotspot_acres': float(hotspot_count * acres_per_pixel),
            'hotspot_percent': float(100 * hotspot_count / valid_count),
            'average_hotspot_slope': float(np.mean(slope[hotspots])) if hotspot_count else None,
            'maximum_hotspot_slope': float(np.max(slope[hotspots])) if hotspot_count else None,
            'cluster_count': int(cluster_count),
            'largest_cluster_acres': float(np.max(cluster_sizes) * acres_per_pixel) if cluster_count else 0.0,
        }


def save_maps(wildfire_file, slope_file, hotspot_file, output_dir, name):
    """Create slope, burn severity and smoothed hotspot maps; smoothing never changes classification."""
    with rasterio.open(wildfire_file) as fire, rasterio.open(slope_file) as terrain, rasterio.open(hotspot_file) as src:
        if not (fire.crs == terrain.crs == src.crs and
                fire.transform.almost_equals(terrain.transform) and
                fire.transform.almost_equals(src.transform) and
                fire.shape == terrain.shape == src.shape):
            raise ValueError('Map input grids do not match.')
        burn = fire.read(1, masked=True)
        slope = terrain.read(1, masked=True)
        hotspot_mask = src.read(1) == 1
        b = fire.bounds
        extent = [b.left, b.right, b.bottom, b.top]
        terrain_colors = ['#2166AC', '#67A9CF', '#1A9850', '#A6D96A', '#FEE08B']
        terrain_cmap = LinearSegmentedColormap.from_list('terrain_contrast', terrain_colors)

        fig, ax = plt.subplots(figsize=(10, 8))
        img = ax.imshow(slope, cmap=terrain_cmap, extent=extent, origin='upper', vmin=0, vmax=65)
        fig.colorbar(img, ax=ax, label='Slope (degrees)')
        ax.set(title=f'{name} Wildfire - Terrain Slope', xlabel='UTM Easting (meters)', ylabel='UTM Northing (meters)')
        fig.tight_layout()
        slope_map = output_dir / 'slope_map.png'
        fig.savefig(slope_map, dpi=200)
        plt.close(fig)

        burn_map = burn.copy()
        burn_map[np.isin(burn_map, [5, 6])] = 5
        burn_colors = ['#A6D96A', '#FEE08B', '#F29E4C', '#D62828', '#A0A0A0']
        cmap = ListedColormap(burn_colors)
        cmap.set_bad((0, 0, 0, 0))
        norm = BoundaryNorm(np.arange(0.5, 6.5, 1), cmap.N)
        fig, ax = plt.subplots(figsize=(10, 8))
        ax.imshow(slope, cmap=terrain_cmap, extent=extent, origin='upper', vmin=0, vmax=65)
        ax.imshow(burn_map, cmap=cmap, norm=norm, extent=extent, origin='upper', interpolation='nearest')
        labels = ['Unburned to low', 'Low severity', 'Moderate severity', 'High severity', 'Other classification']
        ax.legend(handles=[Patch(color=c, label=t) for c, t in zip(burn_colors, labels)], loc='upper right', fontsize=9)
        ax.set(title=f'{name} Wildfire - MTBS Burn Severity', xlabel='UTM Easting (meters)', ylabel='UTM Northing (meters)')
        fig.tight_layout()
        burn_output = output_dir / 'burn_severity_map.png'
        fig.savefig(burn_output, dpi=200)
        plt.close(fig)

        smooth_mask = gaussian_filter(hotspot_mask.astype(float), sigma=1.0)
        fig, ax = plt.subplots(figsize=(10, 8))
        img = ax.imshow(slope, cmap=terrain_cmap, extent=extent, origin='upper', vmin=0, vmax=65)
        fig.colorbar(img, ax=ax, label='Slope (degrees)')
        if hotspot_mask.any():
            ax.contourf(smooth_mask, levels=[0.25, 1.0], colors=['red'], alpha=0.65,
                        extent=extent, origin='upper')
            ax.contour(smooth_mask, levels=[0.25], colors=['darkred'], linewidths=0.8,
                       extent=extent, origin='upper')
        ax.legend(handles=[Patch(color='red', label='Hotspot Region')], loc='upper right')
        ax.set(title=f'{name} Wildfire - Potential Erosion Hotspots',
               xlabel='UTM Easting (meters)', ylabel='UTM Northing (meters)')
        fig.tight_layout()
        hotspot_map = output_dir / 'hotspot_map_smooth.png'
        fig.savefig(hotspot_map, dpi=200)
        plt.close(fig)
        return {'slope_map': str(slope_map), 'burn_map': str(burn_output), 'hotspot_map': str(hotspot_map)}


def run_analysis(wildfire_file, elevation_file, output_dir, wildfire_name, slope_threshold=23):
    """Single entry point for CLI, future GUI, and database integration."""
    wildfire_file = Path(wildfire_file)
    elevation_file = Path(elevation_file)
    output_dir = Path(output_dir)
    validate_inputs(wildfire_file, elevation_file)
    output_dir.mkdir(parents=True, exist_ok=True)
    elevation_out = output_dir / 'elevation_10m.tif'
    slope_10m = output_dir / 'slope_10m.tif'
    slope_30m = output_dir / 'slope_30m.tif'
    hotspots = output_dir / 'hotspots.tif'
    prepare_elevation(wildfire_file, elevation_file, elevation_out)
    calculate_slope(elevation_out, slope_10m)
    align_slope(wildfire_file, slope_10m, slope_30m)
    classify_hotspots(wildfire_file, slope_30m, hotspots, slope_threshold)
    stats = calculate_statistics(hotspots, slope_30m)
    maps = save_maps(wildfire_file, slope_30m, hotspots, output_dir, wildfire_name)
    return {'wildfire_name': wildfire_name, 'wildfire_file': str(wildfire_file),
            'elevation_file': str(elevation_file), 'output_dir': str(output_dir),
            'hotspot_raster': str(hotspots), 'slope_raster': str(slope_30m),
            'elevation_raster': str(elevation_out), 'statistics': stats, 'maps': maps}


def choose_file(files, description):
    """Show available files and ask the user to select one."""
    if not files:
        raise FileNotFoundError(f"No {description} files found in the project folders.")
    print(f"\nAvailable {description} files:")
    for number, file in enumerate(files, 1):
        print(f"{number}. {file.relative_to(PROJECT_DIR)}")
    while True:
        choice = input(f"Choose a {description} number (or q to quit): ").strip()
        if choice.lower() == 'q':
            return None
        if choice.isdigit() and 1 <= int(choice) <= len(files):
            return files[int(choice) - 1]
        print("Enter one of the numbers shown above.")


def main():
    wildfire_files = sorted((PROJECT_DIR / 'Wildfires').rglob('*dnbr6.tif'))
    elevation_files = sorted((PROJECT_DIR / 'Elevation').rglob('*.tif'))
    wildfire = choose_file(wildfire_files, 'wildfire')
    if wildfire is None:
        return
    if len(elevation_files) != 1:
        raise ValueError(f'Expected exactly one elevation TIFF in Elevation/, found {len(elevation_files)}.')
    elevation = elevation_files[0]
    print(f'Using elevation: {elevation.relative_to(PROJECT_DIR)}')

    name = input("Enter wildfire name: ").strip()

    if not name:
        print("Wildfire name cannot be empty.")
        return

    safe_name = wildfire.stem
    # Use a distinct test directory, leaving existing Garden results untouched.
    output = PROJECT_DIR / 'Results' / 'RefactorTest' / safe_name
    print(f"\nAnalyzing: {name}")
    print(f"Output folder: {output}")
    result = run_analysis(wildfire, elevation, output, name)
    print('\nAnalysis completed:')
    for key, value in result['statistics'].items():
        print(f'{key}: {value}')
    print('Output folder:', result['output_dir'])


if __name__ == '__main__':
    main()
