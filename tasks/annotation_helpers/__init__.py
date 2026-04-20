"""
Annotation Helpers - Modules d'assistance à l'annotation

Ce package contient des outils pour accélérer l'annotation de datasets YOLO:
- SamplingHelper: Échantillonnage intelligent des frames
- AutoAnnotationHelper: Pré-annotation automatique avec YOLO
- TrackingHelper: Propagation des annotations avec suivi d'objets
- InterpolationHelper: Interpolation entre deux frames annotés
"""

from .base_helper import BaseAnnotationHelper, HelperResult
from .sampling_helper import SamplingHelper
from .auto_annotation_helper import AutoAnnotationHelper
from .tracking_helper import TrackingHelper
from .interpolation_helper import InterpolationHelper

__all__ = [
    'BaseAnnotationHelper',
    'HelperResult',
    'SamplingHelper',
    'AutoAnnotationHelper',
    'TrackingHelper',
    'InterpolationHelper'
]