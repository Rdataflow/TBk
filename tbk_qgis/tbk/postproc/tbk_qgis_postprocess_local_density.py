# -*- coding: utf-8 -*-

#######################################################################
# Determine local density in TBk stands.
#
# (C) Attilio Benini, HAFL
#######################################################################

"""
/***************************************************************************
 TBk
                                 A QGIS plugin
 Toolkit for the generation of forest stand maps
 Generated by Plugin Builder: http://g-sherman.github.io/Qgis-Plugin-Builder/
                              -------------------
        begin                : 2020-08-03
        copyright            : (C) 2023 by Berner Fachhochschule HAFL
        email                : christian.rosset@bfh.ch
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

__author__ = 'Berner Fachhochschule HAFL'
__date__ = '2020-08-03'
__copyright__ = '(C) 2023 by Berner Fachhochschule HAFL'

# This will get replaced with a git SHA1 when you do a git archive

__revision__ = '$Format:%H$'

import os # os is used below, so make sure it's available in any case
import time
from datetime import datetime, timedelta
import math

from qgis.PyQt.QtCore import QCoreApplication
from qgis.core import (QgsProcessing,
                       QgsProcessingAlgorithm,
                       QgsProcessingParameterRasterLayer,
                       QgsProcessingParameterFile,
                       QgsProcessingParameterBoolean,
                       QgsProcessingParameterNumber,
                       QgsProcessingParameterDefinition,
                       QgsProcessingParameterMatrix,
                       QgsProcessingException,
                       QgsProcessingParameterString,
                       QgsVectorLayer,
                       QgsRasterLayer,
                       QgsApplication)
import processing

from tbk_qgis.tbk.utility.tbk_utilities import *


class TBkPostprocessLocalDensity(QgsProcessingAlgorithm):

    def addAdvancedParameter(self, parameter):
        parameter.setFlags(parameter.flags() | QgsProcessingParameterDefinition.FlagAdvanced)
        return self.addParameter(parameter)

    # Constants used to refer to parameters and outputs. They will be
    # used when calling the algorithm from another algorithm, or when
    # calling from the QGIS console.

    # Directory containing the input files
    PATH_TBk_INPUT = "path_tbk_input"

    OUTPUT = "OUTPUT"

    # Use forest mixture degree / coniferous raster to calculate density zone mean?
    MG_USE = "mg_use"

    # Forest mixture degree / coniferous raster to calculate density zone mean
    MG_INPUT = "mg_input"

    # advanced parameters

    # suffix for output files (string)
    OUTPUT_SUFFIX = "output_suffix"
    # input table for local density classes (matrix as one-dimensional list)
    TABLE_DENSITY_CLASSES = "table_density_classes"
    # determine whether DG is calculated for all layers (KS, US, MS, OS, UEB) (boolean)
    CALC_ALL_DG = "calc_all_dg"
    # radius of circular moving window (in m)
    MW_RAD = "mw_rad"
    # large radius of circular moving window (in m)
    MW_RAD_LARGE = "mw_rad_large"
    # minimum size for dense/sparse "clumps" (m^2)
    MIN_SIZE_CLUMP = "min_size_clump"
    # minimum size for stands to apply calculation of local densities (m^2)
    MIN_SIZE_STAND = "min_size_stand"
    # threshold for minimal holes within local density polygons (m^2)
    HOLES_THRESH = "holes_thresh"
    # method to remove thin parts and details of zones by minus / plus buffering (boolean)
    BUFFER_SMOOTHING = "buffer_smoothing"
    # buffer distance of buffer smoothing (m)
    BUFFER_SMOOTHING_DIST = "buffer_smoothing_dist"

    def initAlgorithm(self, config):
        """
        Here we define the inputs and output of the algorithm, along
        with some other properties.
        """

        # Folder for algo input/output
        self.addParameter(
            QgsProcessingParameterFile(
                self.PATH_TBk_INPUT,
                self.tr("Folder with TBk results"),
                behavior=QgsProcessingParameterFile.Folder,
                fileFilter='All Folders (*.*)',
                defaultValue=None
            )
        )

        # Use forest mixture degree / coniferous raster to calculate density zone mean?
        self.addParameter(
            QgsProcessingParameterBoolean(
                self.MG_USE,
                self.tr("Use forest mixture degree (coniferous raster)?"),
                defaultValue=True
            )
        )

        # Forest mixture degree / coniferous raster to calculate density zone mean
        self.addParameter(
            QgsProcessingParameterRasterLayer(
                self.MG_INPUT,
                self.tr("Forest mixture degree (coniferous raster) 10m input to calculate density zone mean (.tif)"),
                optional=True
            )
        )

        # suffix for output files (string)
        parameter = QgsProcessingParameterString(
            self.OUTPUT_SUFFIX,
            self.tr(
                "Suffix added to names of output files (.gpkg)"
                "\nDefault _v11 stands for current development version of local densities"
            ),
            defaultValue='_v11' # current development version of local densities
        )
        self.addAdvancedParameter(parameter)

        # input table for local density classes (matrix as one-dimensional list)
        parameter = QgsProcessingParameterMatrix(
            self.TABLE_DENSITY_CLASSES,
            self.tr("Table to define classes of local densities"),
            hasFixedNumberRows=False,
            headers=['class', 'min DG [%]', 'max DG [%]', 'use large moving window? [False/True]'],
            defaultValue=[
                1, 85, 100, 'False',
                2, 60, 85, 'True',
                3, 40, 60, 'True',
                4, 25, 40, 'True',
                5, 0, 25, 'False',
                12, 60, 100, 'True'
            ]
        )
        self.addAdvancedParameter(parameter)

        # determine whether DG is calculated for all layers (KS, US, MS, OS, UEB) (boolean)
        parameter = QgsProcessingParameterBoolean(
            self.CALC_ALL_DG,
            self.tr("Determine whether DG is calculated for all layers (KS, US, MS, OS, UEB)"),
            defaultValue=True
        )
        self.addAdvancedParameter(parameter)

        # radius of circular moving window (in m)
        parameter = QgsProcessingParameterNumber(
            self.MW_RAD,
            self.tr("Radius of circular moving window (in m)"),
            type=QgsProcessingParameterNumber.Double,
            defaultValue=7.0
        )
        parameter.setMetadata({'widget_wrapper': {'decimals': 2}})
        self.addAdvancedParameter(parameter)

        # large radius of circular moving window (in m)
        parameter = QgsProcessingParameterNumber(
            self.MW_RAD_LARGE,
            self.tr("Large radius of circular moving window (in m)"),
            type=QgsProcessingParameterNumber.Double,
            defaultValue=14.0
        )
        parameter.setMetadata({'widget_wrapper': {'decimals': 2}})
        self.addAdvancedParameter(parameter)

        # minimum size for dense/sparse "clumps" (m^2)
        parameter = QgsProcessingParameterNumber(
            self.MIN_SIZE_CLUMP,
            self.tr("Minimum size for dense/sparse 'clumps' (m^2)"),
            type=QgsProcessingParameterNumber.Integer,
            defaultValue=1200
        )
        self.addAdvancedParameter(parameter)

        # minimum size for stands to apply calculation of local densities (m^2)
        parameter = QgsProcessingParameterNumber(
            self.MIN_SIZE_STAND,
            self.tr("Minimum size for stands to apply calculation of local densities (m^2)"),
            type=QgsProcessingParameterNumber.Integer,
            defaultValue=1200
        )
        self.addAdvancedParameter(parameter)

        # threshold for minimal holes within local density polygons (m^2)
        parameter = QgsProcessingParameterNumber(
            self.HOLES_THRESH,
            self.tr("Threshold for minimal holes within local density polygons (m^2)"),
            type=QgsProcessingParameterNumber.Integer,
            defaultValue=400
        )
        self.addAdvancedParameter(parameter)

        # method to remove thin parts and details of zones by minus / plus buffering (boolean)
        parameter = QgsProcessingParameterBoolean(
            self.BUFFER_SMOOTHING,
            self.tr("Remove thin parts and details of density zones by minus / plus buffering. If unchecked, no buffer smoothing is applied."),
            defaultValue=True
        )
        self.addAdvancedParameter(parameter)

        # buffer distance of buffer smoothing (m)
        parameter = QgsProcessingParameterNumber(
            self.BUFFER_SMOOTHING_DIST,
            self.tr("Buffer distance of buffer smoothing (m). If set to 0, no buffer smoothing is applied."),
            type=QgsProcessingParameterNumber.Double,
            defaultValue=7
        )
        parameter.setMetadata({'widget_wrapper': {'decimals': 2}})
        self.addAdvancedParameter(parameter)

    def processAlgorithm(self, parameters, context, feedback):
        """
        Here is where the processing itself takes place.
        """
        path_tbk_input = self.parameterAsString(parameters, self.PATH_TBk_INPUT, context)
        path_output = os.path.join(path_tbk_input, "local_densities")
        ensure_dir(path_output)

        settings_path = QgsApplication.qgisSettingsDirPath()
        feedback.pushInfo(settings_path)

        tbk_tool_path = os.path.join(settings_path, "python/plugins/tbk_qgis")

        # boolean input: Use forest mixture degree / coniferous raster to calculate density zone mean?
        mg_use = self.parameterAsDouble(parameters, self.MG_USE, context)

        # raster input: forest mixture degree / coniferous raster to calculate density zone mean
        if mg_use:
            try:
                mg_input = str(self.parameterAsRasterLayer(parameters, self.MG_INPUT, context).source())
                if not os.path.splitext(mg_input)[1].lower() in (".tif", ".tiff"):
                    raise QgsProcessingException("mg_input must be TIFF file")
            except:
                raise QgsProcessingException(
                    'if "Use forest mixture degree / coniferous raster" is True, is mg_input must be TIFF file')

        # suffix for output files (string)
        output_suffix = self.parameterAsString(parameters, self.OUTPUT_SUFFIX, context)

        # input table for local density classes (matrix as one-dimensional list)
        table_density_classes = self.parameterAsMatrix(parameters, self.TABLE_DENSITY_CLASSES, context)
        if len(table_density_classes) % 4 != 0:
            raise QgsProcessingException("Invalid value for table_density_classes: list must contain a multiple of 4 elements.")
        # nuber of density classes
        n_cl = int(len(table_density_classes) / 4)

        # gather and check names of density classes
        cl_names = []
        for i in range(n_cl):
            cl_i = str(table_density_classes[i * 4])
            if cl_i == '':
                raise QgsProcessingException('Empty string ("") among names of DG-density-classes. Only strings with length >= 1 are valid names.')
            else:
                cl_i = cl_i.replace(' ', '_')
                if cl_i in cl_names:
                    raise QgsProcessingException('"' + cl_i + '" is a duplicate among the names of DG-density-classes. Valid names must be unique. Note that under the hood " " is replaced by "_".')
                else:
                    cl_names.append(cl_i)

        # function to check whether string is a number
        def is_number(x):
            try:
                float(x)
                return True
            except ValueError:
                return False

        # gather and check min-values of density classes
        cl_min = []
        for i in range(n_cl):
            min_i = str(table_density_classes[i * 4 + 1])
            if is_number(min_i):
                min_i = float(min_i)
                if min_i < 0 or min_i >= 100:
                    raise QgsProcessingException('The min of DG-class "' + cl_names[i] + '" is set to ' + str(min_i) + ', which is outside of the range valid: 0 >= min < 100.')
                else:
                    cl_min.append(float(min_i))
            else:
                raise QgsProcessingException('The min of DG-class "' + cl_names[i] + '" is set to "' + str(min_i) + '". But it must be a number (0 >= min < 100).')

        # gather and check max-values of density classes
        cl_max = []
        for i in range(n_cl):
            max_i = str(table_density_classes[i * 4 + 2])
            if is_number(max_i):
                max_i = float(max_i)
                if max_i <= 0 or max_i > 100:
                    raise QgsProcessingException('The max of DG-class "' + cl_names[i] + '" is set to ' + str(max_i) + ', which is outside of the range valid: 0 > max =< 100.')
                else:
                    cl_max.append(float(max_i))
            else:
                raise QgsProcessingException('The max of DG-class "' + cl_names[i] + '" is set to "' + str(max_i) + '". But it must be a number (0 >= max < 100).')

        # check whether min-value < max-value of density classes
        for i in range(n_cl):
            if cl_min[i] >= cl_max[i]:
                raise QgsProcessingException('The min and max of DG-class "' + cl_names[i] + '" are set to ' + str(cl_min[i]) + ' resp. to ' + str(cl_max[i]) + '. But min < max must be true.')

        # gather and check values for usage of large moving window
        cl_large_window = []
        for i in range(n_cl):
            large_window_i = str(table_density_classes[i * 4 + 3])
            if large_window_i in ['True', 'False']:
                cl_large_window.append(eval(large_window_i))
            else:
                raise QgsProcessingException('For DG-class "' + cl_names[i] + '" the usage of large moving window of is set to "' + str(large_window_i) + '". Set either to True or to False.')

        # determine whether DG is calculated for all layers (KS, US, MS, OS, UEB) (boolean)
        calc_all_dg = self.parameterAsBool(parameters, self.CALC_ALL_DG, context)

        # radius of circular moving window (in m)
        mw_rad = self.parameterAsDouble(parameters, self.MW_RAD, context)

        # large radius of circular moving window (in m)
        mw_rad_large = self.parameterAsDouble(parameters, self.MW_RAD_LARGE, context)

        # minimum size for dense/sparse "clumps" (m^2)
        min_size_clump = self.parameterAsDouble(parameters, self.MIN_SIZE_CLUMP, context)

        # minimum size for stands to apply calculation of local densities (m^2)
        min_size_stand = self.parameterAsDouble(parameters, self.MIN_SIZE_STAND, context)

        # threshold for minimal holes within local density polygons (m^2)
        holes_thresh = self.parameterAsDouble(parameters, self.HOLES_THRESH, context)

        # method to remove thin parts and details of zones by minus / plus buffering (boolean)
        buffer_smoothing = self.parameterAsBool(parameters, self.BUFFER_SMOOTHING, context)

        # buffer distance of buffer smoothing (m)
        buffer_smoothing_dist = self.parameterAsDouble(parameters, self.BUFFER_SMOOTHING_DIST, context)

        start_time = time.time()

        # lump together density classes
        den_classes = []
        for i in range(n_cl):
            den_classes.append(
                {
                    "class": cl_names[i],  # string / as is
                    "min": cl_min[i] / 100,  # [0%, 100%] --> [0, 1]
                    "max": cl_max[i] / 100,  # [0%, 100%] --> [0, 1]
                    "large_window": cl_large_window[i]  # boolean / as is
                }
            )
        # for i in den_classes: print(i)

        # any large moving window? --> True / False
        large_window_all = []
        for i in den_classes:
            large_window_all.append(i["large_window"])
        any_large_window = any(large_window_all)
        # print(large_window_all)
        # print("any large window?")
        # print(any_large_window)

        # any non-large moving window? --> True / False
        non_large_window_all = []
        for i in large_window_all:
            non_large_window_all.append(i == False)
        any_non_large_window = any(non_large_window_all)
        # print(non_large_window_all)
        # print("any non-large window?")
        # print(any_non_large_window)

        path_dg = os.path.join(path_tbk_input, "dg_layers/dg_layer.tif")

        path_dg_ks = os.path.join(path_tbk_input, "dg_layers/dg_layer_ks.tif")
        path_dg_us = os.path.join(path_tbk_input, "dg_layers/dg_layer_us.tif")
        path_dg_ms = os.path.join(path_tbk_input, "dg_layers/dg_layer_ms.tif")
        path_dg_os = os.path.join(path_tbk_input, "dg_layers/dg_layer_os.tif")
        path_dg_ueb = os.path.join(path_tbk_input, "dg_layers/dg_layer_ueb.tif")

        path_stands = os.path.join(path_tbk_input, "TBk_Bestandeskarte.gpkg")

        stands_all = QgsVectorLayer(path_stands, 'Stands', 'ogr')
        # add fid (--> fid_stand) as unique identifier for later joins to original stands
        param = {'INPUT': stands_all, 'FIELD_NAME': 'fid_stand', 'FIELD_TYPE': 1, 'FIELD_LENGTH': 10,
                 'FIELD_PRECISION': 0, 'FORMULA': ' "fid" ', 'OUTPUT': 'TEMPORARY_OUTPUT'}
        algoOutput = processing.run("native:fieldcalculator", param)
        stands_all = algoOutput["OUTPUT"]

        # load dg raster "DG" (Hauptschicht = hs = DG_OS + DG_UEB)
        hs = QgsRasterLayer(path_dg)

        res_hs = hs.rasterUnitsPerPixelY()

        # load other DG rasters (needed only to determine DGs per zone)
        if calc_all_dg:
            dg_ks = QgsRasterLayer(path_dg_ks)
            dg_us = QgsRasterLayer(path_dg_us)
            dg_ms = QgsRasterLayer(path_dg_ms)
            dg_os = QgsRasterLayer(path_dg_os)
            dg_ueb = QgsRasterLayer(path_dg_ueb)

        # helper functions (start with f_)

        # helper function to save intermediate vector data & tables
        def f_save_as_gpkg(input, name, path=path_output):
            if type(input) == str:
                input = QgsVectorLayer(input, '', 'ogr')
            path_ = os.path.join(path, name + ".gpkg")
            ctc = QgsProject.instance().transformContext()
            QgsVectorFileWriter.writeAsVectorFormatV3(input, path_, ctc, getVectorSaveOptions('GPKG', 'utf-8'))

        # select stands with min. area size
        param = {'INPUT': stands_all, 'EXPRESSION': '$area > ' + str(min_size_stand), 'OUTPUT': 'TEMPORARY_OUTPUT'}
        algoOutput = processing.run("native:extractbyexpression", param)
        stands = algoOutput["OUTPUT"]

        # reduce attributes
        col_names = ['fid_stand', 'ID', 'DG']
        if calc_all_dg:
            col_names_rest = ['DG_ks', 'DG_us', 'DG_ms', 'DG_os', 'DG_ueb', 'NH', 'hdom']
        else:
            col_names_rest = ['NH', 'hdom']
        col_names[len(col_names):] = col_names_rest
        if not mg_use:
            col_names.remove('NH')
        param = {'INPUT': stands, 'FIELDS': col_names, 'OUTPUT': 'TEMPORARY_OUTPUT'}
        algoOutput = processing.run("native:retainfields", param)
        stands = algoOutput["OUTPUT"]

        # suffix attribute columns with _stand
        for col in col_names[1:]:  # 1st of col_names = fid_stand = tmp. id is not suffixed a 2nd time!
            param = {'INPUT': stands, 'FIELD': col, 'NEW_NAME': col + '_stand', 'OUTPUT': 'TEMPORARY_OUTPUT'}
            algoOutput = processing.run("native:renametablefield", param)
            stands = algoOutput["OUTPUT"]

        # recalculate stand area
        param = {'INPUT': stands, 'FIELD_NAME': 'area_stand', 'FIELD_TYPE': 1, 'FIELD_LENGTH': 10, 'FIELD_PRECISION': 0,
                 'FORMULA': 'round($area)', 'OUTPUT': 'TEMPORARY_OUTPUT'}
        algoOutput = processing.run("native:fieldcalculator", param)
        stands = algoOutput["OUTPUT"]

        # check attributes of selected stands
        # print("attributes of selected stands:")
        # for field in stands.fields(): print(field.name(), field.typeName())

        # if required focal statistic with "regular" moving window
        if any_non_large_window:
            # size = width of moving window in pixels (odd nummer)
            size = math.floor(mw_rad / res_hs * 2)
            if size % 2 == 0:
                size = size + 1
            param = {'input': hs, 'selection': hs, 'method': 0, 'size': size, 'gauss': None, 'quantile': '', '-c': True,
                     '-a': False, 'weight': '', 'output': 'TEMPORARY_OUTPUT', 'GRASS_REGION_PARAMETER': None,
                     'GRASS_REGION_CELLSIZE_PARAMETER': 0, 'GRASS_RASTER_FORMAT_OPT': '',
                     'GRASS_RASTER_FORMAT_META': ''}
            algoOutput = processing.run("grass7:r.neighbors", param)
            dg_focal = algoOutput["output"]
            dg_focal = QgsRasterLayer(dg_focal)

        # if required focal statistic with large moving window
        if any_large_window:
            # size = width of moving window in pixels (odd nummer)
            size = math.floor(mw_rad_large / res_hs * 2)
            if size % 2 == 0:
                size = size + 1
            param = {'input': hs, 'selection': hs, 'method': 0, 'size': size, 'gauss': None, 'quantile': '', '-c': True,
                     '-a': False, 'weight': '', 'output': 'TEMPORARY_OUTPUT', 'GRASS_REGION_PARAMETER': None,
                     'GRASS_REGION_CELLSIZE_PARAMETER': 0, 'GRASS_RASTER_FORMAT_OPT': '',
                     'GRASS_RASTER_FORMAT_META': ''}
            algoOutput = processing.run("grass7:r.neighbors", param)
            dg_focal_2 = algoOutput["output"]
            dg_focal_2 = QgsRasterLayer(dg_focal_2)

        # list to gather polygons of oll density classes
        den_polys = []

        for cl in den_classes:
            # input / parameters for a certain density class
            min = str(cl["min"] - 0.0001)
            max = str(cl["max"] + 0.0001)
            cl_ = str(cl["class"])
            if cl["large_window"]:
                focal_in_use = dg_focal_2
            else:
                focal_in_use = dg_focal

            # stats of used focal layer
            focal_stats = focal_in_use.dataProvider().bandStatistics(1, QgsRasterBandStats.All)
            focal_min = focal_stats.minimumValue
            focal_max = focal_stats.maximumValue
            # if range of density class does not overlap with with range of values of focal layer continue with next class
            if float(max) <= focal_min or float(min) >= focal_max:
                continue

            # reclassify raster: 1 = within density range, else or no data
            param = {'INPUT_RASTER': focal_in_use, 'RASTER_BAND': 1, 'TABLE': [min, max, '1'], 'NO_DATA': 0,
                     'RANGE_BOUNDARIES': 0, 'NODATA_FOR_MISSING': True, 'DATA_TYPE': 1, 'OUTPUT': 'TEMPORARY_OUTPUT'}
            algoOutput = processing.run("native:reclassifybytable", param)
            recl = algoOutput["OUTPUT"]

            # polygonize
            param = {'INPUT': recl, 'BAND': 1, 'FIELD': 'DN', 'EIGHT_CONNECTEDNESS': False, 'EXTRA': '',
                     'OUTPUT': 'TEMPORARY_OUTPUT'}
            algoOutput = processing.run("gdal:polygonize", param)
            polys_cl = algoOutput["OUTPUT"]
            # f_save_as_gpkg(polys_cl, "0_class_" + cl_)

            # add density class as attribute
            param = {'INPUT': polys_cl, 'FIELD_NAME': 'class', 'FIELD_TYPE': 2, 'FIELD_LENGTH': 0,
                     'FIELD_PRECISION': 0, 'FORMULA': "to_string( '" + cl_ + "' )", 'OUTPUT': 'TEMPORARY_OUTPUT'}
            algoOutput = processing.run("native:fieldcalculator", param)
            polys_cl = algoOutput["OUTPUT"]
            # f_save_as_gpkg(polys_cl, "3_class_" + cl_)

            den_polys.append(polys_cl)

        # merge listed layers with density polygons of different classes
        param = {'LAYERS': den_polys, 'CRS': None, 'OUTPUT': 'TEMPORARY_OUTPUT'}
        # 'TEMPORARY_OUTPUT' does work as output! --> all off a sudden all listed layers are merged (unclear which code
        # manipulation(s) enable this) --> temp. .gpkg as output / workaround not needed any more!
        # path_tmp_den_polys = os.path.join(path_output, "tmp_den_polys.gpkg") # hopefully no future need for this ...
        # param =  {'LAYERS': den_polys, 'CRS': None, 'OUTPUT': path_tmp_den_polys} # ... since deleting tmp. .gpkg is an unsolved issue
        algoOutput = processing.run("native:mergevectorlayers", param)
        den_polys = algoOutput["OUTPUT"]
        # f_save_as_gpkg(den_polys, "den_polys_polygonized")

        # remove holes smaller than threshold
        param = {'INPUT': den_polys, 'MIN_AREA': holes_thresh, 'OUTPUT': 'TEMPORARY_OUTPUT'}
        algoOutput = processing.run("native:deleteholes", param)
        den_polys = algoOutput["OUTPUT"]
        # f_save_as_gpkg(den_polys, "den_polys_without_holes")

        # apply buffer smoothing if ...
        if buffer_smoothing and buffer_smoothing_dist != 0:
            param = {'INPUT': den_polys, 'DISTANCE': -buffer_smoothing_dist, 'SEGMENTS': 5, 'END_CAP_STYLE': 0,
                     'JOIN_STYLE': 0, 'MITER_LIMIT': 2, 'DISSOLVE': False, 'SEPARATE_DISJOINT': False,
                     'OUTPUT': 'TEMPORARY_OUTPUT'}
            algoOutput = processing.run("native:buffer", param)
            den_polys = algoOutput["OUTPUT"]
            # f_save_as_gpkg(den_polys, "den_polys_minus_buffered")
            param = {'INPUT': den_polys, 'DISTANCE': buffer_smoothing_dist + 1.5, 'SEGMENTS': 5, 'END_CAP_STYLE': 0,
                     'JOIN_STYLE': 0, 'MITER_LIMIT': 2, 'DISSOLVE': False, 'SEPARATE_DISJOINT': False,
                     'OUTPUT': 'TEMPORARY_OUTPUT'}
            algoOutput = processing.run("native:buffer", param)
            den_polys = algoOutput["OUTPUT"]
            # f_save_as_gpkg(den_polys, "den_polys_plus_buffered")

        # check attribute of selected stands
        # for field in stands.fields(): print(field.name(), field.typeName())
        # list all fields of selected stands (fid is not included!)
        stands_fields = []
        for field in stands.fields():
            stands_fields.append(field.name())
        # print(stands_fields)
        param = {'INPUT': den_polys, 'OVERLAY': stands, 'INPUT_FIELDS': ['class'], 'OVERLAY_FIELDS': stands_fields,
                 'OVERLAY_FIELDS_PREFIX': '', 'OUTPUT': 'TEMPORARY_OUTPUT', 'GRID_SIZE': None}
        algoOutput = processing.run("native:intersection", param)
        den_polys = algoOutput["OUTPUT"]
        # f_save_as_gpkg(den_polys, "den_polys_intersected")

        # multi parts --> single parts
        param = {'INPUT': den_polys, 'OUTPUT': 'TEMPORARY_OUTPUT'}
        algoOutput = processing.run("native:multiparttosingleparts", param)
        den_polys = algoOutput["OUTPUT"]
        # f_save_as_gpkg(den_polys, "den_polys_sigle_parts")

        # drop local densities polygons having areas below min. area
        param = {'INPUT': den_polys, 'EXPRESSION': '$area > ' + str(min_size_clump), 'OUTPUT': 'TEMPORARY_OUTPUT'}
        algoOutput = processing.run("native:extractbyexpression", param)
        den_polys = algoOutput["OUTPUT"]
        # f_save_as_gpkg(den_polys, "den_polys_larger_than_min_area")

        # calculate area of local densities
        param = {'INPUT': den_polys, 'FIELD_NAME': 'area', 'FIELD_TYPE': 1, 'FIELD_LENGTH': 10, 'FIELD_PRECISION': 0,
                 'FORMULA': 'round($area)', 'OUTPUT': 'TEMPORARY_OUTPUT'}
        algoOutput = processing.run("native:fieldcalculator", param)
        den_polys = algoOutput["OUTPUT"]

        # calculate ratio of area of local density to area of stand
        param = {'INPUT': den_polys, 'FIELD_NAME': 'area_pct', 'FIELD_TYPE': 0, 'FIELD_LENGTH': 0, 'FIELD_PRECISION': 0,
                 'FORMULA': 'round($area / area_stand, 2)', 'OUTPUT': 'TEMPORARY_OUTPUT'}
        algoOutput = processing.run("native:fieldcalculator", param)
        den_polys = algoOutput["OUTPUT"]

        # resample Mishungsgrad / Nadelholzanteil raster to resolution 1m x 1m within extent of Deckungsgrad (= hs = DG)
        # 'RESAMPLING': 0 --> Nearest Neighbour
        if mg_use:
            param = {'INPUT': mg_input, 'SOURCE_CRS': None, 'TARGET_CRS': None, 'RESAMPLING': 0, 'NODATA': None,
                     'TARGET_RESOLUTION': 1, 'OPTIONS': '', 'DATA_TYPE': 0, 'TARGET_EXTENT': hs.extent(),
                     'TARGET_EXTENT_CRS': None, 'MULTITHREADING': False, 'EXTRA': '', 'OUTPUT': 'TEMPORARY_OUTPUT'}
            algoOutput = processing.run("gdal:warpreproject", param)
            mg = algoOutput["OUTPUT"]

        # zonal statistics
        if calc_all_dg:
            rasters_4_stats = {'DG': hs, 'DG_ks': dg_ks, 'DG_us': dg_us, 'DG_ms': dg_ms, 'DG_os': dg_os, 'DG_ueb': dg_ueb}
        else:
            rasters_4_stats = {'DG': hs}
        if mg_use:
            rasters_4_stats['NH'] = mg

        for raster in rasters_4_stats:
            # actual zonal stats: 'STATISTICS': [2] --> mean
            param = {'INPUT': den_polys, 'INPUT_RASTER': rasters_4_stats[raster], 'RASTER_BAND': 1,
                     'COLUMN_PREFIX': raster + '_', 'STATISTICS': [2], 'OUTPUT': 'TEMPORARY_OUTPUT'}
            algoOutput = processing.run("native:zonalstatisticsfb", param)
            den_polys = algoOutput["OUTPUT"]
            # get rid attribute suffix _mean
            param = {'INPUT': den_polys, 'FIELD': raster + '_mean', 'NEW_NAME': raster, 'OUTPUT': 'TEMPORARY_OUTPUT'}
            algoOutput = processing.run("native:renametablefield", param)
            den_polys = algoOutput["OUTPUT"]
        # f_save_as_gpkg(den_polys, "den_polys_zonal_stats")

        # from by now existing attributes of density polygons aggregate a (long) summary table for each combination of
        # density class & stand
        # - fid_stand: tmp. id of each stand allowing later to join to original stand layer
        # - class:     local density class
        # - area:      total area of a class within a stand [m^2]
        # - area_pct:  ratio of total area (s. above) to area of stand [0, 1]
        # - dg:        mean DG of HS (= DG_OS + DG_UEB) of all subsurface of a class with the same stand [0, 100] (%)
        # - nh:        mean NH  of all subsurface of a class with the same stand [0, 100] (%)
        param = {'INPUT': den_polys, 'OUTPUT': 'TEMPORARY_OUTPUT'}
        algoOutput = processing.run("native:dropgeometries", param)
        aggregates = [
                {'aggregate': 'first_value', 'delimiter': ',', 'input': '"fid_stand"', 'length': 0, 'name': 'fid_stand',
                 'precision': 0, 'sub_type': 0, 'type': 2, 'type_name': 'integer'},
                {'aggregate': 'first_value', 'delimiter': ',', 'input': '"class"', 'length': 0, 'name': 'class',
                 'precision': 0, 'sub_type': 0, 'type': 10, 'type_name': 'text'},
                {'aggregate': 'sum', 'delimiter': ',', 'input': '"area"', 'length': 0, 'name': 'area', 'precision': 0,
                 'sub_type': 0, 'type': 2, 'type_name': 'integer'},
                {'aggregate': 'first_value', 'delimiter': ',', 'input': 'round(sum(area) / mean(area_stand), 2)',
                 'length': 0, 'name': 'area_pct', 'precision': 0, 'sub_type': 0, 'type': 6,
                 'type_name': 'double precision'},
                {'aggregate': 'first_value', 'delimiter': ',', 'input': 'round(sum(DG * area) / sum(area) * 100)',
                 'length': 0, 'name': 'dg', 'precision': 0, 'sub_type': 0, 'type': 4, 'type_name': 'integer'}
            ]
        if mg_use:
            aggregates.append(
                {'aggregate': 'first_value', 'delimiter': ',', 'input': 'round(sum(NH * area) / sum(area))',
                 'length': 0, 'name': 'nh', 'precision': 0, 'sub_type': 0, 'type': 2, 'type_name': 'integer'}
            )
        param = {
            'INPUT': algoOutput["OUTPUT"],
            'GROUP_BY': 'Array( "fid_stand", "class")',
            'AGGREGATES': aggregates,
            'OUTPUT': 'TEMPORARY_OUTPUT'
        }
        algoOutput = processing.run("native:aggregate", param)
        statstable_long = algoOutput["OUTPUT"]
        # f_save_as_gpkg(statstable_long, "statstable_long")

        # all density classes
        all_classes = []
        for cl in den_classes:
            all_classes.append(str(cl["class"]))
        # all value types included in stats on local densities (s. long table above)
        value_types = ['area', 'area_pct', 'dg']
        if mg_use:
            value_types.append('nh')
        # list of new fields for stats on local densities
        new_fields = []
        for cl in all_classes:
            for v in value_types:
                new_fields.append("z" + cl + "_" + v)
        # add new fields / attributes to original stands layer
        new_attributes = []
        for i in new_fields:
            if i[-8:] == "area_pct":
                new_attributes.append(QgsField(i, QVariant.Double))
            else:
                new_attributes.append(QgsField(i, QVariant.Int))
        pr = stands_all.dataProvider()
        pr.addAttributes(new_attributes)
        stands_all.updateFields()
        # populate new attributes with values from (long) summary table
        for f in statstable_long.getFeatures():
            with edit(stands_all):
                for stand in stands_all.getFeatures():
                    if stand["fid_stand"] == f["fid_stand"]:
                        for v in value_types:
                            stand["z" + f["class"] + "_" + v] = f[v]
                    stands_all.updateFeature(stand)

        # sequence fields of local densities for output. note: tmp. id for stands (= fid_stand) is not part of output!
        field_names = ['class', 'ID_stand', 'area', 'area_stand', 'area_pct']
        for raster in rasters_4_stats:
            field_names.append(raster)
            field_names.append(raster + '_stand')
        field_names.append('hdom_stand')
        # print(field_names)

        # select fields for local-density-output according sequence created above and prettify zonal-stats-attributes
        fields_mapping = []
        for field in field_names:
            if field == 'class':
                type = int(10)
                type_name = 'text'
                exp = '"class"'  # keep as is
            elif field == 'area_pct':
                type = int(6)
                type_name = 'double precision'
                exp = '"area_pct"'  # keep as is
            elif field == 'NH':
                type = int(2)
                type_name = 'integer'
                exp = 'round("NH")'  # already %-tage
            elif field != 'NH' and field in rasters_4_stats:
                type = int(2)
                type_name = 'integer'
                exp = 'round("' + field + '" * 100)'  # [0, 1] --> [0, 100]%
            else:
                type = int(2)
                type_name = 'integer'
                exp = '' + '"' + field + '"' + ''  # keep as is
            map = {'alias': '', 'comment': '', 'expression': exp, 'length': 0, 'name': field, 'precision': 0,
                   'sub_type': 0, 'type': type, 'type_name': type_name}
            fields_mapping.append(map)
        param = {'INPUT': den_polys, 'FIELDS_MAPPING': fields_mapping, 'OUTPUT': 'TEMPORARY_OUTPUT'}
        algoOutput = processing.run("native:refactorfields", param)
        den_polys = algoOutput["OUTPUT"]

        # save local densities output
        path_local_den_out = os.path.join(path_output, "TBk_local_densities" + output_suffix + ".gpkg")
        ctc = QgsProject.instance().transformContext()
        QgsVectorFileWriter.writeAsVectorFormatV3(den_polys, path_local_den_out, ctc,
                                                  getVectorSaveOptions('GPKG', 'utf-8'))

        # tmp. id (= fid_stand) is not part of output!
        param = {'INPUT': stands_all, 'COLUMN': ['fid_stand'], 'OUTPUT': 'TEMPORARY_OUTPUT'}
        algoOutput = processing.run("native:deletecolumn", param)
        stands_all = algoOutput["OUTPUT"]
        # output original stands + local density stats
        path_stands_out = os.path.join(path_output, "TBk_Bestandeskarte_local_densities" + output_suffix + ".gpkg")
        ctc = QgsProject.instance().transformContext()
        QgsVectorFileWriter.writeAsVectorFormatV3(stands_all, path_stands_out, ctc,
                                                  getVectorSaveOptions('GPKG', 'utf-8'))

        feedback.pushInfo("====================================================================")
        feedback.pushInfo("FINISHED")
        feedback.pushInfo("TOTAL PROCESSING TIME: %s (h:min:sec)" % str(timedelta(seconds=(time.time() - start_time))))
        feedback.pushInfo("====================================================================")

        return {self.OUTPUT: path_output}

    def name(self):
        """
        Returns the algorithm name, used for identifying the algorithm. This
        string should be fixed for the algorithm, and must not be localised.
        The name should be unique within each provider. Names should contain
        lowercase alphanumeric characters only and no spaces or other
        formatting characters.
        """
        return 'TBk postprocess local density'

    def displayName(self):
        """
        Returns the translated algorithm name, which should be used for any
        user-visible display of the algorithm name.
        """
        return self.tr(self.name())

    def group(self):
        """
        Returns the name of the group this algorithm belongs to. This string
        should be localised.
        """
        # return self.tr(self.groupId())
        return '2 TBk Postprocessing'

    def groupId(self):
        """
        Returns the unique ID of the group this algorithm belongs to. This
        string should be fixed for the algorithm, and must not be localised.
        The group id should be unique within each provider. Group id should
        contain lowercase alphanumeric characters only and no spaces or other
        formatting characters.
        """
        return 'postproc'

    def tr(self, string):
        return QCoreApplication.translate('Processing', string)

    def createInstance(self):
        return TBkPostprocessLocalDensity()