# -*- coding: utf-8 -*-
# *************************************************************************** #
# Merge multiple TBk stand maps.
#
# Authors: Attilio Benini (BFH-HAFL)
# *************************************************************************** #
"""
/***************************************************************************
    TBk: Toolkit Bestandeskarte (QGIS Plugin)
    Toolkit for the generating and processing forest stand maps
    Copyright (C) 2025 BFH-HAFL (hannes.horneber@bfh.ch, christian.rosset@bfh.ch)

    This program is free software: you can redistribute it and/or modify
    it under the terms of the GNU Affero General Public License as published by
    the Free Software Foundation, either version 3 of the License, or
    (at your option) any later version.

    This program is distributed in the hope that it will be useful,
    but WITHOUT ANY WARRANTY; without even the implied warranty of
    MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
    GNU Affero General Public License for more details.

    You should have received a copy of the GNU Affero General Public License
    along with this program.  If not, see <https://www.gnu.org/licenses/>.
 ***************************************************************************/
"""
# This will get replaced with a git SHA1 when you do a git archive
__revision__ = '$Format:%H$'

import math
import time
from datetime import datetime, timedelta
import pandas as pd
# import string # not needed since some code involving chr() replaces string.ascii_uppercase

from qgis.PyQt.QtCore import QCoreApplication, QVariant
from qgis.core import (
    QgsProcessing,
    QgsField,
    QgsProcessingAlgorithm,
    QgsProcessingParameterVectorDestination,
    QgsProcessingParameterDefinition,
    QgsProcessingParameterMultipleLayers,
    QgsProcessingParameterEnum
)
import processing

from tbk_qgis.tbk.utility.tbk_utilities import *


class TBkPostprocessMergeStandMaps(QgsProcessingAlgorithm):

    def addAdvancedParameter(self, parameter):
        parameter.setFlags(parameter.flags() | QgsProcessingParameterDefinition.FlagAdvanced)
        return self.addParameter(parameter)

    # Constants used to refer to parameters and outputs. They will be
    # used when calling the algorithm from another algorithm, or when
    # calling from the QGIS console.

    # list of TBK mamp layer to merge
    TBK_MAP_LAYERS = 'tbk_map_layers'

    # dropdown for type ID prefix
    ID_PREFIX = 'id_prefix'

    # merged TBk map layer
    OUTPUT = 'OUTPUT'

    def initAlgorithm(self, config):
        """
        Here we define the inputs and output of the algorithm, along
        with some other properties.
        """

        # list of TBK mamp layer to merge
        self.addParameter(
            QgsProcessingParameterMultipleLayers(
                self.TBK_MAP_LAYERS,
                self.tr('TBk map layers')
            )
        )

        # dropdown for type ID prefix
        self.addParameter(
            QgsProcessingParameterEnum(
                self.ID_PREFIX,
                self.tr(
                    'ID prefix: unique value for each TBk map layer'
                    '\n A, B, C, ... alphabetical A ... Z, AA ... AZ, BA ...'
                    '\n 1, 2, 3, ... numerical 1 to N'
                ),
                options=['A, B, C, ... ', '1, 2, 3, ... '],
                defaultValue=0,
                optional=False
            )
        )

        # merged TBk map layer
        self.addParameter(
            QgsProcessingParameterVectorDestination(
                self.OUTPUT,
                self.tr('Merged TBk map')
            )
        )

    def processAlgorithm(self, parameters, context, feedback):
        """
         Here is where the processing itself takes place.
         """

        # list of TBK mamp layer to merge
        tbk_map_layers = self.parameterAsLayerList(parameters, self.TBK_MAP_LAYERS, context)

        # dropdown for type ID prefix
        id_prefix = self.parameterAsInt(parameters, self.ID_PREFIX, context)
        prefix_type = ['alphabetical', 'numerical'][id_prefix]

        # merged TBk map layer
        output = self.parameterAsOutputLayer(parameters, self.OUTPUT, context)

        start_time = time.time()

        # gather information: table index and most north-western bounding box coordinates of listed TBk map layers
        n = []
        XMIN = []
        xmin = []
        YMAX = []
        ymax = []
        for i in range(len(tbk_map_layers)):
            n.append(i)
            ext = tbk_map_layers[i].extent()
            XMIN.append(math.floor(ext.xMinimum() / 1000))  # km-x-coordinate closed westwards
            xmin.append(ext.xMinimum())
            YMAX.append(math.ceil(ext.yMaximum() / 1000))  # km-y-coordinate closed northwards
            ymax.append(ext.yMaximum())
        info_tab = pd.DataFrame({'index': n, 'XMIN': XMIN, 'xmin': xmin, 'YMAX': YMAX, 'ymax': ymax})
        # print(info_tab)

        # sort by 1) most northern comes 1st & 2) most western comes 1st
        # in two phases 1) over all by a 1 km x 1 km grid, 2) within each grid cell
        info_tab = info_tab.sort_values(by=['YMAX', 'XMIN', 'ymax', 'xmin'], ascending=[False, True, False, True])
        # print(info_tab)

        # add ID-prefixes to table
        if prefix_type == 'alphabetical':
            def f_prefix_abc():
                # alphabet = string.ascii_uppercase
                alphabet = [chr(code) for code in list(range(65, 91))]  # 65 = A, 90 = Z
                s = [alphabet[0]]
                while 1:
                    yield ''.join(s)
                    l = len(s)
                    for i in range(l - 1, -1, -1):
                        if s[i] != alphabet[-1]:
                            s[i] = alphabet[alphabet.index(s[i]) + 1]
                            s[i + 1:] = [alphabet[0]] * (l - i - 1)
                            break
                    else:
                        s = [alphabet[0]] * (l + 1)

            prefix_abc = f_prefix_abc()
            info_tab['prefix'] = [next(prefix_abc) for _ in range(len(tbk_map_layers))]
        if prefix_type == 'numerical':
            info_tab['prefix'] = list(range(1, len(tbk_map_layers) + 1))
        # print(info_tab)

        indexes = list(info_tab['index'])
        # print(type(indexes[0]))
        prefixes = list(info_tab['prefix'])
        # print(type(prefixes[0]))
        # list of placeholders to later insert manipulated TBk-maps in correct sequence
        tbk_map_layers_new = [None] * len(tbk_map_layers)

        for i in range(len(tbk_map_layers)):
            index = indexes[i]
            prefix = prefixes[i]

            # rename ID --> ID_pre_merge
            param = {'INPUT': tbk_map_layers[index], 'FIELD': 'ID', 'NEW_NAME': 'ID_pre_merge',
                     'OUTPUT': 'TEMPORARY_OUTPUT'}
            algoOutput = processing.run("native:renametablefield", param)
            tbk_map = algoOutput["OUTPUT"]

            # add attribute ID_meta & ID
            if prefix_type == 'numerical':
                ID_meta = QgsField('ID_meta', QVariant.Int)
            else:
                ID_meta = QgsField('ID_meta', QVariant.String)
            ID = QgsField('ID', QVariant.String)
            pr = tbk_map.dataProvider()
            pr.addAttributes([ID_meta, ID])
            tbk_map.updateFields()

            # populate attribute ID_meta & ID with values
            with edit(tbk_map):
                for f in tbk_map.getFeatures():
                    f['ID_meta'] = prefix
                    f['ID'] = str(prefix) + '_' + str(f['ID_pre_merge'])
                    tbk_map.updateFeature(f)

            # insert manipulated TBk-map into list
            tbk_map_layers_new[i] = tbk_map

        param = {'LAYERS': tbk_map_layers_new, 'CRS': None, 'OUTPUT': 'TEMPORARY_OUTPUT'}
        algoOutput = processing.run("native:mergevectorlayers", param)
        tbk_map_merged = algoOutput["OUTPUT"]

        # drop attribute layer & path (add by native:mergevectorlayers)
        param = {'INPUT': tbk_map_merged, 'COLUMN': ['layer', 'path'], 'OUTPUT': output}
        algoOutput = processing.run("native:deletecolumn", param)
        tbk_map_merged = algoOutput["OUTPUT"]

        feedback.pushInfo("====================================================================")
        feedback.pushInfo("FINISHED")
        feedback.pushInfo("TOTAL PROCESSING TIME: %s (h:min:sec)" % str(timedelta(seconds=(time.time() - start_time))))
        feedback.pushInfo("====================================================================")

        return {self.OUTPUT: tbk_map_merged}

    def name(self):
        """
        Returns the algorithm name, used for identifying the algorithm. This
        string should be fixed for the algorithm, and must not be localised.
        The name should be unique within each provider. Names should contain
        lowercase alphanumeric characters only and no spaces or other
        formatting characters.
        """
        return 'TBk postprocess merge stand maps'

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

    def shortHelpString(self):
        return """<html><body><p><!DOCTYPE HTML PUBLIC "-//W3C//DTD HTML 4.0//EN" "http://www.w3.org/TR/REC-html40/strict.dtd">
<html><head><meta name="qrichtext" content="1" /><style type="text/css">
</style></head><body style=" font-family:'MS Shell Dlg 2'; font-size:8.3pt; font-weight:400; font-style:normal;">
<p style=" margin-top:0px; margin-bottom:0px; margin-left:0px; margin-right:0px; -qt-block-indent:0; text-indent:0px;">Merges multiple TBk stand maps to one layer and remakes the attribute <i>ID</i>, such that it still functions as unique identifier for stands within the return. The former attribute <i>ID</i> is renamed and kept as <i>ID_pre_merge</i>, which is equivalent to the new <i>ID</i>'s suffix, while the new <i>ID</i>'s prefix corresponds to a unique value for each TBk stand map being merged. The prefix is also included as attribute <i>ID_meta</i>.</p></body></html></p>
<h2>Input parameters</h2>
<h3>TBk map layers</h3>
<p>Liste of TBk stand maps to be merged</p>
<h3>ID prefix</h3>
<p>Type of prefix incorporated into the remade <i>ID</i></p>
<h2>Outputs</h2>
<h3>Merged TBk map</h3>
<p>One layer including the merged TBk stand map with a unique because remade attribute <i>ID</i> + two new attributes: <i>ID_pre_merge</i> (suffix of <i>ID</i>) and <i>ID_meta</i> (prefix of <i>ID</i>).</p>
<p><!DOCTYPE HTML PUBLIC "-//W3C//DTD HTML 4.0//EN" "http://www.w3.org/TR/REC-html40/strict.dtd">
<html><head><meta name="qrichtext" content="1" /><style type="text/css">
</style></head><body style=" font-family:'MS Shell Dlg 2'; font-size:8.3pt; font-weight:400; font-style:normal;">
<p style="-qt-paragraph-type:empty; margin-top:0px; margin-bottom:0px; margin-left:0px; margin-right:0px; -qt-block-indent:0; text-indent:0px;"><br /></p></body></html></p><br><p align="right">Algorithm author: Attilio Benini @ BFH-HAFL (2024)</p></body></html>"""

    def createInstance(self):
        return TBkPostprocessMergeStandMaps()
