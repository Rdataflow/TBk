# -*- coding: utf-8 -*-
"""External call to QGIS to run/test/debug the TBk plugin main algorithm

This script runs TBk algorithm in a QGIS application without UI.

Make sure to run this with a Python environment similar (or identical) to the QGIS Python.
The environment needs to know about QGIS, the QGIS Core Plugins (i.e. Processing, GRASS) and the TBk Plugin.
Set your PYTHONPATH accordingly or use sys.path.append to add paths to these modules as needed.
"""

__author__ = 'Berner Fachhochschule HAFL'
__date__ = '2023-10-18'
__copyright__ = '(C) 2023 by Berner Fachhochschule HAFL'

import sys
from qgis.core import (
    QgsApplication,
    Qgis
)
import pathlib

# get git revision hash
# https://stackoverflow.com/a/56245722/6409572
def get_git_revision(base_path, short=True):
    git_dir = pathlib.Path(base_path) / '.git'
    with (git_dir / 'HEAD').open('r') as head:
        ref = head.readline().split(' ')[-1].strip()

    with (git_dir / ref).open('r') as git_hash:
        if short:
            return git_hash.readline().strip()[:8]
        else:
            return git_hash.readline().strip()

# Path to the TBk plugin folder/repository, containing plugin code and test data
tbk_path = 'C:/dev/hafl/TBk'

# The path to the plugin is environment specific
# Appending it is only necessary if that path is not on the PYTHONPATH. Do so e.g. with:
sys.path.append(tbk_path)
from tbk_qgis.tbk_qgis_provider import TBkProvider


print("\n\n#==============================#")
print("####   TEST TBK ALGORITHM   ####")
print(f"#### git revision: {get_git_revision(tbk_path)} ####")
print("####------------------------####")
print("# imported TBk Provider")
print("# init QGIS Application")

# initialize QGIS Application
# See https://gis.stackexchange.com/a/155852/4972 for details about the prefix
QgsApplication.setPrefixPath('C:/OSGeo4W/apps/qgis-ltr', True)
qgs = QgsApplication([], False)
qgs.initQgis()

print("# load & init Processing")
# The path to the QGIS processing plugin (core) is environment specific
# Appending it is only necessary if that path is not on the PYTHONPATH. Do so e.g. with:
# sys.path.append('C:/OSGeo4W/apps/qgis-ltr/python/plugins')
from processing.core.Processing import Processing
Processing.initialize()

# Add TBk Plugin Provider so that the QGIS instance knows about it's algorithms
provider = TBkProvider()
QgsApplication.processingRegistry().addProvider(provider)

# Get versions of tools
print("####------------------------####")
from grassprovider.Grass7Utils import Grass7Utils
from processing.algs.gdal.GdalUtils import GdalUtils
print(f"# QGIS Version: {Qgis.QGIS_VERSION}")
print(f"# Python Version: {sys.version}")
print(f"# GRASS Version: {Grass7Utils.installedVersion()}")
print(f"# GDAL Version: {GdalUtils.version()}")
print("#==============================#\n")
print("####  call TBk Algorithm    ####")
print("#------------------------------#\n\n")

# Main call of the algorithm
processing.run("TBk:Generate BK", {
    'config_file': f'',  # without config file
    # 'config_file': f'{tbk_path}/tbk_qgis/config/default_input_config.toml', # with config file
    'vhm_10m': f'{tbk_path}/data/tbk_2012/VHM_10m.tif',
    'vhm_150cm': f'{tbk_path}/data/tbk_2012/VHM_150cm.tif',
    'coniferous_raster': f'{tbk_path}/data/tbk_2012/MG_10m.tif',
    'coniferous_raster_for_classification': f'{tbk_path}/data/tbk_2012/MG_10m_binary.tif',
    'perimeter': f'{tbk_path}/data/basedata/waldmaske_hafl.gpkg|layername=waldmaske_hafl',
    'output_root': f'{tbk_path}/data/tbk_test_output',
    'vegZoneDefault': 2, 'vegZoneLayer': None, 'vegZoneLayerField': '',
    'forestSiteDefault': '', 'forestSiteLayer': None, 'forestSiteLayerField': '',
    'useConiferousRasterForClassification': True, 'logfile_name': 'tbk_processing.log',
    'description': 'TBk dataset', 'min_tol': 0.1, 'max_tol': 0.1, 'min_corr': 4,
    'max_corr': 4, 'min_valid_cells': 0.5, 'min_cells_per_stand': 10,
    'min_cells_per_pure_stand': 30, 'vhm_min_height': 0, 'vhm_max_height': 60,
    'simplification_tolerance': 8, 'min_area_m2': 1000,
    'similar_neighbours_min_area': 2000, 'similar_neighbours_hdom_diff_rel': 0.15,
    'calc_mixture_for_main_layer': True, 'del_tmp': True})

