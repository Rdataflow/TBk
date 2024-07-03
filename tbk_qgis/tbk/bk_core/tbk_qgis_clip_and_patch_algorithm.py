#todo
import logging

from qgis.core import (QgsProcessingParameterBoolean,
                       QgsProcessingParameterFeatureSource,
                       QgsProcessingParameterFile,
                       QgsProcessing,
                       QgsProcessingParameterString)
from tbk_qgis.tbk.bk_core.clip_to_perimeter import clip_to_perimeter, eliminate_gaps
from tbk_qgis.tbk.bk_core.tbk_qgis_processing_algorithm import TBkProcessingAlgorithm
from tbk_qgis.tbk.utility.tbk_utilities import ensure_dir


#todo: split in 2 algorithms?
class TBkClipToPerimeterAndEliminateGapsAlgorithm(TBkProcessingAlgorithm):
    """
    todo
    """
    # ------- Define Constants -------#
    # Constants used to refer to parameters and outputs.

    # These constants will be used when calling the algorithm from another algorithm,
    # or when calling from the QGIS console.

    # Directory containing the output files
    OUTPUT = "OUTPUT"
    # Folder for storing all input files and saving output files
    WORKING_ROOT = "working_root"
    # File storing configuration parameters
    CONFIG_FILE = "config_file"
    # Perimeter shapefile to clip final result
    PERIMETER = "perimeter"
    # Default log file name
    LOGFILE_NAME = "logfile_name"

    # Additional parameters
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
                                                     extension='toml',
                                                     optional=True))

        # These parameters are only displayed a config parameter is given
        if not config:
            self.addParameter(QgsProcessingParameterFile(self.WORKING_ROOT,
                                                         "Working root folder. This folder must contain the outputs "
                                                         "from previous steps.",
                                                         behavior=QgsProcessingParameterFile.Folder))
        # Perimeter shapefile to clip final result
        self.addParameter(
            QgsProcessingParameterFeatureSource(self.PERIMETER, "Perimeter shapefile to clip final result",
                                                [QgsProcessing.TypeVectorPolygon]))

        # --- Advanced Parameters

        # Additional parameters
        parameter = QgsProcessingParameterString(self.LOGFILE_NAME, "Log File Name (.log)",
                                                 defaultValue="tbk_processing.log")
        self._add_advanced_parameter(parameter)

        parameter = QgsProcessingParameterBoolean(self.DEL_TMP, "Delete temporary files and fields",
                                                  defaultValue=True)
        self._add_advanced_parameter(parameter)

    def processAlgorithm(self, parameters, context, feedback):
        """
        Here is where the processing itself takes place.
        """
        # --- Get input parameters

        params = self._extract_context_params(parameters, context)

        # Handle the working root and temp output folders
        working_root = params.working_root
        ensure_dir(working_root)
        tmp_output_folder = self._get_tmp_output_path(params.working_root)
        ensure_dir(tmp_output_folder)

        # Set the logger
        self._configure_logging(params.working_root, params.logfile_name)
        log = logging.getLogger('Clip to perimeter and eliminate gaps')  # todo: use self.name()?

        # --- Merge similar neighbours
        log.info('Starting')
        # run clip function
        clip_to_perimeter(working_root, tmp_output_folder, params.perimeter, del_tmp=params.del_tmp)
        # run gaps function
        eliminate_gaps(working_root, tmp_output_folder, params.perimeter, del_tmp=params.del_tmp)

        return {self.WORKING_ROOT: params.working_root}

    def createInstance(self):
        """
        Returns a new algorithm instance
        """
        return TBkClipToPerimeterAndEliminateGapsAlgorithm()

    def name(self):
        """
        Returns the algorithm name, used for identifying the algorithm. This
        string should be fixed for the algorithm, and must not be localised.
        The name should be unique within each provider. Names should contain
        lowercase alphanumeric characters only and no spaces or other
        formatting characters.
        """
        return '4 Clip to perimeter and eliminate gaps'

    #todo
    def shortHelpString(self):
        """
        Returns a localised short help string for the algorithm.
        """
        return ('')
