# -*- coding: utf-8 -*-
"""
/***************************************************************************
 Streetview_qgis_cej
                                 A QGIS plugin
 Streetview_qgis_cej
 Create Plugin By: https://github.com/Genroy
                              -------------------
        begin                : 2025-05-01
        git sha              : $Format:%H$
        copyright            : (C) 2025 by Thamoon Kedkaew (CeJ)
        Author               : Thamoon Kedkaew (CeJ)
        email                : pongsakornche@gmail.com
 ***************************************************************************/
"""
import os
from qgis.PyQt import QtWidgets, QtWebEngineWidgets, QtCore
from qgis.gui import QgsMapToolEmitPoint
from qgis.core import QgsProject, QgsCoordinateReferenceSystem, QgsCoordinateTransform, QgsMessageLog
from qgis.core import Qgis
from qgis.core import QgsPointXY
from PyQt5.QtWebChannel import QWebChannel
from PyQt5.QtCore import QObject, pyqtSlot



class StreetViewBridge(QObject):
    def __init__(self, plugin_ref):
        super().__init__()
        self.plugin_ref = plugin_ref

    @pyqtSlot(float, float)
    def updatePosition(self, lat, lon):
        QgsMessageLog.logMessage(f"Bridge received: {lat}, {lon}", "StreetView", Qgis.Info)
        if self.plugin_ref.marker:
            self.plugin_ref.marker.setCenter(QgsPointXY(lon, lat))


class StreetViewDockWidget(QtWidgets.QDockWidget):
    def __init__(self, iface, api_key):
        super().__init__("Street View (Interactive)")
        self.iface = iface
        self.api_key = api_key
        
        self.webview = QtWebEngineWidgets.QWebEngineView()
        self.setWidget(self.webview)

        # Show icon.png on initial load
        #icon_path = os.path.join(os.path.dirname(__file__), "panelside")
        icon_html = (
            "<html><body style='text-align:center; background-color:#f5f5f5;'>"
          #  f"<img src='file://{icon_path}' style='margin-top:20px; width:128px;'><br>"
            "<h3>คลิกที่แผนที่เพื่อเริ่มใช้งาน Street View จ้า </h3>"
            "<h3>Click Map canvas Map to open Street View</h3>"
            "<h3>Please Select CRS: WGS84/ESPG:4326 </h3>"
            "</body></html>"
        )
        self.webview.setHtml(icon_html)


        # Setup WebChannel for JS to Python communication
        from PyQt5.QtWebChannel import QWebChannel
        self.channel = QWebChannel()
        self.handler = WebChannelHandler()
        self.handler.iface = self.iface  # pass iface to handler
        self.channel.registerObject('pyHandler', self.handler)
        self.bridge = StreetViewBridge(self)
        self.channel.registerObject("bridge", self.bridge)
        self.webview.page().setWebChannel(self.channel)

        
        iface.addDockWidget(QtCore.Qt.RightDockWidgetArea, self)
        
        self.map_tool = QgsMapToolEmitPoint(iface.mapCanvas())
        self.map_tool.canvasClicked.connect(self.show_street_view)

    def activate_map_tool(self):
        QgsMessageLog.logMessage("Activating map tool...", "StreetView")
        self.iface.mapCanvas().setMapTool(self.map_tool)

    def show_street_view(self, point, button):
        QgsMessageLog.logMessage(f"Point clicked at: {point}", "StreetView")
        crs_src = self.iface.mapCanvas().mapSettings().destinationCrs()
        crs_wgs84 = QgsCoordinateReferenceSystem("EPSG:4326")
        to_wgs84 = QgsCoordinateTransform(crs_src, crs_wgs84, QgsProject.instance())
        from_wgs84 = QgsCoordinateTransform(crs_wgs84, crs_src, QgsProject.instance())

        transformed_point = to_wgs84.transform(point)
        lat = transformed_point.y()
        lon = transformed_point.x()

        # สร้าง marker ถ้ายังไม่มี
        if not hasattr(self, 'marker') or self.marker is None:
            from qgis.gui import QgsVertexMarker
            self.marker = QgsVertexMarker(self.iface.mapCanvas())
            self.marker.setColor(QtCore.Qt.red)
            self.marker.setIconType(QgsVertexMarker.ICON_CROSS)
            self.marker.setIconSize(15)
            self.marker.setPenWidth(3)
            self.marker.setZValue(1000)

            def marker_moved(event):
                new_pos = self.iface.mapCanvas().getCoordinateTransform().toMapCoordinates(
                    event.scenePos().x(), event.scenePos().y())
                dx = new_pos.x() - point.x()
                dy = new_pos.y() - point.y()
                import math
                rad = math.atan2(dy, dx)
                deg = (math.degrees(rad) + 360) % 360
                self.heading = int(deg)
                QgsMessageLog.logMessage(f"New heading: {self.heading}", "StreetView")
                self.show_street_view(new_pos, None)

            self.marker.setFlag(self.marker.ItemIsMovable, True)
            self.marker.setAcceptedMouseButtons(QtCore.Qt.LeftButton)
            self.marker.mouseReleaseEvent = marker_moved

        # แปลง lat/lon กลับเป็น CRS ของ canvas เพื่อ setCenter
        point_canvas = from_wgs84.transform(QgsPointXY(lon, lat))
        self.marker.setCenter(point_canvas)

        # กำหนด heading
        self.heading = getattr(self, 'heading', 0)

        # โหลด HTML แสดง Street View
        with open(os.path.join(os.path.dirname(__file__), "streetview_template.html"), "r", encoding="utf-8") as f:
            html = f.read()
        html = html.replace("{lat}", str(lat)).replace("{lon}", str(lon)).replace("{heading}", str(self.heading)).replace("{api_key}", self.api_key)
        QgsMessageLog.logMessage("HTML Loaded OK", "StreetView", 0)
        QgsMessageLog.logMessage(f"Lat: {lat}, Lon: {lon}, Heading: {self.heading}", "StreetView", 0)
        self.webview.setHtml(html)
        QgsMessageLog.logMessage("Street View loaded in webview.", "StreetView")

class StreetViewQGISCej:
    def __init__(self, iface):
        self.iface = iface
        self.widget = None
        self.action = None

    def initGui(self):
        self.action = QtWidgets.QAction("OpenStreetView", self.iface.mainWindow())
        self.action.triggered.connect(self.open_street_view)
        self.iface.addToolBarIcon(self.action)
        self.iface.addPluginToMenu("&Street View Plugin", self.action)

    def unload(self):
        if self.action:
            self.iface.removePluginMenu("&Street View Plugin", self.action)
            self.iface.removeToolBarIcon(self.action)
        if self.widget:
            self.iface.removeDockWidget(self.widget)
            self.widget = None

    def open_street_view(self):
        if not self.widget:
            api_key = 'AIzaSyDpCovemQ8nDjZfe5am3WexZSH_OmsR1ZI'
            self.widget = StreetViewDockWidget(self.iface, api_key)
        self.widget.show()
        self.widget.activate_map_tool()



from PyQt5.QtWebChannel import QWebChannel
from PyQt5.QtCore import QObject, pyqtSlot

class WebChannelHandler(QObject):
    @pyqtSlot(float, float)
    @pyqtSlot(float, float)
    def updatePosition(self, lat, lon):
        from qgis.core import QgsPointXY, QgsCoordinateReferenceSystem, QgsCoordinateTransform, QgsProject
        point_wgs = QgsPointXY(lon, lat)
        crs_src = QgsCoordinateReferenceSystem("EPSG:4326")
        crs_dest = self.iface.mapCanvas().mapSettings().destinationCrs()
        transform = QgsCoordinateTransform(crs_src, crs_dest, QgsProject.instance())
        point_canvas = transform.transform(point_wgs)

        if hasattr(self, 'marker') and self.marker:
            self.marker.setCenter(point_canvas)