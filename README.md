# pg_raster_upload
QGIS plugin for uploading raster data to a PostGIS database. 

The plugin can be used to load file-based raster layers loaded in QGIS into a PostGIS database. 
It is assumed that the extension PostGIS Raster is installed in the target database.

If the extension is not installed in the target database, it can be done with the following command:

```
sql=# create extension postgis_raster;
```

