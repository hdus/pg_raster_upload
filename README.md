# pg_raster_upload
QGIS plugin for uploading raster data to a PostGIS database.

The plugin can be used to load file-based raster layers loaded in QGIS into a PostGIS database.
Additionally, raster overviews (“pyramids”) can be created during upload or separately for an
already existung layer.

It is assumed that the extension PostGIS Raster is installed in the target database.

If the extension is not installed in the target database, it can be done with the following command:

```
sql=# create extension postgis_raster;
```

## Usage

  * To load a raster into a PostGIS database, the raster must first be loaded into a QGIS project. When the PostGIS Raster Import is then started from the Database menu, the selection list `Raster layer` is filled with the loaded raster layers. Only file-based raster data can be loaded into the DB.

  * The next step is to select the database connection.

  * Select the schema in the selected database. In the selection list `Schema` all schemas of the selected database are displayed. A new schema can be created in the database by entering a new text in the selection list.

  * In the input field `Table name` the name of the target table in the selected database must be entered. As default, the layer name will be shown here, converted to lower case and with punctuation and spaces converted to underscore.

  * In addition, the option `create raster overviews` is available. If this option is activated, overview tables are created in addition to the raster table with the following levels: 2, 4, 8, 16, 32, 64, 256

  * Overview tables can be created for an existing PostGIS raster layer with the “Create raster overviews” from the Database menu. The PostGIS raster layer has to be added to the project first.
