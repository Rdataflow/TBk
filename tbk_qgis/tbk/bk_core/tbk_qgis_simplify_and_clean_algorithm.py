# -*- coding: utf-8 -*-

""" TBk simplify and clean algorithm.
This QGIS plugin allows to simplify the stand boundaries and to clean the data by removing the small stands.

This program is free software; you can redistribute it and/or modify
it under the terms of the GNU General Public License as published by
the Free Software Foundation; either version 2 of the License, or
(at your option) any later version.
"""

__authors__ = 'Dominique Weber, Christoph Schaller'
__copyright__ = '(C) 2024 by Berner Fachhochschule HAFL'
__date__ = '2020-08-03'
__email__ = "christian.rosset@bfh.ch"
# This will get replaced with a git SHA1 when you do a git archive
__revision__ = '$Format:%H$'

import logging
from qgis.core import QgsProcessingParameterString, QgsProcessingParameterNumber, \
    QgsProcessingParameterBoolean, QgsProcessingParameterFile
from tbk_qgis.tbk.bk_core.post_process import post_process
from tbk_qgis.tbk.bk_core.tbk_qgis_processing_algorithm import TBkProcessingAlgorithm
from tbk_qgis.tbk.utility.persistence_utility import write_dict_to_toml_file
from tbk_qgis.tbk.utility.tbk_utilities import ensure_dir


class TBkSimplifyAndCleanAlgorithm(TBkProcessingAlgorithm):
    """
    todo
    """
    # ------- Define Constants -------#
    # Constants used to refer to parameters and outputs.

    # These constants will be used when calling the algorithm from another algorithm,
    # or when calling from the QGIS console.

    # Folder for storing all input files and saving output files
    WORKING_ROOT = "working_root"
    # File storing configuration parameters
    CONFIG_FILE = "config_file"
    # Default log file name
    LOGFILE_NAME = "logfile_name"
    # Simplification tolerance
    SIMPLIFICATION_TOLERANCE = "simplification_tolerance"

    # Additional parameters
    # Min. area to eliminate small stands
    MIN_AREA_M2 = "min_area_m2"
    # Delete temporary files and fields
    DEL_TMP = "del_tmp"

    def initAlgorithm(self, config=None):
        """
        Here we define the inputs and output of the algorithm, along with some other properties.
        """

        # --- Parameters generated by the stand delineation algorithm

        # Config file containing all parameter key-value pairs
        self.addParameter(QgsProcessingParameterFile(self.CONFIG_FILE,
                                                     'Configuration file to set the algorithm parameters. The bellow '
                                                     'non-optional parameters must still be set but will not be used.',
                                                     optional=True))

        # These parameters are only displayed a config parameter is given
        if not config:
            self.addParameter(QgsProcessingParameterFile(self.WORKING_ROOT,
                                                         "Working root folder. This folder must contain the outputs "
                                                         "from previous steps.",
                                                         behavior=QgsProcessingParameterFile.Folder))

        # --- Advanced Parameters
        parameter = QgsProcessingParameterString(self.LOGFILE_NAME, "Log File Name (.log)",
                                                 defaultValue="tbk_processing.log")
        self._add_advanced_parameter(parameter)

        parameter = QgsProcessingParameterNumber(self.SIMPLIFICATION_TOLERANCE, "Simplification tolerance [m]",
                                                 type=QgsProcessingParameterNumber.Double, defaultValue=8)
        self._add_advanced_parameter(parameter)

        parameter = QgsProcessingParameterNumber(self.MIN_AREA_M2, "Min. area to eliminate small stands",
                                                 type=QgsProcessingParameterNumber.Integer, defaultValue=1000)
        self._add_advanced_parameter(parameter)

        # Additional parameters
        parameter = QgsProcessingParameterBoolean(self.DEL_TMP, "Delete temporary files and fields", defaultValue=True)
        self._add_advanced_parameter(parameter)

    def processAlgorithm(self, parameters, context, feedback):
        """
        Here is where the processing itself takes place.
        """
        # prepare the algorithm
        self.prepare(parameters, context, feedback)

        # --- get and check input parameters

        params = self._extract_context_params(parameters, context)

        # Handle the working root and temp output folders
        working_root = params.working_root
        ensure_dir(working_root)
        tmp_output_folder = self._get_tmp_output_path(params.working_root)
        ensure_dir(tmp_output_folder)

        # Set the logger
        self._configure_logging(params.working_root, params.logfile_name)
        log = logging.getLogger('Simplify & Clean')

        # Write the used parameters in a toml file
        try:
            write_dict_to_toml_file(params.__dict__, working_root)
        except Exception:
            feedback.pushWarning('The TOML file was not writen in the output folder because an error occurred')

        # ------- TBk Processing --------#
        # --- Simplify & Clean
        log.info('Starting')

        results = post_process(params.working_root, tmp_output_folder, params.min_area_m2,
                               params.simplification_tolerance, params.del_tmp)

        # todo: add the run_stand_classification code in this file, remove all unnecessary code portion and return the
        #  results
        # return results

    def createInstance(self):
        """
        Returns a new algorithm instance
        """
        return TBkSimplifyAndCleanAlgorithm()

    def name(self):
        """
        Returns the algorithm name, used for identifying the algorithm. This
        string should be fixed for the algorithm, and must not be localised.
        The name should be unique within each provider. Names should contain
        lowercase alphanumeric characters only and no spaces or other
        formatting characters.
        """
        return '2 Simplify and Clean'

    def shortHelpString(self):
        """
        Returns a localised short help string for the algorithm.
        """
        return ('Processing of the "raw" TBk classification. This Algorithm eliminates small stands polygons inferior '
                'to the minimum area and simplifies the stand boundaries using the simplification tolerance.')
