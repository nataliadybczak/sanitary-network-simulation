import osmnx as ox
import contextily as cx
import matplotlib.pyplot as plt

def get_map( south = 49.6600, north=49.7150, east=19.2600 ,west=19.1700, epsg = "EPSG:4326"):
    # bbox Żywca
    # north, south = 49.7150, 49.6600
    # east,  west  = 19.2600, 19.1700

    # pusty wykres z granicami w WGS84
    fig, ax = plt.subplots(figsize=(8,6))
    ax.set_xlim([west, east])
    ax.set_ylim([south, north])

    # dociągnij kafelki w Web Mercator i nałóż (contextily wykona reprojekcję)
    cx.add_basemap(ax, source=cx.providers.OpenStreetMap.Mapnik, crs=epsg, zoom=14)
    ax.axis('off')
    plt.tight_layout()
    plt.savefig("map.png", dpi=200, bbox_inches="tight", pad_inches=0)

# get_map(49.6700, 49.7000, 19.1900, 19.2300)
get_map()