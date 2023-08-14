# -*- coding: utf-8 -*-
"""
/***************************************************************************
 PGRasterImportDialog
                                 A QGIS plugin
 Import Raster to PgRaster
 Generated by Plugin Builder: http://g-sherman.github.io/Qgis-Plugin-Builder/
                             -------------------
        begin                : 2021-06-24
        git sha              : $Format:%H$
        copyright            : (C) 2021 by Dr. Horst Duester / Sourcepols
        email                : horst.duester@sourcepole.ch
 ***************************************************************************/

/***************************************************************************
 *                                                                         *
 *   This program is free software; you can redistribute it and/or modify  *
 *   it under the terms of the GNU General Public License as published by  *
 *   the Free Software Foundation; either version 2 of the License, or     *
 *   (at your option) any later version.                                   *
 *                                                                         *
 ***************************************************************************/
"""
import os
import sys
import re
import psycopg2
from qgis.PyQt import uic
from qgis.core import *
from qgis.utils import OverrideCursor
from qgis.PyQt.QtCore import Qt,  pyqtSlot,  QSettings
from qgis.PyQt.QtWidgets import QDialog,  QMessageBox
from .raster.raster_upload import RasterUpload
from .about.about import About

# This loads your .ui file so that PyQt can populate your plugin with the elements from Qt Designer
FORM_CLASS, _ = uic.loadUiType(os.path.join(
    os.path.dirname(__file__), 'pgraster_import_dialog_base.ui'))


class PGRasterImportDialog(QDialog, FORM_CLASS):
    def __init__(self, iface,  parent=None):
        """Constructor."""
        super(PGRasterImportDialog, self).__init__(parent)
        # Set up the user interface from Designer through FORM_CLASS.
        # After self.setupUi() you can access any designer object by doing
        # self.<objectname>, and you can use autoconnect slots - see
        # http://qt-project.org/doc/qt-4.8/designer-using-a-ui-file.html
        # #widgets-and-dialogs-with-auto-connect
        self.setupUi(self)
        self.iface = iface
        self.getDbSettings()
        self.cmb_map_layer.setCurrentIndex(-1) 
        self.cmb_map_layer.setFilters(QgsMapLayerProxyModel.RasterLayer)        
        self.excluded_layers()
        
    def __error_message(self, e):
        result = QMessageBox.critical(
            None,
            self.tr("Error"),
            "%s" % e,
            QMessageBox.StandardButtons(
                QMessageBox.Ok),
            QMessageBox.Ok)
        
        return None        
        
    def message(self,  title,  text,  type):
        widget = self.iface.messageBar().createMessage(title, text)
        self.iface.messageBar().pushWidget(widget, type,  duration=5)
        
    def excluded_layers(self):
        excepted_layers = []
        for i in range(self.cmb_map_layer.count()):
            layer = self.cmb_map_layer.layer(i)
            if layer.dataProvider().name() == 'postgresraster':
                excepted_layers.append(layer)
                
        self.cmb_map_layer.setExceptedLayerList(excepted_layers)
        
    def enable_buttons(self):
        if self.cmb_map_layer.currentIndex() == -1 or self.cmb_db_connections.currentIndex() == 0:
            self.btn_upload.setEnabled(False)
        else:
            self.btn_upload.setEnabled(True)
            
    def table_exists(self,  conn,  schema,  table):
            
        sql = """
            SELECT exists( 
                SELECT table_name 
                FROM information_schema.tables 
                WHERE table_schema = '%s' and table_name = '%s')
            """ % (schema,  table)
        cur = conn.cursor()
        cur.execute(sql)
        rows = cur.fetchall()        

        return rows[0][0]
            

    def getDbSettings(self):
        self.cmb_db_connections.clear()
        settings = QSettings()
        settings.beginGroup('PostgreSQL/connections')
        self.cmb_db_connections.addItem('------------')
        self.cmb_db_connections.addItems(settings.childGroups())
        settings.endGroup()
        self.cmb_db_connections.setCurrentIndex(0)
        
    def init_DB(self, selectedServer):
        """Connect to DB, asking for credentials if neccessary. Return connection and password, or (None, None) if no connection possible."""
        if self.cmb_db_connections.currentIndex() == 0:
            return None, None
            
        settings = QSettings()
        mySettings = '/PostgreSQL/connections/' + selectedServer
        DBNAME = settings.value(mySettings + '/database')
        DBUSER = str(settings.value(mySettings + '/username', ''))
        DBHOST = settings.value(mySettings + '/host')
        DBPORT = settings.value(mySettings + '/port')
        DBPASSWD = str(settings.value(mySettings + '/password', ''))
        SERVICE_NAME = str(settings.value(mySettings + '/service', ''))
        
        if SERVICE_NAME and SERVICE_NAME not in ('', 'NULL', 'None'):
            connection_info = "service='{0}'".format(SERVICE_NAME)
        else:
            if DBPORT == None or DBPORT == 'NULL' or DBPORT == '':
                DBPORT = '5432'
                
            if DBUSER == 'NULL' or DBPASSWD == 'NULL' or DBUSER == '' or DBPASSWD == '':
                connection_info = "dbname='{0}' host='{1}' port={2}".format(DBNAME,  DBHOST,  DBPORT)                
                if DBUSER == 'NULL' or DBUSER == '':
                    try:  # try connecting without asking for credentials (e.g. Postgres is set up with Windows authentication)
                        conn = psycopg2.connect(connection_info)
                        if conn:
                            (success, user, password) = (True, '', '')
                            conn.close()
                        else:
                            success = False
                    except psycopg2.Error:
                        (success, user, password) = QgsCredentials.instance().get(connection_info, None, None)
                else:
                    (success, user, password) = QgsCredentials.instance().get(connection_info, str(DBUSER), None)
                    
                if not success:
                    QMessageBox.critical(None,  self.tr('Error'),  self.tr('Username or password incorrect!'))
                    return None, None

                DBUSER = user
                DBPASSWD = password
    
            connection_info = "dbname='{0}' host='{1}' port={2} user='{3}' password='{4}'".format(DBNAME, DBHOST, DBPORT, DBUSER, DBPASSWD)
        
        try:
            conn = psycopg2.connect(connection_info)
        except psycopg2.Error:
            QMessageBox.critical(None, self.tr('Error'),
                                 self.tr('Cannot connect to {0}: Exception info: {1}').format(
                                     connection_info, sys.exc_info()[1]))
            return None, None
        
        return conn, DBPASSWD
        
    def db_schemas(self,  conn):
        """Retrieve valid schemas for import from DB connection `conn`"""      
        sql = """
             SELECT n.nspname AS "Name"
               FROM pg_catalog.pg_namespace n                                      
             WHERE n.nspname !~ '^pg_' AND n.nspname <> 'information_schema'     
             ORDER BY 1;        
        """
        cur = conn.cursor()
        cur.execute(sql)
        rows = cur.fetchall()        
        schema_list = [row[0] for row in rows]
        return schema_list           

    @pyqtSlot()
    def on_btn_close_clicked(self):
        """
        Slot documentation goes here.
        """
        self.close()
    
    
    @pyqtSlot(str)
    def on_cmb_db_connections_currentIndexChanged(self, p0):
        """
        Update schema list when new DB is selected and enable buttons correspondingly.
        
        @param p0 selected item
        @type str
        """
        self.cmb_schema.clear()
        conn, passwd = self.init_DB(p0)
        if not conn:
            return
        if self.raster_extension_exists(conn):
            self.cmb_schema.addItems(self.db_schemas(conn))
            self.enable_buttons()
        else:
            QMessageBox.warning(None, self.tr('Error'),  self.tr('PostGIS Raster Extension not installed in destination DB'))
            
    
    @pyqtSlot()
    def on_btn_upload_clicked(self):
        """
        Slot documentation goes here.
        """
        conn,  password = self.init_DB(self.cmb_db_connections.currentText())
        if not conn:  # invalid DB connection or no connection possible (wrong password etc.)
            return
   
        if self.table_exists(conn,  self.cmb_schema.currentText(),  self.lne_table_name.text()):
            result = QMessageBox.question(
                None,
                self.tr("Table exists"),
                self.tr("""The selected table already exists in the database. Do you want to overwrite the table?"""),
                QMessageBox.StandardButtons(
                    QMessageBox.No |
                    QMessageBox.Yes),
                QMessageBox.No)
            
            if result == QMessageBox.Yes:
                if self.raster_upload(conn):
                    self.message(self.tr('Success'),  self.tr('Raster successful uploaded to database'),  Qgis.Success)
                else:
                    self.message(self.tr('Error'),  self.tr('Upload failed'),  Qgis.Critical)
                    return  # Do not add layer if upload failed
            else:
                self.message(self.tr('PostGIS Raster Import'), self.tr('Upload cancelled'),  Qgis.Warning)
                return  # Do not add layer if upload was cancelled by user
        else:
            if self.raster_upload(conn):
                self.message(self.tr('Success'),  self.tr('Raster successful uploaded to database'),  Qgis.Success)
            else:
                self.message(self.tr('Error'),  self.tr('Upload failed'),  Qgis.Critical)
                return  # Do not add layer if upload failed
        self.progress_bar.setValue(0)
        
        if self.chk_add_raster.isChecked():
            self.load_raster_layer()
        
    
    def raster_upload(self,  conn):
#     If schema doesn't exists in DB create a new schema        
        if self.cmb_schema.currentText() not in self.db_schemas(conn):
            sql = """
            create schema {0}
            """.format(self.cmb_schema.currentText())
            cursor = conn.cursor()
            cursor.execute(sql)
        
        
        layer = self.cmb_map_layer.currentLayer()
        if not layer.crs().isValid():
            QMessageBox.warning(self, self.tr('Warning'),
                                self.tr('Raster has no valid CRS'))
            return False
        if layer.dataProvider().name() == 'gdal':
            raster_to_upload = {
                        'layer': layer,
                        'data_source': layer.source(),
                        'db_name': self.cmb_db_connections.currentText(),
                        'schema_name': self.cmb_schema.currentText(), 
                        'table_name': self.lne_table_name.text(),
                        'geom_column': 'rast'
                    }
            
            with OverrideCursor(Qt.WaitCursor):
                uploader = RasterUpload(conn, self.progress_label, self.progress_bar)
                success = uploader.import_raster(raster_to_upload, self.chk_overviews.isChecked())
            conn.close()
            return success
        else:
            QMessageBox.information(
                self,
                self.tr("Warning"),
                self.tr("""Layers of type {0} are not supported!""".format(layer.dataProvider().name())),
                QMessageBox.StandardButtons(
                    QMessageBox.Ok))
            return False
    
    @pyqtSlot()
    def on_btn_about_clicked(self):
        """
        Slot documentation goes here.
        """
        About().exec_()
    
    @pyqtSlot(str)
    def on_cmb_map_layer_currentIndexChanged(self, p0):
        """
        Slot documentation goes here.
        
        @param p0 DESCRIPTION
        @type str
        """
        self.lne_table_name.setText(self.launder_table_name(p0))
        self.enable_buttons()
        
    def raster_extension_exists(self,  conn):
        sql = 'SELECT extname FROM pg_extension;'
        cursor = conn.cursor()
        cursor.execute(sql)
        conn.commit()
        result = cursor.fetchall()
        
        for extension in result:
            if str(extension) == "('postgis_raster',)":
                return True
                
        return False
            
#    @staticmethod
    def launder_table_name(self,  name):
        # OGRPGDataSource::LaunderName
        # return re.sub(r"[#'-]", '_', unicode(name).lower())
        input_string = str(name).lower().encode('ascii', 'replace')
        input_string = input_string.replace(b" ", b"_")
        input_string = input_string.replace(b".", b"_")
        input_string = input_string.replace(b"-", b"_")
        input_string = input_string.replace(b"'", b"_")
        input_string = input_string.replace(b"(", b"_")
        input_string = input_string.replace(b")", b"_")

        # check if table_name starts with number

        if re.search(r"^\d", input_string.decode('utf-8')):
            input_string = '_'+input_string.decode('utf-8')

        try:
            return input_string.decode('utf-8')
        except:
            return input_string        
            
    def load_raster_layer(self):
                
#['user=hdus', 'password=xxx', 'dbname=raster', 'host=localhost', 'port=5432']
#{'dbname': 'test', 'user': 'postgres', 'port': '5432', 'sslmode': 'prefer'}

        conn, passwd = self.init_DB(self.cmb_db_connections.currentText())
        if not conn:
            self.message(self.tr('PostGIS Raster Import'),
                         self.tr('Could not load raster layer: database connection not available'),
                         Qgis.Warning)
            return

        db_connection_params = conn.get_dsn_parameters()
        if passwd:
            uri_authcfg = 'QconfigId'
            uri_username = '%s' % db_connection_params['user']
            uri_passwd = '%s' % passwd
            # TODO: if service has been used for init_DB, will username+password work here?
        else:  # authentication without Qgis credentials
            uri_authcfg = None
            uri_username = None
            uri_passwd = None  # skip password in uri_config if it is empty string

        uri_config = {
            # database parameters
            'dbname': '%s' % db_connection_params['dbname'],      # The PostgreSQL database to connect to.
            'host': '%s' % db_connection_params['host'],     # The host IP address or localhost.
            'port': '%s' % db_connection_params['port'],          # The port to connect on.
            'sslmode': QgsDataSourceUri.SslDisable, # SslAllow, SslPrefer, SslRequire, SslVerifyCa, SslVerifyFull
            # user and password are not needed if stored in the authcfg or service
            'authcfg': uri_authcfg,  # The QGIS athentication database ID holding connection details.
            'service': None, # TODO: see above    # The PostgreSQL service to be used for connection to the database.
            'username': uri_username,  # The PostgreSQL user name.
            'password': uri_passwd,    # The PostgreSQL password for the user.
            # table and raster column details
            'schema':'%s' % self.cmb_schema.currentText(),      # The database schema that the table is located in.
            'table':'%s' % self.lne_table_name.text(),   # The database table to be loaded.
            'geometrycolumn':'rast',# raster column in PostGIS table
            'sql':None,             # An SQL WHERE clause. It should be placed at the end of the string.
            'key':None,             # A key column from the table.
            'srid':None,            # A string designating the SRID of the coordinate reference system.
            'estimatedmetadata':'False', # A boolean value telling if the metadata is estimated.
            'type':None,            # A WKT string designating the WKB Type.
            'selectatid':None,      # Set to True to disable selection by feature ID.
            'options':None,         # other PostgreSQL connection options not in this list.
            'enableTime': None,
            'temporalDefaultTime': None,
            'temporalFieldIndex': None,
            'mode':'2',             # GDAL 'mode' parameter, 2 unions raster tiles, 1 adds tiles separately (may require user input)
        }
        # remove any NULL parameters
        uri_config = {key:val for key, val in uri_config.items() if val is not None}
        # get the metadata for the raster provider and configure the URI
        md = QgsProviderRegistry.instance().providerMetadata('postgresraster')
        uri = QgsDataSourceUri(md.encodeUri(uri_config))

        # the raster can then be loaded into the project
        rlayer = self.iface.addRasterLayer(uri.uri(False), self.lne_table_name.text(), "postgresraster")        
