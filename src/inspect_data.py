import rasterio

# Location of the elevation file
elevation_file = r"C:\Users\Samna\OneDrive\Desktop\SequoiaForestData\Elevation\USGS_13_n36w119_20260610.tif"

with rasterio.open(elevation_file) as data:
    print("File:", data.name)
    print("Coordinate System:", data.crs)
    print("Resolution:", data.res)
    print("Dimensions:", data.width, "x", data.height)
    print("Geographic Bounds:", data.bounds)
    print("NoData Value:", data.nodata)