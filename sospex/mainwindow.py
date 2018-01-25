#!/usr/bin/env python
import sys,os
import numpy as np
from PyQt5.QtWidgets import (QApplication, QWidget, QMainWindow, QTabWidget, QTabBar,QHBoxLayout,
                             QGroupBox, QVBoxLayout, QSizePolicy, QStatusBar, QSplitter,
                             QToolBar, QAction, QFileDialog,  QTableView, QComboBox, QAbstractItemView,
                             QToolButton, QMessageBox, QPushButton, QInputDialog, QDialog, QProgressDialog, QLabel,
                             QCheckBox, QButtonGroup, QAbstractButton, QSplashScreen)
from PyQt5.QtGui import QIcon, QStandardItem, QStandardItemModel, QPixmap, QMovie
from PyQt5.QtCore import Qt, QSize, QTimer, QThread, QObject, pyqtSignal

import matplotlib
matplotlib.use('Qt5Agg')
from matplotlib.widgets import SpanSelector, PolygonSelector, RectangleSelector, EllipseSelector, LassoSelector
from matplotlib.patches import Ellipse, Rectangle, Circle, Ellipse, Polygon
from matplotlib.path import Path

import time

import warnings
# To avoid excessive warning messages
warnings.filterwarnings('ignore')

# Local imports
#from sospex.graphics import  NavigationToolbar, ImageCanvas, ImageHistoCanvas, SpectrumCanvas, cmDialog
from sospex.apertures import photoAperture,PolygonInteractor, EllipseInteractor, RectangleInteractor
#from sospex.specobj import specCube, Spectrum
#from sospex.cloud import cloudImage

from graphics import  NavigationToolbar, ImageCanvas, ImageHistoCanvas, SpectrumCanvas, cmDialog
#from apertures import photoAperture,PolygonInteractor, EllipseInteractor, RectangleInteractor
from specobj import specCube,Spectrum
from cloud import cloudImage

class UpdateTabs(QObject):
#    from sospex.cloud import cloudImage
    newImage = pyqtSignal([cloudImage])

class DownloadThread(QThread):
    """ Thread to download images from web archives """

    updateTabs = UpdateTabs()
    sendMessage = pyqtSignal([str])

    def __init__(self,lon,lat,xsize,ysize,band, parent = None):
        super().__init__(parent)
        #super().__init__()
        self.lon = lon
        self.lat = lat
        self.xsize = xsize
        self.ysize = ysize
        self.band = band
        self.parent = parent

    def run(self):
#        from sospex.cloud import cloudImage

        downloadedImage = cloudImage(self.lon,self.lat,self.xsize,self.ysize,self.band)
        if downloadedImage.data is not None:
            self.updateTabs.newImage.emit(downloadedImage)
            message = 'New image downloaded'
        else:
            message = 'The selected survey does not cover the displayed image'
        print(message)
        self.sendMessage.emit(message)
        # Disconnect signal at the end of the thread
        self.updateTabs.newImage.disconnect()
        
# Does not work since calls for matplotlib threads
class ContoursThread(QThread):
    """ Thread to compute new contour and add it to the existing collection """

    updateOtherContours = pyqtSignal([int])

    def __init__(self, ic0, level, n, i0, parent=None):
        super().__init__(parent)
        self.ic0 = ic0
        self.level = level
        self.n = n
        self.i0 = i0

    def run(self):
        if self.n > 1000:
            self.n -= 1000
            new = self.ic0.axes.contour(self.ic0.oimage, self.level, colors='cyan')
            # Insert new contour in the contour collection
            #print("insert new contour")
            contours = self.ic0.contour.collections
            contours.insert(self.n,new.collections[0])
        else:
            new = self.ic0.axes.contour(self.ic0.oimage, self.level, colors='cyan')
            # Update the collection
            #print("update contour")
            self.ic0.contour.collections[self.n] = new.collections[0]
        self.updateOtherContours.emit(self.i0)
        
        
class GUI (QMainWindow):
 
    def __init__(self):
        super().__init__()
        self.title = 'SOSPEX: SOFIA Spectrum Explorer'
        self.left = 10
        self.top = 10
        self.width = 640
        self.height = 480

        # Avoid Python deleting object in unpredictable order on exit
        self.setAttribute(Qt.WA_DeleteOnClose)

        # Default color map for images
        self.colorMap = 'gist_heat'
        self.colorMapDirection = '_r'
        
        # Get the path of the package
        self.path0, file0 = os.path.split(__file__)
        # Define style
        with open(self.path0+'/yellow-stylesheet.css',"r") as fh:
            self.setStyleSheet(fh.read())

            
        self.initUI()
 
    def initUI(self):
        """ Define the user interface """
        
        self.setWindowTitle(self.title)
        #self.setWindowIcon(QIcon(self.path0+'/icons/sospex.png'))
        self.setGeometry(self.left, self.top, self.width, self.height)

        # Create main widget
        wid = QWidget()
        self.setCentralWidget(wid)

        # Main layout is horizontal
        mainLayout = QHBoxLayout()

        # Horizontal splitter
        self.hsplitter = QSplitter(Qt.Horizontal)
        
        # Create main panels
        self.createImagePanel()
        self.createSpectralPanel()

        # Add panels to splitter
        self.hsplitter.addWidget(self.imagePanel)
        self.hsplitter.addWidget(self.spectralPanel)

        # Add panels to main layout
        mainLayout.addWidget(self.hsplitter)
        wid.setLayout(mainLayout)
        self.show()

        # Timer for periodical events
        self.timer = QTimer(self)
        self.timer.timeout.connect(self.blinkTab)

        # Load lines
        from sospex.lines import define_lines
        self.Lines = define_lines()

        # Welcome message
        self.welcomeMessage()

        # Menu
        self.createMenu()
        
    def welcomeMessage(self):
        self.wbox = QMessageBox()
        pixmap = QPixmap(self.path0+'/icons/sospex.png')
        self.wbox.setIconPixmap(pixmap)
        self.wbox.setText("Welcome to SOSPEX")
        #spath = "{:s}/icons/".format(self.path0)
        #self.wbox.setInformativeText('SOFIA Spectrum Explorer\n\n * Click on <img src="'+spath+'open.png"> to load spectra\n\n'+\
        self.wbox.setInformativeText('SOFIA Spectrum Explorer\n\n * Click on folder icon to load spectra\n\n'+\
                                     '* Click on running men icon to exit\n\n'+\
                                     '* Click on question mark for further help')
        self.wbox.show()
        
    def createMenu(self):

        bar = self.menuBar()
        file = bar.addMenu("File")
        quit = QAction("Quit",self,shortcut='Ctrl+q',triggered=self.fileQuit)
        file.addAction(quit)
        new = QAction("New",self,shortcut='Ctrl+n',triggered=self.newFile)
        file.addAction(new)

        help = bar.addMenu("Help")
        about = QAction('About', self, shortcut='Ctrl+a',triggered=self.about)
        help.addAction(about)
        tutorials = QAction('Tutorials', self, shortcut='Ctrl+T',triggered=self.onHelp)
        help.addAction(tutorials)

        bar.setNativeMenuBar(False)

    def about(self):
        # Get path of the package
        file=open(self.path0+"/copyright.txt","r")
        message=file.read()
        QMessageBox.about(self, "About", message)

    def createImagePanel(self):
        """ Panel to display images """

        #self.imagePanel = QGroupBox("")
        self.imagePanel = QWidget()
        layout = QVBoxLayout(self.imagePanel)
        
        # Tabs with images        
        self.itabs = QTabWidget()
        self.itabs.setTabsClosable(True)
        self.itabs.tabCloseRequested.connect(self.removeTab)
        #self.itabs.setSizePolicy(QSizePolicy.Expanding,QSizePolicy.Expanding)
        self.itabs.setSizePolicy(QSizePolicy.Minimum,QSizePolicy.Minimum)
        self.itabs.currentChanged.connect(self.onITabChange)  # things to do when changing tab
        self.tabi = []
        self.ici  = []
        self.ihi  = []
        self.ihcid = []
        self.icid1 = []
        self.icid2 = []
        self.icid3 = []

        
        # Add widgets to panel
        layout.addWidget(self.itabs)
        

    def addSpectrum(self,b):
        #from sospex.graphics import SpectrumCanvas
        #from graphics import SpectrumCanvas
        ''' Add a tab with an image '''
        t = QWidget()
        t.layout = QVBoxLayout(t)
        t.setSizePolicy(QSizePolicy.Ignored,QSizePolicy.Ignored) # Avoid expansion
        self.stabs.addTab(t, b)
        sc = SpectrumCanvas(t, width=11, height=10.5, dpi=100)
        #ih.setVisible(False)
        # Toolbar
        toolbar = QToolBar()
        # Add actions to toolbar
        toolbar.addAction(self.sliceAction)
        toolbar.addAction(self.cutAction)
        #toolbar.addAction(self.maskAction)
        toolbar.addAction(self.specAction)
        toolbar.addAction(self.guessAction)
        toolbar.addSeparator()
        toolbar.addSeparator()
        toolbar.addAction(self.hresizeAction)
        toolbar.addAction(self.vresizeAction)


        
        # Navigation toolbar
        sc.toolbar = NavigationToolbar(sc, self)

        foot = QWidget()
        foot.layout = QHBoxLayout(foot)
        foot.layout.addWidget(toolbar)
        foot.layout.addWidget(sc.toolbar)

        t.layout.addWidget(sc)
        t.layout.addWidget(foot)
        self.stabs.resize(self.stabs.minimumSizeHint())  # Avoid expansion
        # connect image and histogram to  events
        scid1=sc.mpl_connect('button_release_event', self.onDraw2)
        scid2=sc.mpl_connect('scroll_event',self.onWheel2)
        scid3=sc.mpl_connect('key_press_event',self.onKeyPress2)
        scid4=sc.mpl_connect('key_release_event',self.onKeyRelease2)
        self.shiftIsHeld = False
        return t,sc,scid1,scid2,scid3,scid4

    def addImage(self,b):
        #from sospex.graphics import ImageCanvas, ImageHistoCanvas
        #from graphics import ImageCanvas, ImageHistoCanvas
        ''' Add a tab with an image '''
        t = QWidget()
        t.layout = QVBoxLayout(t)
        t.setSizePolicy(QSizePolicy.Ignored,QSizePolicy.Ignored) # Avoid expansion
        self.itabs.addTab(t, b)
        ic = ImageCanvas(t, width=11, height=10.5, dpi=100)
        ih = ImageHistoCanvas(t, width=11, height=0.5, dpi=100)
        ih.setVisible(False)
        ic.toolbar = NavigationToolbar(ic, self)

        # Toolbar
        toolbar = QToolBar()
        toolbar.addAction(self.levelsAction)
        toolbar.addAction(self.cmapAction)
        toolbar.addAction(self.blinkAction)
        toolbar.addAction(self.contoursAction)
        toolbar.addAction(self.momentAction)
        toolbar.addAction(self.cropAction)
        toolbar.addAction(self.cloudAction)
        toolbar.addAction(self.fitsAction)
        toolbar.addAction(self.fitregionAction)
        toolbar.addSeparator()
        #toolbar.addWidget(self.apertureAction)        

        # Foot
        foot = QWidget()
        foot.layout = QHBoxLayout(foot)
        foot.layout.addWidget(toolbar)
        foot.layout.addWidget(ic.toolbar)
        
        #ic.toolbar.pan('on')
        t.layout.addWidget(ic)
        t.layout.addWidget(ih)
        t.layout.addWidget(foot)
        self.itabs.resize(self.itabs.minimumSizeHint())  # Avoid expansion
        # connect image and histogram to  events
        cidh=ih.limSignal.connect(self.onChangeIntensity)
        cid1=ic.mpl_connect('button_release_event', self.onDraw)
        cid2=ic.mpl_connect('scroll_event',self.onWheel)
        cid3=ic.mpl_connect('motion_notify_event', self.onMotion)

        return t,ic,ih,cidh,cid1,cid2,cid3

    def removeTab(self, itab):
        #print('Removing image tab no ',itab)
        widget = self.itabs.widget(itab)
        if widget is not None:
            widget.deleteLater()
        self.itabs.removeTab(itab)
        # Disconnect and remove canvases
        tab = self.tabi[itab]
        ima = self.ici[itab]
        his = self.ihi[itab]
        hcid = self.ihcid[itab]
        c1 = self.icid1[itab]
        c2 = self.icid2[itab]
        c3 = self.icid3[itab]
        his.mpl_disconnect(hcid)
        ima.mpl_disconnect(c1)
        ima.mpl_disconnect(c2)
        ima.mpl_disconnect(c3)
        self.tabi.remove(tab)
        self.ici.remove(ima)
        self.ihi.remove(his)
        self.ihcid.remove(hcid)
        self.icid1.remove(c1)
        self.icid2.remove(c2)
        self.icid3.remove(c3)
        ima = None
        his = None
        # Remove band from band list
        del self.bands[itab]
        
    def removeSpecTab(self, stab):
        #print('Removing spectral tab no ',stab)
        if stab > 0:
            # Once the tab is removed, also the relative aperture should be removed
            itab = self.itabs.currentIndex()
            ic0 = self.ici[itab]
            n = stab-1
            #print('removing aperture ',n,' type: ',ic0.photApertures[n].type)
            for ic in self.ici:
                ap = ic.photApertures[n]
                aps = ic.photApertureSignal[n]
                #print('removing the aperture: ',ap.type)
                ap.mySignal.disconnect()
                ap.disconnect()
                del ic.photApertureSignal[n]
                del ic.photApertures[n]
            # Remove photoAperture
            del self.photoApertures[n]
            # Redraw apertures
            ic0.fig.canvas.draw_idle()
        # Remove tab
        widget = self.stabs.widget(stab)
        if widget is not None:
            widget.deleteLater()
        self.stabs.removeTab(stab)
        # Disconnect and remove canvases
        tab = self.stabi[stab]
        spec = self.sci[stab]
        c1 = self.scid1[stab]
        c2 = self.scid2[stab]
        c3 = self.scid3[stab]
        c4 = self.scid4[stab]
        spec.mpl_disconnect(c1)
        spec.mpl_disconnect(c2)
        spec.mpl_disconnect(c3)
        spec.mpl_disconnect(c4)
        self.stabi.remove(tab)
        self.sci.remove(spec)
        self.scid1.remove(c1)
        self.scid2.remove(c2)
        self.scid3.remove(c3)
        self.scid4.remove(c4)
        spec = None
        # Rename aperture tabs
        if len(self.stabs)> 1:
            for i in range(1,len(self.stabs)):
                apname = "{:d}".format(i-1)
                self.stabs.setTabText(i,apname)
                
    def onITabChange(self, itab):
        ''' When tab changes check if latest update of ellipse are implemented '''

        if itab < len(self.ici):
            ima = self.ici[itab]
            if len(self.stabs) > 1:
                # Check if vertices are activated correctly
                istab = self.stabs.currentIndex()
                nap = len(self.stabs)-1
                n = istab-1  # aperture number
                # Activate interactor (toogle on) and disactivate
                for iap in range(nap):
                    ap = ima.photApertures[iap]
                    if iap == n:
                        ap.showverts = True
                    else:
                        ap.showverts = False
                    ap.updateMarkers()
                    ap.line.set_visible(ap.showverts)
                ima.changed = True
            if ima.changed:
                ima.fig.canvas.draw_idle()
                ima.changed = False
            if self.blink == 'select':
                # Select 2nd tab and start blinking until blink status changes ...
                self.btab[1] = itab
                self.blink = 'on'
                self.timer.start(1000)
        
    def onChangeIntensity(self, event):
        itab = self.itabs.currentIndex()
        ic = self.ici[itab]
        ih = self.ihi[itab]
        # apply intensity limits to the relative figure
        ic.image.set_clim(ih.limits)
        ic.fig.canvas.draw_idle()

    def onHelp(self, event):
        import webbrowser

        webbrowser.open('file://'+os.path.abspath(self.path0+'/help/Help.html'))


    def onIssue(self, event):
        import webbrowser
        
        webbrowser.open('https://github.com/darioflute/sospex/issues')

    def onMotion(self, event):
        """ Update spectrum when moving an aperture on the image """

        pass
        
        # itab = self.itabs.currentIndex()
        # ic = self.ici[itab]

        # if ic.toolbar._active == 'PAN':
        #     return

        # Grab aperture in the flux image to compute the new fluxes
        # istab = self.stabs.currentIndex()
        # if istab > 0:
        #     sc = self.sci[istab]
        #     s = self.specCube
        #     # I should find a way to know if the aperture has changed
        #     if itab != 0:
        #         self.updateAperture()
        #     aperture = self.ici[0].photApertures[istab-1].aperture
        #     path = aperture.get_path()
        #     transform = aperture.get_patch_transform()
        #     npath = transform.transform_path(path)
        #     inpoints = s.points[npath.contains_points(s.points)]
        #     xx,yy = inpoints.T
        
        #     fluxAll = np.nansum(s.flux[:,yy,xx], axis=1)
        #     if s.instrument == 'GREAT':
        #         sc.updateSpectrum(fluxAll)
        #     elif s.instrument == 'FIFI-LS':
        #         ufluxAll = np.nansum(s.uflux[:,yy,xx], axis=1)
        #         expAll = np.nansum(s.exposure[:,yy,xx], axis=1)
        #         sc.updateSpectrum(fluxAll,uf=ufluxAll,exp=expAll)

    def updateAperture(self):

        itab = self.itabs.currentIndex()
        ic = self.ici[itab]
        ic0 = self.ici[0]
        nap = self.stabs.currentIndex()-1

        aper = ic.photApertures[nap]
        aper0 = ic0.photApertures[nap]

        if aper.type == 'Polygon':
            verts = aper.poly.get_xy()
            adverts = np.array([(ic.wcs.all_pix2world(x,y,1)) for (x,y) in verts])                
            verts = [(ic0.wcs.all_world2pix(ra,dec,1)) for (ra,dec) in adverts]
            aper0.poly.set_xy(verts)
        elif aper.type == 'Ellipse' or aper.type == 'Circle':
            x0,y0 = aper.ellipse.center
            w0    = aper.ellipse.width
            h0    = aper.ellipse.height
            angle = aper.ellipse.angle
            ra0,dec0 = ic.wcs.all_pix2world(x0,y0,1)
            ws = w0 * ic.pixscale; hs = h0 * ic.pixscale
            x0,y0 = ic0.wcs.all_world2pix(ra0,dec0,1)
            w0 = ws/ic0.pixscale; h0 = hs/ic0.pixscale
            aper0.ellipse.center = x0,y0
            aper0.ellipse.width = w0
            aper0.ellipse.height = h0
            aper0.ellipse.angle = angle
        if aper.type == 'Rectangle' or aper.type == 'Square':
            x0,y0 = aper.rect.get_xy()
            w0    = aper.rect.get_width()
            h0    = aper.rect.get_height()
            angle = aper.rect.angle
            ra0,dec0 = ic.wcs.all_pix2world(x0,y0,1)
            ws = w0 * ic.pixscale; hs = h0 * ic.pixscale
            x0,y0 = ic0.wcs.all_world2pix(ra0,dec0,1)
            w0 = ws/ic0.pixscale; h0 = hs/ic0.pixscale
            aper0.rect.set_xy((x0,y0))
            aper0.rect.set_width(w0)
            aper0.rect.set_height(h0)
            aper0.rect.angle = angle
        
    def onRemoveAperture(self,event):
        """ Interpret signal from apertures """
        
        itab = self.itabs.currentIndex()
        istab = self.stabs.currentIndex()
        n = istab-1
        ap = self.ici[itab].photApertures[n]
        apertype = ap.__class__.__name__

        if (event == 'rectangle deleted' and apertype == 'RectangleInteractor') or \
           (event == 'ellipse deleted' and apertype == 'EllipseInteractor') \
           or (event == 'polygon deleted' and apertype == 'PolygonInteractor'):
            # Check if polygon
            self.stabs.currentChanged.disconnect()
            self.removeSpecTab(istab)
            self.stabs.setCurrentIndex(0)
            self.stabs.currentChanged.connect(self.onSTabChange)
        else:
            print(event)


    def onModifiedAperture(self, event):
        """ Update spectrum when aperture is modified """

        itab = self.itabs.currentIndex()
        ic = self.ici[itab]

        # Grab aperture in the flux image to compute the new fluxes
        istab = self.stabs.currentIndex()
        if istab > 0:
            sc = self.sci[istab]
            s = self.specCube
            # I should find a way to know if the aperture has changed
            if itab != 0:
                self.updateAperture()
            aperture = self.ici[0].photApertures[istab-1].aperture
            path = aperture.get_path()
            transform = aperture.get_patch_transform()
            npath = transform.transform_path(path)
            inpoints = s.points[npath.contains_points(s.points)]
            xx,yy = inpoints.T
            npoints = np.size(xx)
            
            fluxAll = np.nansum(s.flux[:,yy,xx], axis=1)
            sc.spectrum.flux = fluxAll
            if s.instrument == 'GREAT':
                sc.updateSpectrum(fluxAll)
            elif s.instrument == 'PACS':
                expAll = np.nansum(s.exposure[:,yy,xx], axis=1)
                sc.updateSpectrum(fluxAll,exp=expAll)
            elif s.instrument == 'FIFI-LS':
                ufluxAll = np.nansum(s.uflux[:,yy,xx], axis=1)
                expAll = np.nansum(s.exposure[:,yy,xx], axis=1)
                sc.spectrum.uflux = ufluxAll
                sc.updateSpectrum(fluxAll,uf=ufluxAll,exp=expAll)
        
            
    def onDraw(self,event):
        
        itab = self.itabs.currentIndex()
        ic = self.ici[itab]

        # Deselect pan option on release of mouse
        if ic.toolbar._active == "PAN":
            ic.toolbar.pan()

        # Update patch in all the images
        # a status should be added to the apertures to avoid unnecessary redrawings
        istab = self.stabs.currentIndex()
        ici = self.ici.copy()
        ici.remove(ic)
        if istab != 0 and len(ici) > 0:
            aper = ic.photApertures[istab-1]
            #apertype = aper.__class__.__name__
            if aper.type == 'Ellipse' or aper.type == 'Circle':
                x0,y0 = aper.ellipse.center
                w0    = aper.ellipse.width
                h0    = aper.ellipse.height
                angle = aper.ellipse.angle
                ra0,dec0 = ic.wcs.all_pix2world(x0,y0,1)
                ws = w0 * ic.pixscale; hs = h0 * ic.pixscale
                for ima in ici:
                    x0,y0 = ima.wcs.all_world2pix(ra0,dec0,1)
                    w0 = ws/ima.pixscale; h0 = hs/ima.pixscale
                    ap = ima.photApertures[istab-1]
                    ap.ellipse.center = x0,y0
                    ap.ellipse.width = w0
                    ap.ellipse.height = h0
                    ap.ellipse.angle = angle
                    ap.updateMarkers()
                    ima.changed = True
            if aper.type == 'Rectangle' or aper.type == 'Square':
                x0,y0 = aper.rect.get_xy()
                w0    = aper.rect.get_width()
                h0    = aper.rect.get_height()
                angle = aper.rect.angle
                ra0,dec0 = ic.wcs.all_pix2world(x0,y0,1)
                ws = w0 * ic.pixscale; hs = h0 * ic.pixscale
                for ima in ici:
                    x0,y0 = ima.wcs.all_world2pix(ra0,dec0,1)
                    w0 = ws/ima.pixscale; h0 = hs/ima.pixscale
                    ap = ima.photApertures[istab-1]
                    ap.rect.set_xy((x0,y0))
                    ap.rect.set_width(w0)
                    ap.rect.set_height(h0)
                    ap.rect.angle = angle
                    ap.updateMarkers()
                    ima.changed = True
            elif aper.type == 'Polygon':
                verts = aper.poly.get_xy()
                adverts = np.array([(ic.wcs.all_pix2world(x,y,1)) for (x,y) in verts])                
                for ima in ici:
                    verts = [(ima.wcs.all_world2pix(ra,dec,1)) for (ra,dec) in adverts]
                    ap = ima.photApertures[istab-1]
                    ap.poly.set_xy(verts)
                    ap.updateMarkers()
                    ima.changed = True

            

    def onWheel(self,event):
        ''' enable zoom with mouse wheel and propagate changes to other tabs '''
        eb = event.button
        itab = self.itabs.currentIndex()
        ic = self.ici[itab]
        curr_xlim = ic.axes.get_xlim()
        curr_ylim = ic.axes.get_ylim()
        curr_x0 = (curr_xlim[0]+curr_xlim[1])*0.5
        curr_y0 = (curr_ylim[0]+curr_ylim[1])*0.5
        if eb == 'up':
            factor=0.9
        elif eb == 'down':
            factor=1.1
        #print('zooming by a factor ',factor)
        new_width = (curr_xlim[1]-curr_xlim[0])*factor*0.5
        new_height= (curr_ylim[1]-curr_ylim[0])*factor*0.5
        x = [curr_x0-new_width,curr_x0+new_width]
        y = [curr_y0-new_height,curr_y0+new_height]
        ic.axes.set_xlim(x)
        ic.axes.set_ylim(y)
        ic.fig.canvas.draw_idle()
        ici = self.ici.copy()
        ici.remove(ic)
        ra,dec = ic.wcs.all_pix2world(x,y,1)
        for ima in ici:
            x,y = ima.wcs.all_world2pix(ra,dec,1)
            ima.axes.set_xlim(x)
            ima.axes.set_ylim(y)
            ima.changed = True

    def onDraw2(self,event):
        stab = self.stabs.currentIndex()        
        sc = self.sci[stab]
        if sc.spectrum.redshift != self.specCube.redshift:
            flags = QMessageBox.Yes 
            flags |= QMessageBox.No
            question = "Do you want to update the redshift ?"
            response = QMessageBox.question(self, "Question",
                                                  question,
                                                  flags)            
            if response == QMessageBox.Yes:
                self.sb.showMessage("Updating the redshift ", 2000)
                self.specCube.redshift = sc.spectrum.redshift
            elif QMessageBox.No:
                self.sb.showMessage("Redshift value unchanged ", 2000)
                sc.spectrum.redshift = self.specCube.redshift
                for annotation in sc.annotations:
                    annotation.remove()
                sc.zannotation.remove()
                sc.lannotation.remove()
                sc.drawSpectrum()
                sc.fig.canvas.draw_idle()
            else:
                pass           
        if sc.spectrum.l0 != self.specCube.l0:
            flags = QMessageBox.Yes 
            flags |= QMessageBox.No
            question = "Do you want to update the reference wavelength ?"
            response = QMessageBox.question(self, "Question",
                                                  question,
                                                  flags)            
            if response == QMessageBox.Yes:
                self.sb.showMessage("Updating the reference wavelength ", 2000)
                self.specCube.l0 = sc.spectrum.l0
            elif QMessageBox.No:
                self.sb.showMessage("Redshift value unchanged ", 2000)
                sc.spectrum.l0 = self.specCube.l0
                for annotation in sc.annotations:
                    annotation.remove()
                sc.zannotation.remove()
                sc.lannotation.remove()
                sc.drawSpectrum()
                sc.fig.canvas.draw_idle()
            else:
                pass           
            
        # Deselect pan & zoom options on mouse release
        if sc.toolbar._active == "PAN":
            sc.toolbar.pan()
        if sc.toolbar._active == "ZOOM":
            sc.toolbar.zoom()

    def onKeyPress2(self,event):
        #print(event.key)        
        if event.key == 'control':
            self.shiftIsHeld = True

    def onKeyRelease2(self,event):
        if event.key == 'control':
            self.shiftIsHeld = False

            
    def onWheel2(self,event):
        """ Wheel moves right/left the slice defined on spectrum """

        sc = self.sci[self.spectra.index('All')]
        #print('shift: ',self.shiftIsHeld)
        if self.shiftIsHeld:
            if sc.regionlimits is not None:
                eb = event.button
                xmin,xmax = sc.regionlimits
                dx = (xmax-xmin) * 0.5
                
                # Increment region limits
                if eb == 'up':
                    xmin += dx
                    xmax += dx
                elif eb == 'down':
                    xmin -= dx
                    xmax -= dx
                else:
                    pass        
                # redraw images
                self.slice = 'on'
                if sc.xunit == 'THz':
                    c = 299792458.0  # speed of light in m/s
                    xmin, xmax = c/xmax*1.e-6, c/xmin*1.e-6  # Transform in THz as expected by onSelect
                self.onSelect(xmin,xmax)
        else:
            if event.inaxes:
                # zoom/unzoom 
                eb = event.button
                itab = self.itabs.currentIndex()
                sc = self.sci[itab]
                curr_xlim = sc.axes.get_xlim()
                curr_ylim = sc.axes.get_ylim()
                curr_x0 = (curr_xlim[0]+curr_xlim[1])*0.5
                curr_y0 = (curr_ylim[0]+curr_ylim[1])*0.5
                if eb == 'up':
                    factor=0.9
                elif eb == 'down':
                    factor=1.1
                #print('zooming by a factor ',factor)
                new_width = (curr_xlim[1]-curr_xlim[0])*factor*0.5
                new_height= (curr_ylim[1]-curr_ylim[0])*factor*0.5
                sc.xlimits = (curr_x0-new_width,curr_x0+new_width)
                sc.updateXlim()
                sc.ylimits = (curr_y0-new_height,curr_y0+new_height)
                sc.updateYlim()
            

                
    def createSpectralPanel(self):
        """ Panel to plot spectra """

        #self.spectralPanel = QGroupBox("")
        self.spectralPanel = QWidget()
        layout = QVBoxLayout(self.spectralPanel)
        
        
        # Toolbar
        self.createToolbar()

        # Tabs with plots        
        self.stabs = QTabWidget()
        self.stabs.setTabsClosable(True)
        self.stabs.tabCloseRequested.connect(self.removeSpecTab)
        self.stabs.setSizePolicy(QSizePolicy.Expanding,QSizePolicy.Expanding)
        self.stabs.currentChanged.connect(self.onSTabChange)  # things to do when changing tab
        self.stabi = []
        self.sci  = []
        self.scid1 = []
        self.scid2 = []
        self.scid3 = []
        self.scid4 = []
        
        # Status bar
        self.sb = QStatusBar()
        self.sb.showMessage("Click the folder icon to load a cube !", 10000)
        
        # Add widgets to panel
        banner = QWidget()
        banner.layout = QHBoxLayout(banner)
        banner.layout.addWidget(self.tb)
        banner.layout.addWidget(self.sb)

        layout.addWidget(self.stabs)
        layout.addWidget(banner)

        
    def createToolbar(self):
        """ Toolbar with main commands """

        # Toolbar definition
        self.tb = QToolBar()
        self.tb.setMovable(True)
        self.tb.setObjectName('toolbar')

        # Actions
        self.helpAction = self.createAction(self.path0+'/icons/help.png','Help','Ctrl+q',self.onHelp)
        self.issueAction = self.createAction(self.path0+'/icons/issue.png','Report an issue','Ctrl+q',self.onIssue)
        self.quitAction = self.createAction(self.path0+'/icons/exit.png','Quit program','Ctrl+q',self.fileQuit)
        self.startAction = self.createAction(self.path0+'/icons/open.png','Load new observation','Ctrl+n',self.newFile)
        self.levelsAction = self.createAction(self.path0+'/icons/levels.png','Adjust image levels','Ctrl+L',self.changeVisibility)
        self.cmapAction = self.createAction(self.path0+'/icons/rainbow.png','Choose color map','Ctrl+m',self.changeColorMap)
        self.blink = 'off'
        self.blinkAction = self.createAction(self.path0+'/icons/blink.png','Blink between 2 images','Ctrl+B',self.blinkImages)
        self.momentAction = self.createAction(self.path0+'/icons/map.png','Compute moment 0','Ctrl+m',self.zeroMoment)
        self.contours = 'off'
        self.contoursAction = self.createAction(self.path0+'/icons/contours.png','Overlap contours','Ctrl+c',self.overlapContours)
        self.apertureAction = self.createApertureAction()
        self.fitAction = self.createFitAction()
        self.cutAction = self.createAction(self.path0+'/icons/cut.png','Cut part of the cube','Ctrl+k',self.cutCube)
        self.cropAction = self.createAction(self.path0+'/icons/crop.png','Crop the cube','Ctrl+K',self.cropCube)
        self.sliceAction = self.createAction(self.path0+'/icons/slice.png','Select a slice of the cube','Ctrl+K',self.sliceCube)
        self.maskAction =  self.createAction(self.path0+'/icons/mask.png','Mask a slice of the cube','Ctrl+m',self.maskCube)
        self.cloudAction = self.createAction(self.path0+'/icons/cloud.png','Download image from cloud','Ctrl+D',self.selectDownloadImage)
        self.fitsAction =  self.createAction(self.path0+'/icons/download.png','Save the image as a FITS/PNG/JPG/PDF file','Ctrl+S',self.saveFits)
        self.specAction = self.createAction(self.path0+'/icons/download.png','Save the spectrum as a ASCII/FITS/PNG/JPG/PDF file','Ctrl+S',self.saveSpectrum)

        self.vresizeAction = self.createAction(self.path0+'/icons/vresize.png','Resize image vertically','Ctrl+V',self.vresizeSpectrum)
        self.hresizeAction = self.createAction(self.path0+'/icons/hresize.png','Resize image horizontally','Ctrl+H',self.hresizeSpectrum)
        self.guessAction = self.createAction(self.path0+'/icons/guess.png','Draw guess Gaussian fit','Ctrl+g',self.guessLine)
        self.fitregionAction = self.createAction(self.path0+'/icons/fitregion.png','Fit line inside chosen region','Ctrl+f',self.fitRegion)
        
        # Add buttons to the toolbar

        self.spacer = QWidget()
        self.spacer.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)

        self.tb.addAction(self.startAction)
        self.tb.addAction(self.helpAction)
        self.tb.addAction(self.issueAction)
        self.tb.addWidget(self.apertureAction)        
        self.tb.addWidget(self.fitAction)        
        self.tb.addAction(self.quitAction)




    def guessLine(self):
        """ Create a first guess for fitting """
        from moments import SegmentsSelector

        # Similar to defining a region. A Gaussian+offset is defined with two points,
        # limits of the continuum. Other two points define the Gaussian (top and 1-sigma).
        # i: adds a Gaussian component


        self.sb.showMessage("Drag the mouse over the spectrum to select two continuum regions ", 2000)        
        
        #self.continuum = 'one'
        istab = self.stabs.currentIndex()
        sc = self.sci[istab]
        #sc.span.set_active(True)

        self.CS = SegmentsSelector(sc.axes,sc.fig, self.onContinuumSelect)

        

        
        #istab = self.stabs.currentIndex()
        #sc = self.sci[istab]
        #self.LS = LassoSelector(sc.axes, self.onLassoSelect, lineprops=dict(linestyle='-',color='g'),
        #                        useblit=True)#,markerprops=dict(marker='o',mec='g'),vertex_select_radius=15)
        #self.PS = PolygonSelector(sc.axes, self.onLassoSelect, lineprops=dict(linestyle='-',color='g'),
        #                        useblit=True,markerprops=dict(marker='o',mec='g'),vertex_select_radius=15)


    def onContinuumSelect(self, verts):
        from moments import SegmentsInteractor
        
        istab = self.stabs.currentIndex()
        sc = self.sci[istab]
        SI = SegmentsInteractor(sc.axes, verts)
        sc.guess = SI
        cidapm=SI.modSignal.connect(self.onModifiedGuess)


    def onModifiedGuess(self):
        print('modified guess')    
        
    def onLassoSelect(self,verts):
        """ Generate a guess structure based on the lasso selection """
        #path = Path(verts)
        #print('Select the guess')
        #self.disactiveSelectors()
        #self.LS = None
        
    def fitRegion(self):
        """ Fit the guess over a square region """

        # 1) Define region
        # 2) Create 4 tabs (location, scale, dispersion, offset)
        # 3) Run fit on pixels inside region
        # 4) Display fits on 4 planes
        
    
    def createAction(self,icon,text,shortcut,action):
        act = QAction(QIcon(icon),text, self)
        act.setShortcut(shortcut)
        act.triggered.connect(action)
        return act


    
    def createApertureAction(self):
        """ Create combo box for choosing an aperture """

        self.apertures = [['apertures','square','rectangle'],
                     ['circle','ellipse','polygon']]

        self.model = QStandardItemModel()
        for d in self.apertures:                
            row = []
            for text in d:
                item = QStandardItem(QIcon(self.path0+'/icons/'+text+'.png'),"")
                item.setTextAlignment(Qt.AlignCenter)
                if text != 'apertures':
                    item.setToolTip("Choose a "+text)
                else:
                    item.setToolTip("Choose an aperture ")
                #item.setCheckable(True)
                #item.setCheckState(False)
                row.append(item)
            self.model.appendRow(row)

        self.apView = QTableView()
        # Remove headers and grid
        self.apView.verticalHeader().setVisible(False) 
        self.apView.horizontalHeader().setVisible(False)
        self.apView.setShowGrid(False)
        self.apView.setIconSize(QSize(24,24))

        
        apertureAction = QComboBox()
        apertureAction.setToolTip("Choose an aperture\n")
        #apertureAction.SizeAdjustPolicy(QComboBox.AdjustToContentsOnFirstShow)
        apertureAction.SizeAdjustPolicy(QComboBox.AdjustToMinimumContentsLengthWithIcon)
        apertureAction.setIconSize(QSize(24,24))
        apertureAction.setView(self.apView)
        apertureAction.setModel(self.model)
        self.apView.setModel(self.model)
            
        self.apView.resizeColumnsToContents()  # Once defined the model, resize the column width
        self.apView.setSelectionMode(QAbstractItemView.SingleSelection)
        self.apView.setSelectionBehavior(QAbstractItemView.SelectItems)
        #sp = self.apView.sizePolicy()
        #sp.setHorizontalPolicy(QSizePolicy.MinimumExpanding)
        self.apView.setMinimumWidth(120)  
        self.apView.setMinimumHeight(70)  
        #self.apView.setSizePolicy(sp)
        apertureAction.activated.connect(self.chooseAperture)

        return apertureAction

    def createFitAction(self):
        """ Create combo box for choosing an aperture """

        self.fitoptions = [['gaussfit','continuum','list'],
                           ['location','dispersion','check']]

        self.fmodel = QStandardItemModel()
        for d in self.fitoptions:                
            row = []
            for text in d:
                item = QStandardItem(QIcon(self.path0+'/icons/'+text+'.png'),"")
                item.setTextAlignment(Qt.AlignCenter)
                if text == 'gaussfit':
                    item.setToolTip("Choose an option")
                elif text == 'list':
                    item.setToolTip("Select manually all the constrains")
                elif text == 'check':
                    item.setToolTip("Fit all over the cube")
                else:
                    item.setToolTip("Constrain the "+text)
                row.append(item)
            self.fmodel.appendRow(row)

        self.fitView = QTableView()
        # Remove headers and grid
        self.fitView.verticalHeader().setVisible(False) 
        self.fitView.horizontalHeader().setVisible(False)
        self.fitView.setShowGrid(False)
        self.fitView.setIconSize(QSize(24,24))

        
        fitAction = QComboBox()
        fitAction.setToolTip("Fit line and continuum (under construction)\n")
        #apertureAction.SizeAdjustPolicy(QComboBox.AdjustToContentsOnFirstShow)
        fitAction.SizeAdjustPolicy(QComboBox.AdjustToMinimumContentsLengthWithIcon)
        fitAction.setIconSize(QSize(24,24))
        fitAction.setView(self.fitView)
        fitAction.setModel(self.fmodel)
        self.fitView.setModel(self.fmodel)
            
        self.fitView.resizeColumnsToContents()  # Once defined the model, resize the column width
        self.fitView.setSelectionMode(QAbstractItemView.SingleSelection)
        self.fitView.setSelectionBehavior(QAbstractItemView.SelectItems)
        self.fitView.setMinimumWidth(120)  
        self.fitView.setMinimumHeight(70)  

        fitAction.activated.connect(self.chooseFitOption)

        return fitAction


    
    def onPolySelect(self, verts):
        #from sospex.apertures import PolygonInteractor

        self.disactiveSelectors()
        # 1 vertices in RA,Dec coords
        itab = self.itabs.currentIndex()
        ic0 = self.ici[itab]
        adverts = np.array([(ic0.wcs.all_pix2world(x,y,1)) for (x,y) in verts])
        # Save aperture with vertices in ra,dec coordinates
        n = len(self.photoApertures)
        self.photoApertures.append(photoAperture(n,'polygon',adverts))
        
        for ic in self.ici:
            # First adjust vertices to astrometry (they are in xy coords)
            verts = [(ic.wcs.all_world2pix(ra,dec,1)) for (ra,dec) in adverts]
            poly  = PolygonInteractor(ic.axes, verts)
            ic.photApertures.append(poly)
            cidap=poly.mySignal.connect(self.onRemoveAperture)
            ic.photApertureSignal.append(cidap)
            cidapm=poly.modSignal.connect(self.onModifiedAperture)
        self.PS = None

        self.drawNewSpectrum(n)

    def drawNewSpectrum(self, n):        
        """ Add tab with the flux inside the aperture """

        #from sospex.specobj import Spectrum

        apname = "{:d}".format(n)
        self.spectra.append(apname)
        t,sc,scid1,scid2,scid3,scid4 = self.addSpectrum(apname)
        self.stabi.append(t)
        self.sci.append(sc)
        self.scid1.append(scid1)
        self.scid2.append(scid2)
        self.scid3.append(scid3)
        self.scid4.append(scid4)

        #print('apertures are: ',len(self.ici[0].photApertures))
        #print('current aperture is: ',n)
        
        # Draw spectrum from polygon
        aperture = self.ici[0].photApertures[n].aperture
        path = aperture.get_path()
        transform = aperture.get_patch_transform()
        npath = transform.transform_path(path)
        s = self.specCube
        inpoints = s.points[npath.contains_points(s.points)]
        xx,yy = inpoints.T
        
        fluxAll = np.nansum(s.flux[:,yy,xx], axis=1)
        if s.instrument == 'GREAT':
            spec = Spectrum(s.wave, fluxAll, instrument=s.instrument, redshift=s.redshift, l0=s.l0 )
        elif s.instrument == 'FIFI-LS':
            ufluxAll = np.nansum(s.uflux[:,yy,xx], axis=1)
            expAll = np.nansum(s.exposure[:,yy,xx], axis=1)
            spec = Spectrum(s.wave, fluxAll, uflux= ufluxAll,
                            exposure=expAll, atran = s.atran, instrument=s.instrument,
                            redshift=s.redshift, baryshift = s.baryshift, l0=s.l0)
        elif s.instrument == 'PACS':
            expAll = np.nansum(s.exposure[:,yy,xx], axis=1)
            spec = Spectrum(s.wave, fluxAll, exposure=expAll, instrument=s.instrument, redshift=s.redshift, l0=s.l0 )
            
        sc.compute_initial_spectrum(spectrum=spec)
        self.specZoomlimits = [sc.xlimits,sc.ylimits]
        sc.cid = sc.axes.callbacks.connect('xlim_changed' and 'ylim_changed', self.doZoomSpec)
        # Start the span selector to show only part of the cube
        sc.span = SpanSelector(sc.axes, self.onSelect, 'horizontal', useblit=True,
                               rectprops=dict(alpha=0.5, facecolor='green'))
        sc.span.active = False

        # Select new tab
        self.stabs.setCurrentIndex(n+1)
            
        
    def onRectSelect(self, eclick, erelease):
        'eclick and erelease are the press and release events'
        
        x1, y1 = eclick.xdata, eclick.ydata
        x2, y2 = erelease.xdata, erelease.ydata

        if self.selAp == 'square' or self.selAp == 'rectangle':
            x0=x1;y0=y1
            w  = np.abs(x2-x1)
            h  = np.abs(y2-y1)
        else:
            x0 = (x1+x2)*0.5
            y0 = (y1+y2)*0.5
            w  = np.abs(x2-x1)
            h  = np.abs(y2-y1)

        self.newSelectedAperture(x0,y0,w,h,self.selAp)

    def newSelectedAperture(self, x0, y0, w, h, selAp):
        
        itab = self.itabs.currentIndex()
        ic0 = self.ici[itab]
        r0,d0 = ic0.wcs.all_pix2world(x0,y0,1)
        ws = w*ic0.pixscale; hs = h*ic0.pixscale

        
        n = len(self.photoApertures)
        if selAp == 'square':
            self.disactiveSelectors()
            self.RS = None
            # Define square
            data = [r0,d0,ws]
            self.photoApertures.append(photoAperture(n,'square',data))
            for ic in self.ici:
                x0,y0 = ic.wcs.all_world2pix(r0,d0,1)
                w = ws/ic.pixscale; h = hs/ic.pixscale
                square = RectangleInteractor(ic.axes, (x0,y0), w)
                ic.photApertures.append(square)
                cidap=square.mySignal.connect(self.onRemoveAperture)
                ic.photApertureSignal.append(cidap)
                cidapm=square.modSignal.connect(self.onModifiedAperture)
        elif selAp == 'rectangle':
            self.disactiveSelectors()
            self.RS = None
            # Define rectangle
            data = [r0,d0,ws,hs]
            self.photoApertures.append(photoAperture(n,'rectangle',data))
            for ic in self.ici:
                x0,y0 = ic.wcs.all_world2pix(r0,d0,1)
                w = ws/ic.pixscale; h = hs/ic.pixscale
                rectangle = RectangleInteractor(ic.axes, (x0,y0), w, h)
                ic.photApertures.append(rectangle)
                cidap=rectangle.mySignal.connect(self.onRemoveAperture)
                ic.photApertureSignal.append(cidap)
                cidapm=rectangle.modSignal.connect(self.onModifiedAperture)
        elif selAp == 'circle':
            self.disactiveSelectors()
            self.ES = None
            pass
            # Define circle
            data = [r0,d0,ws]
            self.photoApertures.append(photoAperture(n,'circle',data))
            for ic in self.ici:
                x0,y0 = ic.wcs.all_world2pix(r0,d0,1)
                w = ws/ic.pixscale; h = hs/ic.pixscale
                circle = EllipseInteractor(ic.axes, (x0,y0), w)
                ic.photApertures.append(circle)
                cidap=circle.mySignal.connect(self.onRemoveAperture)
                ic.photApertureSignal.append(cidap)
                cidapm=circle.modSignal.connect(self.onModifiedAperture)
        elif selAp == 'ellipse':
            self.disactiveSelectors()
            self.ES = None
            # Define ellipse
            data = [r0,d0,ws,hs]
            self.photoApertures.append(photoAperture(n,'ellipse',data))
            for ic in self.ici:
                x0,y0 = ic.wcs.all_world2pix(r0,d0,1)
                w = ws/ic.pixscale; h = hs/ic.pixscale
                ellipse = EllipseInteractor(ic.axes, (x0,y0), w, h)
                ic.photApertures.append(ellipse)
                cidap=ellipse.mySignal.connect(self.onRemoveAperture)
                ic.photApertureSignal.append(cidap)
                cidapm=ellipse.modSignal.connect(self.onModifiedAperture)
        self.drawNewSpectrum(n)


    def disactiveSelectors(self):
        """ Disactive all selectors, in the case more than one is selected """
        if self.RS is not None:
            self.RS.set_active(False)
        if self.ES is not None:
            self.ES.set_active(False)
        if self.PS is not None:
            self.PS.set_active(False)
        #if self.LS is not None:
        #    self.LS.set_active(False)

    def chooseFitOption(self, i):
        """ Choosing a fit option """

        index  = self.fitView.selectionModel().currentIndex()
        i = index.row()
        j = index.column()

        self.selFit = self.fitoptions[i][j]
        if self.selFit == 'list':
            self.sb.showMessage("You chose to open the "+self.selFit, 1000)
        if self.selFit == 'check':
            self.sb.showMessage("You chose to compute the fit for all the pixels ", 1000)
        elif self.selFit == 'gaussfit':
            self.sb.showMessage("Choose a fitting option ", 1000)
        else:
            self.sb.showMessage("You chose the action "+self.selFit, 1000)


        #put back to the 0-th item
        self.fitAction.setCurrentIndex(0)

        
    def chooseAperture(self, i):
        """ Choosing an aperture """
        index  = self.apView.selectionModel().currentIndex()
        i = index.row()
        j = index.column()

        self.selAp = self.apertures[i][j]
        if self.selAp == 'ellipse':
            self.sb.showMessage("You chose an "+self.selAp, 1000)
        elif self.selAp == 'apertures':
            self.sb.showMessage("Choose an aperture shape ", 1000)
        else:
            self.sb.showMessage("You chose a "+self.selAp, 1000)

        if len(self.ici) == 0:
            self.sb.showMessage("Start by opening a new image ", 1000)
            self.apertureAction.setCurrentIndex(0)
            return
            
        itab = self.itabs.currentIndex()
        ic = self.ici[itab]
        if self.selAp == 'polygon':
            self.PS = PolygonSelector(ic.axes, self.onPolySelect, lineprops=dict(linestyle='-',color='g'),
                                      useblit=True,markerprops=dict(marker='o',mec='g'),vertex_select_radius=15)
        elif self.selAp == 'rectangle':
            self.RS = RectangleSelector(ic.axes, self.onRectSelect,
                                        drawtype='box', useblit=True,
                                        button=[1, 3],  # don't use middle button
                                        minspanx=5, minspany=5,
                                        spancoords='pixels',
                                        rectprops = dict(facecolor='g', edgecolor = 'g',alpha=0.8, fill=False),
                                        lineprops = dict(color='g', linestyle='-',linewidth = 2, alpha=0.8),
                                        interactive=False)
            self.RS.state.add('center')
        elif self.selAp == 'square':
            self.RS = RectangleSelector(ic.axes, self.onRectSelect,
                                        drawtype='box', useblit=True,
                                        button=[1, 3],  # don't use middle button
                                        minspanx=5, minspany=5,
                                        spancoords='pixels',
                                        rectprops = dict(facecolor='g', edgecolor = 'g',alpha=0.8, fill=False),
                                        lineprops = dict(color='g', linestyle='-',linewidth = 2, alpha=0.8),
                                        interactive=False)
            self.RS.state.add('square')
            self.RS.state.add('center')
        elif self.selAp == 'ellipse':
            self.ES = EllipseSelector(ic.axes, self.onRectSelect,
                                      drawtype='line', useblit=True,
                                      button=[1, 3],  # don't use middle button
                                      minspanx=5, minspany=5,
                                      spancoords='pixels',
                                      rectprops = dict(facecolor='g', edgecolor = 'g',alpha=0.8, fill=False),
                                      lineprops = dict(color='g', linestyle='-',linewidth = 2, alpha=0.8),
                                      interactive=False)
            self.ES.state.add('center')
        elif self.selAp == 'circle':
            self.ES = EllipseSelector(ic.axes, self.onRectSelect,
                                      drawtype='line', useblit=True,
                                      button=[1, 3],  # don't use middle button
                                      minspanx=5, minspany=5,
                                      spancoords='pixels',
                                      rectprops = dict(facecolor='g', edgecolor = 'g',alpha=0.8, fill=False),
                                      lineprops = dict(color='g', linestyle='-',linewidth = 2, alpha=0.8),
                                      interactive=False)
            self.ES.state.add('square')
            self.ES.state.add('center')
        
        if self.selAp != 'apertures':
            ic.fig.canvas.draw_idle()
        #put back to the 0-th item
        self.apertureAction.setCurrentIndex(0)

    def selectDownloadImage(self):
        """ Select the image to download """

        selectDI = QInputDialog()
        selectDI.setStyleSheet("* { font-size: 14pt; }")
        selectDI.setOption(QInputDialog.UseListViewForComboBoxItems)
        selectDI.setWindowTitle("Select image to download")
        selectDI.setLabelText("Selection")
        imagelist = ['local',
                     'sdss-u','sdss-g','sdss-r','sdss-i','sdss-z',
                     'panstarrs-g','panstarrs-r','panstarrs-i','panstarrs-z','panstarrs-y',
                     '2mass-j','2mass-h','2mass-k',
                     'wise1','wise2','wise3','wise4',
                     'first','nvss','sumss']
        selectDI.setComboBoxItems(imagelist)
        select = selectDI.exec_()
        if select == QDialog.Accepted:
            self.downloadImage(selectDI.textValue())

    def downloadImage(self, band):
        """ Download an image covering the cube """

        # Compute center and size of image (in arcmin)
        nz,ny,nx = np.shape(self.specCube.flux)
        lon,lat = self.specCube.wcs.celestial.all_pix2world(ny//2,nx//2, 0)
        xsize = nx * self.specCube.pixscale /60. #size in arcmin
        ysize = ny * self.specCube.pixscale /60. #size in arcmin

        # Compute center and size (arcmin) of the displayed image 
        itab = self.itabs.currentIndex()
        ic = self.ici[itab]
        x = ic.axes.get_xlim()
        y = ic.axes.get_ylim()
        ra,dec = ic.wcs.all_pix2world(x,y,1)
        lon = np.mean(ra)
        lat = np.mean(dec)
        xsize = np.abs(ra[0]-ra[1])*np.cos(lat*np.pi/180.)*60.
        ysize = np.abs(dec[0]-dec[1])*60.
        #print('Band selected is: ',band)


        if band != 'local':
            # Here call the thread
            self.downloadThread = DownloadThread(lon,lat,xsize,ysize,band,parent=self)
            self.downloadThread.updateTabs.newImage.connect(self.newImage)
            self.downloadThread.sendMessage.connect(self.newImageMessage)
            self.downloadThread.start()
            # and start the spinning messagebox
            self.msgbox = QMessageBox()
            #self.msgbox.setIcon(QMessageBox.Information)
            label = QLabel(self.msgbox)
            pixmap = QPixmap(self.path0+'/icons/niet.png')
            label.setPixmap(pixmap)
            movie = QMovie(self.path0+'/icons/spinplane.gif')
            #movie = QMovie(self.path0+'/icons/loader.gif')
            label.setMovie(movie)
            movie.jumpToFrame(0)
            movie.start()
            label.resize(QSize(200,200))
            self.msgbox.setIconPixmap(pixmap)
            self.msgbox.setText("Quering "+band+" ... ")
            retval = self.msgbox.exec_()
        else:
            # Download the local fits
#            from sospex.cloud import cloudImage
            downloadedImage = cloudImage(lon,lat,xsize,ysize,band)
            if downloadedImage.data is not None:
                self.newImageTab(downloadedImage)
                message = 'New image downloaded'
            else:
                message = 'The selected survey does not cover the displayed image'
            self.newImageMessage(message)

        
    def newImageMessage(self, message):
        """ Message sent from download thread """
        
        self.sb.showMessage(message, 5000)
        try:
            self.msgbox.done(1)
        except:
            pass

    def newImage(self, downloadedImage):
        " Save and display "
        self.saveDownloadedFits(downloadedImage)
        self.newImageTab(downloadedImage)
        

    def newImageTab(self, downloadedImage):
        """ Open  a tab and display the new image """

        #print("Adding the new image ...")
        image = downloadedImage.data
        mask = np.isfinite(image)
        if np.sum(mask) == 0:
            self.sb.showMessage("The selected survey does not cover the displayed image", 2000)
        else:
            self.sb.showMessage("Image downloaded", 2000)
            band = downloadedImage.source
            self.bands.append(band)
            t,ic,ih,h,c1,c2,c3 = self.addImage(band)
            self.tabi.append(t)
            self.ici.append(ic)
            self.ihi.append(ih)
            self.ihcid.append(h)
            self.icid1.append(c1)
            self.icid2.append(c2)
            self.icid3.append(c3)
            
            image = downloadedImage.data
            wcs = downloadedImage.wcs

            ic.compute_initial_figure(image=image,wcs=wcs,title=band)
            ih.compute_initial_figure(image=image)
            
            # Align with spectral cube
            ic0 = self.ici[0]
            x = ic0.axes.get_xlim()
            y = ic0.axes.get_ylim()
            ra,dec = ic0.wcs.all_pix2world(x,y,1)
            x,y = ic.wcs.all_world2pix(ra,dec,1)            
            ic.axes.set_xlim(x)
            ic.axes.set_ylim(y)
            ic.changed = True


            # Add existing apertures
            self.addApertures(ic)

            # Add existing contours
            self.addContours(ic)

            # Callback to propagate axes limit changes to other images
            ic.cid = ic.axes.callbacks.connect('xlim_changed' and 'ylim_changed', self.doZoomAll)


    def saveDownloadedFits(self, downloadedImage):
        """ Save the downloaded FITS image """

        from astropy.io import fits
        
        # Dialog to save file
        fd = QFileDialog()
        fd.setNameFilters(["Fits Files (*.fits)","All Files (*)"])
        fd.setOptions(QFileDialog.DontUseNativeDialog)
        fd.setViewMode(QFileDialog.List)
        fd.selectFile(downloadedImage.source+'.fits')
        
        if (fd.exec()):
            fileName = fd.selectedFiles()
            outfile = fileName[0]

            # Check the 
            filename, file_extension = os.path.splitext(outfile)
            
            # Primary header
            image = downloadedImage.data
            wcs   = downloadedImage.wcs
            header = wcs.to_header()
            header.remove('WCSAXES')
            header['OBJECT'] = (self.specCube.objname, 'Object Name')
            hdu = fits.PrimaryHDU(image)
            hdu.header.extend(header)
            hdul = fits.HDUList([hdu])
            hdul.writeto(outfile,overwrite=True) # clobber true  allows rewriting
            hdul.close()

            
    def uploadSpectrum(self, event):
        """
        Upload existing spectrum
        """
        #from sospex.specobj import Spectrum
        
        fd = QFileDialog()
        fd.setNameFilters(["Fits Files (*.fits)","All Files (*)"])
        fd.setOptions(QFileDialog.DontUseNativeDialog)
        fd.setViewMode(QFileDialog.List)
        fd.setFileMode(QFileDialog.ExistingFile)

        if (fd.exec()):
            fileName= fd.selectedFiles()
            #print(fileName[0])
            # Read external spectrum
            self.extSpectrum = ExtSpectrum(filename[0])            
            # Plot over selected tab
            istab = self.stabs.currentIndex()
            sc = self.sci[istab]
            sc.extspecLayer, = sc.axes.plot(self.extSpectrum.wave,self.extSpectrum.flux, color='orange')
            sc.displayExtSpec = True

    def addApertures(self, ic):
        """ Add apertures already defined on new image """
        #from sospex.apertures import 

        ic0 = self.ici[0]
        for aper in ic0.photApertures:
            #apertype = aper.__class__.__name__
            if aper.type == 'Ellipse' or aper.type == 'Circle':
                x0,y0 = aper.ellipse.center
                w0    = aper.ellipse.width
                h0    = aper.ellipse.height
                angle = aper.ellipse.angle
                ra0,dec0 = ic0.wcs.all_pix2world(x0,y0,1)
                ws = w0 * ic0.pixscale; hs = h0 * ic0.pixscale
                # Add ellipse
                x0,y0 = ic.wcs.all_world2pix(ra0,dec0,1)
                w0 = ws/ic.pixscale; h0 = hs/ic.pixscale
                ellipse = EllipseInteractor(ic.axes, (x0,y0),w0,h0,angle)
                ellipse.type = aper.type
                ellipse.showverts = aper.showverts
                ic.photApertures.append(ellipse)
                cidap=ellipse.mySignal.connect(self.onRemoveAperture)
                ic.photApertureSignal.append(cidap)
            elif aper.type == 'Rectangle' or aper.type == 'Square':
                x0,y0 = aper.rect.get_xy()
                w0    = aper.rect.get_width()
                h0    = aper.rect.get_height()
                #print(type(h0))
                angle = aper.rect.angle
                ra0,dec0 = ic0.wcs.all_pix2world(x0,y0,1)
                ws = w0 * ic0.pixscale; hs = h0 * ic0.pixscale
                # Add rectangle
                x0,y0 = ic.wcs.all_world2pix(ra0,dec0,1)
                w0 = ws/ic.pixscale; h0 = hs/ic.pixscale
                rectangle = RectangleInteractor(ic.axes, (x0,y0),w0,h0,angle)
                rectangle.type = aper.type
                rectangle.showverts = aper.showverts
                rectangle.rect.set_xy((x0,y0))
                rectangle.updateMarkers()
                ic.photApertures.append(rectangle)
                cidap=rectangle.mySignal.connect(self.onRemoveAperture)
                ic.photApertureSignal.append(cidap)
            elif aper.type == 'Polygon':
                verts = aper.poly.get_xy()
                adverts = np.array([(ic0.wcs.all_pix2world(x,y,1)) for (x,y) in verts])
                verts = [(ic.wcs.all_world2pix(ra,dec,1)) for (ra,dec) in adverts]
                # Add polygon
                poly = PolygonInteractor(ic.axes,verts)                
                poly.showverts = aper.showverts
                ic.photApertures.append(poly)
                cidap=poly.mySignal.connect(self.onRemoveAperture)
                ic.photApertureSignal.append(cidap)

        

    def blinkTab(self):
        ''' keep switching between two tabs until blink changes state '''
        itab = self.itabs.currentIndex()
        if itab == self.btab[0]:
            i = 1
        else:
            i = 0
        self.itabs.setCurrentIndex(self.btab[i])
        
    def blinkImages(self, event):
        ''' Blink between two images in different tabs or stop blinking'''
        if self.blink == 'off':
            self.btab = [self.itabs.currentIndex(),0]
            self.sb.showMessage("Select another tab to blink / click again to stop blinking", 2000)
            self.blink = 'select'
        else:
            self.blink = 'off'
            self.timer.stop()


        
    def fileQuit(self):
        """ Quitting the program """
        self.close()

        

    def cutCube(self):  
        """ Cut part of the cube """
        self.sb.showMessage("Drag the mouse over the slice of the cube to save ", 2000)
        self.cutcube = 'on'
        istab = self.spectra.index('All')
        self.stabs.setCurrentIndex(istab)
        sc = self.sci[istab]
        #sc.span.set_visible(True)
        sc.span.set_active(True)

        
    def cropCube(self):
        """ Crop part of the cube """
        self.sb.showMessage("Crop the cube using the zoomed image shown ", 2000)

        # Get limits and center
        ic0 = self.ici[0]
        xlimits = ic0.axes.get_xlim()
        ylimits = ic0.axes.get_ylim()
        center =  ((xlimits[0]+xlimits[1])*0.5,(ylimits[0]+ylimits[1])*0.5)
        size = (np.abs((ylimits[1]-ylimits[0]).astype(int)),np.abs((xlimits[1]-xlimits[0]).astype(int)))
        nz,nx,ny = np.shape(self.specCube.flux)
        #print('Size is ',size,nx,ny)
        if size[0] == nx and size[1] == ny:
            self.sb.showMessage("No cropping needed ", 2000)
        else:
            flags = QMessageBox.Yes 
            flags |= QMessageBox.No
            question = "Do you want to crop the part of the cube shown on the image ?"
            response = QMessageBox.question(self, "Question",
                                                  question,
                                                  flags)            
            if response == QMessageBox.Yes:
                self.sb.showMessage("Cropping the cube ", 2000)
                self.cropCube2D(center,size)
                self.saveCube()
            elif QMessageBox.No:
                self.sb.showMessage("Cropping aborted ", 2000)
            else:
                pass

    def cropCube2D(self,center,size):
        """ Generate cropped cube """

        from astropy.nddata import Cutout2D
        ic0 = self.ici[0]
        co = Cutout2D(ic0.oimage,center,size,wcs=ic0.wcs)
        bb = co.bbox_original

        self.specCube.flux = self.specCube.flux[:,bb[0][0]:bb[0][1]+1,bb[1][0]:bb[1][1]+1]
        self.specCube.wcs = co.wcs
        if self.specCube.instrument == 'FIFI-LS':
            self.specCube.eflux = self.specCube.eflux[:,bb[0][0]:bb[0][1]+1,bb[1][0]:bb[1][1]+1]
            self.specCube.uflux = self.specCube.uflux[:,bb[0][0]:bb[0][1]+1,bb[1][0]:bb[1][1]+1]
            self.specCube.euflux = self.specCube.euflux[:,bb[0][0]:bb[0][1]+1,bb[1][0]:bb[1][1]+1]
            self.specCube.x = self.specCube.x[bb[1][0]:bb[1][1]+1]
            self.specCube.y = self.specCube.y[bb[0][0]:bb[0][1]+1]
            self.specCube.exposure = self.specCube.exposure[:,bb[0][0]:bb[0][1]+1,bb[1][0]:bb[1][1]+1]
        # Create a grid of points
        nz,ny,nx = np.shape(self.specCube.flux)
        xi = np.arange(nx); yi = np.arange(ny)
        xi,yi = np.meshgrid(xi,yi)
        self.points = np.array([np.ravel(xi),np.ravel(yi)]).transpose()
        

    def cutCube1D(self,xmin,xmax):
        """ Generate cut cube """

        self.specCube.flux = self.specCube.flux[xmin:xmax,:,:]
        self.specCube.wave = self.specCube.wave[xmin:xmax]
        nz,ny,nx = np.shape(self.specCube.flux)
        #print('new cube z-size is ',nz)
        self.specCube.n = nz
        # Cut the cubes
        if self.specCube.instrument == 'FIFI-LS':
            self.specCube.eflux = self.specCube.eflux[xmin:xmax,:,:]
            self.specCube.uflux = self.specCube.uflux[xmin:xmax,:,:]
            self.specCube.euflux = self.specCube.euflux[xmin:xmax,:,:]
            self.specCube.exposure = self.specCube.exposure[xmin:xmax,:,:]
            self.specCube.atran = self.specCube.atran[xmin:xmax]
            self.specCube.response = self.specCube.response[xmin:xmax]
       
    def saveFits(self):
        """ Save the displayed image as a FITS file """

        from astropy.io import fits
        
        # Dialog to save file
        fd = QFileDialog()
        fd.setNameFilters(["Fits Files (*.fits)","PNG Files (*.png)",
                           "JPG Files (*.jpg)","PDF Files (*.pdf)","All Files (*)"])
        fd.setOptions(QFileDialog.DontUseNativeDialog)
        fd.setViewMode(QFileDialog.List)

        if (fd.exec()):
            fileName = fd.selectedFiles()
            #print(fileName[0])
            outfile = fileName[0]

            itab = self.itabs.currentIndex()
            ic = self.ici[itab]
            band = self.bands[itab]

            if band == 'Flux' or band == 'Uflux' or band == 'Exp':
                instrument = self.specCube.instrument
            else:
                instrument = band

            # Check the 
            filename, file_extension = os.path.splitext(outfile)

            if file_extension == '.fits':
                # Primary header
                header = ic.wcs.to_header()
                header.remove('WCSAXES')
                header['INSTRUME'] = instrument
                header['OBJECT'] = (self.specCube.objname, 'Object Name')
                hdu = fits.PrimaryHDU(ic.oimage)
                hdu.header.extend(header)
                hdul = fits.HDUList([hdu])
                hdul.writeto(outfile,overwrite=True) # clobber true  allows rewriting
                hdul.close()
            elif file_extension == '.png' or file_extension == '.pdf' or file_extension == '.jpg':
                ic.fig.savefig(outfile)
            else:
                message = 'extension has to be *.fits, *.png, *.jpg or *.pdf' 
                print(message)
                self.sb.showMessage(message, 2000)


    def saveSpectrum(self):
        """ Save the displayed spectrum as a FITS/ASCII file or as PNG/PDF image """

        from astropy.io import fits
        
        # Dialog to save file
        fd = QFileDialog()
        fd.setNameFilters(["Fits Files (*.fits)","PNG Files (*.png)","JPG Files (*.jpg)",
                           "PDF Files (*.pdf)","ASCII Files (*.txt)", "CSV Files (*.csv)","All Files (*)"])
        fd.setOptions(QFileDialog.DontUseNativeDialog)
        fd.setViewMode(QFileDialog.List)

        if (fd.exec()):
            fileName = fd.selectedFiles()
            outfile = fileName[0]
            filename, file_extension = os.path.splitext(outfile)

            # Tabs
            istab = self.stabs.currentIndex()
            itab = self.itabs.currentIndex()
            sc = self.sci[istab]
            ic = self.ici[itab]
            n = istab-1

            # Compute area of the aperture
            if n >= 0:
                aperture = self.ici[0].photApertures[n].aperture
                path = aperture.get_path()
                transform = aperture.get_patch_transform()
                npath = transform.transform_path(path)
                s = self.specCube
                inpoints = s.points[npath.contains_points(s.points)]
                npoints = np.size(inpoints)/2
                ps = s.pixscale/3600.
                area = npoints*ps*ps
            
            if file_extension == '.fits':
                # Primary header
                hdu = fits.PrimaryHDU()
                hdu.header['OBJ_NAME'] = (self.specCube.objname, 'Object Name')
                hdu.header['INSTRUME'] = (self.specCube.instrument, 'SOFIA instrument')
                hdu.header['REDSHIFT'] = (self.specCube.redshift, 'Object Redshift')
                if self.specCube.instrument == 'FIFI-LS':
                    hdu.header['BARYSHFT'] = (self.specCube.baryshift, 'Barycentric shift')
                if n >= 0:
                    aper = ic.photApertures[n]
                    if aper.type == 'Ellipse':
                        x0,y0 = aper.ellipse.center
                        pixel = np.array([[x0, y0]], np.float_)
                        world = ic.wcs.wcs_pix2world(pixel, 1)
                        hdu.header['APERTURE']=('Ellipse','Type of photometric aperture')
                        hdu.header['RA'] = (world[0][0], 'RA of aperture center')
                        hdu.header['DEC'] = (world[0][1], 'Dec of aperture center')
                        hdu.header['ANGLE'] = (aper.ellipse.angle, 'Angle of elliptical aperture [degs]')
                        hdu.header['MAJAX'] = (aper.ellipse.width*ic.pixscale, 'Major axis of elliptical aperture [arcsec]')
                        hdu.header['MINAX'] = (aper.ellipse.height*ic.pixscale, 'Minor axis of elliptical aperture [arcsec]')
                    elif aper.type == 'Circle':
                        x0,y0 = aper.ellipse.center
                        pixel = np.array([[x0, y0]], np.float_)
                        world = ic.wcs.wcs_pix2world(pixel, 1)
                        hdu.header['APERTURE']=('Circle','Type of photometric aperture')
                        hdu.header['RA'] = (world[0][0]/15., 'RA of aperture center [hours]')
                        hdu.header['DEC'] = (world[0][1], 'Dec of aperture center [degs]')
                        hdu.header['RADIUS'] = (aper.ellipse.height*ic.pixscale, 'Radius of circular aperture [arcsec]')
                    elif aper.type == 'Square':
                        x0,y0 = aper.xy[0]
                        pixel = np.array([[x0, y0]], np.float_)
                        world = ic.wcs.wcs_pix2world(pixel, 1)
                        hdu.header['APERTURE']=('Square','Type of photometric aperture')
                        hdu.header['RA'] = (world[0][0]/15., 'RA of aperture center [hours]')
                        hdu.header['DEC'] = (world[0][1], 'Dec of aperture center [degs]')
                        hdu.header['ANGLE'] = (aper.rect.angle, 'Angle of square aperture')
                        hdu.header['SIDE'] = (aper.rect.get_height()*ic.pixscale, 'Side of square aperture [arcsec]')
                    elif aper.type == 'Rectangle':
                        x0,y0 = aper.xy[0]
                        pixel = np.array([[x0, y0]], np.float_)
                        world = ic.wcs.wcs_pix2world(pixel, 1)
                        hdu.header['APERTURE']=('Rectangle','Type of photometric aperture')
                        hdu.header['RA'] = (world[0][0]/15., 'RA of aperture center [hours]')
                        hdu.header['DEC'] = (world[0][1], 'Dec of aperture center [degs]')
                        hdu.header['WIDTH'] = (aper.rect.get_width()*ic.pixscale, 'Width of rectangle aperture [arcsec]')
                        hdu.header['HEIGHT'] = (aper.rect.get_height()*ic.pixscale, 'Height of rectangle aperture [arcsec]')
                        hdu.header['ANGLE'] = (aper.rect.angle, 'Angle of rectangle aperture [degs]')
                    elif aper.type == 'Polygon':
                        hdu.header['APERTURE']=('Polygon','Type of photometric aperture')
                        xy = np.asarray(aper.poly.xy)
                        world = ic.wcs.wcs_pix2world(xy, 1)
                        i = 0
                        for w in world:
                            hdu.header['RA_PT'+"{:03d}".format(i)] = (w[0]/15.,'RA [hours] of polygon aperture point no {:d}'.format(i))
                            hdu.header['DECPT'+"{:03d}".format(i)] = (w[1],'Dec [degs] of polygon aperture point no {:d}'.format(i))
                            i += 1
                    hdu.header['AREA'] = (area,'Area aperture in sq. degs.')
                # Add extensions
                hdu1 = self.addExtension(sc.spectrum.wave,'WAVELENGTH','um',None)
                hdu2 = self.addExtension(sc.spectrum.flux,'FLUX','Jy',None)
                hdlist = [hdu,hdu1,hdu2]
                if self.specCube.instrument == 'FIFI-LS':
                    hdu3 = self.addExtension(sc.spectrum.uflux,'UNCORR_FLUX','Jy',None)
                    hdu4 = self.addExtension(sc.spectrum.exposure,'EXPOSURE','s',None)
                    hdu5 = self.addExtension(self.specCube.atran,'ATM_TRANS','Norm',None)
                    hdlist.append(hdu3)
                    hdlist.append(hdu4)
                    hdlist.append(hdu5)
                # Save file
                hdul = fits.HDUList(hdlist)
                #hdul.info()    
                hdul.writeto(outfile,overwrite=True) # clobber true  allows rewriting
                hdul.close()
            elif file_extension == '.txt' or file_extension == '.csv':
                header = "# Object name: "+self.specCube.objname
                header += "\n# Instrument: "+self.specCube.instrument
                header += "\n# z: {:.8f}".format(self.specCube.redshift)
                header += "\n# Ref. Wav.: {:.8f}".format(self.specCube.l0)
                if n >= 0:
                    aper = ic.photApertures[n]
                    if aper.type == 'Ellipse':
                        x0,y0 = aper.ellipse.center
                        pixel = np.array([[x0, y0]], np.float_)
                        world = ic.wcs.wcs_pix2world(pixel, 1)                    
                        header += '\n# Aperture: Ellipse'
                        header += '\n# Center: {:.5f} {:.6f}'.format(world[0][0], world[0][1])
                        header += '\n# Angle: {:.1f} degs'.format(aper.ellipse.angle)
                        header += '\n# Axes: {:.1f} {:.1f} [arcsec]'.format(aper.ellipse.width*ic.pixscale,aper.ellipse.height*ic.pixscale)
                    elif aper.type == 'Circle':
                        x0,y0 = aper.ellipse.center
                        pixel = np.array([[x0, y0]], np.float_)
                        world = ic.wcs.wcs_pix2world(pixel, 1)                    
                        header += '\n# Aperture: Circle'
                        header += '\n# Center: {:.5f} {:.6f}'.format(world[0][0], world[0][1])
                        header += '\n# Radius: {:.1f} [arcsec]'.format(aper.ellipse.height*ic.pixscale)
                    elif aper.type == 'Square':
                        x0,y0 = aper.xy[0]
                        pixel = np.array([[x0, y0]], np.float_)
                        world = ic.wcs.wcs_pix2world(pixel, 1)
                        header += '\n# Aperture: Square'
                        header += '\n# Center: {:.5f} {:.6f}'.format(world[0][0], world[0][1])
                        header += '\n# Side: {:.1f} [arcsec]'.format(aper.rect.get_height()*ic.pixscale)
                        header += '\n# Angle: {:.1f} degs'.format(aper.rect.angle)
                    elif aper.type == 'Rectangle':
                        x0,y0 = aper.xy[0]
                        pixel = np.array([[x0, y0]], np.float_)
                        world = ic.wcs.wcs_pix2world(pixel, 1)
                        header += '\n# Aperture: Rectangle'
                        header += '\n# Center: {:.5f} {:.6f}'.format(world[0][0], world[0][1])
                        header += '\n# Height: {:.1f} [arcsec]'.format(aper.rect.get_height()*ic.pixscale)
                        header += '\n# Width: {:.1f} [arcsec]'.format(aper.rect.get_width()*ic.pixscale)
                        header += '\n# Angle: {:.1f} degs'.format(aper.rect.angle)
                    elif aper.type == 'Polygon':
                        header += '\n# Aperture: Polygon'
                        xy = np.asarray(aper.poly.xy)
                        world = ic.wcs.wcs_pix2world(xy, 1)
                        i = 0
                        for w in world:
                            header += '\n# Point {:03d}: {:.5f}h {:.6f}d'.format(i,w[0]/15.,w[1])
                            i += 1
                    header += '\n# Area aperture: {:.5f} degs'.format(area)
                #
                w = sc.spectrum.wave
                f = sc.spectrum.flux
                if file_extension == '.txt':
                    delimiter = ' '
                else:
                    delimiter = ','
                if self.specCube.instrument == 'FIFI-LS':
                    uf = sc.spectrum.flux
                    e  = sc.spectrum.exposure
                    a  = self.specCube.atran
                    # Normal ASCII file
                    fmt = delimiter.join(["%10.6e"]*5)
                    with open(outfile, 'wb') as file:
                        file.write(header.encode())
                        file.write(b'\n"wavelength","flux","uflux","exposure","atran"\n')
                        np.savetxt(file, np.column_stack((w,f,uf,e,a)), fmt=fmt, delimiter=delimiter)
                else:
                    fmt = delimiter.join(["%10.6e"]*2)
                    with open(outfile, 'wb') as file:
                        file.write(header.encode())
                        file.write(b'\n"wavelength","flux"\n')
                        np.savetxt(file, np.column_stack((w,f)), fmt=fmt, delimiter=delimiter)                
            elif file_extension == '.png' or file_extension == '.pdf' or file_extension == '.jpg':
                sc.fig.savefig(outfile)
            else:
                message = "Extension has to be *.fits, *.txt, *.csv, *.png, *.jpg, or *.pdf "
                self.sb.showMessage(message, 2000)
                print(message)

    def saveCube(self):
        """ Save a cut/cropped cube """ # TODO
        from astropy.io import fits
        
        # Dialog to save file
        fd = QFileDialog()
        fd.setNameFilters(["Fits Files (*.fits)","All Files (*)"])
        fd.setOptions(QFileDialog.DontUseNativeDialog)
        fd.setViewMode(QFileDialog.List)

        if (fd.exec()):
            fileName = fd.selectedFiles()
            #print(fileName[0])
            outfile = fileName[0]

            #print('Saving the cube with z size: ',self.specCube.n)
            # Reusable header
            header = self.specCube.wcs.to_header()
            header.remove('WCSAXES')
            header['CRPIX3'] = (self.specCube.crpix3,'Reference pixel')
            header['CRVAL3'] = (self.specCube.crval3,'Reference pixel value')
            header['CDELT3'] = (self.specCube.cdelt3,'Increment')
            header['NAXIS3'] = (self.specCube.n,'3rd dimension')
            header['INSTRUME'] = (self.specCube.instrument, 'Instrument')
            
            if self.specCube.instrument == 'FIFI-LS':
                header['CUNIT3'] = ('um','Wavelength unit')
                header['OBJ_NAME'] = (self.specCube.objname, 'Object Name')
                header['REDSHIFT'] = (self.specCube.redshift, 'Redshift')
                header['FILEGPID'] = (self.specCube.filegpid, 'File Group ID')
                header['BARYSHFT'] = (self.specCube.baryshift, 'Barycentric shift')
                header['RESOLUN'] = (self.specCube.resolution, 'Spectral resolution')
                header['ZA_START'] = (self.specCube.za[0],'Zenith angle [degrees]')
                header['ZA_END'] = (self.specCube.za[1],'Zenith angle [degrees]')
                header['ALTI_STA'] = (self.specCube.altitude[0],'Equivalent aircraft pressure altitude [feet]')
                header['ALTI_END'] = (self.specCube.altitude[1],'Equivalent aircraft pressure altitude [feet]')
                header['PIXSCAL'] = (self.specCube.pixscale,'Pixel scale [arcsec]' )
                header['RESOLUN'] = (self.specCube.resolution,'Spectral resolution')
                header['NAXIS'] = (3,'Number of axis')
                
                # Primary header
                hdu = fits.PrimaryHDU()
                hdu.header.extend(header)
                
                # Extensions
                hdu1 = self.addExtension(self.specCube.flux,'FLUX','Jy',header)
                hdu2 = self.addExtension(self.specCube.eflux,'ERROR','Jy',header)
                hdu3 = self.addExtension(self.specCube.uflux,'UNCORRECTED_FLUX','Jy',header)
                hdu4 = self.addExtension(self.specCube.euflux,'UNCORRECTED_ERROR','Jy',header)
                hdu5 = self.addExtension(self.specCube.wave,'WAVELENGTH','um',None)
                hdu6 = self.addExtension(self.specCube.x,'X',None,None)
                hdu7 = self.addExtension(self.specCube.y,'Y',None,None)
                hdu8 = self.addExtension(self.specCube.atran,'TRANSMISSION',None,None)
                hdu9 = self.addExtension(self.specCube.response,'RESPONSE',None,None)
                hdu10 = self.addExtension(self.specCube.exposure,'EXPOSURE_MAP',None,header)
                hdul = fits.HDUList([hdu, hdu1, hdu2, hdu3, hdu4, hdu5, hdu6, hdu7, hdu8, hdu9, hdu10])            
                #hdul.info()    
                hdul.writeto(outfile,overwrite=True) # clobber true  allows rewriting
                hdul.close()
            elif self.specCube.instrument == 'GREAT':
                header['OBJECT'] = (self.specCube.objname, 'Object Name')
                c = 299792458.0  # speed of light in m/s 
                header['VELO-LSR'] = self.specCube.redshift * c
                header['RESTFREQ'] = self.specCube.header['RESTFREQ']
                header['CUNIT3'] = ('m/s','Velocity unit')
                eta_fss=0.97
                eta_mb =0.67
                calib = 971.
                factor = calib*eta_fss*eta_mb
                temperature = self.specCube.flux / factor  # Transform flux into temperature
                # Primary header
                hdu = fits.PrimaryHDU(temperature)
                header['NAXIS'] = (3,'Number of axis')
                hdu.header.extend(header)
                hdul = fits.HDUList([hdu])
                hdul.writeto(outfile,overwrite=True) # clobber true  allows rewriting
                hdul.close()
            else:
                pass    


    def addExtension(self,data, extname, unit, hdr):
        from astropy.io import fits
        hdu = fits.ImageHDU()
        hdu.data = data
        hdu.header['EXTNAME']=(extname)
        if unit !=None: hdu.header['BUNIT']=(unit)
        if hdr != None: hdu.header.extend(hdr)
        return hdu

        
    def sliceCube(self):
        """ Cut part of the cube """
        self.sb.showMessage("Define slice of the cube ", 1000)
        self.slice = 'on'
        istab = self.spectra.index('All')
        self.stabs.setCurrentIndex(istab)
        sc = self.sci[istab]
        sc.span.active=True

    def maskCube(self):
        """ Mask a slice of the cube """
        self.sb.showMessage("Drag your mouse over the spectrum to mask part of the cube or click over to unmask", 2000)

    def computeZeroMoment(self):
        
        c = 299792458. # m/s
        w = self.specCube.wave
        dw = [] 
        dw.append([w[1]-w[0]])
        dw.append(list((w[2:]-w[:-2])*0.5))
        dw.append([w[-1]-w[-2]])
        dw = np.concatenate(dw)

        nz,ny,nx = np.shape(self.specCube.flux)
        self.M0 = np.zeros((ny,nx))
        for i in range(nx):
            for j in range(ny):
                Snu = self.specCube.flux[:,j,i]
                Slambda = c*(Snu-np.nanmedian(Snu))/(w*w)*1.e6   # [Jy * Hz / um]
                self.M0[j,i] = np.nansum(Slambda*dw)*1.e-26 # [Jy Hz]  (W/m2 = Jy*Hz*1.e-26)
        
    def zeroMoment(self):
        """ Compute and display zero moment of flux """

        self.computeZeroMoment()
        
        band = 'M0'
        # Open tab and display the image
        self.bands.append(band)
        t,ic,ih,h,c1,c2,c3 = self.addImage(band)
        self.tabi.append(t)
        self.ici.append(ic)
        self.ihi.append(ih)
        self.ihcid.append(h)
        self.icid1.append(c1)
        self.icid2.append(c2)
        self.icid3.append(c3)
        
        ic.compute_initial_figure(image=self.M0,wcs=self.specCube.wcs,title=band)
        # Callback to propagate axes limit changes among images
        ic.cid = ic.axes.callbacks.connect('xlim_changed' and 'ylim_changed', self.doZoomAll)
        ih = self.ihi[self.bands.index(band)]
        clim = ic.image.get_clim()
        ih.compute_initial_figure(image=self.M0,xmin=clim[0],xmax=clim[1])

        # Add apertures
        self.addApertures(ic)

        # Add contours
        self.addContours(ic) 

        # Align with spectral cube
        ic0 = self.ici[0]
        x = ic0.axes.get_xlim()
        y = ic0.axes.get_ylim()
        ra,dec = ic0.wcs.all_pix2world(x,y,1)
        x,y = ic.wcs.all_world2pix(ra,dec,1)            
        ic.axes.set_xlim(x)
        ic.axes.set_ylim(y)
        ic.changed = True


    def addContours(self, ic):
        """ Add existing contours to newly added images """

        if self.contours == 'on':
            ih0 = None
            for ih,ic_ in zip(self.ihi, self.ici):
                if len(ih.levels) > 0:
                    ih0 = ih
                    ic0 = ic_
            if ih0 is not None:
                ic.contour = ic.axes.contour(ic0.oimage,ih0.levels, colors='cyan',transform=ic.axes.get_transform(ic0.wcs))
                ic.fig.canvas.draw_idle()
            else:
                pass
                #print("No contours available")
            
    def overlapContours(self):
        """ Compute contours and overlap/remove them on images """

        if self.contours == 'off':
            #self.ctab = [self.itabs.currentIndex(),0]
            self.sb.showMessage("Click again to remove contours", 2000)
            self.drawContours()
            self.contours = 'on'
        else:
            self.contours = 'off'
            # Remove level lines in histogram 
            for ih in self.ihi:
                if len(ih.levels) > 0:
                    ih.levSignal.disconnect()
                ih.removeLevels()
            # Remove contours
            for ic in self.ici:
                if ic.contour is not None:
                    for coll in ic.contour.collections:
                        coll.remove()
                    ic.contour = None
                    ic.changed = True
            # Update current tab
            itab = self.itabs.currentIndex()
            #print('current tab is: ',itab)
            ic0 = self.ici[itab]
            ic0.fig.canvas.draw_idle()
            ic0.changed = False
            self.sb.showMessage('Contours deleted ', 1000)

    def drawContours(self):
        """ Draw contours of image """

        itab = self.itabs.currentIndex()
        ic0 = self.ici[itab]
        ih0 = self.ihi[itab]
        if self.bands[itab] == 'Cov':
            ih0.levels = list(np.arange(ih0.min,ih0.max,(ih0.max-ih0.min)/8))
        else:
            levels = ih0.median + np.array([1,2,3,5,10]) * ih0.sdev
            mask = levels < ih0.max
            ih0.levels = list(levels[mask])
        #print('Contour levels are: ',ih0.levels)
        ic0.contour = ic0.axes.contour(ic0.oimage,ih0.levels,colors='cyan')
        ic0.fig.canvas.draw_idle()
        # Add levels to histogram
        ih0.drawLevels()
        # Connect signal event to action
        cidh0=ih0.levSignal.connect(self.onModifyContours)
        # Update contours on all other images
        ici = self.ici.copy()
        ici.remove(ic0)
        for ic in ici:
            ic.contour = ic.axes.contour(ic0.oimage,ih0.levels, colors='cyan',transform=ic.axes.get_transform(ic0.wcs))
            ic.changed = True

    def onModifyContours(self, n):
        """ Called by mysignal in the histogram canvas if contour levels change """

        # In some cases, computing contours can be computationally intense. So
        # we call threads in the case of new/modified contours
        # Unfortunately this does not work because matplotlib is not thread safe.
        
        itab = self.itabs.currentIndex()
        ic0 = self.ici[itab]
        ih0 = self.ihi[itab]
        if ic0.contour is not None:
            nlev = len(ic0.contour.collections)
            if n > 1000:
                #contoursThread = ContoursThread(ic0,ih0.levels[n-1000], n, itab)
                #contoursThread.updateOtherContours.connect(self.modifyOtherImagesContours)
                #contoursThread.start()
                n -= 1000
                new = ic0.axes.contour(ic0.oimage, [ih0.levels[n]], colors='cyan')
                # Insert new contour in the contour collection
                contours = ic0.contour.collections
                contours.insert(n,new.collections[0])
            elif n < 0:
                # Remove contour from image
                ic0.axes.collections.remove(ic0.contour.collections[n])
                # Delete element from contour collection list
                del ic0.contour.collections[n]
            else:
                ic0.axes.collections.remove(ic0.contour.collections[n])
                ic0.fig.canvas.draw_idle()
                #contoursThread = ContoursThread(ic0,ih0.levels[n], n, itab)
                #contoursThread.updateOtherContours.connect(self.modifyOtherImagesContours)
                #contoursThread.start()
                new = ic0.axes.contour(ic0.oimage, [ih0.levels[n]], colors='cyan')
                # Update the collection
                ic0.contour.collections[n] = new.collections[0]
            self.modifyOtherImagesContours(itab)
                
    def modifyOtherImagesContours(self, i0):
        """ Once the new contours are computed, propagate them to other images """
        
        ic0 = self.ici[i0]
        ih0 = self.ihi[i0]
        ic0.fig.canvas.draw_idle()
        
        ici = self.ici.copy()
        ici.remove(ic0)
        for ic in ici:
            if ic.contour is not None:
                # Remove previous contours
                for coll in ic.contour.collections:
                    coll.remove()
                    ic.contour = None
                # Compute new contours
                levels =  sorted(ih0.levels)   
                ic.contour = ic.axes.contour(ic0.oimage, levels, colors='cyan',transform=ic.axes.get_transform(ic0.wcs))
                # Differ drawing until changing tab
                ic.changed = True
            
        
    def newFile(self):
        """ Display a new image """

        #from sospex.specobj import specCube, Spectrum

        fd = QFileDialog()
        fd.setNameFilters(["Fits Files (*.fits)","All Files (*)"])
        fd.setOptions(QFileDialog.DontUseNativeDialog)
        fd.setViewMode(QFileDialog.List)
        fd.setFileMode(QFileDialog.ExistingFile)

        if (fd.exec()):
            fileName= fd.selectedFiles()
            #print(fileName[0])
            # Read the spectral cube
            # A more robust step to skip bad files should be added
            try:
                self.specCube = specCube(fileName[0])
            except:
                self.sb.showMessage("ERROR: The selected file is not a good spectral cube ", 2000)
                return
            # Delete pre-existing spectral tabs
            try:
                for stab in reversed(range(len(self.sci))):
                    self.removeSpecTab(stab)
                #print('all spectral tabs removed')
            except:
                pass
            # Delete pre-existing image tabs
            try:
                # Remove tabs, image and histo canvases and disconnect them
                # The removal is done in reversed order to get all the tabs
                for itab in reversed(range(len(self.ici))):
                    self.removeTab(itab)
                #print('all image tabs removed')
            except:
                pass

            # Initialize
            self.tabi = []
            self.ici  = []
            self.ihi  = []
            self.ihcid = []
            self.icid1 = []
            self.icid2 = []
            self.icid3 = []
            self.stabi = []
            self.sci  = []
            self.scid1 = []
            self.scid2 = []
            self.scid3 = []
            self.scid4 = []

            # Open new tabs and display it
            if self.specCube.instrument == 'FIFI-LS':
                self.bands = ['Flux','uFlux','Exp']
                self.spectra = ['All']
            elif self.specCube.instrument == 'GREAT':
                self.bands = ['Flux','M0']
                self.spectra = ['All']
            elif self.specCube.instrument == 'PACS':
                self.bands = ['Flux','Exp']
                self.spectra = ['All']
            else:
                self.spectra = []
                self.bands = []
            #print ("bands are ", self.bands)
            self.photoApertures = []
            for b in self.bands:
                t,ic,ih,h,c1,c2,c3 = self.addImage(b)
                self.tabi.append(t)
                self.ici.append(ic)
                self.ihi.append(ih)
                self.ihcid.append(h)
                self.icid1.append(c1)
                self.icid2.append(c2)
                self.icid3.append(c3)
            # Make tab 'Flux' unclosable
            self.itabs.tabBar().setTabButton(0,QTabBar.LeftSide,None)
            self.itabs.tabBar().setTabButton(0,QTabBar.RightSide,None)
            for s in self.spectra:
                t,sc,scid1,scid2,scid3,scid4 = self.addSpectrum(s)
                self.stabi.append(t)
                self.sci.append(sc)
                self.scid1.append(scid1)
                self.scid2.append(scid2)
                self.scid3.append(scid3)
                self.scid4.append(scid4)
            # Make tab 'All' unclosable
            self.stabs.tabBar().setTabButton(0,QTabBar.LeftSide,None)
            self.stabs.tabBar().setTabButton(0,QTabBar.RightSide,None)
                
            # Compute initial images
            for ima in self.bands:
                ic = self.ici[self.bands.index(ima)]
                if ima == 'Flux':
                    image = np.nanmedian(self.specCube.flux, axis=0)
                elif ima == 'uFlux':
                    image = np.nanmedian(self.specCube.uflux, axis=0)
                elif ima == 'Exp':
                    image = np.nansum(self.specCube.exposure, axis=0)
                elif ima == 'M0':
                    self.computeZeroMoment()
                    image = self.M0
                else:
                    pass
                #print('size of image is ',np.shape(image))
                ic.compute_initial_figure(image=image,wcs=self.specCube.wcs,title=ima)
                # Callback to propagate axes limit changes among images
                ic.cid = ic.axes.callbacks.connect('xlim_changed' and 'ylim_changed', self.doZoomAll)
                ih = self.ihi[self.bands.index(ima)]
                clim = ic.image.get_clim()
                ih.compute_initial_figure(image=image,xmin=clim[0],xmax=clim[1])
                x = ic.axes.get_xlim()
                y = ic.axes.get_ylim()
                self.zoomlimits = [x,y]
            # Compute initial spectra
            spectrum = self.spectra[0]
            sc = self.sci[self.spectra.index(spectrum)]
            fluxAll = np.nansum(self.specCube.flux, axis=(1,2))
            s = self.specCube
            if s.instrument == 'GREAT':
                spec = Spectrum(s.wave, fluxAll, instrument=s.instrument, redshift=s.redshift, l0=s.l0 )
            elif s.instrument == 'PACS':
                expAll = np.nansum(s.exposure, axis=(1,2))
                spec = Spectrum(s.wave, fluxAll, exposure=expAll,instrument=s.instrument, redshift=s.redshift, l0=s.l0 )
            elif s.instrument == 'FIFI-LS':
                ufluxAll = np.nansum(s.uflux, axis=(1,2))
                expAll = np.nansum(s.exposure, axis=(1,2))
                spec = Spectrum(s.wave, fluxAll, uflux= ufluxAll,
                                exposure=expAll, atran = s.atran, instrument=s.instrument,
                                redshift=s.redshift, baryshift = s.baryshift, l0=s.l0)
            #print("Compute initial spectrum")
            sc.compute_initial_spectrum(spectrum=spec)
            self.specZoomlimits = [sc.xlimits,sc.ylimits]
            sc.cid = sc.axes.callbacks.connect('xlim_changed' and 'ylim_changed', self.doZoomSpec)
            # Start the span selector to show only part of the cube
            sc.span = SpanSelector(sc.axes, self.onSelect, 'horizontal', useblit=True,
                                   rectprops=dict(alpha=0.5, facecolor='LightSalmon'))
            sc.span.active = False
                
            # Re-initiate variables
            self.contours = 'off'
            self.blink = 'off'
            self.slice = 'off'
            self.cutcube = 'off'
            self.continuum = 'off'
            # Selectors
            self.PS = None
            self.ES = None
            self.RS = None
            self.LS = None

            # Add first aperture (size of a pixel)
            #w=h=s.pixscale/2.
            #x0 = np.abs(x[1]-x[0])/2.
            #y0 = np.abs(y[1]-y[0])/2.
            #self.newSelectedAperture(x0,y0,w,h,'square')

            
    def onSelect(self, xmin, xmax):
        """ Consider only a slice of the cube when computing the image """

        if self.slice == 'on':
            # Find indices of the shaded region
            #print('xmin, xmax ',xmin,xmax)
            sc = self.sci[self.spectra.index('All')]
            if sc.xunit == 'THz':
                c = 299792458.0  # speed of light in m/s
                xmin, xmax = c/xmax*1.e-6, c/xmin*1.e-6

            #print('xmin, xmax ',xmin,xmax)
            indmin, indmax = np.searchsorted(self.specCube.wave, (xmin, xmax))
            indmax = min(len(self.specCube.wave) - 1, indmax)
            #print('indmin, indmax', indmin,indmax)
            sc.regionlimits = [xmin,xmax]


            # Remove previous contours on image
            for ic in self.ici:
                if ic.contour is not None:
                    for coll in ic.contour.collections:
                        coll.remove()
                    ic.contour = None
                    ic.changed = True
            self.contours = 'off'

            # Draw region on spectrum (All) and hide span selector
            sc.shadeSpectrum()
            sc.fig.canvas.draw_idle()
            sc.span.active = False

            # Update images (flux, uflux, coverage)
            if self.specCube.instrument == 'GREAT':
                imas = ['Flux']
            elif self.specCube.instrument == 'PACS':
                imas = ['Flux','Exp']
            elif self.specCube.instrument == 'FIFI-LS':
                imas = ['Flux','uFlux','Exp']
            
            x,y = self.zoomlimits
            for ima in imas:
                ic = self.ici[self.bands.index(ima)]
                ih = self.ihi[self.bands.index(ima)]
                if ima == 'Flux':
                    image = np.nanmedian(self.specCube.flux[indmin:indmax,:,:], axis=0)
                elif ima == 'uFlux':
                    image = np.nanmedian(self.specCube.uflux[indmin:indmax,:,:], axis=0)
                elif ima == 'Exp':
                    image = np.nansum(self.specCube.exposure[indmin:indmax,:,:], axis=0)
                else:
                    pass
                ic.showImage(image)
                # Set image limits to pre-existing values
                ic.axes.set_xlim(x)
                ic.axes.set_ylim(y)
                ic.changed = True
                # Update histogram
                clim = ic.image.get_clim()
                ih.axes.clear()
                ih.compute_initial_figure(image=image,xmin=clim[0],xmax=clim[1])
                ih.fig.canvas.draw_idle()
            self.slice = 'off'
        elif self.cutcube == 'on':
            # Find indices of the shaded region
            #print('xmin, xmax ',xmin,xmax)
            sc = self.sci[self.spectra.index('All')]
            if sc.xunit == 'THz':
                c = 299792458.0  # speed of light in m/s
                xmin, xmax = c/xmax*1.e-6, c/xmin*1.e-6
            sc.shadeRegion([xmin,xmax],'LightYellow')
            sc.fig.canvas.draw_idle()
            sc.span.active = False
            indmin, indmax = np.searchsorted(self.specCube.wave, (xmin, xmax))
            indmax = min(len(self.specCube.wave) - 1, indmax)
            #print('indmin, indmax', indmin,indmax)
            size = indmax-indmin
            nz,nx,ny = np.shape(self.specCube.flux)
            if size == nx:
                self.sb.showMessage("No cutting needed ", 2000)
            else:
                flags = QMessageBox.Yes 
                flags |= QMessageBox.No
                question = "Do you want to cut the part of the cube selected on the image ?"
                response = QMessageBox.question(self, "Question",
                                                question,
                                                flags)            
                if response == QMessageBox.Yes:
                    self.sb.showMessage("Cutting the cube ", 2000)
                    self.cutCube1D(indmin,indmax)
                    self.saveCube()
                elif QMessageBox.No:
                    self.sb.showMessage("Cropping aborted ", 2000)
                else:
                    pass
            self.cutcube = 'off'
            sc.tmpRegion.remove()
            sc.fig.canvas.draw_idle()
        elif self.continuum == 'one' or self.continuum == 'two':
            print('continuum is ', self.continuum)
            istab = self.stabs.currentIndex()
            sc = self.sci[istab]
            if sc.xunit == 'THz':
                c = 299792458.0  # speed of light in m/s
                xmin, xmax = c/xmax*1.e-6, c/xmin*1.e-6
            sc.shadeRegion([xmin,xmax],'lightcoral')
            sc.fig.canvas.draw_idle()
            indmin, indmax = np.searchsorted(self.specCube.wave, (xmin, xmax))
            indmax = min(len(self.specCube.wave) - 1, indmax)
            print('indmin, indmax', indmin,indmax)
            if self.continuum == 'one':
                self.continuum = 'two'
                self.contpts = [indmin, indmax]
            elif self.continuum == 'two':
                self.contpts.extend([indmin,indmax])
                # order the list
                self.contpts.sort()
                xpts = self.specCube.wave[self.contpts]
                yc = np.nanmax(sc.spectrum.flux[xpts[1]:xpts[2]])
                continuum = sc.spectrum.flux[xpts[0]:xpts[1]]
                continuum.append(sc.spectrum.flux[xpts[2]:xpts[3]])
                offset = np.nanmedian(continuum)
                # build the guess structure and display the curve
                self.guess = Guess(self.contpts,xpts,yc,offset)
                # span inactive
                sc.span.active = False
                self.continuum = 'off'
                self.contpts = None
            
            
    def doZoomAll(self, event):
        ''' propagate limit changes to all images '''
        itab = self.itabs.currentIndex()
        ic = self.ici[itab]
        if ic.axes == event: # only consider axes on screen (not other tabs)
            self.zoomAll(itab)

    def zoomAll(self, itab):


        # Update total spectrum
        s = self.specCube
        spectrum = self.spectra.index('All')
        sc = self.sci[spectrum]
        
        ic = self.ici[itab]
        if ic.toolbar._active == 'ZOOM':
            ic.toolbar.zoom()  # turn off zoom
        x = ic.axes.get_xlim()
        y = ic.axes.get_ylim()
        ra,dec = ic.wcs.all_pix2world(x,y,1)

        # If not in the flux image, compute values for the flux image
        band = self.bands.index('Flux')
        if itab != band:
            ic = self.ici[band]
            x,y = ic.wcs.all_world2pix(ra,dec,1)            
        self.zoomlimits = [x,y]

        # Compute limits for new total spectrum
        x0 = int(np.min(x)); x1 = int(np.max(x))
        y0 = int(np.min(y)); y1 = int(np.max(y))
        if x0 < 0: x0=0
        if y0 < 0: y0=0
        if x1 >= s.nx: x1 = s.nx-1
        if y1 >= s.ny: y1 = s.ny-1

        # Set new values in other image tabs
        ici = self.ici.copy()
        ici.remove(ic)
        for ima in ici:
            x,y = ima.wcs.all_world2pix(ra,dec,1)
            ima.axes.callbacks.disconnect(ima.cid)
            ima.axes.set_xlim(x)
            ima.axes.set_ylim(y)
            ima.changed = True
            ima.cid = ima.axes.callbacks.connect('xlim_changed' and 'ylim_changed', self.doZoomAll)

        #print('itab',itab,'band',band,'limits ',x,y)

        
        fluxAll = np.nansum(self.specCube.flux[:,y0:y1,x0:x1], axis=(1,2))
        if s.instrument == 'GREAT':
            sc.updateSpectrum(fluxAll)
        elif s.instrument == 'PACS':
            expAll = np.nansum(s.exposure[:,y0:y1,x0:x1], axis=(1,2))
            sc.updateSpectrum(fluxAll,exp=expAll)            
        elif self.specCube.instrument == 'FIFI-LS':
            ufluxAll = np.nansum(s.uflux[:,y0:y1,x0:x1], axis=(1,2))
            expAll = np.nansum(s.exposure[:,y0:y1,x0:x1], axis=(1,2))
            sc.updateSpectrum(fluxAll,uf=ufluxAll,exp=expAll)
            
            
    def doZoomSpec(self,event):
        """ In the future impose the same limits to all the spectral tabs """
        stab = self.stabs.currentIndex()
        sc = self.sci[stab]
        if sc.toolbar._active == 'ZOOM':
            sc.toolbar.zoom()  # turn off zoom
        xmin,xmax = sc.axes.get_xlim()
        if sc.xunit == 'THz':
            c = 299792458.0  # speed of light in m/s
            xmin, xmax = c/xmax*1.e-6, c/xmin*1.e-6  # Transform in THz as expected by onSelect            
        sc.xlimits = (xmin,xmax)
        sc.ylimits = sc.axes.get_ylim()
        self.specZoomlimits = [sc.xlimits,sc.ylimits]

        
    def changeVisibility(self):
        """ Hide/show the histogram of image intensities """
        try:
            itab = self.itabs.currentIndex()
            ih = self.ihi[itab]
            state = ih.isVisible()
            for ih in self.ihi:
                ih.setVisible(not state)
        except:
            self.sb.showMessage("First choose a cube (press arrow) ", 1000)
            

    def changeColorMap(self):
        """ Change a color map for the images """

        self.CMlist = ['gist_heat','gist_earth','gist_gray','afmhot','inferno','ocean','plasma']
        self.selectCM = cmDialog(self.CMlist, self.colorMap)
        self.selectCM.list.currentRowChanged.connect(self.updateColorMap)
        self.selectCM.dirSignal.connect(self.reverseColorMap)
        self.selectCM.exec_()
        
    def updateColorMap(self,newRow):
        """ Update the color map of the image tabs """
        
        newCM = self.CMlist[newRow]
        if newCM != self.colorMap:
            self.colorMap = newCM
            for ic in self.ici:
                ic.colorMap = self.colorMap
                ic.showImage(ic.oimage)
                ic.fig.canvas.draw_idle()

    def reverseColorMap(self, reverse):
        """ Reverse color map direction """

        if self.colorMapDirection == "":
            self.colorMapDirection = "_r"
        else:
            self.colorMapDirection = ""

        for ic in self.ici:
            ic.colorMapDirection = self.colorMapDirection
            ic.showImage(ic.oimage)
            ic.fig.canvas.draw_idle()

            
    def onSTabChange(self, stab):
        #print('Spectral tab changed to ', stab)

        # This should activate an aperture (put dots on it and/or change color)
        if len(self.stabs) > 1:
            itab  = self.itabs.currentIndex()
            ic = self.ici[itab]
            nap = len(self.stabs)-1
            istab = self.stabs.currentIndex()
            n = istab-1  # aperture number
            # Activate interactor (toogle on) and disactivate
            for iap in range(nap):
                ap = ic.photApertures[iap]
                aps = ic.photApertureSignal[iap]
                if iap == n:
                    ap.showverts = True
                    #ic.photApertureSignal[iap]=ap.mySignal.connect(self.onRemovePolyAperture)
                else:
                    ap.showverts = False
                    #ap.mySignal.disconnect()
                ap.line.set_visible(ap.showverts)
            ic.fig.canvas.draw_idle()

    def hresizeSpectrum(self):
        """ Expand spectrum to maximum wavelength range """

        istab = self.stabs.currentIndex()
        sc = self.sci[istab]
        xlim0 = np.min(sc.spectrum.wave)
        xlim1 = np.max(sc.spectrum.wave)
        sc.xlimits=(xlim0,xlim1)
        sc.updateXlim()
        
    def vresizeSpectrum(self):
        """ Expand spectrum to maximum flux range """

        istab = self.stabs.currentIndex()
        sc = self.sci[istab]
        spec = sc.spectrum

        ylim0 = np.nanmin(spec.flux)
        ylim1 = np.nanmax(spec.flux)

        if sc.instrument == 'FIFI-LS':
            u0 = np.nanmin(spec.uflux)
            u1 = np.nanmax(spec.uflux)
            if u0 < ylim0: ylim0 = u0
            if u1 > ylim1: ylim1 = u1

        # Slightly higher maximum
        sc.ylimits = (ylim0,ylim1*1.1)
        sc.updateYlim()
        
        
if __name__ == '__main__':
#def main():
    #QApplication.setStyle('Fusion')
    app = QApplication(sys.argv)
    gui = GUI()
    
    # Create and display the splash screen
    #splash_pix = QPixmap(gui.path0+'/icons/sospex.png')
    #splash = QSplashScreen(splash_pix, Qt.WindowStaysOnTopHint)
    #splash.setMask(splash_pix.mask())
    #splash.show()
    #splash.showMessage("<h1><font color='green'>Welcome to SOSPEX!</font></h1>", Qt.AlignTop | Qt.AlignCenter, Qt.white)
    #app.processEvents()
    
    # Adjust geometry to size of the screen
    screen_resolution = app.desktop().screenGeometry()
    width = screen_resolution.width()
    gui.setGeometry(width*0.025, 0, width*0.95, width*0.5)
    gui.hsplitter.setSizes ([width*0.38,width*0.5])
    # Add an icon for the application
    app.setWindowIcon(QIcon(gui.path0+'/icons/sospex.png'))
    app.setApplicationName('SOSPEX')
    app.setApplicationVersion('0.16-beta')
    sys.exit(app.exec_())
    #splash.finish(gui)
